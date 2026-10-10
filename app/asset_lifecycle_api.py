"""Scope-authorized asset recovery and approved lexical visual references."""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from .config import settings
from .services.asset_library_service import AssetIntegrityError, AssetIdempotencyConflict
from .services.v1_capability_service import CapabilityVersionConflict, VisualMemoryIn


class VisualReferenceApprovalIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)


def create_asset_lifecycle_router(assets, capabilities) -> APIRouter:
    router = APIRouter()

    def authorize(nid, session, branch, permission):
        # Import lazily so registering this domain router never introduces an
        # api/dependencies import cycle. These are server-owned authorization.
        from .api import _authorize_asset_project
        from .dependencies import trusted_session_resolver
        _authorize_asset_project(nid, session, branch, permission)
        if settings.enable_collaboration_runtime:
            return branch, trusted_session_resolver.resolve(session).actor_id
        return None, "local-author"

    def guard(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except CapabilityVersionConflict as exc:
            raise HTTPException(409, {"code": "VERSION_CONFLICT", "current": exc.current}) from exc
        except AssetIntegrityError as exc:
            raise HTTPException(409, {"code": "ASSET_INTEGRITY_FAILED", "message": str(exc)}) from exc
        except AssetIdempotencyConflict as exc:
            raise HTTPException(409, {"code": "ASSET_IDEMPOTENCY_CONFLICT", "message": str(exc)}) from exc
        except FileNotFoundError:
            raise HTTPException(404, {"code": "ASSET_OR_REFERENCE_NOT_FOUND"}) from None
        except (ValueError, TypeError) as exc:
            raise HTTPException(400, {"code": "INVALID_ASSET_REQUEST", "message": str(exc)}) from exc

    def owned(asset_id, nid, branch, *, include_deleted=False):
        item = assets.get(asset_id, branch_id=branch, include_deleted=include_deleted)
        if item.get("novel_id") != nid:
            raise FileNotFoundError(asset_id)
        return item

    @router.get("/novels/{nid}/asset-trash")
    def trash(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        branch, _ = authorize(nid, x_session_token, x_branch_id, "domain.read")
        guard(capabilities._require_novel, nid)
        items = [item for item in guard(assets.list, nid, branch_id=branch, include_deleted=True) if item.get("deleted_at")]
        return assets.public({"items": items, "total": len(items), "recoverable": True})

    @router.post("/novels/{nid}/assets/{asset_id}/restore")
    def restore(nid: str, asset_id: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        branch, _ = authorize(nid, x_session_token, x_branch_id, "domain.write")
        guard(owned, asset_id, nid, branch, include_deleted=True)
        return assets.public(guard(assets.restore, asset_id, branch_id=branch))

    @router.get("/novels/{nid}/assets/{asset_id}/references")
    def references(nid: str, asset_id: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        branch, _ = authorize(nid, x_session_token, x_branch_id, "domain.read")
        guard(owned, asset_id, nid, branch, include_deleted=True)
        return guard(capabilities.asset_references, asset_id, branch_id=branch, include_deleted=True)

    @router.get("/novels/{nid}/visual-references")
    def list_references(nid: str, asset_id: str | None = None,
                        x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        branch, _ = authorize(nid, x_session_token, x_branch_id, "domain.read")
        result = guard(capabilities.list_visual_memory, nid, branch_id=branch)
        if asset_id:
            guard(owned, asset_id, nid, branch)
            result["items"] = [item for item in result["items"] if item.get("asset_id") == asset_id]
            result["total"] = len(result["items"])
        return result

    @router.post("/novels/{nid}/visual-references", status_code=201)
    def create_reference(nid: str, body: VisualMemoryIn, x_session_token: str | None = Header(None),
                         x_branch_id: str | None = Header(None),
                         idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
        branch, _ = authorize(nid, x_session_token, x_branch_id, "domain.write")
        return guard(capabilities.create_visual_memory, nid, body, idempotency_key, branch_id=branch)

    @router.put("/novels/{nid}/visual-references/{memory_id}")
    def update_reference(nid: str, memory_id: str, body: VisualMemoryIn,
                         expected_version: int = Query(ge=1), x_session_token: str | None = Header(None),
                         x_branch_id: str | None = Header(None)):
        branch, _ = authorize(nid, x_session_token, x_branch_id, "domain.write")
        return guard(capabilities.update_visual_memory, nid, memory_id, body, expected_version, branch_id=branch)

    @router.post("/novels/{nid}/visual-references/{memory_id}/approve")
    def approve_reference(nid: str, memory_id: str, body: VisualReferenceApprovalIn,
                          x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        branch, actor = authorize(nid, x_session_token, x_branch_id, "domain.write")
        return guard(capabilities.approve_visual_memory, nid, memory_id, body.expected_version,
                     branch_id=branch, actor_id=actor)

    @router.get("/novels/{nid}/visual-reference-search")
    def search(nid: str, query: str = Query(default="", max_length=1000), entity_type: str | None = None,
               entity_id: str | None = None, limit: int = Query(default=20, ge=1, le=100),
               x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        branch, _ = authorize(nid, x_session_token, x_branch_id, "domain.read")
        return guard(capabilities.search_visual_memory, nid, query, entity_type=entity_type,
                     entity_id=entity_id, limit=limit, branch_id=branch)

    return router
