from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Body, Header, HTTPException
from pydantic import BaseModel, Field

from .domain import serialize
from .service import ModelCenterService


class RuntimeConfigIn(BaseModel):
    executable: str | None = None
    working_directory: str | None = None
    base_url: str | None = None
    bind_address: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    launch_arguments: list[str] | None = None


def create_model_center_router(
    service: ModelCenterService,
    prefix: str = "/api/model-center",
    mutation_authorization: Callable[[str | None], dict] | None = None,
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=["model-center"])

    def runtime(runtime_id: str):
        try: return service.runtimes[runtime_id]
        except KeyError: raise HTTPException(404, {"code": "MODEL_CENTER_RUNTIME_NOT_FOUND"}) from None

    def runtime_definition(item):
        value = serialize(item)
        for sensitive_field in ("environment", "executable", "working_directory", "launch_arguments", "model_path", "extra_arguments"):
            value.pop(sensitive_field, None)
        return value

    def require_control(token: str | None):
        authorization = mutation_authorization(token) if mutation_authorization else {"can_mutate": False}
        if not authorization.get("can_mutate"):
            raise HTTPException(401, {"code": "SESSION_REQUIRED"})
        return authorization

    def trusted_runtime_definition(item):
        value = serialize(item)
        value.pop("environment", None)
        return value

    @router.get("/models")
    def models(): return {"items": [service.model(item.id) for item in service.models.values()]}

    @router.get("/models/{model_id}")
    def model(model_id: str):
        try: return service.model(model_id)
        except KeyError: raise HTTPException(404, {"code": "MODEL_CENTER_MODEL_NOT_FOUND"}) from None

    @router.get("/runtimes")
    def runtimes():
        return {"items": [{**runtime_definition(item), "instance": serialize(service.lifecycle.refresh(item.id)) if item.id in service.lifecycle.instances else None, "discovery": service.lifecycle.discover(item)} for item in service.runtimes.values()]}

    @router.get("/runtimes/{runtime_id}")
    def runtime_detail(runtime_id: str):
        item=runtime(runtime_id); return {**runtime_definition(item), "instance": serialize(service.lifecycle.refresh(item.id)) if item.id in service.lifecycle.instances else None, "discovery": service.lifecycle.discover(item)}

    @router.post("/runtimes/{runtime_id}/validate")
    def validate_runtime(runtime_id: str, body: RuntimeConfigIn | None = None):
        item=runtime(runtime_id)
        if body:
            values=body.model_dump(exclude_none=True)
            try:
                item=service.configure_runtime(runtime_id, values)
            except ValueError as exc:
                raise HTTPException(409, {"code": str(exc)}) from exc
        return service.validate_runtime(runtime_id)

    @router.post("/runtimes/{runtime_id}/start")
    def start_runtime(runtime_id: str):
        try: return serialize(service.lifecycle.start(runtime(runtime_id)))
        except ValueError as exc: raise HTTPException(409, {"code": str(exc)}) from exc

    @router.post("/runtimes/{runtime_id}/stop")
    def stop_runtime(runtime_id: str):
        runtime(runtime_id)
        try: return serialize(service.lifecycle.stop(runtime_id))
        except ValueError as exc: raise HTTPException(409, {"code": str(exc)}) from exc

    @router.get("/runtimes/{runtime_id}/configuration")
    def runtime_configuration(runtime_id: str, x_session_token: str | None = Header(default=None, alias="X-Session-Token")):
        require_control(x_session_token)
        return trusted_runtime_definition(runtime(runtime_id))

    @router.put("/runtimes/{runtime_id}/configuration")
    def update_runtime_configuration(runtime_id: str, body: dict = Body(...), x_session_token: str | None = Header(default=None, alias="X-Session-Token")):
        require_control(x_session_token)
        runtime(runtime_id)
        try: return trusted_runtime_definition(service.configure_runtime_profile(runtime_id, body))
        except ValueError as exc: raise HTTPException(409, {"code": str(exc)}) from exc

    @router.get("/runtimes/{runtime_id}/diagnostics")
    def runtime_diagnostics(runtime_id: str, x_session_token: str | None = Header(default=None, alias="X-Session-Token")):
        require_control(x_session_token); runtime(runtime_id)
        return service.diagnostics(runtime_id)

    @router.get("/runtimes/{runtime_id}/logs")
    def runtime_logs(runtime_id: str, x_session_token: str | None = Header(default=None, alias="X-Session-Token")):
        require_control(x_session_token); runtime(runtime_id)
        return {"runtime_id": runtime_id, **service.lifecycle.sanitized_logs(runtime_id)}

    @router.get("/runtimes/{runtime_id}/capabilities")
    def runtime_capabilities(runtime_id: str):
        runtime(runtime_id)
        return serialize(service.capability_snapshot(runtime_id))

    @router.get("/pipelines")
    def pipelines(): return {"items":[serialize(item) for item in service.pipelines.values()]}

    @router.get("/health")
    def health(x_session_token: str | None = Header(default=None, alias="X-Session-Token")):
        authorization = mutation_authorization(x_session_token) if mutation_authorization else {
            "can_mutate": False,
            "mutation_auth_mode": "TRUSTED_SESSION_REQUIRED",
        }
        return {**service.health(), "mutation_authorization": authorization}

    return router
