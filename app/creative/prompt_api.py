"""Closed read-only routes for the Prompt Library.

Three GETs. None of them writes: authoring a prompt asset stays on the existing
asset owner (`create` + `update_metadata` + `annotate_lineage`), and review stays on
`promote_owned`. There is deliberately no route here that could overwrite a user's
prompt, bump a version or delete history — Round 3 §10.
"""
from fastapi import APIRouter, Header, Query


def create_prompt_router(prompts, invoke):
    router = APIRouter(tags=["Studio prompt library"])

    @router.get("/projects/{nid}/studio/prompts")
    def prompt_library(nid: str, x_session_token: str | None = Header(None),
                       x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: prompts.library(nid, scope))

    # Registered before the parameterised route so `context` is not read as a family id.
    @router.get("/projects/{nid}/studio/prompts/context")
    def prompt_context(nid: str, character_id: list[str] | None = Query(None),
                       location_id: list[str] | None = Query(None), document_id: str | None = Query(None),
                       x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: prompts.context(
                          nid, scope, character_ids=character_id or [], location_ids=location_id or [],
                          document_id=document_id))

    @router.get("/projects/{nid}/studio/prompts/{family_id}")
    def prompt_detail(nid: str, family_id: str, x_session_token: str | None = Header(None),
                      x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: prompts.detail(nid, scope, family_id))

    return router
