from __future__ import annotations

from collections.abc import Callable
from threading import RLock

from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict

from .local_session_bootstrap import BootstrapDenied, LocalSessionBootstrap
from .initial_workspace import InitialWorkspaceProvisioningDenied


class BootstrapExchangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bootstrap_secret: str
    runtime_instance_id: str


class BootstrapExchangeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_token: str


class InitialWorkspaceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InitialWorkspaceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str


class PackagedBootstrapRegistry:
    """Process-local handoff configured by the future launcher adapter."""

    def __init__(self, *, expected_origin: str | Callable[[], str] | None = None):
        self._manager: LocalSessionBootstrap | None = None
        self._lock = RLock()
        self._expected_origin = expected_origin

    def configure(self, manager: LocalSessionBootstrap) -> None:
        with self._lock:
            if self._manager is not None:
                raise RuntimeError("packaged bootstrap is already configured")
            expected = self._expected_origin() if callable(self._expected_origin) else self._expected_origin
            if expected is not None and manager.expected_origin != expected.rstrip("/"):
                raise ValueError("packaged bootstrap origin must match the configured frontend origin")
            self._manager = manager

    def current(self) -> LocalSessionBootstrap | None:
        with self._lock:
            return self._manager

    def clear(self) -> None:
        with self._lock:
            manager, self._manager = self._manager, None
        if manager is not None:
            manager.invalidate()


def create_packaged_bootstrap_router(
    registry: PackagedBootstrapRegistry, *, enabled: Callable[[], bool] = lambda: True,
    initial_workspace_provisioner=None, prefix: str = "/api/packaged",
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=["packaged-bootstrap"])

    @router.post("/bootstrap", response_model=BootstrapExchangeResponse)
    def exchange(
        body: BootstrapExchangeRequest, request: Request, response: Response,
        origin: str | None = Header(None),
    ) -> BootstrapExchangeResponse:
        manager = registry.current() if enabled() else None
        if manager is None:
            raise HTTPException(404, {"code": "PACKAGED_BOOTSTRAP_DISABLED"})
        try:
            receipt = manager.exchange(
                bootstrap_secret=body.bootstrap_secret,
                runtime_instance_id=body.runtime_instance_id,
                origin=origin,
                remote_host=request.client.host if request.client else None,
            )
        except BootstrapDenied as exc:
            status = 403 if exc.code in {"BOOTSTRAP_LOOPBACK_REQUIRED", "BOOTSTRAP_ORIGIN_DENIED"} else 401
            raise HTTPException(status, {"code": exc.code, "detail": exc.safe_message}) from exc
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["Referrer-Policy"] = "no-referrer"
        return BootstrapExchangeResponse(session_token=receipt.session_token)

    @router.post("/initial-workspace", response_model=InitialWorkspaceResponse)
    def initial_workspace(
        body: InitialWorkspaceRequest,
        x_session_token: str | None = Header(None),
    ) -> InitialWorkspaceResponse:
        manager = registry.current() if enabled() else None
        if manager is None or initial_workspace_provisioner is None:
            raise HTTPException(404, {"code": "PACKAGED_PROVISIONING_DISABLED"})
        try:
            actor = manager.resolve_issued_session(x_session_token)
            workspace = initial_workspace_provisioner.provision(actor)
        except BootstrapDenied as exc:
            raise HTTPException(401, {"code": exc.code, "detail": exc.safe_message}) from exc
        except InitialWorkspaceProvisioningDenied as exc:
            raise HTTPException(409, {"code": "INITIAL_WORKSPACE_NOT_ELIGIBLE", "detail": "无法建立初始创作空间。"}) from exc
        return InitialWorkspaceResponse(id=workspace["id"], name=workspace["name"])

    return router
