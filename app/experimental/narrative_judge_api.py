"""Current-authority narrative review; the inbox remains a read-through projection."""
from fastapi import APIRouter, Header, HTTPException, Response
from .common import api_call
from .narrative_judge import FEATURE, JudgeRunIn, JudgeReviewIn, JudgeRevisionTaskIn


def create_narrative_judge_router(service, authorize, require_flag, *, preparer=None, manager=None, broker=None, require_host_session=None):
    from .narrative_judge_model import NarrativeJudgeModelCoordinator, JudgeModelActionIn, JudgeModelPreviewIn, JudgeModelDispatchIn
    from .ux import ReadContext
    if preparer is not None and manager is not None and broker is not None:
        service.model_coordinator = NarrativeJudgeModelCoordinator(service, preparer, manager, broker)
    router = APIRouter(prefix="/novels/{nid}/experimental/narrative-judge", tags=["experimental-narrative-judge"])

    def access(nid, token, branch, response, review=False):
        require_flag(FEATURE)
        initial = authorize(nid, token, branch, "domain.write")
        if review and authorize(nid, token, branch, "domain.review") != initial:
            raise HTTPException(403, {"code": "JUDGE_REVIEW_AUTHORITY_REQUIRED"})
        response.headers["Cache-Control"] = "no-store"
        def again():
            require_flag(FEATURE)
            if authorize(nid, token, branch, "domain.write") != initial or review and authorize(nid, token, branch, "domain.review") != initial:
                raise HTTPException(409, {"code": "JUDGE_AUTHORITY_CHANGED"})
        return (*initial, again)

    @router.get("/catalog")
    def catalog(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.catalog, nid, scope); again(); return result

    @router.get("/runs")
    def runs(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = {"items": api_call(service.runs, nid, scope)}; again(); return result

    @router.get("/runs/{rid}")
    def run(nid: str, rid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.run, nid, scope, rid); again(); return result

    @router.post("/runs", status_code=201)
    def create(nid: str, body: JudgeRunIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.create_run, nid, scope, actor, body, reauthorize=again); again(); return result

    @router.post("/findings/{rid}/review")
    def review(nid: str, rid: str, body: JudgeReviewIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope, again = access(nid, x_session_token, x_branch_id, response, True)
        result = api_call(service.review, nid, scope, actor, rid, body, reauthorize=again); again(); return result

    def revision_access(nid, token, branch, response):
        actor, scope, again = access(nid, token, branch, response, True)
        def current():
            again(); require_flag('writer_room_v2')
        current()
        return ReadContext(nid, scope, actor, token, branch), current

    @router.get('/findings/{rid}/revision-task')
    def revision_task_catalog(nid: str, rid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, current = revision_access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.revision_task_catalog, ctx, rid, current); current(); return result

    @router.post('/findings/{rid}/revision-task', status_code=201)
    def revision_task(nid: str, rid: str, body: JudgeRevisionTaskIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, current = revision_access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.create_revision_task, ctx, rid, body, current); current(); return result

    def model_access(nid, token, branch, response):
        actor, scope, again = access(nid, token, branch, response)
        if service.model_coordinator is None or not callable(require_host_session):
            raise HTTPException(409, {'code': 'JUDGE_REGISTERED_MODEL_EXECUTOR_UNAVAILABLE'})
        def current():
            again(); require_flag('model_broker_v2'); require_flag('author_context_inspector_v2'); require_host_session(token)
        current()
        return ReadContext(nid, scope, actor, token, branch), current

    @router.get('/model/catalog')
    def model_catalog(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, current = model_access(nid, x_session_token, x_branch_id, response)
        return api_call(service.model_coordinator.catalog, ctx, current)

    @router.post('/runs/{rid}/model/preview')
    def model_preview(nid: str, rid: str, body: JudgeModelPreviewIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, current = model_access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.model_coordinator.preview, ctx, rid, body, current); current(); return result

    @router.post('/runs/{rid}/model/dispatch')
    def model_dispatch(nid: str, rid: str, body: JudgeModelDispatchIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, current = model_access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.model_coordinator.dispatch, ctx, rid, body, current); current(); return result

    @router.post('/runs/{rid}/model/refresh')
    def model_refresh(nid: str, rid: str, body: JudgeModelActionIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, current = model_access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.model_coordinator.refresh, ctx, rid, body, current); current(); return result

    @router.post('/runs/{rid}/model/cancel')
    def model_cancel(nid: str, rid: str, body: JudgeModelActionIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        ctx, current = model_access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.model_coordinator.cancel, ctx, rid, body, current); current(); return result

    return router
