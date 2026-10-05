"""Feature-fenced, actor-owned batch previews and explicit per-stage commands."""
from fastapi import APIRouter, Header, HTTPException, Response
from .common import api_call as domain_call
from .safe_batches import FEATURE, BatchIn, VersionIn, ConfirmIn, ReviewIn
from .ux import ReadContext


def api_call(fn, *args):
    try:
        return domain_call(fn, *args)
    except HTTPException as exc:
        # Scope-store CAS snapshots contain private frozen sources and binary
        # artifacts. Never echo the internal row through a conflict response.
        if exc.status_code == 409 and isinstance(exc.detail, dict) and 'current' in exc.detail:
            raise HTTPException(409, {'code': exc.detail['code'], 'message': 'Refresh the current authorized preview before retrying.'}) from None
        raise


def create_safe_batches_router(service, authorize, require_flag, require_host_session):
    router = APIRouter(prefix='/novels/{nid}/experimental/safe-batches', tags=['safe-batches'])
    def access(nid, token, branch, permission='domain.read'):
        require_flag(FEATURE); require_host_session(token)
        actor, scope = authorize(nid, token, branch, permission)
        def check():
            require_flag(FEATURE); require_host_session(token)
            if authorize(nid, token, branch, permission) != (actor, scope): raise HTTPException(409, {'code': 'BATCH_AUTHORITY_CHANGED'})
        return ReadContext(nid, scope, actor, token, branch), check
    @router.get('/catalog')
    def catalog(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id); response.headers['Cache-Control'] = 'no-store'
        result = api_call(service.catalog, ctx); check(); return result
    @router.get('')
    def batches(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id); response.headers['Cache-Control'] = 'no-store'
        result = api_call(service.list_batches, ctx); check(); return result
    @router.post('/preflight')
    def preflight(nid: str, body: BatchIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, 'domain.write'); return api_call(service.preflight, ctx, body, check)
    @router.post('/{rid}/confirm')
    def confirm(nid: str, rid: str, body: ConfirmIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, 'domain.write'); return api_call(service.confirm, ctx, rid, body, check)
    @router.post('/{rid}/dispatch-next')
    def dispatch(nid: str, rid: str, body: VersionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, 'domain.write'); return api_call(service.dispatch, ctx, rid, body, check)
    @router.post('/{rid}/stop')
    def stop(nid: str, rid: str, body: VersionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, 'domain.write'); return api_call(service.stop, ctx, rid, body, check)
    @router.post('/{rid}/retry-failed')
    def retry(nid: str, rid: str, body: VersionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, 'domain.write'); return api_call(service.retry_failed, ctx, rid, body, check)
    @router.get('/{rid}/items/{index}/file')
    def download(nid: str, rid: str, index: int, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id)
        raw, fmt, mime = api_call(service.download, ctx, rid, index, check)
        return Response(raw, media_type=mime, headers={'Cache-Control': 'no-store', 'Content-Disposition': f'attachment; filename="batch-export.{fmt}"', 'X-Content-Type-Options': 'nosniff'})
    @router.get('/{rid}/proposals/{pid}/preview')
    def preview(nid: str, rid: str, pid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id)
        raw, mime = api_call(service.preview_media, ctx, rid, pid, check)
        return Response(raw, media_type=mime, headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
    @router.post('/{rid}/approve-media')
    def approve(nid: str, rid: str, body: ReviewIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, 'domain.review'); return api_call(service.approve_media, ctx, rid, body, check)
    return router
