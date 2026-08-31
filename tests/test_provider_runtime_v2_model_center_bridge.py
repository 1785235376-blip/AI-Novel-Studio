import ast
import json
from pathlib import Path
from uuid import UUID

import pytest

from app.provider_runtime_v2_contracts import *
from app.provider_routing_policy_v2 import evaluate_routing
from app.provider_runtime_v2_model_center_bridge import (
    BRIDGE_VERSION,
    ModelCenterFactSource,
    ModelCenterHardwareFact,
    ModelCenterInstanceFact,
    ModelCenterModelFact,
    ModelCenterRuntimeFact,
    ModelCenterSnapshotBridge,
    ProviderRuntimeSnapshotBundle,
    SnapshotReason,
    build_provider_runtime_snapshots,
    capture_model_center_facts,
)


@pytest.fixture(autouse=True)
def restore_global_settings():
    """Bridge tests do not initialize app runtime or Vault."""
    yield


def uid(n):
    return UUID(int=n)


def facts(
    model_status="READY",
    runtime_status="CONFIGURED",
    state=None,
    process_alive=False,
    http_reachable=False,
    bind="127.0.0.1",
    caps=("TEXT",),
    runtime_type="LLAMA_CPP",
    model_id="qwen36-27b-q4km",
    runtime_id="llama-cpp-local",
    provider="OPENAI_COMPATIBLE_TEXT",
    family="QWEN3.6",
):
    instances = ()
    if state is not None:
        instances = (ModelCenterInstanceFact(
            runtime_registry_id=runtime_id, state=state,
            process_alive=process_alive, http_reachable=http_reachable,
        ),)
    return ModelCenterFactSource(
        models=(ModelCenterModelFact(
            registry_id=model_id, runtime_type=runtime_type, status=model_status,
            capabilities=caps, family=family,
        ),),
        runtimes=(ModelCenterRuntimeFact(
            registry_id=runtime_id, runtime_type=runtime_type, status=runtime_status,
            provider_adapter=provider, bind_address=bind,
        ),),
        instances=instances,
        hardware_profiles=(ModelCenterHardwareFact(
            profile_id="profile-1", model_registry_id=model_id, tested=True,
        ),),
    )


def bundle_of(**kwargs):
    return ModelCenterSnapshotBridge.build(facts(**kwargs))


def rejection_of(**kwargs):
    bundle = bundle_of(**kwargs)
    assert len(bundle.rejections) == 1
    return bundle.rejections[0]


def routing_request():
    return ProviderRoutingRequest(
        modality=Modality.TEXT, workspace_id=uid(100), user_id=uid(101),
        local_node=ExecutionNodeIdentity(execution_node_id=uid(1)),
        privacy=PrivacyPolicy.DEVICE_ONLY,
    )


def assert_non_routable(bundle):
    assert bundle.candidates == ()
    assert bundle.hardware == ()
    assert bundle.credentials == ()
    decision = evaluate_routing(
        routing_request(), bundle.candidates, bundle.credentials, bundle.hardware,
    )
    assert decision.decision != Decision.ALLOW
    assert decision.identity is None
    assert decision.credential_handle is None


def test_default_model_center_never_emits_route_identity():
    from app.model_center.service import create_default_model_center
    bundle = ModelCenterSnapshotBridge.from_model_center(create_default_model_center())
    assert bundle.bridge_version == BRIDGE_VERSION
    assert_non_routable(bundle)
    reasons = {reason for item in bundle.rejections for reason in item.reasons}
    assert SnapshotReason.MISSING_PROVIDER_IDENTITY in reasons
    assert SnapshotReason.MISSING_MODEL_IDENTITY in reasons
    assert SnapshotReason.MISSING_RUNTIME_IDENTITY in reasons
    assert SnapshotReason.MISSING_EXECUTION_NODE_IDENTITY in reasons
    assert SnapshotReason.MISSING_HARDWARE_FACT in reasons
    assert SnapshotReason.RUNTIME_UNAUTHORIZED in reasons
    qwen = next(item for item in bundle.rejections if item.model_registry_id == "qwen36-27b-q4km")
    assert qwen.runtime_registry_id == "llama-cpp-local"
    assert qwen.location == Location.DEVICE
    assert qwen.mapped_modalities == frozenset({Modality.TEXT})
    assert qwen.availability.authorized is False
    assert qwen.availability.compatible is False
    assert qwen.availability.configured is True
    assert qwen.availability.installed is False


@pytest.mark.parametrize("field,value", [
    ("model_id", "qwen36-27b-q4km"),
    ("runtime_id", "llama-cpp-local"),
    ("provider", "OPENAI_COMPATIBLE_TEXT"),
    ("model_id", "Qwen 3.6 Display"),
    ("runtime_id", "/usr/bin/llama-server"),
    ("provider", "http://127.0.0.1:8081"),
    ("model_id", "flux2-klein-4b-fp8"),
    ("runtime_id", "comfyui-local"),
])
def test_string_slugs_names_paths_and_urls_are_not_identities(field, value):
    item = rejection_of(**{field: value})
    assert SnapshotReason.MISSING_EXECUTION_NODE_IDENTITY in item.reasons
    if field == "model_id":
        assert SnapshotReason.MISSING_MODEL_IDENTITY in item.reasons
    if field == "runtime_id":
        assert SnapshotReason.MISSING_RUNTIME_IDENTITY in item.reasons
    if field == "provider":
        assert SnapshotReason.MISSING_PROVIDER_IDENTITY in item.reasons
    assert_non_routable(bundle_of(**{field: value}))


def test_uuid_shaped_registry_ids_still_lack_execution_node_and_hardware():
    model_id = str(uid(11))
    runtime_id = str(uid(12))
    provider = str(uid(13))
    item = rejection_of(model_id=model_id, runtime_id=runtime_id, provider=provider)
    assert SnapshotReason.MISSING_MODEL_IDENTITY not in item.reasons
    assert SnapshotReason.MISSING_RUNTIME_IDENTITY not in item.reasons
    assert SnapshotReason.MISSING_PROVIDER_IDENTITY not in item.reasons
    assert SnapshotReason.MISSING_EXECUTION_NODE_IDENTITY in item.reasons
    assert SnapshotReason.MISSING_HARDWARE_FACT in item.reasons
    assert_non_routable(bundle_of(model_id=model_id, runtime_id=runtime_id, provider=provider))


def test_missing_execution_node_identity_is_structural():
    source = facts()
    assert not hasattr(source, "execution_node_id")
    assert "execution_node" not in ModelCenterFactSource.model_fields
    assert all(SnapshotReason.MISSING_EXECUTION_NODE_IDENTITY in item.reasons for item in bundle_of().rejections)


@pytest.mark.parametrize("caps,mapped,unknown,assets,expect_unknown,expect_unsupported", [
    (("TEXT",), {Modality.TEXT}, frozenset(), {AssetType.TEXT}, False, False),
    (("IMAGE",), {Modality.IMAGE}, frozenset(), {AssetType.IMAGE}, False, False),
    (("VIDEO",), {Modality.VIDEO}, frozenset(), {AssetType.VIDEO}, False, False),
    (("TTS",), {Modality.TTS}, frozenset(), {AssetType.AUDIO}, False, False),
    (("AUDIO",), {Modality.AUDIO}, frozenset(), {AssetType.AUDIO}, False, False),
    (("EMBEDDING",), {Modality.EMBEDDING}, frozenset(), frozenset(), False, False),
    (("RESTORATION",), frozenset(), {"RESTORATION"}, frozenset(), True, True),
    (("INTERPOLATION",), frozenset(), {"INTERPOLATION"}, frozenset(), True, True),
    (("VISION",), frozenset(), {"VISION"}, frozenset(), True, True),
    (("RERANK",), frozenset(), {"RERANK"}, frozenset(), True, True),
    (("TEXT", "VISION"), {Modality.TEXT}, {"VISION"}, {AssetType.TEXT}, True, False),
    ((), frozenset(), frozenset(), frozenset(), False, True),
])
def test_capability_normalization_does_not_guess(caps, mapped, unknown, assets, expect_unknown, expect_unsupported):
    item = rejection_of(caps=caps, family="qwen")
    assert item.mapped_modalities == frozenset(mapped)
    assert item.unknown_capabilities == frozenset(unknown)
    assert item.input_asset_types == frozenset(assets)
    assert item.output_asset_types == frozenset(assets)
    assert (SnapshotReason.UNKNOWN_CAPABILITY in item.reasons) is expect_unknown
    assert (SnapshotReason.UNSUPPORTED_MODALITY in item.reasons) is expect_unsupported


def test_family_or_runtime_name_is_not_a_capability():
    item = rejection_of(caps=(), family="qwen", runtime_id="llama-cpp-local")
    assert item.mapped_modalities == frozenset()
    assert SnapshotReason.UNSUPPORTED_MODALITY in item.reasons


@pytest.mark.parametrize("status,installed", [
    ("NOT_INSTALLED", False),
    ("MISSING_COMPONENT", False),
    ("RUNTIME_REQUIRED", False),
    ("LICENSE_REQUIRED", False),
    ("READY", False),
    ("DISCOVERED", False),
    ("DEGRADED", False),
])
def test_catalog_status_without_instance_is_not_runtime_installed(status, installed):
    item = rejection_of(model_status=status)
    assert item.availability.installed is installed
    assert SnapshotReason.RUNTIME_NOT_INSTALLED in item.reasons


def test_availability_dimensions_stay_distinct():
    running = rejection_of(state="RUNNING", process_alive=True, http_reachable=True)
    assert running.availability.configured is True
    assert running.availability.installed is True
    assert running.availability.healthy is True
    assert running.availability.reachable is True
    assert running.availability.authorized is False
    assert running.availability.compatible is False
    assert SnapshotReason.RUNTIME_UNAUTHORIZED in running.reasons
    assert SnapshotReason.RUNTIME_INCOMPATIBLE in running.reasons
    stopped = rejection_of(state="STOPPED", process_alive=False, http_reachable=False)
    assert stopped.availability.installed is False
    assert stopped.availability.healthy is False
    assert stopped.availability.reachable is False
    unreachable = rejection_of(state="RUNNING", process_alive=True, http_reachable=False)
    assert unreachable.availability.healthy is True
    assert unreachable.availability.reachable is False
    assert SnapshotReason.RUNTIME_UNREACHABLE in unreachable.reasons
    external = rejection_of(state="EXTERNAL", process_alive=False, http_reachable=True)
    assert external.availability.healthy is True
    assert external.availability.reachable is True
    assert external.availability.installed is True


def test_runtime_not_configured_unhealthy_and_incompatible():
    pending = rejection_of(runtime_status="PENDING")
    assert pending.availability.configured is False
    assert SnapshotReason.RUNTIME_NOT_CONFIGURED in pending.reasons
    failed = rejection_of(state="FAILED", process_alive=False, http_reachable=False)
    assert failed.availability.healthy is False
    assert SnapshotReason.RUNTIME_UNHEALTHY in failed.reasons
    assert SnapshotReason.RUNTIME_INCOMPATIBLE in failed.reasons
    assert SnapshotReason.MISSING_HARDWARE_FACT in failed.reasons


def test_hardware_numbers_without_uuid_architecture_remain_non_routable():
    source = facts()
    source = ModelCenterFactSource(
        models=source.models, runtimes=source.runtimes, instances=source.instances,
        hardware_profiles=(ModelCenterHardwareFact(
            profile_id="qwen36-rtx5080-8k", model_registry_id="qwen36-27b-q4km",
            vram_required=16, ram_required=32, context=8192, tested=True,
        ),),
    )
    bundle = build_provider_runtime_snapshots(source)
    assert bundle.hardware == ()
    assert SnapshotReason.MISSING_HARDWARE_FACT in bundle.rejections[0].reasons
    assert_non_routable(bundle)


@pytest.mark.parametrize("bind,location", [
    ("127.0.0.1", Location.DEVICE),
    ("::1", Location.DEVICE),
    ("localhost", None),
    ("0.0.0.0", None),
    ("192.168.1.10", None),
    ("10.0.0.5", None),
    ("8.8.8.8", None),
    ("", None),
])
def test_location_is_device_only_for_loopback_literals(bind, location):
    item = rejection_of(bind=bind)
    assert item.location == location
    if location is None:
        assert SnapshotReason.UNSUPPORTED_LOCATION in item.reasons
    assert SnapshotReason.TEAM_COMPUTE_SUBSTITUTION_FORBIDDEN not in item.reasons or location is None
    assert_non_routable(bundle_of(bind=bind))


@pytest.mark.parametrize("overrides,extra", [
    ({"trusted": True}, SnapshotReason.PLUGIN_TRUST_SUBSTITUTION_FORBIDDEN),
    ({"authorized": True}, SnapshotReason.PLUGIN_TRUST_SUBSTITUTION_FORBIDDEN),
    ({"healthy": True, "compatible": True}, SnapshotReason.PLUGIN_TRUST_SUBSTITUTION_FORBIDDEN),
    ({"plugin_verified": True}, SnapshotReason.PLUGIN_TRUST_SUBSTITUTION_FORBIDDEN),
    ({"verified": True}, SnapshotReason.PLUGIN_TRUST_SUBSTITUTION_FORBIDDEN),
    ({"credential": "secret"}, SnapshotReason.CREDENTIAL_RESOLUTION_FORBIDDEN),
    ({"api_key": "sk-test"}, SnapshotReason.CREDENTIAL_RESOLUTION_FORBIDDEN),
    ({"vault": True}, SnapshotReason.CREDENTIAL_RESOLUTION_FORBIDDEN),
    ({"team_compute": True}, SnapshotReason.TEAM_COMPUTE_SUBSTITUTION_FORBIDDEN),
    ({"location": "CLOUD"}, SnapshotReason.TEAM_COMPUTE_SUBSTITUTION_FORBIDDEN),
    ({"execution_node_id": str(uid(1))}, SnapshotReason.TEAM_COMPUTE_SUBSTITUTION_FORBIDDEN),
])
def test_caller_overrides_are_rejected(overrides, extra):
    bundle = build_provider_runtime_snapshots(facts(), caller_overrides=overrides)
    assert_non_routable(bundle)
    reasons = bundle.rejections[0].reasons
    assert SnapshotReason.UNTRUSTED_CALLER_OVERRIDE in reasons
    assert extra in reasons
    assert all(item.availability.authorized is False for item in bundle.rejections)


def test_no_credential_resolution_or_plugin_trust_substitution():
    bundle = bundle_of(state="RUNNING", process_alive=True, http_reachable=True)
    assert bundle.credentials == ()
    assert all(item.availability.authorized is False for item in bundle.rejections)
    dumped = json.loads(bundle.model_dump_json())
    blob = json.dumps(dumped)
    for forbidden in ("api_key", "password", "secret", "token", "executable", "launch_arguments"):
        assert forbidden not in bundle.model_dump()
    assert "sk-" not in blob


def test_capture_omits_executables_secrets_and_process_objects():
    from app.model_center.service import create_default_model_center
    source = capture_model_center_facts(create_default_model_center())
    dumped = source.model_dump()
    blob = json.dumps(dumped)
    for forbidden in ("executable", "environment", "launch_arguments", "model_path",
                      "working_directory", "base_url", "process_id", "api_key", "secret"):
        assert forbidden not in blob
    assert {item.registry_id for item in source.runtimes} == {"comfyui-local", "llama-cpp-local"}
    assert "qwen36-27b-q4km" in {item.registry_id for item in source.models}


def test_deterministic_and_immutable():
    source = facts()
    first = build_provider_runtime_snapshots(source)
    second = build_provider_runtime_snapshots(source)
    assert first == second
    with pytest.raises(Exception):
        first.candidates = (first.candidates[0] if first.candidates else None,)
    roundtrip = ProviderRuntimeSnapshotBundle.model_validate_json(first.model_dump_json())
    assert roundtrip == first


def test_bridge_has_no_io_or_identity_minting(monkeypatch):
    import builtins
    import hashlib
    import io
    import os
    import pathlib
    import socket
    import subprocess
    import uuid as uuid_mod
    source = facts()
    def forbidden(*args, **kwargs):
        raise AssertionError("bridge attempted I/O or identity minting")
    with monkeypatch.context() as patch:
        for obj, name in (
            (builtins, "open"), (io, "open"), (os, "open"), (os, "system"),
            (pathlib.Path, "open"), (socket, "socket"), (socket, "create_connection"),
            (subprocess, "Popen"), (subprocess, "run"),
            (uuid_mod, "uuid1"), (uuid_mod, "uuid3"), (uuid_mod, "uuid4"), (uuid_mod, "uuid5"),
            (hashlib, "md5"), (hashlib, "sha1"), (hashlib, "sha256"),
        ):
            patch.setattr(obj, name, forbidden)
        bundle = build_provider_runtime_snapshots(source)
        assert_non_routable(bundle)


def test_bridge_module_imports_stay_pure():
    root = Path(__file__).resolve().parents[1]
    tree = ast.parse((root / "app" / "provider_runtime_v2_model_center_bridge.py").read_text())
    permitted = {
        "__future__", "enum", "typing", "uuid", "ipaddress",
        "app.provider_runtime_v2_contracts",
    }
    forbidden_modules = {
        "subprocess", "socket", "hashlib", "requests", "httpx", "urllib",
        "app.credential_vault", "app.plugin_trust_contracts", "app.plugin_runtime_contracts",
        "app.model_center.service",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module in permitted
            assert node.module not in forbidden_modules
        if isinstance(node, ast.Import):
            assert all(alias.name in permitted for alias in node.names)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "uuid":
                assert node.func.attr not in {"uuid1", "uuid3", "uuid4", "uuid5"}
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"open", "exec", "eval", "__import__", "compile"}


def test_existing_provider_runtime_contracts_are_untouched():
    root = Path(__file__).resolve().parents[1]
    for name in ("provider_runtime_v2_contracts.py", "provider_routing_policy_v2.py"):
        tree = ast.parse((root / "app" / name).read_text())
        modules = {
            node.module for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        assert "app.provider_runtime_v2_model_center_bridge" not in modules
        assert "app.model_center" not in modules
        assert "app.model_center.service" not in modules
