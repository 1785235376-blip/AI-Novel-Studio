"""Read-only Model Center -> Provider Runtime fact bridge.

The bridge deliberately stops at immutable metadata.  It does not execute a
provider, probe a runtime, consult credentials, or mutate the identity store.
"""

from __future__ import annotations

import platform
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable
from uuid import UUID

from .model_center.domain import Capability, ModelDefinition, ModelStatus, RuntimeDefinition, RuntimeManagement, RuntimeType, RuntimeState
from .model_runtime import ModelDescriptor, ModelRegistry, ProviderDescriptor, ProviderRegistry
from .provider_runtime_v2_contracts import (
    AssetType,
    Availability,
    CandidateDescriptor,
    CapabilityDescriptor,
    ExecutionNodeIdentity,
    Location,
    Modality,
    ModelIdentity,
    ProviderIdentity,
    RouteIdentity,
    RuntimeIdentity,
    RuntimeRequirements,
)
from .stable_identity import (
    ARCHITECTURE_ARM64,
    ARCHITECTURE_X86_64,
    RUNTIME_FAMILY_COMFYUI,
    RUNTIME_FAMILY_LLAMA_CPP,
    validate_uuid,
)


class SnapshotRejectionCode(StrEnum):
    MISSING_PROVIDER_IDENTITY = "MISSING_PROVIDER_IDENTITY"
    MISSING_MODEL_IDENTITY = "MISSING_MODEL_IDENTITY"
    MISSING_RUNTIME_IDENTITY = "MISSING_RUNTIME_IDENTITY"
    MISSING_EXECUTION_NODE_IDENTITY = "MISSING_EXECUTION_NODE_IDENTITY"
    INVALID_IDENTITY = "INVALID_IDENTITY"
    UNKNOWN_CAPABILITY = "UNKNOWN_CAPABILITY"
    UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"
    DUPLICATE_RUNTIME_IDENTITY = "DUPLICATE_RUNTIME_IDENTITY"
    CONFLICTING_RUNTIME_FACTS = "CONFLICTING_RUNTIME_FACTS"
    DUPLICATE_CANDIDATE_IDENTITY = "DUPLICATE_CANDIDATE_IDENTITY"
    UNKNOWN_AVAILABILITY = "UNKNOWN_AVAILABILITY"
    UNTRUSTED_SOURCE = "UNTRUSTED_SOURCE"
    MISSING_REQUIRED_HARDWARE_FACT = "MISSING_REQUIRED_HARDWARE_FACT"


@dataclass(frozen=True, slots=True)
class SnapshotRejection:
    code: SnapshotRejectionCode
    source_key: str
    detail: str = ""

    def to_dict(self) -> dict[str, str]:
        value = {"code": self.code.value, "source_key": self.source_key}
        if self.detail:
            value["detail"] = self.detail
        return value


@dataclass(frozen=True, slots=True)
class SnapshotItem:
    """A source item is structurally either accepted or rejected."""

    source_key: str
    candidate: CandidateDescriptor | None = None
    rejection: SnapshotRejection | None = None

    def __post_init__(self) -> None:
        if (self.candidate is None) == (self.rejection is None):
            raise ValueError("snapshot item must contain exactly one candidate or rejection")

    @property
    def accepted(self) -> CandidateDescriptor | None:
        return self.candidate

    @property
    def rejected(self) -> SnapshotRejection | None:
        return self.rejection


@dataclass(frozen=True, slots=True)
class ProviderRuntimeSnapshot:
    version: str
    items: tuple[SnapshotItem, ...]

    @property
    def candidates(self) -> tuple[CandidateDescriptor, ...]:
        return tuple(item.candidate for item in self.items if item.candidate is not None)

    @property
    def accepted_candidates(self) -> tuple[CandidateDescriptor, ...]:
        return self.candidates

    @property
    def rejections(self) -> tuple[SnapshotRejection, ...]:
        return tuple(item.rejection for item in self.items if item.rejection is not None)

    @property
    def rejected(self) -> tuple[SnapshotRejection, ...]:
        return self.rejections

    def to_dict(self) -> dict[str, Any]:
        def uuid_value(value: Any) -> Any:
            if isinstance(value, UUID):
                return str(value)
            if isinstance(value, (set, frozenset, tuple)):
                return sorted((uuid_value(item) for item in value), key=str)
            if hasattr(value, "value") and isinstance(value.value, str):
                return value.value
            if hasattr(value, "model_dump"):
                return uuid_value(value.model_dump(mode="python"))
            if isinstance(value, dict):
                return {str(key): uuid_value(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
            return value

        return {
            "version": self.version,
            "items": [
                {
                    "source_key": item.source_key,
                    **({"candidate": uuid_value(item.candidate)} if item.candidate else {"rejection": item.rejection.to_dict()}),
                }
                for item in self.items
            ],
        }

    def serialize(self) -> dict[str, Any]:
        return self.to_dict()


_CAPABILITY_MAP: dict[Capability, tuple[Modality, frozenset[AssetType], frozenset[AssetType]]] = {
    Capability.TEXT: (Modality.TEXT, frozenset({AssetType.TEXT}), frozenset({AssetType.TEXT})),
    Capability.IMAGE: (Modality.IMAGE, frozenset({AssetType.TEXT}), frozenset({AssetType.IMAGE})),
    Capability.VIDEO: (Modality.VIDEO, frozenset({AssetType.TEXT}), frozenset({AssetType.VIDEO})),
    Capability.TTS: (Modality.TTS, frozenset({AssetType.TEXT}), frozenset({AssetType.AUDIO})),
    Capability.AUDIO: (Modality.AUDIO, frozenset({AssetType.AUDIO}), frozenset({AssetType.AUDIO})),
    Capability.EMBEDDING: (Modality.EMBEDDING, frozenset({AssetType.TEXT}), frozenset({AssetType.VECTOR})),
}

_RUNTIME_FAMILY = {
    RuntimeType.LLAMA_CPP: RUNTIME_FAMILY_LLAMA_CPP.taxonomy_id,
    RuntimeType.COMFYUI: RUNTIME_FAMILY_COMFYUI.taxonomy_id,
}


def _architecture_id() -> UUID | None:
    value = platform.machine().casefold().replace("-", "_")
    if value in {"x86_64", "amd64"}:
        return ARCHITECTURE_X86_64.taxonomy_id
    if value in {"aarch64", "arm64"}:
        return ARCHITECTURE_ARM64.taxonomy_id
    return None


def _identity(value: Any, field: str) -> UUID | None:
    if value is None:
        return None
    try:
        return validate_uuid(value, field=field)
    except Exception:
        return None


def _node_id(node_store: Any) -> UUID | None:
    """Read an existing node identity; never call get_or_create here."""
    store = getattr(node_store, "store", node_store)
    getter = getattr(store, "get", None)
    if not callable(getter):
        return None
    return _identity(getter("execution_node", "local"), "execution_node_id")


def _provider_key(runtime: RuntimeDefinition) -> str | None:
    return {RuntimeType.LLAMA_CPP: "ollama", RuntimeType.COMFYUI: "comfyui"}.get(runtime.runtime_type)


def _availability(model: ModelDefinition, runtime: RuntimeDefinition, lifecycle: Any) -> Availability:
    instance = getattr(lifecycle, "instances", {}).get(runtime.id)
    running = bool(instance and getattr(instance, "state", None) is RuntimeState.RUNNING)
    reachable = bool(instance and getattr(instance, "http_reachable", False))
    health = bool(instance and isinstance(getattr(instance, "health", None), dict) and instance.health.get("healthy", False))
    installed = model.status in {ModelStatus.READY, ModelStatus.DEGRADED, ModelStatus.DISABLED, ModelStatus.INCOMPATIBLE}
    configured = str(runtime.status).upper() in {"CONFIGURED", "READY", "RUNNING"}
    authorized = runtime.management is RuntimeManagement.MANAGED
    compatible = model.status is not ModelStatus.INCOMPATIBLE and runtime.runtime_type in _RUNTIME_FAMILY
    return Availability(configured=configured, installed=installed, healthy=health and running, reachable=reachable, authorized=authorized, compatible=compatible)


def _capability(model: ModelDefinition, runtime: RuntimeDefinition, architecture: UUID) -> CapabilityDescriptor | SnapshotRejectionCode:
    mapped = []
    for raw in model.capabilities:
        try:
            capability = raw if isinstance(raw, Capability) else Capability(str(raw))
        except (TypeError, ValueError):
            return SnapshotRejectionCode.UNKNOWN_CAPABILITY
        item = _CAPABILITY_MAP.get(capability)
        if item is None:
            return SnapshotRejectionCode.UNSUPPORTED_CAPABILITY
        mapped.append(item)
    if not mapped:
        return SnapshotRejectionCode.UNKNOWN_CAPABILITY
    modalities = frozenset(item[0] for item in mapped)
    inputs = frozenset(asset for item in mapped for asset in item[1])
    outputs = frozenset(asset for item in mapped for asset in item[2])
    family = _RUNTIME_FAMILY.get(runtime.runtime_type)
    if family is None:
        return SnapshotRejectionCode.UNSUPPORTED_CAPABILITY
    return CapabilityDescriptor(
        supported_modalities=modalities,
        input_asset_types=inputs,
        output_asset_types=outputs,
        streaming=Capability.TEXT in model.capabilities,
        requirements=RuntimeRequirements(runtime_family_id=family, architecture_id=architecture),
    )


def build_provider_runtime_snapshot(
    provider_registry: ProviderRegistry,
    model_registry: ModelRegistry,
    model_center: Any,
    execution_node_identity: Any,
) -> ProviderRuntimeSnapshot:
    """Build a snapshot from already-owned services (internal/test seam)."""
    items: list[SnapshotItem] = []
    provider_descriptors = list(provider_registry.descriptors())
    providers = {item.provider_id: item for item in provider_descriptors}
    provider_conflicts: set[str] = set()
    for index, item in enumerate(provider_descriptors):
        for other in provider_descriptors[index + 1 :]:
            if item.provider_id == other.provider_id and item != other:
                provider_conflicts.add(item.provider_id)
            if item.identity_id is not None and item.identity_id == other.identity_id and item.provider_id != other.provider_id:
                provider_conflicts.update((item.provider_id, other.provider_id))
    model_descriptors = list(model_registry.descriptors())
    models = {(item.provider_id, item.model_id): item for item in model_descriptors}
    model_conflicts: set[tuple[str, str]] = set()
    for index, item in enumerate(model_descriptors):
        for other in model_descriptors[index + 1 :]:
            if (item.provider_id, item.model_id) == (other.provider_id, other.model_id) and item != other:
                model_conflicts.add((item.provider_id, item.model_id))
            if item.identity_id is not None and item.identity_id == other.identity_id and (item.provider_id, item.model_id) != (other.provider_id, other.model_id):
                model_conflicts.update(((item.provider_id, item.model_id), (other.provider_id, other.model_id)))
    runtime_source = getattr(model_center, "runtimes", {})
    runtime_values = list(runtime_source.values()) if isinstance(runtime_source, dict) else list(runtime_source)
    runtimes: dict[str, RuntimeDefinition] = {item.id: item for item in runtime_values}
    lifecycle = getattr(model_center, "lifecycle", None)
    architecture = _architecture_id()
    node_uuid = _node_id(execution_node_identity)
    duplicate_runtime_ids: set[UUID] = set()
    conflicting_runtime_keys: set[str] = set()
    seen_runtime: dict[UUID, str] = {}
    runtime_identity_counts: dict[UUID, int] = {}
    seen_runtime_values: dict[str, RuntimeDefinition] = {}
    for runtime in sorted(runtime_values, key=lambda value: value.id):
        rid = _identity(runtime.identity_id, "runtime_id")
        if rid is not None:
            runtime_identity_counts[rid] = runtime_identity_counts.get(rid, 0) + 1
        if rid is not None and rid in seen_runtime and seen_runtime[rid] != runtime.id:
            duplicate_runtime_ids.add(rid)
        elif rid is not None:
            seen_runtime[rid] = runtime.id
        if runtime.id in seen_runtime_values and seen_runtime_values[runtime.id] != runtime:
            conflicting_runtime_keys.add(runtime.id)
        seen_runtime_values[runtime.id] = runtime
    duplicate_runtime_ids.update(rid for rid, count in runtime_identity_counts.items() if count > 1)

    for model in sorted(getattr(model_center, "models", {}).values(), key=lambda value: value.id):
        provider_key = _provider_key_for_model(model, runtimes)
        source_prefix = f"{provider_key or '?'}:{model.id}"
        if provider_key is None or provider_key not in providers or provider_key in provider_conflicts:
            items.append(SnapshotItem(source_prefix, rejection=SnapshotRejection(SnapshotRejectionCode.MISSING_PROVIDER_IDENTITY, source_prefix)))
            continue
        provider = providers[provider_key]
        provider_uuid = _identity(provider.identity_id, "provider_id")
        registry_model = models.get((provider_key, model.id))
        model_uuid = _identity(model.identity_id, "model_id")
        registry_model_uuid = _identity(getattr(registry_model, "identity_id", None), "model_id")
        if provider_uuid is None:
            items.append(SnapshotItem(source_prefix, rejection=SnapshotRejection(SnapshotRejectionCode.MISSING_PROVIDER_IDENTITY, source_prefix)))
            continue
        if model_uuid is None or registry_model is None or registry_model_uuid is None or model_uuid != registry_model_uuid or (provider_key, model.id) in model_conflicts:
            items.append(SnapshotItem(source_prefix, rejection=SnapshotRejection(SnapshotRejectionCode.MISSING_MODEL_IDENTITY, source_prefix)))
            continue
        capability_error = _capability_declaration_error(model)
        if capability_error is not None:
            items.append(SnapshotItem(source_prefix, rejection=SnapshotRejection(capability_error, source_prefix)))
            continue
        runtime_candidates = [runtime for runtime in runtimes.values() if runtime.runtime_type is model.runtime_type and any(cap in runtime.capabilities for cap in model.capabilities)]
        if not runtime_candidates:
            items.append(SnapshotItem(source_prefix, rejection=SnapshotRejection(SnapshotRejectionCode.MISSING_RUNTIME_IDENTITY, source_prefix)))
            continue
        for runtime in sorted(runtime_candidates, key=lambda value: value.id):
            source_key = f"{provider_key}:{model.id}:{runtime.id}"
            runtime_uuid = _identity(runtime.identity_id, "runtime_id")
            if runtime_uuid is None:
                items.append(SnapshotItem(source_key, rejection=SnapshotRejection(SnapshotRejectionCode.MISSING_RUNTIME_IDENTITY, source_key)))
                continue
            if runtime_uuid in duplicate_runtime_ids or runtime.id in conflicting_runtime_keys:
                items.append(SnapshotItem(source_key, rejection=SnapshotRejection(SnapshotRejectionCode.DUPLICATE_RUNTIME_IDENTITY, source_key)))
                continue
            if node_uuid is None:
                items.append(SnapshotItem(source_key, rejection=SnapshotRejection(SnapshotRejectionCode.MISSING_EXECUTION_NODE_IDENTITY, source_key)))
                continue
            if architecture is None:
                items.append(SnapshotItem(source_key, rejection=SnapshotRejection(SnapshotRejectionCode.MISSING_REQUIRED_HARDWARE_FACT, source_key)))
                continue
            capability = _capability(model, runtime, architecture)
            if isinstance(capability, SnapshotRejectionCode):
                items.append(SnapshotItem(source_key, rejection=SnapshotRejection(capability, source_key)))
                continue
            availability = _availability(model, runtime, lifecycle)
            candidate = CandidateDescriptor(
                identity=RouteIdentity(
                    provider=ProviderIdentity(provider_id=provider_uuid),
                    model=ModelIdentity(model_id=model_uuid),
                    runtime=RuntimeIdentity(runtime_id=runtime_uuid),
                    node=ExecutionNodeIdentity(execution_node_id=node_uuid),
                ),
                location=Location.DEVICE if runtime.management is RuntimeManagement.MANAGED else Location.WORKSPACE_NODE,
                trusted=runtime.management is RuntimeManagement.MANAGED,
                self_hosted=runtime.management is RuntimeManagement.MANAGED,
                availability=availability,
                capabilities=capability,
            )
            items.append(SnapshotItem(source_key, candidate=candidate))

    # Stable source ordering makes input iteration order irrelevant.
    items.sort(key=lambda item: item.source_key)
    return ProviderRuntimeSnapshot(version="2.1A-snapshot-1", items=tuple(items))


def _provider_key_for_model(model: ModelDefinition, runtimes: dict[str, RuntimeDefinition]) -> str | None:
    for runtime in runtimes.values():
        if runtime.runtime_type is model.runtime_type:
            return _provider_key(runtime)
    return _provider_key(RuntimeDefinition("", model.runtime_type))


def _capability_declaration_error(model: ModelDefinition) -> SnapshotRejectionCode | None:
    if not model.capabilities:
        return SnapshotRejectionCode.UNKNOWN_CAPABILITY
    for raw in model.capabilities:
        try:
            capability = raw if isinstance(raw, Capability) else Capability(str(raw))
        except (TypeError, ValueError):
            return SnapshotRejectionCode.UNKNOWN_CAPABILITY
        if capability not in _CAPABILITY_MAP:
            return SnapshotRejectionCode.UNSUPPORTED_CAPABILITY
    return None


def create_provider_runtime_snapshot() -> ProviderRuntimeSnapshot:
    """Trusted production entrypoint; authority is acquired from Host wiring."""
    from . import dependencies

    return build_provider_runtime_snapshot(
        dependencies.runtime.provider_registry,
        dependencies.runtime.model_registry,
        dependencies.model_center_service,
        dependencies.runtime.execution_node_identity,
    )


# Short aliases for callers migrating from early review terminology.
build_snapshot = build_provider_runtime_snapshot
create_snapshot = create_provider_runtime_snapshot
