"""B02 current-actor/scope/feature guarded authoring and explicit execution."""
from fastapi import APIRouter, Header, HTTPException, Response
from .common import api_call
from .ux import ReadContext
from .declarative_agents import FEATURE, WorkflowAuthoring, SaveDefinitionIn, TestIn, ActionIn


def create_declarative_agents_router(service, authorize, require_flag):
    router = APIRouter(prefix='/novels/{nid}/experimental/declarative-agents', tags=['declarative-agents'])
    def access(nid, token, branch, permission='domain.read'):
        require_flag(FEATURE)
        actor, scope = authorize(nid, token, branch, permission)
        ctx = ReadContext(nid, scope, actor, token, branch)
        def check():
            require_flag(FEATURE)
            if authorize(nid, token, branch, permission) != (actor, scope):
                raise HTTPException(409, {'code': 'DECLARATIVE_SCOPE_CHANGED'})
        return ctx, check
    def read(name, nid, token, branch, *args):
        ctx, check = access(nid, token, branch); result = api_call(getattr(service, name), ctx, *args); check(); return result
    @router.get('/catalog')
    def catalog(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'; return read('catalog', nid, x_session_token, x_branch_id)
    @router.post('/preflight')
    def preflight(nid: str, body: WorkflowAuthoring, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return read('preflight', nid, x_session_token, x_branch_id, body)
    @router.get('/definitions')
    def definitions(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'; return read('definitions', nid, x_session_token, x_branch_id)
    @router.post('/definitions', status_code=201)
    def create(nid: str, body: SaveDefinitionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, 'domain.write'); return api_call(service.save, ctx, None, body, check)
    @router.put('/definitions/{rid}')
    def save(nid: str, rid: str, body: SaveDefinitionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, 'domain.write'); return api_call(service.save, ctx, rid, body, check)
    @router.post('/definitions/{rid}/runs', status_code=201)
    def test(nid: str, rid: str, body: TestIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, 'domain.write'); return api_call(service.create_run, ctx, rid, body, check)
    @router.get('/runs')
    def runs(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'; return read('runs', nid, x_session_token, x_branch_id)
    @router.get('/runs/{rid}')
    def run(nid: str, rid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'; return read('get_run', nid, x_session_token, x_branch_id, rid)
    @router.post('/runs/{rid}/{action}')
    def transition(nid: str, rid: str, action: str, body: ActionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        permission = 'domain.review' if action in {'approve', 'reject'} else 'domain.write'
        ctx, check = access(nid, x_session_token, x_branch_id, permission)
        return api_call(service.transition, ctx, rid, action, body, check)
    return router
