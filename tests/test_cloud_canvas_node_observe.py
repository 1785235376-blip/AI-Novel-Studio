"""Real original File/API metadata for a cold cancelled-node observation.

The source is queued then cancelled through its original HTTP owner. Subsequent
reads use fresh File owners in the same process, without browser graph/hints,
provider execution, candidate content or approval.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.creative.production_execution import ProductionExecutionService
from app.services.image_job_service import ImageJobService
from test_cloud_canvas_node_resume import (admitted_source, capture_source,
    formal_node, read_json, resume_source, rig)
from test_cloud_canvas_queue_recovery import lookup, original_files, original_jobs


pytestmark = pytest.mark.file_backend_only
SOURCE_COMMIT = "ef65454344709d98f891f246e8c56e3e1d15d647"


@pytest.fixture
def observe_source(resume_source, monkeypatch):
    e = resume_source
    canvas, command, queued, preview = admitted_source(e)
    response = e.client.post(e.base + f"/production/jobs/image/{queued['id']}/cancel",
        headers=e.headers, json={"expected_version": queued["version"],
            "expected_request_digest": queued["request_digest"]})
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    cancelled = response.json()
    assert cancelled["id"] == queued["id"] and cancelled["version"] == queued["version"] + 1
    assert cancelled["status"] == "CANCELLED" and cancelled["attempt"] == 0
    assert cancelled["request_digest"] == queued["request_digest"]
    assert cancelled["cancellation_mode"] == "LOCAL_RESULT_DISCARD"
    assert cancelled["remote_compute_may_continue"] is True
    assert cancelled["output_candidate"] is None and cancelled["approved_asset_version"] is None
    assert cancelled["receipt_digest"] is None and cancelled["automatic_replay"] is False
    e.observation = (canvas, command, queued, cancelled, preview)
    # Metadata preparation above is deliberate. Nothing observing that source
    # may preview, queue, execute, load media or repair an execution afterward.
    forbidden = []
    for owner, name in ((ProductionExecutionService, "preview"),
                        (ProductionExecutionService, "create"),
                        (ProductionExecutionService, "cancel"),
                        (ProductionExecutionService, "reconcile"),
                        (ImageJobService, "create_studio")):
        sentinel = Mock(side_effect=AssertionError("Node observation cannot call " + name))
        monkeypatch.setattr(owner, name, sentinel)
        forbidden.append(sentinel)
    yield e
    for sentinel in forbidden:
        sentinel.assert_not_called()


def test_cancelled_node_metadata_is_exact_after_fresh_file_owners_without_local_hints(observe_source):
    e = observe_source
    canvas, command, queued, cancelled, preview = e.observation
    old = (e.graph, e.production, e.workspace.assets, e.production.image_jobs, e.production.video_owner)
    before = original_files(e)
    e.reopen()
    current = (e.graph, e.production, e.workspace.assets, e.production.image_jobs, e.production.video_owner)
    assert all(a is not b for a, b in zip(old, current))
    captured = capture_source(e, canvas, command, cancelled, preview)
    assert captured["job"] == cancelled and captured["job"] != queued
    assert captured["job"]["status"] == "CANCELLED" and captured["job"]["attempt"] == 0
    assert captured["canvas"]["execution_authority"] is False
    assert captured["canvas"]["binary_content_verified"] is False
    # A second explicit read observes the same owner, not a resume/retry action.
    assert read_json(e, f"/production/jobs/image/{cancelled['id']}") == cancelled
    assert original_files(e) == before and len(original_jobs(e)) == 1
    captured.update(contract="studio-canvas-node-observe-file-api/1",
        evidence_type="REAL_ORIGINAL_FILE_API_CANCELLED_METADATA_ONLY",
        source_commit=SOURCE_COMMIT, queued_job=queued, cancelled_job=cancelled)
    capture = os.environ.get("CLOUD_CANVAS_NODE_OBSERVE_CAPTURE_FILE")
    if capture:
        raw = json.dumps(captured, ensure_ascii=False, indent=2) + "\n"
        for forbidden in (str(e.rig.root), "formal-node-test-host", "formal-node-test-session", "X-Session-Token", "Bearer "):
            assert forbidden not in raw
        Path(capture).write_text(raw, encoding="utf-8")


def test_cancelled_job_does_not_hide_changed_original_canvas_version(observe_source):
    e = observe_source
    canvas, command, _queued, cancelled, preview = e.observation
    changed = deepcopy(canvas["definition"])
    changed["title"] = "An explicitly changed cancelled-node canvas"
    response = e.client.put(e.base + f"/canvas-views/{canvas['id']}", headers=e.headers,
        json={"expected_version": canvas["version"], "definition": changed})
    assert response.status_code == 200, response.text
    before = original_files(e)
    e.reopen()
    assert read_json(e, f"/production/jobs/image/{cancelled['id']}") == cancelled
    target = read_json(e, f"/canvas-views/{canvas['id']}")
    history = read_json(e, f"/canvas-views/{canvas['id']}/history")
    assert target["version"] == history["current_version"] == canvas["version"] + 1
    assert target["definition_digest"] != command["canvas_image_node"]["canvas_digest"]
    resolved = e.client.post(e.resolve_url, headers=e.headers, json=lookup(command, preview))
    assert resolved.status_code == 409, resolved.text
    assert original_files(e) == before and len(original_jobs(e)) == 1


def test_cancelled_source_still_requires_live_production_read_authority(observe_source):
    e = observe_source
    canvas, command, _queued, cancelled, preview = e.observation
    e.reopen()
    assert read_json(e, f"/production/jobs/image/{cancelled['id']}") == cancelled
    before = original_files(e)
    e.rig.sessions.revoke(e.headers["X-Session-Token"])
    for suffix in ("/production/jobs", f"/production/jobs/image/{cancelled['id']}"):
        denied = e.client.get(e.base + suffix, headers=e.headers)
        assert denied.status_code in {401, 403}, denied.text
        assert cancelled["id"] not in denied.text and canvas["id"] not in denied.text
    denied = e.client.post(e.resolve_url, headers=e.headers, json=lookup(command, preview))
    assert denied.status_code in {401, 403}, denied.text
    # Plain trusted-loopback Canvas metadata is a different original authority;
    # its successful read cannot replace the denied production-owner proof.
    assert read_json(e, f"/canvas-views/{canvas['id']}") == canvas
    assert original_files(e) == before and len(original_jobs(e)) == 1
