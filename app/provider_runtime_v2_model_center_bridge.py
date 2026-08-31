"""Read-only Model Center -> Provider Runtime 2.0 snapshot bridge.

This module normalizes already-resident Model Center facts into Provider Runtime
2.0 snapshot types. It does not execute models, start or stop runtimes, resolve
credentials, touch Vault, probe the network, spawn subprocesses, or mutate
Model Center / Provider Runtime contracts.

Identity rule: RouteIdentity requires registry UUIDs. Model Center currently
exposes string slugs (model/runtime ids), adapter names (provider_adapter), and
no ExecutionNodeIdentity. This bridge never hashes those strings into UUIDs and
never mints random identities. Missing identities fail closed: candidates,
hardware snapshots, and credentials are empty.
"""
from __future__ import annotations

import ipaddress
from enum import Enum
from typing import Any, Literal, Mapping
from uuid import UUID

from app.provider_runtime_v2_contracts import (
    AssetType,
    Availability,
    CandidateDescriptor,
    Contract,
    CredentialAvailability,
    HardwareSnapshot,
    Location,
    Modality,
)

BRIDGE_VERSION = "2.1A-snapshot-1"
_LOOPBACK_LITERALS = frozenset({"127.0.0.1", "::1"})
_MODEL_NOT_INSTALLED = frozenset({
    "NOT_INSTALLED", "MISSING_COMPONENT", "RUNTIME_REQUIRED", "LICENSE_REQUIRED",
})
_MAPPED_MODALITIES = {
    "TEXT": Modality.TEXT,
    "IMAGE": Modality.IMAGE,
    "VIDEO": Modality.VIDEO,
    "TTS": Modality.TTS,
    "AUDIO": Modality.AUDIO,
    "EMBEDDING": Modality.EMBEDDING,
}
_MODALITY_ASSETS = {
    Modality.TEXT: AssetType.TEXT,
    Modality.IMAGE: AssetType.IMAGE,
    Modality.VIDEO: AssetType.VIDEO,
    Modality.TTS: AssetType.AUDIO,
    Modality.AUDIO: AssetType.AUDIO,
}
_OVERRIDE_TRUST_KEYS = frozenset({
    "trusted", "authorized", "healthy", "compatible", "installed", "reachable",
    "configured", "plugin_trust", "plugin_verified", "verified", "trust_decision",
    "execution_supported",
})
_OVERRIDE_CREDENTIAL_KEYS = frozenset({
    "credential", "credentials", "api_key", "token", "secret", "vault", "password",
    "credential_handle",
})
_OVERRIDE_TEAM_KEYS = frozenset({
    "team_compute", "same_user_node", "workspace_node", "cloud", "location",
    "execution_fabric", "execution_node_id", "execution_node",
})
_UNAVAILABLE = Availability(
    configured=False, installed=False, healthy=False,
    reachable=False, authorized=False, compatible=False,
)


class SnapshotReason(str, Enum):
    MISSING_PROVIDER_IDENTITY = "MISSING_PROVIDER_IDENTITY"
    MISSING_MODEL_IDENTITY = "MISSING_MODEL_IDENTITY"
    MISSING_RUNTIME_IDENTITY = "MISSING_RUNTIME_IDENTITY"
    MISSING_EXECUTION_NODE_IDENTITY = "MISSING_EXECUTION_NODE_IDENTITY"
    UNKNOWN_CAPABILITY = "UNKNOWN_CAPABILITY"
    MISSING_HARDWARE_FACT = "MISSING_HARDWARE_FACT"
    RUNTIME_NOT_CONFIGURED = "RUNTIME_NOT_CONFIGURED"
    RUNTIME_NOT_INSTALLED = "RUNTIME_NOT_INSTALLED"
    RUNTIME_UNHEALTHY = "RUNTIME_UNHEALTHY"
    RUNTIME_UNREACHABLE = "RUNTIME_UNREACHABLE"
    RUNTIME_UNAUTHORIZED = "RUNTIME_UNAUTHORIZED"
    RUNTIME_INCOMPATIBLE = "RUNTIME_INCOMPATIBLE"
    UNSUPPORTED_MODALITY = "UNSUPPORTED_MODALITY"
    UNTRUSTED_CALLER_OVERRIDE = "UNTRUSTED_CALLER_OVERRIDE"
    CREDENTIAL_RESOLUTION_FORBIDDEN = "CREDENTIAL_RESOLUTION_FORBIDDEN"
    PLUGIN_TRUST_SUBSTITUTION_FORBIDDEN = "PLUGIN_TRUST_SUBSTITUTION_FORBIDDEN"
    TEAM_COMPUTE_SUBSTITUTION_FORBIDDEN = "TEAM_COMPUTE_SUBSTITUTION_FORBIDDEN"
    UNSUPPORTED_LOCATION = "UNSUPPORTED_LOCATION"


class ModelCenterModelFact(Contract):
    registry_id: str
    runtime_type: str
    status: str
    capabilities: tuple[str, ...] = ()
    family: str = ""
    quantization: str = ""
    context_tokens: int | None = None


class ModelCenterRuntimeFact(Contract):
    registry_id: str
    runtime_type: str
    status: str = "CONFIGURED"
    provider_adapter: str = ""
    management: str = "MANAGED"
    bind_address: str = ""
    capabilities: tuple[str, ...] = ()
    context_size: int | None = None


class ModelCenterInstanceFact(Contract):
    runtime_registry_id: str
    state: str = "STOPPED"
    process_alive: bool = False
    http_reachable: bool = False


class ModelCenterHardwareFact(Contract):
    profile_id: str
    model_registry_id: str
    vram_required: int | None = None
    ram_required: int | None = None
    context: int | None = None
    tested: bool = False


class ModelCenterFactSource(Contract):
    """Sanitized, immutable Model Center facts. No processes, paths, env, or secrets."""
    models: tuple[ModelCenterModelFact, ...]
    runtimes: tuple[ModelCenterRuntimeFact, ...]
    instances: tuple[ModelCenterInstanceFact, ...] = ()
    hardware_profiles: tuple[ModelCenterHardwareFact, ...] = ()


class SnapshotRejection(Contract):
    reasons: tuple[SnapshotReason, ...]
    model_registry_id: str | None = None
    runtime_registry_id: str | None = None
    availability: Availability = _UNAVAILABLE
    location: Location | None = None
    mapped_modalities: frozenset[Modality] = frozenset()
    unknown_capabilities: frozenset[str] = frozenset()
    input_asset_types: frozenset[AssetType] = frozenset()
    output_asset_types: frozenset[AssetType] = frozenset()


class ProviderRuntimeSnapshotBundle(Contract):
    bridge_version: Literal["2.1A-snapshot-1"] = BRIDGE_VERSION
    candidates: tuple[CandidateDescriptor, ...] = ()
    hardware: tuple[HardwareSnapshot, ...] = ()
    credentials: tuple[CredentialAvailability, ...] = ()
    rejections: tuple[SnapshotRejection, ...] = ()


def capture_model_center_facts(service: Any) -> ModelCenterFactSource:
    """Copy already-resident Model Center registry/instance facts. No I/O."""
    raw_profiles = getattr(service, "profiles", {}) or {}
    profile_items = tuple(raw_profiles.values()) if isinstance(raw_profiles, dict) else tuple(raw_profiles)
    context_by_model: dict[str, int] = {}
    hardware = []
    for profile in profile_items:
        model_id = str(getattr(profile, "model_id", "") or "")
        context = getattr(profile, "context", None)
        hardware.append(ModelCenterHardwareFact(
            profile_id=str(getattr(profile, "id", "") or ""),
            model_registry_id=model_id,
            vram_required=getattr(profile, "vram_required", None),
            ram_required=getattr(profile, "ram_required", None),
            context=context if isinstance(context, int) else None,
            tested=bool(getattr(profile, "tested", False)),
        ))
        if model_id and isinstance(context, int) and context > 0 and model_id not in context_by_model:
            context_by_model[model_id] = context
    models = []
    raw_models = getattr(service, "models", {}) or {}
    model_items = tuple(raw_models.values()) if isinstance(raw_models, dict) else tuple(raw_models)
    for model in model_items:
        registry_id = str(getattr(model, "id", "") or "")
        capabilities = tuple(str(item) for item in (getattr(model, "capabilities", ()) or ()))
        models.append(ModelCenterModelFact(
            registry_id=registry_id,
            runtime_type=str(getattr(model, "runtime_type", "") or ""),
            status=str(getattr(model, "status", "") or ""),
            capabilities=capabilities,
            family=str(getattr(model, "family", "") or ""),
            quantization=str(getattr(model, "quantization", "") or ""),
            context_tokens=context_by_model.get(registry_id),
        ))
    runtimes = []
    raw_runtimes = getattr(service, "runtimes", {}) or {}
    runtime_items = tuple(raw_runtimes.values()) if isinstance(raw_runtimes, dict) else tuple(raw_runtimes)
    for runtime in runtime_items:
        context_size = getattr(runtime, "context_size", None)
        runtimes.append(ModelCenterRuntimeFact(
            registry_id=str(getattr(runtime, "id", "") or ""),
            runtime_type=str(getattr(runtime, "runtime_type", "") or ""),
            status=str(getattr(runtime, "status", "") or ""),
            provider_adapter=str(getattr(runtime, "provider_adapter", "") or ""),
            management=str(getattr(runtime, "management", "") or ""),
            bind_address=str(getattr(runtime, "bind_address", "") or ""),
            capabilities=tuple(str(item) for item in (getattr(runtime, "capabilities", ()) or ())),
            context_size=context_size if isinstance(context_size, int) else None,
        ))
    instances = []
    lifecycle = getattr(service, "lifecycle", None)
    stored = getattr(lifecycle, "instances", {}) if lifecycle is not None else {}
    for runtime_id, instance in (stored or {}).items():
        instances.append(ModelCenterInstanceFact(
            runtime_registry_id=str(runtime_id),
            state=str(getattr(instance, "state", "") or ""),
            process_alive=bool(getattr(instance, "process_alive", False)),
            http_reachable=bool(getattr(instance, "http_reachable", False)),
        ))
    return ModelCenterFactSource(
        models=tuple(sorted(models, key=lambda item: item.registry_id)),
        runtimes=tuple(sorted(runtimes, key=lambda item: item.registry_id)),
        instances=tuple(sorted(instances, key=lambda item: item.runtime_registry_id)),
        hardware_profiles=tuple(sorted(hardware, key=lambda item: (item.model_registry_id, item.profile_id))),
    )


def _registry_uuid(value: str) -> UUID | None:
    text = (value or "").strip()
    if not text or any(mark in text for mark in ("/", "\\", "://", " ", "\n")):
        return None
    try:
        parsed = UUID(text)
    except (ValueError, AttributeError, TypeError):
        return None
    return parsed


def _loopback_location(bind_address: str) -> Location | None:
    text = (bind_address or "").strip()
    if text in _LOOPBACK_LITERALS:
        return Location.DEVICE
    try:
        if ipaddress.ip_address(text).is_loopback:
            return Location.DEVICE
    except ValueError:
        return None
    return None


def _capabilities(declared: tuple[str, ...]) -> tuple[frozenset[Modality], frozenset[str], frozenset[AssetType]]:
    mapped: set[Modality] = set()
    unknown: set[str] = set()
    for item in declared:
        name = str(item)
        modality = _MAPPED_MODALITIES.get(name)
        if modality is None:
            unknown.add(name)
        else:
            mapped.add(modality)
    assets = frozenset(_MODALITY_ASSETS[item] for item in mapped if item in _MODALITY_ASSETS)
    return frozenset(mapped), frozenset(unknown), assets


def _availability(model: ModelCenterModelFact, runtime: ModelCenterRuntimeFact, instance: ModelCenterInstanceFact | None) -> Availability:
    configured = runtime.status == "CONFIGURED"
    model_installed = bool(model.status) and model.status not in _MODEL_NOT_INSTALLED
    if instance is None:
        runtime_installed = False
        healthy = False
        reachable = False
    else:
        runtime_installed = instance.process_alive or instance.http_reachable
        reachable = instance.http_reachable
        if instance.state == "EXTERNAL":
            healthy = instance.http_reachable
        else:
            healthy = instance.state == "RUNNING" and instance.process_alive
    return Availability(
        configured=configured,
        installed=model_installed and runtime_installed,
        healthy=healthy,
        reachable=reachable,
        authorized=False,
        compatible=False,
    )


def _override_reasons(overrides: Mapping[str, Any] | None) -> tuple[SnapshotReason, ...]:
    if not overrides:
        return ()
    keys = {str(key).casefold() for key in overrides}
    reasons = [SnapshotReason.UNTRUSTED_CALLER_OVERRIDE]
    if keys & {item.casefold() for item in _OVERRIDE_CREDENTIAL_KEYS}:
        reasons.append(SnapshotReason.CREDENTIAL_RESOLUTION_FORBIDDEN)
    if keys & {item.casefold() for item in _OVERRIDE_TRUST_KEYS}:
        reasons.append(SnapshotReason.PLUGIN_TRUST_SUBSTITUTION_FORBIDDEN)
    if keys & {item.casefold() for item in _OVERRIDE_TEAM_KEYS}:
        reasons.append(SnapshotReason.TEAM_COMPUTE_SUBSTITUTION_FORBIDDEN)
    return tuple(dict.fromkeys(reasons))


def _route_reasons(
    model: ModelCenterModelFact,
    runtime: ModelCenterRuntimeFact,
    availability: Availability,
    location: Location | None,
    mapped: frozenset[Modality],
    unknown: frozenset[str],
) -> tuple[SnapshotReason, ...]:
    reasons: list[SnapshotReason] = []
    if _registry_uuid(runtime.provider_adapter) is None:
        reasons.append(SnapshotReason.MISSING_PROVIDER_IDENTITY)
    if _registry_uuid(model.registry_id) is None:
        reasons.append(SnapshotReason.MISSING_MODEL_IDENTITY)
    if _registry_uuid(runtime.registry_id) is None:
        reasons.append(SnapshotReason.MISSING_RUNTIME_IDENTITY)
    reasons.append(SnapshotReason.MISSING_EXECUTION_NODE_IDENTITY)
    reasons.append(SnapshotReason.MISSING_HARDWARE_FACT)
    if not availability.configured:
        reasons.append(SnapshotReason.RUNTIME_NOT_CONFIGURED)
    if not availability.installed:
        reasons.append(SnapshotReason.RUNTIME_NOT_INSTALLED)
    if not availability.healthy:
        reasons.append(SnapshotReason.RUNTIME_UNHEALTHY)
    if not availability.reachable:
        reasons.append(SnapshotReason.RUNTIME_UNREACHABLE)
    reasons.append(SnapshotReason.RUNTIME_UNAUTHORIZED)
    reasons.append(SnapshotReason.RUNTIME_INCOMPATIBLE)
    if unknown:
        reasons.append(SnapshotReason.UNKNOWN_CAPABILITY)
    if not mapped:
        reasons.append(SnapshotReason.UNSUPPORTED_MODALITY)
    if location is None:
        reasons.append(SnapshotReason.UNSUPPORTED_LOCATION)
    elif location != Location.DEVICE:
        reasons.append(SnapshotReason.TEAM_COMPUTE_SUBSTITUTION_FORBIDDEN)
        reasons.append(SnapshotReason.UNSUPPORTED_LOCATION)
    return tuple(dict.fromkeys(reasons))


def build_provider_runtime_snapshots(
    source: ModelCenterFactSource,
    caller_overrides: Mapping[str, Any] | None = None,
) -> ProviderRuntimeSnapshotBundle:
    """Pure normalization. Identical facts yield identical snapshots."""
    override_reasons = _override_reasons(caller_overrides)
    if override_reasons:
        return ProviderRuntimeSnapshotBundle(rejections=(SnapshotRejection(reasons=override_reasons),))
    instances = {item.runtime_registry_id: item for item in source.instances}
    rejections: list[SnapshotRejection] = []
    used_runtimes: set[str] = set()
    for model in source.models:
        matches = tuple(item for item in source.runtimes if item.runtime_type == model.runtime_type)
        if not matches:
            mapped, unknown, assets = _capabilities(model.capabilities)
            availability = Availability(
                configured=False, installed=False, healthy=False,
                reachable=False, authorized=False, compatible=False,
            )
            reasons = [
                SnapshotReason.MISSING_PROVIDER_IDENTITY,
                SnapshotReason.MISSING_MODEL_IDENTITY if _registry_uuid(model.registry_id) is None else SnapshotReason.MISSING_RUNTIME_IDENTITY,
                SnapshotReason.MISSING_RUNTIME_IDENTITY,
                SnapshotReason.MISSING_EXECUTION_NODE_IDENTITY,
                SnapshotReason.MISSING_HARDWARE_FACT,
                SnapshotReason.RUNTIME_NOT_CONFIGURED,
                SnapshotReason.RUNTIME_NOT_INSTALLED,
                SnapshotReason.RUNTIME_UNHEALTHY,
                SnapshotReason.RUNTIME_UNREACHABLE,
                SnapshotReason.RUNTIME_UNAUTHORIZED,
                SnapshotReason.RUNTIME_INCOMPATIBLE,
            ]
            if unknown:
                reasons.append(SnapshotReason.UNKNOWN_CAPABILITY)
            if not mapped:
                reasons.append(SnapshotReason.UNSUPPORTED_MODALITY)
            rejections.append(SnapshotRejection(
                reasons=tuple(dict.fromkeys(reasons)),
                model_registry_id=model.registry_id,
                availability=availability,
                mapped_modalities=mapped,
                unknown_capabilities=unknown,
                input_asset_types=assets,
                output_asset_types=assets,
            ))
            continue
        for runtime in matches:
            used_runtimes.add(runtime.registry_id)
            instance = instances.get(runtime.registry_id)
            availability = _availability(model, runtime, instance)
            location = _loopback_location(runtime.bind_address)
            declared = model.capabilities or runtime.capabilities
            mapped, unknown, assets = _capabilities(declared)
            rejections.append(SnapshotRejection(
                reasons=_route_reasons(model, runtime, availability, location, mapped, unknown),
                model_registry_id=model.registry_id,
                runtime_registry_id=runtime.registry_id,
                availability=availability,
                location=location,
                mapped_modalities=mapped,
                unknown_capabilities=unknown,
                input_asset_types=assets,
                output_asset_types=assets,
            ))
    for runtime in source.runtimes:
        if runtime.registry_id in used_runtimes:
            continue
        location = _loopback_location(runtime.bind_address)
        mapped, unknown, assets = _capabilities(runtime.capabilities)
        availability = Availability(
            configured=runtime.status == "CONFIGURED",
            installed=False, healthy=False, reachable=False,
            authorized=False, compatible=False,
        )
        reasons = _route_reasons(
            ModelCenterModelFact(registry_id="", runtime_type=runtime.runtime_type, status="NOT_INSTALLED"),
            runtime, availability, location, mapped, unknown,
        )
        rejections.append(SnapshotRejection(
            reasons=reasons,
            runtime_registry_id=runtime.registry_id,
            availability=availability,
            location=location,
            mapped_modalities=mapped,
            unknown_capabilities=unknown,
            input_asset_types=assets,
            output_asset_types=assets,
        ))
    ordered = tuple(sorted(
        rejections,
        key=lambda item: (item.model_registry_id or "", item.runtime_registry_id or "", item.reasons),
    ))
    return ProviderRuntimeSnapshotBundle(rejections=ordered)


class ModelCenterSnapshotBridge:
    @staticmethod
    def build(
        source: ModelCenterFactSource,
        caller_overrides: Mapping[str, Any] | None = None,
    ) -> ProviderRuntimeSnapshotBundle:
        return build_provider_runtime_snapshots(source, caller_overrides=caller_overrides)

    @staticmethod
    def capture(service: Any) -> ModelCenterFactSource:
        return capture_model_center_facts(service)

    @staticmethod
    def from_model_center(
        service: Any,
        caller_overrides: Mapping[str, Any] | None = None,
    ) -> ProviderRuntimeSnapshotBundle:
        return build_provider_runtime_snapshots(
            capture_model_center_facts(service),
            caller_overrides=caller_overrides,
        )
