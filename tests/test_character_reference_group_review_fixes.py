"""Independent-review repair regressions for World three-view reference groups."""
import base64
from copy import deepcopy
import os
from uuid import uuid4

import pytest

from app.experimental.planning import collection, digest
from app.experimental.store import ExperimentalStore
from app.experimental.world import WorldService
from test_r3_mounted_contracts import checked, mounted, prefix
from test_v2_independent_workspace_api import client
from test_v2_discovered_image_production_api import image_client, action, execute
from test_v2_independent_workspace import png_bytes

def setup_visual(e, monkeypatch):
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", os.environ.get("EXPERIMENTAL_FEATURES", "") + ",world_character_engines_v2")
    base = e.prefix + f"/novels/{e.nid}/experimental/world"
    visual = checked(e.client.post(base + "/records", headers=e.headers, json={
        "kind": "CHARACTER_VISUAL", "title": "Repair synthetic visual",
        "data": {"character_id": "alice", "appearance": "synthetic hair"}}), 201)
    visual = checked(e.client.post(base + f"/records/{visual['id']}/approve", headers=e.headers,
        json={"expected_version": visual["version"]}))
    pin = e.experimental.world_service.character_visual_pin(e.nid, {"mode": "local", "novel_id": e.nid}, visual["id"])
    return base, visual, pin


def make_job(e, index, prompt):
    command = deepcopy(e.command)
    command["request_id"] = "repair-original-view-" + str(index)
    command["prompt"] = prompt
    preview = e.client.post(e.base + "/preview", headers=e.headers, json=command)
    assert preview.status_code == 200, preview.text
    preview = checked(preview)
    queued = checked(e.client.post(e.base + "/jobs", headers=e.headers,
        json={"command": command, "reviewed_preview_digest": preview["preview_digest"]}), 201)
    completed = execute(e, queued)
    assert completed.status_code == 200, completed.text
    completed = checked(completed)
    approved = checked(e.client.post(e.base + "/jobs/image/" + queued["id"] + "/review", headers=e.headers,
        json={**action(completed), "reviewed_output_digest": completed["output_candidate"]["digest"]}))
    formal = checked(e.client.get(e.studio_base + "/assets/" + completed["output_candidate"]["id"], headers=e.headers))
    return approved, formal


def approved_views(e, prompts=("FRONT synthetic source", "SIDE synthetic source", "BACK synthetic source")):
    approved = []
    for index, prompt in enumerate(prompts):
        job, formal = make_job(e, index, prompt)
        command = job["command"]
        approved.append((job, formal, command))
    views = []
    for index, role in enumerate(("FRONT", "SIDE", "BACK")):
        job, formal, command = approved[index]
        views.append({"view": role, "asset_id": formal["id"], "asset_version": formal["version"],
            "asset_sha256": formal["sha256"], "request_id": job["request_id"],
            "provider_id": command["provider_id"], "model_id": command["model_id"],
            "prompt": command["prompt"],
            "parameters": {key: value for key, value in command["parameters"].items()},
            "reference_asset_ids": [source["id"] for source in job["sources"] if source.get("kind") == "ASSET"]})
    return views, approved


def group_body(e, base, visual, pin, views):
    return {"character_id": "alice", "visual_record_id": visual["id"],
        "visual_record_version": visual["version"], "visual_record_digest": pin["digest"],
        "title": "Repair three-view group", "views": views, "consistency_confirmed": True}


def test_valid_three_jobs_review_save_reopen_approve(image_client, monkeypatch):
    e = image_client; base, visual, pin = setup_visual(e, monkeypatch)
    views, approved = approved_views(e)
    body = group_body(e, base, visual, pin, views)
    created = checked(e.client.post(base + "/character-reference-groups", headers=e.headers, json=body), 201)
    assert created["status"] == "REVIEW" and created["data"]["asset_verification"] == "SERVER_VERIFIED_FORMAL_ASSET_SNAPSHOTS"
    assert [view["asset_version"] for view in created["data"]["views"]] == [2, 2, 2]
    assert [view["request_id"] for view in created["data"]["views"]] == [job["request_id"] for job, _, _ in approved]
    restarted = WorldService(ExperimentalStore(e.root, e.backend, e.url), e.novels, e.chapters)
    reopened = restarted.record(e.nid, {"mode": "local", "novel_id": e.nid}, created["id"])
    assert reopened["status"] == "REVIEW"
    approved_group = checked(e.client.post(base + f"/records/{created['id']}/approve", headers=e.headers,
        json={"expected_version": created["version"]}))
    assert approved_group["status"] == "APPROVED" and approved_group["canon_state"] == "CANON"
    assert any(row["source_record_id"] == created["id"] for row in checked(e.client.get(base + "/canon", headers=e.headers))["items"])


def test_generic_world_create_and_edit_cannot_forge_verified_marker(image_client, monkeypatch):
    e = image_client; base, visual, pin = setup_visual(e, monkeypatch)
    views, _ = approved_views(e)
    forged = {"kind": "CHARACTER_REFERENCE_GROUP", "title": "Forged group", "data": {
        **group_body(e, base, visual, pin, [
            {**view, "asset_id": f"missing-{index}"} for index, view in enumerate(views)
        ]),
        "asset_verification": "SERVER_VERIFIED_FORMAL_ASSET_SNAPSHOTS"}}
    response = e.client.post(base + "/records", headers=e.headers, json=forged)
    assert response.status_code in (403, 404, 409, 422), response.text
    assert checked(e.client.get(base + "/records?kind=CHARACTER_REFERENCE_GROUP", headers=e.headers))["items"] == []

    # A valid group can be created only from the real reviewed jobs, then a
    # generic PUT cannot replace an asset while retaining a trusted marker.
    created = checked(e.client.post(base + "/character-reference-groups", headers=e.headers,
        json=group_body(e, base, visual, pin, views)), 201)
    changed = deepcopy(created["data"])
    changed["views"][0]["asset_id"] = "replacement-missing-asset"
    response = e.client.put(base + f"/records/{created['id']}", headers=e.headers, json={
        "kind": created["kind"], "title": created["title"], "chapter_id": created["chapter_id"],
        "event_order": created["event_order"], "data": changed, "expected_version": created["version"]})
    assert response.status_code in (403, 404, 409, 422), response.text
    unchanged = checked(e.client.get(base + f"/records/{created['id']}", headers=e.headers))
    assert unchanged["data"]["views"] == created["data"]["views"]
    assert unchanged["version"] == created["version"]


def test_approval_rechecks_formal_asset_content_after_creation(image_client, monkeypatch):
    e = image_client; base, visual, pin = setup_visual(e, monkeypatch)
    views, _ = approved_views(e)
    created = checked(e.client.post(base + "/character-reference-groups", headers=e.headers,
        json=group_body(e, base, visual, pin, views)), 201)
    with e.studio._asset_scope(e.nid, {"mode": "local", "novel_id": e.nid}):
        path = e.studio.assets._bin_path(views[0]["asset_id"])
        original = path.read_bytes()
    try:
        path.write_bytes(bytes([original[0] ^ 1]) + original[1:])
        response = e.client.post(base + f"/records/{created['id']}/approve", headers=e.headers,
            json={"expected_version": created["version"]})
        assert response.status_code in (409, 422), response.text
        current = checked(e.client.get(base + f"/records/{created['id']}", headers=e.headers))
        assert current["status"] == "REVIEW"
        assert all(row.get("source_record_id") != created["id"] for row in checked(e.client.get(base + "/canon", headers=e.headers))["items"])
    finally:
        path.write_bytes(original)


def test_dedicated_route_rejects_unproven_mixed_and_reused_requests(image_client, monkeypatch):
    e = image_client; base, visual, pin = setup_visual(e, monkeypatch)
    views, approved = approved_views(e)
    # Unrelated request id: no original job exists.
    unproven = deepcopy(views)
    unproven[0]["request_id"] = "never-created-request"
    response = e.client.post(base + "/character-reference-groups", headers=e.headers,
        json=group_body(e, base, visual, pin, unproven))
    assert response.status_code in (403, 404, 409, 422), response.text
    # Asset from one real request but a different real request id.
    mismatched = deepcopy(views)
    mismatched[0]["request_id"] = approved[1][0]["request_id"]
    response = e.client.post(base + "/character-reference-groups", headers=e.headers,
        json=group_body(e, base, visual, pin, mismatched))
    assert response.status_code in (403, 404, 409, 422), response.text
    # Same request reused for two roles cannot become two views.
    reused = deepcopy(views)
    reused[1]["request_id"] = reused[0]["request_id"]
    response = e.client.post(base + "/character-reference-groups", headers=e.headers,
        json=group_body(e, base, visual, pin, reused))
    assert response.status_code in (403, 404, 409, 422), response.text
    # Manual assets with no generation job remain unproven.
    manual = []
    for index, role in enumerate(("FRONT", "SIDE", "BACK")):
        asset = checked(e.client.post(e.studio_base + "/assets", headers=e.headers, json={
            "filename": f"manual-repair-{index}.png", "kind": "image",
            "content_base64": base64.b64encode(png_bytes(bytes([30 + index, 40 + index, 50 + index]))).decode(),
            "idempotency_key": f"manual-repair-{index}"}), 201)
        manual.append({"view": role, "asset_id": asset["id"], "asset_version": asset["version"],
            "asset_sha256": asset["sha256"], "request_id": f"manual-unproven-{index}",
            "provider_id": "claimed", "model_id": "claimed", "prompt": role, "parameters": {},
            "reference_asset_ids": []})
    response = e.client.post(base + "/character-reference-groups", headers=e.headers,
        json=group_body(e, base, visual, pin, manual))
    assert response.status_code in (403, 404, 409, 422), response.text
    assert checked(e.client.get(base + "/records?kind=CHARACTER_REFERENCE_GROUP", headers=e.headers))["items"] == []


def test_legacy_generic_world_paths_verify_instead_of_trusting_markers(image_client, monkeypatch):
    e = image_client; base, visual, pin = setup_visual(e, monkeypatch)
    views, approved = approved_views(e)
    generic_data = group_body(e, base, visual, pin, views)
    generic_data.pop("title")
    generic_data["asset_verification"] = "UNVERIFIED"
    body = {"kind": "CHARACTER_REFERENCE_GROUP", "title": "Generic verified group", "data": generic_data}
    created = checked(e.client.post(base + "/records", headers=e.headers, json=body), 201)
    assert created["data"]["asset_verification"] == "SERVER_VERIFIED_FORMAL_ASSET_SNAPSHOTS"
    # Generic PUT can update one reviewed view only through the same verifier,
    # preserving the other two views and never overwriting an approved record.
    extra_job, extra_formal = make_job(e, 3, "SIDE replacement synthetic source")
    extra_view = {"view": "SIDE", "asset_id": extra_formal["id"], "asset_version": extra_formal["version"],
        "asset_sha256": extra_formal["sha256"], "request_id": extra_job["request_id"],
        "provider_id": extra_job["command"]["provider_id"], "model_id": extra_job["command"]["model_id"],
        "prompt": extra_job["command"]["prompt"], "parameters": extra_job["command"]["parameters"],
        "reference_asset_ids": [source["id"] for source in extra_job["sources"] if source.get("kind") == "ASSET"]}
    changed = deepcopy(created["data"]); changed["views"][1] = extra_view
    edited = checked(e.client.put(base + f"/records/{created['id']}", headers=e.headers, json={
        "kind": created["kind"], "title": created["title"], "chapter_id": created["chapter_id"],
        "event_order": created["event_order"], "data": changed, "expected_version": created["version"]}))
    assert edited["data"]["views"][0] == created["data"]["views"][0]
    assert edited["data"]["views"][2] == created["data"]["views"][2]
    assert edited["data"]["views"][1]["request_id"] == extra_job["request_id"]
    approved_group = checked(e.client.post(base + f"/records/{created['id']}/approve", headers=e.headers,
        json={"expected_version": edited["version"]}))
    assert approved_group["status"] == "APPROVED"


def test_candidate_version_is_not_accepted_as_the_formal_snapshot(image_client, monkeypatch):
    e = image_client; base, visual, pin = setup_visual(e, monkeypatch)
    views, _ = approved_views(e)
    candidate = deepcopy(views)
    candidate[0]["asset_version"] = 1
    response = e.client.post(base + "/character-reference-groups", headers=e.headers,
        json=group_body(e, base, visual, pin, candidate))
    assert response.status_code in (409, 422), response.text
    assert checked(e.client.get(base + "/records?kind=CHARACTER_REFERENCE_GROUP", headers=e.headers))["items"] == []


def test_pin_conflict_is_a_sanitized_client_error(image_client, monkeypatch):
    e = image_client; base, visual, pin = setup_visual(e, monkeypatch)
    views, _ = approved_views(e)
    body = group_body(e, base, visual, pin, views)
    body["visual_record_version"] += 1
    try:
        response = e.client.post(base + "/character-reference-groups", headers=e.headers, json=body)
    except ValueError as exc:
        pytest.fail("raw server ValueError instead of sanitized 409/422: " + str(exc))
    assert response.status_code in (409, 422), response.text
    assert "CHARACTER_REFERENCE_GROUP_VISUAL_PIN_CHANGED" in response.text
    assert checked(e.client.get(base + "/records?kind=CHARACTER_REFERENCE_GROUP", headers=e.headers))["items"] == []

def test_approval_is_atomic_against_asset_change_after_verifier_returns(image_client, monkeypatch):
    """The commit guard must hold the original asset lease through the Canon write."""
    e = image_client; base, visual, pin = setup_visual(e, monkeypatch)
    views, approved = approved_views(e)
    group = checked(e.client.post(base + "/character-reference-groups", headers=e.headers,
        json=group_body(e, base, visual, pin, views)), 201)
    before = checked(e.client.get(base + "/canon", headers=e.headers))["items"]
    service = e.experimental.world_service
    original_verify = service.reference_group_verifier
    events = []

    def interleaved(nid, scope, actor, data):
        result = original_verify(nid, scope, actor, data)
        # Deterministic legal owner mutation at the verified-read / Canon-write
        # boundary. The verifier itself is not forged.
        with e.studio._asset_scope(e.nid, {"mode": "local", "novel_id": e.nid}):
            changed = e.studio.assets.update_metadata(views[0]["asset_id"],
                {"provider_id": "independent-atomic-interleave"}, expected_version=views[0]["asset_version"])
        events.append({"verifier_finished": True, "asset_new_version": changed["version"]})
        return result

    monkeypatch.setattr(service, "reference_group_verifier", interleaved)
    response = e.client.post(base + f"/records/{group['id']}/approve", headers=e.headers,
        json={"expected_version": group["version"]})
    current = checked(e.client.get(base + f"/records/{group['id']}", headers=e.headers))
    after = checked(e.client.get(base + "/canon", headers=e.headers))["items"]
    assert events == [{"verifier_finished": True, "asset_new_version": 3}]
    assert response.status_code in (409, 422), response.text
    assert current["status"] == "REVIEW" and current["canon_state"] == "CANDIDATE"
    assert after == before
    assert not any(row.get("source_record_id") == group["id"] for row in after)
