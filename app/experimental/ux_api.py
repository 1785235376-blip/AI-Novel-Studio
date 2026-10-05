"""Server-gated workspace routes. No commands execute from search or diagnosis."""
import json
from fastapi import APIRouter, Header, HTTPException, Query, Response
from .common import api_call
from .planning import StrictModel
from pydantic import Field
from typing import Literal
from .ux import ReadContext, ResumeIn, VersionIn, ResumeResolveIn, ResolveIn, DiagnosticIn, DiagnosticExportIn


class SearchRequest(StrictModel):
    q: str = Field(default='', max_length=160)
    kind: str = ''
    chapter_id: str | None = None
    scope: Literal['project', 'authorized'] = 'project'
    tag: str = Field(default='', max_length=80)
    recent_days: int = Field(default=0, ge=0, le=3650)
    unresolved: bool = False
    fulltext: bool = False
    offset: int = Field(default=0, ge=0, le=40000)
    request_id: str | None = Field(default=None, pattern=r'^[a-zA-Z0-9_-]{1,80}$')


class SearchCancel(StrictModel):
    request_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,80}$')


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

    def run_search(ctx, options, rebuild=False):
        value = SearchRequest.model_validate(options)
        targets = [ctx]
        if value.scope == 'authorized':
            for nid, branch in service.candidates(ctx):
                if nid == ctx.novel_id and branch == ctx.branch: continue
                try:
                    candidate = access(nid, ctx.token, branch)
                    if candidate.actor != ctx.actor or candidate.scope.get('mode') != ctx.scope.get('mode'): continue
                    targets.append(candidate)
                except HTTPException as exc:
                    if exc.status_code not in {400, 401, 403, 404}: raise
        values = []
        # A bound is reported only for authorized targets, never denied IDs/counts.
        scope_truncated = len(targets) > 20
        for target in targets[:20]:
            try:
                result = service.search(target, value.q, value.kind, value.chapter_id, rebuild,
                    tag=value.tag, recent_days=value.recent_days, unresolved=value.unresolved, fulltext=value.fulltext,
                    request_id=value.request_id, reauthorize=lambda target=target: current(target), require_flag=require_flag,
                    cancelled=lambda: bool(value.request_id and service.search_cancelled(ctx, value.request_id)), limit=2000)
                values.append((target, result))
            except HTTPException as exc:
                if target == ctx or exc.status_code not in {401, 403, 404}: raise
                service.discard_search(target)
        verified = []
        for target, result in values:
            try:
                current(target)
                verified.append(result)
            except HTTPException as exc:
                service.discard_search(target)
                if target == ctx or exc.status_code not in {401, 403, 404}: raise
        current(ctx)
        if value.request_id and service.search_cancelled(ctx, value.request_id):
            raise HTTPException(409, {'code': 'SEARCH_CANCELLED'})
        items = [row for result in verified for row in result['items']]
        query = value.q.strip().casefold()
        def rank(row):
            title, aliases = row['title'].casefold(), [a.casefold() for a in row['aliases']]
            return (0 if query == title else 1 if query in aliases else 2 if title.startswith(query) else 3 if any(query in a for a in aliases) else 4,
                    title, row['novel_id'], row.get('branch_id') or '', row['kind'], row['id'])
        items.sort(key=rank)
        page = items[value.offset:value.offset + 50]
        index_truncated = scope_truncated or any(r['index_truncated'] for r in verified)
        return {'items': page, 'mode': 'LITERAL_LEXICAL', 'model_called': False,
                'match_count': len(items), 'truncated': index_truncated or len(items) > value.offset + 50,
                'index_truncated': index_truncated, 'next_offset': value.offset + 50 if len(items) > value.offset + 50 else None,
                'suggestions': list(dict.fromkeys(row['title'] for row in items))[:8],
                'updated_documents': sum(r['updated_documents'] for r in verified),
                'source_rows_read': sum(r['source_rows_read'] for r in verified),
                'metadata_checks': sum(r['metadata_checks'] for r in verified),
                'chapter_bodies_read': sum(r['chapter_bodies_read'] for r in verified),
                'projection_rows_scanned': sum(r['projection_rows_scanned'] for r in verified),
                'incremental_chapters': all(r['incremental_chapters'] for r in verified),
                'branch_sources_available': all(r['branch_sources_available'] for r in verified), 'limit': 50}

    @router.get('/search')
    def search(nid: str, q: str = Query('', max_length=160), kind: str = '', chapter_id: str | None = None,
               scope: str = 'project', tag: str = Query('', max_length=80), recent_days: int = Query(0, ge=0, le=3650),
               unresolved: bool = False, fulltext: bool = False, offset: int = Query(0, ge=0, le=40000),
               request_id: str | None = Query(None, pattern=r'^[a-zA-Z0-9_-]{1,80}$'),
               x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return api_call(run_search, access(nid, x_session_token, x_branch_id), dict(q=q, kind=kind, chapter_id=chapter_id,
            scope=scope, tag=tag, recent_days=recent_days, unresolved=unresolved, fulltext=fulltext, offset=offset, request_id=request_id))

    @router.post('/search/rebuild')
    def rebuild(nid: str, body: SearchRequest = SearchRequest(), x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return api_call(run_search, access(nid, x_session_token, x_branch_id), body, True)

    @router.post('/search/cancel')
    def cancel(nid: str, body: SearchCancel, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return api_call(service.cancel_search, access(nid, x_session_token, x_branch_id), body.request_id)

    @router.post('/search/resolve')
    def resolve(nid: str, body: ResolveIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        origin = access(nid, x_session_token, x_branch_id)
        target = access(body.novel_id or nid, x_session_token, body.branch_id if body.novel_id else x_branch_id)
        if target.actor != origin.actor or target.scope.get('mode') != origin.scope.get('mode'):
            raise HTTPException(403, {'code': 'WORKSPACE_AUTHORITY_CHANGED'})
        def checked():
            current(origin); current(target)
        return api_call(service.resolve, target, body, reauthorize=checked, require_flag=require_flag)

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
