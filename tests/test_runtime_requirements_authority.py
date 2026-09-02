from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.model_center import create_default_model_center
from app.model_center.domain import RuntimeDefinition, RuntimeType
from app.model_center.runtime_profiles import editable_configuration
from app.model_center.service import RuntimeArchitectureConfigurationError
from app.model_runtime import ModelDescriptor, Modality, ProviderDescriptor
from app.provider_runtime_v2_model_center_snapshot_bridge import (
    SnapshotRejectionCode,
    build_provider_runtime_snapshot,
    create_provider_runtime_snapshot,
)
from app.runtime import Runtime
from app.stable_identity import (
    ARCHITECTURE_ARM64,
    ARCHITECTURE_X86_64,
    GPU_VENDOR_NVIDIA,
    StableIdentityStore,
)


def _authority(tmp_path: Path, architecture_id: UUID | None = ARCHITECTURE_X86_64.taxonomy_id):
    store = StableIdentityStore(tmp_path / "identity.json")
    runtime = Runtime(store)
    center = create_default_model_center(tmp_path / "runtime.json", identity_store=store)
    definition = center.runtimes["llama-cpp-local"]
    center.runtimes[definition.id] = replace(definition, architecture_id=architecture_id)
    model = center.models["qwen36-27b-q4km"]
    provider = next(item for item in runtime.provider_registry.descriptors() if item.provider_id == "ollama")
    runtime.provider_registry.register(
        ProviderDescriptor("ollama", provider.display_name, provider.provider_type, provider.supported_modalities, True, True),
        runtime.providers["ollama"], replace=True,
    )
    runtime.model_registry.register(
        ModelDescriptor(model.id, "ollama", model.display_name, Modality.TEXT, frozenset({"generate"}), identity_id=model.identity_id),
        replace=True,
    )
    return store, runtime, center


def test_runtime_architecture_persists_and_reloads(tmp_path: Path):
    store = StableIdentityStore(tmp_path / "identity.json")
    config = tmp_path / "runtime.json"
    service = create_default_model_center(config, identity_store=store)
    service.configure_runtime("llama-cpp-local", {"architecture_id": str(ARCHITECTURE_ARM64.taxonomy_id)})
    payload = json.loads(config.read_text(encoding="utf-8"))
    assert payload["runtimes"]["llama-cpp-local"]["architecture_id"] == str(ARCHITECTURE_ARM64.taxonomy_id)
    reloaded = create_default_model_center(config, identity_store=store)
    assert reloaded.runtimes["llama-cpp-local"].architecture_id == ARCHITECTURE_ARM64.taxonomy_id


def test_snapshot_consumes_exact_authoritative_architecture_without_mutation(tmp_path: Path):
    store, runtime, center = _authority(tmp_path, ARCHITECTURE_ARM64.taxonomy_id)
    before = hashlib.sha256(store.path.read_bytes()).digest()
    first = build_provider_runtime_snapshot(runtime.provider_registry, runtime.model_registry, center, runtime.execution_node_identity, store)
    second = build_provider_runtime_snapshot(runtime.provider_registry, runtime.model_registry, center, runtime.execution_node_identity, store)
    assert first.to_dict() == second.to_dict()
    assert hashlib.sha256(store.path.read_bytes()).digest() == before
    assert first.candidates[0].capabilities.requirements.architecture_id == ARCHITECTURE_ARM64.taxonomy_id


@pytest.mark.parametrize("value", [UUID(int=0), uuid4(), GPU_VENDOR_NVIDIA.taxonomy_id])
def test_runtime_definition_rejects_non_architecture_taxonomy(value: UUID):
    with pytest.raises(ValueError):
        RuntimeDefinition("runtime", RuntimeType.LLAMA_CPP, architecture_id=value)


def test_runtime_definition_rejects_malformed_architecture():
    with pytest.raises(ValueError, match="architecture_id_MALFORMED"):
        RuntimeDefinition("runtime", RuntimeType.LLAMA_CPP, architecture_id="x86_64")  # type: ignore[arg-type]


def test_missing_architecture_fails_closed_without_platform_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    store, runtime, center = _authority(tmp_path, None)
    monkeypatch.setattr("platform.machine", lambda: (_ for _ in ()).throw(AssertionError("host probe")))
    snapshot = build_provider_runtime_snapshot(runtime.provider_registry, runtime.model_registry, center, runtime.execution_node_identity, store)
    assert not snapshot.candidates
    assert any(item.code is SnapshotRejectionCode.MISSING_REQUIRED_HARDWARE_FACT for item in snapshot.rejections)


def test_invalid_owned_architecture_is_structurally_rejected(tmp_path: Path):
    store, runtime, center = _authority(tmp_path)
    object.__setattr__(center.runtimes["llama-cpp-local"], "architecture_id", GPU_VENDOR_NVIDIA.taxonomy_id)
    snapshot = build_provider_runtime_snapshot(runtime.provider_registry, runtime.model_registry, center, runtime.execution_node_identity, store)
    assert not snapshot.candidates
    assert any(item.code is SnapshotRejectionCode.INVALID_IDENTITY for item in snapshot.rejections)


def test_snapshot_entrypoints_accept_no_architecture_override():
    with pytest.raises(TypeError):
        create_provider_runtime_snapshot(architecture_id=ARCHITECTURE_X86_64.taxonomy_id)  # type: ignore[call-arg]


@pytest.mark.parametrize("runtime_id", ["llama-cpp-local", "comfyui-local"])
def test_protected_readback_roundtrip_for_both_runtime_types(tmp_path: Path, runtime_id: str):
    store = StableIdentityStore(tmp_path / "identity.json")
    config = tmp_path / "runtime.json"
    service = create_default_model_center(config, identity_store=store)
    configured = service.configure_runtime(runtime_id, {"architecture_id": str(ARCHITECTURE_ARM64.taxonomy_id)})
    assert editable_configuration(configured)["architecture_id"] == ARCHITECTURE_ARM64.taxonomy_id
    assert json.loads(config.read_text(encoding="utf-8"))["runtimes"][runtime_id]["architecture_id"] == str(ARCHITECTURE_ARM64.taxonomy_id)

    reloaded = create_default_model_center(config, identity_store=store)
    assert reloaded.runtimes[runtime_id].architecture_id == ARCHITECTURE_ARM64.taxonomy_id
    assert editable_configuration(reloaded.runtimes[runtime_id])["architecture_id"] == ARCHITECTURE_ARM64.taxonomy_id


def test_missing_architecture_protected_readback_is_none(tmp_path: Path):
    service = create_default_model_center(identity_store=StableIdentityStore(tmp_path / "identity.json"))
    assert editable_configuration(service.runtimes["llama-cpp-local"])["architecture_id"] is None
    assert editable_configuration(service.runtimes["comfyui-local"])["architecture_id"] is None


@pytest.mark.parametrize("value", [
    "x86_64",
    str(UUID(int=0)),
    str(uuid4()),
    str(GPU_VENDOR_NVIDIA.taxonomy_id),
])
def test_invalid_persisted_architecture_fails_closed_without_file_mutation(tmp_path: Path, value: str):
    config = tmp_path / "runtime.json"
    config.write_text(json.dumps({
        "schema_version": 1,
        "runtimes": {"llama-cpp-local": {"architecture_id": value}},
    }), encoding="utf-8")
    before = config.read_bytes()
    with pytest.raises(RuntimeArchitectureConfigurationError, match="RUNTIME_ARCHITECTURE_INVALID"):
        create_default_model_center(config, identity_store=StableIdentityStore(tmp_path / "identity.json"))
    assert config.read_bytes() == before


@pytest.mark.parametrize("architecture", ["absent", None])
def test_old_or_null_architecture_configuration_loads_as_missing(tmp_path: Path, architecture: str | None):
    values = {} if architecture == "absent" else {"architecture_id": None}
    config = tmp_path / "runtime.json"
    config.write_text(json.dumps({
        "schema_version": 1,
        "runtimes": {"llama-cpp-local": values},
    }), encoding="utf-8")
    service = create_default_model_center(config, identity_store=StableIdentityStore(tmp_path / "identity.json"))
    assert service.runtimes["llama-cpp-local"].architecture_id is None


def test_invalid_configure_runtime_is_atomic(tmp_path: Path):
    store = StableIdentityStore(tmp_path / "identity.json")
    config = tmp_path / "runtime.json"
    service = create_default_model_center(config, identity_store=store)
    service.configure_runtime("llama-cpp-local", {"architecture_id": str(ARCHITECTURE_X86_64.taxonomy_id)})
    before_runtime = service.runtimes["llama-cpp-local"]
    before_file = config.read_bytes()
    with pytest.raises(ValueError, match="RUNTIME_ARCHITECTURE_INVALID"):
        service.configure_runtime("llama-cpp-local", {"architecture_id": str(GPU_VENDOR_NVIDIA.taxonomy_id)})
    assert service.runtimes["llama-cpp-local"] == before_runtime
    assert config.read_bytes() == before_file


def test_requirement_documentation_has_one_semantic_meaning():
    text = Path("docs/provider_runtime_v2_runtime_requirements_authority.md").read_text(encoding="utf-8")
    assert "requires or supports" not in text
    assert "CPU architecture required by the explicitly configured runtime" in text
