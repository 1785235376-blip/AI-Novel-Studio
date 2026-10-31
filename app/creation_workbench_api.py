"""Scope-bound authoring endpoints; authority is supplied by the main API."""
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from contextlib import nullcontext
from .services.creation_workbench_service import WorkbenchRecordIn, CommentIn
from .services.v1_capability_service import CapabilityVersionConflict


class ActionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    restore_version: int | None = Field(default=None, ge=1)
    text: str = Field(default="", max_length=8000)


def create_workbench_router(service, authorize, *, authority_lease=None):
    router = APIRouter()

    def call(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except CapabilityVersionConflict as exc:
            raise HTTPException(409, {"code": "WORKBENCH_VERSION_CONFLICT", "current": exc.current}) from exc
        except FileNotFoundError as exc:
            raise HTTPException(404, {"code": "WORKBENCH_NOT_FOUND"}) from exc
        except ValueError as exc:
            raise HTTPException(422, {"code": "WORKBENCH_INVALID", "message": str(exc)}) from exc

    def mutate(nid, token, branch, method, *args):
        actor, scope = authorize(nid, token, branch, 'domain.write')
        if authority_lease is None:
            bound = any(getattr(arg, 'style_dna', None) is not None for arg in args)
            rid = next((arg for arg in args if isinstance(arg, str)), None)
            if rid is not None:
                bound = bound or bool(call(service.get_record, nid, scope, rid).get('style_dna'))
            if bound:
                raise HTTPException(409, {'code': 'STYLE_DNA_AUTHORITY_LEASE_REQUIRED'})
        def again():
            if authorize(nid, token, branch, 'domain.write') != (actor, scope):
                raise HTTPException(403, {"code": "WORKBENCH_AUTHORITY_CHANGED"})
        # Existing authority leases precede Workbench -> scope -> project.
        with (authority_lease(nid, token, actor, scope) if authority_lease else nullcontext()):
            again()
            try:
                return call(method, nid, scope, actor, *args, reauthorize=again)
            finally:
                again()

    @router.get("/novels/{nid}/creation-reference-data")
    def reference_data(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        authorize(nid, x_session_token, x_branch_id, "domain.read")
        return call(service.reference_data, nid)

    @router.get("/novels/{nid}/creation-records")
    def records(nid: str, kind: str | None = None, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = authorize(nid, x_session_token, x_branch_id, "domain.read")
        def again():
            if authorize(nid, x_session_token, x_branch_id, 'domain.read') != (actor, scope):
                raise HTTPException(403, {'code': 'WORKBENCH_AUTHORITY_CHANGED'})
        with (authority_lease(nid, x_session_token, actor, scope) if authority_lease else nullcontext()):
            again()
            try:
                return call(service.list_records, nid, scope, kind)
            finally:
                again()

    @router.post("/novels/{nid}/creation-records", status_code=201)
    def create(nid: str, body: WorkbenchRecordIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return mutate(nid, x_session_token, x_branch_id, service.save_record, body)

    @router.put("/novels/{nid}/creation-records/{rid}")
    def update(nid: str, rid: str, body: WorkbenchRecordIn, expected_version: int = Query(ge=1), x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return mutate(nid, x_session_token, x_branch_id, service.save_record, body, rid, expected_version)

    @router.post("/novels/{nid}/creation-records/{rid}/{action}")
    def transition(nid: str, rid: str, action: str, body: ActionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return mutate(nid, x_session_token, x_branch_id, service.transition_record, rid, action, body.expected_version, body.restore_version)

    @router.get("/novels/{nid}/review-threads")
    def comments(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = authorize(nid, x_session_token, x_branch_id, "domain.read")
        return call(service.list_comments, nid, scope)

    @router.post("/novels/{nid}/review-threads", status_code=201)
    def create_comment(nid: str, body: CommentIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = authorize(nid, x_session_token, x_branch_id, "domain.write")
        return call(service.create_comment, nid, scope, actor, body)

    @router.post("/novels/{nid}/review-threads/{rid}/{action}")
    def comment_action(nid: str, rid: str, action: str, body: ActionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = authorize(nid, x_session_token, x_branch_id, "domain.write")
        return call(service.update_comment, nid, scope, actor, rid, action, body.expected_version, body.text)

    return router
