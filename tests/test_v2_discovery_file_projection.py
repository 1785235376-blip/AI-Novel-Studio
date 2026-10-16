"""Original mounted discovery projections; tiny synthetic metadata, no inference."""
from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import Mock

import pytest

from test_local_ai_discovery import gguf
from test_local_ai_environment_v2 import safetensors
from test_v2_discovery_onboarding_api import HEADERS, onboard  # noqa: F401


def populate(root: Path):
    root.mkdir()
    gguf(root / "same.gguf")
    safetensors(root / "sdxl.safetensors")
    bundle = root / "flux"
    bundle.mkdir()
    index = bundle / "model_index.json"
    index.write_text(json.dumps({"_class_name": "FluxPipeline"}))
    return index


def confirmed_scan(client, base: str):
    preview = client.get(base + "/onboarding/scan-scope", headers=HEADERS)
    assert preview.status_code == 200, preview.text
    response = client.post(base + "/onboarding/scan", headers=HEADERS,
        json={"scope_digest": preview.json()["scope_digest"], "confirmed": True})
    assert response.status_code == 202, response.text
    job = response.json()
    deadline = time.monotonic() + 3
    while job["status"] == "RUNNING" and time.monotonic() < deadline:
        time.sleep(0.005)
        response = client.get(base + "/scan/" + job["id"], headers=HEADERS)
        assert response.status_code == 200, response.text
        job = response.json()
    assert job["status"] != "RUNNING"
    return job


def configure(client, base, root):
    response = client.put(base + "/settings", headers=HEADERS,
        json={"scan_roots": [str(root)], "include_common_model_dirs": False})
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_snapshot_status_and_environment_project_one_scan_without_new_reads(onboard, tmp_path, monkeypatch, prefix):
    client, svc, _ = onboard
    base = prefix + "/model-center/local-ai"
    root = tmp_path / "synthetic-models"
    index = populate(root)
    configure(client, base, root)
    job = confirmed_scan(client, base)
    assert job["environment_schema_version"] == 2
    assert {row["format"] for row in job["model_files"]} == {"GGUF", "SAFETENSORS", "DIFFUSERS"}
    indexed = next(row for row in job["model_files"] if row["format"] == "DIFFUSERS")
    assert indexed["path"] == str(index) and indexed["size_bytes"] == index.stat().st_size
    calls = list(svc.client.calls)
    guard = Mock(side_effect=AssertionError("GET must project the existing scan only"))
    monkeypatch.setattr(svc.client, "json", guard)
    monkeypatch.setattr(svc, "hardware_probe", guard)
    monkeypatch.setattr("app.model_center.discovery_environment._metadata_bytes", guard)
    monkeypatch.setattr("app.model_center.discovery_environment._scoped_scandir", guard)
    for _ in range(2):
        snapshot = client.get(base, headers=HEADERS)
        status = client.get(base + "/scan/" + job["id"], headers=HEADERS)
        environment = client.get(base + "/environment", headers=HEADERS)
        for response in (snapshot, status, environment):
            assert response.status_code == 200, response.text
            assert response.headers["Cache-Control"] == "no-store"
        assert snapshot.json()["scan"] == status.json() == job
        report = environment.json()
        assert report["scan_id"] == job["id"]
        assert report["model_files"] == job["model_files"]
        assert report["roots"] == job["roots"]
        assert report["started_at"] == job["started_at"]
        assert report["finished_at"] == job["finished_at"]
        assert report["inference_status"] == report["windows_acceptance"] == "NOT_RUN"
    guard.assert_not_called()
    assert svc.client.calls == calls and not svc.registrations
    svc.center.lifecycle.start.assert_not_called()


def test_projection_copies_cannot_mutate_original_file_or_binding_evidence(onboard, tmp_path):
    client, svc, _ = onboard
    base = "/api/model-center/local-ai"
    root = tmp_path / "synthetic-models"
    populate(root)
    configure(client, base, root)
    original = confirmed_scan(client, base)
    for projected in (svc.snapshot()["scan"], svc.get_scan(original["id"]), svc.environment_report()):
        projected["model_files"][0]["path"] = "synthetic-response-only-edit"
        projected["model_files"][0]["candidate_ids"].append("not-a-real-candidate")
        projected["roots"][0]["path"] = "synthetic-response-only-root"
    assert svc.get_scan(original["id"]) == original
    assert svc.environment_report()["model_files"] == original["model_files"]


def test_same_filename_paths_keep_distinct_observation_and_candidate_ids(onboard, tmp_path):
    client, svc, _ = onboard
    base = "/api/model-center/local-ai"
    root = tmp_path / "synthetic-models"
    root.mkdir()
    for name in ("first", "second"):
        folder = root / name
        folder.mkdir()
        gguf(folder / "same.gguf")
        safetensors(folder / "same.safetensors")
    configure(client, base, root)
    job = confirmed_scan(client, base)
    observations = job["model_files"]
    assert len(observations) == len({row["id"] for row in observations}) == 4
    by_id = {candidate["id"]: candidate for candidate in job["candidates"]}
    gguf_ids = []
    for row in observations:
        assert row["inference_verified"] is False
        if row["format"] == "GGUF":
            assert len(row["candidate_ids"]) == 1
            candidate = by_id[row["candidate_ids"][0]]
            assert candidate["local_path"] == row["path"]
            assert candidate["verified"] is False and candidate["enabled"] is False
            gguf_ids.extend(row["candidate_ids"])
        else:
            assert row["candidate_ids"] == []
    assert len(set(gguf_ids)) == 2
    assert not svc.registrations


def test_changed_file_is_not_reinspected_until_another_explicit_scan(onboard, tmp_path):
    client, svc, _ = onboard
    base = "/api/model-center/local-ai"
    root = tmp_path / "synthetic-models"
    root.mkdir()
    path = root / "fixture.safetensors"
    safetensors(path)
    configure(client, base, root)
    original = confirmed_scan(client, base)
    before = original["model_files"][0]
    assert before["header_valid"] is True
    path.write_bytes(b"invalid synthetic replacement")
    cached = client.get(base, headers=HEADERS)
    assert cached.status_code == 200 and cached.json()["scan"] == original
    assert svc.environment_report()["model_files"][0] == before
    updated = confirmed_scan(client, base)
    after = updated["model_files"][0]
    assert updated["id"] != original["id"]
    assert after["id"] == before["id"]  # Path identity, deliberately not content identity.
    assert after["size_bytes"] != before["size_bytes"]
    assert after["header_valid"] is False and after["inference_verified"] is False
    assert not svc.registrations


@pytest.mark.parametrize("enabled", [True, False])
@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_revoke_blocks_actual_cached_file_paths_even_after_flag_is_disabled(onboard, tmp_path, monkeypatch, enabled, prefix):
    client, svc, sessions = onboard
    base = prefix + "/model-center/local-ai"
    root = tmp_path / "synthetic-private-observations"
    populate(root)
    configure(client, base, root)
    job = confirmed_scan(client, base)
    assert job["model_files"]
    sessions.revoke(HEADERS["X-Session-Token"])
    if not enabled:
        monkeypatch.setenv("EXPERIMENTAL_FEATURES", "")
    for suffix in ("", "/scan/" + job["id"], "/environment"):
        response = client.get(base + suffix, headers=HEADERS)
        assert response.status_code == 401, response.text
        assert "synthetic-private-observations" not in response.text
        assert response.headers["Cache-Control"] == "no-store"
    assert svc.get_scan(job["id"])["model_files"] == job["model_files"]
