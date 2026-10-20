"""Dedicated router; mounting requires the original injected Studio Host call."""
from fastapi import APIRouter, Header, Request, Response, HTTPException
from fastapi.exceptions import RequestValidationError
from .production_lineage_api import PrivateProductionRoute
from .audio_manifest import AudioManifestService, AudioManifestInput
from .common import StaleSourceError
from .store import canonical


class AudioManifestRoute(PrivateProductionRoute):
    MAX_BODY = 8192

    def get_route_handler(self):
        handler = super().get_route_handler()
        async def checked(request):
            try:
                body = bytearray()
                async for chunk in request.stream():
                    if len(body) + len(chunk) > self.MAX_BODY:
                        raise HTTPException(413, {'code': 'AUDIO_MANIFEST_REQUEST_LIMIT'})
                    body.extend(chunk)
                if request.method == 'GET' and body:
                    raise HTTPException(422, {'code': 'AUDIO_MANIFEST_REQUEST_INVALID'})
                request._body = bytes(body)
                return await handler(request)
            except RequestValidationError:
                raise HTTPException(422, {'code': 'AUDIO_MANIFEST_REQUEST_INVALID'}, headers={'Cache-Control': 'no-store'}) from None
            except HTTPException as exc:
                exc.headers = {**(exc.headers or {}), 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}
                raise
        return checked


def create_audio_manifest_router(production_service, studio_host_call):
    """call(request,nid,token,branch,permission,callback,*,model=False).

    The shared owner must inject its original Host-bound Production invoker.
    There is deliberately no novel-authorize fallback.
    """
    service = AudioManifestService(production_service)
    router = APIRouter(prefix='/novels/{nid}/experimental/production/audio-manifests',
                       tags=['Studio Audio manifests'], route_class=AudioManifestRoute)

    def perform(request, nid, token, branch, callback, *, write=False):
        if not callable(studio_host_call):
            raise HTTPException(403, {'code': 'AUDIO_MANIFEST_HOST_REQUIRED'})
        def read(actor, scope, read_guard):
            def guarded(work_actor, work_scope, write_guard=None):
                if (work_actor, work_scope) != (actor, scope):
                    raise HTTPException(403, {'code': 'AUDIO_MANIFEST_AUTHORITY_CHANGED'})
                def current():
                    read_guard()
                    if write_guard is not None: write_guard()
                try:
                    result = callback(actor, scope, current)
                except FileNotFoundError:
                    current(); raise HTTPException(404, {'code': 'AUDIO_MANIFEST_UNAVAILABLE'}) from None
                except StaleSourceError:
                    current(); raise HTTPException(409, {'code': 'AUDIO_MANIFEST_CHANGED'}) from None
                except ValueError:
                    current(); raise HTTPException(409, {'code': 'AUDIO_MANIFEST_INVALID_OR_CHANGED'}) from None
                current()
                return result
            if write:
                return studio_host_call(request, nid, token, branch, 'domain.write', guarded)
            return guarded(actor, scope)
        with production_service.store.existing_owner_only():
            return studio_host_call(request, nid, token, branch, 'domain.read', read)

    @router.get('/results')
    def results(nid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return perform(request, nid, x_session_token, x_branch_id, lambda actor, scope, guard: service.results(nid, scope, actor, guard))

    @router.get('/results/{jid}')
    def preview(nid: str, jid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return perform(request, nid, x_session_token, x_branch_id, lambda actor, scope, guard: service.preview(nid, scope, actor, jid, guard))

    @router.get('')
    def manifests(nid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return perform(request, nid, x_session_token, x_branch_id, lambda actor, scope, guard: service.list(nid, scope, actor, guard))

    @router.post('', status_code=201)
    def record(nid: str, request: Request, body: AudioManifestInput, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return perform(request, nid, x_session_token, x_branch_id, lambda actor, scope, guard: service.record(nid, scope, actor, body, guard), write=True)

    @router.get('/{mid}')
    def manifest(nid: str, mid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return perform(request, nid, x_session_token, x_branch_id, lambda actor, scope, guard: service.get(nid, scope, actor, mid, guard))

    @router.get('/{mid}/export')
    def export(nid: str, mid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        value = perform(request, nid, x_session_token, x_branch_id, lambda actor, scope, guard: service.get(nid, scope, actor, mid, guard))
        return Response(canonical(value), media_type='application/json', headers={
            'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
            'Content-Disposition': 'attachment; filename="studio-audio-manifest.json"'})
    return router
