"""A08 current-authority API; private responses never include raw conflicts."""
from fastapi import APIRouter, Header, HTTPException
from pydantic import Field
from ..repositories.chapter_repository import VersionConflict
from .director import DirectorPlanIn
from .media import StrictModel
from .production_lineage_api import api_call, PrivateProductionRoute


class DirectorCompare(StrictModel):
    plan_ids: list[str] = Field(min_length=1, max_length=4)


class DirectorAction(StrictModel):
    expected_version: int = Field(ge=1)
    comparison_digest: str = Field(default="", max_length=64)


def create_director_router(service, authorize, require_flag):
    router = APIRouter(prefix="/novels/{nid}/experimental/director", tags=["Experimental director"], route_class=PrivateProductionRoute)

    def invoke(nid, token, branch, permission, callback):
        def access():
            require_flag("ai_director_v2")
            return authorize(nid, token, branch, permission)
        actor, scope = access()
        def guard():
            if access() != (actor, scope):
                raise HTTPException(403, {"code": "DIRECTOR_AUTHORITY_CHANGED"})
        try:
            result = api_call(callback, actor, scope, guard)
        except VersionConflict:
            raise HTTPException(409, {"code": "DIRECTOR_SCREENPLAY_VERSION_CONFLICT"}) from None
        guard()
        return result

    @router.get("/catalog")
    def catalog(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read", lambda actor, scope, guard: service.catalog(nid, scope, actor))

    @router.get("/plans")
    def plans(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read", lambda actor, scope, guard: service.plans(nid, scope, actor))

    @router.post("/plans", status_code=201)
    def create(nid: str, body: DirectorPlanIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write", lambda actor, scope, guard: service.create_plan(nid, scope, actor, body, guard))

    @router.post("/compare")
    def compare(nid: str, body: DirectorCompare, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read", lambda actor, scope, guard: service.compare(nid, scope, actor, body.plan_ids))

    @router.post("/plans/{rid}/{action}")
    def action(nid: str, rid: str, action: str, body: DirectorAction, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        if action not in {"apply", "reject"}:
            raise HTTPException(404)
        return invoke(nid, x_session_token, x_branch_id, "domain.review", lambda actor, scope, guard:
                      service.apply(nid, scope, actor, rid, body.expected_version, body.comparison_digest, guard) if action == "apply"
                      else service.reject(nid, scope, actor, rid, body.expected_version, guard))
    return router
