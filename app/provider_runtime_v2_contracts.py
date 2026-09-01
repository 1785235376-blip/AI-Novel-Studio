"""Metadata only. IDs are registry UUIDs, never names, endpoints or credentials."""
from enum import Enum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

NonNegative = Annotated[int, Field(ge=0)]
Positive = Annotated[int, Field(gt=0)]
Score = Annotated[int, Field(ge=0, le=100)]


class Contract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


class Modality(str, Enum):
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    TTS = "TTS"
    AUDIO = "AUDIO"
    EMBEDDING = "EMBEDDING"


class CredentialScope(str, Enum):
    SYSTEM = "SYSTEM"
    WORKSPACE = "WORKSPACE"
    USER = "USER"
    EXECUTION_NODE = "EXECUTION_NODE"


class PrivacyPolicy(str, Enum):
    DEVICE_ONLY = "DEVICE_ONLY"
    SELF_HOSTED_ONLY = "SELF_HOSTED_ONLY"
    TRUSTED_WORKSPACE_NODES = "TRUSTED_WORKSPACE_NODES"
    CLOUD_ALLOWED = "CLOUD_ALLOWED"


class Location(str, Enum):
    DEVICE = "DEVICE"
    SAME_USER_NODE = "SAME_USER_NODE"
    WORKSPACE_NODE = "WORKSPACE_NODE"
    CLOUD = "CLOUD"


class Preference(str, Enum):
    QUALITY = "QUALITY"
    COST = "COST"
    LATENCY = "LATENCY"


class AssetType(str, Enum):
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    AUDIO = "AUDIO"
    VECTOR = "VECTOR"


class ProviderIdentity(Contract):
    provider_id: UUID

    @field_validator("provider_id")
    @classmethod
    def nonzero(cls, value: UUID) -> UUID:
        if value.int == 0:
            raise ValueError("provider_id must not be zero UUID")
        return value


class ModelIdentity(Contract):
    model_id: UUID

    @field_validator("model_id")
    @classmethod
    def nonzero(cls, value: UUID) -> UUID:
        if value.int == 0:
            raise ValueError("model_id must not be zero UUID")
        return value


class RuntimeIdentity(Contract):
    runtime_id: UUID

    @field_validator("runtime_id")
    @classmethod
    def nonzero(cls, value: UUID) -> UUID:
        if value.int == 0:
            raise ValueError("runtime_id must not be zero UUID")
        return value


class ExecutionNodeIdentity(Contract):
    execution_node_id: UUID

    @field_validator("execution_node_id")
    @classmethod
    def nonzero(cls, value: UUID) -> UUID:
        if value.int == 0:
            raise ValueError("execution_node_id must not be zero UUID")
        return value


class RouteIdentity(Contract):
    provider: ProviderIdentity
    model: ModelIdentity
    runtime: RuntimeIdentity
    node: ExecutionNodeIdentity


class CredentialReference(Contract):
    # Random registry handle; not a bearer token, secret value or retrieval URL.
    handle: UUID
    scope: CredentialScope
    scope_id: UUID | None = None

    @model_validator(mode="after")
    def scoped(self):
        if (self.scope == CredentialScope.SYSTEM) != (self.scope_id is None):
            raise ValueError("SYSTEM has no scope_id; other scopes require one")
        return self


class CredentialAvailability(Contract):
    reference: CredentialReference
    provider: ProviderIdentity
    available: bool
    authorized: bool


class Availability(Contract):
    configured: bool
    installed: bool
    healthy: bool
    reachable: bool
    authorized: bool
    compatible: bool


class RuntimeRequirements(Contract):
    # Registry IDs permit future families/architectures without arbitrary strings.
    runtime_family_id: UUID
    architecture_id: UUID
    gpu_vendor_id: UUID | None = None
    minimum_vram_mib: NonNegative = 0
    minimum_ram_mib: NonNegative = 0


class HardwareSnapshot(Contract):
    node: ExecutionNodeIdentity
    architecture_id: UUID
    gpu_vendor_id: UUID | None = None
    vram_mib: NonNegative
    ram_mib: NonNegative
    runtime_family_ids: frozenset[UUID]


class CapabilityDescriptor(Contract):
    supported_modalities: frozenset[Modality] = Field(min_length=1)
    input_asset_types: frozenset[AssetType]
    output_asset_types: frozenset[AssetType]
    streaming: bool = False
    batch: bool = False
    max_context_tokens: Positive | None = None
    max_output_tokens: Positive | None = None
    estimated_vram_mib: NonNegative | None = None
    estimated_ram_mib: NonNegative | None = None
    quantization_id: UUID | None = None
    requirements: RuntimeRequirements


class RequiredCapabilities(Contract):
    input_asset_types: frozenset[AssetType] = frozenset()
    output_asset_types: frozenset[AssetType] = frozenset()
    streaming: bool = False
    batch: bool = False
    context_tokens: Positive | None = None
    output_tokens: Positive | None = None


class CandidateDescriptor(Contract):
    identity: RouteIdentity
    location: Location
    owner_user_id: UUID | None = None
    workspace_id: UUID | None = None
    trusted: bool = False
    self_hosted: bool = False
    availability: Availability
    capabilities: CapabilityDescriptor
    credential: CredentialReference | None = None
    # Per-request normalized estimates; None is unknown, never free/fast/high quality.
    estimated_cost_microusd: NonNegative | None = None
    estimated_latency_ms: NonNegative | None = None
    quality_score: Score | None = None


class CloudApproval(Contract):
    identity: RouteIdentity
    user_id: UUID
    workspace_id: UUID
    maximum_cost_microusd: NonNegative


class BudgetPolicy(Contract):
    maximum_cost_microusd: NonNegative = 0
    approvals: tuple[CloudApproval, ...] = ()


class ProviderRoutingRequest(Contract):
    modality: Modality
    required: RequiredCapabilities = RequiredCapabilities()
    workspace_id: UUID
    user_id: UUID
    local_node: ExecutionNodeIdentity
    privacy: PrivacyPolicy
    budget: BudgetPolicy = BudgetPolicy()
    candidate_locations: frozenset[Location] = frozenset({Location.DEVICE})
    # Lexicographic order, after execution location; no weighted score.
    preferences: tuple[Preference, ...] = (Preference.COST, Preference.LATENCY, Preference.QUALITY)

    @model_validator(mode="after")
    def unique_preferences(self):
        if len(self.preferences) != len(set(self.preferences)):
            raise ValueError("preference dimensions must be unique")
        return self


class Decision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    NO_COMPATIBLE_ROUTE = "NO_COMPATIBLE_ROUTE"
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL"


class ReasonCode(str, Enum):
    SELECTED = "SELECTED"
    NO_CANDIDATES = "NO_CANDIDATES"
    NO_ELIGIBLE_CANDIDATE = "NO_ELIGIBLE_CANDIDATE"
    CLOUD_COST_APPROVAL = "CLOUD_COST_APPROVAL"
    CONFLICTING_FACTS = "CONFLICTING_FACTS"


class ProviderRoutingDecision(Contract):
    decision: Decision
    identity: RouteIdentity | None = None
    credential_handle: UUID | None = None
    reason_code: ReasonCode
    policy_version: Literal["2.0-contract-1"] = "2.0-contract-1"

    @model_validator(mode="after")
    def consistent(self):
        selected = self.decision in (Decision.ALLOW, Decision.REQUIRES_APPROVAL)
        if selected != (self.identity is not None):
            raise ValueError("only selected decisions carry a route")
        if self.decision != Decision.ALLOW and self.credential_handle is not None:
            raise ValueError("only ALLOW carries a credential handle")
        reasons = {
            Decision.ALLOW: {ReasonCode.SELECTED},
            Decision.REQUIRES_APPROVAL: {ReasonCode.CLOUD_COST_APPROVAL},
            Decision.DENY: {ReasonCode.CONFLICTING_FACTS},
            Decision.NO_COMPATIBLE_ROUTE: {ReasonCode.NO_CANDIDATES, ReasonCode.NO_ELIGIBLE_CANDIDATE},
        }
        if self.reason_code not in reasons[self.decision]:
            raise ValueError("decision and reason must agree")
        return self
