from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol

from .paths import WindowsPackagingPaths
from .runtime_identity import (
    ProcessIdentity,
    ProcessInspector,
    RuntimeIdentity,
    RuntimeMetadata,
    RuntimeMetadataStore,
    RuntimeRole,
    RuntimeState,
    process_metadata,
    validate_process_ownership,
)
from .windows_primitives import LoopbackPortReservations


class MutexBoundary(Protocol):
    def acquire(self) -> None: ...
    def release(self) -> None: ...


class JobBoundary(Protocol):
    def assign_pid(self, pid: int) -> None: ...
    def terminate(self, exit_code: int = 1) -> None: ...
    def close(self) -> None: ...


class ManagedChild(Protocol):
    identity: ProcessIdentity
    def wait_ready(self, timeout_seconds: float) -> bool: ...
    def request_shutdown(self) -> None: ...
    def wait_exited(self, timeout_seconds: float) -> bool: ...
    def force_terminate(self) -> None: ...
    def is_running(self) -> bool: ...


class ProcessFactory(Protocol):
    def start(
        self, role: RuntimeRole, port: int, runtime: RuntimeIdentity,
        paths: WindowsPackagingPaths,
    ) -> ManagedChild: ...


class PortAllocator(Protocol):
    def reserve(self) -> LoopbackPortReservations: ...


@dataclass(frozen=True)
class RuntimeFailure:
    code: str
    message: str
    role: RuntimeRole | None = None
    can_restart: bool = True


class RuntimeLifecycle:
    STARTUP_ORDER = (RuntimeRole.POSTGRESQL, RuntimeRole.BACKEND, RuntimeRole.FRONTEND)
    SHUTDOWN_ORDER = (RuntimeRole.FRONTEND, RuntimeRole.BACKEND, RuntimeRole.POSTGRESQL)

    def __init__(
        self, *, paths: WindowsPackagingPaths, mutex: MutexBoundary,
        job: JobBoundary, port_allocator: PortAllocator, process_factory: ProcessFactory,
        inspector: ProcessInspector, metadata_store: RuntimeMetadataStore | None = None,
        readiness_timeout_seconds: float = 30.0, shutdown_timeout_seconds: float = 15.0,
        startup_order: Iterable[RuntimeRole] | None = None,
    ):
        self.paths = paths
        self.mutex = mutex
        self.job = job
        self.port_allocator = port_allocator
        self.process_factory = process_factory
        self.inspector = inspector
        self.metadata_store = metadata_store or RuntimeMetadataStore(paths.runtime)
        self.readiness_timeout_seconds = readiness_timeout_seconds
        self.shutdown_timeout_seconds = shutdown_timeout_seconds
        self.startup_order = tuple(startup_order or self.STARTUP_ORDER)
        if not self.startup_order or len(set(self.startup_order)) != len(self.startup_order):
            raise ValueError("startup_order must contain unique runtime roles")
        self.shutdown_order = tuple(reversed(self.startup_order))
        self.state = RuntimeState.NEW
        self.identity: RuntimeIdentity | None = None
        self.children: dict[RuntimeRole, ManagedChild] = {}
        self.reservations: LoopbackPortReservations | None = None
        self.events: list[str] = []
        self.actions_blocked = False

    def startup(self) -> RuntimeIdentity:
        if self.state not in {RuntimeState.NEW, RuntimeState.STOPPED}:
            raise RuntimeError(f"Runtime cannot start from {self.state}")
        self.mutex.acquire()
        self.events.append("mutex.acquired")
        self.identity = RuntimeIdentity.create()
        self.state = RuntimeState.STARTING
        try:
            self.paths.validate()
            self.events.append("directories.validated")
            self.reservations = self.port_allocator.reserve()
            self.events.append("ports.reserved")
            self._save_metadata()
            for role in self.startup_order:
                self.reservations.release(role)
                self.events.append(f"port.released:{role.value}")
                child = self.process_factory.start(
                    role, self.reservations.ports[role], self.identity, self.paths
                )
                self.children[role] = child
                self.job.assign_pid(child.identity.pid)
                self.events.append(f"job.assigned:{role.value}")
                validate_process_ownership(
                    child.identity, self.inspector.inspect(child.identity.pid), self.identity
                )
                self.events.append(f"ownership.validated:{role.value}")
                self._save_metadata()
                if not child.wait_ready(self.readiness_timeout_seconds):
                    raise RuntimeError(f"{role.value} readiness timed out")
                self.events.append(f"ready:{role.value}")
            self.state = RuntimeState.READY
            self.actions_blocked = False
            self._save_metadata()
            self.events.append("runtime.ready")
            return self.identity
        except Exception:
            self.state = RuntimeState.FAILED
            self.actions_blocked = True
            self._cleanup_after_failed_startup()
            raise

    def shutdown(self) -> None:
        if self.state in {RuntimeState.NEW, RuntimeState.STOPPED}:
            return
        self.actions_blocked = True
        self.state = RuntimeState.STOPPING
        self.events.append("actions.blocked")
        self._save_metadata()
        failure: Exception | None = None
        for role in self.shutdown_order:
            child = self.children.get(role)
            if child is None:
                continue
            try:
                child.request_shutdown()
                self.events.append(f"shutdown.requested:{role.value}")
                if not child.wait_exited(self.shutdown_timeout_seconds):
                    child.force_terminate()
                    self.events.append(f"shutdown.forced:{role.value}")
                if child.is_running():
                    raise RuntimeError(f"{role.value} did not exit")
                self.events.append(f"stopped:{role.value}")
            except Exception as exc:
                failure = failure or exc
        if failure is not None or any(child.is_running() for child in self.children.values()):
            try:
                self.job.terminate()
                self.events.append("job.terminated")
            except Exception as exc:
                failure = failure or exc
        self.children.clear()
        self._finalize_ownership()
        self.state = RuntimeState.FAILED if failure else RuntimeState.STOPPED
        if failure is not None:
            raise failure

    def check_for_child_crash(self) -> RuntimeFailure | None:
        for role in self.startup_order:
            child = self.children.get(role)
            if child is not None and not child.is_running():
                self.state = RuntimeState.FAILED
                self.actions_blocked = True
                self._save_metadata()
                return RuntimeFailure(
                    code="RUNTIME_CHILD_EXITED",
                    message=f"{_role_label(role)}意外停止。作品数据未被删除，可以安全重启应用。",
                    role=role,
                )
        return None

    def _cleanup_after_failed_startup(self) -> None:
        if self.reservations is not None:
            self.reservations.close()
        requires_job_termination = False
        for role in self.shutdown_order:
            child = self.children.get(role)
            if child is None:
                continue
            try:
                child.request_shutdown()
                if not child.wait_exited(self.shutdown_timeout_seconds):
                    child.force_terminate()
                requires_job_termination = requires_job_termination or child.is_running()
            except Exception:
                requires_job_termination = True
        if requires_job_termination:
            try:
                self.job.terminate()
            except Exception:
                pass
        self.children.clear()
        self._finalize_ownership()
        self.events.append("startup.rollback.complete")

    def _save_metadata(self) -> None:
        if self.identity is None:
            return
        ports = {}
        if self.reservations is not None:
            ports = {role.value: port for role, port in self.reservations.ports.items()}
        self.metadata_store.save(RuntimeMetadata(
            runtime_instance_id=self.identity.runtime_instance_id,
            state=self.state,
            launcher=self.identity.public_metadata(),
            ports=ports,
            children=[process_metadata(child.identity) for child in self.children.values()],
        ))

    def _finalize_ownership(self) -> None:
        if self.reservations is not None:
            self.reservations.close()
        cleanup_error: Exception | None = None
        try:
            self.metadata_store.clear()
            self.events.append("metadata.cleared")
        except Exception as exc:
            cleanup_error = exc
        try:
            self.job.close()
            self.events.append("job.closed")
        except Exception as exc:
            cleanup_error = cleanup_error or exc
        try:
            self.mutex.release()
            self.events.append("mutex.released")
        except Exception as exc:
            cleanup_error = cleanup_error or exc
        if cleanup_error is not None:
            raise cleanup_error


class DefaultPortAllocator:
    def reserve(self) -> LoopbackPortReservations:
        from .windows_primitives import reserve_loopback_ports
        return reserve_loopback_ports()


def _role_label(role: RuntimeRole) -> str:
    return {
        RuntimeRole.POSTGRESQL: "本地数据库",
        RuntimeRole.BACKEND: "写作服务",
        RuntimeRole.FRONTEND: "应用界面",
    }[role]
