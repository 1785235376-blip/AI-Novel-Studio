"""Metadata-only hosted fixture safeguards. These tests do not launch Chromium."""
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest

from app.model_center.discovery_environment import diffusion_metadata, safetensors_metadata
from app.model_center.discovery_probes import gguf_metadata
from scripts.run_v2_checks import isolated_environment
from test_local_ai_discovery import service
from v2_discovery_browser_server import SyntheticDiscoveryFixture


def test_explicit_fixture_seed_contains_only_fixed_tiny_metadata_and_never_scans(tmp_path):
    fixture = SyntheticDiscoveryFixture(tmp_path / "adapter", delay_seconds=0)
    discovery = service(tmp_path)
    fixture.install(discovery)
    guard = Mock()
    rows = fixture.seed_model_metadata(discovery, guard)
    assert {row["name"] for row in rows} == {
        "synthetic-metadata.gguf", "synthetic-metadata.safetensors", "model_index.json"}
    assert sum(row["bytes"] for row in rows) < 512
    assert all(len(row["sha256"]) == 64 for row in rows)
    assert gguf_metadata(fixture.common / "synthetic-metadata.gguf")["header_valid"]
    assert safetensors_metadata(fixture.common / "synthetic-metadata.safetensors")["header_valid"]
    assert diffusion_metadata(fixture.common / "model_index.json")["header_valid"]
    receipt = fixture.receipt(discovery)
    assert receipt["synthetic_metadata_fixtures"] == rows
    assert receipt["probe_calls"] == [] and receipt["hardware_calls"] == 0 and receipt["scan_id"] is None
    assert receipt["model_weights_loaded"] is False and not receipt["registrations"]
    assert guard.call_count == 4


def test_seed_refuses_to_replace_preexisting_metadata(tmp_path):
    fixture = SyntheticDiscoveryFixture(tmp_path / "adapter", delay_seconds=0)
    discovery = service(tmp_path)
    path = fixture.common / "synthetic-metadata.gguf"
    path.write_bytes(b"existing synthetic evidence")
    with pytest.raises(ValueError, match="METADATA_ALREADY_EXISTS"):
        fixture.seed_model_metadata(discovery, lambda: None)
    assert path.read_bytes() == b"existing synthetic evidence"
    assert list(fixture.common.iterdir()) == [path]
    assert fixture.metadata_fixtures == []


def test_seed_refuses_active_scan_and_revoked_guard_without_writing(tmp_path):
    fixture = SyntheticDiscoveryFixture(tmp_path / "adapter", delay_seconds=0)
    discovery = service(tmp_path)
    discovery.scan = {"status": "RUNNING"}
    with pytest.raises(ValueError, match="SCAN_ACTIVE"):
        fixture.seed_model_metadata(discovery, lambda: None)
    discovery.scan = None
    with pytest.raises(ValueError, match="SYNTHETIC_REVOKED"):
        fixture.seed_model_metadata(discovery, Mock(side_effect=ValueError("SYNTHETIC_REVOKED")))
    assert not list(fixture.common.iterdir()) and fixture.metadata_fixtures == []


def test_repeated_seed_preserves_first_files_and_receipt(tmp_path):
    fixture = SyntheticDiscoveryFixture(tmp_path / "adapter", delay_seconds=0)
    discovery = service(tmp_path)
    first = fixture.seed_model_metadata(discovery, lambda: None)
    contents = {p.name: p.read_bytes() for p in fixture.common.iterdir()}
    with pytest.raises(ValueError, match="METADATA_ALREADY_EXISTS"):
        fixture.seed_model_metadata(discovery, lambda: None)
    assert fixture.metadata_fixtures == first
    assert {p.name: p.read_bytes() for p in fixture.common.iterdir()} == contents


@pytest.mark.parametrize("mode", ["enabled", "default-off", "acceptance"])
def test_real_mounted_fixture_seed_and_explicit_scan_keep_metadata_inference_separate(tmp_path, mode):
    root = Path(__file__).resolve().parents[1]
    owned = tmp_path / "file-observation-process"
    env = {**os.environ, **isolated_environment(root, owned),
        "V2_DISCOVERY_FIXTURE_ROOT": str(owned), "NOVEL_DATA_PATH": str(owned / "novel-data"),
        "EXPERIMENTAL_FEATURES": "" if mode == "default-off" else "narrative_production_v2",
        "V1_ACCEPTANCE_MODE": str(mode == "acceptance").lower(),
        "COLLABORATION_DEV_SESSIONS_JSON": "", "FRONTEND_ORIGIN": "http://127.0.0.1:5187",
        "ENABLE_PROVIDER_FALLBACK": "false", "CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK": "true"}
    result = subprocess.run([sys.executable, str(root / "tests/v2_discovery_browser_server.py"), "--self-check-files"],
        env=env, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    receipt = json.loads(result.stdout.strip().splitlines()[-1])
    enabled = mode == "enabled"
    assert len(receipt["synthetic_metadata_fixtures"]) == (3 if enabled else 0)
    assert receipt["hardware_calls"] == (1 if enabled else 0)
    assert len(receipt["probe_calls"]) == (7 if enabled else 0)
    assert receipt["scan_status"] == ("COMPLETED" if enabled else None)
    assert receipt["inference_status"] == receipt["windows_acceptance"] == "NOT_RUN"
    assert receipt["registrations"] == receipt["enabled_registrations"] == receipt["launch_attempts"] == 0
    assert receipt["model_weights_loaded"] is False and receipt["blocked_attempts"] == []
