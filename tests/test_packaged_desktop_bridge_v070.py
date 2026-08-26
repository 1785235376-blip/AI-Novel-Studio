from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.packaging.desktop_bridge import DesktopBridgeState, PackagedDesktopLifecycle
from app.packaging.local_session_bootstrap import LocalSessionBootstrap, TrustedLocalIdentity
from app.packaging.runtime_identity import RuntimeIdentity
from app.trusted_sessions import TrustedSessionResolver


FRONTEND = "http://127.0.0.1:4173"
BACKEND = "http://127.0.0.1:8000"


class Runtime:
    def __init__(self, root):
        self.paths = SimpleNamespace(cache=root / "Cache", user_data=root / "UserData")
        self.identity = RuntimeIdentity.create()
        self.calls = []
    def startup(self): self.calls.append("startup"); return self.identity
    def shutdown(self): self.calls.append("shutdown")


class BrokenRuntime(Runtime):
    def startup(self): self.calls.append("startup"); raise RuntimeError("raw backend detail")


class Host:
    def __init__(self, manager_ref, *, ready=True, running=True):
        self.manager_ref = manager_ref; self.ready = ready; self.running = running; self.calls = []; self.launch = None
    def start(self, launch):
        self.calls.append("start"); self.launch = launch
        if self.ready:
            manager = self.manager_ref[0]
            self.receipt = manager.exchange(
                bootstrap_secret=launch.bootstrap_secret,
                runtime_instance_id=launch.runtime_instance_id,
                origin=launch.frontend_origin,
                remote_host="127.0.0.1",
            )
    def wait_session_ready(self, _timeout): self.calls.append("wait_session_ready"); return self.ready
    def block_actions(self): self.calls.append("block_actions")
    def close(self): self.calls.append("close"); self.running = False
    def is_running(self): return self.running


def setup_bridge(tmp_path, *, ready=True, running=True):
    sessions = TrustedSessionResolver(); manager_ref = []
    runtime = Runtime(tmp_path); host = Host(manager_ref, ready=ready, running=running)
    def factory(identity):
        manager = LocalSessionBootstrap(
            runtime=identity, sessions=sessions,
            trusted_identity=TrustedLocalIdentity("author", "workspace-a"),
            expected_origin=FRONTEND,
        )
        manager_ref.append(manager); return manager
    bridge = PackagedDesktopLifecycle(
        runtime=runtime, host=host, bootstrap_factory=factory,
        frontend_origin=FRONTEND, backend_origin=BACKEND,
    )
    return bridge, runtime, host, sessions, manager_ref


def test_ready_requires_real_one_time_session_handoff(tmp_path):
    bridge, runtime, host, sessions, managers = setup_bridge(tmp_path)
    identity = bridge.startup()
    assert bridge.state is DesktopBridgeState.READY
    assert bridge.events == [
        "runtime.services.ready", "bootstrap.prepared", "desktop.started",
        "trusted.session.active", "application.ready",
    ]
    assert host.launch.runtime_instance_id == identity.runtime_instance_id
    assert host.launch.frontend_origin == FRONTEND
    assert host.launch.backend_origin == BACKEND
    assert host.launch.webview_profile_directory.startswith(str(runtime.paths.cache))
    assert str(runtime.paths.user_data) not in host.launch.webview_profile_directory
    assert sessions.resolve(host.receipt.session_token).workspace_id == "workspace-a"
    with pytest.raises(Exception):
        managers[0].exchange(
            bootstrap_secret=host.launch.bootstrap_secret,
            runtime_instance_id=identity.runtime_instance_id,
            origin=FRONTEND, remote_host="127.0.0.1",
        )


def test_bootstrap_or_backend_failure_prevents_ready_and_rolls_back(tmp_path):
    bridge, runtime, host, sessions, managers = setup_bridge(tmp_path, ready=False)
    with pytest.raises(RuntimeError, match="本地安全会话初始化失败"):
        bridge.startup()
    assert bridge.state is DesktopBridgeState.FAILED
    assert runtime.calls == ["startup", "shutdown"]
    assert host.calls[-1] == "close"
    assert managers[0].state.value == "INVALIDATED"

    sessions = TrustedSessionResolver(); manager_ref=[]; runtime2=BrokenRuntime(tmp_path); host2=Host(manager_ref)
    bridge2=PackagedDesktopLifecycle(
        runtime=runtime2, host=host2, bootstrap_factory=lambda _identity: None,
        frontend_origin=FRONTEND, backend_origin=BACKEND,
    )
    with pytest.raises(RuntimeError, match="写作服务启动失败。你的小说数据未被删除。") as error:
        bridge2.startup()
    assert "raw backend detail" not in str(error.value)


def test_shutdown_order_revokes_session_before_runtime_shutdown(tmp_path):
    bridge, runtime, host, sessions, _ = setup_bridge(tmp_path)
    bridge.startup(); token = host.receipt.session_token
    bridge.shutdown()
    assert bridge.state is DesktopBridgeState.STOPPED
    assert host.calls[-2:] == ["block_actions", "close"]
    assert bridge.events[-4:] == [
        "frontend.actions.blocked", "desktop.closed", "session.invalidated", "runtime.stopped",
    ]
    assert runtime.calls == ["startup", "shutdown"]
    with pytest.raises(KeyError): sessions.resolve(token)


def test_host_crash_invalidates_session_without_touching_userdata(tmp_path):
    bridge, runtime, host, sessions, _ = setup_bridge(tmp_path)
    runtime.paths.user_data.mkdir(); marker = runtime.paths.user_data / "novel.keep"; marker.write_text("safe")
    bridge.startup(); token = host.receipt.session_token; host.running = False
    failure = bridge.check_host()
    assert failure and failure.code == "DESKTOP_HOST_EXITED"
    assert failure.author_message == "应用窗口启动失败，请重新启动 AI-Novel-Studio。"
    with pytest.raises(KeyError): sessions.resolve(token)
    assert marker.read_text() == "safe"
    assert runtime.calls == ["startup", "shutdown"]
    assert bridge.events[-1] == "host.crash.cleanup.complete"


def test_bridge_events_and_launch_metadata_do_not_expose_security_material(tmp_path):
    bridge, _, host, _, _ = setup_bridge(tmp_path)
    identity = bridge.startup()
    serialized = "\n".join(bridge.events)
    assert host.launch.bootstrap_secret not in serialized
    assert identity.ownership_nonce not in serialized
    assert "session_token" not in serialized
    assert "DEEPSEEK_KEY_SENTINEL" not in serialized
