from fastapi import APIRouter, Header
from pydantic import Field
from .common import api_call
from .embeddings import EmbeddingIndexIn, EmbeddingQueryIn
from .media import StrictModel


class EmbeddingActionIn(StrictModel):
    expected_version: int = Field(ge=1)


def create_embeddings_router(service, authorize, require_flag):
    router = APIRouter(prefix="/novels/{nid}/experimental/embeddings", tags=["Experimental embeddings"])

    def access(nid, token, branch, permission="domain.read"):
        require_flag("visual_embeddings")
        return authorize(nid, token, branch, permission)

    def guard(nid, token, branch, actor, scope, permission):
        def verify():
            if access(nid, token, branch, permission) != (actor, scope):
                raise ValueError("EMBEDDING_SCOPE_CHANGED")
        return verify

    @router.get("/status")
    def status(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        access(nid, x_session_token, x_branch_id)
        return service.status()

    @router.get("/indexes")
    def indexes(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return {"items": api_call(service.indexes, nid, scope)}

    @router.post("/indexes", status_code=201)
    def create(nid: str, body: EmbeddingIndexIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.write")
        return api_call(service.create_index, nid, scope, actor, body)

    @router.get("/indexes/{rid}/records")
    def records(nid: str, rid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return {"items": api_call(service.records, nid, scope, rid)}

    @router.post("/indexes/{rid}/{action}")
    def action(nid: str, rid: str, action: str, body: EmbeddingActionIn,
               x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.write")
        if action == "rebuild":
            return api_call(service.rebuild, nid, scope, actor, rid, body.expected_version,
                            guard(nid, x_session_token, x_branch_id, actor, scope, "domain.write"))
        return api_call(service.transition, nid, scope, actor, rid, action, body.expected_version)

    @router.post("/query")
    def query(nid: str, body: EmbeddingQueryIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id)
        return api_call(service.query, nid, scope, body, guard(nid, x_session_token, x_branch_id, actor, scope, "domain.read"))

    return router
