"""Pinned original CanvasView records, without editor, content or generation.

The manual reference is an original synthetic metadata seed, not a generated
or approved image. No image validity or formal adoption is established here.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.creative.production_execution import ProductionExecutionService
from test_cloud_canvas_node_target_observation import (
    target_source, formal_node, rig, observe, forbid_observation_calls, original_files, original_jobs)


pytestmark = pytest.mark.file_backend_only
BASELINE = "7736423c9c261e2028d0b675935ca7b9b2482f7e"


def request_pin(observation):
    return {"expected_version": observation["job"]["version"],
        "expected_request_digest": observation["job"]["request_digest"],
        "expected_incarnation": observation["incarnation"],
        "expected_canvas_version": observation["canvas"]["version"],
        "expected_canvas_digest": observation["canvas"]["definition_digest"]}


def read_view(e, body, *, headers=None, jid=None):
    job = e.target_source[2]
    url = e.base + f"/production/jobs/image/{jid or job['id']}/target-view"
    return e.client.post(url, headers=e.headers if headers is None else headers, json=body)


def closed(response, status):
    assert response.status_code == status, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    problem = response.json()
    assert set(problem) == {"detail", "code", "message", "details", "request_id"}
    assert problem["detail"] == problem["details"] == {"code": problem["code"]}
    assert problem["message"] == problem["code"]
    assert problem["code"].startswith("STUDIO_IMAGE_NODE_TARGET_VIEW_")
    assert problem["request_id"] == response.headers["x-request-id"]


def manual_record(e):
    original = e.target_source[0]
    asset = e.rig.seed("Synthetic manual metadata reference.png")
    definition = deepcopy(original["definition"])
    definition["title"] = "A saved manual reference, not generated output"
    definition["cards"] = [{"id": "manual-reference-card", "position": {"x": 160, "y": 96},
        "asset": {"asset_id": asset["id"], "version": asset["version"], "digest": asset["sha256"], "kind": "image"}}]
    response = e.client.put(e.base + f"/canvas-views/{original['id']}", headers=e.headers,
        json={"expected_version": original["version"], "definition": definition})
    assert response.status_code == 200, response.text
    record = response.json()
    assert record["reference_states"] == [{"card_id": "manual-reference-card", "state": "CURRENT_METADATA",
        "filename": asset["filename"]}]
    return record


@pytest.mark.parametrize("manual", [False, True])
def test_explicit_pinned_record_is_original_cold_file_projection_not_a_second_get(target_source, forbid_observation_calls, monkeypatch, manual):
    e = target_source
    expected = manual_record(e) if manual else e.target_source[0]
    observation = observe(e)
    assert observation.status_code == 200, observation.text
    observation = observation.json()
    assert observation["comparison"] == ("CURRENT_CHANGED" if manual else "CURRENT_MATCH")
    old = e.graph, e.production, e.workspace.assets
    e.reopen()
    assert all(a is not b for a, b in zip(old, (e.graph, e.production, e.workspace.assets)))
    get = Mock(wraps=e.graph.canvas_views.get)
    monkeypatch.setattr(e.graph.canvas_views, "get", get)
    before = original_files(e)
    forbid_observation_calls()
    response = read_view(e, request_pin(observation))
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    value = response.json()
    assert set(value) == {"contract", "job", "target", "incarnation", "canvas", "automatic_actions"}
    assert value["contract"] == "studio-image-node-target-view/1" and value["automatic_actions"] is False
    assert value["job"] == observation["job"] == e.target_source[2]
    assert value["target"] == observation["target"] and value["incarnation"] == observation["incarnation"]
    assert value["canvas"] == expected and value["canvas"]["binary_content_verified"] is False
    assert value["canvas"]["execution_authority"] is False
    assert "image_node_origin" not in value["canvas"]["definition"]
    assert all(card["id"] != value["target"]["node_id"] for card in expected["definition"]["cards"])
    assert get.call_count == 1
    assert original_files(e) == before and len(original_jobs(e)) == 1
    capture = os.environ.get("CLOUD_CANVAS_NODE_TARGET_VIEW_CAPTURE_FILE")
    if manual and capture:
        root = Path(__file__).resolve().parents[1]
        paths = ["app/creative/canvas_image_node_target_observation.py", "app/creative/production_execution.py",
            "app/creative/production_execution_api.py", "app/creative/production_execution_models.py"]
        fixture = {"contract": "studio-node-target-view-file-api/1", "baseline_commit": BASELINE,
            "implementation_sha256": {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in paths},
            "evidence_type": "REAL_ORIGINAL_FILE_API_MANUAL_REFERENCE_METADATA_ONLY", "project": e.nid, "scope": e.scope,
            "queued_job": e.target_source[2], "observation": observation, "view": value}
        raw = json.dumps(fixture, ensure_ascii=False, indent=2) + "\n"
        for forbidden in (str(e.rig.root), "formal-node-test-host", "formal-node-test-session", "X-Session-Token", "Bearer "):
            assert forbidden not in raw
        Path(capture).write_text(raw, encoding="utf-8")


@pytest.mark.parametrize("field", ["incarnation", "canvas-version", "canvas-digest", "job-version", "job-digest"])
def test_stale_pins_are_not_replaced_with_latest_record(target_source, forbid_observation_calls, field):
    e = target_source
    body = request_pin(observe(e).json())
    if field == "incarnation": body["expected_incarnation"] = "file:00000000-0000-4000-8000-000000000000"
    elif field == "canvas-version": body["expected_canvas_version"] += 1
    elif field == "canvas-digest": body["expected_canvas_digest"] = "0" * 64
    elif field == "job-version": body["expected_version"] += 1
    else: body["expected_request_digest"] = "0" * 64
    before = original_files(e)
    forbid_observation_calls()
    closed(read_view(e, body), 409)
    assert original_files(e) == before


def test_current_canvas_edit_after_observation_refuses_old_view_pin(target_source, forbid_observation_calls):
    e = target_source
    body = request_pin(observe(e).json())
    manual_record(e)
    before = original_files(e)
    forbid_observation_calls()
    closed(read_view(e, body), 409)
    assert original_files(e) == before


def test_missing_identity_stays_missing_and_preserved_in_fixture(target_source, forbid_observation_calls):
    e = target_source
    body = request_pin(observe(e).json())
    marker = e.rig.root / "novels" / e.nid / "creative_project_v2.json"
    content = marker.read_bytes()
    preserved = marker.with_suffix(".retained-for-target-view-test")
    marker.rename(preserved)
    before = original_files(e)
    forbid_observation_calls()
    response = read_view(e, body)
    assert response.status_code in {404, 422}, response.text
    closed(response, response.status_code)
    assert not marker.exists() and preserved.read_bytes() == content and original_files(e) == before


def test_read_still_needs_original_production_host_authority(target_source, forbid_observation_calls):
    e = target_source
    body = request_pin(observe(e).json())
    e.rig.sessions.revoke(e.headers["X-Session-Token"])
    before = original_files(e)
    forbid_observation_calls()
    response = read_view(e, body)
    assert response.status_code in {401, 403}, response.text
    closed(response, response.status_code)
    assert e.target_source[2]["id"] not in response.text and original_files(e) == before


@pytest.mark.parametrize("fault", ["canvas-id", "boolean-version", "request-limit", "response-limit"])
def test_new_record_route_has_closed_independent_limits(target_source, forbid_observation_calls, monkeypatch, fault):
    e = target_source
    body = request_pin(observe(e).json())
    before = original_files(e)
    forbid_observation_calls()
    if fault == "canvas-id": response = read_view(e, {**body, "canvas_id": e.target_source[0]["id"]}); status = 422
    elif fault == "boolean-version": response = read_view(e, {**body, "expected_canvas_version": True}); status = 422
    elif fault == "request-limit":
        response = e.client.post(e.observation_url.replace("target-observation", "target-view"),
            headers={**e.headers, "Content-Type": "application/json"}, content='{"padding":"'+'x'*4100+'"}'); status = 413
    else:
        # A deterministic oversized response projection, not an actual huge
        # persisted Canvas or any generated media/content.
        monkeypatch.setattr(ProductionExecutionService, "view_image_node_target", lambda *_a, **_k: {"padding": "x"*(8*1024*1024)})
        response = read_view(e, body); status = 413
    closed(response, status)
    assert original_files(e) == before
