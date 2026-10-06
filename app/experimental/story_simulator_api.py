"""Server-authoritative manual simulation and explicitly reviewed local model candidates."""
from fastapi import APIRouter, Header, HTTPException, Response
from .common import api_call
from .story_simulator import FEATURE, SimulationRunIn, SimulatorContextIn, SimulationActionIn, SimulationSaveIn


def create_story_simulator_router(service, authorize, require_flag, *, preparer=None, manager=None, require_host_session=None):
    from .story_simulator_model import StorySimulatorModelCoordinator, SimulatorModelPreviewIn, SimulatorModelDispatchIn, SimulatorModelSelectIn, REQUIRED_FLAGS
    from .ux import ReadContext
    if preparer is not None and manager is not None and service.broker is not None:
        service.model_coordinator = StorySimulatorModelCoordinator(service, preparer, manager)
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

    def model_access(nid, token, branch, response):
        actor, scope, again = access(nid, token, branch, response)
        if not service.model_coordinator or not callable(require_host_session):
            raise HTTPException(409, {'code': 'SIMULATOR_BOUND_EXECUTOR_REQUIRED'})
        def current():
            again()
            for flag in REQUIRED_FLAGS: require_flag(flag)
            require_host_session(token)
        current()
        return ReadContext(nid, scope, actor, token, branch), current

    @router.post('/runs/{rid}/model/preview')
    def model_preview(nid: str, rid: str, body: SimulatorModelPreviewIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = model_access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.model_coordinator.preview, ctx, rid, body, check); check(); return result

    @router.post('/runs/{rid}/model/dispatch')
    def model_dispatch(nid: str, rid: str, body: SimulatorModelDispatchIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = model_access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.model_coordinator.dispatch, ctx, rid, body, check); check(); return result

    @router.post('/runs/{rid}/model/refresh')
    def model_refresh(nid: str, rid: str, body: SimulationActionIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = model_access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.model_coordinator.refresh, ctx, rid, body, check); check(); return result

    @router.post('/runs/{rid}/model/select', status_code=201)
    def model_select(nid: str, rid: str, body: SimulatorModelSelectIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = model_access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.model_coordinator.select, ctx, rid, body, check); check(); return result

    @router.post('/runs/{rid}/model/cancel')
    def model_cancel(nid: str, rid: str, body: SimulationActionIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, check = model_access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.model_coordinator.cancel, ctx, rid, body, check); check(); return result

    return router
