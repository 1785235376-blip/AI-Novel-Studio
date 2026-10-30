"""Opt-in neutral project routes; original project/branch authority is unchanged."""
from urllib.parse import quote
import json
import re
from typing import Literal
from contextlib import nullcontext

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError

from ..config import settings
from ..experimental.production_lineage_api import PrivateProductionRoute, api_call
from .workspace import FLAG
from .storage_admission import StudioStorageCapacityError
from .workspace_models import (AssetRelationshipIn, AssetVersion, BlankProjectIn, ManualModelReferenceImport, ManualAssetImport, ManualBinaryMask,
                               ProjectCapacityLimitUpdate, StudioAssetQuery, StudioLineageInput, WorkspacePreferencesUpdate)


def is_independent_studio_route(method, normalized_path):
    """Exact method/path admission; each handler still resolves full authority."""
    root = r"/api/projects/[^/]+/studio"
    patterns = {
        "GET": root + r"(?:/(?:comic-workspace|preferences|storage|capacity|references|relationships|production-contracts(?:/runtime)?|bible|prompts(?:/[^/]+(?:/revisions/[^/]+/body)?)?|documents/[^/]+/prompt-adoption|assets(?:/[^/]+(?:/(?:download|model-reference(?:/(?:mesh-preview|scene-preview|materials|cameras))?))?)?|director/workspace/[^/]+))?",
        "POST": r"(?:/api/experimental/projects|" + root + r"/(?:capacity/reconcile|assets/[^/]+/history/migrate|activate|prompts(?:/[^/]+/revisions(?:/[^/]+/approve)?)?|documents/[^/]+/shots/[^/]+/prompt-adoption|assets(?:/model-reference|/[^/]+/(?:restore|relationships|mask|model-reference/(?:depth-export|clay-export|clay-save|camera-export)|video-reference/(?:preview|save)))?))",
        "PUT": root + r"/(?:capacity/limit|preferences|assets/[^/]+/lineage)",
        "DELETE": root + r"/assets/[^/]+(?:/relationships/[^/]+)?",
    }
    if method in patterns and re.fullmatch(patterns[method], normalized_path) is not None:
        return True
    if method == "GET" and re.fullmatch(root + r"/assets/[^/]+/history(?:/[a-f0-9]{64}(?:/download)?)?", normalized_path):
        return True
    production = root + r"/production"
    owners = r"(?:image|audio|video|timeline)"
    production_patterns = {
        "GET": production + r"/(?:workflow|providers|jobs(?:/" + owners + r"/[^/]+(?:/candidate)?)?|timelines(?:/[^/]+(?:/history)?)?)",
        "POST": production + r"/(?:workflow/intent|preview|jobs(?:/" + owners + r"/[^/]+/(?:execute|cancel|review|reconcile))?|jobs/image/resolve-create|jobs/video/[^/]+/refresh|timelines(?:/[^/]+/(?:render|edit|restore|export-preview|export|waveform-preview|source-bounds))?)",
        "PUT": production + r"/timelines/[^/]+",
    }
    if method in production_patterns and re.fullmatch(production_patterns[method], normalized_path) is not None:
        return True
    handoff_patterns = {
        'GET': production + r'/comic-handoffs/[A-Za-z0-9][A-Za-z0-9_-]{0,79}',
        'POST': production + r'/comic-handoffs(?:/preview|/[A-Za-z0-9][A-Za-z0-9_-]{0,79}/(?:resume|cancel))?',
    }
    if method in handoff_patterns and re.fullmatch(handoff_patterns[method], normalized_path) is not None:
        return True
    canvas_patterns = {
        "GET": root + r"/canvas-views(?:/[^/]+(?:/history)?)?",
        "POST": root + r"/canvas-views(?:/resolve-create|/[^/]+/(?:restore|image-node-result))?",
        "PUT": root + r"/canvas-views/[^/]+",
    }
    if method in canvas_patterns and re.fullmatch(canvas_patterns[method], normalized_path) is not None:
        return True
    # Closed graph routes retain the same feature and project authority checks.
    # Unknown actions/methods never gain collaboration middleware admission.
    graph_patterns = {
        "GET": root + r"/(?:graphs(?:/[^/]+(?:/runs)?)?|graph-runs/[^/]+(?:/media/candidate/[^/]+)?)",
        "POST": root + r"/(?:graphs(?:/model-match|/[^/]+/(?:preflight|runs))?|graph-runs/[^/]+/(?:execute|approve|reject|cancel|pause|resume|retry-local|image-leaf-rerun(?:/preview)?|model/(?:preview|dispatch|refresh)|media/(?:preview|dispatch|execute|refresh|reconcile|review)))",
        "PUT": root + r"/graphs/[^/]+",
    }
    return method in graph_patterns and re.fullmatch(graph_patterns[method], normalized_path) is not None


class AssetQueryRoute(PrivateProductionRoute):
    """Keep invalid search input out of validation responses on this GET only."""

    def get_route_handler(self):
        handler = super().get_route_handler()
        async def checked(request):
            try:
                return await handler(request)
            except RequestValidationError:
                raise HTTPException(422, {"code": "EXPERIMENTAL_INVALID", "message": "ASSET_QUERY_INVALID"},
                                    headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}) from None
        return checked


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


class ModelReferenceImportRoute(PrivateProductionRoute):
    MAX_BODY = 12 * 1024 * 1024

    def get_route_handler(self):
        handler = super().get_route_handler()
        async def checked(request):
            headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
            try:
                payload, total = bytearray(), 0
                async for part in request.stream():
                    total += len(part)
                    if total > self.MAX_BODY:
                        raise HTTPException(413, {"code": "MODEL_REFERENCE_REQUEST_LIMIT"}, headers=headers)
                    payload.extend(part)
                request._body = bytes(payload)
                return await handler(request)
            except RequestValidationError:
                raise HTTPException(422, {"code": "MODEL_REFERENCE_REQUEST_INVALID"}, headers=headers) from None
            except HTTPException as exc:
                exc.headers = {**(exc.headers or {}), **headers}
                raise
        return checked


class ModelCameraExportRoute(PrivateProductionRoute):
    """Private camera reads and small closed source-selection export requests."""
    MAX_BODY = 4096

    def get_route_handler(self):
        handler = super().get_route_handler()
        async def checked(request):
            headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
            try:
                if request.method == "GET":
                    return await handler(request)
                payload = bytearray()
                async for part in request.stream():
                    if len(payload) + len(part) > self.MAX_BODY:
                        raise HTTPException(413, {"code": "MODEL_REFERENCE_CAMERA_REQUEST_LIMIT"}, headers=headers)
                    payload.extend(part)
                request._body = bytes(payload)
                def pairs(items):
                    result = {}
                    for key, value in items:
                        if key in result:
                            raise ValueError("duplicate")
                        result[key] = value
                    return result
                def invalid_constant(value):
                    raise ValueError("nonfinite")
                request._json = json.loads(request._body, object_pairs_hook=pairs, parse_constant=invalid_constant)
                return await handler(request)
            except (RequestValidationError, ValueError, UnicodeError, RecursionError):
                raise HTTPException(422, {"code": "MODEL_REFERENCE_CAMERA_REQUEST_INVALID"}, headers=headers) from None
            except HTTPException as exc:
                exc.headers = {**(exc.headers or {}), **headers}
                raise
        return checked


class VideoReferenceRoute(PrivateProductionRoute):
    """Bound source-only requests; validation never echoes private input."""
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def checked(request):
            headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
            try:
                payload = bytearray()
                async for part in request.stream():
                    if len(payload) + len(part) > 4096:
                        raise HTTPException(413, {"code": "VIDEO_REFERENCE_REQUEST_LIMIT"}, headers=headers)
                    payload.extend(part)
                request._body = bytes(payload)
                return await handler(request)
            except RequestValidationError:
                raise HTTPException(422, {"code": "VIDEO_REFERENCE_REQUEST_INVALID"}, headers=headers) from None
            except HTTPException as exc:
                exc.headers = {**(exc.headers or {}), **headers}
                raise
        return checked


def create_independent_workspace_router(service, authorize, require_flag, *, create_project, workspace_writer,
                                    graph_service=None, require_host_session=None, model_host_authority=None, production_service=None,
                                    bible_service=None, prompt_service=None, prompt_authoring_service=None,
                                    prompt_adoption_service=None, authority_lease=None, comic_authorize=None,
                                    studio_image_batches=None):
    router = APIRouter(tags=["Independent Studios V2"], route_class=PrivateProductionRoute)

    def access(nid, token, branch, permission):
        require_flag(FLAG)
        actor, scope = authorize(nid, token, branch, permission)
        service.store.key(nid, scope)
        if not isinstance(actor, str) or not actor:
            raise HTTPException(403, {"code": "CREATIVE_AUTHORITY_INVALID"})
        return actor, scope

    def invoke(nid, token, branch, permission, callback, *, commit=False, existing_owner=False, require_commit_authority=False, require_existing_owner=False):
        def operation():
            actor, scope = access(nid, token, branch, permission)
            def current_incarnation():
                try:
                    return service.store.incarnation(nid)
                except FileNotFoundError:
                    if existing_owner:
                        raise HTTPException(409, {"code": "STUDIO_STORAGE_READ_ONLY_UNAVAILABLE"}) from None
                    raise
            incarnation = current_incarnation()
            def guard():
                if (access(nid, token, branch, permission) != (actor, scope)
                        or current_incarnation() != incarnation):
                    raise HTTPException(403, {"code": "CREATIVE_AUTHORITY_CHANGED"})
            if require_commit_authority and authority_lease is None:
                raise HTTPException(503, {'code': 'CREATIVE_COMMIT_AUTHORITY_UNAVAILABLE'})
            lease = authority_lease(nid, token, actor, scope) if commit and authority_lease else nullcontext()
            with lease:
                guard()
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
        if require_existing_owner:
            # A stop of an existing image batch cannot manufacture the project
            # identity that its historical source would then appear to bind.
            with service.store.existing_owner_only():
                return api_call(operation)
        return api_call(operation)

    def commit_invoke(nid, token, branch, permission, callback):
        # Only bounded Prompt and metadata lifecycle operations use this lease.
        # Production/model routes retain their original non-blocking invoker.
        return invoke(nid, token, branch, permission, callback, commit=True)

    def handoff_invoke(nid, token, branch, permission, callback):
        # Source read and destination write reuse the original NOVEL/Studio
        # resolver. The Comic IMAGE-only fallback never authorizes this path.
        def target(actor, scope, target_guard):
            def source(source_actor, source_scope, source_guard):
                if (source_actor, source_scope) != (actor, scope):
                    raise HTTPException(403, {'code': 'COMIC_HANDOFF_AUTHORITY_CHANGED'})
                def current():
                    target_guard(); source_guard()
                current()
                result = callback(actor, scope, current)
                current()
                return result
            return invoke(nid, token, branch, 'domain.read', source)
        return invoke(nid, token, branch, permission, target, commit=permission == 'domain.write')

    from .production_execution_api import create_production_invoker
    mask_call = create_production_invoker(invoke, require_host_session=require_host_session,
        model_host_authority=model_host_authority, authority_precheck=access)

    def reject_closed_audio_batch(request, nid, token, branch, expected_actor, expected_scope, outer_guard):
        """Reuse the host checks solely to reject a mixed closed preflight.

        This cannot authorize a write and never initializes a project owner.
        Ordinary Studio operations retain the full incarnation-bound invoker.
        """
        actor, scope = access(nid, token, branch, 'domain.write')
        if (actor, scope) != (expected_actor, expected_scope):
            raise HTTPException(403, {'code': 'BATCH_STUDIO_AUTHORITY_CHANGED'})
        if require_host_session is None or model_host_authority is None:
            raise HTTPException(403, {'code': 'CREATIVE_MODEL_HOST_REQUIRED'})
        authority = model_host_authority(request, token)
        if not authority.principal:
            raise HTTPException(403, {'code': 'CREATIVE_MODEL_HOST_BINDING_REQUIRED'})
        def current():
            if access(nid, token, branch, 'domain.write') != (actor, scope):
                raise HTTPException(403, {'code': 'CREATIVE_AUTHORITY_CHANGED'})
            require_host_session(token); authority.guard(); outer_guard()
        current()
        require_flag('voice_direction_v2'); require_flag('audiobook_v2')
        try:
            from ..experimental.audiobook import AudiobookV2Service
            AudiobookV2Service._require_candidate_write_capacity()
        except Exception:
            current()
            raise
        # This diagnostic path must never become a write-capable shortcut if
        # the audio owner's normal gate is opened in a later version.
        raise HTTPException(503, {'code': 'BATCH_STUDIO_HOST_INVOKER_REQUIRED'})

    mask_call.reject_closed_audio_batch = reject_closed_audio_batch
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

    @router.get("/projects/{nid}/studio/comic-workspace")
    def comic_workspace(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        # A narrow bootstrap for IMAGE-authorized, source-free Comic. This is
        # deliberately not a generic Studio overview or preference activation.
        def operation():
            def access_comic(permission):
                require_flag(FLAG)
                for flag in ("comic_layouts_v2", "asset_lineage_v2", "ai_director_v2"):
                    require_flag(flag)
                if comic_authorize is None:
                    raise HTTPException(404, {"code": "COMIC_WORKSPACE_UNAVAILABLE"})
                actor, scope, source_free = comic_authorize(nid, x_session_token, x_branch_id, permission)
                service.store.key(nid, scope)
                if not isinstance(actor, str) or not actor or type(source_free) is not bool:
                    raise HTTPException(403, {"code": "COMIC_AUTHORITY_INVALID"})
                return actor, scope, source_free
            authority = access_comic("domain.read")
            actor, scope, source_free = authority
            def guard():
                if access_comic("domain.read") != authority:
                    raise HTTPException(403, {"code": "COMIC_AUTHORITY_CHANGED"})
            # The existing project/session lease preserves project lifetime; do
            # not call service.project/incarnation, which may create a File V2
            # marker on a fresh project. This read must not initialize anything.
            lease = authority_lease(nid, x_session_token, actor, scope) if authority_lease else nullcontext()
            with lease:
                guard()
                project = service.novels.get(nid)
                capabilities = {}
                for name, permission in (("can_mutate", "domain.write"), ("can_review", "domain.review")):
                    try:
                        capabilities[name] = access_comic(permission)[:2] == authority[:2]
                    except HTTPException as exc:
                        if exc.status_code != 403:
                            raise
                        capabilities[name] = False
                guard()
                return {"contract": "studio-comic-workspace/1", "project": {"id": project["id"], "title": project["title"]},
                        "source_free": source_free, "capabilities": capabilities}
        return api_call(operation)

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

    asset_query_router = APIRouter(route_class=AssetQueryRoute)

    @asset_query_router.get("/projects/{nid}/studio/assets",
                            openapi_extra={"parameters": StudioAssetQuery.openapi_parameters()})
    def assets(nid: str, request: Request,
               x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        def read(actor, scope, guard):
            query, include_deleted = StudioAssetQuery.from_query_params(request.query_params)
            from ..services.asset_query_index import AssetQueryBudgetExceeded, AssetQueryChanged, AssetQueryUnavailable
            from .asset_query_cursor import AssetQueryCursorRestart, AssetQueryCursorUnavailable
            try:
                return service.list_assets(nid, scope, include_deleted=include_deleted, query=query, actor_id=actor)
            except (AssetQueryCursorRestart, AssetQueryCursorUnavailable) as exc:
                guard()
                status = 409 if isinstance(exc, AssetQueryCursorRestart) else 503
                raise HTTPException(status, {"code": str(exc)}, headers={"Cache-Control": "no-store"}) from None
            except (AssetQueryBudgetExceeded, AssetQueryChanged, AssetQueryUnavailable) as exc:
                guard()
                status = 409 if isinstance(exc, AssetQueryChanged) else 503
                raise HTTPException(status, {"code": str(exc)}, headers={"Cache-Control": "no-store"}) from None
            except OSError:
                guard()
                raise HTTPException(503, {"code": "ASSET_QUERY_INDEX_UNAVAILABLE"},
                                    headers={"Cache-Control": "no-store"}) from None
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      read)

    router.include_router(asset_query_router)

    @router.post("/projects/{nid}/studio/assets", status_code=201)
    def upload(nid: str, body: ManualAssetImport,
               x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        # Check the original authority before disclosing the closed entry, but
        # do not initialize a project marker just to reject the write.
        access(nid, x_session_token, x_branch_id, "domain.write")
        if not settings.enable_project_capacity_admission:
            raise HTTPException(503, {"code": "PROJECT_CAPACITY_WRITE_UNAVAILABLE"})
        # Flag-gated path: the original asset owner still performs the write,
        # bounded by the capacity ledger admission in IndependentWorkspaceService.
        with service.store.existing_owner_only():
            return invoke(nid, x_session_token, x_branch_id, "domain.write",
                          lambda actor, scope, guard: service.import_asset(nid, scope, actor, body, guard),
                          existing_owner=True)

    from .video_reference import ReferencePreview, ReferenceSave
    video_reference_router = APIRouter(route_class=VideoReferenceRoute)

    def video_reference_call(nid, token, branch, permission, callback):
        def operation(actor, scope, guard):
            from ..experimental.common import StaleSourceError
            try:
                return callback(actor, scope, guard)
            except StaleSourceError:
                guard()
                raise HTTPException(409, {"code": "VIDEO_REFERENCE_SOURCE_CHANGED"}) from None
            except ValueError as error:
                guard()
                code = str(error)
                if re.fullmatch(r"VIDEO_REFERENCE_[A-Z_]{1,80}", code) is None:
                    code = "VIDEO_REFERENCE_UNAVAILABLE"
                raise HTTPException(422, {"code": code}) from None
        with service.store.existing_owner_only():
            return invoke(nid, token, branch, permission, operation)

    @video_reference_router.post("/projects/{nid}/studio/assets/{aid}/video-reference/preview")
    def preview_video_reference(nid: str, aid: str, body: ReferencePreview,
                                x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return video_reference_call(nid, x_session_token, x_branch_id, "domain.read",
            lambda actor, scope, guard: service.preview_video_reference(nid, scope, aid, body, guard))

    @video_reference_router.post("/projects/{nid}/studio/assets/{aid}/video-reference/save", status_code=201)
    def save_video_reference(nid: str, aid: str, body: ReferenceSave,
                             x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return video_reference_call(nid, x_session_token, x_branch_id, "domain.write",
            lambda actor, scope, guard: service.save_video_reference(nid, scope, actor, aid, body, guard))

    router.include_router(video_reference_router)

    def model_reference_call(nid, token, branch, permission, callback):
        def operation(actor, scope, guard):
            from ..experimental.common import StaleSourceError
            try:
                return callback(actor, scope, guard)
            except StaleSourceError:
                raise
            except ValueError as error:
                code = str(error)
                if re.fullmatch(r"MODEL_REFERENCE_GLB_[A-Z_]{1,80}", code):
                    raise HTTPException(422, {"code": code}) from None
                raise
        return invoke(nid, token, branch, permission, operation)

    model_reference_router = APIRouter(route_class=ModelReferenceImportRoute)

    @model_reference_router.post("/projects/{nid}/studio/assets/model-reference", status_code=201)
    def import_model_reference(nid: str, body: ManualModelReferenceImport,
                               x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        access(nid, x_session_token, x_branch_id, "domain.write")
        raise HTTPException(503, {"code": "PROJECT_CAPACITY_WRITE_UNAVAILABLE"})

    router.include_router(model_reference_router)

    from .workspace_models import StaticCameraExport
    camera_router = APIRouter(route_class=ModelCameraExportRoute)

    def camera_reference_call(nid, token, branch, callback):
        # Cover invoke's initial identity/authority reads as well as the
        # service callback: an observation cannot create a missing owner.
        with service.store.existing_owner_only():
            return model_reference_call(nid, token, branch, "domain.read", callback)

    @camera_router.post("/projects/{nid}/studio/assets/{aid}/model-reference/camera-export")
    def export_model_reference_camera(nid: str, aid: str, body: StaticCameraExport,
                                      x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return camera_reference_call(nid, x_session_token, x_branch_id,
            lambda actor, scope, guard: service.export_model_camera(nid, scope, aid, body, guard))

    @camera_router.get("/projects/{nid}/studio/assets/{aid}/model-reference/cameras")
    def inspect_model_reference_cameras(nid: str, aid: str,
                                       x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return camera_reference_call(nid, x_session_token, x_branch_id,
            lambda actor, scope, guard: service.inspect_model_reference(nid, scope, aid, guard, camera_inspection=True))

    router.include_router(camera_router)

    @router.get("/projects/{nid}/studio/assets/{aid}/model-reference")
    def inspect_model_reference(nid: str, aid: str,
                                x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return model_reference_call(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.inspect_model_reference(nid, scope, aid, guard))

    @router.get("/projects/{nid}/studio/assets/{aid}/model-reference/mesh-preview")
    def preview_model_reference_mesh(nid: str, aid: str,
                                     x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return model_reference_call(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.inspect_model_reference(nid, scope, aid, guard, mesh_preview=True))

    from .workspace_models import StaticSceneDepthExport, StaticSceneClayExport, StaticSceneClaySave

    @router.post("/projects/{nid}/studio/assets/{aid}/model-reference/depth-export")
    def export_model_reference_depth(nid: str, aid: str, body: StaticSceneDepthExport,
                                     x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return model_reference_call(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.export_model_depth(nid, scope, aid, body, guard))

    @router.post("/projects/{nid}/studio/assets/{aid}/model-reference/clay-export")
    def export_model_reference_clay(nid: str, aid: str, body: StaticSceneClayExport,
                                    x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return model_reference_call(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.export_model_clay(nid, scope, aid, body, guard))

    @router.post("/projects/{nid}/studio/assets/{aid}/model-reference/clay-save", status_code=201)
    def save_model_reference_clay(nid: str, aid: str, body: StaticSceneClaySave,
                                  x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return model_reference_call(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.save_model_clay_reference(nid, scope, actor, aid, body, guard))

    @router.get("/projects/{nid}/studio/assets/{aid}/model-reference/scene-preview")
    def preview_model_reference_mesh_scene(nid: str, aid: str,
                                     x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return model_reference_call(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.inspect_model_reference(nid, scope, aid, guard, scene_preview=True))

    @router.get("/projects/{nid}/studio/assets/{aid}/model-reference/materials")
    def inspect_model_reference_materials(nid: str, aid: str,
                                     x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return model_reference_call(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.inspect_model_reference(nid, scope, aid, guard, material_inspection=True))

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
        return commit_invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.lifecycle(nid, scope, aid, expected_version, guard=guard, actor_id=actor))

    @router.post("/projects/{nid}/studio/assets/{aid}/restore")
    def restore(nid: str, aid: str, body: AssetVersion,
                x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return commit_invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.lifecycle(nid, scope, aid, body.expected_version, restore=True, guard=guard, actor_id=actor))

    @router.get("/projects/{nid}/studio/storage")
    def storage(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        # The original owner and authority chain apply throughout the request;
        # a read must never provision a missing project incarnation.
        with service.store.existing_owner_only():
            return invoke(nid, x_session_token, x_branch_id, "domain.read",
                          lambda actor, scope, guard: service.storage(nid, scope), existing_owner=True)

    @router.get("/projects/{nid}/studio/capacity")
    def capacity_diagnostics(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        # Read-only observation: no ledger initialization, reservation or gate.
        with service.store.existing_owner_only():
            return invoke(nid, x_session_token, x_branch_id, "domain.read",
                          lambda actor, scope, guard: service.capacity_diagnostics(nid, scope),
                          existing_owner=True)

    @router.post("/projects/{nid}/studio/capacity/reconcile")
    def capacity_reconcile(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        # Explicit reconcile is a server-computed write to the capacity ledger;
        # it never admits a content write (the write gate stays closed).
        with service.store.existing_owner_only():
            return invoke(nid, x_session_token, x_branch_id, "domain.write",
                          lambda actor, scope, guard: service.capacity_reconcile(nid, scope, actor),
                          existing_owner=True)

    @router.put("/projects/{nid}/studio/capacity/limit")
    def capacity_limit(nid: str, body: ProjectCapacityLimitUpdate,
                       x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        # The original project-management lease, incarnation and ledger CAS are
        # all required; the handler itself does not define a new authority owner.
        with service.store.existing_owner_only():
            return invoke(nid, x_session_token, x_branch_id, "domain.write",
                          lambda actor, scope, guard: service.capacity_adjust_limit(
                              nid, scope, actor, x_session_token, body),
                          existing_owner=True)

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

    @router.get("/projects/{nid}/studio/assets/{aid}/history")
    def audio_history_status(nid: str, aid: str, request: Request, x_session_token: str | None = Header(None),
                             x_branch_id: str | None = Header(None)):
        from .audio_history_status import uncaptured_audio_status
        from .. import api as original_api
        sessions = original_api.trusted_session_resolver
        try:
            session = sessions.binding_observation(x_session_token) if x_session_token else None
        except KeyError:
            raise HTTPException(401, {"code": "SESSION_REQUIRED"}) from None

        def session_guard():
            if session is not None:
                try:
                    if not sessions.revalidate_binding(x_session_token, session):
                        raise KeyError()
                except KeyError:
                    raise HTTPException(403, {"code": "AUDIO_HISTORY_AUTHORITY_CHANGED"}) from None

        authority_observation = None
        def observe(actor, scope, guard):
            nonlocal authority_observation
            from .audio_history_authority import file_collaboration_observation
            # Query validation follows original project authorization and never
            # provisions a cursor key or accepts a continuation as an empty page.
            guard()
            session_guard()
            if len(request.scope.get('query_string', b'')) > 2048:
                raise HTTPException(422, {"code": "AUDIO_HISTORY_QUERY_INVALID"})
            limits = request.query_params.getlist('limit')
            try:
                from pydantic import TypeAdapter
                parsed_limits = [TypeAdapter(int).validate_python(value) for value in limits]
            except ValueError:
                raise HTTPException(422, {"code": "AUDIO_HISTORY_QUERY_INVALID"}) from None
            if len(parsed_limits) > 1 or any(not 1 <= value <= 50 for value in parsed_limits):
                raise HTTPException(422, {"code": "AUDIO_HISTORY_QUERY_INVALID"})
            if request.query_params.getlist('cursor'):
                raise HTTPException(409, {"code": "AUDIO_HISTORY_CURSOR_UNAVAILABLE"})
            if scope.get("mode") == "collaboration":
                authority_observation = (actor, scope, file_collaboration_observation(
                    service, nid, scope, actor, x_session_token))
            def checked():
                guard()
                session_guard()
            result = service.audio_history(nid, scope, actor, aid, checked, limit=(parsed_limits[0] if parsed_limits else 50))
            if authority_observation is not None:
                checked()
                if file_collaboration_observation(service, nid, scope, actor, x_session_token) != authority_observation[2]:
                    raise HTTPException(403, {"code": "AUDIO_HISTORY_AUTHORITY_CHANGED"})
            return result

        with service.store.existing_owner_only():
            session_guard()
            result = invoke(nid, x_session_token, x_branch_id, "domain.read", observe)
            session_guard()
            if authority_observation is not None:
                from .audio_history_authority import file_collaboration_observation
                actor, scope, initial = authority_observation
                if file_collaboration_observation(service, nid, scope, actor, x_session_token) != initial:
                    raise HTTPException(403, {"code": "AUDIO_HISTORY_AUTHORITY_CHANGED"})
            return result

    @router.get("/projects/{nid}/studio/assets/{aid}/history/{version_id}")
    def audio_history_version(nid: str, aid: str, version_id: str,
                              x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.audio_history_version(
                          nid, scope, actor, aid, version_id, guard))

    @router.get("/projects/{nid}/studio/assets/{aid}/history/{version_id}/download")
    def audio_history_download(nid: str, aid: str, version_id: str,
                               x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        view, data = invoke(nid, x_session_token, x_branch_id, "domain.read",
                            lambda actor, scope, guard: service.audio_history_content(
                                nid, scope, actor, aid, version_id, guard))
        media_type = view["metadata"]["media_type"]
        return Response(data, media_type=media_type, headers={
            "Content-Disposition": f"attachment; filename=\"history-{version_id[:12]}\"; filename*=UTF-8''{quote('history-' + version_id[:12], safe='')}",
            "X-Asset-SHA256": view["sha256"], "X-Asset-Version": str(view["asset_version"]),
            "X-History-Version-Id": version_id})

    @router.post("/projects/{nid}/studio/assets/{aid}/history/migrate")
    def audio_history_migrate(nid: str, aid: str, body: AssetVersion,
                              x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        # Explicit migration of a legacy uncaptured audio asset: reads never do
        # this, and no baseline is fabricated from Job/Timeline history.
        return commit_invoke(nid, x_session_token, x_branch_id, "domain.write",
                             lambda actor, scope, guard: service.capture_audio_history(
                                 nid, scope, actor, aid, body.expected_version, guard))

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
        router.include_router(create_prompt_authoring_router(prompt_authoring_service, commit_invoke))

    if prompt_adoption_service is not None:
        # R3-I: two closed routes only — adopt into a STORYBOARD shot, and read the pinned
        # adoptions. No generic owner write surface is opened.
        from .prompt_adoption_api import create_prompt_adoption_router
        router.include_router(create_prompt_adoption_router(prompt_adoption_service, commit_invoke))

    if production_service is not None:
        # The Audio manifest adapter resolves its production owner once at mount;
        # keep that owner's rebindable store/workspace live, like every other
        # router closure in this module, without editing the author's files.
        class _LiveOwner:
            def __getattr__(self, name): return getattr(production_service, name)
        class _LiveStore:
            def __getattr__(self, name): return getattr(production_service.store, name)
        class _LiveWorkspace:
            def __getattr__(self, name): return getattr(production_service.workspace, name)
        class _AudioManifestOwner(_LiveOwner):
            @property
            def store(self): return _LiveStore()
            @property
            def workspace(self): return _LiveWorkspace()
        from ..experimental.audio_manifest_api import create_audio_manifest_router
        router.include_router(create_audio_manifest_router(_AudioManifestOwner(), mask_call))
        if studio_image_batches is not None:
            studio_image_batches.configure_studio_image(production_service, mask_call)
        from .production_execution_api import create_production_execution_router
        router.include_router(create_production_execution_router(production_service, invoke,
            require_host_session=require_host_session, model_host_authority=model_host_authority,
            handoff_invoke=handoff_invoke))

    if graph_service is not None:
        from .graph_api import create_creative_graph_router
        router.include_router(create_creative_graph_router(graph_service, invoke, require_host_session=require_host_session,
            model_host_authority=model_host_authority, usage_production=production_service))
    return router




