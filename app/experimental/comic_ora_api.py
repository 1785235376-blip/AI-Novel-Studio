"""Original-owner ORA transport: bounded transient uploads and explicit transitions."""
import base64
import binascii
import hashlib
from contextlib import nullcontext

from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import JSONResponse
from pydantic import Field, ValidationError
from starlette.concurrency import run_in_threadpool
from .comic_layouts_api import ComicPrivateRoute
from .media import StrictModel
from .comic_ora_import import preview_ora
from .production_lineage_api import api_call
from ..creative.storage_admission import StudioStorageCapacityError

MAX_ARCHIVE = 16 * 1024 * 1024
MAX_BODY = 4 * ((MAX_ARCHIVE + 2) // 3) + 16 * 1024
HEADERS = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}

class ArchiveIn(StrictModel):
    archive_base64: str = Field(max_length=4 * ((MAX_ARCHIVE + 2) // 3))
    archive_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')

class PrepareIn(ArchiveIn):
    request_key: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')

class StageIn(ArchiveIn):
    max_steps: int = Field(default=1, strict=True, ge=1, le=8)

class ReviewIn(StageIn):
    manifest_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    license_note: str = Field(min_length=1, max_length=1000)
    acknowledge_raster_text: bool = Field(strict=True)

class AttachIn(StrictModel):
    page_id: str = Field(min_length=1, max_length=100)
    expected_page_version: int = Field(strict=True, ge=1)
    review_digest: str = Field(pattern=r'^[a-f0-9]{64}$')

class OraRoute(ComicPrivateRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def private(request):
            try:
                return await handler(request)
            except Exception:
                # No archive content, paths, session material or internal failures.
                return JSONResponse({'detail': {'code': 'COMIC_ORA_REQUEST_FAILED'}}, status_code=500, headers=HEADERS)
        return private


def create_comic_ora_router(service, authorize, require_flag, *, authority_lease):
    router = APIRouter(prefix='/novels/{nid}/experimental/comic-layouts/ora-imports',
                       tags=['Experimental comic layouts'], route_class=OraRoute)

    def access(nid, request, permission):
        for flag in ('comic_layouts_v2', 'asset_lineage_v2', 'ai_director_v2', 'narrative_production_v2'):
            require_flag(flag)
        actor, scope = authorize(nid, request.headers.get('x-session-token'), request.headers.get('x-branch-id'), permission)
        service.store.key(nid, scope)
        with service.owner.existing_owner_only():
            incarnation = service.owner.incarnation(nid)
        return actor, scope, incarnation

    def invoke(nid, request, permission, captured, callback, commit=False):
        def operation():
            with service.owner.existing_owner_only():
                actor, scope, _ = captured
                def guard():
                    if access(nid, request, permission) != captured:
                        raise HTTPException(403, {'code': 'COMIC_ORA_AUTHORITY_CHANGED'})
                lease = authority_lease(nid, request.headers.get('x-session-token'), actor, scope) if commit else nullcontext()
                with lease:
                    guard()
                    try:
                        result = callback(actor, scope, guard)
                    except StudioStorageCapacityError as exc:
                        guard()
                        raise HTTPException(507, {'code': str(exc)}) from None
                    except Exception:
                        guard()
                        raise
                    guard()
                    return result
        return api_call(operation)

    async def upload(nid, request, permission, model, callback, *, archive=True, commit=False):
        # Authenticate/capture existing owner before reading. No synchronous lease
        # spans await: authorization is rechecked under the commit lease afterward.
        captured = api_call(access, nid, request, permission)
        payload = bytearray(); total = 0
        limit = MAX_BODY if archive else 16 * 1024
        async for part in request.stream():
            total += len(part)
            if total > limit: raise HTTPException(413, {'code': 'COMIC_ORA_REQUEST_LIMIT'})
            payload.extend(part)
        def process():
            def validated(actor, scope, guard):
                try:
                    body = model.model_validate_json(payload)
                except ValidationError:
                    raise HTTPException(422, {'code': 'COMIC_ORA_INPUT_INVALID'}) from None
                raw = None
                if archive:
                    try: raw = base64.b64decode(body.archive_base64, validate=True)
                    except (binascii.Error, ValueError):
                        raise HTTPException(422, {'code': 'COMIC_ORA_BASE64_INVALID'}) from None
                    if not 22 <= len(raw) <= MAX_ARCHIVE:
                        raise HTTPException(413, {'code': 'COMIC_ORA_ARCHIVE_SIZE_LIMIT'})
                    if hashlib.sha256(raw).hexdigest() != body.archive_sha256:
                        raise HTTPException(422, {'code': 'COMIC_ORA_PREVIEW_CHANGED'})
                guard()
                return callback(actor, scope, guard, body, raw)
            return invoke(nid, request, permission, captured, validated, commit)
        return await run_in_threadpool(process)

    @router.post('/preview')
    async def preview(nid: str, request: Request):
        def result(a, s, g, b, raw):
            parsed = preview_ora(raw, thumbnail_only=True)
            return {'report': parsed.report, 'thumbnail_base64': base64.b64encode(parsed.preview_png).decode('ascii')}
        return await upload(nid, request, 'domain.read', ArchiveIn, result)

    @router.get('')
    def receipts(nid: str, request: Request):
        captured = api_call(access, nid, request, 'domain.read')
        return invoke(nid, request, 'domain.read', captured, lambda a,s,g: {'receipts': service.receipts(nid,s,a,guard=g)})

    @router.post('')
    async def prepare(nid: str, request: Request):
        return await upload(nid, request, 'domain.write', PrepareIn,
            lambda a,s,g,b,raw: service.prepare(nid,s,a,raw,archive_sha256=b.archive_sha256,request_key=b.request_key,guard=g), commit=True)

    @router.get('/{rid}')
    def status(nid: str, rid: str, request: Request):
        captured = api_call(access, nid, request, 'domain.read')
        return invoke(nid, request, 'domain.read', captured, lambda a,s,g: service.status(nid,s,a,rid,guard=g))

    @router.post('/{rid}/stage')
    async def stage(nid: str, rid: str, request: Request):
        return await upload(nid, request, 'domain.write', StageIn,
            lambda a,s,g,b,raw: service.stage(nid,s,a,rid,raw,max_steps=b.max_steps,guard=g), commit=True)

    @router.post('/{rid}/review-manifest')
    async def manifest(nid: str, rid: str, request: Request):
        return await upload(nid, request, 'domain.read', ArchiveIn,
            lambda a,s,g,b,raw: service.review_manifest(nid,s,a,rid,raw,guard=g))

    @router.get('/{rid}/candidates/{index}')
    def candidate(nid: str, rid: str, index: int, request: Request):
        captured = api_call(access, nid, request, 'domain.read')
        return invoke(nid, request, 'domain.read', captured,
            lambda a,s,g: Response(service.candidate(nid,s,a,rid,index,guard=g),media_type='image/png'))

    @router.post('/{rid}/review')
    async def review(nid: str, rid: str, request: Request):
        return await upload(nid, request, 'domain.review', ReviewIn,
            lambda a,s,g,b,raw: service.review(nid,s,a,rid,raw,manifest_digest=b.manifest_digest,
                license_note=b.license_note,acknowledge_raster_text=b.acknowledge_raster_text,max_steps=b.max_steps,guard=g),commit=True)

    @router.post('/{rid}/attach')
    async def attach(nid: str, rid: str, request: Request):
        return await upload(nid, request, 'domain.write', AttachIn,
            lambda a,s,g,b,raw: service.attach(nid,s,a,rid,b.page_id,
                expected_page_version=b.expected_page_version,review_digest=b.review_digest,guard=g),archive=False,commit=True)
    return router
