"""Planning endpoints use the existing authenticated branch authority callback."""
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .services.ai_planning_service import PlanningRunIn
from .services.v1_capability_service import CapabilityVersionConflict


class PlanningActionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)


def create_ai_planning_router(service, authorize):
    router = APIRouter()

    def call(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except CapabilityVersionConflict as exc:
            raise HTTPException(409, {"code": "PLANNING_VERSION_CONFLICT", "message": "任务已更新，请刷新后重试。", "current": exc.current}) from exc
        except FileNotFoundError as exc:
            raise HTTPException(404, {"code": "PLANNING_NOT_FOUND"}) from exc
        except ValueError as exc:
            raise HTTPException(422, {"code": "PLANNING_INVALID", "message": str(exc)}) from exc

    @router.get("/novels/{nid}/planning-runs")
    def runs(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = authorize(nid, x_session_token, x_branch_id, "domain.read")
        return call(service.list, nid, scope)

    @router.post("/novels/{nid}/planning-runs", status_code=202)
    def create(nid: str, body: PlanningRunIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = authorize(nid, x_session_token, x_branch_id, "domain.write")
        def reauthorize():
            current_actor, current_scope = authorize(nid, x_session_token, x_branch_id, "domain.write")
            if current_actor != actor or current_scope != scope:
                raise ValueError("planning authority changed")
        return call(service.create, nid, scope, actor, body, reauthorize=reauthorize)

    @router.get("/novels/{nid}/planning-runs/{rid}")
    def get(nid: str, rid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = authorize(nid, x_session_token, x_branch_id, "domain.read")
        return call(service.get, nid, scope, rid)

    @router.post("/novels/{nid}/planning-runs/{rid}/cancel")
    def cancel(nid: str, rid: str, body: PlanningActionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = authorize(nid, x_session_token, x_branch_id, "domain.write")
        return call(service.cancel, nid, scope, rid, body.expected_version)

    @router.post("/novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft")
    def save(nid: str, rid: str, cid: str, body: PlanningActionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = authorize(nid, x_session_token, x_branch_id, "domain.write")
        return call(service.save_candidate, nid, scope, actor, rid, cid, body.expected_version)

    return router
