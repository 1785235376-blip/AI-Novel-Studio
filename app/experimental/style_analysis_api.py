"""Author-only, server-gated style metric operations."""
from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import Field
from .common import api_call
from .planning import StrictModel
from .style_analysis import FEATURE, StyleProfileIn, StyleProfileEditIn, StyleAnalysisIn, StylePreviewIn


class StyleActionIn(StrictModel):
    expected_version: int = Field(ge=1)


def create_style_analysis_router(service, authorize, require_flag):
    router = APIRouter(prefix="/novels/{nid}/experimental/style-analysis", tags=["experimental-style-analysis"])

    def access(nid, token, branch, response, permission="domain.write"):
        require_flag(FEATURE)
        initial = authorize(nid, token, branch, permission)
        response.headers["Cache-Control"] = "no-store"
        def again():
            require_flag(FEATURE)
            if authorize(nid, token, branch, permission) != initial:
                raise HTTPException(409, {"code": "STYLE_AUTHORITY_CHANGED"})
        return (*initial, again)

    @router.get("/catalog")
    def catalog(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = api_call(service.catalog, nid, scope); again(); return result

    @router.post("/profiles", status_code=201)
    def create(nid: str, body: StyleProfileIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope, again = access(nid, x_session_token, x_branch_id, response)
        return api_call(service.save_profile, nid, scope, actor, body, reauthorize=again)

    @router.put("/profiles/{rid}")
    def edit(nid: str, rid: str, body: StyleProfileEditIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope, again = access(nid, x_session_token, x_branch_id, response)
        return api_call(service.save_profile, nid, scope, actor, body, rid, reauthorize=again)

    @router.post("/profiles/{rid}/preview")
    def preview(nid: str, rid: str, body: StylePreviewIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope, again = access(nid, x_session_token, x_branch_id, response)
        return api_call(service.preview, nid, scope, rid, body, reauthorize=again)

    @router.post("/profiles/{rid}/{action}")
    def transition(nid: str, rid: str, action: str, body: StyleActionIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope, again = access(nid, x_session_token, x_branch_id, response, "domain.review")
        return api_call(service.transition, nid, scope, actor, rid, action, body.expected_version, reauthorize=again)

    @router.get("/analyses")
    def analyses(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope, again = access(nid, x_session_token, x_branch_id, response)
        result = {"items": api_call(service.analyses, nid, scope)}; again(); return result

    @router.post("/analyses", status_code=201)
    def analyze(nid: str, body: StyleAnalysisIn, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope, again = access(nid, x_session_token, x_branch_id, response)
        return api_call(service.analyze, nid, scope, actor, body, reauthorize=again)

    return router
