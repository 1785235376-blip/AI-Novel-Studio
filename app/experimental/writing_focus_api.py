"""Default-off U04 routes; current request authority and CAS on every write."""
from fastapi import APIRouter, Header, HTTPException, Query, Response

from .common import api_call
from .ux import ReadContext
from .writing_focus import PreferencesIn, NoteIn, NoteEditIn, VersionIn, CopyPreviewIn, CopyIn, BookmarkResolveIn


def create_writing_focus_router(service, authorize, require_flag):
    router = APIRouter(prefix='/novels/{nid}/experimental/writing-focus', tags=['experimental-writing-focus'])

    def access(nid, token, branch, write=False, planning=False):
        require_flag('writing_focus_v2')
        if planning:
            require_flag('advanced_planning_v2')
        permission = 'domain.write' if write else 'domain.read'
        actor, scope = authorize(nid, token, branch, permission)
        ctx = ReadContext(nid, scope, actor, token, branch)
        def reauthorize():
            require_flag('writing_focus_v2')
            if planning:
                require_flag('advanced_planning_v2')
            if authorize(nid, token, branch, permission) != (actor, scope):
                raise HTTPException(409, {'code': 'WRITING_FOCUS_SCOPE_CHANGED'})
        return ctx, reauthorize

    @router.get('/preferences')
    def preferences(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'
        return api_call(service.preferences, access(nid, x_session_token, x_branch_id)[0])

    @router.put('/preferences')
    def save_preferences(nid: str, body: PreferencesIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, reauthorize = access(nid, x_session_token, x_branch_id, True)
        return api_call(service.save_preferences, ctx, body, reauthorize)

    @router.get('/references')
    def references(nid: str, response: Response, q: str = Query('', max_length=160), kind: str = '', x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'
        return api_call(service.references, access(nid, x_session_token, x_branch_id)[0], q, kind)

    @router.get('/pins')
    def pins(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'
        return api_call(service.pinned, access(nid, x_session_token, x_branch_id)[0])

    @router.post('/bookmarks/open')
    def open_bookmark(nid: str, body: BookmarkResolveIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return api_call(service.open_bookmark, access(nid, x_session_token, x_branch_id)[0], body)

    @router.get('/overview')
    def overview(nid: str, response: Response, chapter_id: str | None = Query(None, max_length=160), x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'
        return api_call(service.overview, access(nid, x_session_token, x_branch_id)[0], chapter_id)

    @router.get('/notes')
    def notes(nid: str, response: Response, archived: bool = False, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'
        return api_call(service.notes, access(nid, x_session_token, x_branch_id)[0], archived)

    @router.post('/notes', status_code=201)
    def create_note(nid: str, body: NoteIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, reauthorize = access(nid, x_session_token, x_branch_id, True)
        return api_call(service.create_note, ctx, body, reauthorize)

    @router.put('/notes/{note_id}')
    def edit_note(nid: str, note_id: str, body: NoteEditIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, reauthorize = access(nid, x_session_token, x_branch_id, True)
        return api_call(service.edit_note, ctx, note_id, body, reauthorize)

    @router.post('/notes/{note_id}/{action}')
    def transition(nid: str, note_id: str, action: str, body: VersionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, reauthorize = access(nid, x_session_token, x_branch_id, True)
        return api_call(service.transition_note, ctx, note_id, body.expected_version, action, reauthorize)

    @router.get('/planning-targets')
    def targets(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return api_call(service.targets, access(nid, x_session_token, x_branch_id, planning=True)[0])

    @router.post('/notes/{note_id}/planning/preview')
    def preview_copy(nid: str, note_id: str, body: CopyPreviewIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return api_call(service.preview_copy, access(nid, x_session_token, x_branch_id, planning=True)[0], note_id, body)

    @router.post('/notes/{note_id}/planning/copy', status_code=201)
    def copy_to_planning(nid: str, note_id: str, body: CopyIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, reauthorize = access(nid, x_session_token, x_branch_id, True, True)
        return api_call(service.copy_to_planning, ctx, note_id, body, reauthorize)

    return router
