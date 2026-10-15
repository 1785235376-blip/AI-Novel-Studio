"""Dedicated Prompt authoring routes (R3-W).

Three POSTs on the dev studio router. They exist so a **user** can create and revise a
prompt; they are not a back door for an AI to overwrite one:

* every handler resolves project, scope and actor through the shared studio invoker, so
  `SESSION_REQUIRED` and the permission gates apply exactly as they do to the GETs;
* the request DTOs are closed (`extra="forbid"`), so a client cannot supply approval
  time, a reviewer identity, an internal asset owner, a project-binding marker, an
  execution receipt or model-run proof;
* nothing here executes a model, opens a job or spends money.

The three read-only GETs stay read-only; authoring never mutates them.
"""
from fastapi import APIRouter, Header, Query

from .prompt_authoring_models import PromptCreateIn, PromptRevisionIn


def create_prompt_authoring_router(prompts, invoke):
    router = APIRouter(tags=["Studio prompt authoring"])

    @router.post("/projects/{nid}/studio/prompts", status_code=201)
    def create_prompt(nid: str, body: PromptCreateIn, x_session_token: str | None = Header(None),
                      x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: prompts.create(nid, scope, actor, body, guard))

    @router.post("/projects/{nid}/studio/prompts/{family_id}/revisions", status_code=201)
    def revise_prompt(nid: str, family_id: str, body: PromptRevisionIn,
                      x_session_token: str | None = Header(None),
                      x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: prompts.revise(nid, scope, actor, family_id, body, guard))

    @router.post("/projects/{nid}/studio/prompts/{family_id}/revisions/{asset_id}/approve")
    def approve_revision(nid: str, family_id: str, asset_id: str, expected_version: int = Query(ge=1),
                         x_session_token: str | None = Header(None),
                         x_branch_id: str | None = Header(None)):
        """Reuse the owner's review path. Approval is never taken from client input."""
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: prompts.approve(
                          nid, scope, actor, family_id, asset_id, expected_version, guard))

    return router
