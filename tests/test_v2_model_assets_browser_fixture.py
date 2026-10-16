"""Additive M4-B fixture checks, real File/HTTP worker and no browser launch."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from test_v2_ai_execution_browser_fixture import environment as original_environment
from v2_ai_execution_browser_server import LABEL as ORIGINAL_LABEL, SyntheticExecutionFixture
from v2_model_assets_browser_server import FAULT_BODY, LABEL, ModelAssetsFixture, validate_environment


def environment(root):
    return {**original_environment(root), "V2_MODEL_ASSETS_FIXTURE_ROOT": str(root),
        "TEMP": str(root / "tmp"), "TMP": str(root / "tmp"),
        "FRONTEND_ORIGIN": "http://127.0.0.1:5191", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}


def test_m4b_original_http_archival_and_recovery_without_browser(tmp_path):
    env = environment(tmp_path / "m4b-owned-process")
    wire = tmp_path / "actual-http-wire.json"
    result = subprocess.run([sys.executable, str(Path(__file__).with_name("v2_model_assets_browser_server.py")),
        "--self-check", "--wire-receipt", str(wire)], env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    receipt = json.loads(result.stdout.strip().splitlines()[-1])
    assert receipt["fixture"] == LABEL and receipt["original_fixture"] == ORIGINAL_LABEL
    assert receipt["synthetic"] and receipt["mounted_lifecycle"] == "PASS"
    assert receipt["mock_calls"] == receipt["create_calls"] == receipt["review_metadata_faults"] == 1
    assert len(receipt["created_asset_ids"]) == 1 and not receipt["fault_armed"]
    assert receipt["advisory_no_model_call"] and receipt["identical_read_no_duplicate"]
    assert receipt["draft_asset_version"] == 1 and receipt["approved_asset_version"] == 2
    assert receipt["same_asset_recovered"] and receipt["review_metadata_recovery"] == "ORIGINAL_GET"
    assert receipt["fault_observed_asset_version"] == 1 and receipt["fault_observed_asset_state"] == "DRAFT"
    assert receipt["host_revoke"] == "PASS"
    assert receipt["blocked_attempts"] == [] and receipt["cloud_calls"] == 0
    assert receipt["quality_verification"] == receipt["real_inference"] == receipt["browser"] == "NOT_RUN"
    assert receipt["no_chapters"] and receipt["model_weights_loaded"] is False
    evidence = json.loads(wire.read_text())
    assert evidence["dispatch_input"]["archive_result"] is True
    assert evidence["fault_http_status"] == 500
    assert evidence["draft"]["asset_output"]["asset_id"] == evidence["recovered"]["asset_output"]["asset_id"]


@pytest.mark.parametrize("key,value", [("ENABLE_CLOUD", "true"), ("ENABLE_PROVIDER_FALLBACK", "true"),
    ("STORAGE_BACKEND", "postgres"), ("ENABLE_PACKAGED_RUNTIME", "true"), ("V1_ACCEPTANCE_MODE", "true"),
    ("NOVEL_DATA_PATH", "/tmp/unowned"), ("V2_AI_EXECUTION_FIXTURE_ROOT", "/tmp/unowned"),
    ("V2_MODEL_ASSETS_FIXTURE_ROOT", "/tmp/unowned"), ("USERPROFILE", "/tmp/unowned"),
    ("APPDATA", "/tmp/unowned"), ("TEMP", "/tmp/unowned"), ("TMP", "/tmp/unowned"),
    ("FRONTEND_ORIGIN", "http://127.0.0.1:5190"), ("HF_HUB_OFFLINE", "0"), ("TRANSFORMERS_OFFLINE", "0")])
def test_m4b_rejects_shared_or_network_enabled_environment(tmp_path, monkeypatch, key, value):
    root = tmp_path / "m4b-owned-process"
    for name, content in environment(root).items():
        monkeypatch.setenv(name, content)
    monkeypatch.setenv(key, value)
    with pytest.raises(AssertionError, match="M4B?_FIXTURE_"):
        validate_environment(root)


def test_m4b_keeps_original_non_mock_execution_traps():
    original = SyntheticExecutionFixture()
    fixture = ModelAssetsFixture(original)
    for category in ("REAL_PROVIDER", "DISCOVERY_PROBE", "HARDWARE_PROBE", "RUNTIME_LAUNCH"):
        with pytest.raises(AssertionError, match="M4_FIXTURE_FORBIDDEN_" + category):
            original.forbid(category)()
    assert fixture.receipt()["blocked_attempts"] == ["REAL_PROVIDER", "DISCOVERY_PROBE", "HARDWARE_PROBE", "RUNTIME_LAUNCH"]
    assert fixture.receipt()["mock_calls"] == fixture.receipt()["create_calls"] == 0


def test_m4b_fault_requires_one_existing_owned_result():
    from fastapi import HTTPException
    fixture = ModelAssetsFixture(SyntheticExecutionFixture())
    with pytest.raises(HTTPException) as result:
        fixture.arm(FAULT_BODY)
    assert result.value.status_code == 409 and not fixture.fault_armed
