"""U14 request-bound authorization; file inputs are streamed with a hard cap."""
from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import ValidationError
from .common import api_call as domain_call
from ..repositories.chapter_repository import VersionConflict
from .portable_projects import FEATURE, MAX_ARCHIVE, SelectionIn, UploadIn, ConfirmIn, RelinkIn, RelinkConfirmIn, CleanupIn
from .ux import ReadContext


def api_call(fn, *args):
    try:
        return domain_call(fn, *args)
    except VersionConflict:
        raise HTTPException(409, {'code': 'PORTABLE_CHAPTER_VERSION_CONFLICT', 'message': 'The original chapter changed; review the preserved recovery record.'}) from None
    except HTTPException as exc:
        # Scope-store CAS snapshots contain private frozen sources and binary
        # artifacts. Never echo the internal row through a conflict response.
        if exc.status_code == 409 and isinstance(exc.detail, dict) and 'current' in exc.detail:
            raise HTTPException(409, {'code': exc.detail['code'], 'message': 'Refresh the current authorized preview before retrying.'}) from None
        raise


def create_portable_projects_router(service, authorize, require_flag, require_host_session):
    router = APIRouter(prefix='/novels/{nid}/experimental/portable-projects', tags=['portable-projects'])

    def access(nid, token, branch, write=False):
        permission = 'domain.write' if write else 'domain.read'
        require_flag(FEATURE); require_host_session(token)
        actor, scope = authorize(nid, token, branch, permission)
        def check():
            require_flag(FEATURE); require_host_session(token)
            if authorize(nid, token, branch, permission) != (actor, scope): raise HTTPException(409, {'code': 'PORTABLE_AUTHORITY_CHANGED'})
        return ReadContext(nid, scope, actor, token, branch), check

    async def upload(request, model):
        data = bytearray()
        async for part in request.stream():
            data.extend(part)
            if len(data) > 4 * ((MAX_ARCHIVE + 2) // 3) + 8192: raise HTTPException(413, {'code': 'PORTABLE_REQUEST_LIMIT'})
        try: return model.model_validate_json(data)
        except (ValueError, ValidationError): raise HTTPException(422, {'code': 'PORTABLE_INPUT_INVALID'}) from None

    @router.get('/catalog')
    def catalog(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id); response.headers['Cache-Control'] = 'no-store'
        result = api_call(service.catalog, ctx); check(); return result

    @router.get('/records')
    def records(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id); response.headers['Cache-Control'] = 'no-store'
        result = api_call(service.records, ctx); check(); return result

    @router.post('/export')
    def export(nid: str, body: SelectionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, True); return api_call(service.export, ctx, body, check)

    @router.get('/records/{rid}/file')
    def file(nid: str, rid: str, expected_version: int, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id)
        raw = api_call(service.download, ctx, rid, expected_version, check)
        return Response(raw, media_type='application/zip', headers={'Cache-Control': 'no-store', 'Content-Disposition': 'attachment; filename="portable-project.zip"', 'X-Content-Type-Options': 'nosniff'})

    @router.post('/import-preflight')
    async def import_preflight(nid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, True); body = await upload(request, UploadIn)
        from starlette.concurrency import run_in_threadpool
        return await run_in_threadpool(api_call, service.preflight_import, ctx, body, check)

    @router.post('/records/{rid}/restore')
    def restore(nid: str, rid: str, body: ConfirmIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, True); return api_call(service.restore, ctx, rid, body, check)

    @router.post('/relink-preflight')
    async def relink_preflight(nid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, True); body = await upload(request, RelinkIn)
        from starlette.concurrency import run_in_threadpool
        return await run_in_threadpool(api_call, service.preflight_relink, ctx, body, check)

    @router.post('/records/{rid}/relink')
    def relink(nid: str, rid: str, body: RelinkConfirmIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, True); return api_call(service.relink, ctx, rid, body, check)

    @router.get('/storage')
    def storage(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id); response.headers['Cache-Control'] = 'no-store'
        result = api_call(service.storage, ctx); check(); return result

    @router.post('/cleanup')
    def cleanup(nid: str, body: CleanupIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, True); return api_call(service.cleanup, ctx, body, check)
    return router
