"""First-use routes: explicit writes, existing permissions, default-off gate."""
from fastapi import APIRouter, Header, Query, Response
from .common import api_call
from .first_use import FirstUseIn


def create_first_use_router(service, require_flag):
    router = APIRouter(prefix='/experimental/first-use', tags=['experimental-first-use'])

    def context(workspace_id, token):
        require_flag('workspace_tools_v2')
        return service.authority.context(workspace_id, token)

    @router.get('/sample')
    def read(response: Response, workspace_id: str | None = Query(None, min_length=1, max_length=160),
             x_session_token: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'
        return api_call(service.inspect, context(workspace_id, x_session_token))

    @router.post('/sample')
    def start(body: FirstUseIn, response: Response, x_session_token: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'
        return api_call(service.start, context(body.workspace_id, x_session_token))

    @router.post('/sample/recover')
    def recover(body: FirstUseIn, response: Response, x_session_token: str | None = Header(None)):
        response.headers['Cache-Control'] = 'no-store'
        return api_call(service.recover, context(body.workspace_id, x_session_token))

    return router
