"""Current session/project/branch/author fenced A10 routes. No legacy alias."""
from fastapi import APIRouter, Header, HTTPException, Query, Response
from fastapi.routing import APIRoute
from anyio import fail_after
import re
from pydantic import Field

from .common import api_call
from .research_library import FileIn, WebIn, EditIn, CitationIn, NoteIn, AdoptIn, StrictInput, ReplaceFileIn, RestoreSourceIn, EditNoteIn


class VersionIn(StrictInput):
    expected_version: int = Field(ge=1)


class ContextIn(StrictInput):
    citations: list[CitationIn] = Field(min_length=1, max_length=20)


def create_research_library_router(service, authorize, require_flag):
    class BoundedResearchRoute(APIRoute):
        def get_route_handler(self):
            handler = super().get_route_handler()
            async def bounded(request):
                # Reject before body parsing/extraction, even with chunked IO.
                require_flag('research_library_v2')
                authorize(request.path_params['nid'], request.headers.get('X-Session-Token'),
                          request.headers.get('X-Branch-ID'), 'domain.write')
                if request.method in {'POST', 'PUT'}:
                    limit = 6 * 1024 * 1024
                    size = request.headers.get('content-length')
                    if size is not None and (not size.isdecimal() or len(size) > 10 or int(size) > limit):
                        raise HTTPException(413, {'code': 'RESEARCH_REQUEST_LIMIT'})
                    chunks, total = [], 0
                    try:
                        with fail_after(15):
                            async for chunk in request.stream():
                                total += len(chunk)
                                if total > limit: raise HTTPException(413, {'code': 'RESEARCH_REQUEST_LIMIT'})
                                chunks.append(chunk)
                    except TimeoutError as exc:
                        raise HTTPException(408, {'code': 'RESEARCH_REQUEST_TIMEOUT'}) from exc
                    request._body = b''.join(chunks)
                return await handler(request)
            return bounded

    router = APIRouter(prefix='/novels/{nid}/experimental/research-library', tags=['experimental-research'], route_class=BoundedResearchRoute)

    def invoke(fn, *args, **kwargs):
        try:
            return api_call(fn, *args, **kwargs)
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            message = detail.get('message', '')
            if exc.status_code == 422 and isinstance(message, str) and re.fullmatch(r'RESEARCH_[A-Z_]{1,60}', message):
                raise HTTPException(422, {'code': message}) from exc
            raise

    def run(nid, token, branch, fn, *args, mutation=False, permission='domain.write'):
        def access():
            require_flag('research_library_v2')
            identity = authorize(nid, token, branch, 'domain.write')
            if permission != 'domain.write' and authorize(nid, token, branch, permission) != identity:
                raise HTTPException(403, {'code': 'RESEARCH_AUTHORITY_CHANGED'})
            return identity
        actor, scope = access()
        def guard():
            if access() != (actor, scope): raise HTTPException(403, {'code': 'RESEARCH_AUTHORITY_CHANGED'})
        if mutation:
            result = invoke(fn, nid, scope, actor, *args, guard=guard)
            guard()
            return result
        # All native projections share a current transaction view; revocation
        # cannot interleave between source validation and response construction.
        with service.store.transaction(nid, scope):
            guard()
            result = invoke(fn, nid, scope, actor, *args)
            guard()
            return result

    @router.get('/sources')
    def sources(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'
        return run(nid, x_session_token, x_branch_id, service.sources)

    @router.post('/sources/import', status_code=201)
    def import_file(nid: str, body: FileIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return run(nid, x_session_token, x_branch_id, service.import_file, body.model_dump(), mutation=True)

    @router.post('/sources/fetch-webpage', status_code=201)
    def import_web(nid: str, body: WebIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return run(nid, x_session_token, x_branch_id, service.import_web, body.model_dump(), mutation=True)

    @router.get('/sources-archive')
    def archive(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'
        return run(nid, x_session_token, x_branch_id, service.archived_sources)

    @router.get('/sources/{rid}/history')
    def source_history(nid: str, rid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'
        return run(nid, x_session_token, x_branch_id, service.source_history, rid)

    @router.get('/sources/{rid}/history/{version}/original')
    def historical_original(nid: str, rid: str, version: int, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        content, filename = run(nid, x_session_token, x_branch_id, service.historical_original, rid, version)
        from urllib.parse import quote
        return Response(content, media_type='application/octet-stream', headers={
            'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
            'Content-Disposition': "attachment; filename*=UTF-8''" + quote(filename, safe='')})

    @router.put('/sources/{rid}/file')
    def replace_file(nid: str, rid: str, body: ReplaceFileIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return run(nid, x_session_token, x_branch_id, service.replace_file, rid, body.model_dump(), mutation=True)

    @router.post('/sources/{rid}/restore')
    def restore_source(nid: str, rid: str, body: RestoreSourceIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return run(nid, x_session_token, x_branch_id, service.restore_source, rid, body.model_dump(), mutation=True)

    @router.get('/sources/{rid}')
    def source(nid: str, rid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'
        return run(nid, x_session_token, x_branch_id, service.source, rid)

    @router.get('/sources/{rid}/original')
    def original(nid: str, rid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        content, filename = run(nid, x_session_token, x_branch_id, service.original, rid)
        # Never inline untrusted PDFs/HTML/SVG; a download is an explicit action.
        from urllib.parse import quote
        return Response(content, media_type='application/octet-stream', headers={
            'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
            'Content-Disposition': "attachment; filename*=UTF-8''" + quote(filename, safe='')})

    @router.put('/sources/{rid}')
    def edit(nid: str, rid: str, body: EditIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return run(nid, x_session_token, x_branch_id, service.edit_source, rid, body.model_dump(), mutation=True)

    @router.post('/sources/{rid}/{action}')
    def transition(nid: str, rid: str, action: str, body: VersionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return run(nid, x_session_token, x_branch_id, service.transition_source, rid, body.expected_version, action, mutation=True)

    @router.get('/sources/{rid}/backrefs')
    def backrefs(nid: str, rid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'
        return run(nid, x_session_token, x_branch_id, service.backrefs, rid)

    @router.get('/search')
    def search(nid: str, response: Response, q: str = Query(min_length=1, max_length=200), limit: int = Query(default=30, ge=1, le=100), x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'
        return run(nid, x_session_token, x_branch_id, service.search, q, limit)

    @router.post('/citation')
    def citation(nid: str, body: CitationIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'
        return run(nid, x_session_token, x_branch_id, service.resolve, body.model_dump())

    @router.post('/context-preview')
    def context(nid: str, body: ContextIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'
        return run(nid, x_session_token, x_branch_id, service.context, [ref.model_dump() for ref in body.citations])

    @router.get('/notes')
    def notes(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'
        return run(nid, x_session_token, x_branch_id, service.notes)

    @router.post('/notes', status_code=201)
    def note(nid: str, body: NoteIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return run(nid, x_session_token, x_branch_id, service.create_note, body.model_dump(), mutation=True)

    @router.get('/note-repairs')
    def note_repairs(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'
        return run(nid, x_session_token, x_branch_id, service.note_repairs)

    @router.put('/notes/{rid}')
    def edit_note(nid: str, rid: str, body: EditNoteIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return run(nid, x_session_token, x_branch_id, service.edit_note, rid, body.model_dump(), mutation=True)

    @router.post('/notes/{rid}/delete')
    def delete_note(nid: str, rid: str, body: VersionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return run(nid, x_session_token, x_branch_id, service.delete_note, rid, body.expected_version, mutation=True)

    @router.get('/notes/{rid}/history')
    def note_history(nid: str, rid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'
        return run(nid, x_session_token, x_branch_id, service.note_history, rid)

    @router.get('/setting-drafts')
    def drafts(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'
        return run(nid, x_session_token, x_branch_id, service.drafts)

    @router.post('/setting-drafts', status_code=201)
    def adopt(nid: str, body: AdoptIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return run(nid, x_session_token, x_branch_id, service.adopt, body.model_dump(), mutation=True)

    @router.post('/setting-drafts/{rid}/{action}')
    def review(nid: str, rid: str, action: str, body: VersionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        # Reviewing a private author draft requires both normal author access
        # and the existing review permission; neither implies Canon approval.
        require_flag('research_library_v2')
        authorize(nid, x_session_token, x_branch_id, 'domain.write')
        return run(nid, x_session_token, x_branch_id, service.review_draft, rid, body.expected_version, action, mutation=True, permission='domain.review')

    return router
