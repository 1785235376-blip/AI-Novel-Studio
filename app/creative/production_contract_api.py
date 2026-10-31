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


class CapabilityEnvironment(StrictContract):
    name: str
    status: Literal["NOT_RUN", "BLOCKED", "NOT_VERIFIED"]


class CapabilityItem(StrictContract):
    id: str
    title: str
    status: Literal["IMPLEMENTED_VERIFIED_SYNTHETIC", "PARTIAL", "UNAVAILABLE_BY_FLAG",
                    "NOT_IMPLEMENTED", "NOT_RUN", "NOT_VERIFIED", "BLOCKED",
                    "PRODUCT_DECISION", "UNKNOWN"]
    verification: Literal["FILE_SYNTHETIC", "HTTP_SYNTHETIC", "WINDOWS_SYNTHETIC",
                          "FILE_AND_HTTP_SYNTHETIC", "NOT_RUN", "NONE"]
    gate: str | None = None
    evidence: tuple[str, ...] = ()
    limits: tuple[str, ...] = ()


class CapabilityRegistry(StrictContract):
    contract: Literal["v2-capability-registry/1"] = "v2-capability-registry/1"
    real_environments: tuple[CapabilityEnvironment, ...]
    items: tuple[CapabilityItem, ...]


def build_capability_registry(*, settings) -> CapabilityRegistry:
    """Machine-readable V2.0 capability readiness; no environment is promoted by this object."""
    history = bool(settings.enable_audio_asset_history)
    capacity = bool(settings.enable_project_capacity_admission)
    environments = (
        CapabilityEnvironment(name="real_postgres", status="NOT_RUN"),
        CapabilityEnvironment(name="real_browser_e2e", status="NOT_RUN"),
        CapabilityEnvironment(name="real_model_gpu_provider", status="NOT_RUN"),
        CapabilityEnvironment(name="windows_packaged_desktop", status="NOT_RUN"),
        CapabilityEnvironment(name="hosted_ci", status="NOT_RUN"),
        CapabilityEnvironment(name="external_nle", status="NOT_RUN"),
        CapabilityEnvironment(name="publishing_review", status="BLOCKED"),
        CapabilityEnvironment(name="windows_acl_junction_probe", status="BLOCKED"),
    )
    items = (
        CapabilityItem(id="novel_chapter_bible", title="小说/章节/世界观/角色",
            status="IMPLEMENTED_VERIFIED_SYNTHETIC", verification="FILE_AND_HTTP_SYNTHETIC",
            evidence=("tests/test_phase4_*", "tests/test_phase5_*"),
            limits=("real_postgres:NOT_RUN", "real_browser:NOT_RUN")),
        CapabilityItem(id="screenplay_storyboard_shot", title="剧本/分镜/镜头与来源 pin",
            status="IMPLEMENTED_VERIFIED_SYNTHETIC", verification="FILE_AND_HTTP_SYNTHETIC",
            evidence=("tests/test_phase8_storyboard.py", "tests/test_phase8_shots.py"),
            limits=("real_media_chain:NOT_RUN",)),
        CapabilityItem(id="image_single_job_loop", title="IMAGE 单任务/候选/审核/采用/重开",
            status="IMPLEMENTED_VERIFIED_SYNTHETIC", verification="FILE_AND_HTTP_SYNTHETIC",
            evidence=("tests/test_studio_production_job_cost_contract.py", "tests/test_studio_frontend_alignment_v2.py"),
            limits=("real_model:NOT_RUN",)),
        CapabilityItem(id="video_execution", title="VIDEO 任务执行/候选/回填",
            status="PARTIAL", verification="FILE_AND_HTTP_SYNTHETIC",
            evidence=("tests/test_studio_video_synthetic_api.py", "tests/test_phase1_video_runtime.py"),
            limits=("real_model_provider:NOT_RUN", "real_clip_decode:NOT_RUN",
                    "late_duplicate_cancel_real_process:NOT_VERIFIED",
                    "historical_unified_limits_listed_VIDEO_execution_unsupported")),
        CapabilityItem(id="graph_local_branch", title="Graph 本地分支/受限图片叶重跑",
            status="IMPLEMENTED_VERIFIED_SYNTHETIC", verification="FILE_AND_HTTP_SYNTHETIC",
            evidence=("tests/test_graph_binary_branch_actual.py", "tests/test_graph_image_leaf_rerun.py"),
            limits=("only_bounded_local_branches_verified",)),
        CapabilityItem(id="graph_multi_node_recovery", title="Graph 多节点产物/失败恢复",
            status="PARTIAL", verification="FILE_AND_HTTP_SYNTHETIC",
            evidence=("tests/test_graph_local_branch_persistence.py", "tests/test_graph_source_guard_regression.py",
                      "tests/test_graph_multinode_media_chain.py"),
            limits=("multi_level_media_chain:FILE_SYNTHETIC_VERIFIED",
                    "full_multi_node_unknown_recovery:NOT_VERIFIED", "real_model:NOT_RUN")),
        CapabilityItem(id="audio_production", title="音频请求/执行/候选/采用",
            status="PARTIAL", verification="FILE_AND_HTTP_SYNTHETIC",
            evidence=("tests/test_audio_production_api.py", "tests/test_audio_providers.py"),
            limits=("real_provider:NOT_RUN", "canvas_return_target_semantics:PRODUCT_DECISION")),
        CapabilityItem(id="audio_asset_history", title="音频不可变历史/显式迁移/显式恢复",
            status="IMPLEMENTED_VERIFIED_SYNTHETIC" if history else "UNAVAILABLE_BY_FLAG",
            verification="FILE_AND_HTTP_SYNTHETIC",
            gate="ENABLE_AUDIO_ASSET_HISTORY",
            evidence=("tests/test_audio_asset_history_capture.py", "tests/test_audio_asset_history_restore.py",
                      "tests/test_audio_history_capacity_accounting.py"),
            limits=("real_postgres_crash_windows:NOT_RUN", "legacy_assets_require_explicit_migration",
                    "review_inherited:false_by_design")),
        CapabilityItem(id="timeline_edit", title="Timeline 多轨/音量/编辑",
            status="PARTIAL", verification="FILE_SYNTHETIC",
            evidence=("tests/test_studio_timeline_multitrack_real.py", "tests/test_studio_timeline_process_failures.py"),
            limits=("full_multitrack_formats:NOT_RUN", "real_process_restart:NOT_VERIFIED")),
        CapabilityItem(id="timeline_render_export", title="Timeline 渲染/混音/媒体导出",
            status="PARTIAL", verification="FILE_SYNTHETIC",
            evidence=("tests/test_studio_timeline_multitrack_real.py",
                      "tests/test_studio_timeline_audio_profiles.py"),
            limits=("real_nle:NOT_RUN", "all_codecs_and_recovery:NOT_VERIFIED",
                    "audio_profiles:PCM16_PCM24_SYNTHETIC")),
        CapabilityItem(id="export_formats", title="TXT/Markdown/JSON/DOCX/PDF 导出",
            status="IMPLEMENTED_VERIFIED_SYNTHETIC", verification="FILE_AND_HTTP_SYNTHETIC",
            evidence=("tests/test_export_jobs.py", "tests/test_docx_export.py", "tests/test_pdf_export.py"),
            limits=("cross_machine_exactly_once:NOT_CLAIMED",)),
        CapabilityItem(id="taskcenter_query", title="TaskCenter 分页/回执/期限",
            status="IMPLEMENTED_VERIFIED_SYNTHETIC", verification="FILE_AND_HTTP_SYNTHETIC",
            evidence=("tests/test_taskcenter_reader_receipts.py", "tests/test_taskcenter_return_deadline.py"),
            limits=("mixed_scope_bounded_to_semantic_import_and_exports",
                    "f37_warm409_root_cause:UNKNOWN")),
        CapabilityItem(id="asset_query_budget", title="资产查询分页/预算/Windows 游标",
            status="IMPLEMENTED_VERIFIED_SYNTHETIC", verification="WINDOWS_SYNTHETIC",
            evidence=("tests/test_asset_query_cursor_windows_key.py", "tests/test_studio_asset_usage_budget_guards.py"),
            limits=("windows_desktop_end_to_end:NOT_VERIFIED",)),
        CapabilityItem(id="project_capacity_ledger", title="项目容量账本/预留/对账/调额/admission",
            status="PARTIAL" if capacity else "UNAVAILABLE_BY_FLAG",
            verification="FILE_AND_HTTP_SYNTHETIC",
            gate="ENABLE_PROJECT_CAPACITY_ADMISSION",
            evidence=("tests/test_project_capacity_ledger.py", "tests/test_project_capacity_create_coverage.py",
                      "tests/test_project_capacity_admission_manual_import.py"),
            limits=("non_asset_project_writers:NOT_CONNECTED", "startup_reconcile_gate:IMPLEMENTED_FOR_HISTORY_WRITES_ONLY",
                    "approval_revocation_races:NOT_VERIFIED", "real_postgres:NOT_RUN")),
        CapabilityItem(id="project_identity_tombstones", title="项目 incarnation/删除墓碑",
            status="IMPLEMENTED_VERIFIED_SYNTHETIC", verification="FILE_AND_HTTP_SYNTHETIC",
            evidence=("tests/test_project_tombstones_and_incarnation.py",),
            limits=("real_postgres:NOT_RUN", "packaged_desktop:NOT_RUN")),
        CapabilityItem(id="studio_task_cost", title="Studio 任务成本",
            status="PARTIAL", verification="NONE",
            evidence=("tests/test_studio_production_job_cost_contract.py",),
            limits=("explicit_unknown_only", "trusted_provider_usage_price_linkage:NOT_IMPLEMENTED")),
        CapabilityItem(id="audio_canvas_return", title="音频 canvas_return 目标/回写",
            status="PRODUCT_DECISION", verification="NONE",
            evidence=("docs/delivery/STUDIO_V2_BACKEND_COMPLETION_LEDGER_20261028.md",),
            limits=("target_permission_review_semantics:PRODUCT_DECISION",)),
        CapabilityItem(id="real_provider_inference", title="真实 Provider/模型推理",
            status="NOT_RUN", verification="NOT_RUN",
            limits=("no_authorization_or_real_model_executed",)),
        CapabilityItem(id="postgres_backend", title="真实 PostgreSQL 后端/迁移/备份恢复",
            status="NOT_RUN", verification="NOT_RUN",
            evidence=("tests/test_backend_mode_harness.py",),
            limits=("migrations_018_020_real_run:NOT_RUN", "backup_restore_real_run:NOT_RUN")),
        CapabilityItem(id="browser_e2e", title="真实浏览器前后端 E2E",
            status="NOT_RUN", verification="NOT_RUN"),
        CapabilityItem(id="windows_packaged_desktop", title="Windows 打包桌面",
            status="NOT_RUN", verification="NOT_RUN"),
        CapabilityItem(id="hosted_ci", title="托管 CI",
            status="NOT_RUN", verification="NOT_RUN"),
        CapabilityItem(id="external_nle", title="外部 NLE/平台",
            status="NOT_RUN", verification="NOT_RUN"),
        CapabilityItem(id="publishing_review", title="PUBLISHING 独立审阅",
            status="BLOCKED", verification="NONE",
            limits=("blocked_by_policy_not_retried",)),
        CapabilityItem(id="windows_acl_junction_probe", title="Windows ACL/junction 探测",
            status="BLOCKED", verification="NONE",
            limits=("blocked_by_policy_not_retried",)),
        CapabilityItem(id="f37_warm409_root_cause", title="F37 37 次拒绝 / strict-warm 409 根因",
            status="UNKNOWN", verification="NONE",
            limits=("root_cause_unknown_not_closed",)),
        CapabilityItem(id="historical_product_branches", title="历史产品分支 #36–#49/#26",
            status="PRODUCT_DECISION", verification="NONE",
            limits=("not_merged_into_main", "would_regress_verified_v2")),
    )
    return CapabilityRegistry(real_environments=environments, items=items)


class StudioRuntimeCapabilities(StrictContract):
    contract: Literal["studio-runtime-capabilities/1"] = "studio-runtime-capabilities/1"
    project_id: Name
    asset_query_cursor: CursorRuntimeCapability
    audio_asset_history: AudioAssetHistoryCapability = AudioAssetHistoryCapability()
    project_capacity: ProjectCapacityCapability = ProjectCapacityCapability()
    u16_batches: U16BatchCapability = U16BatchCapability()
    model_inference_acceptance: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"
    capability_registry: CapabilityRegistry = CapabilityRegistry(real_environments=(), items=())


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
                    content_admission="FLAG_GATED" if capacity_admission else "UNAVAILABLE"),
                capability_registry=build_capability_registry(settings=settings))
            guard()
            return result

        return invoke(nid, x_session_token, x_branch_id, "domain.read", view)

    return router

