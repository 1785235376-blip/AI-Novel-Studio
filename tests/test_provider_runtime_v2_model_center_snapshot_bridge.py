from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

from app.model_center import create_default_model_center
from app.model_runtime import ModelDescriptor, Modality, ProviderDescriptor
from app.provider_runtime_v2_model_center_snapshot_bridge import (
    SnapshotItem,
    SnapshotRejectionCode,
    build_provider_runtime_snapshot,
    create_provider_runtime_snapshot,
)
from app.runtime import Runtime
from app.stable_identity import StableIdentityStore


def _setup(tmp_path: Path):
    store = StableIdentityStore(tmp_path / "identity.json")
    runtime = Runtime(store)
    center = create_default_model_center(tmp_path / "runtime.json", identity_store=store)
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
