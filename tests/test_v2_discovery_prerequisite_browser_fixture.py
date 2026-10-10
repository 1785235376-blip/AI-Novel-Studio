"""Closed prerequisite fixture contracts. No Chromium, TCP or inference is run."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest

from scripts.run_v2_checks import isolated_environment
from test_local_ai_discovery import service
from v2_discovery_browser_server import SyntheticDiscoveryFixture


MODEL_ID = "synthetic-prerequisite-catalogue-only"
COMPONENT_ID = "synthetic-prerequisite-text-encoder"
OBJECT_INFO = ("http://127.0.0.1:8188", "/object_info")


def test_default_fixture_payload_and_receipt_remain_unchanged_without_opt_in(tmp_path):
    fixture = SyntheticDiscoveryFixture(tmp_path / "adapter", delay_seconds=0)
    discovery = service(tmp_path)
    fixture.install(discovery)
    assert fixture.json(*OBJECT_INFO) == {}
    assert "synthetic_prerequisite_fixture" not in fixture.receipt(discovery)
    assert MODEL_ID not in discovery.center.models
    assert COMPONENT_ID not in discovery.center.components
    assert SyntheticDiscoveryFixture.payloads[OBJECT_INFO] == {}


def test_explicit_seed_only_adds_tiny_metadata_to_existing_owners_without_scanning(tmp_path, monkeypatch):
    fixture = SyntheticDiscoveryFixture(tmp_path / "adapter", delay_seconds=0)
    discovery = service(tmp_path)
    fixture.install(discovery)
    discovery.scan = {"id": "prior-scan", "status": "COMPLETED", "candidates": []}
    original_scan = copy.deepcopy(discovery.scan)
    original_runtimes = copy.deepcopy(discovery.center.runtimes)
    original_policy = copy.deepcopy(discovery.center.routing_policy)
    original_payloads = copy.deepcopy(SyntheticDiscoveryFixture.payloads)
    def network_forbidden(*_args, **_kwargs):
        raise AssertionError("Synthetic prerequisite fixture has no network transport")
    monkeypatch.setattr("urllib.request.urlopen", network_forbidden)
    monkeypatch.setattr("socket.create_connection", network_forbidden)
    guard = Mock()
    seeded = fixture.seed_workflow_prerequisites(discovery, guard)
    assert guard.call_count == 2
    assert seeded["fixture"] == "workflow-prerequisites-only-v1"
    assert seeded["catalogue_model_id"] == MODEL_ID
    assert seeded["catalogue_component_id"] == COMPONENT_ID
    assert seeded["object_info_bytes"] < 512
    assert len(seeded["object_info_sha256"]) == 64
    assert discovery.scan == original_scan
    assert discovery.center.runtimes == original_runtimes
    assert discovery.center.routing_policy == original_policy
    assert SyntheticDiscoveryFixture.payloads == original_payloads
    model = discovery.center.models[MODEL_ID]
    assert model.status == "NOT_INSTALLED" and model.local_paths == ()
    assert model.components == (COMPONENT_ID,)
    assert discovery.center.components[COMPONENT_ID].component_type == "TEXT_ENCODER"
    assert not list(fixture.common.iterdir())
    result = fixture.receipt(discovery)
    assert result["synthetic_prerequisite_fixture"] == seeded
    assert result["probe_calls"] == [] and result["hardware_calls"] == 0
    assert result["registrations"] == result["enabled_registrations"] == result["launch_attempts"] == 0
    assert result["inference_status"] == result["windows_acceptance"] == "NOT_RUN"
    assert result["model_weights_loaded"] is False


def test_seeded_object_info_is_closed_copied_and_other_probes_are_unchanged(tmp_path):
    fixture = SyntheticDiscoveryFixture(tmp_path / "adapter", delay_seconds=0)
    discovery = service(tmp_path)
    fixture.install(discovery)
    seeded = fixture.seed_workflow_prerequisites(discovery, lambda: None)
    info = fixture.json(*OBJECT_INFO)
    assert set(info) == {"CheckpointLoaderSimple", "KSampler", "EmptyLatentImage", "CLIPTextEncode", "VAEDecode"}
    assert info["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"] == [["synthetic-prerequisite-sdxl.safetensors"]]
    info.clear()
    seeded.clear()
    assert len(fixture.json(*OBJECT_INFO)) == 5
    assert fixture.receipt(discovery)["synthetic_prerequisite_fixture"]["catalogue_model_id"] == MODEL_ID
    for key, expected in SyntheticDiscoveryFixture.payloads.items():
        if key != OBJECT_INFO:
            assert fixture.json(*key) == expected
    for endpoint, path, body in [("http://127.0.0.1:1", "/object_info", None), (*OBJECT_INFO, {})]:
        with pytest.raises(AssertionError, match="UNAPPROVED_PROBE"):
            fixture.json(endpoint, path, body=body)


@pytest.mark.parametrize("blocked", ["active", "revoked", "existing_model", "existing_component", "repeat"])
def test_prerequisite_seed_never_replaces_existing_state(tmp_path, blocked):
    fixture = SyntheticDiscoveryFixture(tmp_path / "adapter", delay_seconds=0)
    discovery = service(tmp_path)
    fixture.install(discovery)
    guard = lambda: None
    expected = "PREREQUISITES_ALREADY_EXISTS"
    if blocked == "active":
        discovery.scan = {"id": "prior-scan", "status": "RUNNING"}
        expected = "SCAN_ACTIVE"
    elif blocked == "revoked":
        guard = Mock(side_effect=ValueError("SYNTHETIC_REVOKED"))
        expected = "SYNTHETIC_REVOKED"
    elif blocked == "existing_model":
        discovery.center.models[MODEL_ID] = object()
    elif blocked == "existing_component":
        discovery.center.components[COMPONENT_ID] = object()
    else:
        fixture.seed_workflow_prerequisites(discovery, lambda: None)
    scan_before = copy.deepcopy(discovery.scan)
    models_before = dict(discovery.center.models)
    components_before = dict(discovery.center.components)
    info_before = fixture.json(*OBJECT_INFO)
    with pytest.raises(ValueError, match=expected):
        fixture.seed_workflow_prerequisites(discovery, guard)
    assert discovery.scan == scan_before
    assert discovery.center.models == models_before
    assert discovery.center.components == components_before
    assert fixture.json(*OBJECT_INFO) == info_before
    assert not list(fixture.common.iterdir())


@pytest.mark.parametrize("mode", ["enabled", "default-off", "acceptance"])
def test_mounted_seed_preserves_authority_scan_and_readonly_evidence(tmp_path, mode):
    root = Path(__file__).resolve().parents[1]
    owned = tmp_path / "prerequisite-process"
    env = {**os.environ, **isolated_environment(root, owned),
        "V2_DISCOVERY_FIXTURE_ROOT": str(owned), "NOVEL_DATA_PATH": str(owned / "novel-data"),
        "EXPERIMENTAL_FEATURES": "" if mode == "default-off" else "narrative_production_v2",
        "V1_ACCEPTANCE_MODE": str(mode == "acceptance").lower(),
        "COLLABORATION_DEV_SESSIONS_JSON": "", "FRONTEND_ORIGIN": "http://127.0.0.1:5187",
        "ENABLE_PROVIDER_FALLBACK": "false", "CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK": "true"}
    result = subprocess.run([sys.executable, str(root / "tests/v2_discovery_browser_server.py"), "--self-check-prerequisites"],
        env=env, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    receipt = json.loads(result.stdout.strip().splitlines()[-1])
    enabled = mode == "enabled"
    assert ("synthetic_prerequisite_fixture" in receipt) is enabled
    assert receipt["hardware_calls"] == (2 if enabled else 0)
    assert len(receipt["probe_calls"]) == (14 if enabled else 0)
    assert receipt["scan_status"] == ("COMPLETED" if enabled else None)
    assert receipt["inference_status"] == receipt["windows_acceptance"] == "NOT_RUN"
    assert receipt["registrations"] == receipt["enabled_registrations"] == receipt["launch_attempts"] == 0
    assert receipt["model_weights_loaded"] is False and receipt["blocked_attempts"] == []
