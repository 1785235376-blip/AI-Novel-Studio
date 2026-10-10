"""Separate fixture/self-check evidence; these tests do not launch Chromium."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from v2_ai_execution_browser_server import FLAGS, LABEL, SyntheticExecutionFixture, validate_environment


def environment(root):
    for folder in ("home", "data", "cache", "config", "local", "tmp"):
        (root / folder).mkdir(parents=True)
    return {**os.environ, "V2_AI_EXECUTION_FIXTURE_ROOT": str(root), "NOVEL_DATA_PATH": str(root / "novel-data"),
        "HOME": str(root / "home"), "USERPROFILE": str(root / "home"), "XDG_DATA_HOME": str(root / "data"),
        "XDG_CACHE_HOME": str(root / "cache"), "XDG_CONFIG_HOME": str(root / "config"), "LOCALAPPDATA": str(root / "local"),
        "APPDATA": str(root / "local"), "TMPDIR": str(root / "tmp"), "STORAGE_BACKEND": "file",
        "ENABLE_COLLABORATION_RUNTIME": "false", "ENABLE_PACKAGED_RUNTIME": "false", "MOCK_PROVIDER": "true",
        "MOCK_STREAM_DELAY_MS": "0", "ENABLE_CLOUD": "false", "ENABLE_PROVIDER_FALLBACK": "false",
        "EXPERIMENTAL_FEATURES": FLAGS, "V1_ACCEPTANCE_MODE": "false", "COLLABORATION_DEV_SESSIONS_JSON": "",
        "FRONTEND_ORIGIN": "http://127.0.0.1:5190", "CREDENTIAL_VAULT_BACKEND": "memory", "CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK": "true"}


def test_m4_original_mounted_worker_fixture_without_browser(tmp_path):
    env = environment(tmp_path / "owned-process")
    result = subprocess.run([sys.executable, str(Path(__file__).with_name("v2_ai_execution_browser_server.py")), "--self-check"],
                            env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    receipt = json.loads(result.stdout.strip().splitlines()[-1])
    assert receipt["fixture"] == LABEL and receipt["synthetic"] and receipt["mock_calls"] == 1
    assert receipt["blocked_attempts"] == [] and receipt["cloud_calls"] == 0
    assert receipt["metadata_probe_attempts"] == 1
    assert receipt["quality_verification"] == receipt["real_inference"] == receipt["browser"] == "NOT_RUN"
    assert receipt["mounted_lifecycle"] == receipt["host_revoke"] == "PASS"
    assert receipt["duplicate_dispatch"] == "SAME_ORIGINAL_JOB" and receipt["read_replay"] is False
    assert receipt["cancelled_without_call"] and receipt["model_weights_loaded"] is False


@pytest.mark.parametrize("key,value", [("ENABLE_CLOUD", "true"), ("ENABLE_PROVIDER_FALLBACK", "true"), ("STORAGE_BACKEND", "postgres"),
    ("ENABLE_PACKAGED_RUNTIME", "true"), ("EXPERIMENTAL_FEATURES", "narrative_production_v2"), ("V1_ACCEPTANCE_MODE", "true"),
    ("NOVEL_DATA_PATH", "/tmp/unowned"), ("HOME", "/tmp/unowned"), ("V2_AI_EXECUTION_FIXTURE_ROOT", "/tmp/unowned")])
def test_fixture_refuses_unisolated_or_real_execution_environment(tmp_path, monkeypatch, key, value):
    root = tmp_path / "owned-process"
    for name, content in environment(root).items():
        monkeypatch.setenv(name, content)
    monkeypatch.setenv(key, value)
    with pytest.raises(AssertionError, match="M4_FIXTURE_"):
        validate_environment(root)


def test_fixture_traps_are_counted_and_never_fall_back():
    fixture = SyntheticExecutionFixture()
    for category in ("REAL_PROVIDER", "DISCOVERY_PROBE", "HARDWARE_PROBE", "RUNTIME_LAUNCH"):
        with pytest.raises(AssertionError, match="M4_FIXTURE_FORBIDDEN_" + category):
            fixture.forbid(category)("untrusted-input")
    assert fixture.receipt()["blocked_attempts"] == ["REAL_PROVIDER", "DISCOVERY_PROBE", "HARDWARE_PROBE", "RUNTIME_LAUNCH"]
    assert fixture.receipt()["mock_calls"] == 0
