"""Original File/API source tuples for hint-free single-node task resumption.

Only original metadata preparation and reads are used. A fresh File owner is
constructed in the same process; no browser draft or recovery hint participates.
The optional capture exports actual HTTP projections, never an approval state.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.experimental import api as experimental_api
from app.services.video_assembly_service import VideoAssemblyService
from test_cloud_canvas_queue_recovery import (lookup, original_files, original_jobs,
    queue, target_command)
from test_cloud_formal_canvas_node import formal_node
from test_studio_asset_query import rig


pytestmark = pytest.mark.file_backend_only
SOURCE_COMMIT = "68291ec79b3be9c842c8d0e82f6f1ba4cb1a2b60"


@pytest.fixture
def resume_source(formal_node, monkeypatch):
    e = formal_node
    # The production list spans its existing image/audio/video owners. Complete
    # the otherwise-unused video read owner with a real empty File service,
    # rather than replacing the list with a synthetic response.
    forbidden = []
    for name in ("create_studio", "queue_studio", "execute_studio", "_render_studio_receipt"):
        sentinel = Mock(side_effect=AssertionError("Node-resume source reads cannot call " + name))
        monkeypatch.setattr(VideoAssemblyService, name, sentinel)
        forbidden.append(sentinel)

    def video_read_owner():
        owner = VideoAssemblyService(e.rig.root / "resume-video-owner", e.workspace.assets)
        e.production.video_owner = owner
        e.production.video.owner = owner
        mounted = experimental_api.studio_production_service
        monkeypatch.setattr(mounted, "video_owner", owner)
        monkeypatch.setattr(mounted.video, "owner", owner)

    original_reopen = e.reopen

    def reopen():
        original_reopen()
        video_read_owner()

    e.reopen = reopen
    video_read_owner()
    e.resolve_url = e.base + "/production/jobs/image/resolve-create"
    yield e
    for sentinel in forbidden:
        sentinel.assert_not_called()


def admitted_source(e):
    canvas, command = target_command(e, request_id="hint-free-resume-source")
    job, preview = queue(e, command)
    assert job["status"] == "QUEUED" and job["attempt"] == 0
    assert job["output_candidate"] is None and job["approved_asset_version"] is None
    return canvas, command, job, preview


def read_json(e, suffix):
    response = e.client.get(e.base + suffix, headers=e.headers)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def capture_source(e, canvas, command, job, preview):
    overview = read_json(e, "")
    jobs = read_json(e, "/production/jobs")
    observed = read_json(e, f"/production/jobs/image/{job['id']}")
    target = read_json(e, f"/canvas-views/{canvas['id']}")
    history = read_json(e, f"/canvas-views/{canvas['id']}/history")
    response = e.client.post(e.resolve_url, headers=e.headers, json=lookup(command, preview))
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    resolved = response.json()
    assert jobs["items"] == [observed] and observed == resolved == job
    assert target == canvas and target["definition"]["cards"] == []
    assert history["incarnation"] == command["canvas_image_node"]["incarnation"]
    assert history["current_version"] == target["version"] == 1
    assert history["current_definition_digest"] == target["definition_digest"]
    assert overview["project"]["id"] == e.nid
    assert overview["project"]["incarnation"] == history["incarnation"]
    capsule = observed["command"]["canvas_image_node"]
    assert capsule == command["canvas_image_node"]
    return {"contract": "studio-canvas-node-resume-file-api/1",
        "evidence_type": "REAL_ORIGINAL_FILE_API_QUEUED_METADATA_ONLY",
        "source_commit": SOURCE_COMMIT, "project": e.nid, "scope": deepcopy(e.scope),
        "incarnation": history["incarnation"],
        "node": {"id": capsule["node_id"], "title": capsule["title"],
            "prompt": observed["command"]["prompt"], "x": capsule["position"]["x"], "y": capsule["position"]["y"]},
        "overview": overview, "canvas": target, "history": history, "jobs": jobs,
        "job": observed, "resolved_job": resolved, "preview": preview,
        "command": observed["command"]}


def test_original_known_queued_node_has_exact_hint_free_source_after_fresh_file_owners(resume_source):
    e = resume_source
    canvas, command, job, preview = admitted_source(e)
    old = (e.graph, e.production, e.workspace.assets, e.production.image_jobs, e.production.video_owner)
    before = original_files(e)
    e.reopen()
    current = (e.graph, e.production, e.workspace.assets, e.production.image_jobs, e.production.video_owner)
    assert all(a is not b for a, b in zip(old, current))
    captured = capture_source(e, canvas, command, job, preview)
    assert original_files(e) == before and len(original_jobs(e)) == 1
    assert captured["job"]["automatic_replay"] is False
    assert captured["canvas"]["execution_authority"] is False
    assert captured["canvas"]["binary_content_verified"] is False
    # Export is opt-in to a caller-selected artifact path. Normal fixed-source
    # regression runs never rewrite the committed capture or source tree.
    capture = os.environ.get("CLOUD_CANVAS_NODE_RESUME_CAPTURE_FILE")
    if capture:
        raw = json.dumps(captured, ensure_ascii=False, indent=2) + "\n"
        for forbidden in (str(e.rig.root), "formal-node-test-host", "formal-node-test-session", "X-Session-Token", "Bearer "):
            assert forbidden not in raw
        Path(capture).write_text(raw, encoding="utf-8")


def test_selected_queue_version_change_is_visible_in_original_reads_not_silently_resumed(resume_source):
    e = resume_source
    _canvas, command, selected, preview = admitted_source(e)
    listed = read_json(e, "/production/jobs")["items"][0]
    assert listed == selected
    # This original metadata cancellation is separate from execution; no
    # provider is invoked. It creates a deterministic list/get interleaving.
    response = e.client.post(e.base + f"/production/jobs/image/{selected['id']}/cancel", headers=e.headers,
        json={"expected_version": selected["version"], "expected_request_digest": selected["request_digest"]})
    assert response.status_code == 200, response.text
    before = original_files(e)
    observed = read_json(e, f"/production/jobs/image/{selected['id']}")
    assert observed["status"] == "CANCELLED" and observed["version"] > listed["version"]
    assert observed["request_digest"] == listed["request_digest"] and observed["attempt"] == 0
    resolved = e.client.post(e.resolve_url, headers=e.headers, json=lookup(command, preview))
    assert resolved.status_code == 200 and resolved.json() == observed
    assert original_files(e) == before and len(original_jobs(e)) == 1


def test_original_job_read_does_not_hide_changed_canvas_version_or_history(resume_source):
    e = resume_source
    canvas, command, selected, preview = admitted_source(e)
    changed = deepcopy(canvas["definition"])
    changed["title"] = "An explicit intervening canvas edit"
    response = e.client.put(e.base + f"/canvas-views/{canvas['id']}", headers=e.headers,
        json={"expected_version": 1, "definition": changed})
    assert response.status_code == 200, response.text
    before = original_files(e)
    e.reopen()
    assert read_json(e, f"/production/jobs/image/{selected['id']}") == selected
    current = read_json(e, f"/canvas-views/{canvas['id']}")
    history = read_json(e, f"/canvas-views/{canvas['id']}/history")
    assert current["version"] == history["current_version"] == 2
    assert current["definition_digest"] != command["canvas_image_node"]["canvas_digest"]
    assert [item["version"] for item in history["items"]] == [1, 2]
    resolved = e.client.post(e.resolve_url, headers=e.headers, json=lookup(command, preview))
    assert resolved.status_code == 409, resolved.text
    assert original_files(e) == before


def test_host_read_revocation_between_source_reads_prevents_a_complete_handoff(resume_source):
    e = resume_source
    canvas, command, selected, preview = admitted_source(e)
    assert read_json(e, f"/production/jobs/image/{selected['id']}") == selected
    before = original_files(e)
    e.rig.sessions.revoke(e.headers["X-Session-Token"])
    urls = ["/production/jobs", f"/production/jobs/image/{selected['id']}"]
    for url in urls:
        denied = e.client.get(e.base + url, headers=e.headers)
        assert denied.status_code in {401, 403}, denied.text
        assert selected["id"] not in denied.text and canvas["id"] not in denied.text
    denied = e.client.post(e.resolve_url, headers=e.headers, json=lookup(command, preview))
    assert denied.status_code in {401, 403}, denied.text
    # Plain local Canvas metadata retains its original trusted-loopback
    # authority. Its continued readability is insufficient when the separate
    # production Host proof is no longer available; do not broaden that owner.
    assert read_json(e, f"/canvas-views/{canvas['id']}") == canvas
    assert read_json(e, f"/canvas-views/{canvas['id']}/history")["current_version"] == 1
    assert original_files(e) == before and len(original_jobs(e)) == 1
