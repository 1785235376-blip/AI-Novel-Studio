"""Closed, explicit production commands on original Host and scope authority."""
from contextlib import ExitStack
from urllib.parse import quote
from fastapi import APIRouter, Header, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError

from ..experimental.production_lineage_api import PrivateProductionRoute
from ..services.v1_capability_service import CapabilityVersionConflict
from ..services.audiobook_service import AudiobookError
from ..audio_production_store import AudioStateVersionConflict
from .production_execution_models import (MediaCommand, MediaCreate, CanvasImageNodeQueueResolve, MediaJobAction, CanvasImageNodeTargetView, CanvasImageNodeJobDiscard, MediaReview, TimelineSave, TimelineRender,
    TimelineEdit, TimelineRestore, TimelineExportPreview, TimelineExport,
    TimelineTransferPreview, TimelineTransferImport, TimelineTransferDownload, TimelinePlaybackPreview, TimelinePlaybackBuild, TimelinePlaybackAttestation,
    TimelineWaveformPreview, StudioProductionQuery, ProductionJobOwner)

from .canvas_video_task import CanvasVideoCommand, CanvasVideoQueue

Owner = ProductionJobOwner


class ImageNodeQueueResolveRoute(PrivateProductionRoute):
    """Closed metadata-only lookup, not another queue admission path."""
    MAX_BODY = 16 * 1024
    MAX_RESPONSE = 256 * 1024

    def get_route_handler(self):
        handler = super().get_route_handler()
        async def checked(request):
            headers = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}
            try:
                payload = bytearray()
                async for part in request.stream():
                    if len(payload) + len(part) > self.MAX_BODY:
                        raise HTTPException(413, {'code': 'STUDIO_IMAGE_NODE_QUEUE_REQUEST_LIMIT'})
                    payload.extend(part)
                request._body = bytes(payload)
                response = await handler(request)
                if len(response.body) > self.MAX_RESPONSE:
                    raise HTTPException(413, {'code': 'STUDIO_IMAGE_NODE_QUEUE_RESPONSE_LIMIT'})
                return response
            except RequestValidationError:
                raise HTTPException(422, {'code': 'STUDIO_IMAGE_NODE_QUEUE_REQUEST_INVALID'}, headers=headers) from None
            except HTTPException as exc:
                code = {400:'STUDIO_IMAGE_NODE_QUEUE_REQUEST_INVALID', 403:'STUDIO_IMAGE_NODE_QUEUE_FORBIDDEN',
                    404:'STUDIO_IMAGE_NODE_QUEUE_NOT_FOUND', 409:'STUDIO_IMAGE_NODE_QUEUE_CHANGED',
                    413:'STUDIO_IMAGE_NODE_QUEUE_LIMIT', 422:'STUDIO_IMAGE_NODE_QUEUE_REQUEST_INVALID'}.get(
                        exc.status_code, 'STUDIO_IMAGE_NODE_QUEUE_REJECTED')
                raise HTTPException(exc.status_code, {'code': code},
                    headers={**(exc.headers or {}), **headers}) from None
            except Exception:
                raise HTTPException(503, {'code': 'STUDIO_IMAGE_NODE_QUEUE_LOOKUP_UNKNOWN'}, headers=headers) from None
        return checked


class ImageNodeTargetObservationRoute(PrivateProductionRoute):
    """Closed metadata comparison; errors disclose no lower-owner values."""
    MAX_BODY = 4 * 1024
    MAX_RESPONSE = 256 * 1024
    ERROR_PREFIX = 'STUDIO_IMAGE_NODE_TARGET_OBSERVATION_'

    def get_route_handler(self):
        import json
        handler = super().get_route_handler()

        async def checked(request):
            headers = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}
            prefix = self.ERROR_PREFIX
            try:
                payload = bytearray()
                async for part in request.stream():
                    if len(payload) + len(part) > self.MAX_BODY:
                        raise HTTPException(413, {'code': prefix + 'LIMIT'})
                    payload.extend(part)

                def pairs(items):
                    result = {}
                    for key, value in items:
                        if key in result:
                            raise ValueError('duplicate key')
                        result[key] = value
                    return result

                try:
                    parsed = json.loads(payload, object_pairs_hook=pairs)
                    if not isinstance(parsed, dict):
                        raise ValueError('object required')
                except (ValueError, UnicodeDecodeError):
                    raise HTTPException(422, {'code': prefix + 'INVALID'}) from None
                request._body = bytes(payload)
                response = await handler(request)
                if len(response.body) > self.MAX_RESPONSE:
                    raise HTTPException(413, {'code': prefix + 'LIMIT'})
                return response
            except RequestValidationError:
                raise HTTPException(422, {'code': prefix + 'INVALID'}, headers=headers) from None
            except HTTPException as exc:
                code = {400: 'INVALID', 401: 'AUTH_REJECTED', 403: 'FORBIDDEN',
                    404: 'UNAVAILABLE', 409: 'CHANGED', 413: 'LIMIT', 422: 'INVALID'}.get(exc.status_code, 'UNKNOWN')
                status = exc.status_code if exc.status_code in {400, 401, 403, 404, 409, 413, 422} else 503
                raise HTTPException(status, {'code': prefix + code},
                    headers={**(exc.headers or {}), **headers}) from None
            except Exception:
                raise HTTPException(503, {'code': prefix + 'UNKNOWN'}, headers=headers) from None
        return checked


class ImageNodeTargetViewRoute(ImageNodeTargetObservationRoute):
    """Return one exact original public display record, never history payloads."""
    MAX_RESPONSE = 8 * 1024 * 1024
    ERROR_PREFIX = 'STUDIO_IMAGE_NODE_TARGET_VIEW_'


class ImageNodeJobObservationRoute(ImageNodeTargetObservationRoute):
    """Closed original Job metadata without current-Canvas dependencies."""
    ERROR_PREFIX = 'STUDIO_IMAGE_NODE_JOB_OBSERVATION_'


class ImageNodeJobDiscardRoute(ImageNodeTargetObservationRoute):
    """Explicit original-queue discard with closed acknowledgement/errors."""
    ERROR_PREFIX = 'STUDIO_IMAGE_NODE_JOB_DISCARD_'


class TimelineWaveformRoute(PrivateProductionRoute):
    """Bound and sanitize only this new observation request, never old routes."""
    MAX_BODY = 4096

    def get_route_handler(self):
        handler = super().get_route_handler()
        async def checked(request):
            headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
            try:
                parts, total = [], 0
                async for part in request.stream():
                    total += len(part)
                    if total > self.MAX_BODY:
                        raise HTTPException(413, {"code": "STUDIO_WAVEFORM_REQUEST_LIMIT"}, headers=headers)
                    parts.append(part)
                request._body = b"".join(parts)
                return await handler(request)
            except RequestValidationError:
                raise HTTPException(422, {"code": "STUDIO_WAVEFORM_REQUEST_INVALID"}, headers=headers) from None
            except HTTPException as exc:
                exc.headers = {**(exc.headers or {}), **headers}
                raise
        return checked


def create_production_invoker(invoke, *, require_host_session, model_host_authority):
    def call(request, nid, token, branch, permission, callback, *, model=False):
        def operation(actor, scope, guard):
            if require_host_session is None or model_host_authority is None:
                raise HTTPException(403, {"code": "CREATIVE_MODEL_HOST_REQUIRED"})
            authority = model_host_authority(request, token)
            if not authority.principal: raise HTTPException(403, {"code": "CREATIVE_MODEL_HOST_BINDING_REQUIRED"})
            def current():
                guard(); require_host_session(token); authority.guard()
                if model:
                    from .ai_execution import require_execution
                    require_execution()
            current()
            try: result = callback(actor, scope, current)
            except AudiobookError as exc:
                current()
                raise HTTPException(exc.status, {"code": exc.code}) from None
            except AudioStateVersionConflict as exc:
                current()
                raise HTTPException(409, {"code": exc.code}) from None
            except CapabilityVersionConflict as exc:
                current()
                # Never echo private owner tokens, prompts, URLs or context from
                # a lower-level job owner's raw CAS exception.
                raise HTTPException(409, {"code": "STUDIO_PRODUCTION_VERSION_CONFLICT", "current_version": exc.current.get("version")}) from None
            except Exception:
                current(); raise
            current()
            return result
        return invoke(nid, token, branch, permission, operation)

    return call


class ComicHandoffRoute(PrivateProductionRoute):
    """Closed handoff JSON only; no uploaded images, executable data or paths."""
    MAX_BODY = 16 * 1024
    MAX_RESPONSE = 12 * 1024 * 1024
    MAX_PNG = 8 * 1024 * 1024

    def get_route_handler(self):
        import json
        from fastapi.responses import JSONResponse
        handler = super().get_route_handler()
        async def checked(request):
            headers = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}
            def pairs(items):
                result = {}
                for key, value in items:
                    if key in result: raise ValueError('duplicate field')
                    result[key] = value
                return result
            def constant(value): raise ValueError('nonfinite JSON')
            try:
                payload = bytearray()
                async for part in request.stream():
                    if len(payload) + len(part) > self.MAX_BODY:
                        raise HTTPException(413, {'code': 'COMIC_HANDOFF_REQUEST_LIMIT'})
                    payload.extend(part)
                request._body = bytes(payload)
                if request.method == 'GET':
                    if payload: raise ValueError('GET body')
                else:
                    if request.headers.get('content-type', '').split(';')[0].strip().lower() != 'application/json':
                        raise HTTPException(415, {'code': 'COMIC_HANDOFF_JSON_REQUIRED'})
                    request._json = json.loads(request._body, object_pairs_hook=pairs, parse_constant=constant)
                response = await handler(request)
                if len(response.body) > self.MAX_RESPONSE:
                    raise HTTPException(413, {'code': 'COMIC_HANDOFF_RESPONSE_LIMIT'})
                return response
            except (RequestValidationError, ValueError, UnicodeError, RecursionError):
                return JSONResponse({'detail': {'code': 'COMIC_HANDOFF_REQUEST_INVALID'}}, status_code=422, headers=headers)
            except HTTPException as error:
                # Original domain errors can contain raw owner exception text.
                # This new HTTP contract exposes codes and bounded CAS only.
                import re
                raw = error.detail if isinstance(error.detail, dict) else {}
                code = raw.get('code')
                if not isinstance(code, str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', code):
                    code = 'COMIC_HANDOFF_REQUEST_REJECTED'
                detail = {'code': code}
                version = raw.get('current_version')
                if (code == 'STUDIO_PRODUCTION_VERSION_CONFLICT'
                        and type(version) is int and 1 <= version <= 8):
                    detail['current_version'] = version
                return JSONResponse({'detail': detail}, status_code=error.status_code, headers=headers)
            except Exception:
                # A lost write acknowledgement is not a failed/rolled-back
                # operation. The caller must inspect its exact request ID.
                return JSONResponse({'detail': {'code': 'COMIC_HANDOFF_OUTCOME_UNKNOWN'}}, status_code=503, headers=headers)
        return checked


def create_comic_handoff_routes(service, invoke, *, require_host_session, model_host_authority):
    import base64
    import hashlib
    import struct
    from pydantic import Field
    from ..experimental.media import StrictModel
    from ..experimental.comic_timeline_handoff import HandoffRequest, HandoffConfirm
    from ..services.comic_page_origin import FEATURES

    class ReceiptVersion(StrictModel):
        expected_version: int = Field(ge=1, le=8, strict=True)

    router = APIRouter(route_class=ComicHandoffRoute)
    root = '/projects/{nid}/studio/production/comic-handoffs'
    call = create_production_invoker(invoke, require_host_session=require_host_session,
                                    model_host_authority=model_host_authority) if invoke else None

    def perform(request, nid, token, branch, permission, operation):
        from ..experimental.flags import require_flag
        for flag in sorted(FEATURES): require_flag(flag)
        if call is None or service.comic_handoff is None:
            raise HTTPException(404, {'code': 'COMIC_HANDOFF_UNAVAILABLE'})
        def current(actor, scope, guard):
            with service.comic_handoff.comic.page_source_authority(request, nid, token, branch):
                return operation(service.comic_handoff, actor, scope, guard)
        with service.store.existing_owner_only():
            return call(request, nid, token, branch, permission, current)

    @router.post(root + '/preview')
    def preview(nid: str, request: Request, body: HandoffRequest,
                x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        def operation(handoff, actor, scope, guard):
            report, images = handoff.preview(nid, scope, actor, body, guard)
            if len(images) != len(report['pages']):
                raise ValueError('COMIC_HANDOFF_PREVIEW_PROOF_INVALID')
            if sum(map(len, images)) > ComicHandoffRoute.MAX_PNG:
                raise HTTPException(413, {'code': 'COMIC_HANDOFF_PREVIEW_PNG_LIMIT'})
            pages = []
            for index, (data, pin) in enumerate(zip(images, report['pages'])):
                if (not isinstance(data, bytes) or len(data) < 24 or data[:8] != b'\x89PNG\r\n\x1a\n'
                        or hashlib.sha256(data).hexdigest() != pin['png_sha256']
                        or struct.unpack('>II', data[16:24]) != (pin['width'], pin['height'])):
                    raise ValueError('COMIC_HANDOFF_PREVIEW_PROOF_INVALID')
                pages.append({'index': index, 'png_base64': base64.b64encode(data).decode('ascii')})
            guard()
            return {'preview': report, 'pages': pages}
        return perform(request, nid, x_session_token, x_branch_id, 'domain.read', operation)

    @router.post(root)
    def confirm(nid: str, request: Request, body: HandoffConfirm,
                x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return perform(request, nid, x_session_token, x_branch_id, 'domain.write',
                       lambda h, a, s, g: h.confirm(nid, s, a, body.model_dump(), g))

    @router.get(root + '/{request_id}')
    def status(nid: str, request_id: str, request: Request,
               x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return perform(request, nid, x_session_token, x_branch_id, 'domain.read',
                       lambda h, a, s, g: h.status(nid, s, a, request_id, g))

    @router.post(root + '/{request_id}/resume')
    def resume(nid: str, request_id: str, request: Request, body: ReceiptVersion,
               x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return perform(request, nid, x_session_token, x_branch_id, 'domain.write',
                       lambda h, a, s, g: h.resume(nid, s, a, request_id, body.expected_version, g))

    @router.post(root + '/{request_id}/cancel')
    def cancel(nid: str, request_id: str, request: Request, body: ReceiptVersion,
               x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return perform(request, nid, x_session_token, x_branch_id, 'domain.write',
                       lambda h, a, s, g: h.cancel(nid, s, a, request_id, body.expected_version, g))
    return router


def create_production_execution_router(service, invoke, *, require_host_session, model_host_authority, handoff_invoke=None):
    router = APIRouter(tags=["Studio Production Execution V2"], route_class=PrivateProductionRoute)

    call = create_production_invoker(invoke, require_host_session=require_host_session, model_host_authority=model_host_authority)

    router.include_router(create_comic_handoff_routes(service, handoff_invoke,
        require_host_session=require_host_session, model_host_authority=model_host_authority))

    from .comic_image_generation import ComicImageRequest, ComicImageAdopt

    @router.post("/projects/{nid}/studio/production/comic-pages/{rid}/panels/{panel_id}/image-request")
    def comic_image_request(nid: str, rid: str, panel_id: str, request: Request, body: ComicImageRequest,
                            x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        with service.store.existing_owner_only():
            return call(request, nid, x_session_token, x_branch_id, "domain.read",
                lambda actor, scope, guard: service._comic_owner().image_request(nid, scope, actor, rid, panel_id, body, guard))

    @router.post("/projects/{nid}/studio/production/comic-pages/{rid}/panels/{panel_id}/adopt-image")
    def comic_image_adopt(nid: str, rid: str, panel_id: str, request: Request, body: ComicImageAdopt,
                          x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        with service.store.existing_owner_only():
            return call(request, nid, x_session_token, x_branch_id, "domain.write",
                lambda actor, scope, guard: service._comic_owner().adopt(nid, scope, actor, rid, panel_id, body, guard))

    waveform_router = APIRouter(route_class=TimelineWaveformRoute)

    @waveform_router.post("/projects/{nid}/studio/production/timelines/{tid}/waveform-preview")
    def waveform_preview(nid: str, tid: str, request: Request, body: TimelineWaveformPreview,
                         x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        # Cover the original invoker's pre-callback incarnation check too.
        with service.store.existing_owner_only():
            return call(request, nid, x_session_token, x_branch_id, "domain.read",
                        lambda actor, scope, guard: service.timeline_waveform_preview(nid, scope, actor, tid, body, guard))

    @waveform_router.post("/projects/{nid}/studio/production/timelines/{tid}/source-bounds")
    def source_bounds(nid: str, tid: str, request: Request, body: TimelineWaveformPreview,
                      x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        with service.store.existing_owner_only():
            return call(request, nid, x_session_token, x_branch_id, "domain.read",
                        lambda actor, scope, guard: service.timeline_source_bounds(nid, scope, actor, tid, body, guard))

    router.include_router(waveform_router)

    @router.get("/projects/{nid}/studio/production/providers")
    def providers(nid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.read", lambda actor, scope, guard: service.providers(nid, scope, actor, guard))

    @router.post("/projects/{nid}/studio/production/timelines/{tid}/playback-preview")
    def playback_preview(nid: str, tid: str, request: Request, body: TimelinePlaybackPreview, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.read", lambda actor, scope, guard: service.timeline_playback_preview(nid, scope, actor, tid, body, guard))

    @router.post("/projects/{nid}/studio/production/timelines/{tid}/playback-build")
    def playback_build(nid: str, tid: str, request: Request, body: TimelinePlaybackBuild, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.write", lambda actor, scope, guard: service.timeline_playback_build(nid, scope, actor, tid, body, guard))

    @router.post("/projects/{nid}/studio/production/timelines/{tid}/playback-attestation")
    def playback_attestation(nid: str, tid: str, request: Request, body: TimelinePlaybackAttestation, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.read", lambda actor, scope, guard: service.timeline_playback_attest(nid, scope, actor, tid, body, guard))

    @router.post("/projects/{nid}/studio/production/preview")
    def preview(nid: str, request: Request, body: MediaCommand, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.read", lambda actor, scope, guard: service.preview(nid, scope, actor, body, guard)[0], model=body.operation_id not in {"m8.audio.trim", "m5.image.cutout", "m5.image.composite"})

    @router.post("/projects/{nid}/studio/production/jobs", status_code=201)
    def create(nid: str, request: Request, body: MediaCreate, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.write", lambda actor, scope, guard: service.create(nid, scope, actor, body, guard), model=body.command.operation_id not in {"m8.audio.trim", "m5.image.cutout", "m5.image.composite"})

    node_queue_reads = APIRouter(route_class=ImageNodeQueueResolveRoute)

    @node_queue_reads.post('/projects/{nid}/studio/production/jobs/image/resolve-create')
    def resolve_image_node_create(nid: str, request: Request, body: CanvasImageNodeQueueResolve,
                                  x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        with ExitStack() as observations:
            observations.enter_context(service.store.existing_owner_only())
            graph = getattr(service, 'graph_service', None)
            if graph is not None:
                observations.enter_context(graph.store.existing_owner_only())
            return call(request, nid, x_session_token, x_branch_id, 'domain.read',
                lambda actor,scope,guard:service.resolve_image_node_create(nid,scope,actor,body,guard))

    router.include_router(node_queue_reads)

    node_target_observations = APIRouter(route_class=ImageNodeTargetObservationRoute)

    @node_target_observations.post('/projects/{nid}/studio/production/jobs/image/{jid}/target-observation')
    def observe_image_node_target(nid: str, jid: str, request: Request, body: MediaJobAction,
                                  x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        with ExitStack() as observations:
            observations.enter_context(service.store.existing_owner_only())
            graph = getattr(service, 'graph_service', None)
            if graph is not None:
                observations.enter_context(graph.store.existing_owner_only())
            return call(request, nid, x_session_token, x_branch_id, 'domain.read',
                lambda actor, scope, guard: service.observe_image_node_target(nid, scope, actor, jid, body, guard))

    router.include_router(node_target_observations)

    node_target_views = APIRouter(route_class=ImageNodeTargetViewRoute)

    @node_target_views.post('/projects/{nid}/studio/production/jobs/image/{jid}/target-view')
    def view_image_node_target(nid: str, jid: str, request: Request, body: CanvasImageNodeTargetView,
                               x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        with ExitStack() as observations:
            observations.enter_context(service.store.existing_owner_only())
            graph = getattr(service, 'graph_service', None)
            if graph is not None:
                observations.enter_context(graph.store.existing_owner_only())
            return call(request, nid, x_session_token, x_branch_id, 'domain.read',
                lambda actor, scope, guard: service.view_image_node_target(nid, scope, actor, jid, body, guard))

    router.include_router(node_target_views)

    node_job_observations = APIRouter(route_class=ImageNodeJobObservationRoute)

    @node_job_observations.post('/projects/{nid}/studio/production/jobs/image/{jid}/node-observation')
    def observe_image_node_job(nid: str, jid: str, request: Request, body: MediaJobAction,
                               x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        with ExitStack() as observations:
            observations.enter_context(service.store.existing_owner_only())
            graph = getattr(service, 'graph_service', None)
            if graph is not None:
                observations.enter_context(graph.store.existing_owner_only())
            return call(request, nid, x_session_token, x_branch_id, 'domain.read',
                lambda actor, scope, guard: service.observe_image_node_job(nid, scope, actor, jid, body, guard))

    router.include_router(node_job_observations)

    node_job_discards = APIRouter(route_class=ImageNodeJobDiscardRoute)

    @node_job_discards.post('/projects/{nid}/studio/production/jobs/image/{jid}/node-discard')
    def discard_image_node_job(nid: str, jid: str, request: Request, body: CanvasImageNodeJobDiscard,
                               x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        with ExitStack() as observations:
            observations.enter_context(service.store.existing_owner_only())
            graph = getattr(service, 'graph_service', None)
            if graph is not None:
                observations.enter_context(graph.store.existing_owner_only())

            def source(actor, scope, read_guard):
                def write(write_actor, write_scope, write_guard):
                    if (write_actor, write_scope) != (actor, scope):
                        raise HTTPException(403, {'code': 'CREATIVE_AUTHORITY_CHANGED'})
                    def current():
                        read_guard()
                        write_guard()
                    current()
                    return service.discard_image_node_job(nid, scope, actor, jid, body, current)
                return call(request, nid, x_session_token, x_branch_id, 'domain.write', write)
            return call(request, nid, x_session_token, x_branch_id, 'domain.read', source)

    router.include_router(node_job_discards)

    @router.get("/projects/{nid}/studio/production/jobs",
                openapi_extra={"parameters": StudioProductionQuery.openapi_parameters()})
    def jobs(nid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        def read(actor, scope, guard):
            # Query validation must not overtake any original refusal, including
            # neutral-project activation. list() independently rechecks _base.
            service._base(nid, scope, actor, guard)
            query = StudioProductionQuery.from_query_params(request.query_params)
            return service.list(nid, scope, actor, guard, query=query)
        return call(request, nid, x_session_token, x_branch_id, "domain.read", read)

    @router.get("/projects/{nid}/studio/production/jobs/{owner}/{jid}")
    def job(nid: str, owner: Owner, jid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.read", lambda actor, scope, guard: service.get(nid, scope, actor, owner, jid, guard))

    @router.get("/projects/{nid}/studio/production/jobs/{owner}/{jid}/candidate")
    def candidate(nid: str, owner: Owner, jid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        row, data = call(request, nid, x_session_token, x_branch_id, "domain.read", lambda actor, scope, guard: service.candidate(nid, scope, actor, owner, jid, guard))
        return Response(data, media_type=row["media_type"], headers={"Cache-Control": "no-store", "X-Asset-SHA256": row["sha256"],
            "X-Asset-Version": str(row["version"]), "Content-Disposition": f"attachment; filename*=UTF-8''{quote(row['filename'], safe='')}"})

    @router.post("/projects/{nid}/studio/production/jobs/{owner}/{jid}/execute")
    def execute(nid: str, owner: Owner, jid: str, request: Request, body: MediaJobAction, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.write", lambda actor, scope, guard: service.execute(nid, scope, actor, owner, jid, body, guard))

    @router.post("/projects/{nid}/studio/production/jobs/video/{jid}/refresh")
    def refresh(nid: str, jid: str, request: Request, body: MediaJobAction, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.write", lambda actor, scope, guard: service.refresh_video(nid, scope, actor, jid, body, guard), model=True)

    @router.post("/projects/{nid}/studio/production/jobs/{owner}/{jid}/cancel")
    def cancel(nid: str, owner: Owner, jid: str, request: Request, body: MediaJobAction, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.write", lambda actor, scope, guard: service.cancel(nid, scope, actor, owner, jid, body, guard))

    @router.post("/projects/{nid}/studio/production/jobs/{owner}/{jid}/review")
    def review(nid: str, owner: Owner, jid: str, request: Request, body: MediaReview, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.review", lambda actor, scope, guard: service.review(nid, scope, actor, owner, jid, body, guard))

    @router.post("/projects/{nid}/studio/production/jobs/{owner}/{jid}/reconcile")
    def reconcile(nid: str, owner: Owner, jid: str, request: Request, body: MediaJobAction, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.write", lambda actor, scope, guard: service.reconcile(nid, scope, actor, owner, jid, body, guard))

    @router.get("/novels/{nid}/experimental/production/assets/{aid}/studio-timeline-usages")
    def asset_usages(nid: str, aid: str, request: Request,
                     x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        from .asset_usages import timeline_asset_usages
        from .asset_usage_paging import query_options
        from .asset_usage_budget import usage_read_budget, UsageBudgetError
        from .asset_usage_read_mode import usage_coordination, ReadOnlyCoordinationUnavailable
        def observe(actor, scope, guard):
            try:
                return timeline_asset_usages(service, nid, scope, actor, aid, guard,
                                             **(query_options(request) or {}))
            except (ValueError, TypeError, KeyError, FileNotFoundError, PermissionError, UsageBudgetError):
                guard()
                raise HTTPException(409, {"code": "STUDIO_TIMELINE_USAGE_UNAVAILABLE"}) from None
        with service.store.existing_owner_only(), usage_read_budget(bool(request.scope.get('query_string'))), usage_coordination(request):
            try:
                return call(request, nid, x_session_token, x_branch_id, "domain.read",
                    observe)
            except ReadOnlyCoordinationUnavailable:
                raise HTTPException(409, {'code': 'STUDIO_USAGE_STRICT_READ_ONLY_UNAVAILABLE'}) from None
            except (ValueError, TypeError, KeyError, FileNotFoundError, PermissionError, UsageBudgetError):
                raise HTTPException(409, {"code": "STUDIO_TIMELINE_USAGE_UNAVAILABLE"}) from None
            except (AttributeError, RecursionError):
                if not request.scope.get('query_string'):
                    raise
                raise HTTPException(409, {"code": "STUDIO_TIMELINE_USAGE_UNAVAILABLE"}) from None

    @router.post("/projects/{nid}/studio/production/canvas-video/preview")
    def canvas_video_preview(nid: str, request: Request, body: CanvasVideoCommand,
            x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.read",
            lambda actor, scope, guard: service.canvas_video_preview(nid, scope, actor, body, guard))

    @router.post("/projects/{nid}/studio/production/canvas-video/queue", status_code=201)
    def canvas_video_queue(nid: str, request: Request, body: CanvasVideoQueue,
            x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.write",
            lambda actor, scope, guard: service.canvas_video_queue(nid, scope, actor, body, guard))

    @router.post("/projects/{nid}/studio/production/canvas-video/jobs/{jid}/execute")
    def canvas_video_execute(nid: str, jid: str, request: Request, body: MediaJobAction,
            x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.write",
            lambda actor, scope, guard: service.canvas_video_execute(nid, scope, actor, jid, body, guard))

    @router.get("/projects/{nid}/studio/production/timelines")
    def timelines(nid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.read", lambda actor, scope, guard: service.timeline_list(nid, scope, actor, guard))

    @router.post("/projects/{nid}/studio/production/timelines", status_code=201)
    def create_timeline(nid: str, request: Request, body: TimelineSave, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return save_timeline_call(request, nid, x_session_token, x_branch_id, None, body)

    def save_timeline_call(request, nid, token, branch, tid, body):
        def operation(actor, scope, guard):
            if service.comic_handoff is None:
                return service.timeline_save(nid, scope, actor, tid, body, guard)
            with service.comic_handoff.timeline_source_authority(request, nid, token, branch,
                    scope, actor, body.timeline, guard):
                return service.timeline_save(nid, scope, actor, tid, body, guard)
        return call(request, nid, token, branch, 'domain.write', operation)

    @router.get("/projects/{nid}/studio/production/timelines/{tid}")
    def timeline(nid: str, tid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.read", lambda actor, scope, guard: service.timeline_get(nid, scope, actor, tid, guard))

    @router.put("/projects/{nid}/studio/production/timelines/{tid}")
    def save_timeline(nid: str, tid: str, request: Request, body: TimelineSave, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return save_timeline_call(request, nid, x_session_token, x_branch_id, tid, body)

    @router.post("/projects/{nid}/studio/production/timelines/{tid}/render")
    def render(nid: str, tid: str, request: Request, body: TimelineRender, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.write", lambda actor, scope, guard: service.timeline_render(nid, scope, actor, tid, body, guard))

    @router.post("/projects/{nid}/studio/production/timelines/{tid}/edit")
    def edit(nid: str, tid: str, request: Request, body: TimelineEdit, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.write", lambda actor, scope, guard: service.timeline_edit(nid, scope, actor, tid, body, guard))

    @router.get("/projects/{nid}/studio/production/timelines/{tid}/history")
    def history(nid: str, tid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.read", lambda actor, scope, guard: service.timeline_history(nid, scope, actor, tid, guard))

    @router.post("/projects/{nid}/studio/production/timelines/{tid}/restore")
    def restore(nid: str, tid: str, request: Request, body: TimelineRestore, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.write", lambda actor, scope, guard: service.timeline_restore(nid, scope, actor, tid, body, guard))

    @router.post("/projects/{nid}/studio/production/timelines/{tid}/export-preview")
    def export_preview(nid: str, tid: str, request: Request, body: TimelineExportPreview, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.read", lambda actor, scope, guard: service.timeline_export_preview(nid, scope, actor, tid, body, guard))

    @router.post("/projects/{nid}/studio/production/timelines/{tid}/export")
    def export(nid: str, tid: str, request: Request, body: TimelineExport, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.write", lambda actor, scope, guard: service.timeline_export(nid, scope, actor, tid, body, guard))

    @router.post("/projects/{nid}/studio/production/timelines/{tid}/transfer-preview")
    def transfer_preview(nid: str, tid: str, request: Request, body: TimelineTransferPreview, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.read", lambda actor, scope, guard: service.timeline_transfer_preview(nid, scope, actor, tid, body, guard))

    @router.post("/projects/{nid}/studio/production/timelines/{tid}/transfer-import")
    def transfer_import(nid: str, tid: str, request: Request, body: TimelineTransferImport, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(request, nid, x_session_token, x_branch_id, "domain.write", lambda actor, scope, guard: service.timeline_transfer_import(nid, scope, actor, tid, body, guard))

    @router.post("/projects/{nid}/studio/production/timelines/{tid}/transfer-attachment")
    def transfer_attachment(nid: str, tid: str, request: Request, body: TimelineTransferDownload, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        data, sha256, format = call(request, nid, x_session_token, x_branch_id, "domain.read", lambda actor, scope, guard: service.timeline_transfer_attachment(nid, scope, actor, tid, body, guard))
        return Response(data, media_type={"OTIO": "application/vnd.opentimelineio+json", "SRT": "application/x-subrip", "VTT": "text/vtt"}[format],
            headers={"Cache-Control": "no-store", "X-Asset-SHA256": sha256, "Content-Disposition": f'attachment; filename="studio-timeline.{format.lower()}"'})

    return router
