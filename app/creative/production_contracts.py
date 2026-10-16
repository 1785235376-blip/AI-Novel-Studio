"""Read-only M4-M9 operation contracts over existing execution owners.

This catalog neither imports media owners nor resolves models, credentials,
hardware, processes or provider availability. An action describes an existing
API; it is never a dispatch target or a permission grant.
"""
from __future__ import annotations

from fractions import Fraction
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, JsonValue, model_validator

CONTRACT = "studio-production-operation-contracts/1"
EVIDENCE = "NOT_EVALUATED_BY_THIS_ENDPOINT"
Milestone = Literal["M4", "M5", "M6", "M7", "M8", "M9"]
OperationId = Literal[
    "m4.text.generate", "m5.image.generate", "m5.image.edit", "m5.image.t2i", "m5.image.i2i", "m5.image.cutout",
    "m6.director.propose", "m6.director.model", "m6.storyboard.derive", "m7.video.plan",
    "m7.video.generate", "m7.video.t2v", "m7.video.i2v", "m7.video.v2v", "m8.audio.speech",
    "m8.audio.import", "m8.audio.music", "m8.audio.effects", "m8.audio.trim",
    "m9.video.assemble", "m9.timeline.exchange", "m9.subtitle.edit", "m9.timeline.multitrack",
]
ACCEPTANCE_SEQUENCE = ("M4", "M5", "M6", "M7", "M8", "M9")
PUBLIC_SCOPE_KEYS = frozenset({"mode", "novel_id", "workspace_id", "project_id", "storyline_id", "branch_id"})
Requirement = Annotated[str, Field(min_length=1, max_length=640, strict=True)]
Requirements = Annotated[list[Requirement], Field(min_length=1, max_length=16)]


def _nonempty_identity(value: str) -> str:
    if not value.strip() or any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError("PRODUCTION_IDENTITY_INVALID")
    return value


Name = Annotated[str, Field(min_length=1, max_length=240, strict=True), AfterValidator(_nonempty_identity)]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$", strict=True)]
MAX_TIMING_TICK = 3_600_000_000
# The original OTIO exchange limits each represented track's duration to one day.
# This is a bounded shape limit, not measured source duration or an owner grant.
MAX_TIMELINE_SECONDS = 86_400


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class ProductionSourceSnapshot(StrictContract):
    """Reference only; ASSET requires asset_kind and other source kinds forbid it."""
    id: Name
    kind: Literal["CHAPTER", "CREATIVE_DOCUMENT", "ASSET", "TIMELINE", "CAPTION"]
    version: int = Field(ge=1, strict=True)
    digest: Digest
    asset_kind: Literal["text", "image", "video", "audio"] | None = Field(default=None,
        description="ASSET 时必须提供原资产 kind；其他来源种类不得填写。此值仍须由原服务重新校验。")
    reference_only: Literal[True] = True

    @model_validator(mode="after")
    def asset_kind_binding(self):
        if (self.kind == "ASSET") != (self.asset_kind is not None):
            raise ValueError("PRODUCTION_SOURCE_ASSET_KIND_MISMATCH")
        return self


class ProductionProviderReference(StrictContract):
    route_digest: Digest
    provider_id: Name
    model_id: Name
    workflow_digest: Digest | None = None
    original_owner_revalidation_required: Literal[True] = True
    automatic_fallback: Literal[False] = False


class ProductionRightsRequirements(StrictContract):
    license_note: str = Field(default="", max_length=2000, strict=True)
    license_reference_digest: Digest | None = None
    consent_receipt_digest: Digest | None = None
    verification: Literal["ORIGINAL_OWNER_REQUIRED"] = "ORIGINAL_OWNER_REQUIRED"
    caller_claim_is_authority: Literal[False] = False


class ProductionTimingRequirements(StrictContract):
    """Rational placement; end ticks are bounded, interval duration is at most one day."""
    timebase_numerator: int = Field(ge=1, le=1_000_000, strict=True)
    timebase_denominator: int = Field(ge=1, le=1_000_000, strict=True)
    start_tick: int = Field(ge=0, le=MAX_TIMING_TICK, strict=True)
    duration_ticks: int = Field(ge=1, le=MAX_TIMING_TICK, strict=True)
    playback_rate: float = Field(default=1.0, gt=0, le=8, strict=True)

    def interval_seconds(self) -> tuple[Fraction, Fraction]:
        """Timeline placement, not a measured source trim or playback duration."""
        tick_seconds = Fraction(self.timebase_denominator, self.timebase_numerator)
        return self.start_tick * tick_seconds, (self.start_tick + self.duration_ticks) * tick_seconds

    @model_validator(mode="after")
    def bounded_interval(self):
        if self.start_tick + self.duration_ticks > MAX_TIMING_TICK:
            raise ValueError("PRODUCTION_TIMING_END_TICK_LIMIT")
        if Fraction(self.duration_ticks * self.timebase_denominator, self.timebase_numerator) > MAX_TIMELINE_SECONDS:
            raise ValueError("PRODUCTION_TIMING_DURATION_RANGE")
        return self


class ProductionTrackRequirements(StrictContract):
    """VIDEO/AUDIO bind same-kind assets; CAPTION binds a caption document, gain is audio-only."""
    id: Name
    kind: Literal["VIDEO", "AUDIO", "CAPTION"]
    order: int = Field(ge=0, le=7, strict=True)
    source_snapshot: ProductionSourceSnapshot
    timing: ProductionTimingRequirements
    muted: bool = False
    gain_db: float = Field(default=0.0, ge=-60, le=12, strict=True)
    owner_adapter_required: Literal[True] = True

    @model_validator(mode="after")
    def source_and_track_kind(self):
        source = self.source_snapshot
        if self.kind == "CAPTION":
            compatible = source.kind == "CAPTION"
        else:
            compatible = source.kind == "ASSET" and source.asset_kind == self.kind.lower()
        if not compatible:
            raise ValueError("PRODUCTION_TRACK_SOURCE_KIND_MISMATCH")
        if self.kind != "AUDIO" and self.gain_db != 0.0:
            raise ValueError("PRODUCTION_TRACK_GAIN_REQUIRES_AUDIO")
        return self


def _validate_composition(sources, tracks, timing):
    """Check only internal references; never query or authorize the source owner."""
    source_map = {}
    for source in sources:
        key = (source.kind, source.id)
        if key in source_map:
            if source != source_map[key]:
                raise ValueError("PRODUCTION_SOURCE_SNAPSHOT_CONFLICT")
            raise ValueError("PRODUCTION_SOURCE_SNAPSHOT_DUPLICATE")
        source_map[key] = source
    seen_ids, seen_orders = set(), set()
    for track in tracks:
        if track.id in seen_ids:
            raise ValueError("PRODUCTION_TRACK_ID_DUPLICATE")
        if track.order in seen_orders:
            raise ValueError("PRODUCTION_TRACK_ORDER_DUPLICATE")
        seen_ids.add(track.id)
        seen_orders.add(track.order)
        source = track.source_snapshot
        if source_map.get((source.kind, source.id)) != source:
            raise ValueError("PRODUCTION_TRACK_SOURCE_SNAPSHOT_MISMATCH")
        if timing is not None:
            start, end = timing.interval_seconds()
            track_start, track_end = track.timing.interval_seconds()
            if track_start < start or track_end > end:
                raise ValueError("PRODUCTION_TRACK_OUTSIDE_TIMELINE")


class ProductionIntentParameters(StrictContract):
    """Finite future interface fields; these do not widen legacy input models."""
    prompt: str = Field(default="", max_length=16_000, strict=True)
    negative_prompt: str = Field(default="", max_length=8000, strict=True)
    seed: int | None = Field(default=None, ge=0, le=2**32 - 1, strict=True)
    width: int | None = Field(default=None, ge=16, le=7680, strict=True)
    height: int | None = Field(default=None, ge=16, le=7680, strict=True)
    frame_rate: int | None = Field(default=None, ge=1, le=120, strict=True)
    duration_seconds: int | None = Field(default=None, ge=1, le=600, strict=True)
    strength: float | None = Field(default=None, ge=0, le=1, strict=True)
    voice_id: Name | None = None
    speech_rate: float | None = Field(default=None, ge=0.25, le=4, strict=True)
    output_profile: Name | None = None

    @model_validator(mode="after")
    def dimensions_are_paired(self):
        if (self.width is None) != (self.height is None):
            raise ValueError("PRODUCTION_DIMENSIONS_PAIR_REQUIRED")
        return self


class ProductionOperationIntent(StrictContract):
    """Proposal only; unique sources/tracks and exact source/placement consistency are required."""
    operation_id: OperationId
    request_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$", strict=True)
    source_snapshots: list[ProductionSourceSnapshot] = Field(max_length=32)
    provider_reference: ProductionProviderReference | None = None
    parameters: ProductionIntentParameters
    rights: ProductionRightsRequirements
    timing: ProductionTimingRequirements | None = None
    tracks: list[ProductionTrackRequirements] = Field(default_factory=list, max_length=8)
    proposal_only: Literal[True] = True
    execution_authority: Literal[False] = False

    @model_validator(mode="after")
    def coherent_sources_and_tracks(self):
        _validate_composition(self.source_snapshots, self.tracks, self.timing)
        return self


class ProductionMediaResult(StrictContract):
    """Future receipt shape; sources/tracks, MIME/size and declared job/review references must agree."""
    output_id: Name
    output_kind: Literal["text", "image", "video", "audio", "timeline", "caption"]
    version: int = Field(ge=1, strict=True)
    digest: Digest
    source_snapshots: list[ProductionSourceSnapshot] = Field(max_length=32)
    job_id: Name | None = None
    owner_receipt_digest: Digest | None = None
    execution_mode: Literal["ORIGINAL_OWNER_REAL", "MANUAL", "STRUCTURED_DERIVATION"]
    review_state: Literal["HUMAN_REVIEW_REQUIRED", "ORIGINAL_OWNER_REVIEWED"] = "HUMAN_REVIEW_REQUIRED"
    rights: ProductionRightsRequirements
    timing: ProductionTimingRequirements | None = None
    tracks: list[ProductionTrackRequirements] = Field(default_factory=list, max_length=8)
    media_type: str | None = Field(default=None, pattern=r"^[a-z0-9.+-]+/[a-z0-9.+-]+$", max_length=120)
    byte_count: int | None = Field(default=None, ge=1, le=2_147_483_648, strict=True)
    execution_authority: Literal[False] = False

    @model_validator(mode="after")
    def original_completion_binding(self):
        _validate_composition(self.source_snapshots, self.tracks, self.timing)
        if self.execution_mode == "ORIGINAL_OWNER_REAL" and (not self.job_id or not self.owner_receipt_digest):
            raise ValueError("ORIGINAL_JOB_AND_RECEIPT_REQUIRED")
        if self.job_id is not None and self.owner_receipt_digest is None:
            raise ValueError("PRODUCTION_JOB_RECEIPT_REQUIRED")
        if self.review_state == "ORIGINAL_OWNER_REVIEWED" and self.owner_receipt_digest is None:
            raise ValueError("PRODUCTION_REVIEW_RECEIPT_REQUIRED")
        if self.execution_mode == "STRUCTURED_DERIVATION" and not self.source_snapshots:
            raise ValueError("PRODUCTION_DERIVATION_SOURCE_REQUIRED")
        if (self.media_type is None) != (self.byte_count is None):
            raise ValueError("PRODUCTION_MEDIA_METADATA_PAIR_REQUIRED")
        if self.media_type is not None:
            allowed = {
                "text": self.media_type.startswith("text/") or self.media_type == "application/json",
                "image": self.media_type.startswith("image/"),
                "video": self.media_type.startswith("video/"),
                "audio": self.media_type.startswith("audio/"),
                "timeline": self.media_type == "application/vnd.opentimelineio+json",
                "caption": self.media_type in {"text/vtt", "application/x-subrip"},
            }
            if not allowed[self.output_kind]:
                raise ValueError("PRODUCTION_OUTPUT_MEDIA_KIND_MISMATCH")
        if self.output_kind in {"text", "image"} and self.tracks:
            raise ValueError("PRODUCTION_OUTPUT_KIND_CANNOT_HAVE_TRACKS")
        if self.output_kind == "audio" and any(track.kind != "AUDIO" for track in self.tracks):
            raise ValueError("PRODUCTION_AUDIO_OUTPUT_TRACK_KIND_MISMATCH")
        if self.output_kind == "caption" and any(track.kind != "CAPTION" for track in self.tracks):
            raise ValueError("PRODUCTION_CAPTION_OUTPUT_TRACK_KIND_MISMATCH")
        return self


class ProductionInterfaceReferences(StrictContract):
    source_snapshot: Literal["source-snapshot/1"] = "source-snapshot/1"
    intent: Literal["operation-intent/1"] = "operation-intent/1"
    result: Literal["media-result/1"] = "media-result/1"
    rights: Literal["rights-requirements/1"] = "rights-requirements/1"
    timing: Literal["timing-requirements/1"] = "timing-requirements/1"
    tracks: Literal["track-requirements/1"] = "track-requirements/1"


INTERFACE_MODELS = (
    ("source-snapshot/1", ProductionSourceSnapshot),
    ("provider-reference/1", ProductionProviderReference),
    ("rights-requirements/1", ProductionRightsRequirements),
    ("timing-requirements/1", ProductionTimingRequirements),
    ("track-requirements/1", ProductionTrackRequirements),
    ("operation-intent/1", ProductionOperationIntent),
    ("media-result/1", ProductionMediaResult),
)


class ProductionOwner(StrictContract):
    module: str = Field(pattern=r"^app(?:\.[a-z_][a-z0-9_]*)+$", max_length=160)
    class_name: str = Field(pattern=r"^[A-Z][A-Za-z0-9_]*$", max_length=120)
    methods: list[Annotated[str, Field(pattern=r"^[a-z_][a-z0-9_]*$", max_length=80)]] = Field(min_length=1, max_length=12)


class ProductionAction(StrictContract):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$", max_length=64)
    method: Literal["GET", "POST", "PUT", "DELETE"]
    path: str = Field(pattern=r"^/api/", max_length=400)
    permission: Literal["domain.read", "domain.write", "domain.review"]
    input_schema: Name | None
    owner_method: str = Field(pattern=r"^app(?:\.[A-Za-z_][A-Za-z0-9_]*)+$", max_length=260)
    requires_original_host_session: bool
    execution_grant: Literal[False] = False
    conditions: Requirements


class ProductionOperation(StrictContract):
    id: OperationId
    milestone: Milestone
    title: str = Field(min_length=1, max_length=120)
    capability_status: Literal["EXISTING_OWNER_CONTRACT", "RESERVED_INTERFACE"]
    acceptance_status: Literal["LOCAL_REQUIRED"] = "LOCAL_REQUIRED"
    acceptance_evidence: Literal["NOT_EVALUATED_BY_THIS_ENDPOINT"] = EVIDENCE
    execution_available: Literal[False] = False
    blocked_reasons: list[Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]*$", max_length=120)]] = Field(min_length=1, max_length=12)
    owner: ProductionOwner | None
    actions: list[ProductionAction] = Field(max_length=16)
    interface_contracts: ProductionInterfaceReferences = Field(default_factory=ProductionInterfaceReferences)
    input_requirements: Requirements
    source_requirements: Requirements
    output_requirements: Requirements
    review_requirements: Requirements
    limitations: Requirements

    @model_validator(mode="after")
    def truthful_boundary(self):
        if len(self.actions) > (16 if self.id == "m9.timeline.multitrack" else 12):
            raise ValueError("PRODUCTION_OPERATION_ACTION_LIMIT")
        if not self.id.startswith(self.milestone.lower() + "."):
            raise ValueError("PRODUCTION_OPERATION_MILESTONE_MISMATCH")
        if len({action.id for action in self.actions}) != len(self.actions):
            raise ValueError("PRODUCTION_OPERATION_DUPLICATE_ACTION")
        if self.capability_status == "RESERVED_INTERFACE":
            if self.owner is not None or self.actions:
                raise ValueError("RESERVED_OPERATION_CANNOT_ADVERTISE_OWNER_OR_ROUTE")
        elif self.owner is None or not self.actions:
            raise ValueError("EXISTING_OPERATION_REQUIRES_ACTUAL_OWNER_AND_ACTION")
        return self


class ProductionCatalog(StrictContract):
    contract: Literal["studio-production-operation-contracts/1"] = CONTRACT
    schema_version: Annotated[int, Field(strict=True, ge=1, le=1)] = 1
    project_id: Name
    scope: dict[str, str | None]
    studio_entry_kind: Literal["NEUTRAL_STUDIO"] = "NEUTRAL_STUDIO"
    advisory_only: Literal[True] = True
    execution_authority: Literal[False] = False
    acceptance_sequence: list[Milestone]
    acceptance_evidence: Literal["NOT_EVALUATED_BY_THIS_ENDPOINT"] = EVIDENCE
    interface_schemas: dict[str, dict[str, JsonValue]]
    operations: list[ProductionOperation] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def current_public_context(self):
        if (set(self.scope) - PUBLIC_SCOPE_KEYS or self.scope.get("novel_id") != self.project_id
                or self.scope.get("mode") not in {"local", "collaboration"}
                or any(value is not None and not 1 <= len(value) <= 240 for value in self.scope.values())):
            raise ValueError("PRODUCTION_CATALOG_SCOPE_INVALID")
        if self.scope["mode"] == "collaboration" and any(not self.scope.get(key)
                for key in ("workspace_id", "storyline_id", "branch_id")):
            raise ValueError("PRODUCTION_CATALOG_COLLABORATION_SCOPE_INCOMPLETE")
        if tuple(self.acceptance_sequence) != ACCEPTANCE_SEQUENCE:
            raise ValueError("PRODUCTION_ACCEPTANCE_SEQUENCE_CHANGED")
        if len({operation.id for operation in self.operations}) != len(self.operations):
            raise ValueError("PRODUCTION_CATALOG_DUPLICATE_OPERATION")
        if set(self.interface_schemas) != {name for name, _ in INTERFACE_MODELS}:
            raise ValueError("PRODUCTION_INTERFACE_SCHEMAS_CHANGED")
        return self


def _owner(module, class_name, *methods):
    return ProductionOwner(module=module, class_name=class_name, methods=list(methods))


def _action(action_id, method, path, owner_method, schema=None, *, permission="domain.write", host=False, extra_conditions=()):
    return ProductionAction(id=action_id, method=method, path="/api" + path,
        permission=permission, input_schema=schema, owner_method=owner_method,
        requires_original_host_session=host,
        conditions=["须继续通过原 " + permission + " 权限校验，项目和分支范围必须保持当前有效。",
            "该动作须由原可信 DesktopHost 会话授权。" if host else
            "沿用原接口权限；此处的说明不能授予打包版 V2 会话或执行权限。", *extra_conditions])


def _existing(operation_id, title, owner, actions, *, inputs, sources, outputs, review, limitations, blockers=()):
    actions = [ProductionAction.model_validate({**action.model_dump(),
        "conditions": [*action.conditions, *sources]}) for action in actions]
    return ProductionOperation(id=operation_id, milestone=operation_id[:2].upper(), title=title,
        capability_status="EXISTING_OWNER_CONTRACT", owner=owner, actions=actions,
        blocked_reasons=[*blockers, "WINDOWS_PRODUCT_ACCEPTANCE_LOCAL_REQUIRED"],
        input_requirements=list(inputs), source_requirements=list(sources), output_requirements=list(outputs),
        review_requirements=list(review), limitations=list(limitations))


def _reserved(operation_id, title, *, inputs, sources, outputs, blocker):
    return ProductionOperation(id=operation_id, milestone=operation_id[:2].upper(), title=title,
        capability_status="RESERVED_INTERFACE", owner=None, actions=[],
        blocked_reasons=[blocker, "ORIGINAL_OWNER_ADAPTER_REQUIRED", "WINDOWS_PRODUCT_ACCEPTANCE_LOCAL_REQUIRED"],
        input_requirements=list(inputs), source_requirements=list(sources), output_requirements=list(outputs),
        review_requirements=["后续必须取得原执行服务的结果回执并由人明确复审；读取本目录不进行复审。"],
        limitations=["这里只定义预留接口，尚未接入执行端点、作业、模型服务或渲染器。",
            "此记录不能证明模型已配置、来源已校验、执行已启用或产品验收已通过。"])


def _operations():
    graph = "/projects/{nid}/studio/graph-runs/{rid}"
    creative = "/novels/{nid}/experimental/creative"
    images = "/novels/{nid}/image-jobs"
    motion = "/novels/{nid}/screenplays/{screenplay_id}/motion-tasks/{task_id}"
    audio = "/novels/{nid}/audiobook"
    timeline = "/novels/{nid}/experimental/timeline-exchange"
    subtitle = "/novels/{nid}/experimental/subtitle-timeline/records"
    local_boundary = "历史媒体接口保留原授权与外发审查，不能用来绕过打包版 V2 的可信登录。"
    media_output = "原执行服务须校验实际媒体文件、保存生成来源并通过 AssetLibrary 入库；仅有模型服务状态不足以确认结果。"
    binding = "须重新核对项目、分支、操作者范围和原服务保存的来源证据；客户端提交的结果不构成执行授权。"
    reserved_sources = ["须绑定原项目／分支中的来源 ID、版本和摘要；执行前还须接入可原子校验输入的原服务适配器。"]
    reserved_outputs = ["须保存原作业的持久终态回执、已校验媒体的资产版本／摘要和人工复审记录；不能填入模拟结果。"]
    operations = [
        _existing("m4.text.generate", "文本生成、资产归档与复审",
            _owner("app.creative.ai_execution", "CreativeGraphNodeRuntime", "preview", "dispatch", "refresh"), [
                _action("preview", "POST", graph + "/model/preview", "app.creative.ai_execution.CreativeGraphNodeRuntime.preview", "ModelPreview", host=True),
                _action("dispatch", "POST", graph + "/model/dispatch", "app.creative.ai_execution.CreativeGraphNodeRuntime.dispatch", "ModelDispatch", host=True),
                _action("refresh", "POST", graph + "/model/refresh", "app.creative.ai_execution.CreativeGraphNodeRuntime.refresh", "ModelRefresh", host=True),
                _action("approve", "POST", graph + "/approve", "app.creative.graph.CreativeGraphService.action", "GraphAction", permission="domain.review", host=True),
                _action("reject", "POST", graph + "/reject", "app.creative.graph.CreativeGraphService.action", "GraphAction", permission="domain.review", host=True)],
            inputs=["使用一个 schema_version=2 的 text_generate 节点，限制指令长度和输出 token 数，并选择原本地 TEXT 路线。", "创建运行须提供 expected_graph_version 与已审查的 preflight 摘要；预览、执行、刷新须提供 expected_version。"],
            sources=["原流程版本、定义摘要、操作者范围、已准备请求摘要和 reviewed_preview_digest 必须贯穿两次执行校验。"],
            outputs=["由原 JobManager／Broker 完成结算并保存文本回执；archive_result 请求原 GraphTextAssets 归档，客户端不能直接发布结果。"],
            review=["原作业持久完成且所需资产归档后才能人工复审；批准／拒绝不能替代终态回调完成。"],
            limitations=["此流程只执行本地文本；发现模型、协议模拟或标注 real 的响应均不能证明 GPU／产品验收。", "不增加自动重试、云端回退、凭据回退或媒体执行。"]),
        _existing("m5.image.generate", "图像生成（原接口）",
            _owner("app.services.image_job_service", "ImageJobService", "create", "execute", "accept", "transition"), [
                _action("create", "POST", images, "app.services.image_job_service.ImageJobService.create", "ImageGenerateIn"),
                _action("execute", "POST", images + "/{job_id}/execute", "app.services.image_job_service.ImageJobService.execute"),
                _action("accept", "POST", images + "/{job_id}/accept", "app.services.image_job_service.ImageJobService.accept"),
                _action("cancel", "POST", images + "/{job_id}/cancel", "app.services.image_job_service.ImageJobService.transition"),
                _action("retry", "POST", images + "/{job_id}/retry", "app.services.image_job_service.ImageJobService.transition")],
            inputs=["原 ImageGenerateIn 接收模型、提示词、可选来源 ID 和参数，并保留原外发审查；支持 Idempotency-Key。"],
            sources=[binding, "历史创建／执行／接受接口没有 expected_version；同次 execution_token 与请求绑定不能替代 V2 来源版本校验。"],
            outputs=[media_output], review=["原 accept 核对同一次执行，下载并校验真实图片后批准原资产；权限是 domain.write，不能视为文本流程的复审回执。"],
            limitations=[local_boundary, "V2 图像节点执行以及来源到资产的原子适配器尚未接入。"], blockers=["V2_GRAPH_IMAGE_EXECUTION_NOT_ENABLED"]),
        _existing("m5.image.edit", "图像编辑（原接口）",
            _owner("app.services.image_job_service", "ImageJobService", "create", "execute", "accept"), [
                _action("create", "POST", images, "app.services.image_job_service.ImageJobService.create", "ImageEditIn"),
                _action("execute", "POST", images + "/{job_id}/execute", "app.services.image_job_service.ImageJobService.execute"),
                _action("accept", "POST", images + "/{job_id}/accept", "app.services.image_job_service.ImageJobService.accept")],
            inputs=["ImageEditIn 在原图像请求中增加 images；继续检查媒体路径和模型服务的编辑能力。"],
            sources=[binding, "必须绑定输入图片和同次执行；历史端点没有客户端 expected_version 或 V2 节点适配器。"],
            outputs=[media_output], review=["真实编辑完成后使用原 accept 动作复核；本目录不会加载或提交参考图。"],
            limitations=[local_boundary, "历史编辑接口不表示 V2 图生图节点已经可执行。"], blockers=["V2_GRAPH_IMAGE_EXECUTION_NOT_ENABLED"]),
        _reserved("m5.image.t2i", "文生图节点（预留）", inputs=["限制提示词、负面提示词、尺寸和 seed；须保留已审查的模型／工作流参数。"], sources=reserved_sources, outputs=reserved_outputs, blocker="V2_GRAPH_T2I_OWNER_NOT_CONNECTED"),
        _reserved("m5.image.i2i", "图生图节点（预留）", inputs=["输入图片须绑定资产版本／摘要；编辑提示词、蒙版、strength 和模型／工作流参数均须有边界。"], sources=reserved_sources, outputs=reserved_outputs, blocker="V2_GRAPH_I2I_OWNER_NOT_CONNECTED"),
        _existing("m6.director.propose", "导演建议与人工复审",
            _owner("app.creative.proposals", "DirectorProposalService", "create", "review", "cancel"), [
                _action("create", "POST", creative + "/director-proposals", "app.creative.proposals.DirectorProposalService.create", "DirectorProposalIn"),
                _action("review", "POST", creative + "/director-proposals/{rid}/review", "app.creative.proposals.DirectorProposalService.review", "DirectorProposalReview"),
                _action("cancel", "POST", creative + "/director-proposals/{rid}/cancel", "app.creative.proposals.DirectorProposalService.cancel", "ProposalAction")],
            inputs=["提供 source_document_id、expected_source_version，以及逐场景的镜头、情绪、节奏和表演建议。"],
            sources=["来源文档的版本和摘要必须仍有效；修改提案须提供 expected_version 与准确的 reviewed_output_digest。"],
            outputs=["原 CreativeService 创建独立 DIRECTOR 文档，保存来源版本／摘要和复审人记录。"],
            review=["NEEDS_REVIEW → APPROVED 必须经过原 DirectorProposalReview；规则辅助创建仍记录 model_called=false。"],
            limitations=["规则辅助整理作者资料，不能证明导演模型已调用、镜头质量合格或 GPU 验收通过。"]),
        _existing("m6.director.model", "导演建议的本地模型接口",
            _owner("app.creative.generation", "DirectorModelCoordinator", "preview", "dispatch", "refresh"), [
                _action("preview", "POST", creative + "/director-proposals/{rid}/preview", "app.creative.generation.DirectorModelCoordinator.preview", "DirectorModelPreview", host=True),
                _action("dispatch", "POST", creative + "/director-proposals/{rid}/dispatch", "app.creative.generation.DirectorModelCoordinator.dispatch", "DirectorModelDispatch", host=True),
                _action("refresh", "POST", creative + "/director-proposals/{rid}/refresh", "app.creative.generation.DirectorModelCoordinator.refresh", "ProposalAction", host=True)],
            inputs=["提供原提案 expected_version、准确本地模型路线和 reviewed_preview_digest；输出使用结构化 DirectorModelOutput。"],
            sources=["原剧本证据、操作者／分支范围和请求审查同意必须持续绑定原作业。"],
            outputs=["保存已校验导演建议提案和原作业回执，人工复审后才生成派生 DIRECTOR 文档。"],
            review=["必须保留原提案复审与输出摘要；模型返回文字不等于已应用的导演建议。"],
            limitations=["本端点不探测模型是否可用、注册状态或 Host 会话；真实本地模型与质量验收独立进行。"]),
        _existing("m6.storyboard.derive", "剧本／导演笔记转分镜",
            _owner("app.creative.service", "CreativeService", "derive", "update", "history", "restore"), [
                _action("derive", "POST", creative + "/documents/{rid}/derive", "app.creative.service.CreativeService.derive", "CreativeDocumentDerive"),
                _action("update", "PUT", creative + "/documents/{rid}", "app.creative.service.CreativeService.update", "CreativeDocumentUpdate")],
            inputs=["以 mode=STORYBOARD 和 expected_version 派生；来源须是含场景的 SCREENPLAY 或 DIRECTOR 文档。"],
            sources=["保留原父文档 ID、版本、摘要，场景 ID／顺序和当前来源校验。"],
            outputs=["独立 ShotCard 文档保留构图、镜头、灯光、声音和对白等字段，来源记录为 STRUCTURED_DERIVATION。"],
            review=["复制的镜头资料是可编辑草稿，仍须人工作出视觉决定；资产批准关系沿用原工作区关系服务。"],
            limitations=["derive 不调用模型或渲染器，缺失视觉决定保持空白；镜头卡片不代表已生成分镜图片。"]),
        _existing("m7.video.plan", "分镜转视频制作计划",
            _owner("app.creative.service", "CreativeService", "derive", "update"), [
                _action("derive", "POST", creative + "/documents/{rid}/derive", "app.creative.service.CreativeService.derive", "CreativeDocumentDerive"),
                _action("update", "PUT", creative + "/documents/{rid}", "app.creative.service.CreativeService.update", "CreativeDocumentUpdate")],
            inputs=["以 mode=PRODUCTION 和 expected_version 派生；分镜须有场景／镜头，VideoPlan 描述尺寸、帧率和片段。"],
            sources=["派生计划绑定原分镜文档 ID、版本、摘要和稳定镜头 ID。"],
            outputs=["形成可编辑的逐镜头时长／备注计划，仍记录 STRUCTURED_DERIVATION 与 model_called=false。"],
            review=["后续实际制作前，必须人工复审编写的时长和内容。"],
            limitations=["VIDEO_PLANNING 是 PRODUCTION 的别名；编写计划不等于视频渲染或模型执行。"]),
        _existing("m7.video.generate", "动态镜头生成（原接口）",
            _owner("app.services.screenplay_service", "ScreenplayService", "execute_motion_task", "sync_motion_task", "download_motion_asset"), [
                _action("execute", "POST", motion + "/execute", "app.services.screenplay_service.ScreenplayService.execute_motion_task"),
                _action("sync", "POST", motion + "/sync", "app.services.screenplay_service.ScreenplayService.sync_motion_task"),
                _action("download", "POST", motion + "/import-asset/download", "app.services.screenplay_service.ScreenplayService.download_motion_asset")],
            inputs=["须已有原剧本动态镜头作业；执行前用原 MotionFramesIn／MotionProviderIn 设置参考帧和模型服务。"],
            sources=[binding, "继续检查首尾帧证据、隐私请求摘要和作业归属／同次 token；这些动作没有客户端 expected_version 请求体。"],
            outputs=[media_output, "原同步／下载保持同次 token 与结果 URL 绑定，视频校验通过后才能导入。"],
            review=["保留原作业／资产复审和来源记录；历史 SUCCEEDED 不能改称 V2 Router SETTLED。"],
            limitations=[local_boundary, "V2 视频节点执行及统一复审／结算适配器尚未接入。"], blockers=["V2_GRAPH_VIDEO_EXECUTION_NOT_ENABLED"]),
        _reserved("m7.video.t2v", "文生视频（预留）", inputs=["限制提示词、时长、帧率、尺寸和 seed；须绑定准确的已审查工作流。"], sources=reserved_sources, outputs=reserved_outputs, blocker="V2_GRAPH_T2V_OWNER_NOT_CONNECTED"),
        _reserved("m7.video.i2v", "图生视频（预留）", inputs=["输入帧须绑定当前资产版本／摘要；运动、时长和已审查工作流参数须有边界。"], sources=reserved_sources, outputs=reserved_outputs, blocker="V2_GRAPH_I2V_OWNER_NOT_CONNECTED"),
        _reserved("m7.video.v2v", "视频转视频（预留）", inputs=["输入视频须绑定当前资产版本／摘要，并明确有界时间区间和转换参数。"], sources=reserved_sources, outputs=reserved_outputs, blocker="V2_GRAPH_V2V_OWNER_NOT_CONNECTED"),
        _existing("m8.audio.speech", "语音生成（原接口）",
            _owner("app.services.audiobook_service", "AudiobookService", "queue", "execute"), [
                _action("queue", "POST", audio + "/chapters/{chapter_id}/queue", "app.services.audiobook_service.AudiobookService.queue", "AudiobookJobIn"),
                _action("execute", "POST", audio + "/jobs/{job_id}/execute", "app.services.audiobook_service.AudiobookService.execute")],
            inputs=["使用原章节、模型、voice、情绪、角色、语速、停顿、许可备注与 Idempotency-Key；排队接口没有 expected_source_version。"],
            sources=["服务端保存原正文快照、版本和摘要；远端／实验来源的校验不能描述为全部普通本地路径都具备同等来源 CAS。"],
            outputs=[media_output, "异步未完成响应继续拒绝为 AUDIOBOOK_ASYNC_UNSUPPORTED，不能填入假完成音频。"],
            review=["仍须保留原语音作业／资产来源与授权；统一 V2 节点结算／复审尚未接入。"],
            limitations=[local_boundary, "语音生成不等于音乐、音效、语音识别或强制对齐。"], blockers=["V2_GRAPH_AUDIO_OWNER_NOT_CONNECTED"]),
        _existing("m8.audio.import", "独立 Studio 手动音频资产",
            _owner("app.creative.workspace", "IndependentWorkspaceService", "import_asset", "annotate", "lifecycle"), [
                _action("import", "POST", "/projects/{nid}/studio/assets", "app.creative.workspace.IndependentWorkspaceService.import_asset", "ManualAssetImport"),
                _action("lineage", "PUT", "/projects/{nid}/studio/assets/{aid}/lineage", "app.creative.workspace.IndependentWorkspaceService.annotate", "StudioLineageInput")],
            inputs=["以 ManualAssetImport.kind=audio 提交原有界上传数据；须已配置原 ffprobe／ffmpeg 校验器。"],
            sources=["沿用原项目生命周期／分支资产锁；来源备注修改使用 StudioLineageInput.expected_version。"],
            outputs=["原 AssetLibrary 保存手动输入音频的资产版本／sha256；导入动作本身不自动保存来源声明。", "来源声明是单独的显式 annotate 变更；当前界面写 EXTERNAL_IMPORT，声明失败保留已导入资产且只重试声明。"],
            review=["批准关系沿用原关系服务和 domain.review；导入／来源备注不等于批准。"],
            limitations=["已校验的手动媒体是作者输入，不是生成音频或 GPU 结果；本目录不初始化 Runtime 或校验器。"]),
        _reserved("m8.audio.music", "音乐生成（预留）", inputs=["限制音乐描述和时长，并绑定准确的已审查模型／参数。"], sources=reserved_sources, outputs=reserved_outputs, blocker="MUSIC_GENERATION_OWNER_NOT_CONNECTED"),
        _reserved("m8.audio.effects", "音效生成（预留）", inputs=["限制音效描述和时长，可引用当前来源资产。"], sources=reserved_sources, outputs=reserved_outputs, blocker="SOUND_EFFECT_GENERATION_OWNER_NOT_CONNECTED"),
        _reserved("m8.audio.trim", "音频剪裁（预留）", inputs=["绑定当前音频资产版本／摘要并限制开始／结束时间；输出格式和重采样策略还须接入原处理服务。"], sources=reserved_sources, outputs=reserved_outputs, blocker="AUDIO_TRIM_OWNER_NOT_CONNECTED"),
        _existing("m9.video.assemble", "原 FFmpeg 视频审阅拼接",
            _owner("app.services.video_assembly_service", "VideoAssemblyService", "create", "list"), [
                _action("assemble", "POST", "/novels/{nid}/screenplays/{screenplay_id}/video-assemblies", "app.services.video_assembly_service.VideoAssemblyService.create", "VideoAssemblyIn")],
            inputs=["VideoAssemblyIn.clips 接收 1–30 段 asset_id／start_ms／end_ms，总时长最多十分钟。"],
            sources=["保存原剧本／项目／分支权限与输入资产版本／摘要；没有 expected_version 或复审输入，也未实现渲染后的来源 CAS 复核。"],
            outputs=["原 FFmpeg 校验剪裁／拼接输出，保留 REVIEW_640x360_24FPS_VIDEO_ONLY 规格和资产来源。"],
            review=["拼接预览不等于人工验收；此处不宣称已有拼接复审端点或 V2 Router 结算。"],
            limitations=[local_boundary, "固定 640×360／24FPS 的纯视频审阅输出；不包含混音、多轨剪辑、成片渲染或导出质量验收。"], blockers=["V2_EDITING_SOURCE_CAS_ADAPTER_REQUIRED"]),
        _existing("m9.timeline.exchange", "OTIO 时间线交换快照",
            _owner("app.experimental.timeline_exchange", "TimelineExchangeService", "import_file", "from_screenplay", "download"), [
                _action("import", "POST", timeline + "/import", "app.experimental.timeline_exchange.TimelineExchangeService.import_file", "ImportOTIOIn"),
                _action("from_screenplay", "POST", timeline + "/from-screenplay", "app.experimental.timeline_exchange.TimelineExchangeService.from_screenplay", "ScreenplayOTIOIn"),
                _action("download", "GET", timeline + "/records/{rid}/file", "app.experimental.timeline_exchange.TimelineExchangeService.download", permission="domain.read", extra_conditions=["原查询参数 expected_version 必填并核对当前版本；acknowledge_losses 可选，默认为 false，发生转换损失时须显式确认；此动作没有请求体 schema。"] )],
            inputs=["使用原有界 ImportOTIOIn 或 ScreenplayOTIOIn，绑定剧本版本和镜头／资产；下载须提供 expected_version。"],
            sources=["重新核对原剧本证据和资产版本／摘要；有损交换必须明确 acknowledge_losses。"],
            outputs=["只生成新 OTIO 附件／快照；不读外部媒体、不写指定路径、不渲染或打包媒体。"],
            review=["时间线损失确认和来源校验与编辑内容批准分别处理。"],
            limitations=["Resolve／Premiere 往返验证仍为 NOT_RUN；有效交换快照不等于可播放或已渲染媒体。"]),
        _existing("m9.subtitle.edit", "原手工字幕时间线",
            _owner("app.experimental.subtitle_timeline", "SubtitleTimelineService", "create_track", "update", "split", "merge", "download"), [
                _action("create", "POST", subtitle, "app.experimental.subtitle_timeline.SubtitleTimelineService.create_track", "CaptionCreateIn"),
                _action("update", "PUT", subtitle + "/{rid}", "app.experimental.subtitle_timeline.SubtitleTimelineService.update", "CaptionUpdateIn"),
                _action("split", "POST", subtitle + "/{rid}/cues/{cid}/split", "app.experimental.subtitle_timeline.SubtitleTimelineService.split", "CaptionSplitIn"),
                _action("merge", "POST", subtitle + "/{rid}/cues/{cid}/merge", "app.experimental.subtitle_timeline.SubtitleTimelineService.merge", "CaptionMergeIn"),
                _action("download", "GET", subtitle + "/{rid}/file.{format}", "app.experimental.subtitle_timeline.SubtitleTimelineService.download", permission="domain.read", extra_conditions=["原路径参数 format 只允许 srt／vtt；查询参数 expected_version 必填并核对当前版本；此动作没有请求体 schema。"] )],
            inputs=["CaptionCreateIn 绑定 asset_id，可选计划版本，并提供时间基准、字幕、语言和标题；修改／下载须提供 expected_version。"],
            sources=["沿用原音频资产和可选计划版本证据，检查当前操作者范围和字幕版本。"],
            outputs=["原服务保存带版本的手工字幕文档和有界 SRT／VTT 附件。"],
            review=["时间与文字由人明确决定；拆分、合并、保存不能证明语音识别或对齐验收已过。"],
            limitations=["自动对齐仍为 NOT_CONFIGURED；字幕烧录只有显式配置原处理 adapter 后才可执行，真实质量为 NOT_RUN；手工字幕编辑不实现自动转录。"]),
        _reserved("m9.timeline.multitrack", "多轨剪辑／混音／成片渲染（预留）", inputs=["绑定视频／音频／字幕资产版本，限制轨道、片段和时间基准编辑，并明确最终导出规格。"], sources=reserved_sources, outputs=reserved_outputs, blocker="MULTITRACK_NLE_OWNER_NOT_CONNECTED"),
    ]
    # The advisory catalog still grants no execution. These descriptors now
    # point to the closed, separate Studio commands over the original owners.
    production = "/projects/{nid}/studio/production"
    replacements = {}
    for operation_id, title, owner_name in (
        ("m5.image.t2i", "独立文生图", "ImageJobService"),
        ("m5.image.i2i", "独立参考图生成", "ImageJobService"),
        ("m7.video.t2v", "独立文生视频", "VideoAssemblyService"),
        ("m7.video.i2v", "独立图生视频", "VideoAssemblyService"),
        ("m7.video.v2v", "独立视频转视频", "VideoAssemblyService"),
        ("m8.audio.speech", "独立语音合成", "AudiobookService"),
        ("m8.audio.music", "独立音乐生成", "AudiobookService"),
        ("m8.audio.effects", "独立音效生成", "AudiobookService"),
        ("m8.audio.trim", "本地音频截取", "AudiobookService"),
    ):
        replacements[operation_id] = _existing(operation_id, title,
            _owner("app.creative.production_execution", "ProductionExecutionService", "preview", "create", "execute", "get", "review", "reconcile"), [
                _action("preview", "POST", production + "/preview", "app.creative.production_execution.ProductionExecutionService.preview", "MediaCommand", permission="domain.read", host=True),
                _action("queue", "POST", production + "/jobs", "app.creative.production_execution.ProductionExecutionService.create", "MediaCreate", host=True),
                _action("execute", "POST", production + "/jobs/{owner}/{jid}/execute", "app.creative.production_execution.ProductionExecutionService.execute", "MediaJobAction", host=True),
                _action("receipt", "GET", production + "/jobs/{owner}/{jid}", "app.creative.production_execution.ProductionExecutionService.get", permission="domain.read", host=True),
                _action("review", "POST", production + "/jobs/{owner}/{jid}/review", "app.creative.production_execution.ProductionExecutionService.review", "MediaReview", permission="domain.review", host=True),
                _action("reconcile", "POST", production + "/jobs/{owner}/{jid}/reconcile", "app.creative.production_execution.ProductionExecutionService.reconcile", "MediaJobAction", host=True)],
            inputs=["使用独立 MediaCommand 有界输入；先预览并确认摘要，再入队，执行为另一个显式动作。", "图像参数按原 Provider 支持范围核验；音频截取仅本地、单个已保存音频，最多 120 秒。"],
            sources=["绑定原项目 incarnation、操作者与分支；来源 ID／版本／摘要在分派、保存结果、审核时重新核对。", "模型必须明确选择当前配置；云端须原全局开关、项目来源政策与本次显式同意同时有效。"],
            outputs=[owner_name + " 的原持久存储保存本次任务；真实结果字节通过原媒体校验器。", "候选保留原私有资产与不可变来源记录，人工确认输出摘要后才入素材库。"],
            review=["读取原任务与候选，确认准确版本／输出摘要后由 domain.review 显式审核。", "中断分派保持 UNKNOWN，显式 reconcile 不重发；丢弃本地采用权不代表远端计算已取消。"],
            limitations=["本目录仅描述入口；实际命令另走可信 Host、权限、源版本与原执行开关校验。", "本批源码尚未执行测试、Windows／GPU／真实模型验收；异步音频尚无远端查询协议，保留 UNKNOWN。", "Graph 媒体只在显式 schema 3 原运行中预览、入队、执行与审核，不扩展原 TEXT Router allowlist。"],
            blockers=["M4_TO_M9_ORDERED_ACCEPTANCE_REQUIRED", "GRAPH_MEDIA_RUNTIME_ACCEPTANCE_LOCAL_REQUIRED"])
        descriptor = replacements[operation_id]
        media_owner = "app.creative.graph_media_execution.CreativeGraphMediaRuntime."
        descriptor.actions.extend([
            _action("graph_preview", "POST", graph + "/media/preview", media_owner + "preview", "MediaNodeRequest", host=True),
            _action("graph_queue", "POST", graph + "/media/dispatch", media_owner + "dispatch", "MediaDispatch", host=True),
            _action("graph_execute", "POST", graph + "/media/execute", media_owner + "execute_job", "MediaJobRequest", host=True),
            _action("graph_receipt", "GET", graph, "app.creative.graph.CreativeGraphService.get_run", permission="domain.read", host=True),
            _action("graph_candidate", "GET", graph + "/media/candidate/{node_id}", media_owner + "candidate", permission="domain.read", host=True),
            _action("graph_review", "POST", graph + "/media/review", media_owner + "review", "MediaGraphReview", permission="domain.review", host=True),
        ])
        descriptor.input_requirements.append("Graph schema 3 使用闭合媒体节点与原 ASSET_REF；准确绑定运行与节点版本，先仅入队再另行明确执行。")
        descriptor.review_requirements.append("MEDIA_CANDIDATE 只可交给唯一 media_review；审核后原素材版本作为 ASSET_REF 下传。Graph 绑定任务不借独立媒体入口执行或审核。")
    replacements["m9.timeline.multitrack"] = _existing("m9.timeline.multitrack", "多轨剪辑、Graph 时间线与明确编码导出",
        _owner("app.creative.production_execution", "ProductionExecutionService", "timeline_list", "timeline_get", "timeline_save", "timeline_edit", "timeline_history", "timeline_restore", "timeline_export_preview", "timeline_export", "timeline_render", "review", "reconcile", "cancel"), [
            _action("save", "POST", production + "/timelines", "app.creative.production_execution.ProductionExecutionService.timeline_save", "TimelineSave", host=True),
            _action("update", "PUT", production + "/timelines/{tid}", "app.creative.production_execution.ProductionExecutionService.timeline_save", "TimelineSave", host=True),
            _action("render", "POST", production + "/timelines/{tid}/render", "app.creative.production_execution.ProductionExecutionService.timeline_render", "TimelineRender", host=True),
            _action("edit", "POST", production + "/timelines/{tid}/edit", "app.creative.production_execution.ProductionExecutionService.timeline_edit", "TimelineEdit", host=True),
            _action("history", "GET", production + "/timelines/{tid}/history", "app.creative.production_execution.ProductionExecutionService.timeline_history", permission="domain.read", host=True),
            _action("restore", "POST", production + "/timelines/{tid}/restore", "app.creative.production_execution.ProductionExecutionService.timeline_restore", "TimelineRestore", host=True),
            _action("export_preview", "POST", production + "/timelines/{tid}/export-preview", "app.creative.production_execution.ProductionExecutionService.timeline_export_preview", "TimelineExportPreview", permission="domain.read", host=True),
            _action("export", "POST", production + "/timelines/{tid}/export", "app.creative.production_execution.ProductionExecutionService.timeline_export", "TimelineExport", host=True),
            _action("cancel", "POST", production + "/jobs/timeline/{jid}/cancel", "app.creative.production_execution.ProductionExecutionService.cancel", "MediaJobAction", host=True),
            _action("review", "POST", production + "/jobs/timeline/{jid}/review", "app.creative.production_execution.ProductionExecutionService.review", "MediaReview", permission="domain.review", host=True)],
        inputs=["保存版本化时间线后，准确确认版本／摘要；最多 8 轨、30 段、10 分钟、1920×1080／60FPS。", "原子分切／移动／复制／滑移／波纹裁剪／分轨／字幕及历史恢复；显式 schema 2 另含静态图片、变速、透明度、淡入淡出与原视频声音混音。"],
        sources=["绑定原视频／图片／音频资产快照与时间线版本，在原 scope→asset→project 临界区保存／编辑，渲染前后及审核时再次校验。"],
        outputs=["原 VideoAssemblyService 持久任务调用本地 FFmpeg，支持原审阅 MP4、H.264/AAC MP4、VP9/Opus WebM；实际 probe 核对编码／容器／画幅／帧率／声音／时长后保存私有候选。"],
        review=["显式预览候选并确认输出摘要；只审核通过才进入素材库，UNKNOWN 不自动重新渲染。"],
        limitations=["导出使用原 25MiB Asset 上限和有界时长／原生执行时限，超限拒绝而不悄悄降低要求；不代表自动转录、跨软件往返或质量验收。", "本批构建、渲染、Windows／GPU与完整产品验收均 NOT_RUN。"],
        blockers=["M4_TO_M9_ORDERED_ACCEPTANCE_REQUIRED", "GRAPH_TIMELINE_RUNTIME_ACCEPTANCE_LOCAL_REQUIRED"])
    timeline = replacements["m9.timeline.multitrack"]
    media_owner = "app.creative.graph_media_execution.CreativeGraphMediaRuntime."
    timeline.actions.extend([
        _action("graph_preview", "POST", graph + "/media/preview", media_owner + "preview", "MediaNodeRequest", host=True),
        _action("graph_queue", "POST", graph + "/media/dispatch", media_owner + "dispatch", "MediaDispatch", host=True),
        _action("graph_execute", "POST", graph + "/media/execute", media_owner + "execute_job", "MediaJobRequest", host=True),
        _action("graph_candidate", "GET", graph + "/media/candidate/{node_id}", media_owner + "candidate", permission="domain.read", host=True),
        _action("graph_review", "POST", graph + "/media/review", media_owner + "review", "MediaGraphReview", permission="domain.review", host=True),
        _action("graph_reconcile", "POST", graph + "/media/reconcile", media_owner + "reconcile", "MediaJobRequest", host=True),
    ])
    timeline.input_requirements.append("显式 schema 3 timeline_export 绑定原时间线 ID／version／digest；闭合剪辑与最多 8 个已审核 ASSET_REF→clip 绑定合计最多 40 操作，预览不执行。")
    timeline.output_requirements.append("Graph 确认摘要后，在原 raw scope／asset phase 同时保存剪辑历史与节点 claim，再仅入队原 VideoAssemblyService；明确 execute 才调用同一个本地 FFmpeg owner。")
    timeline.review_requirements.append("唯一 media_review 审核原 timeline candidate 后输出 video ASSET_REF；原独立任务入口不能执行或审核 Graph 绑定任务，UNKNOWN 只查原记录且不重复剪辑或渲染。")
    timeline.input_requirements.append("schema 2 可选源编码像素 crop 矩形；实际源尺寸在原渲染器校验，裁切后缩放。轨道 locked 是作者锁，只有原 track.update 的独立解锁动作可以解除。")
    timeline.review_requirements.append("原媒体 publish 前持久保存真实输出摘要、大小与类型；显式 reconcile 仅恢复同一来源与私有字节，不重发。未提升审核失败按精确私有候选证明补偿，已提升或不明的 REVIEWING 保留。")
    transfer_owner = "app.creative.production_execution.ProductionExecutionService."
    transfer_actions = [
        _action("transfer_preview", "POST", production + "/timelines/{tid}/transfer-preview", transfer_owner + "timeline_transfer_preview", "TimelineTransferPreview", permission="domain.read", host=True),
        _action("transfer_import", "POST", production + "/timelines/{tid}/transfer-import", transfer_owner + "timeline_transfer_import", "TimelineTransferImport", host=True),
        _action("transfer_attachment", "POST", production + "/timelines/{tid}/transfer-attachment", transfer_owner + "timeline_transfer_attachment", "TimelineTransferDownload", permission="domain.read", host=True),
    ]
    exchange = next(item for item in operations if item.id == "m9.timeline.exchange")
    exchange.actions.extend(transfer_actions)
    exchange.input_requirements.append("Studio 原时间线支持 OTIO 的明确预览、精确媒体快照映射、转换损失确认及 CAS 导入；导出附件重新核对预览摘要／来源，不写客户端路径。")
    exchange.output_requirements.append("原官方 OTIO 0.18.1 serializer 与有界转换器处理多轨、Gap、精确 rational speed 与只读媒体引用；Studio 完整 metadata 仅在原生投影未改变时还原。")
    exchange.limitations.append("导入不打开外部引用；跨软件效果／混音／裁切／锁定等差异须确认 loss receipt。Resolve／Premiere、FCPXML／EDL 与交互 proxy 播放未因此通过验收。")
    subtitle = next(item for item in operations if item.id == "m9.subtitle.edit")
    subtitle.actions.extend(transfer_actions)
    subtitle.input_requirements.append("原 Studio 时间线另可导入／导出闭合 SRT／WebVTT；预览不写，替换已有字幕须明确确认损失与准确版本。")
    subtitle.output_requirements.append("原 SubtitleTimelineService 持久处理任务可注入 V2 显式配置的受控 FFmpeg 烧录；本地 ASR 执行代码经原 Registry AUDIO 与可信 Host model admission，未配置则拒绝执行。")
    subtitle.limitations.append("真实 ASR 需要可靠的已启用模型／runtime 身份准入；whisper.cpp wire 本身不证明模型哈希。Forced alignment engine 仍 NOT_CONFIGURED，不能把 ASR 段时间戳写成强制对齐。")
    # Standalone only: deliberately outside the shared Graph descriptor loop.
    operations.append(_existing("m5.image.cutout", "本地手工蒙版抠图",
        _owner("app.creative.production_execution", "ProductionExecutionService", "preview", "create", "execute", "get", "cancel", "review", "reconcile"), [
            _action("preview", "POST", production + "/preview", "app.creative.production_execution.ProductionExecutionService.preview", "MediaCommand", permission="domain.read", host=True),
            _action("queue", "POST", production + "/jobs", "app.creative.production_execution.ProductionExecutionService.create", "MediaCreate", host=True),
            _action("execute", "POST", production + "/jobs/image/{jid}/execute", "app.creative.production_execution.ProductionExecutionService.execute", "MediaJobAction", host=True),
            _action("receipt", "GET", production + "/jobs/image/{jid}", "app.creative.production_execution.ProductionExecutionService.get", permission="domain.read", host=True),
            _action("cancel", "POST", production + "/jobs/image/{jid}/cancel", "app.creative.production_execution.ProductionExecutionService.cancel", "MediaJobAction", host=True),
            _action("review", "POST", production + "/jobs/image/{jid}/review", "app.creative.production_execution.ProductionExecutionService.review", "MediaReview", permission="domain.review", host=True),
            _action("reconcile", "POST", production + "/jobs/image/{jid}/reconcile", "app.creative.production_execution.ProductionExecutionService.reconcile", "MediaJobAction", host=True)],
        inputs=["仅两个有序图像快照：原 PNG、已保存手工二值蒙版；provider/model 为空、prompt/parameters 为空、allow_cloud=false。", "8 位非交错灰度/RGB/灰度透明/RGBA PNG；64–1024 像素且为 8 的倍数；拒绝附加块、调色板、动画和越界数据。"],
        sources=["原 AssetLibrary 核验蒙版不可变来源、原图与蒙版准确版本/摘要、当前作用域与 Host 权限；保留两份快照。"],
        outputs=["原 ImageJobService 保存确定性 RGBA PNG 私有候选。白色保留原像素与 alpha，黑色输出零 RGBA；不调用 provider、网络、子进程或 Pillow。"],
        review=["单独预览、入队、执行，核对候选摘要后人工明确批准；中断回执不自动重放。", "仅此 CPU 操作支持 RUNNING 协作式取消；已保存候选保持私有。"],
        limitations=["仅独立 IMAGE 工作区；不加入 Graph 闭合媒体操作集合；不是自动分割、羽化或通用图片编辑。", "真实用户浏览器与 Windows 验收另行记录，产品验收仍 LOCAL_REQUIRED。"],
        blockers=["M4_TO_M9_ORDERED_ACCEPTANCE_REQUIRED"]))
    return [replacements.get(operation.id, operation) for operation in operations]


def production_catalog(project_id: str, scope: dict) -> ProductionCatalog:
    """Project only captured public scope; no identity or provider facts leak."""
    public_scope = {key: value for key, value in scope.items() if key in PUBLIC_SCOPE_KEYS}
    return ProductionCatalog(project_id=project_id, scope=public_scope,
        acceptance_sequence=list(ACCEPTANCE_SEQUENCE), operations=_operations(),
        interface_schemas={name: model.model_json_schema() for name, model in INTERFACE_MODELS})
