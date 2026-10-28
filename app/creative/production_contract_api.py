"""Read-only production catalog through the original Studio invocation guard."""
from fastapi import APIRouter, Header, HTTPException
from typing import Literal
from pydantic import model_validator

from ..experimental.production_lineage_api import PrivateProductionRoute
from .asset_query_cursor import signing_key_primitives_available
from .production_contracts import Name, ProductionCatalog, StrictContract, production_catalog


class CursorRuntimeCapability(StrictContract):
    key_primitives: Literal["PRESENT", "UNAVAILABLE"]
    end_to_end: Literal["NOT_VERIFIED", "UNSUPPORTED"]

    @model_validator(mode="after")
    def consistent_boundary(self):
        if (self.key_primitives, self.end_to_end) not in (("PRESENT", "NOT_VERIFIED"), ("UNAVAILABLE", "UNSUPPORTED")):
            raise ValueError("STUDIO_CURSOR_CAPABILITY_INCONSISTENT")
        return self


class AudioAssetHistoryCapability(StrictContract):
    version_history_read: Literal["UNAVAILABLE"] = "UNAVAILABLE"
    version_restore: Literal["UNAVAILABLE"] = "UNAVAILABLE"


class StudioRuntimeCapabilities(StrictContract):
    contract: Literal["studio-runtime-capabilities/1"] = "studio-runtime-capabilities/1"
    project_id: Name
    asset_query_cursor: CursorRuntimeCapability
    audio_asset_history: AudioAssetHistoryCapability = AudioAssetHistoryCapability()
    model_inference_acceptance: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"


def create_production_contract_router(service, invoke):
    """The parent supplies original access, flag, actor/scope/incarnation guards."""
    router = APIRouter(tags=["Studio Production Contracts V2"], route_class=PrivateProductionRoute)

    @router.get("/projects/{nid}/studio/production-contracts", response_model=ProductionCatalog)
    def contracts(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        def view(actor, scope, guard):
            guard()
            project = service.project(nid, scope)
            owner = project.get("project", {})
            if owner.get("id") != nid:
                raise HTTPException(403, {"code": "CREATIVE_PRODUCTION_OWNER_CHANGED"})
            if owner.get("entry_kind") != "NEUTRAL_STUDIO":
                raise HTTPException(409, {"code": "CREATIVE_STUDIO_ACTIVATION_REQUIRED"})
            result = production_catalog(nid, scope)
            guard()
            return result

        return invoke(nid, x_session_token, x_branch_id, "domain.read", view)

    @router.get("/projects/{nid}/studio/production-contracts/runtime", response_model=StudioRuntimeCapabilities)
    def runtime_capabilities(nid: str, x_session_token: str | None = Header(None), x_branch_id: str | None = Header(None)):
        def view(actor, scope, guard):
            guard()
            owner = service.project(nid, scope).get("project", {})
            if owner.get("id") != nid:
                raise HTTPException(403, {"code": "CREATIVE_PRODUCTION_OWNER_CHANGED"})
            if owner.get("entry_kind") != "NEUTRAL_STUDIO":
                raise HTTPException(409, {"code": "CREATIVE_STUDIO_ACTIVATION_REQUIRED"})
            present = signing_key_primitives_available()
            result = StudioRuntimeCapabilities(project_id=nid,
                asset_query_cursor=CursorRuntimeCapability(key_primitives="PRESENT" if present else "UNAVAILABLE",
                    end_to_end="NOT_VERIFIED" if present else "UNSUPPORTED"))
            guard()
            return result

        return invoke(nid, x_session_token, x_branch_id, "domain.read", view)

    return router
