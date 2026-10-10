"""Feature-gated world candidates, reviewed Canon and deterministic queries."""
from fastapi import APIRouter, Header, Query
from pydantic import Field

from .common import api_call
from .planning import StrictModel
from .world import WorldRecordIn, WorldRecordEditIn


class WorldActionIn(StrictModel):
    expected_version: int = Field(ge=1)


def create_world_router(service, authorize, require_flag):
    router = APIRouter(prefix="/novels/{nid}/experimental/world", tags=["experimental-world"])

    def access(nid, token, branch, permission="domain.read"):
        require_flag("world_character_engines_v2")
        return authorize(nid, token, branch, permission)

    @router.get("/schema")
    def schema(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        access(nid, x_session_token, x_branch_id)
        from .world import DATA_MODELS
        return {"record": WorldRecordIn.model_json_schema(), "kinds": {kind: model.model_json_schema() for kind, model in DATA_MODELS.items()}, "verification": "DETERMINISTIC_RULES"}

    @router.get("/records")
    def records(nid: str, kind: str | None = None, status: str | None = None, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        rows = api_call(service.records, nid, scope)
        return {"items": [row for row in rows if (not kind or row["kind"] == kind) and (not status or row["status"] == status)]}

    @router.post("/records", status_code=201)
    def create_record(nid: str, body: WorldRecordIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.write")
        return api_call(service.create_record, nid, scope, actor, body)

    @router.get("/records/{rid}")
    def record(nid: str, rid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return api_call(service.record, nid, scope, rid)

    @router.put("/records/{rid}")
    def edit_record(nid: str, rid: str, body: WorldRecordEditIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.write")
        return api_call(service.edit_record, nid, scope, actor, rid, body)

    @router.get("/records/{rid}/history")
    def history(nid: str, rid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return {"items": api_call(service.history, nid, scope, rid)}

    @router.post("/records/{rid}/{action}")
    def review(nid: str, rid: str, action: str, body: WorldActionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        permission = "domain.review" if action in {"approve", "reject", "reopen", "archive"} else "domain.write"
        actor, scope = access(nid, x_session_token, x_branch_id, permission)
        return api_call(service.review, nid, scope, actor, rid, action, body.expected_version)

    @router.get("/canon")
    def canon(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return {"items": api_call(service.canon, nid, scope)}

    @router.get("/continuity")
    def continuity(nid: str, include_candidates: bool = Query(False), x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return api_call(service.continuity, nid, scope, include_candidates)

    @router.get("/character-state")
    def character_state(nid: str, character_id: str, chapter_id: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return api_call(service.character_state, nid, scope, character_id, chapter_id)

    return router
