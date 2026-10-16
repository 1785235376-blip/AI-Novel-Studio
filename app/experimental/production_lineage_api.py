"""Mounted, current-authority A09/A13 routes; exports never return raw prompts."""
from fastapi import APIRouter, Header
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException
from pydantic import Field

from .common import api_call as domain_call
from .media import StrictModel
from .production_lineage import LineageInput, ManifestInput, ReplayInput
from ..services.v1_capability_service import CapabilityVersionConflict


def api_call(fn, *args, **kwargs):
    """A conflict cannot smuggle raw task snapshots or denied parent IDs.

    The UI preserves its local draft and explicitly reloads the authorized
    projection instead of receiving a complete internal current record.
    """
    def checked():
        try:
            return fn(*args, **kwargs)
        except CapabilityVersionConflict as exc:
            raise CapabilityVersionConflict({k: exc.current[k] for k in ("version", "status") if k in exc.current}) from None
    return domain_call(checked)


class ManifestVersion(StrictModel):
    expected_version: int = Field(ge=1)


class ReplayVersion(StrictModel):
    expected_task_version: int = Field(ge=1)


class PrivateProductionRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def private(request):
            try:
                response = await handler(request)
            except HTTPException as exc:
                exc.headers = {**(exc.headers or {}), "Cache-Control": "no-store"}
                raise
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response
        return private


def create_production_lineage_router(service, authorize, require_flag):
    router = APIRouter(prefix="/novels/{nid}/experimental/production", tags=["Experimental production lineage"], route_class=PrivateProductionRoute)

    def access(nid, token, branch, permission="domain.read", manifest=False):
        require_flag("asset_lineage_v2")
        if manifest:
            require_flag("production_manifest_v2")
            require_flag("cover_storyboard_generation")
            require_flag("media_adapter_registry")
        return authorize(nid, token, branch, permission)

    def fresh(nid, token, branch, actor, scope, manifest=False):
        def guard():
            if access(nid, token, branch, "domain.write", manifest) != (actor, scope):
                raise ValueError("PRODUCTION_AUTHORITY_CHANGED")
        return guard

    @router.get("/assets")
    def assets(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return api_call(service.assets_view, nid, scope)

    @router.get("/assets/{aid}")
    def asset(nid: str, aid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return api_call(service.asset, nid, scope, aid)

    @router.put("/assets/{aid}/lineage")
    def annotate(nid: str, aid: str, body: LineageInput, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.write")
        return api_call(service.annotate, nid, scope, actor, aid, body, fresh(nid, x_session_token, x_branch_id, actor, scope))

    @router.get("/assets/{aid}/impact")
    def impact(nid: str, aid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id)
        return api_call(service.impact, nid, scope, aid)

    @router.get("/manifests")
    def manifests(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id, manifest=True)
        return api_call(service.manifests, nid, scope)

    @router.post("/manifests", status_code=201)
    def capture(nid: str, body: ManifestInput, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.write", True)
        return api_call(service.capture, nid, scope, actor, body, fresh(nid, x_session_token, x_branch_id, actor, scope, True))

    @router.post("/manifests/{rid}/preflight")
    def preflight(nid: str, rid: str, body: ManifestVersion, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.write", True)
        return api_call(service.preflight, nid, scope, actor, rid, body.expected_version, fresh(nid, x_session_token, x_branch_id, actor, scope, True))

    @router.get("/manifests/{rid}/export")
    def export(nid: str, rid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        _, scope = access(nid, x_session_token, x_branch_id, manifest=True)
        return api_call(service.export, nid, scope, rid)

    @router.post("/manifests/{rid}/replay", status_code=201)
    def replay(nid: str, rid: str, body: ReplayInput, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.write", True)
        return api_call(service.replay, nid, scope, actor, rid, body, fresh(nid, x_session_token, x_branch_id, actor, scope, True))

    @router.get("/replays")
    def replays(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, manifest=True)
        return api_call(service.replays, nid, scope, actor)

    @router.post("/replays/{rid}/execute")
    def execute(nid: str, rid: str, body: ReplayVersion, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.write", True)
        return api_call(service.execute_replay, nid, scope, actor, rid, body.expected_task_version, fresh(nid, x_session_token, x_branch_id, actor, scope, True))

    @router.post("/replays/{rid}/cancel")
    def cancel(nid: str, rid: str, body: ReplayVersion, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        actor, scope = access(nid, x_session_token, x_branch_id, "domain.write", True)
        return api_call(service.cancel_replay, nid, scope, actor, rid, body.expected_task_version, fresh(nid, x_session_token, x_branch_id, actor, scope, True))

    return router
