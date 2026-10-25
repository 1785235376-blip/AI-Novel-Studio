"""Private, bounded history routes mounted by the original workspace router."""
from __future__ import annotations
import json
import time
from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from ..experimental.production_lineage_api import PrivateProductionRoute
from ..services.asset_query_budget import asset_query_budget
from ..services.asset_query_index import AssetQueryBudgetExceeded, AssetQueryUnavailable
from .audio_asset_history import AudioAssetHistoryService
from .audio_asset_history_restore import (AudioAssetHistoryRestore, AudioHistoryRestorePreview,
    AudioHistoryRestoreConfirm, AudioHistoryRestoreResolve)

class AudioHistoryRoute(PrivateProductionRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def checked(request: Request):
            headers = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}
            try:
                body = bytearray()
                async for chunk in request.stream():
                    if len(body) + len(chunk) > 16384:
                        raise HTTPException(413, {'code': 'AUDIO_HISTORY_REQUEST_LIMIT'}, headers=headers)
                    body.extend(chunk)
                request._body = bytes(body)
                if body and request.method == 'POST':
                    def pairs(items):
                        result = {}
                        for key, value in items:
                            if key in result:
                                raise ValueError('duplicate key')
                            result[key] = value
                        return result
                    def constant(_):
                        raise ValueError('nonfinite number')
                    request._json = json.loads(body, object_pairs_hook=pairs, parse_constant=constant)
                return await handler(request)
            except (AssetQueryBudgetExceeded, AssetQueryUnavailable):
                raise HTTPException(422, {'code': 'AUDIO_HISTORY_READ_BUDGET'}, headers=headers) from None
            except (RequestValidationError, ValueError, UnicodeError, RecursionError):
                raise HTTPException(422, {'code': 'AUDIO_HISTORY_REQUEST_INVALID'}, headers=headers) from None
            except HTTPException as exc:
                code = 'AUDIO_HISTORY_REQUEST_REJECTED'
                if exc.status_code == 404:
                    code = 'AUDIO_HISTORY_UNAVAILABLE'
                elif exc.status_code == 409:
                    code = 'AUDIO_HISTORY_STALE'
                    if isinstance(exc.detail, dict) and exc.detail.get('code') == 'AUDIO_HISTORY_RESTORE_ADMISSION_UNAVAILABLE':
                        code = 'AUDIO_HISTORY_RESTORE_ADMISSION_UNAVAILABLE'
                raise HTTPException(exc.status_code, {'code': code}, headers=headers) from None
        return checked

def create_audio_asset_history_router(service, invoke, commit_invoke, *, authority_snapshot):
    router = APIRouter(route_class=AudioHistoryRoute, tags=['Audio asset history'])
    history, restore = AudioAssetHistoryService(service), AudioAssetHistoryRestore(service)

    def call(nid, token, branch, permission, callback):
        with service.store.existing_owner_only(), asset_query_budget() as budget:
            budget.MAX_METADATA_READS = 500
            budget.MAX_METADATA_BYTES = 8 * 1024 * 1024
            deadline = time.monotonic() + 5.0
            budget.deadline = min(budget.deadline, deadline)
            def operation(actor, scope, original_guard):
                initial = authority_snapshot(nid, token, actor, scope)
                def guard():
                    if time.monotonic() > deadline:
                        raise HTTPException(422, {'code': 'AUDIO_HISTORY_READ_BUDGET'})
                    original_guard()
                    if authority_snapshot(nid, token, actor, scope) != initial:
                        raise HTTPException(403, {'code': 'AUDIO_HISTORY_AUTHORITY_CHANGED'})
                    if time.monotonic() > deadline:
                        raise HTTPException(422, {'code': 'AUDIO_HISTORY_READ_BUDGET'})
                guard()
                try:
                    result = callback(actor, scope, guard, initial)
                except ValueError as exc:
                    if str(exc) == 'AUDIO_HISTORY_RESTORE_ADMISSION_UNAVAILABLE':
                        raise HTTPException(409, {'code': 'AUDIO_HISTORY_RESTORE_ADMISSION_UNAVAILABLE'}) from None
                    raise
                guard()
                return result
            return commit_invoke(nid, token, branch, permission, operation)

    @router.get('/projects/{nid}/studio/assets/{aid}/history')
    def versions(nid: str, aid: str, limit: int = Query(20, ge=1, le=50),
                 cursor: str | None = Query(None, max_length=8192),
                 x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(nid, x_session_token, x_branch_id, 'domain.read',
            lambda actor, scope, guard, authority: history.list(nid, scope, actor, aid, guard,
                authority=authority, limit=limit, cursor=cursor))

    @router.get('/projects/{nid}/studio/assets/{aid}/history/{version_id}')
    def version(nid: str, aid: str, version_id: str,
                x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(nid, x_session_token, x_branch_id, 'domain.read',
            lambda actor, scope, guard, authority: history.detail(nid, scope, actor, aid, version_id, guard))

    @router.get('/projects/{nid}/studio/assets/{aid}/history/{version_id}/download')
    def download(nid: str, aid: str, version_id: str,
                 x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        def response(actor, scope, guard, authority):
            view, data = history.content(nid, scope, actor, aid, version_id, guard)
            result = Response(data, media_type=view['metadata']['media_type'], headers={
                'Content-Disposition': 'attachment; filename="audio-history.bin"',
                'X-Asset-SHA256': view['sha256'], 'X-Asset-Version': str(view['asset_version']),
                'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
            guard()
            return result
        return call(nid, x_session_token, x_branch_id, 'domain.read', response)

    @router.post('/projects/{nid}/studio/assets/{aid}/history/{version_id}/restore-preview')
    def restore_preview(nid: str, aid: str, version_id: str, body: AudioHistoryRestorePreview,
                        x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(nid, x_session_token, x_branch_id, 'domain.read',
            lambda actor, scope, guard, authority: restore.inspect(nid, scope, actor, aid, version_id, guard,
                operation_id=body.operation_id, authority=authority,
                authorize_source=history.authorize_source(nid, scope, actor, guard)))

    @router.post('/projects/{nid}/studio/assets/{aid}/history/{version_id}/restore-confirm')
    def restore_confirm(nid: str, aid: str, version_id: str, body: AudioHistoryRestoreConfirm,
                        x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(nid, x_session_token, x_branch_id, 'domain.write',
            lambda actor, scope, guard, authority: restore.confirm(nid, scope, actor, aid, version_id, body, guard,
                authority=authority, authorize_source=history.authorize_source(nid, scope, actor, guard)))

    @router.post('/projects/{nid}/studio/assets/{aid}/history/restore-resolve')
    def restore_resolve(nid: str, aid: str, body: AudioHistoryRestoreResolve,
                        x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call(nid, x_session_token, x_branch_id, 'domain.read',
            lambda actor, scope, guard, authority: restore.resolve(nid, scope, actor, aid, body, guard,
                authority=authority, authorize_source=history.authorize_source(nid, scope, actor, guard)))
    return router
