"""Wire checks against provisional friendlier-default frontend 34eb95c7.

Real mounted File/HTTP routes and original owners, with no provider execution.
User rejected the earlier 048c5ebb target; its evidence remains historical.
34eb95c7 contains the default tasks drawer and is a provisional target, not
user-confirmed acceptance. Its Production client blob is identical to 048c5ebb.
This is not browser acceptance. The strict xfail records a real, unresolved
frontend command-validator incompatibility; it must not be counted as a pass.
"""
from copy import deepcopy
import re

import pytest

from test_studio_asset_query import rig
from test_cloud_formal_canvas_node import formal_node, create_target, command, queue
from test_cloud_canvas_node_resume import resume_source
from test_studio_production_query import queued, get
from test_studio_workspace_identity_history_contract import (
    audio_history, checked, create_timeline, edit_timeline, restore_body,
)


pytestmark = pytest.mark.file_backend_only
FRONTEND_SHA = "34eb95c7f247e90168b27f96e33e6feacd80fc8d"
FRONTEND_TARGET_STATUS = "PROVISIONAL_DEFAULT_UW_PORT"
SUPERSEDED_FRONTEND_SHA = "048c5ebb3cedb138dcef15bbfc5e9f4be8c92760"
# studioProductionClient.ts:426, job() strict command-key validator at that SHA.
# Keep this snapshot distinct from the newer backend branch's frontend sources.
FRONTEND_COMMAND_KEYS = frozenset((
    "operation_id", "request_id", "provider_id", "model_id", "prompt", "parameters",
    "source_snapshots", "allow_cloud", "license_note", "image_source",
    "image_references", "mask_source", "video_reference", "video_frames",
    "storyboard_shot", "storyboard_speech", "audio_profile", "image_layers", "canvas_return",
))


def assert_paged_wire(body, limit, offset):
    assert set(body) == {"items", "total", "limit", "offset", "has_more", "product_acceptance"}
    assert body["limit"] == limit and body["offset"] == offset
    assert type(body["total"]) is int and body["total"] >= 0
    assert body["has_more"] is (offset + limit < body["total"])
    assert len(body["items"]) <= limit
    if offset >= body["total"]:
        assert body["items"] == []
    assert body["product_acceptance"] == "LOCAL_REQUIRED"


def test_overview_identity_matches_frontend_observation_after_recreation(rig):
    url = f"/api/projects/{rig.nid}/studio"
    first = checked(rig.client.get(url))["project"]
    incarnation = first["incarnation"]
    # projectIncarnation.ts validIncarnation / incarnationFromOverview contract.
    assert first["id"] == rig.nid
    assert 0 < len(incarnation) <= 200 and incarnation.strip() == incarnation
    assert re.fullmatch(r"[\x21-\x7e][\x20-\x7e]*", incarnation)
    assert checked(rig.client.get(url))["project"]["incarnation"] == incarnation
    rig.novels.delete(rig.nid)
    assert rig.client.get(url).status_code == 404
    rig.project(rig.nid)
    recreated = checked(rig.client.get(url))["project"]
    assert recreated["id"] == first["id"] and recreated["incarnation"] != incarnation


@pytest.mark.parametrize("offset", [0, 1, 50, 1_000_000])
def test_image_list_page_wire_is_compatible_and_read_only(resume_source, offset):
    e = resume_source
    canvas = create_target(e)
    request = command(e, canvas, request_id="frontend-image-page")
    # Ordinary media callers do not send the separate formal-node capsule.
    request.pop("canvas_image_node")
    image, _preview = queue(e, request)
    response = get(e, {"owner": "image", "operation_id": "m5.image.t2i", "limit": 1, "offset": offset})
    body = checked(response)
    assert_paged_wire(body, 1, offset)
    assert body["total"] == 1
    assert [row["id"] for row in body["items"]] == ([image["id"]] if offset == 0 else [])
    if body["items"]:
        row = body["items"][0]
        assert row["contract"] == "studio-production-job/1"
        assert row["owner"] == "image" and row["status"] == "QUEUED"
        assert row["automatic_replay"] is False and row["output_candidate"] is None
        assert set(row["command"]) <= FRONTEND_COMMAND_KEYS
    assert response.headers["cache-control"] == "no-store"
    assert len(checked(get(e))["items"]) == 1


def test_production_query_failure_is_structured_without_private_input(queued):
    e = queued
    response = get(e, {"owner": "C:/private/invalid-owner", "limit": 1, "offset": 0})
    body = checked(response, 422)
    assert body["detail"] == {"code": "EXPERIMENTAL_INVALID", "message": "STUDIO_PRODUCTION_QUERY_INVALID"}
    assert "private" not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert len(checked(get(e))["items"]) == 5


def test_production_query_feature_off_does_not_return_fake_empty_success(queued, monkeypatch):
    e = queued
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "")
    response = get(e, {"owner": "audio", "limit": 1, "offset": 0})
    assert response.status_code == 404
    assert "items" not in response.json()


def test_canvas_restore_wire_matches_frontend_cas_and_retains_history(formal_node):
    e = formal_node
    original = create_target(e)
    url = e.base + "/canvas-views/" + original["id"]
    definition = deepcopy(original["definition"])
    definition["title"] = "Explicit frontend metadata save"
    current = checked(e.client.put(url, headers=e.headers,
        json={"expected_version": 1, "definition": definition}))
    history = checked(e.client.get(url + "/history", headers=e.headers))
    assert set(history) == {"project_id", "scope", "id", "incarnation", "current_version",
        "current_definition_digest", "items", "restore_policy", "execution_authority", "binary_content_verified"}
    assert history["restore_policy"] == "CURRENT_METADATA_ONLY"
    assert history["execution_authority"] is False and history["binary_content_verified"] is False
    assert [item["version"] for item in history["items"]] == [1, 2]
    assert history["items"][0]["can_restore"] is True
    body = {"expected_version": 2, "expected_definition_digest": current["definition_digest"],
        "expected_incarnation": history["incarnation"], "restore_version": 1,
        "restore_definition_digest": original["definition_digest"]}
    restored = checked(e.client.post(url + "/restore", headers=e.headers, json=body))
    assert restored["version"] == 3 and restored["definition"] == original["definition"]
    stale = e.client.post(url + "/restore", headers=e.headers, json=body)
    assert stale.status_code == 409
    assert checked(e.client.get(url, headers=e.headers)) == restored
    assert [item["version"] for item in checked(e.client.get(url + "/history", headers=e.headers))["items"]] == [1, 2, 3]


def test_audio_raw_timeline_restore_does_not_restore_asset_bytes(audio_history):
    e = audio_history
    original = create_timeline(e)
    current = edit_timeline(e, original)
    url = e.base + "/production/timelines/" + original["id"]
    history = checked(e.client.get(url + "/history", headers=e.headers))
    assert history["timeline_id"] == original["id"] and history["current_version"] == 2
    assert history["items"] == [original]
    restored = checked(e.client.post(url + "/restore", headers=e.headers, json=restore_body(current, original)))
    assert restored["version"] == 3 and restored["timeline"] == original["timeline"]
    with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
        assert e.rig.assets.get(e.asset["id"])["version"] == 1
        assert e.rig.assets.content(e.asset["id"]) == e.content
    assert checked(e.client.get(e.base + "/production/jobs", headers=e.headers))["items"] == []


def formal_image_job_wire(e):
    canvas = create_target(e)
    saved, _preview = queue(e, command(e, canvas, request_id="frontend-formal-node-wire"))
    response = e.client.get(e.base + "/production/jobs/image/" + saved["id"], headers=e.headers)
    return checked(response)


def test_original_backend_retains_formal_node_provenance(resume_source):
    e = resume_source
    row = formal_image_job_wire(e)
    origin = row["command"]["canvas_image_node"]
    assert origin["project_id"] == e.nid
    assert origin["incarnation"] == e.workspace.store.incarnation(e.nid)
    assert checked(get(e))["items"] == [row]
    assert row["status"] == "QUEUED" and row["output_candidate"] is None


@pytest.mark.xfail(strict=True, reason="PROVISIONAL_FRONTEND_BLOCKED: 34eb95c7 job command allowlist rejects canvas_image_node provenance")
def test_selected_frontend_admits_formal_image_node_job_command(resume_source):
    e = resume_source
    row = formal_image_job_wire(e)
    assert "canvas_image_node" in row["command"]  # Original authority must remain intact.
    unknown = set(row["command"]) - FRONTEND_COMMAND_KEYS
    assert not unknown, f"Frontend {FRONTEND_SHA} rejects original backend command fields: {sorted(unknown)}"
