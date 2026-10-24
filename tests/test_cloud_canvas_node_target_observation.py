"""Real original File/API observations; setup stops at a QUEUED image Job.

No execution, media, approval or target restore occurs. Fault-injected read
projections below are explicitly negative software interleavings, not generated
content or real concurrent commits. Cold reconstruction stays in this process.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.creative.canvas_views import CreativeCanvasViews
from app.creative.production_execution import ProductionExecutionService
from app.experimental import api as experimental_api
from app.services.image_job_service import ImageJobService
from test_cloud_formal_canvas_node import formal_node
from test_cloud_canvas_queue_recovery import target_command, queue, lookup, original_files, original_jobs
from test_studio_asset_query import rig


pytestmark = pytest.mark.file_backend_only
BASELINE = "9153bbcabd4d77f68859d61d1d635526fc636c69"


@pytest.fixture
def target_source(formal_node):
    e = formal_node
    canvas, command = target_command(e, request_id="original-target-observation")
    job, preview = queue(e, command)
    e.target_source = canvas, command, job, preview
    e.observation_url = e.base + f"/production/jobs/image/{job['id']}/target-observation"
    return e


def pin(job):
    return {"expected_version": job["version"], "expected_request_digest": job["request_digest"]}


def observe(e, body=None, *, headers=None, jid=None):
    url = e.observation_url if jid is None else e.base + f"/production/jobs/image/{jid}/target-observation"
    return e.client.post(url, headers=e.headers if headers is None else headers,
        json=pin(e.target_source[2]) if body is None else body)


def save_title(e, source, title):
    definition = deepcopy(source["definition"])
    definition["title"] = title
    response = e.client.put(e.base + f"/canvas-views/{source['id']}", headers=e.headers,
        json={"expected_version": source["version"], "definition": definition})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def forbid_observation_calls(monkeypatch):
    forbidden = []

    def seal():
        for owner, name in ((ProductionExecutionService, "preview"), (ProductionExecutionService, "create"),
                            (ProductionExecutionService, "cancel"), (ProductionExecutionService, "reconcile"),
                            (ProductionExecutionService, "providers"), (ProductionExecutionService, "resolve_image_node_create"),
                            (ProductionExecutionService, "list"), (ImageJobService, "create_studio"),
                            (ImageJobService, "list_studio"), (CreativeCanvasViews, "create"),
                            (CreativeCanvasViews, "save"), (CreativeCanvasViews, "restore"),
                            (CreativeCanvasViews, "image_node_result")):
            sentinel = Mock(side_effect=AssertionError("Target observation must not call " + name))
            monkeypatch.setattr(owner, name, sentinel)
            forbidden.append(sentinel)
    yield seal
    for sentinel in forbidden:
        sentinel.assert_not_called()


def assert_closed(response, status):
    assert response.status_code == status, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    problem = response.json()
    # The application retains its existing common Problem JSON envelope.
    assert set(problem) == {"detail", "code", "message", "details", "request_id"}
    assert set(problem["detail"]) == {"code"}
    assert problem["code"] == problem["message"] == problem["detail"]["code"]
    assert problem["details"] == problem["detail"]
    assert problem["code"].startswith("STUDIO_IMAGE_NODE_TARGET_OBSERVATION_")
    assert problem["request_id"] == response.headers["x-request-id"]


@pytest.mark.parametrize("changed", [False, True])
def test_original_target_comparison_is_cold_readable_without_mutating_original_files(target_source, forbid_observation_calls, changed):
    e = target_source
    original, command, job, preview = e.target_source
    current = save_title(e, original, "A deliberately changed saved canvas") if changed else original
    if changed:
        refused = e.client.post(e.base + "/production/jobs/image/resolve-create", headers=e.headers,
            json=lookup(command, preview))
        assert refused.status_code == 409, refused.text
    old = (e.graph, e.production, e.workspace.assets, e.production.image_jobs)
    e.reopen()
    fresh = (e.graph, e.production, e.workspace.assets, e.production.image_jobs)
    assert all(a is not b for a, b in zip(old, fresh))
    before = original_files(e)
    forbid_observation_calls()
    response = observe(e)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    result = response.json()
    assert set(result) == {"contract", "job", "target", "incarnation", "canvas", "history", "comparison", "automatic_actions"}
    assert result["contract"] == "studio-image-node-target-observation/1"
    assert result["job"] == job and result["job"]["attempt"] == 0
    assert result["job"]["output_candidate"] is None and result["job"]["approved_asset_version"] is None
    assert result["target"] == command["canvas_image_node"]
    assert result["incarnation"] == command["canvas_image_node"]["incarnation"]
    assert result["comparison"] == ("CURRENT_CHANGED" if changed else "CURRENT_MATCH")
    assert result["automatic_actions"] is False
    assert result["canvas"] == {"id": current["id"], "project_id": e.nid, "scope": e.scope,
        "version": current["version"], "definition_digest": current["definition_digest"],
        "title": current["definition"]["title"], "card_count": 0,
        "execution_authority": False, "binary_content_verified": False}
    assert result["history"] == {"incarnation": result["incarnation"], "current_version": current["version"],
        "current_definition_digest": current["definition_digest"], "target_version": original["version"],
        "target_definition_digest": original["definition_digest"], "target_empty": True}
    assert original_files(e) == before and len(original_jobs(e)) == 1
    capture = os.environ.get("CLOUD_CANVAS_NODE_TARGET_CAPTURE_FILE")
    if changed and capture:
        root = Path(__file__).resolve().parents[1]
        backend = ("app/creative/canvas_image_node_target_observation.py", "app/creative/production_execution.py",
                   "app/creative/production_execution_api.py")
        source = {"contract": "studio-node-target-observation-file-api/1", "baseline_commit": BASELINE,
            "implementation_sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in backend},
            "evidence_type": "REAL_ORIGINAL_FILE_API_QUEUED_TARGET_METADATA_ONLY", "project": e.nid,
            "scope": e.scope, "queued_job": job, "original_canvas": original, "changed_canvas": current,
            "observation": result}
        raw = json.dumps(source, ensure_ascii=False, indent=2) + "\n"
        for forbidden in (str(e.rig.root), "formal-node-test-host", "formal-node-test-session", "X-Session-Token", "Bearer "):
            assert forbidden not in raw
        Path(capture).write_text(raw, encoding="utf-8")


def test_higher_canvas_version_is_changed_even_when_definition_digest_returns_to_original(target_source, forbid_observation_calls):
    e = target_source
    original = e.target_source[0]
    second = save_title(e, original, "An intervening title")
    current = save_title(e, second, original["definition"]["title"])
    assert current["version"] == 3 and current["definition_digest"] == original["definition_digest"]
    before = original_files(e)
    forbid_observation_calls()
    response = observe(e)
    assert response.status_code == 200, response.text
    assert response.json()["comparison"] == "CURRENT_CHANGED"
    assert response.json()["history"]["target_version"] == 1
    assert original_files(e) == before


@pytest.mark.parametrize("field", ["version", "digest"])
def test_changed_selected_job_precondition_refuses_without_target_observation(target_source, forbid_observation_calls, monkeypatch, field):
    e = target_source
    body = pin(e.target_source[2])
    body["expected_version" if field == "version" else "expected_request_digest"] = 2 if field == "version" else "0" * 64
    never = Mock(side_effect=AssertionError("Stale Job must not inspect a canvas"))
    monkeypatch.setattr(e.graph.canvas_views, "get", never)
    before = original_files(e)
    forbid_observation_calls()
    assert_closed(observe(e, body), 409)
    never.assert_not_called()
    assert original_files(e) == before


@pytest.mark.parametrize("fault", ["history-current", "historical-digest", "historical-empty", "history-incarnation"])
def test_inconsistent_or_changed_history_projection_cannot_inherit_target_proof(target_source, forbid_observation_calls, monkeypatch, fault):
    e = target_source
    history = e.graph.canvas_views.history

    def inconsistent(*args, **kwargs):
        value = deepcopy(history(*args, **kwargs))
        if fault == "history-current": value["current_version"] += 1
        elif fault == "historical-digest": value["items"][0]["definition_digest"] = "0" * 64
        elif fault == "historical-empty": value["items"][0]["definition"]["cards"] = [{"id": "injected-read-fault"}]
        else: value["incarnation"] = "file:00000000-0000-4000-8000-000000000000"
        return value

    monkeypatch.setattr(e.graph.canvas_views, "history", inconsistent)
    before = original_files(e)
    forbid_observation_calls()
    assert_closed(observe(e), 409)
    assert original_files(e) == before


def test_second_original_job_read_must_match_complete_captured_receipt(target_source, forbid_observation_calls, monkeypatch):
    e = target_source
    read = ProductionExecutionService._row
    calls = 0

    def changed(owner, *args, **kwargs):
        nonlocal calls
        row, context = read(owner, *args, **kwargs)
        calls += 1
        if calls == 2:
            row = deepcopy(row)
            row["version"] += 1
        return row, context

    monkeypatch.setattr(ProductionExecutionService, "_row", changed)
    before = original_files(e)
    forbid_observation_calls()
    assert_closed(observe(e), 409)
    assert calls == 2 and original_files(e) == before


def test_revoked_host_refuses_even_when_trusted_loopback_canvas_metadata_is_readable(target_source, forbid_observation_calls):
    e = target_source
    e.rig.sessions.revoke(e.headers["X-Session-Token"])
    assert e.client.get(e.base + f"/canvas-views/{e.target_source[0]['id']}").status_code == 200
    before = original_files(e)
    forbid_observation_calls()
    result = observe(e)
    assert result.status_code in {401, 403}, result.text
    assert_closed(result, result.status_code)
    assert e.target_source[2]["id"] not in result.text
    assert original_files(e) == before


def test_missing_file_identity_is_not_reprovisioned_by_observation(target_source, forbid_observation_calls):
    e = target_source
    marker = e.rig.root / "novels" / e.nid / "creative_project_v2.json"
    preserved = marker.with_suffix(".retained-for-observation-test")
    original = marker.read_bytes()
    # Only this freshly created synthetic fixture marker is moved, preserving
    # its bytes. No user/source file is deleted or touched.
    marker.rename(preserved)
    before = original_files(e)
    forbid_observation_calls()
    result = observe(e)
    assert result.status_code in {404, 422}, result.text
    assert_closed(result, result.status_code)
    assert not marker.exists() and preserved.read_bytes() == original
    assert original_files(e) == before


@pytest.mark.parametrize("kind", ["unknown-job", "extra-field", "boolean-version", "duplicate-key", "too-large"])
def test_closed_request_errors_are_bounded_and_nonmutating(target_source, forbid_observation_calls, kind):
    e = target_source
    body = pin(e.target_source[2])
    before = original_files(e)
    forbid_observation_calls()
    if kind == "unknown-job": response = observe(e, jid="missing-original-job"); status = 404
    elif kind == "extra-field": response = observe(e, {**body, "canvas_id": e.target_source[0]["id"]}); status = 422
    elif kind == "boolean-version": response = observe(e, {**body, "expected_version": True}); status = 422
    elif kind == "duplicate-key":
        raw = '{"expected_version":1,"expected_version":1,"expected_request_digest":"' + body["expected_request_digest"] + '"}'
        response = e.client.post(e.observation_url, headers={**e.headers, "Content-Type": "application/json"}, content=raw); status = 422
    else:
        response = e.client.post(e.observation_url, headers={**e.headers, "Content-Type": "application/json"}, content='{"padding":"' + 'x' * 4100 + '"}'); status = 413
    assert_closed(response, status)
    assert original_files(e) == before
