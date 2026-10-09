"""Typed creative graph routes over the existing Studio authority boundary.

The parent router supplies its captured actor/scope/incarnation invocation guard.
No route can submit provider outputs or dynamically register executable actions.
"""
from fastapi import APIRouter, Header

from ..experimental.production_lineage_api import PrivateProductionRoute
from .graph_models import GraphAction, GraphCreate, GraphPreflight, GraphRunCreate, GraphSave


def create_creative_graph_router(service, invoke):
    router = APIRouter(tags=["Creative Graph V2"], route_class=PrivateProductionRoute)

    @router.get("/projects/{nid}/studio/graphs/catalog")
    def catalog(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.catalog(nid, scope, actor, guard=guard))

    @router.get("/projects/{nid}/studio/graphs")
    def graphs(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.list(nid, scope, actor, guard=guard))

    @router.post("/projects/{nid}/studio/graphs", status_code=201)
    def create(nid: str, body: GraphCreate,
               x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.create(nid, scope, actor, body, guard=guard))

    @router.get("/projects/{nid}/studio/graphs/{gid}")
    def graph(nid: str, gid: str,
              x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.get(nid, scope, actor, gid, guard=guard))

    @router.put("/projects/{nid}/studio/graphs/{gid}")
    def save(nid: str, gid: str, body: GraphSave,
             x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.save(nid, scope, actor, gid, body, guard=guard))

    @router.post("/projects/{nid}/studio/graphs/{gid}/preflight")
    def preflight(nid: str, gid: str, body: GraphPreflight,
                  x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.preflight(nid, scope, actor, gid, body, guard=guard))

    @router.get("/projects/{nid}/studio/graphs/{gid}/runs")
    def runs(nid: str, gid: str,
             x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.runs(nid, scope, actor, gid, guard=guard))

    @router.post("/projects/{nid}/studio/graphs/{gid}/runs", status_code=201)
    def create_run(nid: str, gid: str, body: GraphRunCreate,
                   x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.create_run(nid, scope, actor, gid, body, guard=guard))

    @router.get("/projects/{nid}/studio/graph-runs/{rid}")
    def run(nid: str, rid: str,
            x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.get_run(nid, scope, actor, rid, guard=guard))

    def action_handler(action):
        permission = "domain.review" if action in {"approve", "reject"} else "domain.write"

        def handle(nid: str, rid: str, body: GraphAction,
                   x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
            return invoke(nid, x_session_token, x_branch_id, permission,
                          lambda actor, scope, guard: service.action(nid, scope, actor, rid, action, body, guard=guard))

        handle.__name__ = "creative_graph_" + action
        return handle

    for action in ("execute", "approve", "reject", "cancel", "pause", "resume"):
        router.add_api_route("/projects/{nid}/studio/graph-runs/{rid}/" + action,
                             action_handler(action), methods=["POST"])
    return router
