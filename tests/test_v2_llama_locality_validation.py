"""Original llama discovery locality, with synthetic metadata and no model process."""
from types import SimpleNamespace

import pytest

from app.asset_providers import AssetProviderRegistry
from app.model_center.discovery_bridge import LocalDiscoveryBridge
from app.model_center.discovery import LocalDiscoveryService
from app.model_center.discovery_probes import ProbeFailure
from app.model_center.discovery_types import LocalRuntimeInput
from app.model_execution import LocalModelInvocation
from app.model_runtime import ModelRegistry, ModelRuntimeError, ProviderRegistry, TextGenerationRequest
from test_local_ai_discovery import FixtureClient, approve_license, gguf, scan, service


def llama_fixture(tmp_path, *, alias="configured-text-alias", management="EXTERNAL"):
    svc = service(tmp_path)
    path = tmp_path / "qwen.gguf"
    gguf(path)
    endpoint = "http://127.0.0.1:19991"
    executable = ""
    if management == "MANAGED":
        executable = str(tmp_path / "llama-server")
        (tmp_path / "llama-server").write_bytes(b"SYNTHETIC_NOT_EXECUTABLE")
    runtime = svc.configure_runtime(LocalRuntimeInput(name="Synthetic llama", type="LLAMA_CPP",
        endpoint=endpoint, model_path=str(path), model_id=alias, management=management,
        executable=executable))
    svc.client.payloads[(endpoint, "/v1/models")] = {"data": [{"id": alias or path.name}]}
    host = SimpleNamespace(provider_registry=ProviderRegistry(), model_registry=ModelRegistry(),
                           is_remote_text_provider=lambda _: False)
    svc.route_bridge = LocalDiscoveryBridge(svc, host, AssetProviderRegistry())
    candidate = next(row for row in scan(svc)["candidates"] if row["runtime_id"] == runtime["id"])
    return svc, host, candidate, runtime, path


def enable(svc, candidate):
    identifier = candidate["id"]
    svc.validate(identifier)
    svc.register(identifier)
    approve_license(svc, identifier)
    return svc.enable(identifier)


@pytest.mark.parametrize("alias", ["configured-text-alias", ""])
def test_verified_external_llama_enters_unchanged_local_invocation_gate(tmp_path, alias):
    svc, host, candidate, _, _ = llama_fixture(tmp_path, alias=alias)
    enabled = enable(svc, candidate)
    # Regression: before locality evidence, the original invocation rejected this
    # registered, licensed and enabled llama with GRAPH_VERIFIED_LOCAL_MODEL_REQUIRED.
    invocation = LocalModelInvocation(host, candidate["provider_id"], candidate["id"])
    assert invocation._provider is host.provider_registry.resolve(candidate["provider_id"])
    assert enabled["source_locality"] == "LOCAL_VERIFIED" and enabled["local"]
    assert enabled["verified_capabilities"] == ["TEXT"]
    assert enabled["model_evidence_fingerprint"] and enabled["runtime_fingerprint"]
    assert not enabled["verified"] and "INFERENCE_NOT_RUN" in enabled["validation_notes"]
    assert all(body is None for _, _, body in svc.client.calls)
    assert all(path != "/v1/chat/completions" for _, path, _ in svc.client.calls)
    svc.center.lifecycle.start.assert_not_called()


@pytest.mark.parametrize("change,blocker", [
    ("missing", "GGUF_HEADER_INVALID"), ("header", "GGUF_HEADER_INVALID"),
    ("architecture", "CAPABILITY_UNVERIFIED"), ("linked", "GGUF_HEADER_INVALID"),
    ("mismatched_path", "RUNTIME_MODEL_PATH_MISMATCH"),
    ("alias", "RUNTIME_MODEL_UNVERIFIED"), ("not_running", "RUNTIME_MODEL_UNVERIFIED"),
])
def test_external_llama_requires_all_locality_evidence(tmp_path, change, blocker):
    svc, _, candidate, config, path = llama_fixture(tmp_path)
    if change == "missing": path.unlink()
    elif change == "header": path.write_bytes(b"INVALID_GGUF")
    elif change == "architecture": gguf(path, arch="clip")
    elif change == "linked":
        target = tmp_path / "different.gguf"
        gguf(target)
        path.unlink()
        path.symlink_to(target)
    elif change == "mismatched_path":
        target = tmp_path / "different.gguf"
        gguf(target)
        svc.configure_runtime(LocalRuntimeInput.model_validate({
            **{k: v for k, v in config.items() if k != "id"}, "model_path": str(target)}), config["id"])
    elif change == "alias": svc.client.payloads[(config["endpoint"], "/v1/models")] = {"data": [{"id": "different-alias"}]}
    else: svc.client.payloads[(config["endpoint"], "/v1/models")] = ProbeFailure("LOCAL_AI_PROBE_UNAVAILABLE")
    validated = svc.validate(candidate["id"])
    assert validated["source_locality"] == "NOT_VERIFIED" and not validated["local"]
    assert blocker in validated["enable_blockers"]
    svc.register(candidate["id"])
    approve_license(svc, candidate["id"])
    with pytest.raises(ValueError, match="LOCAL_AI_ENABLE_BLOCKED"):
        svc.enable(candidate["id"])
    assert not svc.registrations[candidate["id"]]["enabled"]
    svc.center.lifecycle.start.assert_not_called()


def test_loopback_model_list_without_configured_file_never_proves_locality(tmp_path):
    svc = service(tmp_path)
    config = svc.configure_runtime(LocalRuntimeInput(name="List only", type="LLAMA_CPP",
        endpoint="http://localhost:19991", model_id="qwen.gguf"))
    assert config["endpoint"] == "http://127.0.0.1:19991"
    svc.client.payloads[(config["endpoint"], "/v1/models")] = {"data": [{"id": "qwen.gguf"}]}
    candidate = next(row for row in scan(svc)["candidates"] if row["runtime_id"] == config["id"])
    validated = svc.validate(candidate["id"])
    assert validated["source_locality"] == "NOT_VERIFIED" and not validated["local"]
    assert not validated["verified_capabilities"]
    assert "RUNTIME_MODEL_FILE_UNVERIFIED" in validated["enable_blockers"]


@pytest.mark.parametrize("endpoint", ["http://remote.invalid:19991", "http://192.168.1.2:19991", "http://127.0.0.1:19991?proxy=remote"])
def test_non_loopback_or_ambiguous_runtime_is_rejected(endpoint):
    with pytest.raises(ValueError, match="LOCAL_AI_LOOPBACK_ENDPOINT_REQUIRED"):
        LocalRuntimeInput(name="Invalid runtime", type="LLAMA_CPP", endpoint=endpoint)


def test_managed_gguf_does_not_acquire_external_locality_authority(tmp_path):
    svc, host, candidate, _, _ = llama_fixture(tmp_path, management="MANAGED")
    enabled = enable(svc, candidate)
    # The existing managed workflow can still be enabled, but cannot enter the
    # Studio external-only invocation or gain authority to start a process here.
    assert enabled["enabled"] and enabled["verified_capabilities"] == ["TEXT"]
    assert "source_locality" not in enabled
    with pytest.raises(ValueError, match="GRAPH_VERIFIED_LOCAL_MODEL_REQUIRED"):
        LocalModelInvocation(host, candidate["provider_id"], candidate["id"])
    svc.center.lifecycle.start.assert_not_called()


def test_external_locality_does_not_survive_switch_to_managed(tmp_path):
    svc, host, candidate, config, _ = llama_fixture(tmp_path)
    enable(svc, candidate)
    executable = tmp_path / "llama-server"
    executable.write_bytes(b"SYNTHETIC_NOT_EXECUTABLE")
    svc.configure_runtime(LocalRuntimeInput.model_validate({
        **{k: v for k, v in config.items() if k != "id"},
        "management": "MANAGED", "executable": str(executable)}), config["id"])
    checked = svc.validate(candidate["id"])
    assert "source_locality" not in checked and not checked["enabled"]
    assert svc.enable(candidate["id"])["enabled"]
    with pytest.raises(ValueError, match="GRAPH_VERIFIED_LOCAL_MODEL_REQUIRED"):
        LocalModelInvocation(host, candidate["provider_id"], candidate["id"])
    svc.center.lifecycle.start.assert_not_called()


def test_failed_revalidation_clears_previously_verified_locality(tmp_path):
    svc, host, candidate, config, _ = llama_fixture(tmp_path)
    enable(svc, candidate)
    invocation = LocalModelInvocation(host, candidate["provider_id"], candidate["id"])
    svc.client.payloads[(config["endpoint"], "/v1/models")] = {"data": []}
    validated = svc.validate(candidate["id"])
    assert validated["source_locality"] == "NOT_VERIFIED" and not validated["local"]
    assert not validated["enabled"]
    with pytest.raises((ValueError, ModelRuntimeError)):
        invocation.validate()
    svc.client.payloads[(config["endpoint"], "/v1/models")] = {"data": [{"id": config["model_id"]}]}
    restored = svc.validate(candidate["id"])
    assert restored["source_locality"] == "LOCAL_VERIFIED" and not restored["enabled"]
    with pytest.raises((ValueError, ModelRuntimeError)):
        LocalModelInvocation(host, candidate["provider_id"], candidate["id"])


@pytest.mark.parametrize("change", ["metadata", "alias", "not_running"])
def test_dispatch_rechecks_locality_evidence_without_sending_prompt(tmp_path, change):
    svc, host, candidate, config, path = llama_fixture(tmp_path)
    enable(svc, candidate)
    adapter = host.provider_registry.resolve(candidate["provider_id"])
    adapter.client = FixtureClient()
    if change == "metadata": gguf(path, arch="llama")
    elif change == "alias": svc.client.payloads[(config["endpoint"], "/v1/models")] = {"data": [{"id": "replacement-alias"}]}
    else: svc.client.payloads[(config["endpoint"], "/v1/models")] = ProbeFailure("LOCAL_AI_PROBE_UNAVAILABLE")
    with pytest.raises(ModelRuntimeError):
        adapter.generate_text(TextGenerationRequest(candidate["provider_id"], candidate["id"], "SYNTHETIC_PRIVATE_TEXT"))
    record = svc.registrations[candidate["id"]]
    assert not record["enabled"] and not record["license_confirmed"]
    assert record["source_locality"] == "NOT_VERIFIED" and not record["local"]
    assert adapter.client.calls == []
    svc.center.lifecycle.start.assert_not_called()


def test_changed_valid_gguf_requires_license_review_again(tmp_path):
    svc, _, candidate, _, path = llama_fixture(tmp_path)
    previous = enable(svc, candidate)
    gguf(path, arch="llama")
    changed = svc.validate(candidate["id"])
    assert changed["source_locality"] == "LOCAL_VERIFIED"
    assert changed["model_evidence_fingerprint"] != previous["model_evidence_fingerprint"]
    assert not changed["license_confirmed"] and not changed["enabled"]
    assert "MODEL_CHANGED_REVIEW_REQUIRED" in changed["validation_notes"]
    with pytest.raises(ValueError, match="LICENSE_VALIDATION_REQUIRED"):
        svc.enable(candidate["id"])


@pytest.mark.parametrize("control", ["disable", "reconfigure", "reload"])
def test_prior_locality_never_resurrects_revoked_or_reloaded_authority(tmp_path, control):
    svc, host, candidate, config, _ = llama_fixture(tmp_path)
    enable(svc, candidate)
    invocation = LocalModelInvocation(host, candidate["provider_id"], candidate["id"])
    if control == "disable": svc.disable(candidate["id"])
    elif control == "reconfigure":
        svc.configure_runtime(LocalRuntimeInput.model_validate({
            **{k: v for k, v in config.items() if k != "id"}, "model_id": "new-alias"}), config["id"])
    else:
        restored = LocalDiscoveryService(svc.center, svc.path, client=svc.client)
        svc.route_bridge.service = restored
        svc = restored
    record = svc.registrations[candidate["id"]]
    assert not record["enabled"]
    if control != "disable": assert "REVALIDATION_REQUIRED" in record["enable_blockers"]
    with pytest.raises((ValueError, ModelRuntimeError)):
        invocation.validate()
    svc.center.lifecycle.start.assert_not_called()
