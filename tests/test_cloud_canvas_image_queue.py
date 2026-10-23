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
        resolve=resolve, execute=execute,
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
