"""Closed display-only routes using the original Graph invocation boundary."""
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from ..experimental.production_lineage_api import PrivateProductionRoute
from .canvas_view_models import (CANVAS_VIEWS, CanvasViewCreate, CanvasViewSave, CanvasViewRestore,
    CanvasImageNodeResult, CanvasViewResolveCreate)


class CanvasViewRoute(PrivateProductionRoute):
    MAX_BODY = 768_000

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def checked(request):
            headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
            try:
                payload = bytearray()
                limit=16_384 if request.method=='POST' and request.url.path.endswith('/resolve-create') else self.MAX_BODY
                async for part in request.stream():
                    if len(payload) + len(part) > limit:
                        raise HTTPException(413, {"code": "CREATIVE_CANVAS_REQUEST_LIMIT"}, headers=headers)
                    payload.extend(part)
                request._body = bytes(payload)
                return await handler(request)
            except RequestValidationError:
                raise HTTPException(422, {"code": "CREATIVE_CANVAS_REQUEST_INVALID"}, headers=headers) from None
            except HTTPException as exc:
                exc.headers = {**(exc.headers or {}), **headers}
                if request.method == 'POST' and request.url.path.endswith('/resolve-create'):
                    code={400:'CREATIVE_CANVAS_CREATE_INVALID',403:'CREATIVE_CANVAS_CREATE_FORBIDDEN',
                        404:'CREATIVE_CANVAS_CREATE_NOT_FOUND',409:'CREATIVE_CANVAS_CREATE_CHANGED',
                        413:'CREATIVE_CANVAS_REQUEST_LIMIT',422:'CREATIVE_CANVAS_REQUEST_INVALID'}.get(
                            exc.status_code,'CREATIVE_CANVAS_CREATE_REJECTED')
                    raise HTTPException(exc.status_code,{'code':code},headers=exc.headers) from None
                if request.method == 'POST' and request.url.path.endswith('/image-node-result'):
                    # New result-association errors never echo raw Job/Asset
                    # owner exceptions, source identities or input text.
                    code={400:'CREATIVE_CANVAS_IMAGE_NODE_INVALID',403:'CREATIVE_CANVAS_IMAGE_NODE_FORBIDDEN',
                        404:'CREATIVE_CANVAS_IMAGE_NODE_UNAVAILABLE',409:'CREATIVE_CANVAS_IMAGE_NODE_CHANGED',
                        413:'CREATIVE_CANVAS_REQUEST_LIMIT',422:'CREATIVE_CANVAS_REQUEST_INVALID'}.get(
                            exc.status_code,'CREATIVE_CANVAS_IMAGE_NODE_REJECTED')
                    raise HTTPException(exc.status_code,{'code':code},headers=exc.headers) from None
                raise
            except Exception:
                if request.method == 'POST' and request.url.path.endswith('/resolve-create'):
                    raise HTTPException(503,{'code':'CREATIVE_CANVAS_CREATE_LOOKUP_UNKNOWN'},headers=headers) from None
                if request.method == 'POST' and request.url.path.endswith('/image-node-result'):
                    raise HTTPException(503,{'code':'CREATIVE_CANVAS_IMAGE_NODE_OUTCOME_UNKNOWN'},headers=headers) from None
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

    @router.post('/projects/{nid}/studio/canvas-views/resolve-create')
    def resolve_create(nid: str, request: Request, body: CanvasViewResolveCreate,
                       x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        # Original invoker captures incarnation before calling the operation;
        # cover it too so an observation cannot provision a missing identity.
        with service.store.existing_owner_only(), service.workspace.store.existing_owner_only():
            return invoke(nid,x_session_token,x_branch_id,'domain.read',
                lambda actor,scope,guard:service.canvas_views.resolve_create(nid,scope,actor,body,guard),request)

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

    @router.get("/projects/{nid}/studio/canvas-views/{vid}/history")
    def history_view(nid: str, vid: str, request: Request, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
            lambda actor, scope, guard: service.canvas_views.history(nid, scope, actor, vid, guard), request,
            target=(CANVAS_VIEWS, vid))

    @router.post("/projects/{nid}/studio/canvas-views/{vid}/restore")
    def restore_view(nid: str, vid: str, request: Request, body: CanvasViewRestore, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
            lambda actor, scope, guard: service.canvas_views.restore(nid, scope, actor, vid, body, guard), request,
            target=(CANVAS_VIEWS, vid))

    @router.post("/projects/{nid}/studio/canvas-views/{vid}/image-node-result")
    def image_node_result(nid: str, vid: str, request: Request, body: CanvasImageNodeResult,
                          x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        def write(actor,scope,write_guard):
            def read(read_actor,read_scope,read_guard):
                if read_actor != actor or read_scope != scope:
                    raise HTTPException(403,{'code':'CREATIVE_CANVAS_IMAGE_NODE_FORBIDDEN'})
                def current():
                    write_guard();read_guard()
                current()
                return service.canvas_views.image_node_result(nid,scope,actor,vid,body,current)
            return invoke(nid,x_session_token,x_branch_id,'domain.read',read,request,target=(CANVAS_VIEWS,vid))
        # Association introduces a formal source into an initially empty canvas.
        # Capture original read + write authority before that transition, rather
        # than admitting write-only and rejecting our own origin at commit.
        return invoke(nid,x_session_token,x_branch_id,'domain.write',write,request,
            target=(CANVAS_VIEWS,vid),local_input=True)

    return router
