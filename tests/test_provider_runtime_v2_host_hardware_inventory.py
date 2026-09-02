from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.model_center.domain import RuntimeDefinition, RuntimeInstance, RuntimeManagement, RuntimeState, RuntimeType
from app.provider_routing_policy_v2 import evaluate_routing
from app.provider_runtime_v2_contracts import (
    AssetType,
    Availability,
    BudgetPolicy,
    CandidateDescriptor,
    CapabilityDescriptor,
    Decision,
    ExecutionNodeIdentity,
    HardwareSnapshot,
    Location,
    Modality,
    ModelIdentity,
    PrivacyPolicy,
    ProviderIdentity,
    ProviderRoutingRequest,
    RouteIdentity,
    RuntimeIdentity,
    RuntimeRequirements,
)
from app.provider_runtime_v2_host_hardware_inventory import (
    MIB,
    HostGpuFact,
    HostHardwareFacts,
    HostHardwareInventoryError,
    WindowsHostHardwareProbe,
    available_runtime_family_ids,
    build_host_hardware_snapshot,
    normalize_architecture,
    serialize_host_hardware_snapshot,
)
from app.stable_identity import (
    ARCHITECTURE_ARM64,
    ARCHITECTURE_X86_64,
    GPU_VENDOR_NVIDIA,
    RUNTIME_FAMILY_COMFYUI,
    RUNTIME_FAMILY_LLAMA_CPP,
    ExecutionNodeIdentityStore,
    StableIdentityStore,
)


@pytest.fixture(autouse=True)
def restore_global_settings():
    """Inventory contract tests do not initialize application runtime or Vault."""
    yield


class FakeProcess:
    def __init__(self, return_code=None):
        self.return_code = return_code

    def poll(self):
        return self.return_code


class FakeLifecycle:
    def __init__(self, instances=None, owned=None):
        self.instances = instances or {}
        self._owned = owned or {}

    @staticmethod
    def is_local(_runtime):
        return True


def center(*runtimes, instances=None, owned=None, config_path=None, routes=None):
    return SimpleNamespace(
        runtimes={runtime.id: runtime for runtime in runtimes},
        lifecycle=FakeLifecycle(instances, owned),
        config_path=config_path,
        routing_policy=SimpleNamespace(routes=routes or {}),
    )


def node_store(tmp_path: Path):
    path = tmp_path / "identity.json"
    store = StableIdentityStore(path)
    node_id = store.get_or_create("execution_node", "local")
    return ExecutionNodeIdentityStore(path), node_id, path


def facts(*, architecture="AMD64", ram=64 * 1024 * MIB, gpus=()):
    return HostHardwareFacts(architecture=architecture, physical_ram_bytes=ram, gpus=gpus)


@pytest.mark.parametrize("raw", ["AMD64", "amd64", "x86_64", "X86_64"])
def test_x86_architecture_aliases_use_existing_taxonomy(raw: str):
    assert normalize_architecture(raw) == ARCHITECTURE_X86_64.taxonomy_id


@pytest.mark.parametrize("raw", ["ARM64", "arm64", "aarch64", "AARCH64"])
def test_arm_architecture_aliases_use_existing_taxonomy(raw: str):
    assert normalize_architecture(raw) == ARCHITECTURE_ARM64.taxonomy_id


@pytest.mark.parametrize("raw", ["", " ", "x86", "riscv64", None])
def test_unknown_or_empty_architecture_fails_closed(raw):
    with pytest.raises(HostHardwareInventoryError, match="UNKNOWN_ARCHITECTURE"):
        normalize_architecture(raw)


def test_runtime_requirement_cannot_supply_host_architecture(tmp_path: Path):
    identity, _, _ = node_store(tmp_path)
    runtime = RuntimeDefinition(
        "llama", RuntimeType.LLAMA_CPP, architecture_id=ARCHITECTURE_ARM64.taxonomy_id
    )
    snapshot = build_host_hardware_snapshot(facts(architecture="AMD64"), identity, center(runtime))
    assert snapshot.architecture_id == ARCHITECTURE_X86_64.taxonomy_id
    assert snapshot.architecture_id != runtime.architecture_id


def test_physical_ram_uses_floor_mib_and_handles_large_values(tmp_path: Path):
    identity, _, _ = node_store(tmp_path)
    snapshot = build_host_hardware_snapshot(facts(ram=17 * MIB + MIB - 1), identity, center())
    assert snapshot.ram_mib == 17
    huge = build_host_hardware_snapshot(facts(ram=1 << 80), identity, center())
    assert huge.ram_mib == (1 << 80) // MIB


@pytest.mark.parametrize("value", [0, -1, 1.5, "1024", True, None])
def test_invalid_physical_ram_fact_is_rejected(tmp_path: Path, value):
    identity, _, _ = node_store(tmp_path)
    with pytest.raises(HostHardwareInventoryError, match="INVALID_HARDWARE_FACT"):
        build_host_hardware_snapshot(facts(ram=value), identity, center())


def test_available_ram_cannot_be_substituted_for_capacity():
    with pytest.raises(TypeError):
        HostHardwareFacts(architecture="AMD64", physical_ram_bytes=8 * MIB, gpus=(), available_ram_bytes=4 * MIB)  # type: ignore[call-arg]
    source = inspect.getsource(WindowsHostHardwareProbe._physical_ram_bytes)
    assert "ullTotalPhys" in source
    assert "return int(status.ullTotalPhys)" in source


def test_known_gpu_vendor_and_vram_are_exact_conservative_mib(tmp_path: Path):
    identity, _, _ = node_store(tmp_path)
    gpu = HostGpuFact(0x10DE, 16303 * MIB + MIB - 1)
    snapshot = build_host_hardware_snapshot(facts(gpus=(gpu,)), identity, center())
    assert snapshot.gpu_vendor_id == GPU_VENDOR_NVIDIA.taxonomy_id
    assert snapshot.vram_mib == 16303


def test_unknown_vram_and_no_gpu_are_fail_closed(tmp_path: Path):
    identity, _, _ = node_store(tmp_path)
    unknown = build_host_hardware_snapshot(facts(gpus=(HostGpuFact(0x10DE, None),)), identity, center())
    absent = build_host_hardware_snapshot(facts(gpus=()), identity, center())
    unavailable = build_host_hardware_snapshot(facts(gpus=None), identity, center())
    assert unknown.gpu_vendor_id == GPU_VENDOR_NVIDIA.taxonomy_id and unknown.vram_mib == 0
    assert absent.gpu_vendor_id is None and absent.vram_mib == 0
    assert unavailable.gpu_vendor_id is None and unavailable.vram_mib == 0


@pytest.mark.parametrize("value", [-1, 1.5, "1024", True, UUID(int=1)])
def test_malformed_vram_is_rejected(tmp_path: Path, value):
    identity, _, _ = node_store(tmp_path)
    with pytest.raises(HostHardwareInventoryError, match="INVALID_HARDWARE_FACT"):
        build_host_hardware_snapshot(facts(gpus=(HostGpuFact(0x10DE, value),)), identity, center())


def test_unknown_vendor_wrong_taxonomy_and_gpu_name_guessing_are_impossible(tmp_path: Path):
    identity, _, _ = node_store(tmp_path)
    unknown = build_host_hardware_snapshot(facts(gpus=(HostGpuFact(0xFFFF, 24 * 1024 * MIB),)), identity, center())
    assert unknown.gpu_vendor_id is None and unknown.vram_mib == 0
    with pytest.raises(HostHardwareInventoryError, match="INVALID_HARDWARE_FACT"):
        build_host_hardware_snapshot(
            facts(gpus=(HostGpuFact(GPU_VENDOR_NVIDIA.taxonomy_id, 16 * 1024 * MIB),)),  # type: ignore[arg-type]
            identity,
            center(),
        )
    with pytest.raises(TypeError):
        HostGpuFact(pci_vendor_id=0x10DE, dedicated_vram_bytes=None, gpu_name="RTX 5080")  # type: ignore[call-arg]


def test_multiple_gpus_never_select_first_or_largest(tmp_path: Path):
    identity, _, _ = node_store(tmp_path)
    first = HostGpuFact(0x10DE, 8 * 1024 * MIB)
    second = HostGpuFact(0x1002, 24 * 1024 * MIB)
    for order in ((first, second), (second, first)):
        snapshot = build_host_hardware_snapshot(facts(gpus=order), identity, center())
        assert snapshot.gpu_vendor_id is None
        assert snapshot.vram_mib == 0


def test_same_vendor_multiple_gpus_fail_closed(tmp_path: Path):
    identity, _, _ = node_store(tmp_path)
    gpus = (HostGpuFact(0x10DE, 8 * 1024 * MIB), HostGpuFact(0x10DE, 24 * 1024 * MIB))
    snapshot = build_host_hardware_snapshot(facts(gpus=gpus), identity, center())
    assert snapshot.gpu_vendor_id is None
    assert snapshot.vram_mib == 0


def test_headless_secondary_dxgi_gpu_is_still_ambiguous(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    identity, _, _ = node_store(tmp_path)
    enumerated = (HostGpuFact(0x10DE, 8 * 1024 * MIB), HostGpuFact(0x8086, 0))
    probe = WindowsHostHardwareProbe()
    monkeypatch.setattr(probe, "_dxgi_gpu_facts", lambda: enumerated)
    snapshot = build_host_hardware_snapshot(facts(gpus=probe._gpu_facts_fail_closed()), identity, center())
    assert snapshot.gpu_vendor_id is None
    assert snapshot.vram_mib == 0


def test_dxgi_software_adapter_is_excluded_and_hardware_fact_is_same_adapter():
    software = WindowsHostHardwareProbe._fact_from_dxgi_description(0x1414, 2 * 1024 * MIB, 2)
    hardware = WindowsHostHardwareProbe._fact_from_dxgi_description(0x10DE, 16 * 1024 * MIB, 0)
    assert software is None
    assert hardware == HostGpuFact(0x10DE, 16 * 1024 * MIB)


def test_dxgi_failure_maps_to_unknown_gpu(monkeypatch: pytest.MonkeyPatch):
    probe = WindowsHostHardwareProbe()
    monkeypatch.setattr(
        probe,
        "_dxgi_gpu_facts",
        lambda: (_ for _ in ()).throw(HostHardwareInventoryError("GPU_FACT_UNAVAILABLE")),
    )
    assert probe._gpu_facts_fail_closed() is None


def test_multiple_gpus_do_not_hide_malformed_facts(tmp_path: Path):
    identity, _, _ = node_store(tmp_path)
    with pytest.raises(HostHardwareInventoryError, match="INVALID_HARDWARE_FACT"):
        build_host_hardware_snapshot(
            facts(gpus=(HostGpuFact(0x10DE, 8 * MIB), HostGpuFact(0x1002, -1))),
            identity,
            center(),
        )


def test_default_and_configured_but_unavailable_runtimes_are_excluded(tmp_path: Path):
    identity, _, _ = node_store(tmp_path)
    llama = RuntimeDefinition("llama", RuntimeType.LLAMA_CPP)
    comfy = RuntimeDefinition(
        "comfy", RuntimeType.COMFYUI, base_url="http://127.0.0.1:8188",
        port=8188, management=RuntimeManagement.EXTERNAL,
    )
    missing = RuntimeDefinition("missing", RuntimeType.LLAMA_CPP, executable=str(tmp_path / "missing.exe"))
    snapshot = build_host_hardware_snapshot(facts(), identity, center(llama, comfy, missing))
    assert snapshot.runtime_family_ids == frozenset()


def test_fake_managed_executable_without_owned_process_is_excluded(tmp_path: Path):
    executable = tmp_path / "llama-server.exe"
    executable.write_bytes(b"runtime")
    llama = RuntimeDefinition("llama", RuntimeType.LLAMA_CPP, executable=str(executable))
    assert available_runtime_family_ids(center(llama)) == frozenset()


def test_instance_process_alive_without_owned_process_is_excluded():
    llama = RuntimeDefinition("llama", RuntimeType.LLAMA_CPP)
    spoofed = RuntimeInstance("llama", state=RuntimeState.RUNNING, process_alive=True)
    assert available_runtime_family_ids(center(llama, instances={"llama": spoofed})) == frozenset()


def test_host_owned_live_managed_process_is_included():
    llama = RuntimeDefinition("llama", RuntimeType.LLAMA_CPP)
    values = available_runtime_family_ids(center(llama, owned={"llama": FakeProcess()}))
    assert values == frozenset({RUNTIME_FAMILY_LLAMA_CPP.taxonomy_id})


def test_dead_owned_managed_process_is_excluded():
    llama = RuntimeDefinition("llama", RuntimeType.LLAMA_CPP)
    assert available_runtime_family_ids(center(llama, owned={"llama": FakeProcess(1)})) == frozenset()


def test_generic_reachable_external_comfyui_is_excluded():
    comfy = RuntimeDefinition(
        "comfy", RuntimeType.COMFYUI, base_url="http://127.0.0.1:8188",
        port=8188, management=RuntimeManagement.EXTERNAL,
    )
    instance = RuntimeInstance(
        "comfy", state=RuntimeState.EXTERNAL, management=RuntimeManagement.EXTERNAL,
        http_reachable=True,
    )
    values = available_runtime_family_ids(center(comfy, instances={"comfy": instance}))
    assert values == frozenset()


def test_unknown_and_duplicate_runtime_entries_do_not_invent_families(tmp_path: Path):
    executable = tmp_path / "llama-server.exe"
    executable.write_bytes(b"runtime")
    llama = RuntimeDefinition("llama", RuntimeType.LLAMA_CPP, executable=str(executable))
    unknown = SimpleNamespace(id="unknown", runtime_type="UNKNOWN", management="MANAGED", executable=str(executable))
    model_center = SimpleNamespace(
        runtimes=(unknown, llama, llama),
        lifecycle=FakeLifecycle(owned={"llama": FakeProcess()}),
    )
    assert available_runtime_family_ids(model_center) == frozenset({RUNTIME_FAMILY_LLAMA_CPP.taxonomy_id})


def test_existing_node_identity_is_read_without_mutation(tmp_path: Path):
    identity, node_id, path = node_store(tmp_path)
    before = path.read_bytes()
    snapshot = build_host_hardware_snapshot(facts(), identity, center())
    assert snapshot.node.execution_node_id == node_id
    assert path.read_bytes() == before


def test_missing_node_fails_without_minting_identity(tmp_path: Path):
    path = tmp_path / "identity.json"
    identity = ExecutionNodeIdentityStore(path)
    with pytest.raises(HostHardwareInventoryError, match="EXECUTION_NODE_ID_UNAVAILABLE"):
        build_host_hardware_snapshot(facts(), identity, center())
    assert not path.exists()


def test_collection_does_not_mutate_model_center_config_or_routing(tmp_path: Path):
    identity, _, _ = node_store(tmp_path)
    config = tmp_path / "runtime.json"
    config.write_text(json.dumps({"schema_version": 1, "runtimes": {}}), encoding="utf-8")
    routes = {"TEXT": {"model_id": "model", "runtime_id": "runtime"}}
    model_center = center(config_path=config, routes=routes)
    before_file = config.read_bytes()
    before_routes = json.dumps(routes, sort_keys=True)
    build_host_hardware_snapshot(facts(), identity, model_center)
    assert config.read_bytes() == before_file
    assert json.dumps(routes, sort_keys=True) == before_routes


def test_deterministic_serialization_ignores_runtime_enumeration_order(tmp_path: Path):
    identity, _, _ = node_store(tmp_path)
    executable = tmp_path / "llama-server.exe"
    executable.write_bytes(b"runtime")
    llama = RuntimeDefinition("llama", RuntimeType.LLAMA_CPP, executable=str(executable))
    comfy = RuntimeDefinition(
        "comfy", RuntimeType.COMFYUI, base_url="http://127.0.0.1:8188",
        port=8188, management=RuntimeManagement.EXTERNAL,
    )
    instance = RuntimeInstance("comfy", state=RuntimeState.EXTERNAL, http_reachable=True)
    owned = {"llama": FakeProcess()}
    first = SimpleNamespace(runtimes=(llama, comfy), lifecycle=FakeLifecycle({"comfy": instance}, owned))
    second = SimpleNamespace(runtimes=(comfy, llama), lifecycle=FakeLifecycle({"comfy": instance}, owned))
    left = serialize_host_hardware_snapshot(build_host_hardware_snapshot(facts(), identity, first))
    right = serialize_host_hardware_snapshot(build_host_hardware_snapshot(facts(), identity, second))
    assert left == right
    assert left["runtime_family_ids"] == sorted(left["runtime_family_ids"])


def routing_scenario(snapshot: HardwareSnapshot):
    uid = lambda value: UUID(int=value)
    identity = RouteIdentity(
        provider=ProviderIdentity(provider_id=uid(1)),
        model=ModelIdentity(model_id=uid(2)),
        runtime=RuntimeIdentity(runtime_id=uid(3)),
        node=snapshot.node,
    )
    request = ProviderRoutingRequest(
        modality=Modality.TEXT,
        workspace_id=uid(4), user_id=uid(5), local_node=snapshot.node,
        privacy=PrivacyPolicy.DEVICE_ONLY,
        budget=BudgetPolicy(maximum_cost_microusd=0),
    )
    requirements = RuntimeRequirements(
        runtime_family_id=RUNTIME_FAMILY_LLAMA_CPP.taxonomy_id,
        architecture_id=ARCHITECTURE_X86_64.taxonomy_id,
        gpu_vendor_id=GPU_VENDOR_NVIDIA.taxonomy_id,
        minimum_vram_mib=4096,
        minimum_ram_mib=8192,
    )
    candidate = CandidateDescriptor(
        identity=identity, location=Location.DEVICE, owner_user_id=request.user_id,
        trusted=False, self_hosted=False,
        availability=Availability(**{name: True for name in Availability.model_fields}),
        capabilities=CapabilityDescriptor(
            supported_modalities=frozenset({Modality.TEXT}),
            input_asset_types=frozenset({AssetType.TEXT}),
            output_asset_types=frozenset({AssetType.TEXT}),
            requirements=requirements,
        ),
        estimated_cost_microusd=0,
    )
    return request, candidate


def test_existing_routing_policy_consumes_inventory_without_service_layer(tmp_path: Path):
    identity, _, _ = node_store(tmp_path)
    llama = RuntimeDefinition("llama", RuntimeType.LLAMA_CPP)
    snapshot = build_host_hardware_snapshot(
        facts(ram=16 * 1024 * MIB, gpus=(HostGpuFact(0x10DE, 8 * 1024 * MIB),)),
        identity,
        center(llama, owned={"llama": FakeProcess()}),
    )
    request, candidate = routing_scenario(snapshot)
    assert evaluate_routing(request, (candidate,), hardware=(snapshot,)).decision is Decision.ALLOW
    variants = (
        HardwareSnapshot(**{**snapshot.model_dump(), "architecture_id": ARCHITECTURE_ARM64.taxonomy_id}),
        HardwareSnapshot(**{**snapshot.model_dump(), "ram_mib": 8191}),
        HardwareSnapshot(**{**snapshot.model_dump(), "vram_mib": 4095}),
        HardwareSnapshot(**{**snapshot.model_dump(), "runtime_family_ids": frozenset()}),
    )
    for incompatible in variants:
        assert evaluate_routing(request, (candidate,), hardware=(incompatible,)).decision is Decision.NO_COMPATIBLE_ROUTE


@pytest.mark.skipif(sys.platform != "win32", reason="real Windows native acceptance")
def test_real_windows_probe_returns_truthful_minimum_facts():
    actual = WindowsHostHardwareProbe().collect()
    assert normalize_architecture(actual.architecture) in {
        ARCHITECTURE_X86_64.taxonomy_id, ARCHITECTURE_ARM64.taxonomy_id,
    }
    assert actual.physical_ram_bytes > 0
    assert actual.physical_ram_bytes // MIB > 0
    assert actual.gpus is None or isinstance(actual.gpus, tuple)


def test_inventory_module_has_no_execution_network_or_guessing_dependencies():
    import app.provider_runtime_v2_host_hardware_inventory as module

    source = inspect.getsource(module).casefold()
    for forbidden in (
        "uuid4", "nvidia-smi", "wmic", "get-ciminstance", "requests", "httpx",
        "urllib", "socket", "credential_vault", "stream_text", "start_runtime",
        "from . import dependencies",
    ):
        assert forbidden not in source
    assert "enumdisplaydevices" not in source
    assert "managed_executable_file" not in source
