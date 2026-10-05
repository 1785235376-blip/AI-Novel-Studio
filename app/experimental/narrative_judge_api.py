"""Current-authority narrative review; the inbox remains a read-through projection."""
from fastapi import APIRouter, Header, HTTPException, Response
from .common import api_call
from .narrative_judge import FEATURE, JudgeRunIn, JudgeReviewIn


def create_narrative_judge_router(service, authorize, require_flag):
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
        return api_call(service.create_run, nid, scope, actor, body, reauthorize=again)

    @router.post("/findings/{rid}/review")
    def review(nid: str, rid: str, body: JudgeReviewIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope, again = access(nid, x_session_token, x_branch_id, response, True)
        return api_call(service.review, nid, scope, actor, rid, body, reauthorize=again)

    return router
