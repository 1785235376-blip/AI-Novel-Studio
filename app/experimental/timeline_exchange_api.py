"""A12 scope-fenced exchange; each download is a new attachment, never a path write."""
from fastapi import APIRouter, Header, HTTPException, Response
from .production_lineage_api import api_call, PrivateProductionRoute
from .timeline_exchange import ImportOTIOIn, ScreenplayOTIOIn


def create_timeline_exchange_router(service, authorize, require_flag):
    router = APIRouter(prefix="/novels/{nid}/experimental/timeline-exchange", tags=["Experimental OTIO exchange"], route_class=PrivateProductionRoute)

    def invoke(nid, token, branch, permission, callback):
        def access():
            require_flag("timeline_exchange_v2"); require_flag("asset_lineage_v2")
            return authorize(nid, token, branch, permission)
        actor, scope = access()
        def guard():
            if access() != (actor, scope):
                raise HTTPException(403, {"code": "OTIO_AUTHORITY_CHANGED"})
        result = api_call(callback, actor, scope, guard)
        guard(); return result

    @router.get("/catalog")
    def catalog(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read", lambda actor, scope, guard: service.catalog(nid, scope, actor))

    @router.get("/records")
    def records(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read", lambda actor, scope, guard: service.records(nid, scope, actor))

    @router.post("/import", status_code=201)
    def import_file(nid: str, body: ImportOTIOIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write", lambda actor, scope, guard: service.import_file(nid, scope, actor, body, guard))

    @router.post("/from-screenplay", status_code=201)
    def screenplay(nid: str, body: ScreenplayOTIOIn, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write", lambda actor, scope, guard: service.from_screenplay(nid, scope, actor, body, guard))

    @router.get("/records/{rid}/file")
    def file(nid: str, rid: str, expected_version: int, acknowledge_losses: bool = False,
             x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        data, filename = invoke(nid, x_session_token, x_branch_id, "domain.read", lambda actor, scope, guard: service.download(nid, scope, actor, rid, expected_version, acknowledge_losses, guard))
        return Response(data, media_type="application/vnd.opentimelineio+json", headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})
    return router
