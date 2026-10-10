"""Typed creative graph routes over the existing Studio authority boundary.

The parent router supplies its captured actor/scope/incarnation invocation guard.
No route can submit provider outputs or dynamically register executable actions.
"""
from fastapi import APIRouter, Header, HTTPException, Request

from ..experimental.production_lineage_api import PrivateProductionRoute
from .graph_models import GraphAction, GraphCreate, GraphPreflight, GraphRunCreate, GraphSave


def create_creative_graph_router(service, invoke, *, require_host_session=None, model_host_authority=None):
    router = APIRouter(tags=["Creative Graph V2"], route_class=PrivateProductionRoute)

    from .ai_execution import ModelPreview, ModelDispatch, ModelRefresh, require_execution

    def capture_host(request, token):
        if model_host_authority is None:
            raise HTTPException(403, {"code": "CREATIVE_MODEL_HOST_REQUIRED"})
        authority = model_host_authority(request, token)
        if not authority.principal:
            raise HTTPException(403, {"code": "CREATIVE_MODEL_HOST_BINDING_REQUIRED"})
        authority.guard()
        return authority

    def protected_result(value):
        if not isinstance(value, dict):
            return False
        if value.get("model_runtime") or value.get("definition", {}).get("schema_version") == 2:
            return True
        return any(protected_result(item) for item in value.get("items", []))

    def graph_invoke(nid, token, branch, permission, callback, request, *, model_input=False, target=None):
        def checked(actor, scope, guard):
            def host_required():
                if model_input:
                    return True
                if target is None:
                    return False
                if target[0] == "list":
                    records = service.store.read(nid, scope)["collections"].get(service.GRAPHS, {}).values()
                    return any(record.get("created_by") == actor and record.get("definition", {}).get("schema_version") == 2
                        for record in records)
                record = service._owned(nid, scope, actor, target[0], target[1])
                return bool(record.get("model_execution_contract")
                    or record.get("definition", {}).get("schema_version") == 2)
            authority = capture_host(request, token) if host_required() else None
            def current():
                guard()
                if authority is not None:
                    require_execution(); authority.guard()
                elif host_required():
                    # A concurrent schema-1 upgrade cannot borrow this request's
                    # earlier unhosted admission, including inside its commit.
                    raise HTTPException(403, {"code": "CREATIVE_MODEL_HOST_REQUIRED"})
            current()
            try:
                value = callback(actor, scope, current)
            except Exception:
                current()
                raise
            if protected_result(value):
                (authority or capture_host(request, token)).guard()
            current()
            return value
        return invoke(nid, token, branch, permission, checked)

    def model_call(request, nid, token, branch, permission, method, *args):
        def operation(actor, scope, guard):
            authority = capture_host(request, token)
            def current():
                guard(); require_execution()
                if require_host_session is None:
                    raise HTTPException(403, {"code": "CREATIVE_MODEL_HOST_REQUIRED"})
                require_host_session(token)
                authority.guard()
            current()
            if service.model_runtime is None:
                raise HTTPException(503, {"code": "CREATIVE_MODEL_RUNTIME_UNAVAILABLE"})
            try:
                result = getattr(service.model_runtime, method)(nid, scope, actor, *args, current)
            except Exception:
                current()
                raise
            current(); return result
        return invoke(nid, token, branch, permission, operation)

    @router.get("/projects/{nid}/studio/graphs/model-capabilities")
    def models(nid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return model_call(request, nid, x_session_token, x_branch_id, "domain.read", "catalog")

    @router.post("/projects/{nid}/studio/graph-runs/{rid}/model/preview")
    def model_preview(nid: str, rid: str, request: Request, body: ModelPreview, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return model_call(request, nid, x_session_token, x_branch_id, "domain.write", "preview", rid, body)

    @router.post("/projects/{nid}/studio/graph-runs/{rid}/model/dispatch")
    def model_dispatch(nid: str, rid: str, request: Request, body: ModelDispatch, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return model_call(request, nid, x_session_token, x_branch_id, "domain.write", "dispatch", rid, body)

    @router.post("/projects/{nid}/studio/graph-runs/{rid}/model/refresh")
    def model_refresh(nid: str, rid: str, request: Request, body: ModelRefresh, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return model_call(request, nid, x_session_token, x_branch_id, "domain.write", "refresh", rid, body)

    @router.get("/projects/{nid}/studio/graphs/catalog")
    def catalog(nid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return graph_invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.catalog(nid, scope, actor, guard=guard), request)

    @router.get("/projects/{nid}/studio/graphs")
    def graphs(nid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return graph_invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.list(nid, scope, actor, guard=guard), request, target=("list", None))

    @router.post("/projects/{nid}/studio/graphs", status_code=201)
    def create(nid: str, request: Request, body: GraphCreate,
               x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return graph_invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.create(nid, scope, actor, body, guard=guard), request, model_input=body.definition.schema_version == 2)

    @router.get("/projects/{nid}/studio/graphs/{gid}")
    def graph(nid: str, gid: str, request: Request,
              x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return graph_invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.get(nid, scope, actor, gid, guard=guard), request, target=(service.GRAPHS, gid))

    @router.put("/projects/{nid}/studio/graphs/{gid}")
    def save(nid: str, gid: str, request: Request, body: GraphSave,
             x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return graph_invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.save(nid, scope, actor, gid, body, guard=guard), request, model_input=body.definition.schema_version == 2, target=(service.GRAPHS, gid))

    @router.post("/projects/{nid}/studio/graphs/{gid}/preflight")
    def preflight(nid: str, gid: str, request: Request, body: GraphPreflight,
                  x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return graph_invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.preflight(nid, scope, actor, gid, body, guard=guard), request, target=(service.GRAPHS, gid))

    @router.get("/projects/{nid}/studio/graphs/{gid}/runs")
    def runs(nid: str, gid: str, request: Request,
             x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return graph_invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.runs(nid, scope, actor, gid, guard=guard), request, target=(service.GRAPHS, gid))

    @router.post("/projects/{nid}/studio/graphs/{gid}/runs", status_code=201)
    def create_run(nid: str, gid: str, request: Request, body: GraphRunCreate,
                   x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return graph_invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.create_run(nid, scope, actor, gid, body, guard=guard), request, target=(service.GRAPHS, gid))

    @router.get("/projects/{nid}/studio/graph-runs/{rid}")
    def run(nid: str, rid: str, request: Request,
            x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return graph_invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.get_run(nid, scope, actor, rid, guard=guard), request, target=(service.RUNS, rid))

    def action_handler(action):
        permission = "domain.review" if action in {"approve", "reject"} else "domain.write"

        def handle(nid: str, rid: str, request: Request, body: GraphAction,
                   x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
            return graph_invoke(nid, x_session_token, x_branch_id, permission,
                          lambda actor, scope, guard: service.action(nid, scope, actor, rid, action, body, guard=guard), request, target=(service.RUNS, rid))

        handle.__name__ = "creative_graph_" + action
        return handle

    for action in ("execute", "approve", "reject", "cancel", "pause", "resume"):
        router.add_api_route("/projects/{nid}/studio/graph-runs/{rid}/" + action,
                             action_handler(action), methods=["POST"])
    return router
