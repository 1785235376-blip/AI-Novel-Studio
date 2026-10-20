"""B01 declarative catalog API. Imports are data only; no filesystem extraction."""
from fastapi import APIRouter, Header, HTTPException, Response
from .common import api_call
from .ux import ReadContext
from .template_library import FEATURE, PreviewIn, InstallIn, VersionIn, FavoriteIn, CopyIn, EditInstanceIn, CompareIn, ApplyUpdateIn, RevertIn


def create_template_library_router(service, authorize, require_flag):
    router = APIRouter(prefix='/novels/{nid}/experimental/template-library', tags=['template-library'])
    def access(nid, token, branch, write=False):
        require_flag(FEATURE); permission = 'domain.write' if write else 'domain.read'
        actor, scope = authorize(nid, token, branch, permission); ctx = ReadContext(nid, scope, actor, token, branch)
        def check():
            require_flag(FEATURE)
            if authorize(nid, token, branch, permission) != (actor, scope): raise HTTPException(409, {'code': 'TEMPLATE_SCOPE_CHANGED'})
        return ctx, check
    def read(name, nid, token, branch, *args):
        ctx, check = access(nid, token, branch); result = api_call(getattr(service, name), ctx, *args); check(); return result
    @router.get('')
    def catalog(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'; return read('catalog', nid, x_session_token, x_branch_id)
    @router.post('/preview')
    def preview(nid: str, body: PreviewIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return read('preview', nid, x_session_token, x_branch_id, body)
    @router.post('/install')
    def install(nid: str, body: InstallIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, True); return api_call(service.install, ctx, body, check)
    @router.post('/packages/{pid}/favorite')
    def favorite(nid: str, pid: str, body: FavoriteIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, True); return api_call(service.favorite, ctx, pid, body, check)
    @router.post('/packages/{pid}/uninstall')
    def uninstall(nid: str, pid: str, body: VersionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, True); return api_call(service.uninstall, ctx, pid, body, check)
    @router.get('/instances')
    def instances(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'; return read('instances', nid, x_session_token, x_branch_id)
    @router.post('/instances', status_code=201)
    def copy(nid: str, body: CopyIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, True); return api_call(service.copy, ctx, body, check)
    @router.put('/instances/{rid}')
    def edit(nid: str, rid: str, body: EditInstanceIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, True); return api_call(service.edit, ctx, rid, body, check)
    @router.post('/instances/{rid}/compare')
    def compare(nid: str, rid: str, body: CompareIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return read('compare', nid, x_session_token, x_branch_id, rid, body)
    @router.post('/instances/{rid}/update')
    def update(nid: str, rid: str, body: ApplyUpdateIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, True); return api_call(service.apply_update, ctx, rid, body, check)
    @router.get('/instances/{rid}/history')
    def history(nid: str, rid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'; return read('history', nid, x_session_token, x_branch_id, rid)
    @router.post('/instances/{rid}/revert')
    def revert(nid: str, rid: str, body: RevertIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = access(nid, x_session_token, x_branch_id, True); return api_call(service.revert, ctx, rid, body, check)
    return router
