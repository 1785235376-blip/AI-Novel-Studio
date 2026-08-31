from __future__ import annotations

import json
import multiprocessing as mp
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.model_runtime import ModelDescriptor, ModelRegistry, Modality, ProviderDescriptor, ProviderRegistry
from app.model_center.service import create_default_model_center
from app.runtime import Runtime
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
    TrustedLegacySource,
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
    source = TrustedLegacySource.from_entries(entries)
    first = store.migrate("provider", entries, trusted_source=source)
    second = StableIdentityStore(tmp_path / "identity.json").migrate("provider", entries, trusted_source=source)
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


def test_rename_preserves_id_and_delete_create_gets_new_id(tmp_path: Path):
    store = StableIdentityStore(tmp_path / "identity.json")
    original = store.create("provider", "old-name")
    assert store.rename("provider", "old-name", "new-name") == original
    assert store.get("provider", "old-name") is None
    assert store.get("provider", "new-name") == original
    store.delete("provider", "new-name")
    assert store.create("provider", "new-name") != original


def test_strict_store_rejects_duplicate_keys_unknown_content_and_bool_schema(tmp_path: Path):
    path = tmp_path / "identity.json"
    valid_entities = '"entities":{"provider":[],"model":[],"runtime":[],"execution_node":[]}'
    for raw in (
        '{"schema_version":1,"schema_version":1,' + valid_entities + '}',
        '{"schema_version":true,' + valid_entities + '}',
        '{"schema_version":1,"extra":1,' + valid_entities + '}',
        '{"schema_version":1,"entities":{"provider":[],"model":[],"runtime":[],"execution_node":[],"other":[]}}',
    ):
        path.write_text(raw, encoding="utf-8")
        with pytest.raises(IdentityIntegrityError):
            StableIdentityStore(path).list("provider")
    row = {"key": "x", "identity_id": str(uuid4()), "metadata": {}, "unknown": True}
    payload = {"schema_version": 1, "entities": {name: [] for name in StableIdentityStore.KINDS}}
    payload["entities"]["provider"] = [row]
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(IdentityIntegrityError):
        StableIdentityStore(path).list("provider")


def test_migration_requires_explicit_trusted_source(tmp_path: Path):
    with pytest.raises(IdentityIntegrityError, match="TRUST_REQUIRED"):
        StableIdentityStore(tmp_path / "identity.json").migrate("provider", [{"key": "x"}])


def test_model_registry_uses_one_canonical_model_key(tmp_path: Path):
    store = StableIdentityStore(tmp_path / "identity.json")
    models = ModelRegistry(store)
    models.register(ModelDescriptor("shared-model", "provider-a", "Shared", Modality.TEXT, frozenset()))
    first = models.descriptors()[0].model_uuid
    models.register(ModelDescriptor("shared-model", "provider-b", "Shared", Modality.TEXT, frozenset()), replace=True)
    assert models.descriptors()[1].model_uuid == first
    assert len(store.list("model")) == 1


def _mp_get_or_create(path: str, kind: str, key: str, barrier, queue) -> None:
    store = StableIdentityStore(path)
    barrier.wait()
    queue.put((kind, key, str(store.get_or_create(kind, key))))


def test_real_multiprocess_same_key_and_lost_update_safety(tmp_path: Path):
    path = str(tmp_path / "identity.json")
    context = mp.get_context("spawn")
    for keys in (("same", "same"), ("one", "two")):
        barrier = context.Barrier(2)
        queue = context.Queue()
        processes = [context.Process(target=_mp_get_or_create, args=(path, "provider", key, barrier, queue)) for key in keys]
        for process in processes: process.start()
        for process in processes: process.join(20)
        assert all(process.exitcode == 0 for process in processes)
        values = [queue.get(timeout=2)[2] for _ in processes]
        if keys[0] == keys[1]:
            assert values[0] == values[1]
        else:
            assert {item["key"] for item in StableIdentityStore(path).list("provider")} >= set(keys)


def test_real_multiprocess_mixed_kind_mutations_preserve_all_rows(tmp_path: Path):
    path = str(tmp_path / "identity.json")
    context = mp.get_context("spawn")
    jobs = [("provider", "p"), ("model", "m"), ("runtime", "r"), ("execution_node", "local")]
    barrier = context.Barrier(len(jobs))
    queue = context.Queue()
    processes = [context.Process(target=_mp_get_or_create, args=(path, kind, key, barrier, queue)) for kind, key in jobs]
    for process in processes: process.start()
    for process in processes: process.join(20)
    assert all(process.exitcode == 0 for process in processes)
    results = [queue.get(timeout=2) for _ in processes]
    store = StableIdentityStore(path)
    assert {(kind, key) for kind, key, _ in results} == set(jobs)
    assert all(len(store.list(kind)) == 1 for kind, _ in jobs)


def test_route_preparation_is_read_only_and_does_not_mint(tmp_path: Path):
    store = StableIdentityStore(tmp_path / "identity.json")
    runtime = Runtime(store)
    before = store.path.read_bytes()
    runtime.prepare_text_route("mock", "mock-writer")
    runtime.prepare_text_route("mock", "mock-writer")
    assert store.path.read_bytes() == before
    with pytest.raises(Exception, match="尚未完成注册"):
        runtime.prepare_text_route("missing-provider", "missing-model")
    assert store.path.read_bytes() == before
    store.delete("model", "mock-writer")
    before_missing = store.path.read_bytes()
    with pytest.raises(Exception, match="尚未完成注册"):
        runtime.prepare_text_route("mock", "mock-writer")
    assert store.path.read_bytes() == before_missing


def test_runtime_identity_cannot_be_supplied_or_mutated_by_configuration(tmp_path: Path):
    store = StableIdentityStore(tmp_path / "identity.json")
    center = create_default_model_center(tmp_path / "runtime-config.json", identity_store=store)
    original = center.runtimes["llama-cpp-local"].identity_id
    with pytest.raises(ValueError, match="RUNTIME_ID_IMMUTABLE"):
        center.configure_runtime("llama-cpp-local", {"identity_id": str(uuid4()), "port": 18082})
    with pytest.raises(ValueError, match="RUNTIME_ID_IMMUTABLE"):
        center.configure_runtime_profile("llama-cpp-local", {"runtime_uuid": "00000000-0000-0000-0000-000000000000"})
    assert center.runtimes["llama-cpp-local"].identity_id == original


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
