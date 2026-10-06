"""Feature- and request-authorized U11 routes."""
from fastapi import APIRouter, Header, HTTPException, Response
from .common import api_call
from .ux import ReadContext
from .reader_preflight import SettingsIn, AnchorIn, AnnotationIn, IgnoreIn, PreflightIn


def create_reader_preflight_router(service, authorize, require_flag):
    router = APIRouter(prefix='/novels/{nid}/experimental/reader-preflight', tags=['reader-preflight'])
    def access(nid, token, branch, write=False):
        require_flag('reader_preflight_v2'); permission = 'domain.write' if write else 'domain.read'
        actor, scope = authorize(nid, token, branch, permission); ctx = ReadContext(nid, scope, actor, token, branch)
        def reauthorize():
            require_flag('reader_preflight_v2')
            if authorize(nid, token, branch, permission) != (actor, scope): raise HTTPException(409, {'code': 'READER_SCOPE_CHANGED'})
        return ctx, reauthorize
    def read_call(name, nid, token, branch, *args):
        ctx, check = access(nid, token, branch); result = api_call(getattr(service, name), ctx, *args); check(); return result
    @router.get('/settings')
    def settings(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'; return read_call('settings', nid, x_session_token, x_branch_id)
    @router.put('/settings')
    def save(nid: str, body: SettingsIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, True); return api_call(service.save_settings, ctx, body, check)
    @router.get('/read')
    def read(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'; return read_call('read', nid, x_session_token, x_branch_id)
    @router.get('/proof')
    def proof(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'; return read_call('proof', nid, x_session_token, x_branch_id)
    @router.post('/open')
    def open_anchor(nid: str, body: AnchorIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return read_call('open_anchor', nid, x_session_token, x_branch_id, body)
    @router.post('/annotations')
    def annotate(nid: str, body: AnnotationIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, True); return api_call(service.annotate, ctx, body, check)
    @router.post('/ignore')
    def ignore(nid: str, body: IgnoreIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, True); return api_call(service.ignore, ctx, body, check)
    @router.post('/check')
    def check(nid: str, body: PreflightIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'; return read_call('preflight', nid, x_session_token, x_branch_id, body)
    return router
