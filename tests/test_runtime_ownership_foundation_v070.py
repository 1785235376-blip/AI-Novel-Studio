from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

from app.packaging.paths import WindowsPackagingPaths
from app.packaging.runtime_identity import (
    ProcessIdentity,
    RuntimeIdentity,
    RuntimeMetadata,
    RuntimeMetadataStore,
    RuntimeRole,
    RuntimeState,
    StaleRecoveryResult,
    process_metadata,
    recover_stale_runtime_state,
    validate_process_ownership,
)
from app.packaging.runtime_lifecycle import RuntimeLifecycle
from app.packaging.windows_primitives import (
    PortConflictError,
    SingleInstanceError,
    WindowsJobObject,
    WindowsNamedMutex,
    WindowsProcessInspector,
    product_mutex_name,
    reserve_loopback_ports,
)


class FakeMutex:
    def __init__(self): self.held=False; self.events=[]
    def acquire(self):
        if self.held: raise SingleInstanceError("already running")
        self.held=True; self.events.append("acquire")
    def release(self): self.held=False; self.events.append("release")


class FakeInspector:
    def __init__(self): self.processes={}
    def inspect(self,pid): return self.processes.get(pid)


class FakeChild:
    def __init__(self,identity,events,ready=True):
        self.identity=identity;self.events=events;self.ready=ready;self.running=True
    def wait_ready(self,timeout_seconds): self.events.append(f"wait:{self.identity.role.value}");return self.ready
    def request_shutdown(self): self.events.append(f"request:{self.identity.role.value}");self.running=False
    def wait_exited(self,timeout_seconds): self.events.append(f"exit:{self.identity.role.value}");return not self.running
    def force_terminate(self): self.events.append(f"force:{self.identity.role.value}");self.running=False
    def is_running(self): return self.running


class StubbornChild(FakeChild):
    def request_shutdown(self): self.events.append(f"request:{self.identity.role.value}")
    def wait_exited(self,timeout_seconds): return False
    def force_terminate(self): self.events.append(f"force:{self.identity.role.value}")


class FakeFactory:
    def __init__(self,inspector,events,fail_role=None):
        self.inspector=inspector;self.events=events;self.fail_role=fail_role;self.next_pid=2000;self.children={}
    def start(self,role,port,runtime,paths):
        self.events.append(f"start:{role.value}")
        identity=ProcessIdentity(
            role=role,pid=self.next_pid,creation_timestamp=time.time(),
            executable_path=str(paths.application/f"{role.value}.exe"),parent_pid=runtime.launcher_pid,
            runtime_instance_id=runtime.runtime_instance_id,
            ownership_nonce_hash=runtime.ownership_nonce_hash,
        )
        self.next_pid+=1
        child=FakeChild(identity,self.events,ready=role!=self.fail_role)
        self.children[identity.pid]=child;self.inspector.processes[identity.pid]=identity
        return child


class FakeJob:
    def __init__(self,processes): self.pids=[];self.closed=False;self.processes=processes
    def assign_pid(self,pid): self.pids.append(pid)
    def terminate(self,exit_code=1):
        for pid in self.pids:
            if pid in self.processes:
                self.processes[pid].force_terminate();self.processes[pid].running=False
    def close(self): self.closed=True
    def simulate_owner_loss(self): self.terminate()


class FakePortAllocator:
    """Test-owned port numbers for lifecycle *order* tests.

    Does not bind sockets, detect conflicts, or exercise reservation close.
    Real exclusive loopback bind is covered only by the Windows-only test.
    """
    def reserve(self):
        from app.packaging.windows_primitives import LoopbackPortReservations
        return LoopbackPortReservations(
            sockets={},
            ports={
                RuntimeRole.POSTGRESQL: 55101,
                RuntimeRole.BACKEND: 55102,
                RuntimeRole.FRONTEND: 55103,
            },
        )


def _paths(tmp_path):
    return WindowsPackagingPaths.resolve(
        local_app_data=tmp_path/"LocalAppData",user_profile=tmp_path/"User"
    )


def _lifecycle(tmp_path,fail_role=None):
    paths=_paths(tmp_path);events=[];inspector=FakeInspector();factory=FakeFactory(inspector,events,fail_role)
    job=FakeJob(factory.children);mutex=FakeMutex()
    lifecycle=RuntimeLifecycle(
        paths=paths,mutex=mutex,job=job,port_allocator=FakePortAllocator(),
        process_factory=factory,inspector=inspector,readiness_timeout_seconds=.1,
        shutdown_timeout_seconds=.1,
    )
    return lifecycle,paths,events,factory,job,mutex,inspector


def test_runtime_identity_is_unique_and_public_metadata_hides_raw_nonce():
    one=RuntimeIdentity.create();two=RuntimeIdentity.create()
    assert one.runtime_instance_id!=two.runtime_instance_id
    assert one.ownership_nonce!=two.ownership_nonce
    serialized=json.dumps(one.public_metadata())
    assert one.ownership_nonce not in serialized
    assert one.ownership_nonce_hash in serialized
    assert one.launcher_pid==os.getpid()


@pytest.mark.skipif(os.name!="nt",reason="Windows named mutex contract")
def test_named_mutex_is_deterministic_per_user_and_single_instance():
    name=product_mutex_name()+"."+uuid.uuid4().hex
    first=WindowsNamedMutex(name);second=WindowsNamedMutex(name)
    first.acquire()
    try:
        with pytest.raises(SingleInstanceError):second.acquire()
    finally:
        first.release();second.release()
    third=WindowsNamedMutex(name);third.acquire();third.release()


def test_process_ownership_requires_all_identity_dimensions():
    runtime=RuntimeIdentity.create()
    expected=ProcessIdentity(
        RuntimeRole.BACKEND,44,100.0,"C:/runtime/backend.exe",runtime.launcher_pid,
        runtime.runtime_instance_id,runtime.ownership_nonce_hash,
    )
    validate_process_ownership(expected,expected,runtime)
    wrong=ProcessIdentity(
        RuntimeRole.BACKEND,44,100.0,"C:/other/backend.exe",runtime.launcher_pid,
        runtime.runtime_instance_id,runtime.ownership_nonce_hash,
    )
    with pytest.raises(ValueError,match="executable_path"):
        validate_process_ownership(expected,wrong,runtime)


def test_non_loopback_host_is_rejected():
    with pytest.raises(ValueError, match="127.0.0.1"):
        reserve_loopback_ports(host="0.0.0.0")


@pytest.mark.skipif(
    os.name != "nt",
    reason=(
        "Windows exclusive loopback port reservation is not executed on this "
        "platform. Missing socket.SO_EXCLUSIVEADDRUSE AttributeError on Linux "
        "is an implementation accident, not a documented unsupported-platform contract."
    ),
)
def test_windows_loopback_ports_are_unique_and_conflicts_fail_closed():
    reservations = reserve_loopback_ports()
    try:
        assert len(set(reservations.ports.values())) == 3
        for reserved in reservations.sockets.values():
            assert reserved.getsockname()[0] == "127.0.0.1"
    finally:
        reservations.close()
    held = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    held.bind(("127.0.0.1", 0))
    held.listen(1)
    try:
        with pytest.raises(PortConflictError):
            reserve_loopback_ports(
                roles=(RuntimeRole.BACKEND,),
                requested={RuntimeRole.BACKEND: held.getsockname()[1]},
            )
    finally:
        held.close()


def test_startup_and_shutdown_follow_required_order(tmp_path):
    lifecycle,paths,events,factory,job,mutex,_=_lifecycle(tmp_path)
    lifecycle.startup()
    assert lifecycle.state is RuntimeState.READY
    assert events[:6]==[
        "start:postgresql","wait:postgresql","start:backend","wait:backend",
        "start:frontend","wait:frontend",
    ]
    assert len(job.pids)==3 and mutex.held
    assert RuntimeMetadataStore(paths.runtime).load().state is RuntimeState.READY
    lifecycle.shutdown()
    assert events[-6:]==[
        "request:frontend","exit:frontend","request:backend","exit:backend",
        "request:postgresql","exit:postgresql",
    ]
    assert lifecycle.state is RuntimeState.STOPPED
    assert lifecycle.actions_blocked and not mutex.held and job.closed
    assert RuntimeMetadataStore(paths.runtime).load() is None


def test_failed_startup_rolls_back_children_metadata_and_mutex(tmp_path):
    lifecycle,paths,_,factory,job,mutex,_=_lifecycle(tmp_path,RuntimeRole.BACKEND)
    with pytest.raises(RuntimeError,match="backend readiness"):
        lifecycle.startup()
    assert lifecycle.state is RuntimeState.FAILED
    assert not mutex.held and job.closed and not factory.children[2000].running
    assert not factory.children[2001].running
    assert RuntimeMetadataStore(paths.runtime).load() is None


def test_launcher_loss_job_boundary_prevents_orphans(tmp_path):
    lifecycle,_,_,factory,job,_,_=_lifecycle(tmp_path)
    lifecycle.startup();job.simulate_owner_loss()
    assert all(not child.running for child in factory.children.values())


def test_failed_graceful_shutdown_uses_job_boundary_and_releases_mutex(tmp_path):
    lifecycle,paths,events,factory,job,mutex,_=_lifecycle(tmp_path)
    lifecycle.startup()
    backend=factory.children[2001]
    stubborn=StubbornChild(backend.identity,events)
    factory.children[2001]=stubborn;lifecycle.children[RuntimeRole.BACKEND]=stubborn
    with pytest.raises(RuntimeError,match="backend did not exit"):
        lifecycle.shutdown()
    assert "job.terminated" in lifecycle.events
    assert not stubborn.running and not mutex.held and job.closed
    assert RuntimeMetadataStore(paths.runtime).load() is None


def test_child_crash_reports_chinese_recoverable_error_without_data_loss(tmp_path):
    lifecycle,paths,_,factory,_,_,_=_lifecycle(tmp_path)
    paths.novel_data.mkdir(parents=True);novel=paths.novel_data/"novel.json";novel.write_text("preserve",encoding="utf-8")
    lifecycle.startup();factory.children[2001].running=False
    failure=lifecycle.check_for_child_crash()
    assert failure and failure.role is RuntimeRole.BACKEND and failure.can_restart
    assert "作品数据未被删除" in failure.message
    assert novel.read_text(encoding="utf-8")=="preserve"


def test_stale_metadata_clears_only_when_recorded_processes_are_gone(tmp_path):
    paths=_paths(tmp_path);store=RuntimeMetadataStore(paths.runtime);runtime=RuntimeIdentity.create()
    process=ProcessIdentity(
        RuntimeRole.POSTGRESQL,77,123.0,"C:/runtime/postgres.exe",runtime.launcher_pid,
        runtime.runtime_instance_id,runtime.ownership_nonce_hash,
    )
    store.save(RuntimeMetadata(
        runtime.runtime_instance_id,RuntimeState.FAILED,runtime.public_metadata(),
        children=[process_metadata(process)],
    ))
    inspector=FakeInspector();inspector.processes[77]=process
    assert recover_stale_runtime_state(store,inspector) is StaleRecoveryResult.OWNED_PROCESS_STILL_RUNNING
    assert store.load() is not None
    inspector.processes.clear()
    assert recover_stale_runtime_state(store,inspector) is StaleRecoveryResult.CLEARED
    assert store.load() is None


def test_runtime_metadata_is_transient_and_provider_secret_free(tmp_path,monkeypatch):
    sentinel="DEEPSEEK_SECRET_SENTINEL";monkeypatch.setenv("DEEPSEEK_API_KEY",sentinel)
    lifecycle,paths,_,_,_,_,_=_lifecycle(tmp_path);lifecycle.startup()
    payload=(paths.runtime/"runtime-ownership.json").read_text(encoding="utf-8")
    assert sentinel not in payload and "DEEPSEEK_API_KEY" not in payload
    assert "ownership_nonce\"" not in payload
    assert "ownership_nonce_hash" in payload
    lifecycle.shutdown()


@pytest.mark.skipif(os.name!="nt",reason="Windows Job Object contract")
def test_windows_job_object_can_be_created_and_closed_without_children():
    job=WindowsJobObject(name=f"AI-Novel-Studio.Test.{uuid.uuid4().hex}")
    job.close();job.close()


@pytest.mark.skipif(os.name!="nt",reason="Windows Job Object contract")
def test_windows_job_object_kills_child_when_owner_handle_is_lost():
    child=subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"])
    try:
        job=WindowsJobObject(name=f"AI-Novel-Studio.Test.{uuid.uuid4().hex}")
        job.assign_pid(child.pid)
        job.close()
        child.wait(timeout=5)
        assert child.poll() is not None
    finally:
        if child.poll() is None:
            child.kill();child.wait(timeout=5)


@pytest.mark.skipif(os.name!="nt",reason="Windows process identity contract")
def test_windows_process_inspector_reads_executable_creation_and_parent_identity():
    runtime=RuntimeIdentity.create()
    child=subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"])
    try:
        inspector=WindowsProcessInspector();inspector.register(child.pid,RuntimeRole.BACKEND,runtime)
        actual=inspector.inspect(child.pid)
        assert actual is not None
        assert actual.pid==child.pid and actual.parent_pid==os.getpid()
        assert Path(actual.executable_path).resolve()==Path(sys.executable).resolve()
        assert actual.creation_timestamp>0
        assert actual.runtime_instance_id==runtime.runtime_instance_id
        assert actual.ownership_nonce_hash==runtime.ownership_nonce_hash
    finally:
        child.kill();child.wait(timeout=5)
