"""Scope-authorized experimental creative-team endpoints."""
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common import api_call
from .teams import TeamRunIn, TeamOutput


class TeamActionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)


class TeamCompletionIn(TeamActionIn):
    execution_token: str = Field(min_length=1, max_length=100)
    context_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    output: TeamOutput | None = None
    error: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def exactly_one_result(self):
        if (self.output is None) == (self.error is None):
            raise ValueError("supply exactly one of output or error")
        return self


def create_team_router(service, authorize, require_flag):
    router = APIRouter(prefix="/novels/{nid}/experimental/teams", tags=["experimental-teams"])

    def access(nid, token, branch, write=False):
        require_flag("agent_team_recipes")
        return authorize(nid, token, branch, "domain.write" if write else "domain.read")

    @router.get("/catalog")
    def catalog(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        access(nid, x_session_token, x_branch_id)
        return service.catalog()

    @router.get("/runs")
    def runs(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return api_call(service.list_runs, nid, scope)

    @router.post("/runs", status_code=201)
    def create(nid: str, body: TeamRunIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, True)
        return api_call(service.create_run, nid, scope, actor, body)

    @router.get("/runs/{run_id}")
    def get(nid: str, run_id: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return api_call(service.get_run, nid, scope, run_id)

    @router.get("/runs/{run_id}/history")
    def history(nid: str, run_id: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return {"items": api_call(service.get_run, nid, scope, run_id)["history"]}

    @router.post("/runs/{run_id}/nodes/{node_id}/claim")
    def claim(nid: str, run_id: str, node_id: str, body: TeamActionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, True)
        return api_call(service.claim_node, nid, scope, actor, run_id, node_id, body.expected_version)

    @router.post("/runs/{run_id}/nodes/{node_id}/complete")
    def complete(nid: str, run_id: str, node_id: str, body: TeamCompletionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, True)
        output = body.output.model_dump(mode="json", by_alias=True) if body.output else None
        return api_call(service.complete_node, nid, scope, actor, run_id, node_id, body.expected_version,
                        body.execution_token, body.context_hash, output=output, error=body.error)

    @router.post("/runs/{run_id}/review/{action}")
    def review(nid: str, run_id: str, action: str, body: TeamActionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        require_flag("agent_team_recipes")
        actor, scope = authorize(nid, x_session_token, x_branch_id, "domain.review")
        return api_call(service.review, nid, scope, actor, run_id, action, body.expected_version)

    @router.post("/runs/{run_id}/{action}")
    def action(nid: str, run_id: str, action: str, body: TeamActionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, True)
        def reauthorize():
            current_actor, current_scope = access(nid, x_session_token, x_branch_id, True)
            if current_actor != actor or current_scope != scope:
                raise HTTPException(403, {"code": "TEAM_AUTHORITY_CHANGED"})
        return api_call(service.transition, nid, scope, actor, run_id, action, body.expected_version,
                        check_authority=reauthorize)

    return router
