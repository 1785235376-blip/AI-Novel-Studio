"""Original File/API execution with the repository's adapter and memory transport.

The adapter is real Automatic1111ImageProvider; its transport returns a known
synthetic fixture without network, inference, GPU, acceptance or media decoding.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
import json
import os
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app import api as api_module
from app import dependencies
from app.asset_providers import AssetProviderRegistry, Automatic1111ImageProvider
from app.config import settings
from app.main import app
from app.repositories.factory import create_repository_bundle
from app.services import image_job_service as image_job_module
from app.services.image_job_service import ImageJobService
from test_asset_provider_contract import _Response
from test_cloud_canvas_candidate_protocol import SYNTHETIC_PNG_B64
from test_cloud_canvas_image_queue import queue_command


pytestmark = pytest.mark.file_backend_only


class SyntheticLocalTransport:
    """The same injection seam used by test_asset_provider_contract, never HTTP."""

    def __init__(self):
        self.calls = []
        self.entered = Event()
        self.release = Event()
        self.hold = False
        self.failure = None

    def post(self, url, **kwargs):
        assert url == "http://127.0.0.1:7860/sdapi/v1/txt2img"
        self.calls.append(deepcopy(kwargs["json"]))
        self.entered.set()
        if self.hold and not self.release.wait(5):
            raise AssertionError("Synthetic test response was not released")
        if self.failure is not None:
            raise self.failure
        return _Response({"images": [SYNTHETIC_PNG_B64]})


@pytest.fixture
def explicit_execution(tmp_path, monkeypatch):
    config = replace(settings, root=tmp_path, novel_data=tmp_path / "repository",
        storage_backend="file", database_url="", enable_cloud=False,
        enable_collaboration_runtime=False, enable_packaged_runtime=False, mock_provider=True)
    repositories = create_repository_bundle(config, data_root=config.data_path())
    project = repositories.novels.create({"title": "Owned synthetic explicit execution"})
    owner_root = tmp_path / "production"
    owner = ImageJobService(owner_root)
    transport = SyntheticLocalTransport()
    adapter = Automatic1111ImageProvider(transport, "http://127.0.0.1:7860")
    # Explicit fixture classification for the original manual egress guard.
    # No provider discovery, endpoint probe or real transport is performed.
    adapter.local = True
    registry = AssetProviderRegistry()
    registry.register("synthetic-local-automatic1111", adapter)
    forbidden = {}
    for name in ("accept", "inspect_image", "fetch_media_bytes"):
        sentinel = Mock(side_effect=AssertionError("Explicit execution must not call " + name))
        monkeypatch.setattr(ImageJobService if name == "accept" else image_job_module, name, sentinel)
        forbidden[name] = sentinel
    monkeypatch.setattr(api_module, "settings", config)
    monkeypatch.setattr(api_module, "image_job_service", owner)
    monkeypatch.setattr(dependencies, "repositories", repositories)
    monkeypatch.setattr(dependencies, "asset_provider_registry", registry)
    e = SimpleNamespace(client=TestClient(app), project_id=project["id"], owner_root=owner_root,
        owner=owner, transport=transport, forbidden=forbidden)
    yield e
    transport.release.set()
    for sentinel in forbidden.values():
        sentinel.assert_not_called()
    e.client.close()


def queue(e, request_id="synthetic-explicit-execute"):
    body = queue_command(e.project_id)
    body["provider_id"] = "synthetic-local-automatic1111"
    body["model_id"] = "synthetic-no-weights.safetensors"
    route = f"/api/novels/{e.project_id}/image-jobs"
    response = e.client.post(route, json=body, headers={"Idempotency-Key": request_id})
    assert response.status_code == 202
    return route, response.json()


def read(e, route):
    response = e.client.get(route)
    assert response.status_code == 200
    rows = response.json()["items"]
    assert len(rows) == 1
    return rows[0]


def test_original_explicit_execute_persists_candidate_and_rejects_duplicate(explicit_execution, monkeypatch):
    e = explicit_execution
    route, queued = queue(e)
    before = read(e, route)
    assert before["status"] == "QUEUED" and before["attempt"] == 0
    assert e.transport.calls == []

    executed = e.client.post(f"{route}/{queued['id']}/execute")

    assert executed.status_code == 200
    candidate = executed.json()
    assert candidate["id"] == queued["id"]
    assert candidate["status"] == "SUCCEEDED" and candidate["attempt"] == 1
    assert candidate["approval_status"] == "PENDING" and "asset_id" not in candidate
    assert candidate["asset_uri"] == "data:image/png;base64," + SYNTHETIC_PNG_B64
    assert candidate["request_sha256"] == queued["request_sha256"]
    assert len(e.transport.calls) == 1
    assert e.transport.calls[0] == {"prompt": queued["prompt"], **queued["parameters"],
        "override_settings": {"sd_model_checkpoint": queued["model_id"]}}
    monkeypatch.setattr(api_module, "image_job_service", ImageJobService(e.owner_root))
    reopened = read(e, route)
    assert {key: reopened[key] for key in candidate} == candidate
    duplicate = e.client.post(f"{route}/{queued['id']}/execute")
    assert duplicate.status_code == 400
    assert duplicate.json()["detail"] == "IMAGE_JOB_NOT_QUEUED"
    assert read(e, route) == reopened and len(e.transport.calls) == 1

def test_late_original_response_is_read_without_redispatch(explicit_execution):
    e = explicit_execution
    route, queued = queue(e)
    e.transport.hold = True
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(e.client.post, f"{route}/{queued['id']}/execute")
        try:
            assert e.transport.entered.wait(5)
            running = read(e, route)
            assert running["status"] == "RUNNING" and running["attempt"] == 1
            assert running["recoverable"] is False and len(e.transport.calls) == 1
            duplicate = e.client.post(f"{route}/{queued['id']}/execute")
            assert duplicate.status_code == 400 and len(e.transport.calls) == 1
        finally:
            e.transport.release.set()
        # Completion is waited for only to close the test. The next observation
        # is recovered using GET of the original ID, without another dispatch.
        assert future.result(timeout=5).status_code == 200
    completed = read(e, route)
    assert completed["id"] == queued["id"] and completed["status"] == "SUCCEEDED"
    assert completed["attempt"] == 1 and len(e.transport.calls) == 1


def test_transport_timeout_is_read_as_failed_without_automatic_retry(explicit_execution):
    e = explicit_execution
    route, queued = queue(e)
    e.transport.failure = TimeoutError("Synthetic timeout; no network request")

    response = e.client.post(f"{route}/{queued['id']}/execute")

    assert response.status_code == 200
    failed = response.json()
    assert failed["status"] == "FAILED" and failed["attempt"] == 1
    assert failed["error_code"] == "IMAGE_PROVIDER_REQUEST_FAILED"
    assert "asset_uri" not in failed and failed["approval_status"] == "PENDING"
    assert read(e, route)["status"] == "FAILED"
    assert e.client.post(f"{route}/{queued['id']}/execute").status_code == 400
    assert len(e.transport.calls) == 1


def confirmation(row):
    return {"confirmed": True, "expected_request_sha256": row["request_sha256"],
        "expected_attempt": row["attempt"], "expected_updated_at": row["updated_at"]}


def test_confirmation_capability_is_opt_in_without_changing_legacy_list_shape(explicit_execution):
    e = explicit_execution
    route, queued = queue(e)
    legacy = e.client.get(route)
    assert legacy.status_code == 200 and set(legacy.json()) == {"items"}

    capability = e.client.get(route, params={"execution_confirmation": "1"})

    assert capability.status_code == 200
    assert set(capability.json()) == {"items", "execution_confirmation"}
    assert capability.json()["execution_confirmation"] == "legacy-image-confirmation/1"
    assert capability.json()["items"] == legacy.json()["items"]
    assert capability.json()["items"][0]["id"] == queued["id"]
    assert e.client.get(route).json() == legacy.json()
    assert e.transport.calls == []


@pytest.mark.parametrize("field,replacement", [
    ("expected_request_sha256", "f" * 64),
    ("expected_attempt", 1),
    ("expected_updated_at", "2000-01-01T00:00:00+00:00"),
])
def test_stale_execute_confirmation_leaves_queue_and_provider_untouched(explicit_execution, field, replacement):
    e = explicit_execution
    route, queued = queue(e)
    original = read(e, route)
    body = confirmation(original)
    assert body[field] != replacement
    body[field] = replacement

    response = e.client.post(f"{route}/{queued['id']}/execute", json=body)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "IMAGE_JOB_CONFIRMATION_STALE"
    assert read(e, route) == original
    assert e.transport.calls == []


def test_execute_rehashes_changed_payload_even_when_stored_digest_is_unchanged(explicit_execution):
    e = explicit_execution
    route, queued = queue(e)
    reviewed = read(e, route)

    def change_parameters(rows):
        row = e.owner._find(rows, queued["id"])
        row["parameters"] = {**row["parameters"], "seed": row["parameters"]["seed"] + 1}
        return row

    e.owner._mutate(e.project_id, None, change_parameters)
    changed = read(e, route)
    assert changed["request_sha256"] == reviewed["request_sha256"]
    assert changed["updated_at"] == reviewed["updated_at"]

    response = e.client.post(f"{route}/{queued['id']}/execute", json=confirmation(reviewed))

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "IMAGE_JOB_CONFIRMATION_STALE"
    assert read(e, route) == changed
    assert changed["status"] == "QUEUED" and changed["attempt"] == 0
    assert "execution_token" not in changed and e.transport.calls == []


def test_matching_execute_confirmation_runs_original_adapter_once_and_reopens_file(explicit_execution, monkeypatch):
    e = explicit_execution
    route, queued = queue(e)
    before = read(e, route)
    capability = e.client.get(route, params={"execution_confirmation": "1"})
    assert capability.status_code == 200
    assert capability.json()["execution_confirmation"] == "legacy-image-confirmation/1"
    assert capability.json()["items"] == [before]
    body = confirmation(before)
    assert e.transport.calls == []

    executed = e.client.post(f"{route}/{queued['id']}/execute", json=body)

    assert executed.status_code == 200
    candidate = executed.json()
    assert candidate["status"] == "SUCCEEDED" and candidate["attempt"] == 1
    assert candidate["id"] == queued["id"] and candidate["approval_status"] == "PENDING"
    assert candidate["asset_uri"] == "data:image/png;base64," + SYNTHETIC_PNG_B64
    monkeypatch.setattr(api_module, "image_job_service", ImageJobService(e.owner_root))
    reopened = read(e, route)
    assert {key: reopened[key] for key in candidate} == candidate
    assert len(e.transport.calls) == 1
    duplicate = e.client.post(f"{route}/{queued['id']}/execute")
    assert duplicate.status_code == 400 and len(e.transport.calls) == 1

    capture = os.getenv("CLOUD_CANVAS_EXECUTE_CAPTURE_FILE")
    if capture:
        fixture = {"fixture_kind": "ORIGINAL_FILE_EXECUTE_WITH_SYNTHETIC_MEMORY_TRANSPORT",
            "base_commit": "8738ecb2ecd667dd9d401c4c16c2136f812e2a17",
            "limitations": "Original owner/API and repository adapter executed with a matching confirmation; memory transport only, no real inference, acceptance, media inspection or network.",
            "project_id": e.project_id, "task_id": queued["id"], "queued": {"items": [before]},
            "execution_capability": capability.json(), "confirmation": body,
            "execute_response": candidate, "completed": {"items": [reopened]},
            "duplicate_execute": {"status": duplicate.status_code, "body": duplicate.json()},
            "transport_calls": len(e.transport.calls)}
        Path(capture).write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
