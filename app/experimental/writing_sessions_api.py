"""U15 routes reusing current scope authority with CAS metadata writes."""
from fastapi import APIRouter, Header, HTTPException, Response
from .common import api_call
from .ux import ReadContext
from .writing_sessions import StartIn, SessionIn, NoticePreferencesIn, AcknowledgeIn


def create_writing_sessions_router(service, authorize, require_flag):
    router = APIRouter(prefix='/novels/{nid}/experimental/writing-sessions', tags=['writing-sessions'])
    def access(nid, token, branch, write=False):
        require_flag('writing_sessions_v2'); permission = 'domain.write' if write else 'domain.read'
        actor, scope = authorize(nid, token, branch, permission); ctx = ReadContext(nid, scope, actor, token, branch)
        def reauthorize():
            require_flag('writing_sessions_v2')
            if authorize(nid, token, branch, permission) != (actor, scope): raise HTTPException(409, {'code': 'SESSION_SCOPE_CHANGED'})
        return ctx, reauthorize
    def read_call(name, nid, token, branch, *args):
        ctx, check = access(nid, token, branch); result = api_call(getattr(service, name), ctx, *args); check(); return result
    @router.get('')
    def overview(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'; return read_call('overview', nid, x_session_token, x_branch_id)
    @router.post('', status_code=201)
    def start(nid: str, body: StartIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, True); return api_call(service.start, ctx, body, check)
    @router.put('/{sid}')
    def update(nid: str, sid: str, body: SessionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, True); return api_call(service.update, ctx, sid, body, check)
    @router.get('/preferences/notices')
    def preferences(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'; return read_call('preferences', nid, x_session_token, x_branch_id)
    @router.put('/preferences/notices')
    def save_preferences(nid: str, body: NoticePreferencesIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, True); return api_call(service.save_preferences, ctx, body, check)
    @router.get('/notices')
    def notices(nid: str, response: Response, focus: bool = False, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'; return read_call('notices', nid, x_session_token, x_branch_id, focus)
    @router.post('/notices/acknowledge')
    def acknowledge(nid: str, body: AcknowledgeIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, True); return api_call(service.acknowledge, ctx, body, check)
    return router
