from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Callable, Protocol

from .local_session_bootstrap import LocalSessionBootstrap
from .runtime_identity import RuntimeIdentity
from .runtime_lifecycle import RuntimeLifecycle


class DesktopBridgeState(StrEnum):
    NEW = "NEW"
    STARTING = "STARTING"
    READY = "READY"
    FAILED = "FAILED"
    STOPPED = "STOPPED"


@dataclass(frozen=True)
class DesktopHostLaunch:
    frontend_origin: str
    backend_origin: str
    runtime_instance_id: str
    bootstrap_secret: str
    webview_profile_directory: str


@dataclass(frozen=True)
class DesktopFailure:
    code: str
    author_message: str


class DesktopHostBoundary(Protocol):
    def start(self, launch: DesktopHostLaunch) -> None: ...
    def wait_session_ready(self, timeout_seconds: float) -> bool: ...
    def block_actions(self) -> None: ...
    def close(self) -> None: ...
    def is_running(self) -> bool: ...


class PackagedDesktopLifecycle:
    """Composes Phase 2 ownership and Phase 3 bootstrap without a second runtime."""

    def __init__(
        self, *, runtime: RuntimeLifecycle, host: DesktopHostBoundary,
        bootstrap_factory: Callable[[RuntimeIdentity], LocalSessionBootstrap],
        frontend_origin: str, backend_origin: str, ready_timeout_seconds: float = 30.0,
    ):
        self.runtime = runtime
        self.host = host
        self.bootstrap_factory = bootstrap_factory
        self.frontend_origin = frontend_origin
        self.backend_origin = backend_origin
        self.ready_timeout_seconds = ready_timeout_seconds
        self.bootstrap: LocalSessionBootstrap | None = None
        self.state = DesktopBridgeState.NEW
        self.events: list[str] = []

    def startup(self) -> RuntimeIdentity:
        self.state = DesktopBridgeState.STARTING
        stage = "runtime"
        runtime_started = False
        try:
            identity = self.runtime.startup()
            runtime_started = True
            self.events.append("runtime.services.ready")
            stage = "bootstrap"
            self.bootstrap = self.bootstrap_factory(identity)
            secret = self.bootstrap.take_launcher_secret()
            self.events.append("bootstrap.prepared")
            stage = "desktop"
            self.host.start(DesktopHostLaunch(
                frontend_origin=self.frontend_origin,
                backend_origin=self.backend_origin,
                runtime_instance_id=identity.runtime_instance_id,
                bootstrap_secret=secret,
                webview_profile_directory=str(self.runtime.paths.cache / "WebView2" / identity.runtime_instance_id),
            ))
            self.events.append("desktop.started")
            stage = "session"
            if not self.host.wait_session_ready(self.ready_timeout_seconds):
                raise RuntimeError("本地安全会话初始化失败，请关闭程序后重新打开。")
            if not self.host.is_running():
                raise RuntimeError("应用窗口启动失败，请重新启动 AI-Novel-Studio。")
            self.events.append("trusted.session.active")
            self.state = DesktopBridgeState.READY
            self.events.append("application.ready")
            return identity
        except Exception:
            self.state = DesktopBridgeState.FAILED
            self._rollback(runtime_started=runtime_started)
            message = {
                "runtime": "写作服务启动失败。你的小说数据未被删除。",
                "bootstrap": "本地安全会话初始化失败，请关闭程序后重新打开。",
                "desktop": "应用窗口启动失败，请重新启动 AI-Novel-Studio。",
                "session": "本地安全会话初始化失败，请关闭程序后重新打开。",
            }[stage]
            raise RuntimeError(message) from None

    def shutdown(self) -> None:
        if self.state is DesktopBridgeState.STOPPED:
            return
        self.host.block_actions()
        self.events.append("frontend.actions.blocked")
        self.host.close()
        self.events.append("desktop.closed")
        if self.bootstrap is not None:
            self.bootstrap.invalidate()
            self.events.append("session.invalidated")
        self.runtime.shutdown()
        self.events.append("runtime.stopped")
        self.state = DesktopBridgeState.STOPPED

    def check_host(self) -> DesktopFailure | None:
        if self.state is DesktopBridgeState.READY and not self.host.is_running():
            self.state = DesktopBridgeState.FAILED
            if self.bootstrap is not None:
                self.bootstrap.invalidate()
            self.runtime.shutdown()
            self.events.append("host.crash.cleanup.complete")
            return DesktopFailure("DESKTOP_HOST_EXITED", "应用窗口启动失败，请重新启动 AI-Novel-Studio。")
        return None

    def _rollback(self, *, runtime_started: bool) -> None:
        try:
            self.host.close()
        finally:
            if self.bootstrap is not None:
                self.bootstrap.invalidate()
            if runtime_started:
                self.runtime.shutdown()
            self.events.append("startup.rollback.complete")
