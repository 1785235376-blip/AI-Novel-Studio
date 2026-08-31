from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.model_runtime import ModelDescriptor, ModelRegistry, Modality, ProviderDescriptor, ProviderRegistry
from app.model_center.service import create_default_model_center
from app.provider_runtime_v2_contracts import ExecutionNodeIdentity as ContractNodeIdentity
from app.provider_runtime_v2_contracts import ModelIdentity as ContractModelIdentity
from app.provider_runtime_v2_contracts import ProviderIdentity as ContractProviderIdentity
from app.provider_runtime_v2_contracts import RuntimeIdentity as ContractRuntimeIdentity
from app.stable_identity import (
    ARCHITECTURES,
    GPU_VENDORS,
    RUNTIME_FAMILIES,
    ExecutionNodeIdentityStore,
    IdentityIntegrityError,
    IdentityMutationError,
    StableIdentityStore,
)


def test_owner_identity_is_created_once_and_survives_reload(tmp_path: Path):
    path = tmp_path / "identity.json"
    first = StableIdentityStore(path)
    provider_id = first.get_or_create("provider", "deepseek", metadata={"name": "DeepSeek"})
    model_id = first.get_or_create("model", "qwen36-27b-q4km")
    runtime_id = first.get_or_create("runtime", "llama-cpp-local")
    first.update("provider", "deepseek", metadata={"name": "Renamed Provider"})
    reloaded = StableIdentityStore(path)
    assert reloaded.get("provider", "deepseek") == provider_id
    assert reloaded.get("model", "qwen36-27b-q4km") == model_id
    assert reloaded.get("runtime", "llama-cpp-local") == runtime_id


def test_legacy_backfill_is_persisted_and_idempotent(tmp_path: Path):
    store = StableIdentityStore(tmp_path / "identity.json")
    entries = [{"key": "legacy-provider", "display_name": "Legacy"}]
    first = store.migrate("provider", entries)
    second = StableIdentityStore(tmp_path / "identity.json").migrate("provider", entries)
    assert first == second


@pytest.mark.parametrize("kind", ["provider", "model", "runtime"])
def test_zero_and_malformed_persisted_ids_fail_closed(tmp_path: Path, kind: str):
    path = tmp_path / "identity.json"
    payload = {"schema_version": 1, "entities": {name: [] for name in StableIdentityStore.KINDS}}
    payload["entities"][kind] = [{"key": "x", "identity_id": "00000000-0000-0000-0000-000000000000", "metadata": {}}]
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(IdentityIntegrityError):
        StableIdentityStore(path).list(kind)
    payload["entities"][kind][0]["identity_id"] = "not-a-uuid"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(IdentityIntegrityError):
        StableIdentityStore(path).list(kind)


def test_duplicate_ids_fail_closed_independent_of_input_order(tmp_path: Path):
    duplicate = str(uuid4())
    for rows in (
        [{"key": "a", "identity_id": duplicate, "metadata": {}}, {"key": "b", "identity_id": duplicate, "metadata": {}}],
        [{"key": "b", "identity_id": duplicate, "metadata": {}}, {"key": "a", "identity_id": duplicate, "metadata": {}}],
    ):
        path = tmp_path / f"{len(rows)}-{rows[0]['key']}.json"
        payload = {"schema_version": 1, "entities": {name: [] for name in StableIdentityStore.KINDS}}
        payload["entities"]["runtime"] = rows
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(IdentityIntegrityError, match="runtime_DUPLICATE_ID"):
            StableIdentityStore(path).list("runtime")


def test_client_supplied_id_never_becomes_authoritative(tmp_path: Path):
    store = StableIdentityStore(tmp_path / "identity.json")
    supplied = uuid4()
    actual = store.create("provider", "client-created", supplied_id=supplied)
    assert actual != supplied
    with pytest.raises(IdentityMutationError):
        store.update("provider", "client-created", identity_id=supplied)


def test_registry_descriptors_receive_stable_owner_ids_and_reject_mutation(tmp_path: Path):
    store = StableIdentityStore(tmp_path / "identity.json")
    providers = ProviderRegistry(store)
    models = ModelRegistry(store)

    class Provider:
        provider_id = "mock"

    descriptor = ProviderDescriptor("mock", "Mock", "local", frozenset({Modality.TEXT}), True, True)
    providers.register(descriptor, Provider())
    provider_uuid = providers.descriptors()[0].provider_uuid
    assert provider_uuid is not None
    providers.register(descriptor, Provider(), replace=True)
    assert providers.descriptors()[0].provider_uuid == provider_uuid

    model = ModelDescriptor("mock-writer", "mock", "Mock Writer", Modality.TEXT, frozenset({"generate"}))
    models.register(model)
    assert models.descriptors()[0].model_uuid is not None
    with pytest.raises(IdentityMutationError):
        models.register(ModelDescriptor("mock-writer", "mock", "Mock Writer", Modality.TEXT, frozenset(), identity_id=uuid4()), replace=True)


def test_execution_node_is_host_owned_and_stable(tmp_path: Path):
    path = tmp_path / "host" / "identity.json"
    first = ExecutionNodeIdentityStore(path).get_or_create().execution_node_id
    second = ExecutionNodeIdentityStore(path).get_or_create().execution_node_id
    assert first == second and first != UUID(int=0)


def test_model_center_owner_ids_survive_reload_and_configuration(tmp_path: Path):
    config = tmp_path / "model-center" / "runtime-config.json"
    identity = StableIdentityStore(tmp_path / "identity-foundation.json")
    first = create_default_model_center(config, identity_store=identity)
    model_id = first.models["qwen36-27b-q4km"].identity_id
    runtime_id = first.runtimes["llama-cpp-local"].identity_id
    first.configure_runtime("llama-cpp-local", {"port": 18081})
    second = create_default_model_center(config, identity_store=StableIdentityStore(tmp_path / "identity-foundation.json"))
    assert second.models["qwen36-27b-q4km"].identity_id == model_id
    assert second.runtimes["llama-cpp-local"].identity_id == runtime_id


def test_taxonomy_ids_are_explicit_unique_and_stable():
    values = tuple(RUNTIME_FAMILIES.values()) + tuple(ARCHITECTURES.values()) + tuple(GPU_VENDORS.values())
    ids = [item.taxonomy_id for item in values]
    assert len(ids) == len(set(ids))
    assert all(item.taxonomy_id != UUID(int=0) for item in values)
    assert RUNTIME_FAMILIES["llama.cpp"].taxonomy_id == UUID("7c8b4e2a-1b0d-4d8f-9e64-0b5b3f0d1a11")


@pytest.mark.parametrize(
    "contract,field",
    [
        (ContractProviderIdentity, "provider_id"),
        (ContractModelIdentity, "model_id"),
        (ContractRuntimeIdentity, "runtime_id"),
        (ContractNodeIdentity, "execution_node_id"),
    ],
)
def test_contract_identity_rejects_zero_uuid(contract, field):
    with pytest.raises(ValueError):
        contract(**{field: UUID(int=0)})
