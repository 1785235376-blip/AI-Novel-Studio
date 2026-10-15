"""Opt-in neutral project routes; original project/branch authority is unchanged."""
from urllib.parse import quote
import re
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError

from ..experimental.production_lineage_api import PrivateProductionRoute, api_call
from .workspace import FLAG
from .storage_admission import StudioStorageCapacityError
from .workspace_models import (AssetRelationshipIn, AssetVersion, BlankProjectIn, ManualAssetImport, ManualBinaryMask,
                               StudioLineageInput, WorkspacePreferencesUpdate)


def is_independent_studio_route(method, normalized_path):
    """Exact method/path admission; each handler still resolves full authority."""
    root = r"/api/projects/[^/]+/studio"
    patterns = {
        "GET": root + r"(?:/(?:preferences|storage|references|relationships|production-contracts|bible|prompts(?:/[^/]+)?|assets(?:/[^/]+(?:/download)?)?|director/workspace/[^/]+))?",
        "POST": r"(?:/api/experimental/projects|" + root + r"/(?:activate|prompts(?:/[^/]+/revisions(?:/[^/]+/approve)?)?|assets(?:/[^/]+/(?:restore|relationships|mask))?))",
        "PUT": root + r"/(?:preferences|assets/[^/]+/lineage)",
        "DELETE": root + r"/assets/[^/]+(?:/relationships/[^/]+)?",
    }
    if method in patterns and re.fullmatch(patterns[method], normalized_path) is not None:
        return True
    production = root + r"/production"
    owners = r"(?:image|audio|video|timeline)"
    production_patterns = {
        "GET": production + r"/(?:workflow|providers|jobs(?:/" + owners + r"/[^/]+(?:/candidate)?)?|timelines(?:/[^/]+(?:/history)?)?)",
        "POST": production + r"/(?:workflow/intent|preview|jobs(?:/" + owners + r"/[^/]+/(?:execute|cancel|review|reconcile))?|jobs/video/[^/]+/refresh|timelines(?:/[^/]+/(?:render|edit|restore|export-preview|export))?)",
        "PUT": production + r"/timelines/[^/]+",
    }
    if method in production_patterns and re.fullmatch(production_patterns[method], normalized_path) is not None:
        return True
    # Closed graph routes retain the same feature and project authority checks.
    # Unknown actions/methods never gain collaboration middleware admission.
    graph_patterns = {
        "GET": root + r"/(?:graphs(?:/[^/]+(?:/runs)?)?|graph-runs/[^/]+(?:/media/candidate/[^/]+)?)",
        "POST": root + r"/(?:graphs(?:/model-match|/[^/]+/(?:preflight|runs))?|graph-runs/[^/]+/(?:execute|approve|reject|cancel|pause|resume|model/(?:preview|dispatch|refresh)|media/(?:preview|dispatch|execute|refresh|reconcile|review)))",
        "PUT": root + r"/graphs/[^/]+",
    }
    return method in graph_patterns and re.fullmatch(graph_patterns[method], normalized_path) is not None


class ManualMaskRoute(PrivateProductionRoute):
    """Bound the one new bitmap body and never echo private validation input."""
    MAX_BODY = 192 * 1024

    def get_route_handler(self):
        handler = super().get_route_handler()
        async def checked(request):
            headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
            try:
                parts = []; total = 0
                async for part in request.stream():
                    total += len(part)
                    if total > self.MAX_BODY:
                        raise HTTPException(413, {"code": "IMAGE_MASK_REQUEST_LIMIT"}, headers=headers)
                    parts.append(part)
                # Preserve exactly the bounded stream for FastAPI's ordinary
                # JSON/DTO decoder. Content-Length is never the admission proof.
                request._body = b''.join(parts)
                return await handler(request)
            except RequestValidationError:
                raise HTTPException(422, {"code": "IMAGE_MASK_REQUEST_INVALID"}, headers=headers) from None
            except HTTPException as exc:
                exc.headers = {**(exc.headers or {}), **headers}
                raise
        return checked


def create_independent_workspace_router(service, authorize, require_flag, *, create_project, workspace_writer,
                                    graph_service=None, require_host_session=None, model_host_authority=None, production_service=None,
                                    bible_service=None, prompt_service=None, prompt_authoring_service=None):
    router = APIRouter(tags=["Independent Studios V2"], route_class=PrivateProductionRoute)

    def access(nid, token, branch, permission):
        require_flag(FLAG)
        actor, scope = authorize(nid, token, branch, permission)
        service.store.key(nid, scope)
        if not isinstance(actor, str) or not actor:
            raise HTTPException(403, {"code": "CREATIVE_AUTHORITY_INVALID"})
        return actor, scope

    def invoke(nid, token, branch, permission, callback):
        def operation():
            actor, scope = access(nid, token, branch, permission)
            incarnation = service.store.incarnation(nid)
            def guard():
                if (access(nid, token, branch, permission) != (actor, scope)
                        or service.store.incarnation(nid) != incarnation):
                    raise HTTPException(403, {"code": "CREATIVE_AUTHORITY_CHANGED"})
            try:
                result = callback(actor, scope, guard)
            except StudioStorageCapacityError as exc:
                guard()
                raise HTTPException(507, {"code": str(exc)}) from None
            except Exception:
                guard()
                raise
            guard()
            return result
        return api_call(operation)

    from .production_execution_api import create_production_invoker
    mask_call = create_production_invoker(invoke, require_host_session=require_host_session, model_host_authority=model_host_authority)
    mask_router = APIRouter(route_class=ManualMaskRoute)

    @mask_router.post("/projects/{nid}/studio/assets/{aid}/mask", status_code=201)
    def author_mask(nid: str, aid: str, request: Request, body: ManualBinaryMask,
                    x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        def operation(actor, scope, current):
            def guard():
                current(); require_flag("asset_lineage_v2")
            guard()
            from ..services.asset_library_service import AssetIdempotencyConflict
            try:
                return service.author_mask(nid, scope, actor, aid, body, guard)
            except AssetIdempotencyConflict:
                guard()
                raise HTTPException(409, {"code": "IMAGE_MASK_IDEMPOTENCY_CONFLICT"}) from None
        return mask_call(request, nid, x_session_token, x_branch_id, "domain.write", operation, model=False)

    router.include_router(mask_router)

    @router.post("/experimental/projects", status_code=201)
    def blank_project(body: BlankProjectIn, x_session_token: str | None = Header(None)):
        def operation():
            require_flag(FLAG)
            actor = workspace_writer(x_session_token)
            def guard():
                require_flag(FLAG)
                if workspace_writer(x_session_token) != actor:
                    raise HTTPException(403, {"code": "CREATIVE_AUTHORITY_CHANGED"})
            result = create_project(body, x_session_token)
            guard()
            # Shared-mode navigation still comes from the existing admin owner
            # and eligible_paths. Never manufacture a local branch for it.
            if actor is None:
                invoke(result["id"], x_session_token, None, "domain.write",
                    lambda current, scope, fresh: service.activate(result["id"], scope, current, fresh))
            guard()
            return {**result, "studio_ready": actor is None, "requires_scope_selection": actor is not None}
        return api_call(operation)

    @router.get("/projects/{nid}/studio")
    def project(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        def view(actor, scope, guard):
            result = service.project(nid, scope)
            for key, permission in (("can_mutate", "domain.write"), ("can_review", "domain.review")):
                try:
                    allowed = access(nid, x_session_token, x_branch_id, permission) == (actor, scope)
                except HTTPException as exc:
                    if exc.status_code != 403:
                        raise
                    allowed = False
                result["capabilities"][key] = allowed
            return result
        return invoke(nid, x_session_token, x_branch_id, "domain.read", view)

    @router.post("/projects/{nid}/studio/activate")
    def activate(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.activate(nid, scope, actor, guard))

    @router.get("/projects/{nid}/studio/preferences")
    def preferences(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.project(nid, scope)["preferences"])

    @router.put("/projects/{nid}/studio/preferences")
    def update_preferences(nid: str, body: WorkspacePreferencesUpdate,
                           x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.preferences(nid, scope, actor, body, guard))

    @router.get("/projects/{nid}/studio/assets")
    def assets(nid: str, include_deleted: bool = False,
               x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.list_assets(nid, scope, include_deleted=include_deleted))

    @router.post("/projects/{nid}/studio/assets", status_code=201)
    def upload(nid: str, body: ManualAssetImport,
               x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.import_asset(nid, scope, actor, body, guard))

    @router.get("/projects/{nid}/studio/assets/{aid}")
    def asset(nid: str, aid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.asset(nid, scope, aid))

    @router.put("/projects/{nid}/studio/assets/{aid}/lineage")
    def lineage(nid: str, aid: str, body: StudioLineageInput,
                x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.annotate(nid, scope, actor, aid, body, guard))

    @router.get("/projects/{nid}/studio/assets/{aid}/download")
    def download(nid: str, aid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        row, data = invoke(nid, x_session_token, x_branch_id, "domain.read",
                           lambda actor, scope, guard: service.download(nid, scope, aid, guard))
        # Safe generated ASCII fallback plus an RFC 5987 encoded filename.
        return Response(data, media_type=row["media_type"], headers={
            "Content-Disposition": f"attachment; filename=\"asset-{row['id']}\"; filename*=UTF-8''{quote(row['filename'], safe='')}",
            "X-Asset-SHA256": row["sha256"], "X-Asset-Version": str(row["version"])})

    @router.delete("/projects/{nid}/studio/assets/{aid}")
    def remove(nid: str, aid: str, expected_version: int = Query(ge=1),
               x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.lifecycle(nid, scope, aid, expected_version, guard=guard, actor_id=actor))

    @router.post("/projects/{nid}/studio/assets/{aid}/restore")
    def restore(nid: str, aid: str, body: AssetVersion,
                x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.lifecycle(nid, scope, aid, body.expected_version, restore=True, guard=guard, actor_id=actor))

    @router.get("/projects/{nid}/studio/storage")
    def storage(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.storage(nid, scope))

    @router.get("/projects/{nid}/studio/references")
    def references(nid: str, kind: Literal["ASSET", "CHAPTER", "SCREENPLAY"],
                   x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.relationships.references(nid, scope, kind))

    @router.get("/projects/{nid}/studio/relationships")
    def relationships(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.relationships.graph(nid, scope))

    @router.post("/projects/{nid}/studio/assets/{aid}/relationships", status_code=201)
    def add_relationship(nid: str, aid: str, body: AssetRelationshipIn,
                         x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        permission = "domain.review" if body.type == "APPROVED_FOR" else "domain.write"
        return invoke(nid, x_session_token, x_branch_id, permission,
                      lambda actor, scope, guard: service.relationships.add(nid, scope, actor, aid, body, guard))

    @router.delete("/projects/{nid}/studio/assets/{aid}/relationships/{rid}")
    def remove_relationship(nid: str, aid: str, rid: str, expected_version: int = Query(ge=1),
                            x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.relationships.remove(nid, scope, actor, aid, rid, expected_version, guard))

    from .production_contract_api import create_production_contract_router
    router.include_router(create_production_contract_router(service, invoke))

    from .production_workflow import ProductionWorkflowService
    from .production_workflow_api import create_production_workflow_router
    router.include_router(create_production_workflow_router(
        ProductionWorkflowService(service, service.creative), invoke))

    from .director_workspace import DirectorWorkspaceService
    from .director_workspace_api import create_director_workspace_router
    router.include_router(create_director_workspace_router(
        DirectorWorkspaceService(service, service.creative), invoke))

    if bible_service is not None:
        from .bible_api import create_bible_router
        router.include_router(create_bible_router(bible_service, invoke))

    if prompt_service is not None:
        from .prompt_api import create_prompt_router
        router.include_router(create_prompt_router(prompt_service, invoke))

    if prompt_authoring_service is not None:
        from .prompt_authoring_api import create_prompt_authoring_router
        router.include_router(create_prompt_authoring_router(prompt_authoring_service, invoke))

    if production_service is not None:
        from .production_execution_api import create_production_execution_router
        router.include_router(create_production_execution_router(production_service, invoke,
            require_host_session=require_host_session, model_host_authority=model_host_authority))

    if graph_service is not None:
        from .graph_api import create_creative_graph_router
        router.include_router(create_creative_graph_router(graph_service, invoke, require_host_session=require_host_session,
            model_host_authority=model_host_authority))
    return router
