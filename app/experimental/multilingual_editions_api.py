"""B05 author-private routes, exact feature gates and final authority fences."""
from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import ValidationError

from .common import api_call
from .multilingual_editions import FEATURE, EditionIn, VersionIn, SegmentIn, ReviewIn, RuleIn, RuleReviewIn, RefreshIn, ExportIn


def create_multilingual_editions_router(service, authorize, require_flag):
    router = APIRouter(prefix='/novels/{nid}/experimental/language-editions', tags=['experimental-multilingual-editions'])

    def access(nid, token, branch, response, permission='domain.write'):
        require_flag(FEATURE)
        authority = authorize(nid, token, branch, permission)
        response.headers['Cache-Control'] = 'no-store'
        def again():
            require_flag(FEATURE)
            if authorize(nid, token, branch, permission) != authority:
                raise HTTPException(409, {'code': 'LANGUAGE_EDITION_AUTHORITY_CHANGED'})
        return (*authority, again)

    async def body(request, model):
        require_flag(FEATURE)
        raw = bytearray()
        async for part in request.stream():
            raw.extend(part)
            if len(raw) > 2 * 1024 * 1024: raise HTTPException(413, {'code': 'LANGUAGE_EDITION_INPUT_TOO_LARGE'})
        try: return model.model_validate_json(bytes(raw))
        except (ValidationError, ValueError): raise HTTPException(422, {'code': 'LANGUAGE_EDITION_INPUT_INVALID'}) from None

    @router.get('/catalog')
    def catalog(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.catalog, nid, scope); again(); return result

    @router.get('')
    def editions(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.editions, nid, scope, actor); again(); return result

    @router.get('/{eid}')
    def edition(nid: str, eid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.edition, nid, scope, actor, eid); again(); return result

    @router.post('', status_code=201)
    async def create(nid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        data = await body(request, EditionIn); actor, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.create_edition, nid, scope, actor, data, reauthorize=again); again(); return result

    @router.put('/{eid}/segments/{sid}')
    async def save_segment(nid: str, eid: str, sid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        data = await body(request, SegmentIn); actor, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.save_segment, nid, scope, actor, eid, sid, data, reauthorize=again); again(); return result

    @router.post('/{eid}/segments/{sid}/preview')
    async def preview_segment(nid: str, eid: str, sid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        data = await body(request, VersionIn); actor, scope, again = access(nid, x_session_token, x_branch_id, response, 'domain.review')
        return api_call(service.preview_segment, nid, scope, actor, eid, sid, data, reauthorize=again)

    @router.post('/{eid}/segments/{sid}/review')
    async def review_segment(nid: str, eid: str, sid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        data = await body(request, ReviewIn); actor, scope, again = access(nid, x_session_token, x_branch_id, response, 'domain.review')
        result = api_call(service.review_segment, nid, scope, actor, eid, sid, data, reauthorize=again); again(); return result

    @router.post('/{eid}/rules')
    async def add_rule(nid: str, eid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        data = await body(request, RuleIn); actor, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.add_rule, nid, scope, actor, eid, data, reauthorize=again); again(); return result

    @router.post('/{eid}/rules/{rid}/review')
    async def review_rule(nid: str, eid: str, rid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        data = await body(request, RuleReviewIn); actor, scope, again = access(nid, x_session_token, x_branch_id, response, 'domain.review')
        result = api_call(service.review_rule, nid, scope, actor, eid, rid, data, reauthorize=again); again(); return result

    @router.post('/{eid}/refresh-preview')
    async def refresh_preview(nid: str, eid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        data = await body(request, VersionIn); actor, scope, again = access(nid, x_session_token, x_branch_id, response)
        return api_call(service.refresh_preview, nid, scope, actor, eid, data, reauthorize=again)

    @router.post('/{eid}/refresh')
    async def refresh_sources(nid: str, eid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        data = await body(request, RefreshIn); actor, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.refresh_sources, nid, scope, actor, eid, data, reauthorize=again); again(); return result

    @router.post('/{eid}/export-preview')
    async def export_preview(nid: str, eid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        data = await body(request, ExportIn); actor, scope, again = access(nid, x_session_token, x_branch_id, response, 'domain.review')
        return api_call(service.export_preview, nid, scope, actor, eid, data, reauthorize=again)

    @router.post('/{eid}/export')
    async def export(nid: str, eid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        data = await body(request, ExportIn); actor, scope, again = access(nid, x_session_token, x_branch_id, response, 'domain.review')
        return api_call(service.export, nid, scope, actor, eid, data, reauthorize=again)

    return router
