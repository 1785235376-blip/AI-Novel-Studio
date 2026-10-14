"""Closed route for the read-only Director Workspace projection.

One GET. The route resolves the original project authority on every call through
the shared studio invoker, the same way the production workflow projection does.
It starts no model, opens no job, mutates no asset and promotes no acceptance gate.
"""
from fastapi import APIRouter, Header


def create_director_workspace_router(workspace, invoke):
    router = APIRouter(tags=["Studio director workspace"])

    @router.get("/projects/{nid}/studio/director/workspace/{rid}")
    def director_workspace(nid: str, rid: str, x_session_token: str | None = Header(None),
                           x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: workspace.projection(nid, scope, rid))

    return router
