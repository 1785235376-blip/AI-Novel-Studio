from __future__ import annotations

from fastapi import APIRouter, HTTPException
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


def create_model_center_router(service: ModelCenterService, prefix: str = "/api/model-center") -> APIRouter:
    router = APIRouter(prefix=prefix, tags=["model-center"])

    def runtime(runtime_id: str):
        try: return service.runtimes[runtime_id]
        except KeyError: raise HTTPException(404, {"code": "MODEL_CENTER_RUNTIME_NOT_FOUND"}) from None

    @router.get("/models")
    def models(): return {"items": [service.model(item.id) for item in service.models.values()]}

    @router.get("/models/{model_id}")
    def model(model_id: str):
        try: return service.model(model_id)
        except KeyError: raise HTTPException(404, {"code": "MODEL_CENTER_MODEL_NOT_FOUND"}) from None

    @router.get("/runtimes")
    def runtimes():
        return {"items": [{**serialize(item), "instance": serialize(service.lifecycle.refresh(item.id)) if item.id in service.lifecycle.instances else None, "discovery": service.lifecycle.discover(item)} for item in service.runtimes.values()]}

    @router.get("/runtimes/{runtime_id}")
    def runtime_detail(runtime_id: str):
        item=runtime(runtime_id); return {**serialize(item), "instance": serialize(service.lifecycle.refresh(item.id)) if item.id in service.lifecycle.instances else None, "discovery": service.lifecycle.discover(item)}

    @router.post("/runtimes/{runtime_id}/validate")
    def validate_runtime(runtime_id: str, body: RuntimeConfigIn | None = None):
        item=runtime(runtime_id)
        if body:
            values=body.model_dump(exclude_none=True)
            try:
                item=service.configure_runtime(runtime_id, values)
            except ValueError as exc:
                raise HTTPException(409, {"code": str(exc)}) from exc
        instance=service.lifecycle.health(item); discovery=service.lifecycle.discover(item, probe_version=True)
        return {"definition":serialize(item),"discovery":discovery,"instance":serialize(instance)}

    @router.post("/runtimes/{runtime_id}/start")
    def start_runtime(runtime_id: str):
        try: return serialize(service.lifecycle.start(runtime(runtime_id)))
        except ValueError as exc: raise HTTPException(409, {"code": str(exc)}) from exc

    @router.post("/runtimes/{runtime_id}/stop")
    def stop_runtime(runtime_id: str):
        runtime(runtime_id)
        try: return serialize(service.lifecycle.stop(runtime_id))
        except ValueError as exc: raise HTTPException(409, {"code": str(exc)}) from exc

    @router.get("/pipelines")
    def pipelines(): return {"items":[serialize(item) for item in service.pipelines.values()]}

    @router.get("/health")
    def health(): return service.health()

    return router
