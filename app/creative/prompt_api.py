"""Closed read-only routes for the Prompt Library.

Three GETs. None of them writes: authoring a prompt asset goes through the dedicated
authoring routes (`prompt_authoring_api.py`), which reuse the existing asset owner, and
review reuses that owner's review path. Nothing here can overwrite a user's prompt, bump
a revision or delete history — Round 3 §10.

R3-R-06: every handler now passes the **actor the authorisation path resolved** into the
service, so the asset owner's own private-owner filtering applies to the caller. The
actor is never taken from the client and never defaulted to a permissive value.
"""
from fastapi import APIRouter, Header, Query


def create_prompt_router(prompts, invoke):
    router = APIRouter(tags=["Studio prompt library"])

    @router.get("/projects/{nid}/studio/prompts")
    def prompt_library(nid: str, x_session_token: str | None = Header(None),
                       x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: prompts.library(nid, scope, actor))

    # Registered before the parameterised route so `context` is not read as a family id.
    @router.get("/projects/{nid}/studio/prompts/context")
    def prompt_context(nid: str, character_id: list[str] | None = Query(None),
                       location_id: list[str] | None = Query(None), document_id: str | None = Query(None),
                       x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: prompts.context(
                          nid, scope, character_ids=character_id or [], location_ids=location_id or [],
                          document_id=document_id, actor=actor))

    @router.get("/projects/{nid}/studio/prompts/{family_id}")
    def prompt_detail(nid: str, family_id: str, x_session_token: str | None = Header(None),
                      x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: prompts.detail(nid, scope, family_id, actor))

    # R3-U2: the narrow, read-only single-revision body. Registered after the family route
    # but as an explicit longer path, so it cannot shadow `context` or the family detail.
    @router.get("/projects/{nid}/studio/prompts/{family_id}/revisions/{asset_id}/body")
    def prompt_revision_body(nid: str, family_id: str, asset_id: str,
                             x_session_token: str | None = Header(None),
                             x_branch_id: str | None = Header(None)):
        """A revision's real body, read under the caller's own actor.

        This does **not** widen `GET /studio/assets/{aid}/download`; it is a separate,
        family-scoped, actor-resolved read so version comparison can be a true text diff.
        """
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: prompts.revision_body(
                          nid, scope, family_id, asset_id, actor))

    return router
