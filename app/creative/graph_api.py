"""Typed creative graph routes over the existing Studio authority boundary.

The parent router supplies its captured actor/scope/incarnation invocation guard.
No route can submit provider outputs or dynamically register executable actions.
"""
from urllib.parse import quote
from fastapi import APIRouter, Header, HTTPException, Request, Response

from ..experimental.production_lineage_api import PrivateProductionRoute
from .graph_models import (GraphAction, GraphCreate, GraphPreflight, GraphRunCreate, GraphSave, GraphFailedLocalRetry,
    GraphMediaPreflight, GraphMediaRunCreate)


def create_creative_graph_router(service, invoke, *, require_host_session=None, model_host_authority=None,
                                 usage_production=None):
    router = APIRouter(tags=["Creative Graph V2"], route_class=PrivateProductionRoute)

    from .ai_execution import ModelPreview, ModelDispatch, ModelRefresh, require_execution
    from .graph_media_execution import MediaNodeRequest, MediaDispatch, MediaJobRequest, MediaGraphReview
    from ..services.audiobook_service import AudiobookError
    from ..audio_production_store import AudioStateVersionConflict
    from ..services.v1_capability_service import CapabilityVersionConflict
    from ..model_provider_contracts import TaskRequirement

    def capture_host(request, token):
        if model_host_authority is None:
            raise HTTPException(403, {"code": "CREATIVE_MODEL_HOST_REQUIRED"})
        authority = model_host_authority(request, token)
        if not authority.principal:
            raise HTTPException(403, {"code": "CREATIVE_MODEL_HOST_BINDING_REQUIRED"})
        authority.guard()
        return authority

    # Closed schema6 is pure local orchestration: original domain.read/write/review
    # guards apply, as for schema1. It grants no model/Host execution authority.
    # Legacy schemas2-5 retain their exact protected-result and Host classification.
    def protected_result(value):
        if not isinstance(value, dict):
            return False
        if value.get("model_runtime") or value.get("media_runtime") or value.get("definition", {}).get("schema_version") in {2, 3, 4, 5}:
            return True
        return any(protected_result(item) for item in value.get("items", []))

    def graph_invoke(nid, token, branch, permission, callback, request, *, model_input=False, target=None,
                     inspection_host=False, local_input=False, local_cleanup=False):
        def source_read_required(actor, scope):
            if local_input:
                return True
            if target is None or target[0] == "list":
                return False
            record = service._owned(nid, scope, actor, target[0], target[1])
            from .canvas_view_models import CANVAS_VIEWS
            if target[0] == CANVAS_VIEWS and 'image_node_origin' in record.get('definition', {}):
                # Only the new mapped formal-source surface requires source
                # read throughout Save/Restore; old plain Canvas writes keep
                # their existing permission contract. Re-evaluated at commit.
                return True
            return record.get("graph_schema_version") in {6, 7} or record.get("definition", {}).get("schema_version") in {6, 7}

        def checked_graph(actor, scope, guard, *, source_read_authorized=False):
            def host_required():
                if model_input:
                    return True
                if target is None:
                    return False
                if target[0] == "list":
                    records = service.store.read(nid, scope)["collections"].get(service.GRAPHS, {}).values()
                    return any(record.get("created_by") == actor and record.get("definition", {}).get("schema_version") in {2, 3, 4, 5}
                        for record in records)
                record = service._owned(nid, scope, actor, target[0], target[1])
                return bool(record.get("model_execution_contract") or record.get("graph_schema_version") in {3, 4, 5}
                    or record.get("definition", {}).get("schema_version") in {2, 3, 4, 5})
            authority = capture_host(request, token) if inspection_host or host_required() else None
            def current():
                guard()
                if (permission != "domain.read" and not local_cleanup and not source_read_authorized
                        and source_read_required(actor, scope)):
                    # A concurrent schema1 -> schema6 upgrade cannot borrow a
                    # write-only admission captured before it required source read.
                    raise HTTPException(403, {"code": "CREATIVE_SUBGRAPH_SOURCE_READ_REQUIRED"})
                if authority is not None:
                    if not inspection_host or host_required():
                        require_execution()
                    if require_host_session is None:
                        raise HTTPException(403, {"code": "CREATIVE_MODEL_HOST_REQUIRED"})
                    require_host_session(token); authority.guard()
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

        def checked(actor, scope, target_guard):
            if permission == "domain.read" or local_cleanup or not source_read_required(actor, scope):
                return checked_graph(actor, scope, target_guard)

            # Reuse the original invoker for both permissions, including its
            # actor/scope/incarnation guards throughout the same transaction.
            def source(source_actor, source_scope, source_guard):
                if (source_actor, source_scope) != (actor, scope):
                    raise HTTPException(403, {"code": "CREATIVE_SUBGRAPH_AUTHORITY_CHANGED"})
                def current():
                    target_guard(); source_guard()
                current()
                return checked_graph(actor, scope, current, source_read_authorized=True)
            return invoke(nid, token, branch, "domain.read", source)
        return invoke(nid, token, branch, permission, checked)

    from .impact_reads import bind_graph_reads
    bind_graph_reads(service, graph_invoke)

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

    def media_call(request, nid, token, branch, permission, method, *args):
        def operation(actor, scope, guard):
            authority = capture_host(request, token)
            def current():
                guard(); require_execution()
                if require_host_session is None:
                    raise HTTPException(403, {"code": "CREATIVE_MODEL_HOST_REQUIRED"})
                require_host_session(token); authority.guard()
            current()
            if service.media_runtime is None:
                raise HTTPException(503, {"code": "CREATIVE_GRAPH_MEDIA_RUNTIME_UNAVAILABLE"})
            try:
                result = getattr(service.media_runtime, method)(nid, scope, actor, *args, current)
            except AudiobookError as exc:
                current(); raise HTTPException(exc.status, {"code": exc.code}) from None
            except AudioStateVersionConflict as exc:
                current(); raise HTTPException(409, {"code": exc.code}) from None
            except CapabilityVersionConflict as exc:
                current()
                raise HTTPException(409, {"code": "CREATIVE_GRAPH_MEDIA_VERSION_CONFLICT", "current_version": exc.current.get("version")}) from None
            except Exception:
                current(); raise
            current(); return result
        return invoke(nid, token, branch, permission, operation)

    @router.get("/novels/{nid}/experimental/production/assets/{aid}/studio-graph-usages")
    def asset_usages(nid: str, aid: str, request: Request,
                     x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        from .asset_usages import graph_asset_usages
        from .asset_usage_paging import query_options
        from .asset_usage_budget import usage_read_budget, UsageBudgetError
        def observe(actor, scope, guard):
            try:
                return graph_asset_usages(service, nid, scope, actor, aid, guard,
                                          **(query_options(request) or {}))
            except (ValueError, TypeError, KeyError, FileNotFoundError, PermissionError, UsageBudgetError):
                guard()
                raise HTTPException(409, {"code": "STUDIO_GRAPH_USAGE_UNAVAILABLE"}) from None
        # Observation must never mint a missing File project incarnation.
        with service.store.existing_owner_only(), usage_read_budget(bool(request.scope.get('query_string'))):
            try:
                return graph_invoke(nid, x_session_token, x_branch_id, "domain.read",
                    observe,
                    request, target=("list",), inspection_host=True)
            except (ValueError, TypeError, KeyError, FileNotFoundError, PermissionError, UsageBudgetError):
                raise HTTPException(409, {"code": "STUDIO_GRAPH_USAGE_UNAVAILABLE"}) from None
            except (AttributeError, RecursionError):
                if not request.scope.get('query_string'):
                    raise
                raise HTTPException(409, {"code": "STUDIO_GRAPH_USAGE_UNAVAILABLE"}) from None

    @router.get("/novels/{nid}/experimental/production/assets/{aid}/studio-asset-usages")
    def saved_asset_usages(nid: str, aid: str, request: Request,
                          x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        from contextlib import ExitStack
        from .asset_usage_paging import paged_usages, query_options
        from .asset_usage_budget import usage_read_budget, UsageBudgetError
        from .production_execution_api import create_production_invoker
        production_call = create_production_invoker(invoke, require_host_session=require_host_session,
                                                    model_host_authority=model_host_authority)

        def admitted(actor, scope, guard):
            initial_authority = capture_host(request, x_session_token)
            if require_host_session is None:
                raise HTTPException(403, {'code': 'CREATIVE_MODEL_HOST_REQUIRED'})
            require_host_session(x_session_token)
            def admitted_guard():
                guard()
                require_host_session(x_session_token)
                initial_authority.guard()
            admitted_guard()
            options = query_options(request, combined=True)
            if options is None:
                raise ValueError('STUDIO_USAGE_QUERY_INVALID')
            selected = options['sources']
            def observe(selected_actor, selected_scope, selected_guard):
                if (selected_actor, selected_scope) != (actor, scope):
                    raise PermissionError('STUDIO_USAGE_AUTHORITY_CHANGED')
                def current():
                    admitted_guard()
                    selected_guard()
                return paged_usages(service, nid, scope, actor, aid, current, graph=True,
                                    production=usage_production, **options)
            if selected == ['timeline']:
                return production_call(request, nid, x_session_token, x_branch_id, 'domain.read', observe)
            def graph_observe(graph_actor, graph_scope, graph_guard):
                if (graph_actor, graph_scope) != (actor, scope):
                    raise PermissionError('STUDIO_USAGE_AUTHORITY_CHANGED')
                if selected == ['graph']:
                    return observe(graph_actor, graph_scope, graph_guard)
                def both(timeline_actor, timeline_scope, timeline_guard):
                    if (timeline_actor, timeline_scope) != (actor, scope):
                        raise PermissionError('STUDIO_USAGE_AUTHORITY_CHANGED')
                    def current():
                        graph_guard()
                        timeline_guard()
                    return observe(timeline_actor, timeline_scope, current)
                return production_call(request, nid, x_session_token, x_branch_id, 'domain.read', both)
            return graph_invoke(nid, x_session_token, x_branch_id, 'domain.read', graph_observe,
                                request, target=('list',), inspection_host=True)

        # The first original admission precedes query parsing and storage work.
        with ExitStack() as contexts:
            contexts.enter_context(service.store.existing_owner_only())
            if usage_production is not None:
                contexts.enter_context(usage_production.store.existing_owner_only())
            contexts.enter_context(usage_read_budget())
            try:
                return invoke(nid, x_session_token, x_branch_id, 'domain.read', admitted)
            except (ValueError, TypeError, KeyError, FileNotFoundError, PermissionError,
                    UsageBudgetError, AttributeError, RecursionError):
                raise HTTPException(409, {'code': 'STUDIO_ASSET_USAGE_UNAVAILABLE'}) from None
            except HTTPException as exc:
                if exc.status_code in {404, 409, 422}:
                    raise HTTPException(409, {'code': 'STUDIO_ASSET_USAGE_UNAVAILABLE'}) from None
                raise

    @router.post("/projects/{nid}/studio/graph-runs/{rid}/media/preview")
    def media_preview(nid: str, rid: str, request: Request, body: MediaNodeRequest, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return media_call(request, nid, x_session_token, x_branch_id, "domain.write", "preview", rid, body)

    @router.post("/projects/{nid}/studio/graph-runs/{rid}/media/dispatch")
    def media_dispatch(nid: str, rid: str, request: Request, body: MediaDispatch, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return media_call(request, nid, x_session_token, x_branch_id, "domain.write", "dispatch", rid, body)

    @router.post("/projects/{nid}/studio/graph-runs/{rid}/media/execute")
    def media_execute(nid: str, rid: str, request: Request, body: MediaJobRequest, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return media_call(request, nid, x_session_token, x_branch_id, "domain.write", "execute_job", rid, body)

    @router.post("/projects/{nid}/studio/graph-runs/{rid}/media/refresh")
    def media_refresh(nid: str, rid: str, request: Request, body: MediaNodeRequest | MediaJobRequest, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return media_call(request, nid, x_session_token, x_branch_id, "domain.write", "refresh", rid, body)

    @router.post("/projects/{nid}/studio/graph-runs/{rid}/media/reconcile")
    def media_reconcile(nid: str, rid: str, request: Request, body: MediaJobRequest, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return media_call(request, nid, x_session_token, x_branch_id, "domain.write", "reconcile", rid, body)

    @router.post("/projects/{nid}/studio/graph-runs/{rid}/media/review")
    def media_review(nid: str, rid: str, request: Request, body: MediaGraphReview, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return media_call(request, nid, x_session_token, x_branch_id, "domain.review", "review", rid, body)

    @router.get("/projects/{nid}/studio/graph-runs/{rid}/media/candidate/{node_id}")
    def media_candidate(nid: str, rid: str, node_id: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        row, data = media_call(request, nid, x_session_token, x_branch_id, "domain.read", "candidate", rid, node_id)
        return Response(data, media_type=row["media_type"], headers={"Cache-Control": "no-store", "X-Asset-SHA256": row["sha256"],
            "X-Asset-Version": str(row["version"]), "Content-Disposition": f"attachment; filename*=UTF-8''{quote(row['filename'], safe='')}"})

    @router.get("/projects/{nid}/studio/graphs/model-capabilities")
    def models(nid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return model_call(request, nid, x_session_token, x_branch_id, "domain.read", "catalog")

    @router.get("/projects/{nid}/studio/graphs/provider-contracts")
    def provider_contracts(nid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return model_call(request, nid, x_session_token, x_branch_id, "domain.read", "providers")

    @router.post("/projects/{nid}/studio/graphs/model-match")
    def model_match(nid: str, request: Request, body: TaskRequirement, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return model_call(request, nid, x_session_token, x_branch_id, "domain.read", "match_task", body)

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
    def catalog(nid: str, request: Request, include_image: bool = False, include_production: bool = False, include_video: bool = False,
                include_local_subgraph: bool = False, include_local_conditions: bool = False,
                x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return graph_invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.catalog(nid, scope, actor, guard=guard,
                          include_image=include_image, include_production=include_production, include_video=include_video,
                          include_local_subgraph=include_local_subgraph, include_local_conditions=include_local_conditions), request,
                          model_input=include_image or include_production or include_video)

    @router.get("/projects/{nid}/studio/graphs/planning-documents")
    def planning_documents(nid: str, request: Request,
                x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return graph_invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.planning_documents(nid, scope, actor, guard),
                      request, model_input=True)

    @router.get("/projects/{nid}/studio/graphs")
    def graphs(nid: str, request: Request, include_local_subgraph: bool = False, include_local_conditions: bool = False,
               x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return graph_invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.list(nid, scope, actor, guard=guard,
                          include_local_subgraph=include_local_subgraph, include_local_conditions=include_local_conditions), request, target=("list", None))

    @router.post("/projects/{nid}/studio/graphs", status_code=201)
    def create(nid: str, request: Request, body: GraphCreate,
               x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return graph_invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.create(nid, scope, actor, body, guard=guard), request,
                      model_input=body.definition.schema_version in {2, 3, 4, 5}, local_input=body.definition.schema_version in {6, 7})

    @router.get("/projects/{nid}/studio/graphs/{gid}")
    def graph(nid: str, gid: str, request: Request,
              x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return graph_invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.get(nid, scope, actor, gid, guard=guard), request, target=(service.GRAPHS, gid))

    @router.put("/projects/{nid}/studio/graphs/{gid}")
    def save(nid: str, gid: str, request: Request, body: GraphSave,
             x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return graph_invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.save(nid, scope, actor, gid, body, guard=guard), request,
                      model_input=body.definition.schema_version in {2, 3, 4, 5}, target=(service.GRAPHS, gid),
                      local_input=body.definition.schema_version in {6, 7})

    @router.post("/projects/{nid}/studio/graphs/{gid}/preflight")
    def preflight(nid: str, gid: str, request: Request, body: GraphPreflight | GraphMediaPreflight,
                  x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return graph_invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.preflight(nid, scope, actor, gid, body, guard=guard), request, target=(service.GRAPHS, gid))

    @router.get("/projects/{nid}/studio/graphs/{gid}/runs")
    def runs(nid: str, gid: str, request: Request,
             x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return graph_invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.runs(nid, scope, actor, gid, guard=guard), request, target=(service.GRAPHS, gid))

    @router.post("/projects/{nid}/studio/graphs/{gid}/runs", status_code=201)
    def create_run(nid: str, gid: str, request: Request, body: GraphRunCreate | GraphMediaRunCreate,
                   x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return graph_invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.create_run(nid, scope, actor, gid, body, guard=guard), request, target=(service.GRAPHS, gid))

    @router.get("/projects/{nid}/studio/graph-runs/{rid}")
    def run(nid: str, rid: str, request: Request,
            x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return graph_invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.get_run(nid, scope, actor, rid, guard=guard), request, target=(service.RUNS, rid))

    @router.post("/projects/{nid}/studio/graph-runs/{rid}/retry-local", status_code=201)
    def retry_local(nid: str, rid: str, request: Request, body: GraphFailedLocalRetry,
                    x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return graph_invoke(nid, x_session_token, x_branch_id, "domain.write",
            lambda actor, scope, guard: service.executor.retry_failed_local(nid, scope, actor, rid, body.model_dump(), guard),
            request, target=(service.RUNS, rid))

    def action_handler(action):
        permission = "domain.review" if action in {"approve", "reject"} else "domain.write"

        def handle(nid: str, rid: str, request: Request, body: GraphAction,
                   x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
            return graph_invoke(nid, x_session_token, x_branch_id, permission,
                          lambda actor, scope, guard: service.action(nid, scope, actor, rid, action, body, guard=guard), request,
                          target=(service.RUNS, rid), local_cleanup=action in {"cancel", "reject"})

        handle.__name__ = "creative_graph_" + action
        return handle

    for action in ("execute", "approve", "reject", "cancel", "pause", "resume"):
        router.add_api_route("/projects/{nid}/studio/graph-runs/{rid}/" + action,
                             action_handler(action), methods=["POST"])
    from .canvas_view_api import create_canvas_view_router
    router.include_router(create_canvas_view_router(service, graph_invoke))
    return router
