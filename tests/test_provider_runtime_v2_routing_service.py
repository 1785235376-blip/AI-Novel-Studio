"""Orchestration tests: fake owners are private seams, never request authority."""
import builtins
import inspect
import json
import socket
import subprocess
import sys
import warnings
from dataclasses import replace
from types import SimpleNamespace
from uuid import UUID

import pytest
from pydantic import ValidationError

from app import provider_runtime_v2_routing_service as service
from app.provider_runtime_v2_contracts import (
    AssetType, Availability, BudgetPolicy, CandidateDescriptor, CapabilityDescriptor,
    CloudApproval, Decision, ExecutionNodeIdentity, HardwareSnapshot, Location,
    ModelIdentity, Modality, PrivacyPolicy, ProviderIdentity, ProviderRoutingRequest,
    RouteIdentity, RuntimeIdentity, RuntimeRequirements,
)
from app.provider_runtime_v2_host_hardware_inventory import HostHardwareInventoryError
from app.provider_runtime_v2_model_center_snapshot_bridge import (
    ProviderRuntimeSnapshot, SnapshotItem, SnapshotRejection, SnapshotRejectionCode,
)


@pytest.fixture(autouse=True)
def restore_global_settings():
    """Do not initialize global application services or Vault for these tests."""
    yield


def uid(n):
    return UUID(int=n)


def change(value, **updates):
    return type(value).model_validate({**dict(value), **updates})


@pytest.fixture
def facts(monkeypatch):
    node = ExecutionNodeIdentity(execution_node_id=uid(1))
    request = ProviderRoutingRequest(modality=Modality.TEXT, user_id=uid(2),
        workspace_id=uid(3), local_node=node, privacy=PrivacyPolicy.DEVICE_ONLY)
    candidate = CandidateDescriptor(
        identity=RouteIdentity(provider=ProviderIdentity(provider_id=uid(4)),
            model=ModelIdentity(model_id=uid(5)), runtime=RuntimeIdentity(runtime_id=uid(6)), node=node),
        location=Location.DEVICE,
        availability=Availability(configured=True, installed=True, healthy=True,
            reachable=True, authorized=False, compatible=False),
        capabilities=CapabilityDescriptor(supported_modalities=frozenset({Modality.TEXT}),
            input_asset_types=frozenset({AssetType.TEXT}), output_asset_types=frozenset({AssetType.TEXT}),
            requirements=RuntimeRequirements(runtime_family_id=uid(7), architecture_id=uid(8))))
    hardware = HardwareSnapshot(node=node, architecture_id=uid(8), ram_mib=32768,
        vram_mib=8192, runtime_family_ids=frozenset({uid(7)}))
    snapshot = ProviderRuntimeSnapshot("2.1A-snapshot-1", (SnapshotItem("source", candidate=candidate),))
    store = SimpleNamespace(get=lambda namespace, key: uid(1))
    owners = SimpleNamespace(runtime=SimpleNamespace(execution_node_identity=SimpleNamespace(store=store),
        provider_registry=object(), model_registry=object()), model_center_service=object())
    monkeypatch.setattr(service, "build_provider_runtime_snapshot", lambda *args: snapshot)
    monkeypatch.setattr(service, "collect_host_hardware_snapshot", lambda *args: hardware)
    return SimpleNamespace(request=request, candidate=candidate, hardware=hardware, snapshot=snapshot, owners=owners)


def test_production_request_only_and_current_profile_never_allows(facts, monkeypatch):
    assert tuple(inspect.signature(service.route_provider_request).parameters) == ("request",)
    monkeypatch.setitem(sys.modules, "app.dependencies", facts.owners)
    result = service.route_provider_request(facts.request)
    assert result.decision.decision is Decision.NO_COMPATIBLE_ROUTE
    assert result.decision.identity is None and result.decision.credential_handle is None
    assert result.snapshot_complete and result.candidate_count == 1
    assert result.hardware_status is service.HardwareStatus.AVAILABLE
    assert result.service_codes == ()
    assert facts.candidate.owner_user_id is None
    assert facts.candidate.estimated_cost_microusd is None
    assert not facts.candidate.availability.authorized
    assert not facts.candidate.availability.compatible


def test_host_absent_does_not_import_initialize_or_collect(facts, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("unexpected initialization")
    with monkeypatch.context() as guarded:
        guarded.delitem(sys.modules, "app.dependencies", raising=False)
        guarded.setattr(service, "build_provider_runtime_snapshot", forbidden)
        guarded.setattr(builtins, "__import__", forbidden)
        report = service.route_provider_request(facts.request)
        assert report.service_codes == (service.ServiceCode.HOST_NOT_INITIALIZED,)
        assert not report.snapshot_complete


@pytest.mark.parametrize("raw_request", [None, {}, "prompt-with-secret", 1])
def test_malformed_request_is_sanitized_without_sources(raw_request, facts):
    result = service.route_provider_request(raw_request)
    assert result.service_codes == (service.ServiceCode.INVALID_REQUEST,)
    assert "prompt-with-secret" not in json.dumps(result.to_dict())


def test_strict_request_forbids_extra_authority(facts):
    with pytest.raises(ValidationError):
        ProviderRoutingRequest.model_validate({**dict(facts.request), "candidates": (facts.candidate,)})
    with pytest.raises(ValidationError):
        ProviderRoutingRequest.model_validate_json(json.dumps({**facts.request.model_dump(mode="json"), "trusted": True}))


def test_request_approvals_are_not_host_authority(facts):
    approval = CloudApproval(identity=facts.candidate.identity, user_id=facts.request.user_id,
        workspace_id=facts.request.workspace_id, maximum_cost_microusd=100)
    request = change(facts.request, budget=BudgetPolicy(approvals=(approval,)))
    result = service._route_with_owners(request, facts.owners)
    assert result.service_codes == (service.ServiceCode.REQUEST_AUTHORITY_UNSUPPORTED,)


def test_request_wrong_node_is_rejected_not_rewritten(facts):
    request = change(facts.request, local_node=ExecutionNodeIdentity(execution_node_id=uid(99)))
    result = service._route_with_owners(request, facts.owners)
    assert result.service_codes == (service.ServiceCode.REQUEST_NODE_MISMATCH,)
    assert result.hardware_status is service.HardwareStatus.NOT_COLLECTED


@pytest.mark.parametrize("privacy", list(PrivacyPolicy))
def test_no_privacy_profile_creates_authority(facts, privacy):
    request = change(facts.request, privacy=privacy, candidate_locations=frozenset(Location))
    assert service._route_with_owners(request, facts.owners).decision.decision is Decision.NO_COMPATIBLE_ROUTE


@pytest.mark.parametrize("updates", [dict(owner_user_id=uid(2)), dict(workspace_id=uid(3)),
    dict(trusted=True), dict(self_hosted=True), dict(estimated_cost_microusd=0),
    dict(quality_score=100), dict(estimated_latency_ms=0), dict(location=Location.CLOUD)])
def test_snapshot_profile_cannot_invent_authorities(facts, monkeypatch, updates):
    candidate = change(facts.candidate, **updates)
    snapshot = replace(facts.snapshot, items=(SnapshotItem("source", candidate=candidate),))
    monkeypatch.setattr(service, "build_provider_runtime_snapshot", lambda *a: snapshot)
    result = service._route_with_owners(facts.request, facts.owners)
    assert result.service_codes == (service.ServiceCode.SNAPSHOT_PROFILE_UNSUPPORTED,)


@pytest.mark.parametrize("field", ["authorized", "compatible"])
def test_positive_availability_authority_is_not_silently_accepted(facts, monkeypatch, field):
    candidate = change(facts.candidate, availability=change(facts.candidate.availability, **{field: True}))
    monkeypatch.setattr(service, "build_provider_runtime_snapshot", lambda *a:
        replace(facts.snapshot, items=(SnapshotItem("source", candidate=candidate),)))
    assert service._route_with_owners(facts.request, facts.owners).service_codes == (service.ServiceCode.SNAPSHOT_PROFILE_UNSUPPORTED,)


@pytest.mark.parametrize("snapshot,code", [
    (None, service.ServiceCode.SNAPSHOT_INVALID),
    (ProviderRuntimeSnapshot("future", ()), service.ServiceCode.SNAPSHOT_VERSION_UNSUPPORTED),
    (ProviderRuntimeSnapshot("2.1A-snapshot-1", []), service.ServiceCode.SNAPSHOT_INVALID),
    (ProviderRuntimeSnapshot("2.1A-snapshot-1", (None,)), service.ServiceCode.SNAPSHOT_INVALID),
    (ProviderRuntimeSnapshot("2.1A-snapshot-1", (None,) * (service.MAX_SOURCE_ITEMS + 1)), service.ServiceCode.SNAPSHOT_LIMIT_EXCEEDED),
])
def test_malformed_version_and_oversized_sources_fail_whole_snapshot(facts, monkeypatch, snapshot, code):
    monkeypatch.setattr(service, "build_provider_runtime_snapshot", lambda *args: snapshot)
    report = service._route_with_owners(facts.request, facts.owners)
    assert report.service_codes == (code,)
    assert not report.snapshot_complete and report.candidate_count == 0


def test_duplicate_route_facts_remain_policy_deny(facts, monkeypatch):
    snapshot = replace(facts.snapshot, items=(facts.snapshot.items[0], SnapshotItem("other", candidate=facts.candidate)))
    monkeypatch.setattr(service, "build_provider_runtime_snapshot", lambda *args: snapshot)
    result = service._route_with_owners(facts.request, facts.owners)
    assert result.decision.decision is Decision.DENY
    assert result.decision.reason_code.value == "CONFLICTING_FACTS"


def test_duplicate_source_keys_and_invalid_rejection_fail_closed(facts, monkeypatch):
    bad_rejection = SnapshotItem("secret", rejection=SnapshotRejection("unknown", "secret"))
    for items in ((facts.snapshot.items[0], facts.snapshot.items[0]), (bad_rejection,)):
        monkeypatch.setattr(service, "build_provider_runtime_snapshot", lambda *args: replace(facts.snapshot, items=items))
        assert service._route_with_owners(facts.request, facts.owners).service_codes == (service.ServiceCode.SNAPSHOT_INVALID,)


def test_snapshot_and_hardware_require_host_node(facts, monkeypatch):
    node = ExecutionNodeIdentity(execution_node_id=uid(99))
    candidate = change(facts.candidate, identity=change(facts.candidate.identity, node=node))
    monkeypatch.setattr(service, "build_provider_runtime_snapshot", lambda *args:
        replace(facts.snapshot, items=(SnapshotItem("source", candidate=candidate),)))
    assert service._route_with_owners(facts.request, facts.owners).service_codes == (service.ServiceCode.SNAPSHOT_NODE_MISMATCH,)
    monkeypatch.setattr(service, "build_provider_runtime_snapshot", lambda *args: facts.snapshot)
    monkeypatch.setattr(service, "collect_host_hardware_snapshot", lambda *args: change(facts.hardware, node=node))
    assert service._route_with_owners(facts.request, facts.owners).service_codes == (service.ServiceCode.HARDWARE_NODE_MISMATCH,)


def test_bounded_rejections_only_closed_codes_and_counts_are_serialized(facts, monkeypatch):
    code = SnapshotRejectionCode.MISSING_MODEL_IDENTITY
    items = tuple(SnapshotItem(f"/private/path/token-prompt-{i}", rejection=SnapshotRejection(
        code, f"/private/path/token-prompt-{i}", "https://secret.example/password"))
        for i in range(service.MAX_SOURCE_ITEMS))
    monkeypatch.setattr(service, "build_provider_runtime_snapshot", lambda *a: replace(facts.snapshot, items=items))
    report = service._route_with_owners(facts.request, facts.owners)
    serialized = json.dumps(report.to_dict())
    assert report.source_item_count == report.rejection_count == service.MAX_SOURCE_ITEMS
    assert report.source_rejections == (service.RejectionCount(code=code, count=service.MAX_SOURCE_ITEMS),)
    for forbidden in ("source_key", "/private", "token-prompt", "secret.example", "password"):
        assert forbidden not in serialized
    assert len(serialized) < 1000


@pytest.mark.parametrize("source", ["snapshot", "hardware", "identity"])
def test_source_exceptions_do_not_escape_or_leak(facts, monkeypatch, source):
    def fail(*a):
        raise RuntimeError("/private/path?api_key=secret&prompt=private")
    if source == "snapshot":
        monkeypatch.setattr(service, "build_provider_runtime_snapshot", fail)
    elif source == "hardware":
        monkeypatch.setattr(service, "collect_host_hardware_snapshot", fail)
    else:
        facts.owners.runtime.execution_node_identity.store.get = fail
    report = service._route_with_owners(facts.request, facts.owners)
    assert report.service_codes
    assert "private" not in json.dumps(report.to_dict())
    assert report.decision.decision is Decision.NO_COMPATIBLE_ROUTE


@pytest.mark.parametrize("code", ["UNSUPPORTED_PLATFORM", "RAM_FACT_UNAVAILABLE", "UNKNOWN_ARCHITECTURE", "secret-path"])
def test_hardware_failure_codes_are_explicit_and_allowlisted(facts, monkeypatch, code):
    def fail(*a):
        raise HostHardwareInventoryError(code)
    monkeypatch.setattr(service, "collect_host_hardware_snapshot", fail)
    report = service._route_with_owners(facts.request, facts.owners)
    expected = service.HardwareStatus.UNAVAILABLE if code == "secret-path" else service.HardwareStatus(code)
    assert report.hardware_status is expected
    assert report.service_codes == (service.ServiceCode.HARDWARE_SOURCE_FAILED,)
    assert "secret-path" not in json.dumps(report.to_dict())


def test_reports_are_deeply_immutable_and_serialization_detached(facts):
    report = service._route_with_owners(facts.request, facts.owners)
    with pytest.raises(ValidationError):
        report.candidate_count = 99
    with pytest.raises(ValidationError):
        report.decision.identity = facts.candidate.identity
    value = report.to_dict()
    value["decision"]["decision"] = "ALLOW"
    value["service_codes"].append("new")
    assert report.decision.decision is Decision.NO_COMPATIBLE_ROUTE and report.service_codes == ()


def test_orchestration_has_no_io_execution_or_credentials(facts, monkeypatch):
    monkeypatch.setitem(sys.modules, "app.dependencies", facts.owners)
    def fail(*a, **k):
        raise AssertionError("I/O or execution attempted")
    monkeypatch.setattr(builtins, "open", fail)
    monkeypatch.setattr(socket, "socket", fail)
    monkeypatch.setattr(subprocess, "Popen", fail)
    monkeypatch.setattr(subprocess, "run", fail)
    result = service.route_provider_request(facts.request)
    assert result.service_codes == ()  # traps must not be hidden as source failures
    assert result.snapshot_complete


def test_real_bridge_registered_owners_inventory_and_store_unchanged(tmp_path, monkeypatch):
    # Initialization is test setup, deliberately outside the read-only operation.
    from app.model_center import create_default_model_center
    from app.model_runtime import ModelDescriptor, ProviderDescriptor, Modality as RegistryModality
    from app.model_runtime import ProviderRegistry, ModelRegistry
    from app.stable_identity import StableIdentityStore, ARCHITECTURE_X86_64
    from app.provider_runtime_v2_host_hardware_inventory import HostHardwareFacts, MIB, build_host_hardware_snapshot
    from app.provider_runtime_v2_model_center_snapshot_bridge import build_provider_runtime_snapshot
    store = StableIdentityStore(tmp_path / "identity.json")
    store.get_or_create("execution_node", "local")
    runtime = SimpleNamespace(provider_registry=ProviderRegistry(store), model_registry=ModelRegistry(store),
        execution_node_identity=SimpleNamespace(store=store))
    center = create_default_model_center(tmp_path / "runtime.json", identity_store=store)
    model = center.models["qwen36-27b-q4km"]
    # Explicit test requirement; never populated by the new service itself.
    center.runtimes["llama-cpp-local"] = replace(center.runtimes["llama-cpp-local"], architecture_id=ARCHITECTURE_X86_64.taxonomy_id)
    runtime.provider_registry.register(ProviderDescriptor("ollama", "Ollama", "local",
        frozenset({RegistryModality.TEXT}), True, True), object(), replace=True)
    runtime.model_registry.register(ModelDescriptor(model.id, "ollama", model.display_name,
        RegistryModality.TEXT, frozenset({"generate", "stream"}), streaming=True, identity_id=model.identity_id), replace=True)
    owners = SimpleNamespace(runtime=runtime, model_center_service=center)
    node = ExecutionNodeIdentity(execution_node_id=store.get("execution_node", "local"))
    request = ProviderRoutingRequest(modality=Modality.TEXT, user_id=uid(2), workspace_id=uid(3),
        local_node=node, privacy=PrivacyPolicy.DEVICE_ONLY)
    monkeypatch.setattr(service, "build_provider_runtime_snapshot", build_provider_runtime_snapshot)
    monkeypatch.setattr(service, "collect_host_hardware_snapshot", lambda identity, center:
        build_host_hardware_snapshot(HostHardwareFacts("AMD64", 32768 * MIB, ()), identity, center))
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    monkeypatch.setitem(sys.modules, "app.dependencies", owners)
    report = service.route_provider_request(request)
    after = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    assert before == after
    assert report.snapshot_complete and report.candidate_count >= 1
    assert report.hardware_status is service.HardwareStatus.AVAILABLE
    assert report.decision.decision is Decision.NO_COMPATIBLE_ROUTE
    assert report.service_codes == ()


def test_invalid_nested_values_never_emit_input_in_serialization_warnings(facts, monkeypatch):
    canary = "SECRET-CANARY:/private/path"
    # Deliberate validation bypass exercises the boundary, never production use.
    request = facts.request.model_copy(update={"budget": canary})
    candidate = facts.candidate.model_copy(update={"availability": canary})
    hardware = facts.hardware.model_copy(update={"ram_mib": canary})
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert service.route_provider_request(request).service_codes == (service.ServiceCode.INVALID_REQUEST,)
        monkeypatch.setattr(service, "build_provider_runtime_snapshot", lambda *a:
            replace(facts.snapshot, items=(SnapshotItem("source", candidate=candidate),)))
        assert service._route_with_owners(facts.request, facts.owners).service_codes == (service.ServiceCode.SNAPSHOT_INVALID,)
        monkeypatch.setattr(service, "build_provider_runtime_snapshot", lambda *a: facts.snapshot)
        monkeypatch.setattr(service, "collect_host_hardware_snapshot", lambda *a: hardware)
        assert service._route_with_owners(facts.request, facts.owners).service_codes == (service.ServiceCode.HARDWARE_INVALID,)
    assert not caught
