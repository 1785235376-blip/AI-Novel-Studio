"""Current-authority B06 APIs; raster bytes only, no executable exports."""
from fastapi import APIRouter, Header, HTTPException, Response, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import Field
from .comic_layouts import LayoutIn, LayoutEdit
from .media import StrictModel
from .production_lineage_api import PrivateProductionRoute, api_call


class ComicPrivateRoute(PrivateProductionRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def private(request):
            try:
                return await handler(request)
            except StarletteHTTPException as error:
                # Keep B06 validation and domain failures on one bounded private
                # response contract. The shared error envelope also preserves headers.
                return JSONResponse({'detail': error.detail}, status_code=error.status_code,
                                    headers={**(error.headers or {}), 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
            except RequestValidationError:
                return JSONResponse({'detail': {'code': 'COMIC_INPUT_INVALID'}}, status_code=422,
                                    headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
        return private


class VersionIn(StrictModel):
    expected_version: int = Field(ge=1, strict=True)


class ReviewIn(VersionIn):
    review_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    acknowledge_warnings: bool = False


class RestoreIn(VersionIn):
    target_version: int = Field(ge=1, strict=True)


def create_comic_layouts_router(service, authorize, require_flag):
    router = APIRouter(prefix='/novels/{nid}/experimental/comic-layouts', tags=['Experimental comic layouts'], route_class=ComicPrivateRoute)
    def invoke(nid, token, branch, permission, callback):
        def access():
            require_flag('comic_layouts_v2'); require_flag('asset_lineage_v2'); require_flag('ai_director_v2')
            return authorize(nid, token, branch, permission)
        actor, scope = access()
        def guard():
            if access() != (actor, scope): raise HTTPException(403, {'code': 'COMIC_AUTHORITY_CHANGED'})
        result = api_call(callback, actor, scope, guard); guard(); return result

    @router.get('/catalog')
    def catalog(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, 'domain.read', lambda a,s,g: service.catalog(nid,s,a))

    @router.get('/records')
    def records(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, 'domain.read', lambda a,s,g: service.records(nid,s,a))

    @router.get('/images/{aid}')
    def image(nid: str, aid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, 'domain.read', lambda a,s,g: Response(service.image_preview(nid,s,a,aid), media_type='image/png'))

    @router.post('/images/{aid}/approve')
    def approve_image(nid: str, aid: str, body: VersionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, 'domain.review', lambda a,s,g: service.approve_image(nid,s,a,aid,body.expected_version,g))

    @router.post('/records', status_code=201)
    def create(nid: str, body: LayoutIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, 'domain.write', lambda a,s,g: service.save(nid,s,a,body,g))

    @router.put('/records/{rid}')
    def update(nid: str, rid: str, body: LayoutEdit, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, 'domain.write', lambda a,s,g: service.save(nid,s,a,body.model_dump(exclude={'expected_version'}),g,rid,body.expected_version))

    @router.post('/records/{rid}/preflight')
    def preflight(nid: str, rid: str, body: VersionIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, 'domain.read', lambda a,s,g: service.preflight(nid,s,a,rid,body.expected_version))

    @router.post('/records/{rid}/approve')
    def approve(nid: str, rid: str, body: ReviewIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, 'domain.review', lambda a,s,g: service.approve(nid,s,a,rid,body.expected_version,body.review_digest,body.acknowledge_warnings,g))

    @router.post('/records/{rid}/restore')
    def restore(nid: str, rid: str, body: RestoreIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, 'domain.write', lambda a,s,g: service.restore(nid,s,a,rid,body.expected_version,body.target_version,g))

    @router.get('/records/{rid}/segments/{index}')
    def preview(nid: str, rid: str, index: int, expected_version: int = Query(ge=1), x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, 'domain.read', lambda a,s,g: Response(service.preview(nid,s,a,rid,expected_version,index,g), media_type='image/png'))

    @router.get('/records/{rid}/export')
    def export(nid: str, rid: str, expected_version: int = Query(ge=1), x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, 'domain.read', lambda a,s,g: Response(service.export(nid,s,a,rid,expected_version,g), media_type='application/zip', headers={'Content-Disposition': 'attachment; filename="comic-segments.zip"'}))
    return router
