"""Server-authoritative opt-in manual simulation; no model dispatch route."""
from fastapi import APIRouter, Header, HTTPException, Response
from .common import api_call
from .story_simulator import FEATURE, SimulationRunIn, SimulatorContextIn, SimulationActionIn, SimulationSaveIn


def create_story_simulator_router(service, authorize, require_flag):
    router = APIRouter(prefix='/novels/{nid}/experimental/story-simulator', tags=['experimental-story-simulator'])

    def access(nid, token, branch, response):
        require_flag(FEATURE)
        initial = authorize(nid, token, branch, 'domain.write')
        response.headers['Cache-Control'] = 'no-store'
        def again():
            require_flag(FEATURE)
            if authorize(nid, token, branch, 'domain.write') != initial:
                raise HTTPException(409, {'code': 'SIMULATOR_AUTHORITY_CHANGED'})
        return (*initial, again)

    @router.get('/catalog')
    def catalog(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.catalog, nid, scope); again(); return result

    @router.post('/context')
    def context(nid: str, body: SimulatorContextIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.context, nid, scope, body); again(); return result

    @router.get('/runs')
    def runs(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = {'items': api_call(service.runs, nid, scope)}; again(); return result

    @router.get('/runs/{rid}')
    def run(nid: str, rid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.run, nid, scope, rid); again(); return result

    @router.post('/runs', status_code=201)
    def create(nid: str, body: SimulationRunIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope, again = access(nid, x_session_token, x_branch_id, response)
        return api_call(service.create_run, nid, scope, actor, body, reauthorize=again)

    @router.post('/runs/{rid}/step')
    def step(nid: str, rid: str, body: SimulationActionIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope, again = access(nid, x_session_token, x_branch_id, response)
        return api_call(service.step, nid, scope, actor, rid, body.expected_version, reauthorize=again)

    @router.post('/runs/{rid}/cancel')
    def cancel(nid: str, rid: str, body: SimulationActionIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope, again = access(nid, x_session_token, x_branch_id, response)
        return api_call(service.cancel, nid, scope, actor, rid, body.expected_version, reauthorize=again)

    @router.post('/runs/{rid}/save', status_code=201)
    def save(nid: str, rid: str, body: SimulationSaveIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope, again = access(nid, x_session_token, x_branch_id, response)
        return api_call(service.save, nid, scope, actor, rid, body, reauthorize=again)

    return router
