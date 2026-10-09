"""Opt-in neutral project routes; original project/branch authority is unchanged."""
from urllib.parse import quote
import re
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Query, Response

from ..experimental.production_lineage_api import PrivateProductionRoute, api_call
from .workspace import FLAG
from .storage_admission import StudioStorageCapacityError
from .workspace_models import (AssetRelationshipIn, AssetVersion, BlankProjectIn, ManualAssetImport,
                               StudioLineageInput, WorkspacePreferencesUpdate)


def is_independent_studio_route(method, normalized_path):
    """Exact method/path admission; each handler still resolves full authority."""
    root = r"/api/projects/[^/]+/studio"
    patterns = {
        "GET": root + r"(?:/(?:preferences|storage|references|relationships|assets(?:/[^/]+(?:/download)?)?))?",
        "POST": r"(?:/api/experimental/projects|" + root + r"/(?:activate|assets(?:/[^/]+/(?:restore|relationships))?))",
        "PUT": root + r"/(?:preferences|assets/[^/]+/lineage)",
        "DELETE": root + r"/assets/[^/]+(?:/relationships/[^/]+)?",
    }
    return method in patterns and re.fullmatch(patterns[method], normalized_path) is not None


def create_independent_workspace_router(service, authorize, require_flag, *, create_project, workspace_writer):
    router = APIRouter(tags=["Independent Studios V2"], route_class=PrivateProductionRoute)

    def access(nid, token, branch, permission):
        require_flag(FLAG)
        actor, scope = authorize(nid, token, branch, permission)
        service.store.key(nid, scope)
        if not isinstance(actor, str) or not actor:
            raise HTTPException(403, {"code": "CREATIVE_AUTHORITY_INVALID"})
        return actor, scope

    def invoke(nid, token, branch, permission, callback):
        def operation():
            actor, scope = access(nid, token, branch, permission)
            incarnation = service.store.incarnation(nid)
            def guard():
                if (access(nid, token, branch, permission) != (actor, scope)
                        or service.store.incarnation(nid) != incarnation):
                    raise HTTPException(403, {"code": "CREATIVE_AUTHORITY_CHANGED"})
            try:
                result = callback(actor, scope, guard)
            except StudioStorageCapacityError as exc:
                guard()
                raise HTTPException(507, {"code": str(exc)}) from None
            except Exception:
                guard()
                raise
            guard()
            return result
        return api_call(operation)

    @router.post("/experimental/projects", status_code=201)
    def blank_project(body: BlankProjectIn, x_session_token: str | None = Header(None)):
        def operation():
            require_flag(FLAG)
            actor = workspace_writer(x_session_token)
            def guard():
                require_flag(FLAG)
                if workspace_writer(x_session_token) != actor:
                    raise HTTPException(403, {"code": "CREATIVE_AUTHORITY_CHANGED"})
            result = create_project(body, x_session_token)
            guard()
            # Shared-mode navigation still comes from the existing admin owner
            # and eligible_paths. Never manufacture a local branch for it.
            if actor is None:
                invoke(result["id"], x_session_token, None, "domain.write",
                    lambda current, scope, fresh: service.activate(result["id"], scope, current, fresh))
            guard()
            return {**result, "studio_ready": actor is None, "requires_scope_selection": actor is not None}
        return api_call(operation)

    @router.get("/projects/{nid}/studio")
    def project(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        def view(actor, scope, guard):
            result = service.project(nid, scope)
            for key, permission in (("can_mutate", "domain.write"), ("can_review", "domain.review")):
                try:
                    allowed = access(nid, x_session_token, x_branch_id, permission) == (actor, scope)
                except HTTPException as exc:
                    if exc.status_code != 403:
                        raise
                    allowed = False
                result["capabilities"][key] = allowed
            return result
        return invoke(nid, x_session_token, x_branch_id, "domain.read", view)

    @router.post("/projects/{nid}/studio/activate")
    def activate(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.activate(nid, scope, actor, guard))

    @router.get("/projects/{nid}/studio/preferences")
    def preferences(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.project(nid, scope)["preferences"])

    @router.put("/projects/{nid}/studio/preferences")
    def update_preferences(nid: str, body: WorkspacePreferencesUpdate,
                           x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.preferences(nid, scope, actor, body, guard))

    @router.get("/projects/{nid}/studio/assets")
    def assets(nid: str, include_deleted: bool = False,
               x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.list_assets(nid, scope, include_deleted=include_deleted))

    @router.post("/projects/{nid}/studio/assets", status_code=201)
    def upload(nid: str, body: ManualAssetImport,
               x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.import_asset(nid, scope, actor, body, guard))

    @router.get("/projects/{nid}/studio/assets/{aid}")
    def asset(nid: str, aid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.asset(nid, scope, aid))

    @router.put("/projects/{nid}/studio/assets/{aid}/lineage")
    def lineage(nid: str, aid: str, body: StudioLineageInput,
                x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.annotate(nid, scope, actor, aid, body, guard))

    @router.get("/projects/{nid}/studio/assets/{aid}/download")
    def download(nid: str, aid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        row, data = invoke(nid, x_session_token, x_branch_id, "domain.read",
                           lambda actor, scope, guard: service.download(nid, scope, aid, guard))
        # Safe generated ASCII fallback plus an RFC 5987 encoded filename.
        return Response(data, media_type=row["media_type"], headers={
            "Content-Disposition": f"attachment; filename=\"asset-{row['id']}\"; filename*=UTF-8''{quote(row['filename'], safe='')}",
            "X-Asset-SHA256": row["sha256"], "X-Asset-Version": str(row["version"])})

    @router.delete("/projects/{nid}/studio/assets/{aid}")
    def remove(nid: str, aid: str, expected_version: int = Query(ge=1),
               x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.lifecycle(nid, scope, aid, expected_version, guard=guard))

    @router.post("/projects/{nid}/studio/assets/{aid}/restore")
    def restore(nid: str, aid: str, body: AssetVersion,
                x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.lifecycle(nid, scope, aid, body.expected_version, restore=True, guard=guard))

    @router.get("/projects/{nid}/studio/storage")
    def storage(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.storage(nid, scope))

    @router.get("/projects/{nid}/studio/references")
    def references(nid: str, kind: Literal["ASSET", "CHAPTER", "SCREENPLAY"],
                   x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.relationships.references(nid, scope, kind))

    @router.get("/projects/{nid}/studio/relationships")
    def relationships(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.read",
                      lambda actor, scope, guard: service.relationships.graph(nid, scope))

    @router.post("/projects/{nid}/studio/assets/{aid}/relationships", status_code=201)
    def add_relationship(nid: str, aid: str, body: AssetRelationshipIn,
                         x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        permission = "domain.review" if body.type == "APPROVED_FOR" else "domain.write"
        return invoke(nid, x_session_token, x_branch_id, permission,
                      lambda actor, scope, guard: service.relationships.add(nid, scope, actor, aid, body, guard))

    @router.delete("/projects/{nid}/studio/assets/{aid}/relationships/{rid}")
    def remove_relationship(nid: str, aid: str, rid: str, expected_version: int = Query(ge=1),
                            x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        return invoke(nid, x_session_token, x_branch_id, "domain.write",
                      lambda actor, scope, guard: service.relationships.remove(nid, scope, actor, aid, rid, expected_version, guard))

    return router
