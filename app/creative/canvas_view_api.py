"""Closed display-only routes using the original Graph invocation boundary."""
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from ..experimental.production_lineage_api import PrivateProductionRoute
from .canvas_view_models import CANVAS_VIEWS, CanvasViewCreate, CanvasViewSave


class CanvasViewRoute(PrivateProductionRoute):
    MAX_BODY = 768_000

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def checked(request):
            headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
            try:
                payload = bytearray()
                async for part in request.stream():
                    if len(payload) + len(part) > self.MAX_BODY:
                        raise HTTPException(413, {"code": "CREATIVE_CANVAS_REQUEST_LIMIT"}, headers=headers)
                    payload.extend(part)
                request._body = bytes(payload)
                return await handler(request)
            except RequestValidationError:
                raise HTTPException(422, {"code": "CREATIVE_CANVAS_REQUEST_INVALID"}, headers=headers) from None
            except HTTPException as exc:
                exc.headers = {**(exc.headers or {}), **headers}
                raise
        return checked


def create_canvas_view_router(service, invoke):
    router = APIRouter(tags=["Creative Canvas Views V2"], route_class=CanvasViewRoute)

    @router.get("/projects/{nid}/studio/canvas-views")
    def list_views(nid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
            lambda actor, scope, guard: service.canvas_views.list(nid, scope, actor, guard), request)

    @router.post("/projects/{nid}/studio/canvas-views", status_code=201)
    def create_view(nid: str, request: Request, body: CanvasViewCreate, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
            lambda actor, scope, guard: service.canvas_views.create(nid, scope, actor, body, guard), request)

    @router.get("/projects/{nid}/studio/canvas-views/{vid}")
    def get_view(nid: str, vid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
            lambda actor, scope, guard: service.canvas_views.get(nid, scope, actor, vid, guard), request,
            target=(CANVAS_VIEWS, vid))

    @router.put("/projects/{nid}/studio/canvas-views/{vid}")
    def save_view(nid: str, vid: str, request: Request, body: CanvasViewSave, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
            lambda actor, scope, guard: service.canvas_views.save(nid, scope, actor, vid, body, guard), request,
            target=(CANVAS_VIEWS, vid))

    return router
