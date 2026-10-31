"""Cloud canvas queue contract: real File persistence, with no media execution."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app import api as api_module
from app import dependencies
from app.asset_providers import AssetProviderRegistry
from app.config import settings
from app.main import app
from app.repositories.factory import create_repository_bundle
from app.services.image_job_service import ImageJobService


@pytest.fixture
def file_queue(tmp_path, monkeypatch):
    config = replace(
        settings,
        root=tmp_path,
        novel_data=tmp_path / "repository",
        storage_backend="file",
        database_url="",
        enable_cloud=False,
        enable_collaboration_runtime=False,
        enable_packaged_runtime=False,
        mock_provider=True,
    )
    repositories = create_repository_bundle(config, data_root=config.data_path())
    project = repositories.novels.create({"title": "Owned cloud canvas queue"})
    queue_root = tmp_path / "production"
    queue = ImageJobService(queue_root)
    registry = AssetProviderRegistry()
    resolve = Mock(side_effect=AssertionError("Queue operations must not resolve a provider"))
    execute = Mock(side_effect=AssertionError("Queue operations must not execute media"))
    monkeypatch.setattr(registry, "get", resolve)
    monkeypatch.setattr(ImageJobService, "execute", execute)
    monkeypatch.setattr(api_module, "settings", config)
    monkeypatch.setattr(api_module, "image_job_service", queue)
    monkeypatch.setattr(dependencies, "asset_provider_registry", registry)
    monkeypatch.setattr(dependencies, "repositories", repositories)
    return SimpleNamespace(
        client=TestClient(app), project_id=project["id"], queue_root=queue_root,
        repositories=repositories, resolve=resolve, execute=execute,
    )


def queue_command(project_id):
    return {
        "novel_id": project_id,
        "provider_id": "comfyui",
        "model_id": "explicit-author-selection.safetensors",
        "prompt": "Author-owned prompt from the selected image node",
        "parameters": {"width": 768, "height": 512, "steps": 24, "seed": 101},
        "allow_cloud_prompt": False,
    }


@pytest.mark.file_backend_only
def test_canvas_image_queue_retains_parameters_and_reopens_original_job(file_queue, monkeypatch):
    e = file_queue
    route = f"/api/novels/{e.project_id}/image-jobs"
    command = queue_command(e.project_id)
    headers = {"Idempotency-Key": "owned-canvas-node-queue-one"}

    response = e.client.post(route, json=command, headers=headers)

    assert response.status_code == 202
    queued = response.json()
    assert str(UUID(queued["id"])) == queued["id"]
    assert queued["novel_id"] == e.project_id
    assert queued["status"] == "QUEUED"
    assert queued["approval_status"] == "PENDING"
    assert queued["attempt"] == 0
    assert queued["allow_cloud_prompt"] is False
    assert len(queued["request_sha256"]) == 64
    for key in ("prompt", "provider_id", "model_id", "parameters"):
        assert queued[key] == command[key]

    # Rebuild the owner and HTTP client: the original task comes from File
    # storage, rather than the response object or a component's memory.
    monkeypatch.setattr(api_module, "image_job_service", ImageJobService(e.queue_root))
    reopened = TestClient(app)
    read = reopened.get(route)
    assert read.status_code == 200
    rows = read.json()["items"]
    assert len(rows) == 1
    assert {key: rows[0][key] for key in queued} == queued

    repeated = reopened.post(route, json=command, headers=headers)
    assert repeated.status_code == 202
    assert repeated.json()["id"] == queued["id"]
    assert len(reopened.get(route).json()["items"]) == 1
    e.resolve.assert_not_called()
    e.execute.assert_not_called()


@pytest.mark.file_backend_only
def test_changed_canvas_parameters_cannot_reuse_original_queue_request(file_queue):
    e = file_queue
    route = f"/api/novels/{e.project_id}/image-jobs"
    command = queue_command(e.project_id)
    headers = {"Idempotency-Key": "owned-canvas-node-stable-request"}
    response = e.client.post(route, json=command, headers=headers)
    assert response.status_code == 202
    original = response.json()
    changed = deepcopy(command)
    changed["parameters"]["seed"] = 102

    conflict = e.client.post(route, json=changed, headers=headers)

    assert conflict.status_code == 400
    assert conflict.json()["detail"] == {
        "code": "IMAGE_JOB_INVALID", "message": "IMAGE_IDEMPOTENCY_CONFLICT",
    }
    rows = e.client.get(route).json()["items"]
    assert len(rows) == 1
    assert rows[0]["id"] == original["id"]
    assert rows[0]["parameters"] == command["parameters"]
    assert rows[0]["status"] == "QUEUED" and rows[0]["attempt"] == 0
    e.resolve.assert_not_called()
    e.execute.assert_not_called()


@pytest.mark.file_backend_only
def test_cancelled_canvas_job_and_original_parameters_survive_owner_reopen(file_queue, monkeypatch):
    e = file_queue
    route = f"/api/novels/{e.project_id}/image-jobs"
    command = queue_command(e.project_id)
    response = e.client.post(
        route, json=command, headers={"Idempotency-Key": "owned-canvas-cancel-readback"},
    )
    assert response.status_code == 202
    queued = response.json()

    cancelled_response = e.client.post(f"{route}/{queued['id']}/cancel")

    assert cancelled_response.status_code == 200
    cancelled = cancelled_response.json()
    assert cancelled["id"] == queued["id"]
    assert cancelled["status"] == "CANCELLED"
    assert cancelled["cancellation_mode"] == "LOCAL_RESULT_DISCARD"
    assert cancelled["approval_status"] == "PENDING"
    assert cancelled["attempt"] == 0
    assert cancelled["request_sha256"] == queued["request_sha256"]
    for key in ("prompt", "provider_id", "model_id", "parameters", "allow_cloud_prompt"):
        assert cancelled[key] == command[key]
    readback = e.client.get(route)
    assert readback.status_code == 200
    assert len(readback.json()["items"]) == 1
    assert {key: readback.json()["items"][0][key] for key in cancelled} == cancelled

    monkeypatch.setattr(api_module, "image_job_service", ImageJobService(e.queue_root))
    reopened = TestClient(app).get(route)
    assert reopened.status_code == 200
    rows = reopened.json()["items"]
    assert len(rows) == 1
    assert {key: rows[0][key] for key in cancelled} == cancelled
    assert rows[0]["recoverable"] is False
    e.resolve.assert_not_called()
    e.execute.assert_not_called()


@pytest.mark.file_backend_only
def test_local_file_queue_reads_requested_project_and_ignores_branch_headers(file_queue, monkeypatch):
    e = file_queue
    first_route = f"/api/novels/{e.project_id}/image-jobs"
    second_project = e.repositories.novels.create({"title": "Another owned queue project"})
    second_route = f"/api/novels/{second_project['id']}/image-jobs"
    headers = {"Idempotency-Key": "same-request-in-separate-projects", "X-Branch-Id": "branch-a"}
    first = e.client.post(first_route, json=queue_command(e.project_id), headers=headers)
    assert first.status_code == 202
    first_job = first.json()
    assert first_job["branch_id"] is None
    empty = e.client.get(second_route)
    assert empty.status_code == 200 and empty.json()["items"] == []
    second = e.client.post(second_route, json=queue_command(second_project["id"]), headers=headers)
    assert second.status_code == 202
    second_job = second.json()
    assert first_job["id"] != second_job["id"]

    monkeypatch.setattr(api_module, "image_job_service", ImageJobService(e.queue_root))
    reopened = TestClient(app)
    # The selected File/local mode deliberately ignores X-Branch-Id. These
    # observations prove project partitioning, not collaboration branch access.
    for route, job in ((first_route, first_job), (second_route, second_job)):
        readback = reopened.get(route, headers={"X-Branch-Id": "branch-b"})
        assert readback.status_code == 200
        rows = readback.json()["items"]
        assert len(rows) == 1
        assert rows[0]["id"] == job["id"]
        assert rows[0]["novel_id"] == job["novel_id"]
        assert rows[0]["branch_id"] is None
        assert rows[0]["parameters"] == job["parameters"]
        assert rows[0]["status"] == "QUEUED" and rows[0]["attempt"] == 0
    e.resolve.assert_not_called()
    e.execute.assert_not_called()
