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
    gate: Literal["ENABLE_AUDIO_ASSET_HISTORY"] = "ENABLE_AUDIO_ASSET_HISTORY"
    enabled: bool = False
    capture: Literal["ENABLED", "UNAVAILABLE"] = "UNAVAILABLE"
    version_history_read: Literal["ENABLED", "UNAVAILABLE"] = "UNAVAILABLE"
    version_detail: Literal["ENABLED", "UNAVAILABLE"] = "UNAVAILABLE"
    version_download: Literal["ENABLED", "UNAVAILABLE"] = "UNAVAILABLE"
    explicit_migration: Literal["ENABLED", "UNAVAILABLE"] = "UNAVAILABLE"
    version_restore: Literal["ENABLED", "UNAVAILABLE"] = "UNAVAILABLE"
    record_contract: Literal["audio-asset-history/1"] = "audio-asset-history/1"
    restore_contract: Literal["audio-asset-history-restore/1"] = "audio-asset-history-restore/1"
    restore_semantics: Literal["NEW_TRACEABLE_CURRENT_VERSION_REVIEW_NOT_INHERITED"] = \
        "NEW_TRACEABLE_CURRENT_VERSION_REVIEW_NOT_INHERITED"
    legacy_reads_migrate: Literal[False] = False


class ProjectCapacityCapability(StrictContract):
    gate: Literal["ENABLE_PROJECT_CAPACITY_ADMISSION"] = "ENABLE_PROJECT_CAPACITY_ADMISSION"
    admission_enabled: bool = False
    ledger_contract: Literal["project-capacity/1"] = "project-capacity/1"
    measurement: Literal["LOGICAL_FILE_LENGTH_NOT_ALLOCATED"] = "LOGICAL_FILE_LENGTH_NOT_ALLOCATED"
    allocated_storage_bytes: Literal["UNKNOWN"] = "UNKNOWN"
    content_admission: Literal["FLAG_GATED", "UNAVAILABLE"] = "UNAVAILABLE"
    explicit_reconcile: Literal["EXPLICIT_OPERATION"] = "EXPLICIT_OPERATION"
    limit_adjustment: Literal["MANAGEMENT_LEASE_CAS_AUDIT"] = "MANAGEMENT_LEASE_CAS_AUDIT"
    unknown_objects: Literal["REPORT_ONLY_BLOCKS_NEW_RESERVATIONS"] = \
        "REPORT_ONLY_BLOCKS_NEW_RESERVATIONS"
    error_codes: tuple[str, ...] = (
        "PROJECT_CAPACITY_EXCEEDED", "PROJECT_CAPACITY_UNKNOWN_BLOCKED",
        "PROJECT_CAPACITY_VERSION_CONFLICT", "PROJECT_CAPACITY_NOT_RECONCILED",
        "PROJECT_CAPACITY_LEDGER_UNAVAILABLE", "PROJECT_CAPACITY_RESERVATION_UNKNOWN",
        "PROJECT_CAPACITY_COMMIT_EXCEEDS_RESERVATION")


class U16BatchCapability(StrictContract):
    gate_before_claim: Literal["IMPLEMENTED_FILE_SYNTHETIC_ONLY"] = "IMPLEMENTED_FILE_SYNTHETIC_ONLY"
    interrupted_running_claim: Literal["UNKNOWN_NO_REPLAY"] = "UNKNOWN_NO_REPLAY"
    real_postgres: Literal["NOT_RUN"] = "NOT_RUN"
    real_broker: Literal["NOT_RUN"] = "NOT_RUN"


class StudioRuntimeCapabilities(StrictContract):
    contract: Literal["studio-runtime-capabilities/1"] = "studio-runtime-capabilities/1"
    project_id: Name
    asset_query_cursor: CursorRuntimeCapability
    audio_asset_history: AudioAssetHistoryCapability = AudioAssetHistoryCapability()
    project_capacity: ProjectCapacityCapability = ProjectCapacityCapability()
    u16_batches: U16BatchCapability = U16BatchCapability()
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
            from ..config import settings
            audio_history = bool(settings.enable_audio_asset_history)
            capacity_admission = bool(settings.enable_project_capacity_admission)
            result = StudioRuntimeCapabilities(project_id=nid,
                asset_query_cursor=CursorRuntimeCapability(key_primitives="PRESENT" if present else "UNAVAILABLE",
                    end_to_end="NOT_VERIFIED" if present else "UNSUPPORTED"),
                audio_asset_history=AudioAssetHistoryCapability(
                    enabled=audio_history,
                    capture="ENABLED" if audio_history else "UNAVAILABLE",
                    version_history_read="ENABLED" if audio_history else "UNAVAILABLE",
                    version_detail="ENABLED" if audio_history else "UNAVAILABLE",
                    version_download="ENABLED" if audio_history else "UNAVAILABLE",
                    explicit_migration="ENABLED" if audio_history else "UNAVAILABLE",
                    version_restore="ENABLED" if audio_history else "UNAVAILABLE"),
                project_capacity=ProjectCapacityCapability(
                    admission_enabled=capacity_admission,
                    content_admission="FLAG_GATED" if capacity_admission else "UNAVAILABLE"))
            guard()
            return result

        return invoke(nid, x_session_token, x_branch_id, "domain.read", view)

    return router

