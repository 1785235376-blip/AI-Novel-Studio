"""Feature-fenced, actor-owned batch previews and explicit per-stage commands."""
from fastapi import APIRouter, Header, HTTPException, Response
from .common import api_call as domain_call, check_version
from .safe_batches import FEATURE, BatchIn, VersionIn, ConfirmIn, ReviewIn, VoiceReviewIn, ImageReviewIn
from .safe_batch_studio_image import StudioImageRequestRoute
from .ux import ReadContext


def api_call(fn, *args, **kwargs):
    try:
        return domain_call(fn, *args, **kwargs)
    except HTTPException as exc:
        # Scope-store CAS snapshots contain private frozen sources and binary
        # artifacts. Never echo the internal row through a conflict response.
        if exc.status_code == 409 and isinstance(exc.detail, dict) and 'current' in exc.detail:
            raise HTTPException(409, {'code': exc.detail['code'], 'message': 'Refresh the current authorized preview before retrying.'}) from None
        raise


def create_safe_batches_router(service, authorize, require_flag, require_host_session):
    router = APIRouter(prefix='/novels/{nid}/experimental/safe-batches', tags=['safe-batches'], route_class=StudioImageRequestRoute)
    def access(nid, token, branch, permission='domain.read'):
        require_flag(FEATURE); require_host_session(token)
        actor, scope = authorize(nid, token, branch, permission)
        def check():
            require_flag(FEATURE); require_host_session(token)
            if authorize(nid, token, branch, permission) != (actor, scope): raise HTTPException(409, {'code': 'BATCH_AUTHORITY_CHANGED'})
        return ReadContext(nid, scope, actor, token, branch), check

    def batch_call(ctx, check, permission, fn, *args, rid=None, studio=False, commit=False, expected_version=None):
        if rid is not None:
            row = api_call(service.get, ctx.novel_id, ctx.scope, service.BATCHES, rid)
            if row['created_by'] != ctx.actor: raise HTTPException(404, {'code': 'EXPERIMENTAL_NOT_FOUND'})
            studio = any(s['input']['kind'] == 'STUDIO_IMAGE' for s in row['snapshot']['steps'])
            if not studio and expected_version is not None:
                # The selected host authority must describe the same batch
                # version that the downstream writer will commit. Original
                # source visibility must precede any stale-version response.
                visible = api_call(service._owned, ctx, rid)
                studio = any(s['input']['kind'] == 'STUDIO_IMAGE' for s in visible['snapshot']['steps'])
                if not studio:
                    api_call(check_version, visible, expected_version)
        if not studio:
            return api_call(fn, ctx, *args, check)
        if service.studio_image is None:
            raise HTTPException(403, {'code': 'BATCH_STUDIO_HOST_INVOKER_REQUIRED'})
        def operation(host_guard):
            def guard(): check(); host_guard()
            guard()
            return api_call(fn, ctx, *args, guard)
        if commit:
            return api_call(service.studio_image.call, ctx, permission, operation, commit=True)
        return api_call(service.studio_image.call, ctx, permission, operation)

    @router.get('/studio-image/catalog')
    def studio_catalog(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id); response.headers['Cache-Control'] = 'no-store'
        if service.studio_image is None: raise HTTPException(403, {'code': 'BATCH_STUDIO_HOST_INVOKER_REQUIRED'})
        result = api_call(service.studio_image.catalog, ctx); check(); return result
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
        ctx, check = access(nid, x_session_token, x_branch_id, 'domain.write')
        studio = any(i.kind == 'STUDIO_IMAGE' for i in body.items)
        if studio and any(i.kind == 'VOICE_REDO' for i in body.items):
            if service.studio_image is None:
                raise HTTPException(403, {'code': 'BATCH_STUDIO_HOST_INVOKER_REQUIRED'})
            return api_call(service.studio_image.reject_closed_audio_preflight, ctx, check)
        return batch_call(ctx, check, 'domain.write', service.preflight, body, studio=studio)
    @router.post('/{rid}/confirm')
    def confirm(nid: str, rid: str, body: ConfirmIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, 'domain.write'); return batch_call(ctx, check, 'domain.write', service.confirm, rid, body, rid=rid)
    @router.post('/{rid}/dispatch-next')
    def dispatch(nid: str, rid: str, body: VersionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, 'domain.write'); return batch_call(ctx, check, 'domain.write', service.dispatch, rid, body, rid=rid)
    @router.post('/{rid}/stop')
    def stop(nid: str, rid: str, body: VersionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, 'domain.write')
        return batch_call(ctx, check, 'domain.write', service.stop, rid, body, rid=rid,
                          commit=True, expected_version=body.expected_version)
    @router.post('/{rid}/retry-failed')
    def retry(nid: str, rid: str, body: VersionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, 'domain.write'); return batch_call(ctx, check, 'domain.write', service.retry_failed, rid, body, rid=rid)
    @router.post('/{rid}/reconcile')
    def reconcile(nid: str, rid: str, body: VersionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, 'domain.write'); return batch_call(ctx, check, 'domain.write', service.reconcile, rid, body, rid=rid)

    @router.get('/{rid}/items/{index}/image')
    def image(nid: str, rid: str, index: int, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id)
        meta, raw = batch_call(ctx, check, 'domain.read', service.preview_image, rid, index, rid=rid)
        return Response(raw, media_type=meta['media_type'], headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})

    @router.post('/{rid}/approve-image')
    def approve_image(nid: str, rid: str, body: ImageReviewIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, 'domain.review')
        return batch_call(ctx, check, 'domain.review', service.approve_image, rid, body, rid=rid)
    @router.get('/{rid}/items/{index}/file')
    def download(nid: str, rid: str, index: int, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id)
        raw, fmt, mime = api_call(service.download, ctx, rid, index, check)
        return Response(raw, media_type=mime, headers={'Cache-Control': 'no-store', 'Content-Disposition': f'attachment; filename="batch-export.{fmt}"', 'X-Content-Type-Options': 'nosniff'})
    @router.get('/{rid}/items/{index}/audio')
    def audio(nid: str, rid: str, index: int, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id)
        raw, mime = api_call(service.preview_voice, ctx, rid, index, check)
        return Response(raw, media_type=mime, headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
    @router.post('/{rid}/approve-voice')
    def approve_voice(nid: str, rid: str, body: VoiceReviewIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, 'domain.review'); return api_call(service.approve_voice, ctx, rid, body, check)
    @router.get('/{rid}/proposals/{pid}/preview')
    def preview(nid: str, rid: str, pid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id)
        raw, mime = api_call(service.preview_media, ctx, rid, pid, check)
        return Response(raw, media_type=mime, headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
    @router.post('/{rid}/approve-media')
    def approve(nid: str, rid: str, body: ReviewIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, 'domain.review'); return api_call(service.approve_media, ctx, rid, body, check)
    return router
