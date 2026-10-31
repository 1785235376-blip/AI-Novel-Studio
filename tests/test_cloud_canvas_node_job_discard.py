"""Explicit original QUEUED cancellation; no execution, content or review.

Only the original cancel owner writes a synthetic Job. Injected raw-read/CAS
faults are software counterexamples and never establish real provider output.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app import api as legacy_api
from app.creative.canvas_views import CreativeCanvasViews
from app.creative.production_execution import ProductionExecutionService
from app.services.image_job_service import ImageJobService
from test_cloud_canvas_node_target_observation import (
    target_source, formal_node, rig, pin, save_title, original_files, original_jobs)
from test_cloud_canvas_node_job_observation import read_job, FIELDS

pytestmark = pytest.mark.file_backend_only
BASELINE = "e28baafe73b9074ee7f7da8a814637a5958f196f"


def discard(e, body=None, *, headers=None):
    job = e.target_source[2]
    return e.client.post(e.base + f"/production/jobs/image/{job['id']}/node-discard",
        headers=e.headers if headers is None else headers,
        json={**pin(job), "confirmed": True} if body is None else body)


def closed(response, status):
    assert response.status_code == status, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    value = response.json()
    assert set(value) == {"detail", "code", "message", "details", "request_id"}
    assert value["detail"] == value["details"] == {"code": value["code"]}
    assert value["message"] == value["code"]
    assert value["code"].startswith("STUDIO_IMAGE_NODE_JOB_DISCARD_")
    assert value["request_id"] == response.headers["x-request-id"]


@pytest.fixture
def no_other_operations(monkeypatch):
    forbidden = []
    def seal():
        targets = [(ProductionExecutionService, name) for name in (
            "preview", "create", "reconcile", "providers", "resolve_image_node_create", "list")]
        targets += [(ImageJobService, name) for name in ("create_studio", "list_studio", "reconcile_studio")]
        targets += [(CreativeCanvasViews, name) for name in (
            "get", "history", "list", "create", "save", "restore", "image_node_result")]
        for owner, name in targets:
            sentinel = Mock(side_effect=AssertionError("Node discard must not call " + name))
            monkeypatch.setattr(owner, name, sentinel)
            forbidden.append(sentinel)
    yield seal
    for sentinel in forbidden:
        sentinel.assert_not_called()


def queue_path(e):
    return str(e.production.image_jobs.for_actor(e.actor)._path(e.nid, e.scope.get("branch_id")).relative_to(e.rig.root))


def assert_only_original_job_changed(e, before):
    after = original_files(e)
    changed = {key for key in before if before[key] != after[key]}
    assert changed == {queue_path(e)}
    rows = original_jobs(e)
    assert len(rows) == 1 and rows[0]["status"] == "CANCELLED"
    assert rows[0]["version"] == e.target_source[2]["version"] + 1
    assert rows[0]["attempt"] == 0 and rows[0]["output_asset_id"] is None
    assert rows[0]["receipt_digest"] is None and rows[0]["local_result_discarded"] is True
    return rows[0]


def test_explicit_discard_changes_only_original_job_after_canvas_edit_and_is_cold_readable(target_source, no_other_operations):
    e = target_source
    original, command, queued, preview = e.target_source
    current = save_title(e, original, "A later saved Canvas; no generation or discard yet")
    assert current["version"] != command["canvas_image_node"]["canvas_version"]
    e.reopen()
    no_other_operations()
    observation = read_job(e)
    assert observation.status_code == 200, observation.text
    observation = observation.json()
    before = original_files(e)
    response = discard(e)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    result = response.json()
    assert set(result) == {"contract", "job", "target", "incarnation", "canvas_read", "automatic_actions",
        "local_result_discarded", "remote_stop_confirmed"}
    assert result["contract"] == "studio-image-node-job-discard/1"
    assert result["canvas_read"] is result["automatic_actions"] is result["remote_stop_confirmed"] is False
    assert result["local_result_discarded"] is True and set(result["job"]) == FIELDS
    assert result["target"] == command["canvas_image_node"]
    assert result["job"]["id"] == queued["id"] and result["job"]["request_digest"] == queued["request_digest"]
    assert result["job"]["cancellation_mode"] == "LOCAL_RESULT_DISCARD"
    assert result["job"]["remote_compute_may_continue"] is True
    assert_only_original_job_changed(e, before)
    e.reopen()
    after_before = original_files(e)
    after = read_job(e, pin(result["job"]))
    assert after.status_code == 200, after.text
    assert after.json()["job"] == result["job"]
    assert after.json()["canvas_read"] is False and original_files(e) == after_before
    capture = os.environ.get("CLOUD_CANVAS_NODE_DISCARD_CAPTURE_FILE")
    if capture:
        root = Path(__file__).resolve().parents[1]
        backend = ["app/creative/canvas_image_node_job_discard.py", "app/creative/canvas_image_node_job_observation.py",
            "app/creative/production_execution.py", "app/creative/production_execution_api.py",
            "app/creative/production_execution_models.py", "app/services/image_job_service.py", "app/services/studio_image_execution.py"]
        value = {"contract": "studio-node-job-discard-file-api/1", "baseline_commit": BASELINE,
            "implementation_sha256": {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in backend},
            "evidence_type": "REAL_ORIGINAL_FILE_API_QUEUED_LOCAL_DISCARD_ONLY", "project": e.nid, "scope": e.scope,
            "selected_job": queued, "observation": observation, "discard": result, "after": after.json()}
        raw = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        for forbidden in (str(e.rig.root), "formal-node-test-host", "formal-node-test-session", "X-Session-Token", "Bearer "):
            assert forbidden not in raw
        Path(capture).write_text(raw, encoding="utf-8")


@pytest.mark.parametrize("confirmed", [False, 1, "true", None, "MISSING"])
def test_explicit_true_confirmation_cannot_be_coerced(target_source, no_other_operations, confirmed):
    e = target_source
    body = pin(e.target_source[2])
    if confirmed != "MISSING": body["confirmed"] = confirmed
    before = original_files(e)
    no_other_operations()
    closed(discard(e, body), 422)
    assert original_files(e) == before


@pytest.mark.parametrize("fault", ["version", "digest"])
def test_stale_original_preconditions_never_cancel_a_different_snapshot(target_source, no_other_operations, fault):
    e = target_source
    body = {**pin(e.target_source[2]), "confirmed": True}
    body["expected_version" if fault == "version" else "expected_request_digest"] = 2 if fault == "version" else "0" * 64
    before = original_files(e)
    no_other_operations()
    closed(discard(e, body), 409)
    assert original_files(e) == before


@pytest.mark.parametrize("fault", ["target", "recipe"])
def test_original_request_digest_binds_source_even_if_same_version_read_is_tampered(target_source, no_other_operations, monkeypatch, fault):
    e = target_source
    original = ProductionExecutionService._row
    def tampered(owner, *args, **kwargs):
        row, context = original(owner, *args, **kwargs)
        row = deepcopy(row)
        context = row["context"]
        if fault == "target": context["command"]["canvas_image_node"]["node_id"] = "software-tampered-target"
        else: context["execution_recipe"]["defaults"]["steps"] += 1
        return row, context
    monkeypatch.setattr(ProductionExecutionService, "_row", tampered)
    before = original_files(e)
    no_other_operations()
    closed(discard(e), 409)
    assert original_files(e) == before


@pytest.mark.parametrize("field", ["execution_token", "publication_ready", "review_token"])
def test_inconsistent_queued_runtime_evidence_is_not_called_unexecuted(target_source, no_other_operations, monkeypatch, field):
    e = target_source
    original = ProductionExecutionService._row
    def inconsistent(owner, *args, **kwargs):
        row, context = original(owner, *args, **kwargs)
        row = deepcopy(row)
        row[field] = True if field == "publication_ready" else "software-runtime-marker"
        return row, row["context"]
    monkeypatch.setattr(ProductionExecutionService, "_row", inconsistent)
    before = original_files(e)
    no_other_operations()
    closed(discard(e), 409)
    assert original_files(e) == before


def test_same_version_raw_change_inside_original_mutation_cas_is_rejected_before_write(target_source, no_other_operations, monkeypatch):
    e = target_source
    original = ImageJobService._mutate
    injected = []
    def interleaved(owner, nid, branch, operation):
        def changed(rows):
            row = next(row for row in rows if row["id"] == e.target_source[2]["id"])
            row["error_code"] = "SOFTWARE_ATOMIC_ROW_CHANGE"
            injected.append(True)
            return operation(rows)
        return original(owner, nid, branch, changed)
    monkeypatch.setattr(ImageJobService, "_mutate", interleaved)
    before = original_files(e)
    no_other_operations()
    closed(discard(e), 409)
    assert injected == [True] and original_files(e) == before


def test_same_cas_request_cannot_cancel_twice_or_advance_an_already_cancelled_job(target_source, no_other_operations):
    e = target_source
    no_other_operations()
    first = discard(e)
    assert first.status_code == 200, first.text
    before = original_files(e)
    closed(discard(e), 409)
    assert original_files(e) == before and original_jobs(e)[0]["version"] == e.target_source[2]["version"] + 1


@pytest.mark.parametrize("denied_permission", ["domain.read", "domain.write"])
def test_read_and_write_are_separate_original_authority_checks(target_source, no_other_operations, monkeypatch, denied_permission):
    e = target_source
    original = legacy_api._workbench_authorize
    checked = []
    def deny(nid, token, branch, permission):
        result = original(nid, token, branch, permission)
        checked.append(permission)
        if permission == denied_permission: raise HTTPException(403, {"code": "SOFTWARE_PERMISSION_DENIAL"})
        return result
    monkeypatch.setattr(legacy_api, "_workbench_authorize", deny)
    before = original_files(e)
    no_other_operations()
    closed(discard(e), 403)
    assert denied_permission in checked and original_files(e) == before


def test_revoked_original_host_cannot_discard(target_source, no_other_operations):
    e = target_source
    e.rig.sessions.revoke(e.headers["X-Session-Token"])
    before = original_files(e)
    no_other_operations()
    response = discard(e)
    assert response.status_code in {401, 403}, response.text
    closed(response, response.status_code)
    assert original_files(e) == before


def test_missing_identity_is_not_created_by_the_discard_request(target_source, no_other_operations):
    e = target_source
    marker = e.rig.root / "novels" / e.nid / "creative_project_v2.json"
    raw = marker.read_bytes()
    kept = marker.with_suffix(".retained-for-discard-test")
    marker.rename(kept)
    before = original_files(e)
    no_other_operations()
    response = discard(e)
    assert response.status_code in {404, 422}, response.text
    closed(response, response.status_code)
    assert not marker.exists() and kept.read_bytes() == raw and original_files(e) == before


def test_failed_ack_after_real_cancel_is_not_rollback_and_original_job_read_recovers_state(target_source, no_other_operations, monkeypatch):
    from app.creative import canvas_image_node_job_discard as module
    e = target_source
    original = module.project_public_job
    calls = []
    def fail_after_commit(public, command):
        calls.append(public["status"])
        if len(calls) == 2: raise ValueError("SOFTWARE_ACK_VALIDATION_FAILURE")
        return original(public, command)
    monkeypatch.setattr(module, "project_public_job", fail_after_commit)
    before = original_files(e)
    no_other_operations()
    closed(discard(e), 409)
    assert calls == ["QUEUED", "CANCELLED"]
    row = assert_only_original_job_changed(e, before)
    # The owner supplies the exact new pin here; this test does not claim a
    # browser can guess a changed version from a failed write acknowledgement.
    e.reopen()
    observed = read_job(e, pin(row))
    assert observed.status_code == 200, observed.text
    assert observed.json()["job"]["status"] == "CANCELLED"


def test_closed_body_does_not_accept_client_snapshot_or_oversized_data(target_source, no_other_operations):
    e = target_source
    before = original_files(e)
    no_other_operations()
    closed(discard(e, {**pin(e.target_source[2]), "confirmed": True, "expected_snapshot": {}}), 422)
    url = e.base + f"/production/jobs/image/{e.target_source[2]['id']}/node-discard"
    response = e.client.post(url, headers={**e.headers, "Content-Type": "application/json"}, content=b" " * 4097)
    closed(response, 413)
    assert original_files(e) == before
