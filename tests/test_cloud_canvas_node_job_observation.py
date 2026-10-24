"""Exact original Job metadata without Canvas/content/recovery reads.

Positive File states are created only by original queue/cancel routes. Injected
read faults and candidate-extra counterexamples below are software projections,
not execution, reviewed output or evidence of an approved asset.
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
from test_cloud_canvas_node_target_observation import (
    target_source, formal_node, rig, pin, save_title, forbid_observation_calls,
    original_files, original_jobs)

pytestmark = pytest.mark.file_backend_only
BASELINE = "6e6fcd72a09622e600c3f357e5f6bd6ef449072b"
FIELDS = {"contract", "owner", "id", "novel_id", "branch_id", "version", "operation_id", "request_id", "status",
    "request_digest", "receipt_digest", "attempt", "created_at", "updated_at", "error_code", "review_state",
    "cancellation_mode", "needs_reconciliation", "execution_state", "output_candidate", "command", "provider",
    "approved_asset_version", "product_acceptance", "automatic_replay", "remote_compute_may_continue"}


def read_job(e, body=None, *, headers=None, jid=None, nid=None):
    job = e.target_source[2]
    url = f"/api/projects/{nid or e.nid}/studio/production/jobs/image/{jid or job['id']}/node-observation"
    return e.client.post(url, headers=e.headers if headers is None else headers, json=pin(job) if body is None else body)


def closed(response, status):
    assert response.status_code == status, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    problem = response.json()
    assert set(problem) == {"detail", "code", "message", "details", "request_id"}
    assert problem["detail"] == problem["details"] == {"code": problem["code"]}
    assert problem["message"] == problem["code"]
    assert problem["code"].startswith("STUDIO_IMAGE_NODE_JOB_OBSERVATION_")
    assert problem["request_id"] == response.headers["x-request-id"]


@pytest.fixture
def no_canvas_or_actions(forbid_observation_calls, monkeypatch):
    sentinels = []
    def seal():
        forbid_observation_calls()
        for name in ("get", "history", "list"):
            sentinel = Mock(side_effect=AssertionError("Job metadata must not call Canvas " + name))
            monkeypatch.setattr(CreativeCanvasViews, name, sentinel)
            sentinels.append(sentinel)
    yield seal
    for sentinel in sentinels:
        sentinel.assert_not_called()


@pytest.mark.parametrize("cancelled", [False, True])
def test_original_cold_job_remains_readable_after_canvas_change_without_reading_it(target_source, no_canvas_or_actions, cancelled):
    e = target_source
    canvas, command, queued, preview = e.target_source
    selected = queued
    if cancelled:
        response = e.client.post(e.base + f"/production/jobs/image/{queued['id']}/cancel",
            headers=e.headers, json=pin(queued))
        assert response.status_code == 200, response.text
        selected = response.json()
        assert selected["status"] == "CANCELLED" and selected["attempt"] == 0
        assert selected["output_candidate"] is None and selected["approved_asset_version"] is None
    current = save_title(e, canvas, "Later saved metadata; original Job stays independently readable")
    assert current["version"] != command["canvas_image_node"]["canvas_version"]
    old = e.production, e.workspace, e.production.image_jobs
    e.reopen()
    assert all(a is not b for a, b in zip(old, (e.production, e.workspace, e.production.image_jobs)))
    before = original_files(e)
    no_canvas_or_actions()
    response = read_job(e, pin(selected))
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    result = response.json()
    assert set(result) == {"contract", "job", "target", "incarnation", "canvas_read", "automatic_actions"}
    assert result["contract"] == "studio-image-node-job-observation/1"
    assert result["canvas_read"] is result["automatic_actions"] is False
    assert set(result["job"]) == FIELDS
    assert result["job"] == {key: deepcopy(selected.get(key)) for key in FIELDS}
    assert result["target"] == command["canvas_image_node"]
    assert result["incarnation"] == command["canvas_image_node"]["incarnation"]
    assert original_files(e) == before and len(original_jobs(e)) == 1
    capture = os.environ.get("CLOUD_CANVAS_NODE_JOB_CAPTURE_FILE")
    if cancelled and capture:
        root = Path(__file__).resolve().parents[1]
        backend = ["app/creative/canvas_image_node_job_observation.py", "app/creative/production_execution.py",
            "app/creative/production_execution_api.py"]
        source = {"contract": "studio-node-job-observation-file-api/1", "baseline_commit": BASELINE,
            "implementation_sha256": {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in backend},
            "evidence_type": "REAL_ORIGINAL_FILE_API_CANCELLED_METADATA_ONLY", "project": e.nid, "scope": e.scope,
            "selected_job": selected, "observation": result}
        raw = json.dumps(source, ensure_ascii=False, indent=2) + "\n"
        for forbidden in (str(e.rig.root), "formal-node-test-host", "formal-node-test-session", "X-Session-Token", "Bearer "):
            assert forbidden not in raw
        Path(capture).write_text(raw, encoding="utf-8")


@pytest.mark.parametrize("fault", ["version", "digest", "missing-job", "other-project"])
def test_exact_selected_task_is_never_replaced(target_source, no_canvas_or_actions, fault):
    e = target_source
    body = pin(e.target_source[2])
    args = {}
    status = 409
    if fault == "version": body["expected_version"] += 1
    elif fault == "digest": body["expected_request_digest"] = "0" * 64
    elif fault == "missing-job": args["jid"] = "missing-exact-job"; status = 404
    else: args["nid"] = "missing-other-project"; status = 404
    before = original_files(e)
    no_canvas_or_actions()
    response = read_job(e, body, **args)
    closed(response, status)
    assert original_files(e) == before


def test_missing_project_identity_cannot_be_provisioned_by_metadata_observation(target_source, no_canvas_or_actions):
    e = target_source
    marker = e.rig.root / "novels" / e.nid / "creative_project_v2.json"
    content = marker.read_bytes()
    preserved = marker.with_suffix(".retained-for-job-observation-test")
    marker.rename(preserved)
    before = original_files(e)
    no_canvas_or_actions()
    response = read_job(e)
    assert response.status_code in {404, 422}, response.text
    closed(response, response.status_code)
    assert not marker.exists() and preserved.read_bytes() == content and original_files(e) == before


def test_original_production_read_authority_is_rechecked(target_source, no_canvas_or_actions):
    e = target_source
    e.rig.sessions.revoke(e.headers["X-Session-Token"])
    before = original_files(e)
    no_canvas_or_actions()
    response = read_job(e)
    assert response.status_code in {401, 403}, response.text
    closed(response, response.status_code)
    assert e.target_source[2]["id"] not in response.text and original_files(e) == before


@pytest.mark.parametrize("fault", ["row", "context"])
def test_late_job_or_context_change_cannot_inherit_read_metadata(target_source, no_canvas_or_actions, monkeypatch, fault):
    e = target_source
    original = ProductionExecutionService._row
    calls = 0
    def changed(owner, *args, **kwargs):
        nonlocal calls
        row, context = original(owner, *args, **kwargs)
        calls += 1
        if calls == 2:
            row, context = deepcopy(row), deepcopy(context)
            if fault == "row": row["error_code"] = "INJECTED_SOFTWARE_READ_CHANGE"
            else: context["unexpected_read_change"] = True
        return row, context
    monkeypatch.setattr(ProductionExecutionService, "_row", changed)
    before = original_files(e)
    no_canvas_or_actions()
    closed(read_job(e), 409)
    assert calls == 2 and original_files(e) == before


def test_unknown_candidate_payload_fields_are_never_exposed_as_metadata(target_source, no_canvas_or_actions, monkeypatch):
    e = target_source
    original = ProductionExecutionService._row
    payload = "data:application/octet-stream;base64,U09GVFdBUkUtQ09VTlRFUkVYQU1QTEU="
    def projected(owner, *args, **kwargs):
        row, context = original(owner, *args, **kwargs)
        row = deepcopy(row)
        row["output_candidate"] = {"id": "software-candidate-pin", "version": 1, "kind": "image", "digest": "b" * 64,
            "data_uri": payload, "uri": "https://invalid.example/never-fetch"}
        return row, context
    monkeypatch.setattr(ProductionExecutionService, "_row", projected)
    before = original_files(e)
    no_canvas_or_actions()
    response = read_job(e)
    assert response.status_code == 200, response.text
    candidate = response.json()["job"]["output_candidate"]
    assert candidate == {"id": "software-candidate-pin", "version": 1, "kind": "image", "digest": "b" * 64}
    assert payload not in response.text and "invalid.example" not in response.text
    assert original_files(e) == before


@pytest.mark.parametrize("body", [{"canvas_id": "untrusted-canvas"}, {"expected_version": True}])
def test_closed_body_does_not_accept_canvas_override_or_bool_version(target_source, no_canvas_or_actions, body):
    e = target_source
    before = original_files(e)
    no_canvas_or_actions()
    closed(read_job(e, {**pin(e.target_source[2]), **body}), 422)
    assert original_files(e) == before


def test_node_metadata_body_limit_is_closed_before_owner_work(target_source, no_canvas_or_actions):
    e = target_source
    no_canvas_or_actions()
    response = e.client.post(e.base + f"/production/jobs/image/{e.target_source[2]['id']}/node-observation",
        headers={**e.headers, "Content-Type": "application/json"}, content=b" " * 4097)
    closed(response, 413)


def test_oversized_metadata_projection_fails_without_truncation(target_source, no_canvas_or_actions, monkeypatch):
    e = target_source
    original = ProductionExecutionService.observe_image_node_job
    def oversized(owner, *args, **kwargs):
        value = original(owner, *args, **kwargs)
        value["software_size_fault"] = "x" * (256 * 1024)
        return value
    monkeypatch.setattr(ProductionExecutionService, "observe_image_node_job", oversized)
    before = original_files(e)
    no_canvas_or_actions()
    closed(read_job(e), 413)
    assert original_files(e) == before
