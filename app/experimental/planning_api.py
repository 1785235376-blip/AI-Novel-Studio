"""Opt-in planning HTTP contracts; all authority comes from the existing gate."""
from fastapi import APIRouter, Header
from pydantic import Field

from .common import api_call
from .planning import (StrictModel, PlanningGraphIn, PlanningNodeIn, PlanningNodeEditIn,
                       PlanningProposalIn, PlanningTemplateIn, PlanningGenerateIn)


class PlanningActionIn(StrictModel):
    expected_version: int = Field(ge=1)


class PlanningRestoreIn(PlanningActionIn):
    historical_version: int = Field(ge=1)


class PlanningCompareIn(StrictModel):
    proposal_ids: list[str] = Field(min_length=2, max_length=8)


def create_planning_router(service, authorize, require_flag):
    router = APIRouter(prefix="/novels/{nid}/experimental/planning", tags=["experimental-planning"])

    def access(nid, token, branch, write=False, review=False):
        require_flag("advanced_planning_v2")
        return authorize(nid, token, branch, "domain.review" if review else "domain.write" if write else "domain.read")

    @router.get("/graphs")
    def graphs(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return {"items": api_call(service.list_graphs, nid, scope)}

    @router.post("/graphs", status_code=201)
    def create_graph(nid: str, body: PlanningGraphIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, True)
        return api_call(service.create_graph, nid, scope, actor, body)

    @router.get("/graphs/{gid}")
    def graph(nid: str, gid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return api_call(service.graph, nid, scope, gid)

    @router.post("/nodes", status_code=201)
    def create_node(nid: str, body: PlanningNodeIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, True)
        return api_call(service.create_node, nid, scope, actor, body)

    @router.put("/nodes/{node_id}")
    def edit_node(nid: str, node_id: str, body: PlanningNodeEditIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, True)
        return api_call(service.edit_node, nid, scope, actor, node_id, body)

    @router.post("/graphs/{gid}/{action}")
    def transition_graph(nid: str, gid: str, action: str, body: PlanningActionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, True)
        return api_call(service.transition_graph, nid, scope, actor, gid, action, body.expected_version)

    @router.post("/nodes/{node_id}/{action}")
    def transition_node(nid: str, node_id: str, action: str, body: PlanningActionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, True)
        return api_call(service.transition_node, nid, scope, actor, node_id, action, body.expected_version)

    @router.get("/templates")
    def templates(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return {"items": api_call(service.templates, nid, scope)}

    @router.post("/templates", status_code=201)
    def create_template(nid: str, body: PlanningTemplateIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, True)
        return api_call(service.create_template, nid, scope, actor, body)

    @router.post("/generate", status_code=201)
    def generate(nid: str, body: PlanningGenerateIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, True)
        return api_call(service.generate, nid, scope, actor, body)

    @router.get("/proposals")
    def proposals(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return {"items": api_call(service.proposals, nid, scope)}

    @router.post("/proposals", status_code=201)
    def create_proposal(nid: str, body: PlanningProposalIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, True)
        return api_call(service.create_proposal, nid, scope, actor, body)

    @router.post("/proposals/compare")
    def compare(nid: str, body: PlanningCompareIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return api_call(service.compare, nid, scope, body.proposal_ids)

    @router.get("/proposals/{pid}")
    def proposal(nid: str, pid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return api_call(service.proposal, nid, scope, pid)

    @router.get("/proposals/{pid}/history")
    def history(nid: str, pid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return {"items": api_call(service.history, nid, scope, pid)}

    @router.post("/proposals/{pid}/restore")
    def restore(nid: str, pid: str, body: PlanningRestoreIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, True)
        return api_call(service.restore, nid, scope, actor, pid, body.expected_version, body.historical_version)

    @router.post("/proposals/{pid}/{action}")
    def review(nid: str, pid: str, action: str, body: PlanningActionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, True, action in {"approve", "reject", "reopen"})
        return api_call(service.review, nid, scope, actor, pid, action, body.expected_version)

    return router
