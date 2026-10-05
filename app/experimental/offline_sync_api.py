"""B10 bounded HTTP parsing and repeated original identity/feature fences.

These routes run on the existing authorized host. No external transport endpoint
or outbound connection is enabled by opening a channel or exporting a message.
"""
import re

from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from ..repositories.chapter_repository import VersionConflict
from ..revision_constraints import RevisionConstraintError
from .common import api_call as domain_call
from .offline_sync import (FEATURE, MAX_BYTES, ChannelIn, VersionIn, QueueIn, ReceiveIn,
                           ReviewIn, ApplyIn, ExportIn, DeliveryIn, RecoverIn)
from .portable_projects import _json
from .ux import ReadContext


def call(fn, *args, **kwargs):
    try: return domain_call(fn, *args, **kwargs)
    except VersionConflict: raise HTTPException(409, {'code': 'SYNC_CHAPTER_VERSION_CONFLICT'}) from None
    except RevisionConstraintError: raise HTTPException(409, {'code': 'SYNC_REVISION_LOCKED'}) from None
    except HTTPException as exc:
        if exc.status_code == 422 and isinstance(exc.detail, dict):
            code = str(exc.detail.get('message', ''))
            if re.fullmatch(r'SYNC_[A-Z0-9_]+', code):
                raise HTTPException(422, {'code': code}) from None
        if exc.status_code == 409:
            # Do not leak another scope's content through repository conflict data.
            raise HTTPException(409, {'code': 'SYNC_STALE_OR_CONFLICT', 'message': 'Refresh and review current candidates; uncertain writes must be reconciled.'}) from None
        raise


def create_offline_sync_router(service, authorize, require_flag, require_host_session, *, save_document=None, archive_chapter=None, create_chapter=None):
    router = APIRouter(prefix='/novels/{nid}/experimental/offline-sync', tags=['offline-sync'])

    def access(nid, token, branch, write=False):
        permission = 'domain.review' if write else 'domain.read'
        require_flag(FEATURE); require_host_session(token)
        actor, scope = authorize(nid, token, branch, permission)
        def again():
            require_flag(FEATURE); require_host_session(token)
            if authorize(nid, token, branch, permission) != (actor, scope):
                raise HTTPException(409, {'code': 'SYNC_AUTHORITY_CHANGED'})
        return ReadContext(nid, scope, actor, token, branch), again

    async def body(request, model):
        data = bytearray()
        async for part in request.stream():
            data.extend(part)
            if len(data) > MAX_BYTES + 8192: raise HTTPException(413, {'code': 'SYNC_INPUT_LIMIT'})
        try: return model.model_validate(_json(bytes(data)))
        except (ValueError, ValidationError, RecursionError): raise HTTPException(422, {'code': 'SYNC_INPUT_INVALID'}) from None

    @router.get('/catalog')
    def catalog(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again = access(nid, x_session_token, x_branch_id); response.headers['Cache-Control'] = 'no-store'
        result = call(service.catalog, ctx); again(); return result

    @router.get('/records')
    def records(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again = access(nid, x_session_token, x_branch_id); response.headers['Cache-Control'] = 'no-store'
        result = call(service.records, ctx); again(); return result

    @router.post('/channels', status_code=201)
    async def open_channel(nid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again = access(nid, x_session_token, x_branch_id, True); value = await body(request, ChannelIn); response.headers['Cache-Control'] = 'no-store'
        return await run_in_threadpool(call, service.open_channel, ctx, value, again)

    @router.post('/channels/{rid}/revoke')
    async def revoke(nid: str, rid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again = access(nid, x_session_token, x_branch_id, True); value = await body(request, VersionIn); response.headers['Cache-Control'] = 'no-store'
        return await run_in_threadpool(call, service.revoke, ctx, rid, value, again)

    @router.post('/channels/{rid}/queue')
    async def queue(nid: str, rid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again = access(nid, x_session_token, x_branch_id, True); value = await body(request, QueueIn); response.headers['Cache-Control'] = 'no-store'
        return await run_in_threadpool(call, service.queue, ctx, rid, value, again)

    @router.post('/channels/{rid}/receive')
    async def receive(nid: str, rid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again = access(nid, x_session_token, x_branch_id, True); value = await body(request, ReceiveIn); response.headers['Cache-Control'] = 'no-store'
        return await run_in_threadpool(call, service.receive, ctx, rid, value, again)

    @router.get('/outbox/{mid}')
    def inspect(nid: str, mid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again = access(nid, x_session_token, x_branch_id); response.headers['Cache-Control'] = 'no-store'
        result = call(service.inspect_outbox, ctx, mid); again(); return result

    @router.post('/outbox/{mid}/export')
    async def export(nid: str, mid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again = access(nid, x_session_token, x_branch_id, True); value = await body(request, ExportIn); response.headers['Cache-Control'] = 'no-store'
        return await run_in_threadpool(call, service.export, ctx, mid, value, again)

    @router.post('/outbox/{mid}/delivery')
    async def delivery(nid: str, mid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again = access(nid, x_session_token, x_branch_id, True); value = await body(request, DeliveryIn); response.headers['Cache-Control'] = 'no-store'
        return await run_in_threadpool(call, service.delivery, ctx, mid, value, again)

    @router.post('/inbox/{mid}/review')
    async def review(nid: str, mid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again = access(nid, x_session_token, x_branch_id); value = await body(request, ReviewIn); response.headers['Cache-Control'] = 'no-store'
        return await run_in_threadpool(call, service.review, ctx, mid, value, again)

    @router.post('/inbox/{mid}/apply')
    async def apply(nid: str, mid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again = access(nid, x_session_token, x_branch_id, True); value = await body(request, ApplyIn); response.headers['Cache-Control'] = 'no-store'
        writers = {'save_document': (lambda cid, doc, version, source: save_document(cid, doc, version, source, x_session_token, x_branch_id)) if save_document else None,
                   'archive_chapter': (lambda cid, version: archive_chapter(cid, version, x_session_token, x_branch_id)) if archive_chapter else None,
                   'create_chapter': (lambda nid, title, doc: create_chapter(nid, title, doc, x_session_token, x_branch_id)) if create_chapter else None}
        return await run_in_threadpool(call, service.apply, ctx, mid, value, again, **writers)

    @router.post('/inbox/{mid}/recovery')
    async def recovery(nid: str, mid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, again = access(nid, x_session_token, x_branch_id, True); value = await body(request, RecoverIn); response.headers['Cache-Control'] = 'no-store'
        return await run_in_threadpool(call, service.recover, ctx, mid, value, again)

    return router
