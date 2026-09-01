from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest

from app.model_center import create_default_model_center
from app.model_center.domain import RuntimeManagement
from app.model_runtime import ModelDescriptor, Modality, ProviderDescriptor
from app.provider_runtime_v2_model_center_snapshot_bridge import (
    SnapshotItem,
    SnapshotRejectionCode,
    build_provider_runtime_snapshot,
    create_provider_runtime_snapshot,
)
from app.provider_runtime_v2_contracts import Location
from app.runtime import Runtime
from app.stable_identity import StableIdentityStore
from app.stable_identity import ARCHITECTURE_X86_64


def _setup(tmp_path: Path):
    store = StableIdentityStore(tmp_path / "identity.json")
    runtime = Runtime(store)
    center = create_default_model_center(tmp_path / "runtime.json", identity_store=store)
    # Test-only authoritative runtime requirement fact. Production defaults do
    # not expose this fact and therefore fail closed.
    object.__setattr__(center.runtimes["llama-cpp-local"], "architecture_id", ARCHITECTURE_X86_64.taxonomy_id)
    model = center.models["qwen36-27b-q4km"]
    provider = next(item for item in runtime.provider_registry.descriptors() if item.provider_id == "ollama")
    runtime.provider_registry.register(
        ProviderDescriptor("ollama", provider.display_name, provider.provider_type, provider.supported_modalities, True, True),
        runtime.providers["ollama"], replace=True,
    )
    runtime.model_registry.register(
        ModelDescriptor("qwen36-27b-q4km", "ollama", model.display_name, Modality.TEXT, frozenset({"generate", "stream"}), streaming=True, identity_id=model.identity_id),
        replace=True,
    )
    return store, runtime, center


def test_authoritative_text_candidate_and_read_only_store(tmp_path: Path):
    store, runtime, center = _setup(tmp_path)
    before = hashlib.sha256(store.path.read_bytes()).digest()
    snapshot = build_provider_runtime_snapshot(runtime.provider_registry, runtime.model_registry, center, runtime.execution_node_identity)
    after = hashlib.sha256(store.path.read_bytes()).digest()
    assert before == after
    candidate = next(item for item in snapshot.candidates if item.identity.model.model_id == center.models["qwen36-27b-q4km"].identity_id)
    assert candidate.identity.provider.provider_id == next(item for item in runtime.provider_registry.descriptors() if item.provider_id == "ollama").identity_id
    assert candidate.identity.runtime.runtime_id == center.runtimes["llama-cpp-local"].identity_id
    assert candidate.identity.node.execution_node_id == runtime.execution_node_identity.store.get("execution_node", "local")
    assert candidate.capabilities.supported_modalities == frozenset({Modality.TEXT})


def test_rejections_are_exclusive_and_deterministic(tmp_path: Path):
    store, runtime, center = _setup(tmp_path)
    first = build_provider_runtime_snapshot(runtime.provider_registry, runtime.model_registry, center, runtime.execution_node_identity)
    second = build_provider_runtime_snapshot(runtime.provider_registry, runtime.model_registry, center, runtime.execution_node_identity)
    assert first.to_dict() == second.to_dict()
    assert all((item.candidate is None) != (item.rejection is None) for item in first.items)
    assert not set(item.source_key for item in first.items if item.rejection) & set(item.source_key for item in first.items if item.candidate)


@pytest.mark.parametrize("field,code", [
    ("provider", SnapshotRejectionCode.MISSING_PROVIDER_IDENTITY),
    ("model", SnapshotRejectionCode.MISSING_MODEL_IDENTITY),
    ("runtime", SnapshotRejectionCode.MISSING_RUNTIME_IDENTITY),
])
def test_missing_identity_is_rejected(tmp_path: Path, field: str, code: SnapshotRejectionCode):
    store, runtime, center = _setup(tmp_path)
    if field == "provider":
        descriptor = next(x for x in runtime.provider_registry.descriptors() if x.provider_id == "ollama")
        runtime.provider_registry._descriptors["ollama"] = replace(descriptor, identity_id=None)
    elif field == "model":
        descriptor = runtime.model_registry._models[("ollama", "qwen36-27b-q4km")]
        runtime.model_registry._models[("ollama", "qwen36-27b-q4km")] = replace(descriptor, identity_id=None)
    else:
        center.runtimes["llama-cpp-local"] = replace(center.runtimes["llama-cpp-local"], identity_id=None)
    snapshot = build_provider_runtime_snapshot(runtime.provider_registry, runtime.model_registry, center, runtime.execution_node_identity)
    assert any(item.rejection and item.rejection.code is code for item in snapshot.items)
    assert not snapshot.candidates


def test_unknown_capability_and_duplicate_runtime_are_rejected(tmp_path: Path):
    store, runtime, center = _setup(tmp_path)
    model = center.models["qwen36-27b-q4km"]
    center.models[model.id] = replace(model, capabilities=("NOT_A_CAPABILITY",))
    snapshot = build_provider_runtime_snapshot(runtime.provider_registry, runtime.model_registry, center, runtime.execution_node_identity)
    assert any(item.rejection and item.rejection.code is SnapshotRejectionCode.UNKNOWN_CAPABILITY for item in snapshot.items)

    # A repeated authoritative runtime identity is never resolved by order.
    store, runtime, center = _setup(tmp_path / "duplicate")
    original = center.runtimes["llama-cpp-local"]
    center.runtimes = [original, original]  # type: ignore[assignment]
    snapshot = build_provider_runtime_snapshot(runtime.provider_registry, runtime.model_registry, center, runtime.execution_node_identity)
    assert any(item.rejection and item.rejection.code is SnapshotRejectionCode.DUPLICATE_RUNTIME_IDENTITY for item in snapshot.items)


def test_production_entrypoint_does_not_accept_caller_authority():
    with pytest.raises(TypeError):
        create_provider_runtime_snapshot(object())  # type: ignore[call-arg]


@pytest.mark.parametrize("owner", ["provider", "model", "runtime"])
def test_valid_random_uuid_provenance_mismatch_is_rejected(tmp_path: Path, owner: str):
    store, runtime, center = _setup(tmp_path / owner)
    if owner == "provider":
        descriptor = next(x for x in runtime.provider_registry.descriptors() if x.provider_id == "ollama")
        runtime.provider_registry._descriptors["ollama"] = replace(descriptor, identity_id=uuid4())
    elif owner == "model":
        descriptor = runtime.model_registry._models[("ollama", "qwen36-27b-q4km")]
        runtime.model_registry._models[("ollama", "qwen36-27b-q4km")] = replace(descriptor, identity_id=uuid4())
    else:
        center.runtimes["llama-cpp-local"] = replace(center.runtimes["llama-cpp-local"], identity_id=uuid4())
    snapshot = build_provider_runtime_snapshot(runtime.provider_registry, runtime.model_registry, center, runtime.execution_node_identity, store)
    assert not snapshot.candidates
    assert any(item.rejection and item.rejection.code in {SnapshotRejectionCode.INVALID_IDENTITY, SnapshotRejectionCode.MISSING_MODEL_IDENTITY} for item in snapshot.items)


def test_routing_policy_is_the_only_model_runtime_association(tmp_path: Path):
    store, runtime, center = _setup(tmp_path)
    original = center.runtimes["llama-cpp-local"]
    alternate_id = "llama-cpp-alternate"
    alternate_uuid = store.create("runtime", alternate_id)
    alternate = replace(original, id=alternate_id, identity_id=alternate_uuid)
    object.__setattr__(alternate, "architecture_id", ARCHITECTURE_X86_64.taxonomy_id)
    center.runtimes[alternate_id] = alternate
    center.routing_policy.routes["TEXT"] = {"model_id": "qwen36-27b-q4km", "runtime_id": alternate_id}
    snapshot = build_provider_runtime_snapshot(runtime.provider_registry, runtime.model_registry, center, runtime.execution_node_identity, store)
    assert not snapshot.candidates or all(item.identity.runtime.runtime_id == alternate_uuid for item in snapshot.candidates)
    assert all("llama-cpp-local" not in item.source_key for item in snapshot.items)


def test_no_route_produces_no_candidate(tmp_path: Path):
    store, runtime, center = _setup(tmp_path)
    center.routing_policy.routes.clear()
    snapshot = build_provider_runtime_snapshot(runtime.provider_registry, runtime.model_registry, center, runtime.execution_node_identity, store)
    assert snapshot.candidates == ()


def test_external_locality_does_not_grant_trust_or_authorization(tmp_path: Path):
    store, runtime, center = _setup(tmp_path)
    runtime_def = center.runtimes["llama-cpp-local"]
    object.__setattr__(runtime_def, "management", RuntimeManagement.EXTERNAL)
    snapshot = build_provider_runtime_snapshot(runtime.provider_registry, runtime.model_registry, center, runtime.execution_node_identity, store)
    if snapshot.candidates:
        candidate = snapshot.candidates[0]
        assert candidate.location is Location.DEVICE
        assert candidate.trusted is False
        assert candidate.self_hosted is False
        assert candidate.availability.authorized is False


def test_streaming_comes_from_model_registry(tmp_path: Path):
    store, runtime, center = _setup(tmp_path)
    descriptor = runtime.model_registry._models[("ollama", "qwen36-27b-q4km")]
    runtime.model_registry._models[("ollama", "qwen36-27b-q4km")] = replace(descriptor, streaming=False)
    snapshot = build_provider_runtime_snapshot(runtime.provider_registry, runtime.model_registry, center, runtime.execution_node_identity, store)
    if snapshot.candidates:
        assert snapshot.candidates[0].capabilities.streaming is False


def test_default_model_center_rejects_missing_architecture_without_probing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    store, runtime, center = _setup(tmp_path)
    object.__setattr__(center.runtimes["llama-cpp-local"], "architecture_id", None)
    monkeypatch.setattr("platform.machine", lambda: (_ for _ in ()).throw(AssertionError("platform probing")))
    snapshot = build_provider_runtime_snapshot(runtime.provider_registry, runtime.model_registry, center, runtime.execution_node_identity, store)
    assert not snapshot.candidates
    assert any(item.rejection and item.rejection.code is SnapshotRejectionCode.MISSING_REQUIRED_HARDWARE_FACT for item in snapshot.items)
