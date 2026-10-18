"""Layered planning model operations under original feature/session authority."""
from fastapi import APIRouter, Header, HTTPException, Response

from .common import api_call
from .narrative_judge_model import JudgeModelActionIn, JudgeModelPreviewIn, JudgeModelDispatchIn
from .planning_model import LayeredPlanningModelCoordinator, PlanningModelRequestIn, PlanningModelSaveIn
from .ux import ReadContext


def create_planning_model_router(service, authorize, require_flag, *, preparer, manager,
                                 broker, ai_planning, require_host_session):
    service.model_coordinator = LayeredPlanningModelCoordinator(service, preparer, manager, broker, ai_planning)
    router = APIRouter(prefix='/novels/{nid}/experimental/planning/model', tags=['experimental-planning-model'])

    def access(nid, token, branch, response, write=False):
        permission = 'domain.write' if write else 'domain.read'
        require_flag('advanced_planning_v2')
        initial = authorize(nid, token, branch, permission)
        response.headers['Cache-Control'] = 'no-store'
        def guard():
            for flag in ('advanced_planning_v2', 'model_broker_v2', 'author_context_inspector_v2'):
                require_flag(flag)
            require_host_session(token)
            if authorize(nid, token, branch, permission) != initial:
                raise HTTPException(409, {'code': 'PLANNING_MODEL_AUTHORITY_CHANGED'})
        guard()
        return ReadContext(nid, initial[1], initial[0], token, branch), guard

    @router.get('/catalog')
    def catalog(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, guard = access(nid, x_session_token, x_branch_id, response)
        return api_call(service.model_coordinator.catalog, ctx, guard)

    @router.get('/requests')
    def requests(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, guard = access(nid, x_session_token, x_branch_id, response)
        return api_call(service.model_coordinator.requests, ctx, guard)

    @router.get('/requests/{rid}')
    def request(nid: str, rid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, guard = access(nid, x_session_token, x_branch_id, response)
        return api_call(service.model_coordinator.get_request, ctx, rid, guard)

    @router.post('/requests', status_code=201)
    def create(nid: str, body: PlanningModelRequestIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, guard = access(nid, x_session_token, x_branch_id, response, True)
        return api_call(service.model_coordinator.create_request, ctx, body, guard)

    @router.post('/requests/{rid}/preview')
    def preview(nid: str, rid: str, body: JudgeModelPreviewIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, guard = access(nid, x_session_token, x_branch_id, response, True)
        return api_call(service.model_coordinator.preview, ctx, rid, body, guard)

    @router.post('/requests/{rid}/dispatch')
    def dispatch(nid: str, rid: str, body: JudgeModelDispatchIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, guard = access(nid, x_session_token, x_branch_id, response, True)
        return api_call(service.model_coordinator.dispatch, ctx, rid, body, guard)

    @router.post('/requests/{rid}/refresh')
    def refresh(nid: str, rid: str, body: JudgeModelActionIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, guard = access(nid, x_session_token, x_branch_id, response, True)
        return api_call(service.model_coordinator.refresh, ctx, rid, body, guard)

    @router.post('/requests/{rid}/cancel')
    def cancel(nid: str, rid: str, body: JudgeModelActionIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, guard = access(nid, x_session_token, x_branch_id, response, True)
        return api_call(service.model_coordinator.cancel, ctx, rid, body, guard)

    @router.post('/requests/{rid}/candidates/{cid}/save')
    def save(nid: str, rid: str, cid: str, body: PlanningModelSaveIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, guard = access(nid, x_session_token, x_branch_id, response, True)
        return api_call(service.model_coordinator.save, ctx, rid, cid, body, guard)

    return router
