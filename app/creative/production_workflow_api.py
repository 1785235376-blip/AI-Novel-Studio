"""Closed routes for the unified production workflow projection.

Both routes resolve the original project authority on every call through the
shared studio invoker. Neither route starts a model, opens a job, mutates an
asset or promotes an acceptance gate.
"""
from fastapi import APIRouter, Header

from .production_workflow_models import ProductionIntentUpdate


def create_production_workflow_router(workflow, invoke):
    router = APIRouter(tags=["Studio production workflow"])

    @router.get("/projects/{nid}/studio/production/workflow")
    def workflow_projection(nid: str, x_session_token: str | None = Header(None),
                            x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: workflow.projection(nid, scope))

    @router.post("/projects/{nid}/studio/production/workflow/intent")
    def workflow_intent(nid: str, body: ProductionIntentUpdate,
                        x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: workflow.update_intent(nid, scope, actor, body, guard))

    return router
