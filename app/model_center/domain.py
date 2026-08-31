from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID

from ..stable_identity import validate_uuid


class Capability(StrEnum):
    TEXT = "TEXT"; IMAGE = "IMAGE"; VIDEO = "VIDEO"; VISION = "VISION"
    TTS = "TTS"; AUDIO = "AUDIO"; EMBEDDING = "EMBEDDING"; RERANK = "RERANK"
    RESTORATION = "RESTORATION"; INTERPOLATION = "INTERPOLATION"


class ModelStatus(StrEnum):
    NOT_INSTALLED = "NOT_INSTALLED"; DISCOVERED = "DISCOVERED"; VALIDATING = "VALIDATING"
    READY = "READY"; DEGRADED = "DEGRADED"; INCOMPATIBLE = "INCOMPATIBLE"
    MISSING_COMPONENT = "MISSING_COMPONENT"; LICENSE_REQUIRED = "LICENSE_REQUIRED"
    RUNTIME_REQUIRED = "RUNTIME_REQUIRED"; DISABLED = "DISABLED"


class RuntimeType(StrEnum):
    LLAMA_CPP = "LLAMA_CPP"; COMFYUI = "COMFYUI"
    OPENAI_COMPATIBLE_LOCAL = "OPENAI_COMPATIBLE_LOCAL"; CUSTOM_HTTP = "CUSTOM_HTTP"


class RuntimeState(StrEnum):
    STOPPED = "STOPPED"; STARTING = "STARTING"; RUNNING = "RUNNING"
    DEGRADED = "DEGRADED"; FAILED = "FAILED"; EXTERNAL = "EXTERNAL"


class RuntimeManagement(StrEnum):
    MANAGED = "MANAGED"; EXTERNAL = "EXTERNAL"


@dataclass(frozen=True)
class ModelComponentDefinition:
    component_id: str; component_type: str; family: str; variant: str
    architecture: str; version: str; format: str; precision: str; hash: str = ""
    compatible_models: tuple[str, ...] = ()


@dataclass(frozen=True)
class HardwareProfile:
    id: str; model_id: str; gpu_name: str; vram_required: int | None = None
    vram_recommended: int | None = None; ram_required: int | None = None
    ram_recommended: int | None = None; context: int | None = None
    resolution: str | None = None; frames: int | None = None; fps: int | None = None
    offload_mode: str = "GPU_ONLY"; tested: bool = False; verified_at: str | None = None
    benchmark: dict[str, Any] = field(default_factory=dict); profile_kind: str = "SMOKE"


@dataclass(frozen=True)
class ModelDefinition:
    id: str; display_name: str; family: str; variant: str; version: str
    capabilities: tuple[Capability, ...]; runtime_type: RuntimeType; model_format: str
    quantization: str = ""; precision: str = ""; source: str = "LOCAL"
    license: str = "UNKNOWN"; local_paths: tuple[str, ...] = (); components: tuple[str, ...] = ()
    hardware_profiles: tuple[str, ...] = (); compatibility: dict[str, Any] = field(default_factory=dict)
    status: ModelStatus = ModelStatus.NOT_INSTALLED; metadata: dict[str, Any] = field(default_factory=dict)
    identity_id: UUID | None = None

    @property
    def model_uuid(self) -> UUID | None:
        return self.identity_id

    def __post_init__(self) -> None:
        if self.identity_id is not None:
            if not isinstance(self.identity_id, UUID):
                raise ValueError("model_id_MALFORMED")
            object.__setattr__(self, "identity_id", validate_uuid(self.identity_id, field="model_id"))


@dataclass(frozen=True)
class RuntimeDefinition:
    id: str; runtime_type: RuntimeType; executable: str = ""; base_url: str = ""
    bind_address: str = "127.0.0.1"; port: int | None = None; working_directory: str = ""
    launch_arguments: tuple[str, ...] = (); environment: dict[str, str] = field(default_factory=dict)
    health_endpoint: str = ""; capabilities: tuple[Capability, ...] = (); status: str = "CONFIGURED"
    provider_adapter: str = ""; management: RuntimeManagement = RuntimeManagement.MANAGED
    model_path: str = ""; context_size: int | None = None; gpu_layers: int | None = None
    threads: int | None = None; batch_size: int | None = None; extra_arguments: tuple[str, ...] = ()
    identity_id: UUID | None = None

    @property
    def runtime_uuid(self) -> UUID | None:
        return self.identity_id

    def __post_init__(self) -> None:
        if self.identity_id is not None:
            if not isinstance(self.identity_id, UUID):
                raise ValueError("runtime_id_MALFORMED")
            object.__setattr__(self, "identity_id", validate_uuid(self.identity_id, field="runtime_id"))


@dataclass
class RuntimeInstance:
    runtime_id: str; process_id: int | None = None; state: RuntimeState = RuntimeState.STOPPED
    base_url: str = ""; started_at: str | None = None; last_health_check: str | None = None
    health: dict[str, Any] = field(default_factory=dict); loaded_models: list[str] = field(default_factory=list)
    error: str | None = None; management: RuntimeManagement = RuntimeManagement.EXTERNAL
    process_alive: bool = False; http_reachable: bool = False; version: str | None = None
    latency_ms: float | None = None; last_success: str | None = None; last_failure: str | None = None
    safe_error_code: str | None = None


@dataclass(frozen=True)
class RuntimeCapabilitySnapshot:
    runtime_id: str; runtime_version: str | None; detected_at: str; runtime_state: RuntimeState
    capabilities: tuple[str, ...] = (); available_models: tuple[str, ...] = ()
    adapters: tuple[str, ...] = (); node_classes: tuple[str, ...] = (); warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModelValidationRecord:
    model_id: str; runtime_id: str; hardware_profile_id: str; validation_type: str
    status: str; timestamp: str; input_summary: str = ""; output_summary: str = ""
    benchmark: dict[str, Any] = field(default_factory=dict); error: str = ""; hash: str = ""
    runtime_version: str = ""; runtime_fingerprint: str = ""; gpu: str = ""

    @classmethod
    def now(cls, **values: Any) -> "ModelValidationRecord":
        return cls(timestamp=datetime.now(timezone.utc).isoformat(), **values)


@dataclass(frozen=True)
class PipelineDefinition:
    id: str; nodes: tuple[dict[str, Any], ...]; edges: tuple[dict[str, str], ...]
    input_contract: dict[str, Any]; output_contract: dict[str, Any]
    required_capabilities: tuple[str, ...]; fallbacks: tuple[dict[str, Any], ...] = ()
    hardware_requirements: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RoutingPolicy:
    id: str
    routes: dict[str, dict[str, str]]


@dataclass(frozen=True)
class RoutingDecision:
    capability: str
    model_id: str
    runtime_id: str
    provider_adapter: str


def serialize(value: Any) -> dict[str, Any]:
    return asdict(value)
