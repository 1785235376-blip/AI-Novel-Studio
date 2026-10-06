"""Every B08 request re-resolves its existing trusted session and current scope."""
from fastapi import APIRouter, Header, HTTPException, Query, Response
from ..services.creation_workbench_service import CommentIn
from .common import api_call as domain_call
from .ux import ReadContext
from .writer_room import FEATURE, WriterRoomConflict, TaskIn, TaskUpdate, TransitionIn, ThreadAction, PackageIn, PackageConfirm


def create_writer_room_router(service, authorize, require_flag):
    router = APIRouter(prefix='/novels/{nid}/experimental/writer-room', tags=['writer-room'])

    def access(nid, token, branch, write=False, permission=None):
        require_flag(FEATURE)
        permission = permission or ('domain.write' if write else 'domain.read')
        actor, scope = authorize(nid, token, branch, permission)
        ctx = ReadContext(nid, scope, actor, token, branch)
        def check():
            require_flag(FEATURE)
            if authorize(nid, token, branch, permission) != (actor, scope):
                raise HTTPException(403, {'code': 'WRITER_ROOM_AUTHORITY_CHANGED'})
        return ctx, check

    def call(name, nid, token, branch, *args, write=False, permission=None):
        ctx, check = access(nid, token, branch, write, permission)
        try:
            result = domain_call(getattr(service, name), ctx, *args, *([check] if write or name == 'package_download' else []))
            check()
            return result
        except WriterRoomConflict as exc:
            check()
            # Return only the persisted conflict ID; clients reread both candidates
            # through the same fresh authority, never a cached conflict payload.
            raise HTTPException(409, {'code': 'WRITER_ROOM_VERSION_CONFLICT', 'conflict_id': exc.record['id'], 'candidates_preserved': True}) from None

    @router.get('')
    def overview(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'
        return call('overview', nid, x_session_token, x_branch_id)

    @router.get('/presence-contract')
    def presence_contract(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'
        return call('presence_contract', nid, x_session_token, x_branch_id)

    @router.get('/catalog')
    def catalog(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'
        return call('catalog', nid, x_session_token, x_branch_id)

    @router.get('/chapters/{cid}')
    def chapter(nid: str, cid: str, response: Response, revision: str = Query(pattern=r'^[a-f0-9]{64}$'), x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'
        return call('chapter', nid, x_session_token, x_branch_id, cid, revision)

    @router.get('/index')
    def index(nid: str, response: Response, query: str = Query(default='', max_length=200), x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'
        return call('index', nid, x_session_token, x_branch_id, query)

    @router.get('/notices')
    def notices(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'
        return call('notices', nid, x_session_token, x_branch_id)

    @router.get('/conflicts')
    def conflicts(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'
        return call('conflicts', nid, x_session_token, x_branch_id)

    @router.post('/tasks', status_code=201)
    def create(nid: str, body: TaskIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call('create_task', nid, x_session_token, x_branch_id, body, write=True)

    @router.put('/tasks/{rid}')
    def update(nid: str, rid: str, body: TaskUpdate, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call('update_task', nid, x_session_token, x_branch_id, rid, body, write=True)

    @router.post('/tasks/{rid}/transition')
    def transition(nid: str, rid: str, body: TransitionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call('transition', nid, x_session_token, x_branch_id, rid, body, write=True, permission='domain.review' if body.action in {'request_changes', 'close', 'reopen'} else 'domain.write')

    @router.get('/comments')
    def comments(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'
        return call('comments', nid, x_session_token, x_branch_id)

    @router.post('/comments', status_code=201)
    def comment(nid: str, body: CommentIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call('create_comment', nid, x_session_token, x_branch_id, body, write=True)

    @router.post('/comments/{rid}')
    def comment_action(nid: str, rid: str, body: ThreadAction, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return call('comment_action', nid, x_session_token, x_branch_id, rid, body, write=True)

    @router.post('/packages/preview')
    def preview(nid: str, body: PackageIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'
        return call('package_preview', nid, x_session_token, x_branch_id, body)

    @router.post('/packages/download')
    def download(nid: str, body: PackageConfirm, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'
        return call('package_download', nid, x_session_token, x_branch_id, body)

    return router
