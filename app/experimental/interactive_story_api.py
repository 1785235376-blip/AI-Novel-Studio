"""B07 default-off mounted routes with current authority checks and bounded input."""
from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import ValidationError
from .common import api_call
from .interactive_story import FEATURE, CreateIn, SaveIn, VersionIn, ReviewIn, PlayIn, ExportIn


def create_interactive_story_router(service, authorize, require_flag):
    router = APIRouter(prefix='/novels/{nid}/experimental/interactive-stories', tags=['experimental-interactive-story'])

    def access(nid, token, branch, response, permission='domain.write'):
        require_flag(FEATURE); authority = authorize(nid, token, branch, permission)
        response.headers['Cache-Control'] = 'no-store'
        def again():
            require_flag(FEATURE)
            if authorize(nid, token, branch, permission) != authority:
                raise HTTPException(409, {'code': 'INTERACTIVE_STORY_AUTHORITY_CHANGED'})
        return (*authority, again)

    async def body(request, model):
        require_flag(FEATURE); raw = bytearray()
        async for part in request.stream():
            raw.extend(part)
            if len(raw) > 2 * 1024 * 1024: raise HTTPException(413, {'code': 'INTERACTIVE_STORY_INPUT_TOO_LARGE'})
        try: return model.model_validate_json(bytes(raw))
        except (ValidationError, ValueError): raise HTTPException(422, {'code': 'INTERACTIVE_STORY_INPUT_INVALID'}) from None

    @router.get('/catalog')
    def catalog(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.catalog, nid, scope); again(); return result

    @router.get('')
    def stories(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.stories, nid, scope, actor); again(); return result

    @router.get('/{sid}')
    def story(nid: str, sid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.story, nid, scope, actor, sid); again(); return result

    @router.post('', status_code=201)
    async def create(nid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        value = await body(request, CreateIn); actor, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.create_story, nid, scope, actor, value, reauthorize=again); again(); return result

    @router.put('/{sid}')
    async def save(nid: str, sid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        value = await body(request, SaveIn); actor, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.save, nid, scope, actor, sid, value, reauthorize=again); again(); return result

    def post_route(suffix, method, model, permission):
        async def action(nid: str, sid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
            value = await body(request, model); actor, scope, again = access(nid, x_session_token, x_branch_id, response, permission)
            result = api_call(method, nid, scope, actor, sid, value, reauthorize=again); again(); return result
        action.__name__ = 'interactive_story_' + suffix.replace('-', '_')
        router.add_api_route('/{sid}/' + suffix, action, methods=['POST'])
    post_route('review-preview', service.review_preview, VersionIn, 'domain.review')
    post_route('review', service.review, ReviewIn, 'domain.review')
    post_route('preview', service.preview, PlayIn, 'domain.write')
    post_route('refresh-preview', service.refresh_preview, VersionIn, 'domain.write')
    post_route('refresh', service.refresh, ExportIn, 'domain.write')
    post_route('export-preview', service.export_preview, ExportIn, 'domain.review')
    post_route('export', service.export, ExportIn, 'domain.review')
    return router
