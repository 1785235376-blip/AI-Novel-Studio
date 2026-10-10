"""Author-only, server-gated style metric and explicit model-opinion operations."""
from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import Field
from .common import api_call
from .planning import StrictModel
from .style_analysis import FEATURE, StyleProfileIn, StyleProfileEditIn, StyleAnalysisIn, StylePreviewIn

class StyleActionIn(StrictModel):
    expected_version: int = Field(ge=1)

def create_style_analysis_router(service, authorize, require_flag, *, preparer=None, manager=None, broker=None, require_host_session=None):
    from .narrative_judge_model import JudgeModelActionIn, JudgeModelPreviewIn, JudgeModelDispatchIn
    from .style_analysis_model import StyleAnalysisModelCoordinator, StyleOpinionReviewIn
    from .ux import ReadContext
    if preparer is not None and manager is not None and broker is not None:
        service.model_coordinator = StyleAnalysisModelCoordinator(service, preparer, manager, broker)
    router = APIRouter(prefix='/novels/{nid}/experimental/style-analysis', tags=['experimental-style-analysis'])
    def access(nid, token, branch, response, permission='domain.write'):
        require_flag(FEATURE)
        initial = authorize(nid, token, branch, permission)
        response.headers['Cache-Control'] = 'no-store'
        def again():
            require_flag(FEATURE)
            if authorize(nid, token, branch, permission) != initial:
                raise HTTPException(409, {'code': 'STYLE_AUTHORITY_CHANGED'})
        return (*initial, again)
    @router.get('/catalog')
    def catalog(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.catalog, nid, scope); again(); return result
    @router.post('/profiles', status_code=201)
    def create(nid: str, body: StyleProfileIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.save_profile, nid, scope, actor, body, reauthorize=again); again(); return result
    @router.put('/profiles/{rid}')
    def edit(nid: str, rid: str, body: StyleProfileEditIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.save_profile, nid, scope, actor, body, rid, reauthorize=again); again(); return result
    @router.post('/profiles/{rid}/preview')
    def preview(nid: str, rid: str, body: StylePreviewIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.preview, nid, scope, rid, body, reauthorize=again); again(); return result
    @router.post('/profiles/{rid}/{action}')
    def transition(nid: str, rid: str, action: str, body: StyleActionIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope, again = access(nid, x_session_token, x_branch_id, response, 'domain.review')
        result = api_call(service.transition, nid, scope, actor, rid, action, body.expected_version, reauthorize=again); again(); return result
    @router.get('/analyses')
    def analyses(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = {'items': api_call(service.analyses, nid, scope)}; again(); return result
    @router.post('/analyses', status_code=201)
    def analyze(nid: str, body: StyleAnalysisIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.analyze, nid, scope, actor, body, reauthorize=again); again(); return result
    @router.get('/analyses/{rid}')
    def analysis(nid: str, rid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.analysis, nid, scope, rid); again(); return result
    def model_access(nid, token, branch, response):
        actor, scope, again = access(nid, token, branch, response)
        if service.model_coordinator is None or not callable(require_host_session):
            raise HTTPException(409, {'code': 'STYLE_REGISTERED_MODEL_EXECUTOR_UNAVAILABLE'})
        def current():
            again(); require_flag('model_broker_v2'); require_flag('author_context_inspector_v2'); require_host_session(token)
        current()
        return ReadContext(nid, scope, actor, token, branch), current
    @router.get('/model/catalog')
    def model_catalog(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, current = model_access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.model_coordinator.catalog, ctx, current); current(); return result
    @router.post('/analyses/{rid}/model/preview')
    def model_preview(nid: str, rid: str, body: JudgeModelPreviewIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, current = model_access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.model_coordinator.preview, ctx, rid, body, current); current(); return result
    @router.post('/analyses/{rid}/model/dispatch')
    def model_dispatch(nid: str, rid: str, body: JudgeModelDispatchIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, current = model_access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.model_coordinator.dispatch, ctx, rid, body, current); current(); return result
    @router.post('/analyses/{rid}/model/refresh')
    def model_refresh(nid: str, rid: str, body: JudgeModelActionIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, current = model_access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.model_coordinator.refresh, ctx, rid, body, current); current(); return result
    @router.post('/analyses/{rid}/model/cancel')
    def model_cancel(nid: str, rid: str, body: JudgeModelActionIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, current = model_access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.model_coordinator.cancel, ctx, rid, body, current); current(); return result
    @router.post('/analyses/{rid}/opinions/{opinion_id}/review')
    def review_opinion(nid: str, rid: str, opinion_id: str, body: StyleOpinionReviewIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope, again = access(nid, x_session_token, x_branch_id, response)
        def current():
            again()
            if authorize(nid, x_session_token, x_branch_id, 'domain.review') != (actor, scope):
                raise HTTPException(403, {'code': 'STYLE_REVIEW_AUTHORITY_REQUIRED'})
        current()
        result = api_call(service.review_opinion, nid, scope, actor, rid, opinion_id, body, current); current(); return result
    return router
