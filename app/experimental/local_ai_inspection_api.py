"""Host-session AND project-authorized passive workflow inspection routes."""
from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import ValidationError

from .common import api_call
from .local_ai_inspection import FEATURE, MAX_BYTES, InspectionInput


def create_local_ai_inspection_router(service, authorize, require_flag, require_host_session):
    router = APIRouter(prefix="/novels/{nid}/experimental/local-ai/workflow-inspections", tags=["Experimental Local AI"])

    def access(nid, token, branch, permission="domain.read"):
        require_flag(FEATURE)
        # Existing discovery data is host-local, not merely a project reader's data.
        require_host_session(token)
        return authorize(nid, token, branch, permission)

    async def body_from(request):
        # Do not let FastAPI/Pydantic include raw prompt/key values in 422 errors.
        data = bytearray()
        async for part in request.stream():
            data.extend(part)
            if len(data) > MAX_BYTES * 2 + 4096:
                raise HTTPException(413, {"code": "WORKFLOW_REQUEST_TOO_LARGE"})
        try:
            return InspectionInput.model_validate_json(bytes(data))
        except (ValidationError, ValueError):
            raise HTTPException(422, {"code": "WORKFLOW_INPUT_INVALID"}) from None

    @router.get("")
    def metadata(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        access(nid, x_session_token, x_branch_id)
        response.headers["Cache-Control"] = "no-store"
        return api_call(service.metadata)

    @router.post("/inspect")
    async def inspect(nid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        access(nid, x_session_token, x_branch_id)
        body = await body_from(request)
        # Recheck after body arrival; revoked scope must not reveal host metadata.
        access(nid, x_session_token, x_branch_id)
        response.headers["Cache-Control"] = "no-store"
        return api_call(service.inspect, body)

    @router.get("/reports")
    def reports(nid: str, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        response.headers["Cache-Control"] = "no-store"
        return {"items": api_call(service.list, nid, scope, service.REPORTS)}

    @router.post("/reports", status_code=201)
    async def save(nid: str, request: Request, response: Response, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.write")
        body = await body_from(request)
        fresh = access(nid, x_session_token, x_branch_id, "domain.write")
        if fresh != (actor, scope): raise HTTPException(409, {"code": "WORKFLOW_SCOPE_CHANGED"})
        response.headers["Cache-Control"] = "no-store"
        return api_call(service.save_report, nid, scope, actor, body)

    return router
