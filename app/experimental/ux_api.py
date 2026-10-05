"""Server-gated workspace routes. No commands execute from search or diagnosis."""
import json
from fastapi import APIRouter, Header, HTTPException, Query, Response
from .common import api_call
from .ux import ReadContext, ResumeIn, VersionIn, ResumeResolveIn, ResolveIn, DiagnosticIn, DiagnosticExportIn


def create_ux_router(service, authorize, require_flag):
    router = APIRouter(prefix='/novels/{nid}/experimental/workspace', tags=['experimental-workspace'])

    def access(nid, token, branch, write=False):
        require_flag('workspace_tools_v2')
        actor, scope = authorize(nid, token, branch, 'domain.write' if write else 'domain.read')
        return ReadContext(nid, scope, actor, token, branch)

    def current(ctx, write=False):
        if access(ctx.novel_id, ctx.token, ctx.branch, write) != ctx:
            raise HTTPException(403, {'code': 'WORKSPACE_AUTHORITY_CHANGED'})

    @router.get('/resume')
    def resume(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx = access(nid, x_session_token, x_branch_id)
        return api_call(service.resume, ctx, require_flag, lambda: current(ctx))

    @router.put('/resume')
    def save_resume(nid: str, body: ResumeIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx = access(nid, x_session_token, x_branch_id, True)
        return api_call(service.save_resume, ctx, body, require_flag, lambda: current(ctx, True))

    @router.post('/resume/resolve')
    def resume_resolve(nid: str, body: ResumeResolveIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx = access(nid, x_session_token, x_branch_id)
        return api_call(service.resolve_resume, ctx, body, require_flag, lambda: current(ctx))

    @router.get('/resume/history')
    def history(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return api_call(service.resume_history, access(nid, x_session_token, x_branch_id))

    @router.post('/resume/reset-layout')
    def reset(nid: str, body: VersionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx = access(nid, x_session_token, x_branch_id, True)
        return api_call(service.reset_layout, ctx, body.expected_version, require_flag, lambda: current(ctx, True))

    @router.get('/search')
    def search(nid: str, q: str = Query('', max_length=160), kind: str = '', chapter_id: str | None = None,
               x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return api_call(service.search, access(nid, x_session_token, x_branch_id), q, kind, chapter_id)

    @router.post('/search/rebuild')
    def rebuild(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return api_call(service.search, access(nid, x_session_token, x_branch_id), rebuild=True)

    @router.post('/search/resolve')
    def resolve(nid: str, body: ResolveIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return api_call(service.resolve, access(nid, x_session_token, x_branch_id), body)

    @router.get('/tasks')
    def tasks(nid: str, q: str = Query('', max_length=160), failed_only: bool = False,
              x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return api_call(service.tasks, access(nid, x_session_token, x_branch_id), require_flag, q, failed_only)

    @router.post('/diagnostics/preview')
    def preview(nid: str, body: DiagnosticIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return api_call(service.diagnostics, access(nid, x_session_token, x_branch_id), body, require_flag)

    @router.post('/diagnostics/export')
    def export(nid: str, body: DiagnosticExportIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        data = api_call(service.export_diagnostics, access(nid, x_session_token, x_branch_id), body, require_flag)
        return Response(json.dumps(data, ensure_ascii=False, indent=2), media_type='application/json',
                        headers={'Content-Disposition': 'attachment; filename="workspace-diagnostics.json"'})

    return router
