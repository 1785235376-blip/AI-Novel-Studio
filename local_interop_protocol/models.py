"""Public, product-neutral Local Interop 1.0 wire contract.

Freshly authored for the shared boundary. Nothing here imports either product.
Wire data is never permission, source provenance, a locator read, or an action.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationInfo,
    field_validator,
    model_validator,
)

PROTOCOL_NAME = "PoemSeed Local Interop"
PROTOCOL_VERSION = "1.0"
STUDIO_PRODUCT_ID = "poemseed.creative.studio"
TUTOR_PRODUCT_ID = "poemseed.tutor.desktop"

OpaqueId = Annotated[
    str,
    StringConstraints(
        strict=True, min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
    ),
]
ProductId = Annotated[
    str,
    StringConstraints(
        strict=True, min_length=3, max_length=128, pattern=r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)+$"
    ),
]
Version = Annotated[
    str,
    StringConstraints(
        strict=True, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$"
    ),
]
Hash = Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9a-f]{64}$")]
Label = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=256)]
ShortText = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=2048)]
LongText = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=8192)]
Locator = Annotated[
    str,
    StringConstraints(
        strict=True,
        max_length=256,
        pattern=r"^(?:app|project|chapter|task|runtime|model|selection|feature|interop|diagnostic|user-observation):[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$",
    ),
]
PositiveVersion = Annotated[int, Field(strict=True, ge=0, le=2**53 - 1)]
UtcTime = datetime
Privacy = Literal["LOCAL_ONLY", "REDACTION_REQUIRED", "CONSENTED_CLOUD"]
Authority = Literal["AUTHORITATIVE", "CONSTRAINING", "SUPPORTING", "ADVISORY"]
ProductRole = Literal[
    "AI_TUTOR", "CREATIVE_STUDIO", "DCC", "VIDEO_EDITOR", "GAME_ENGINE", "IMAGE_TOOL", "AUDIO_TOOL"
]
Transport = Literal["NAMED_PIPE", "LOOPBACK_HTTP"]
Capability = Literal[
    "project.context.read",
    "project.selection.share",
    "project.metadata.read",
    "task.status.read",
    "task.error.read",
    "diagnostics.read",
    "model.registry.read",
    "model.runtime.status.read",
    "tutor.guidance.request",
    "tutor.guidance.receive",
    "verifier.request",
    "verifier.result.receive",
    "case.candidate.create",
    "handoff.open_feature",
    "handoff.open_project",
    "handoff.open_task",
]
CAPABILITIES: tuple[str, ...] = Capability.__args__
AdvertisedCapability = Annotated[
    str,
    StringConstraints(
        strict=True,
        min_length=3,
        max_length=128,
        pattern=r"^[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)+$",
    ),
]
ErrorCode = Literal[
    "PROTOCOL_INCOMPATIBLE",
    "PRODUCT_NOT_AVAILABLE",
    "CAPABILITY_NOT_SUPPORTED",
    "SESSION_REQUIRED",
    "SESSION_REVOKED",
    "PERMISSION_DENIED",
    "CONTEXT_NOT_AUTHORIZED",
    "CONTEXT_STALE",
    "SOURCE_CHANGED",
    "HANDOFF_TARGET_NOT_FOUND",
    "TUTOR_UNAVAILABLE",
    "VERIFIER_UNAVAILABLE",
    "MODEL_NOT_AVAILABLE",
    "TRANSPORT_ERROR",
    "TIMEOUT",
    "CANCELLED",
    "INVALID_MESSAGE",
]
TaskStatus = Literal[
    "PENDING",
    "QUEUED",
    "RUNNING",
    "WAITING",
    "FAILED",
    "COMPLETED",
    "CANCELLED",
    "BLOCKED",
    "UNKNOWN",
]
RuntimeStatus = Literal["READY", "LOADING", "UNAVAILABLE", "ERROR", "UNKNOWN"]
Modality = Literal["TEXT", "IMAGE", "AUDIO", "VIDEO", "EMBEDDING", "MULTIMODAL"]
ContentLevel = Literal["NONE", "SELECTED_TEXT", "CURRENT_CHAPTER", "PROJECT_CONTEXT"]
_PRIVACY_RANK = {"CONSENTED_CLOUD": 0, "REDACTION_REQUIRED": 1, "LOCAL_ONLY": 2}
_SECRET = re.compile(
    r"(?i)(?:\b(?:api[ _-]?key|provider[ _-]?secret|access[ _-]?token|oauth[ _-]?token|"
    r"password|vault[ _-]?secret|authorization|cookie|dsn)\s*[:=]\s*\S+|"
    r"\bsk-[A-Za-z0-9_-]{16,}|\bBearer\s+[A-Za-z0-9._~+/-]{12,}|"
    r"[a-z][a-z0-9+.-]*://[^\s/@]+:[^\s/@]+@)"
)


def _reject_secrets(value: object) -> None:
    if isinstance(value, str) and _SECRET.search(value):
        raise ValueError("Credential-shaped content is not permitted on the interop boundary")
    if isinstance(value, dict):
        for item in value.values():
            _reject_secrets(item)
    if isinstance(value, (tuple, list)):
        for item in value:
            _reject_secrets(item)


class WireModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, validate_default=True)

    @model_validator(mode="after")
    def reject_secrets(self) -> Self:
        _reject_secrets(self.model_dump(mode="json"))
        return self

    @field_validator("*", mode="after")
    @classmethod
    def normalize_timestamp(cls, value: object) -> object:
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("Timestamp must include a UTC offset")
            return value.astimezone(timezone.utc)
        return value


class ProtocolMessage(WireModel):
    protocol_name: Literal["PoemSeed Local Interop"] = PROTOCOL_NAME
    protocol_version: Literal["1.0"] = PROTOCOL_VERSION

    @model_validator(mode="after")
    def require_wire_protocol(self, info: ValidationInfo) -> Self:
        if (info.context or {}).get("wire") and not {"protocol_name", "protocol_version"}.issubset(
            self.model_fields_set
        ):
            raise ValueError(
                "Every protocol message requires explicit protocol identity on the wire"
            )
        return self


class ProductDescriptor(ProtocolMessage):
    product_id: ProductId
    display_name: Label
    product_version: Version
    instance_id: OpaqueId
    product_role: ProductRole
    protocol_versions: Annotated[tuple[Version, ...], Field(min_length=1, max_length=16)] = (
        PROTOCOL_VERSION,
    )
    capabilities: Annotated[tuple[AdvertisedCapability, ...], Field(max_length=64)] = ()

    @model_validator(mode="after")
    def unique_values(self) -> Self:
        if len(set(self.capabilities)) != len(self.capabilities) or len(
            set(self.protocol_versions)
        ) != len(self.protocol_versions):
            raise ValueError("Duplicate capabilities or protocol versions")
        return self


class HandshakeHello(ProtocolMessage):
    product: ProductDescriptor
    transport: Transport
    session_nonce: Annotated[
        str,
        StringConstraints(strict=True, min_length=24, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"),
    ]
    privacy_mode: Privacy = "LOCAL_ONLY"


Hello = HandshakeHello


class CapabilityNegotiation(ProtocolMessage):
    hello_id: OpaqueId
    requested_capabilities: Annotated[tuple[AdvertisedCapability, ...], Field(max_length=64)]
    granted_capabilities: Annotated[tuple[Capability, ...], Field(max_length=64)] = ()

    @model_validator(mode="after")
    def subset(self) -> Self:
        if not set(self.granted_capabilities).issubset(self.requested_capabilities):
            raise ValueError("Granted capabilities must be requested")
        if len(set(self.requested_capabilities)) != len(self.requested_capabilities) or len(
            set(self.granted_capabilities)
        ) != len(self.granted_capabilities):
            raise ValueError("Duplicate capability")
        return self


class SessionDescriptor(ProtocolMessage):
    session_id: OpaqueId
    product_id: ProductId
    instance_id: OpaqueId
    peer_product_id: ProductId
    peer_instance_id: OpaqueId
    user_identity: OpaqueId
    capabilities: Annotated[tuple[Capability, ...], Field(max_length=64)]
    nonce: Annotated[
        str,
        StringConstraints(strict=True, min_length=24, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"),
    ]
    created_at: UtcTime
    expires_at: UtcTime
    transport: Transport

    @model_validator(mode="after")
    def lifetime(self) -> Self:
        if not 0 < (self.expires_at - self.created_at).total_seconds() <= 86400:
            raise ValueError("Session lifetime must be positive and at most one day")
        if len(set(self.capabilities)) != len(self.capabilities):
            raise ValueError("Duplicate capability")
        return self


class ContextEvidence(WireModel):
    source_id: OpaqueId
    source_version: Version
    locator: Locator
    content_hash: Hash
    timestamp: UtcTime
    authority: Authority
    privacy: Privacy = "LOCAL_ONLY"


class ContextContent(WireModel):
    level: ContentLevel = "NONE"
    text: Annotated[str, StringConstraints(strict=True, min_length=1, max_length=65536)] | None = (
        None
    )
    consent_id: OpaqueId | None = None

    @model_validator(mode="after")
    def consent(self) -> Self:
        if self.level == "NONE":
            if self.text is not None or self.consent_id is not None:
                raise ValueError("NONE cannot carry text or a content consent")
        elif self.text is None or self.consent_id is None:
            raise ValueError("Content requires explicit scoped consent")
        if self.level == "SELECTED_TEXT" and self.text is not None and len(self.text) > 16384:
            raise ValueError("Selected text exceeds the per-request limit")
        return self


class AppContextCapsule(ProtocolMessage):
    capsule_id: OpaqueId
    source_version: Version
    capsule_hash: Hash
    product_id: ProductId
    product_version: Version
    instance_id: OpaqueId
    project_id: OpaqueId | None = None
    project_version: Version | None = None
    workspace_id: OpaqueId | None = None
    storyline_id: OpaqueId | None = None
    branch_id: OpaqueId | None = None
    module: OpaqueId
    surface: OpaqueId
    chapter_id: OpaqueId | None = None
    chapter_version: PositiveVersion | None = None
    selection_id: OpaqueId | None = None
    selection_hash: Hash | None = None
    task_id: OpaqueId | None = None
    task_type: OpaqueId | None = None
    task_status: TaskStatus | None = None
    runtime_id: OpaqueId | None = None
    runtime_status: RuntimeStatus | None = None
    model_id: OpaqueId | None = None
    error_code: OpaqueId | None = None
    privacy_scope: Privacy = "LOCAL_ONLY"
    created_at: UtcTime
    expires_at: UtcTime
    evidence: Annotated[tuple[ContextEvidence, ...], Field(max_length=64)] = ()
    content: ContextContent = Field(default_factory=ContextContent)

    @model_validator(mode="after")
    def semantic_integrity(self, info: ValidationInfo) -> Self:
        from .validation import canonical_hash

        if not 0 < (self.expires_at - self.created_at).total_seconds() <= 3600:
            raise ValueError("Context lifetime must be positive and at most one hour")
        if (
            not (info.context or {}).get("_allow_unsealed")
            and canonical_hash(self, exclude=("capsule_hash",)) != self.capsule_hash
        ):
            raise ValueError("Context capsule hash mismatch")
        _check_privacy(self.privacy_scope, self.evidence)
        if any(item.timestamp > self.created_at for item in self.evidence):
            raise ValueError("Evidence cannot come from after its context snapshot")
        if len({item.source_id for item in self.evidence}) != len(self.evidence):
            raise ValueError("A context cannot contain conflicting duplicate source evidence")
        if self.chapter_id is not None and (
            self.project_id is None or self.chapter_version is None
        ):
            raise ValueError("Chapter requires its project and version")
        if self.project_id is not None and self.project_version is None:
            raise ValueError("Project requires its version")
        if self.content.level == "SELECTED_TEXT" and (
            self.selection_id is None or self.selection_hash is None
        ):
            raise ValueError("Selected text requires selection identity and hash")
        if (
            self.content.level == "SELECTED_TEXT"
            and canonical_hash(self.content.text) != self.selection_hash
        ):
            raise ValueError("Selected text hash does not match the shared selection")
        if self.content.level == "CURRENT_CHAPTER" and self.chapter_id is None:
            raise ValueError("Chapter content requires chapter identity")
        if self.content.level == "PROJECT_CONTEXT" and self.project_id is None:
            raise ValueError("Project content requires project identity")
        return self


def _check_privacy(derived: Privacy, evidence: tuple[ContextEvidence, ...]) -> None:
    if any(_PRIVACY_RANK[derived] < _PRIVACY_RANK[item.privacy] for item in evidence):
        raise ValueError("Derived privacy cannot be weaker than its source")


EventType = Literal[
    "PROJECT_OPENED",
    "PROJECT_CLOSED",
    "CHAPTER_OPENED",
    "TASK_STARTED",
    "TASK_UPDATED",
    "TASK_FAILED",
    "TASK_COMPLETED",
    "TASK_CANCELLED",
    "MODEL_CHANGED",
    "RUNTIME_AVAILABLE",
    "RUNTIME_UNAVAILABLE",
    "VALIDATION_REQUIRED",
    "EXPORT_FAILED",
    "WORKFLOW_BLOCKED",
]


class InteropEvent(ProtocolMessage):
    event_id: OpaqueId
    session_id: OpaqueId
    sequence: Annotated[int, Field(strict=True, ge=1, le=2**53 - 1)]
    event_type: EventType
    created_at: UtcTime
    context: AppContextCapsule

    @model_validator(mode="after")
    def metadata_only(self) -> Self:
        if self.context.content.level != "NONE":
            raise ValueError("Event stream cannot contain content")
        return self


class CapabilityState(WireModel):
    capability: Capability
    available: bool


class DiagnosticCapsule(ProtocolMessage):
    diagnostic_id: OpaqueId
    source_version: Version
    content_hash: Hash
    software_id: ProductId | None = None
    software_version: Version | None = None
    feature: OpaqueId | None = None
    error_code: OpaqueId | None = None
    task_state: TaskStatus | None = None
    runtime: OpaqueId | None = None
    model: OpaqueId | None = None
    capability_state: Annotated[tuple[CapabilityState, ...], Field(max_length=64)] = ()
    privacy_scope: Privacy = "LOCAL_ONLY"
    created_at: UtcTime
    expires_at: UtcTime
    evidence: Annotated[tuple[ContextEvidence, ...], Field(max_length=64)] = ()
    sanitized: Literal[True] = True

    @field_validator("sanitized", mode="before")
    @classmethod
    def sanitized_is_true(cls, value: object) -> bool:
        if value is not True:
            raise ValueError("Diagnostic sanitized flag must be the boolean true")
        return True

    @model_validator(mode="after")
    def semantic_integrity(self, info: ValidationInfo) -> Self:
        from .validation import canonical_hash

        if not 0 < (self.expires_at - self.created_at).total_seconds() <= 3600:
            raise ValueError("Diagnostic lifetime must be positive and at most one hour")
        if (
            not (info.context or {}).get("_allow_unsealed")
            and canonical_hash(self, exclude=("content_hash",)) != self.content_hash
        ):
            raise ValueError("Diagnostic hash mismatch")
        _check_privacy(self.privacy_scope, self.evidence)
        if any(item.timestamp > self.created_at for item in self.evidence):
            raise ValueError("Evidence cannot come from after its diagnostic snapshot")
        return self


class SharedModelDescriptor(WireModel):
    runtime_id: OpaqueId
    model_id: OpaqueId
    family: Label
    modality: Annotated[tuple[Modality, ...], Field(min_length=1, max_length=6)]
    runtime_type: OpaqueId
    local: bool
    declared_capabilities: Annotated[tuple[OpaqueId, ...], Field(max_length=32)] = ()
    verified_capabilities: Annotated[tuple[OpaqueId, ...], Field(max_length=32)] = ()
    model_version: Version | None = None
    model_hash_if_available: Hash | None = None
    context_window: Annotated[int, Field(strict=True, ge=1, le=100_000_000)] | None = None
    compatibility: Annotated[tuple[OpaqueId, ...], Field(max_length=32)] = ()
    availability: Literal["AVAILABLE", "UNAVAILABLE", "UNKNOWN"] = "UNKNOWN"
    last_validated: UtcTime | None = None

    @model_validator(mode="after")
    def verified_subset(self) -> Self:
        if not set(self.verified_capabilities).issubset(self.declared_capabilities):
            raise ValueError("Verified capabilities must be declared")
        return self


class ModelRegistry(ProtocolMessage):
    models: Annotated[tuple[SharedModelDescriptor, ...], Field(max_length=256)] = ()
    created_at: UtcTime


class TaskRequirement(WireModel):
    task_type: OpaqueId
    required_modality: Annotated[tuple[Modality, ...], Field(min_length=1, max_length=6)]
    estimated_context: Annotated[int, Field(strict=True, ge=0, le=100_000_000)]
    privacy: Privacy = "LOCAL_ONLY"
    quality_priority: Annotated[int, Field(strict=True, ge=0, le=100)] = 50
    latency_priority: Annotated[int, Field(strict=True, ge=0, le=100)] = 50
    cost_priority: Annotated[int, Field(strict=True, ge=0, le=100)] = 50


class HandoffTarget(WireModel):
    action: Literal["OPEN_FEATURE", "OPEN_PROJECT", "OPEN_TASK", "OPEN_CHAPTER", "OPEN_SESSION"]
    target_product_id: ProductId
    feature: OpaqueId | None = None
    project_id: OpaqueId | None = None
    chapter_id: OpaqueId | None = None
    task_id: OpaqueId | None = None
    session_id: OpaqueId | None = None
    source_version: Version | None = None

    @model_validator(mode="after")
    def action_shape(self) -> Self:
        required = {
            "OPEN_FEATURE": "feature",
            "OPEN_PROJECT": "project_id",
            "OPEN_TASK": "task_id",
            "OPEN_CHAPTER": "chapter_id",
            "OPEN_SESSION": "session_id",
        }[self.action]
        targets = {
            key
            for key in ("feature", "project_id", "chapter_id", "task_id", "session_id")
            if getattr(self, key) is not None
        }
        allowed = {required} | (
            {"project_id"} if self.action in ("OPEN_TASK", "OPEN_CHAPTER") else set()
        )
        if required not in targets or not targets.issubset(allowed):
            raise ValueError("Handoff fields must match the semantic action")
        if (
            self.action in ("OPEN_PROJECT", "OPEN_TASK", "OPEN_CHAPTER")
            and self.source_version is None
        ):
            raise ValueError("Project, task and chapter handoffs require a source version")
        return self


class HandoffRequest(ProtocolMessage):
    request_id: OpaqueId
    session_id: OpaqueId
    target: HandoffTarget
    user_gesture_id: OpaqueId


class HandoffResult(ProtocolMessage):
    request_id: OpaqueId
    session_id: OpaqueId
    status: Literal["OPENED", "REJECTED"]
    error_code: ErrorCode | None = None

    @model_validator(mode="after")
    def error_shape(self) -> Self:
        if (self.status == "REJECTED") != (self.error_code is not None):
            raise ValueError("Rejected handoffs require a typed error")
        return self


class VerificationCondition(WireModel):
    field: Literal["runtime_status", "task_status", "project_version", "chapter_version"]
    operator: Literal["EQ", "NE", "GTE"] = "EQ"
    expected_value: TaskStatus | RuntimeStatus | Version | PositiveVersion
    source_id: OpaqueId

    @model_validator(mode="after")
    def value_shape(self) -> Self:
        numeric = self.field == "chapter_version"
        if numeric != isinstance(self.expected_value, int):
            raise ValueError("Verification value type must match the selected field")
        if not numeric and self.operator == "GTE":
            raise ValueError("GTE applies only to numeric chapter versions")
        if self.field == "runtime_status" and self.expected_value not in RuntimeStatus.__args__:
            raise ValueError("Expected runtime status is invalid")
        if self.field == "task_status" and self.expected_value not in TaskStatus.__args__:
            raise ValueError("Expected task status is invalid")
        return self


class GuidanceStep(WireModel):
    step_id: OpaqueId
    instruction: ShortText
    handoff: HandoffTarget | None = None


class GuidanceReference(WireModel):
    source_id: OpaqueId
    label: Label
    locator: Locator


class ModelRecommendation(WireModel):
    runtime_id: OpaqueId
    model_id: OpaqueId
    reason: ShortText
    authority: Literal["ADVISORY"] = "ADVISORY"


class TutorRequest(ProtocolMessage):
    request_id: OpaqueId
    session_id: OpaqueId
    context: AppContextCapsule
    question: ShortText | None = None
    diagnostic: DiagnosticCapsule | None = None
    task_requirement: TaskRequirement | None = None

    @model_validator(mode="after")
    def requirement_privacy(self) -> Self:
        if (
            self.task_requirement is not None
            and _PRIVACY_RANK[self.task_requirement.privacy]
            < _PRIVACY_RANK[self.context.privacy_scope]
        ):
            raise ValueError("Task requirement cannot weaken source context privacy")
        return self


class TutorGuidance(ProtocolMessage):
    request_id: OpaqueId
    session_id: OpaqueId
    guidance_id: OpaqueId
    summary: ShortText
    diagnosis: LongText
    steps: Annotated[tuple[GuidanceStep, ...], Field(max_length=32)] = ()
    warnings: Annotated[tuple[ShortText, ...], Field(max_length=16)] = ()
    references: Annotated[tuple[GuidanceReference, ...], Field(max_length=32)] = ()
    verification_condition: VerificationCondition | None = None
    recommended_model: ModelRecommendation | None = None
    privacy_scope: Privacy = "LOCAL_ONLY"
    created_at: UtcTime
    authority: Literal["ADVISORY"] = "ADVISORY"


class VerifierRequest(ProtocolMessage):
    request_id: OpaqueId
    session_id: OpaqueId
    guidance_id: OpaqueId
    condition: VerificationCondition
    context: AppContextCapsule


class VerifierResult(ProtocolMessage):
    request_id: OpaqueId
    session_id: OpaqueId
    result_id: OpaqueId
    status: Literal["VERIFIED", "PARTIAL", "FAILED", "UNKNOWN"]
    reason: ShortText
    evidence: Annotated[tuple[ContextEvidence, ...], Field(max_length=64)] = ()
    privacy_scope: Privacy = "LOCAL_ONLY"
    created_at: UtcTime

    @model_validator(mode="after")
    def source_requirements(self) -> Self:
        _check_privacy(self.privacy_scope, self.evidence)
        if self.status == "VERIFIED" and not any(
            item.authority == "AUTHORITATIVE" for item in self.evidence
        ):
            raise ValueError(
                "VERIFIED requires authoritative source evidence; host must validate provenance"
            )
        return self


class CaseEnvironment(WireModel):
    product_id: ProductId
    product_version: Version
    module: OpaqueId
    runtime_id: OpaqueId | None = None
    model_id: OpaqueId | None = None
    task_type: OpaqueId | None = None


class CaseCandidate(ProtocolMessage):
    candidate_id: OpaqueId
    problem: ShortText
    environment: CaseEnvironment
    diagnosis: LongText
    guidance: TutorGuidance
    result: ShortText
    verification: VerifierResult
    software_id: ProductId
    software_version: Version
    evidence: Annotated[tuple[ContextEvidence, ...], Field(max_length=64)] = ()
    privacy_scope: Privacy = "LOCAL_ONLY"
    created_at: UtcTime

    @model_validator(mode="after")
    def derived_privacy(self) -> Self:
        _check_privacy(self.privacy_scope, self.evidence)
        if any(
            _PRIVACY_RANK[self.privacy_scope] < _PRIVACY_RANK[value]
            for value in (self.guidance.privacy_scope, self.verification.privacy_scope)
        ):
            raise ValueError("Case cannot weaken source privacy")
        if self.verification.status != "VERIFIED":
            raise ValueError("A resolved case requires verified evidence")
        return self


class InteropError(ProtocolMessage):
    request_id: OpaqueId | None = None
    code: ErrorCode
    message: ShortText
    retryable: bool = False


class CancelRequest(ProtocolMessage):
    request_id: OpaqueId
    session_id: OpaqueId | None = None


class Heartbeat(ProtocolMessage):
    session_id: OpaqueId
    sequence: Annotated[int, Field(strict=True, ge=1, le=2**53 - 1)]
    created_at: UtcTime


class DiscoveryRecord(ProtocolMessage):
    product_id: ProductId
    instance_id: OpaqueId
    product_version: Version
    protocol_versions: Annotated[tuple[Version, ...], Field(min_length=1, max_length=16)] = (
        PROTOCOL_VERSION,
    )
    capabilities: Annotated[tuple[AdvertisedCapability, ...], Field(max_length=64)] = ()


class HelloResult(ProtocolMessage):
    hello_id: OpaqueId
    product: ProductDescriptor
    session_nonce: Annotated[
        str,
        StringConstraints(strict=True, min_length=24, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"),
    ]


class SessionOpenRequest(ProtocolMessage):
    hello_id: OpaqueId
    session_nonce: Annotated[
        str,
        StringConstraints(strict=True, min_length=24, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"),
    ]
    user_identity: OpaqueId


class SessionOpenResult(ProtocolMessage):
    session: SessionDescriptor
    session_token: Annotated[
        str,
        StringConstraints(strict=True, min_length=32, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"),
    ]


Operation = Literal[
    "HELLO",
    "CAPABILITY_NEGOTIATION",
    "SESSION",
    "TUTOR",
    "DIAGNOSTICS",
    "VERIFY",
    "HANDOFF",
    "HEARTBEAT",
    "CANCEL",
]


class TransportRequest(ProtocolMessage):
    operation: Operation
    payload: (
        HandshakeHello
        | CapabilityNegotiation
        | SessionOpenRequest
        | TutorRequest
        | DiagnosticCapsule
        | VerifierRequest
        | HandoffRequest
        | Heartbeat
        | CancelRequest
    )

    @model_validator(mode="after")
    def operation_payload(self) -> Self:
        model = {
            "HELLO": HandshakeHello,
            "CAPABILITY_NEGOTIATION": CapabilityNegotiation,
            "SESSION": SessionOpenRequest,
            "TUTOR": TutorRequest,
            "DIAGNOSTICS": DiagnosticCapsule,
            "VERIFY": VerifierRequest,
            "HANDOFF": HandoffRequest,
            "HEARTBEAT": Heartbeat,
            "CANCEL": CancelRequest,
        }[self.operation]
        if not isinstance(self.payload, model):
            raise ValueError("Transport operation does not match payload type")
        return self


class CancelResult(ProtocolMessage):
    request_id: OpaqueId
    session_id: OpaqueId | None = None
    status: Literal["CANCELLED"] = "CANCELLED"


class TransportResponse(ProtocolMessage):
    operation: Operation
    payload: (
        HelloResult
        | CapabilityNegotiation
        | SessionOpenResult
        | TutorGuidance
        | VerifierResult
        | HandoffResult
        | Heartbeat
        | CancelResult
        | InteropError
    )

    @model_validator(mode="after")
    def operation_payload(self) -> Self:
        if isinstance(self.payload, InteropError):
            return self
        model = {
            "HELLO": HelloResult,
            "CAPABILITY_NEGOTIATION": CapabilityNegotiation,
            "SESSION": SessionOpenResult,
            "TUTOR": TutorGuidance,
            "DIAGNOSTICS": TutorGuidance,
            "VERIFY": VerifierResult,
            "HANDOFF": HandoffResult,
            "HEARTBEAT": Heartbeat,
            "CANCEL": CancelResult,
        }[self.operation]
        if not isinstance(self.payload, model):
            raise ValueError("Transport operation does not match payload type")
        return self


class CapabilityDescriptor(WireModel):
    capability: Capability
    supported: bool = True
