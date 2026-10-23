"""Original File/GET candidate protocol over explicitly synthetic owner states.

No generated result or approval is claimed: tests persist known state using the
existing owner, never execute or accept a job, and read only a file they create.
"""
import base64
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app import api as api_module
from app.main import app
from app.repository import now
from app.services import image_job_service as image_job_module
from app.services.asset_library_service import AssetLibraryService
from app.services.image_job_service import ImageJobService
from test_cloud_canvas_image_queue import file_queue, queue_command


pytestmark = pytest.mark.file_backend_only
SYNTHETIC_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8A"
    "AwMCAO+a9skAAAAASUVORK5CYII="
)
INLINE_CANDIDATE = "data:image/png;base64," + SYNTHETIC_PNG_B64


@pytest.fixture
def candidate_protocol(file_queue, monkeypatch):
    e = file_queue
    e.owner = api_module.image_job_service
    e.assets = AssetLibraryService(e.queue_root)
    e.accept = Mock(side_effect=AssertionError("Protocol fixture must not accept a job"))
    e.inspect = Mock(side_effect=AssertionError("Protocol fixture must not decode media"))
    e.fetch = Mock(side_effect=AssertionError("Protocol fixture must not fetch candidate URIs"))
    monkeypatch.setattr(ImageJobService, "accept", e.accept)
    monkeypatch.setattr(image_job_module, "inspect_image", e.inspect)
    monkeypatch.setattr(image_job_module, "fetch_media_bytes", e.fetch)
    monkeypatch.setattr(api_module, "asset_library_service", e.assets)
    return e


def seed_synthetic_candidate(e, *, owner=None, branch=None, request_id="synthetic-candidate-protocol"):
    """Fixture setup, not a production completion or approval transition."""
    owner = owner or e.owner
    queued = owner.create(e.project_id, branch, queue_command(e.project_id), request_id)

    def persist(rows):
        row = owner._find(rows, queued["id"])
        row.update(status="SUCCEEDED", approval_status="PENDING", attempt=1,
                   asset_uri=INLINE_CANDIDATE, updated_at=now())
        return row

    return owner._mutate(e.project_id, branch, persist)


def assert_no_generation_or_accept(e):
    for sentinel in (e.resolve, e.execute, e.accept, e.inspect, e.fetch):
        sentinel.assert_not_called()


def test_original_get_reads_inline_pending_candidate_from_file_after_reopen(candidate_protocol, monkeypatch):
    e = candidate_protocol
    seeded = seed_synthetic_candidate(e)
    route = f"/api/novels/{e.project_id}/image-jobs"

    response = e.client.get(route, headers={"X-Branch-Id": "ignored-in-local-mode"})

    assert response.status_code == 200
    assert set(response.json()) == {"items"}
    row = response.json()["items"][0]
    assert row["id"] == seeded["id"]
    assert row["novel_id"] == e.project_id
    assert row["branch_id"] is None and row["owner_actor_id"] is None
    assert row["status"] == "SUCCEEDED" and row["approval_status"] == "PENDING"
    assert row["asset_uri"] == INLINE_CANDIDATE
    assert "asset_id" not in row and "output_candidate" not in row
    assert row["recoverable"] is False
    monkeypatch.setattr(api_module, "image_job_service", ImageJobService(e.queue_root))
    reopened = TestClient(app)
    assert reopened.get(route).json() == response.json()
    assert_no_generation_or_accept(e)


def test_synthetic_approved_reference_and_known_file_download_match_original_api(candidate_protocol, monkeypatch):
    e = candidate_protocol
    candidate = seed_synthetic_candidate(e)
    route = f"/api/novels/{e.project_id}/image-jobs"
    pending = e.client.get(route)
    assert pending.status_code == 200
    original = base64.b64decode(SYNTHETIC_PNG_B64, validate=True)
    expected_sha = hashlib.sha256(original).hexdigest()
    asset = e.assets.create(e.project_id, "synthetic-canvas-candidate.png", SYNTHETIC_PNG_B64,
        "image/png", "image", "synthetic-protocol-asset:" + candidate["id"])
    stamp = now()
    asset = e.assets.update_metadata(asset["id"], {
        "source_job_id": candidate["id"], "provider_id": candidate["provider_id"],
        "model_id": candidate["model_id"], "parameters": deepcopy(candidate["parameters"]),
        "approved_at": stamp,
    })

    def persist_synthetic_approval(rows):
        row = e.owner._find(rows, candidate["id"])
        row.update(approval_status="APPROVED", asset_id=asset["id"], approved_at=stamp, updated_at=stamp)
        return row

    e.owner._mutate(e.project_id, None, persist_synthetic_approval)
    approved = e.client.get(route)
    assert approved.status_code == 200
    row = approved.json()["items"][0]
    assert row["id"] == candidate["id"] and row["status"] == "SUCCEEDED"
    assert row["approval_status"] == "APPROVED" and row["asset_id"] == asset["id"]
    assert row["asset_uri"] == INLINE_CANDIDATE and row["approved_at"] == stamp
    metadata_path = f"/api/assets/{asset['id']}?novel_id={e.project_id}"
    metadata = e.client.get(metadata_path)
    assert metadata.status_code == 200
    assert metadata.json()["id"] == row["asset_id"]
    assert metadata.json()["novel_id"] == e.project_id
    assert metadata.json()["branch_id"] is None
    assert metadata.json()["source_job_id"] == row["id"]
    assert metadata.json()["sha256"] == expected_sha
    download_path = f"/api/assets/{asset['id']}/download?novel_id={e.project_id}"
    download = e.client.get(download_path)
    assert download.status_code == 200 and download.content == original
    assert download.headers["x-asset-sha256"] == expected_sha
    assert download.headers["content-type"] == "image/png"
    assert download.headers["x-content-type-options"] == "nosniff"
    assert int(download.headers["content-length"]) == len(original)
    assert "attachment" in download.headers["content-disposition"]
    monkeypatch.setattr(api_module, "image_job_service", ImageJobService(e.queue_root))
    assert e.client.get(route).json() == approved.json()
    assert_no_generation_or_accept(e)

    capture = os.getenv("CLOUD_CANVAS_CANDIDATE_CAPTURE_FILE")
    if capture:
        fixture = {
            "fixture_kind": "EXPLICIT_SYNTHETIC_OWNER_STATES_NO_EXECUTION_OR_ACCEPT",
            "base_commit": "1c19d81ddc55043a9bd908af6ddb56cda71e5186",
            "limitations": "Real File persistence and original GET/download protocol only; the status and approval markers are explicit test setup, not generated or accepted media.",
            "project_id": e.project_id, "task_id": candidate["id"],
            "pending_inline": pending.json(), "approved": approved.json(), "approved_asset": metadata.json(),
            "download": {"status": download.status_code, "path": download_path,
                "body_b64": base64.b64encode(download.content).decode(),
                "headers": {name: download.headers[name] for name in (
                    "content-type", "content-disposition", "content-length", "x-asset-sha256", "x-content-type-options")}},
            "paths": {"jobs": route, "approved_asset_metadata": metadata_path},
        }
        Path(capture).write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_candidate_owner_actor_branch_partitions_are_persisted_without_dispatch(candidate_protocol):
    e = candidate_protocol
    first = seed_synthetic_candidate(e, owner=e.owner.for_actor("synthetic-actor-a"), branch="branch-a")
    second = seed_synthetic_candidate(e, owner=e.owner.for_actor("synthetic-actor-a"), branch="branch-b")
    other = seed_synthetic_candidate(e, owner=e.owner.for_actor("synthetic-actor-b"), branch="branch-a")
    reopened = ImageJobService(e.queue_root)
    for actor, branch, expected in (("synthetic-actor-a", "branch-a", first),
                                  ("synthetic-actor-a", "branch-b", second),
                                  ("synthetic-actor-b", "branch-a", other)):
        rows = reopened.for_actor(actor).list(e.project_id, branch)
        assert len(rows) == 1 and rows[0]["id"] == expected["id"]
        assert rows[0]["owner_actor_id"] == actor and rows[0]["branch_id"] == branch
        assert rows[0]["status"] == "SUCCEEDED" and rows[0]["approval_status"] == "PENDING"
    # This is an owner-partition check, not collaboration-session verification.
    # The original local GET does not borrow any actor/branch candidate store.
    local = e.client.get(f"/api/novels/{e.project_id}/image-jobs")
    assert local.status_code == 200 and local.json() == {"items": []}
    assert_no_generation_or_accept(e)
