"""Authorized opt-in HTTP surface for media workflow definitions and reviews."""
from fastapi import APIRouter, Header, Response
from pydantic import Field
from .common import api_call
from .media import CoverBriefIn, MediaTaskIn, StoryboardBriefIn, StrictModel


class MediaActionIn(StrictModel):
    expected_version: int = Field(ge=1)
    broker_decision_id: str | None = Field(default=None, max_length=160)
    broker_decision_version: int | None = Field(default=None, ge=1)


class MediaCompareIn(StrictModel):
    proposal_ids: list[str] = Field(min_length=2, max_length=8)


def create_media_router(service, authorize, require_flag):
    router = APIRouter(prefix="/novels/{nid}/experimental/media", tags=["Experimental media"])

    def access(nid, token, branch, permission="domain.read", registry=False):
        require_flag("media_adapter_registry" if registry else "cover_storyboard_generation")
        return authorize(nid, token, branch, permission)

    @router.get("/adapters")
    def adapters(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        access(nid, x_session_token, x_branch_id, registry=True)
        return service.registry.definitions()

    @router.get("/cover-briefs")
    def briefs(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return {"items": [r for r in api_call(service.list, nid, scope, service.BRIEFS) if r["kind"] == "COVER"]}

    @router.post("/cover-briefs", status_code=201)
    def create_cover(nid: str, body: CoverBriefIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.write")
        return api_call(service.create_cover, nid, scope, actor, body)

    @router.put("/cover-briefs/{rid}")
    def update_cover(nid: str, rid: str, body: CoverBriefIn, expected_version: int,
                     x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.write")
        return api_call(service.update_cover, nid, scope, actor, rid, expected_version, body)

    @router.get("/storyboard-briefs")
    def storyboard_briefs(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return {"items": [r for r in api_call(service.list, nid, scope, service.BRIEFS) if r["kind"] == "STORYBOARD"]}

    @router.post("/storyboard-briefs", status_code=201)
    def create_storyboard(nid: str, body: StoryboardBriefIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.write")
        return api_call(service.create_storyboard, nid, scope, actor, body)

    @router.get("/tasks")
    def tasks(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return {"items": api_call(service.tasks, nid, scope)}

    @router.post("/tasks", status_code=201)
    def queue(nid: str, body: MediaTaskIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.write")
        return api_call(service.queue, nid, scope, actor, body)

    @router.post("/tasks/{rid}/{action}")
    def task_action(nid: str, rid: str, action: str, body: MediaActionIn,
                    x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.write")
        if action in {"execute", "preflight"}:
            def reauthorize():
                fresh_actor, fresh_scope = access(nid, x_session_token, x_branch_id, "domain.write")
                if (fresh_actor, fresh_scope) != (actor, scope):
                    raise ValueError("MEDIA_SCOPE_CHANGED")
            task = api_call(service.get, nid, scope, service.TASKS, rid)
            if action == 'preflight':
                require_flag('model_broker_v2')
                return api_call(service.preflight_registered, nid, scope, actor, rid, body.expected_version, reauthorize)
            if task.get('registration_identity'):
                require_flag('model_broker_v2')
                return api_call(service.execute_registered, nid, scope, actor, rid, body.expected_version,
                    body.broker_decision_id, body.broker_decision_version, reauthorize)
            return api_call(service.execute, nid, scope, actor, rid, body.expected_version, reauthorize)
        return api_call(service.transition, nid, scope, actor, rid, action, body.expected_version)

    @router.get("/proposals")
    def proposals(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return {"items": api_call(service.proposals, nid, scope)}

    @router.post("/proposals/compare")
    def compare(nid: str, body: MediaCompareIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return api_call(service.compare, nid, scope, body.proposal_ids)

    @router.get("/proposals/{rid}/preview")
    def preview(nid: str, rid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        content, media_type = api_call(service.preview, nid, scope, rid)
        return Response(content=content, media_type=media_type, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})

    @router.post("/proposals/{rid}/{action}")
    def review(nid: str, rid: str, action: str, body: MediaActionIn,
               x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.review")
        return api_call(service.review, nid, scope, actor, rid, action, body.expected_version)

    return router
