"""Character three-view reference asset group on the existing World owner.

Service-level tests use the real file store; the mounted test proves the group
save route verifies snapshots against the original Asset owner. No model runs.
"""
import base64
from contextlib import nullcontext
from copy import deepcopy
from uuid import uuid4

import pytest

from app.experimental.common import StaleSourceError
from app.experimental.planning import collection, digest
from app.experimental.world import WorldService
from app.experimental.store import ExperimentalStore
from test_r3_mounted_contracts import checked, mounted, prefix
from test_r3_planning import planning_env
from test_r3_world import world_env, record, approve
from test_v2_independent_workspace import png_bytes
from test_v2_independent_workspace_api import client
from test_v2_discovered_image_production_api import image_client


def install_service_verifier(e):
    # Isolated WorldService tests exercise record/review semantics; the real
    # production verifier is covered by the mounted review-fix suite.
    e.world.reference_group_verifier = lambda nid, scope, actor, data: {
        **data, "asset_verification": "SERVER_VERIFIED_FORMAL_ASSET_SNAPSHOTS"}
    # Isolated service tests do not have the HTTP composition's asset owner.
    # The mounted suites exercise the real atomic commit guard.
    e.world.reference_group_commit_guard = lambda nid, scope, actor, data: nullcontext()


def raw(e, rid):
    state = e.store.read(e.nid, e.scope)
    return collection(state, WorldService.RECORDS)[rid]


def visual_identity(e, visual):
    row = raw(e, visual["id"])
    return row["version"], digest({key: value for key, value in row.items() if key != "history"})


def view(index, **overrides):
    value = {"view": ("FRONT", "SIDE", "BACK")[index], "asset_id": "asset-" + str(index + 1),
             "asset_version": 2, "asset_sha256": ("abcdef0123456789" * 4)[:64],
             "request_id": "turnaround-view-" + str(index + 1), "provider_id": "image-provider",
             "model_id": "image-model", "prompt": "view " + str(index + 1),
             "parameters": {"width": 1024, "height": 1024, "seed": index + 1},
             "reference_asset_ids": ["reference-a"]}
    value.update(overrides)
    return value


def group_data(e, visual, views=None, **overrides):
    version, sha = visual_identity(e, visual)
    data = {"character_id": "alice", "visual_record_id": visual["id"],
            "visual_record_version": version, "visual_record_digest": sha,
            "views": views if views is not None else [view(0), view(1), view(2)],
            "consistency_confirmed": True, "asset_verification": "UNVERIFIED"}
    data.update(overrides)
    return data


def create_group(e, visual, **overrides):
    return e.world.create_record(e.nid, e.scope, "writer", {
        "kind": "CHARACTER_REFERENCE_GROUP", "title": "Alice turnaround",
        "data": group_data(e, visual, **overrides)})


def test_three_distinct_views_are_saved_only_after_user_review_and_reopen(world_env):
    e = world_env
    install_service_verifier(e)
    visual = approve(e, record(e, "CHARACTER_VISUAL", {
        "character_id": "alice", "appearance": "short black hair", "clothing": "blue coat",
        "reference_asset_ids": ["reference-a"]}))
    candidate = create_group(e, visual)
    assert candidate["status"] == "REVIEW" and candidate["canon_state"] == "CANDIDATE"
    assert [row["view"] for row in candidate["data"]["views"]] == ["FRONT", "SIDE", "BACK"]
    assert candidate["data"]["asset_verification"] == "SERVER_VERIFIED_FORMAL_ASSET_SNAPSHOTS"
    assert all(row.get("source_record_id") != candidate["id"] for row in e.world.canon(e.nid, e.scope))
    approved = approve(e, candidate)
    assert approved["status"] == "APPROVED" and approved["canon_state"] == "CANON"
    assert approved["data"]["visual_record_version"] == visual["version"]
    assert approved["data"]["views"][0]["asset_sha256"] == ("abcdef0123456789" * 4)[:64]
    restarted = WorldService(ExperimentalStore(e.root, e.backend, e.url), e.novels, e.chapter_service)
    reopened = restarted.record(e.nid, e.scope, approved["id"])
    assert reopened["status"] == "APPROVED" and reopened["kind"] == "CHARACTER_REFERENCE_GROUP"
    assert [row["view"] for row in reopened["data"]["views"]] == ["FRONT", "SIDE", "BACK"]


@pytest.mark.parametrize("change", ["duplicate-view", "duplicate-asset", "duplicate-request", "unconfirmed", "wrong-order"])
def test_group_rejects_copied_or_unconfirmed_views(world_env, change):
    e = world_env
    install_service_verifier(e)
    visual = approve(e, record(e, "CHARACTER_VISUAL", {"character_id": "alice", "appearance": "hair"}))
    views = [view(0), view(1), view(2)]
    if change == "duplicate-view": views[2]["view"] = "FRONT"
    elif change == "duplicate-asset": views[2]["asset_id"] = views[1]["asset_id"]
    elif change == "duplicate-request": views[2]["request_id"] = views[1]["request_id"]
    elif change == "wrong-order": views = [view(1), view(0), view(2)]
    overrides = {"views": views}
    if change == "unconfirmed": overrides["consistency_confirmed"] = False
    with pytest.raises(ValueError):
        create_group(e, visual, **overrides)


def test_group_pins_the_current_visual_version_and_character(world_env):
    e = world_env
    install_service_verifier(e)
    visual = approve(e, record(e, "CHARACTER_VISUAL", {"character_id": "alice", "appearance": "hair"}))
    version, sha = visual_identity(e, visual)
    assert create_group(e, visual)["status"] == "REVIEW"
    for overrides in ({"visual_record_version": version + 1}, {"visual_record_digest": "0" * 64},
                      {"character_id": "bob"}, {"visual_record_id": "missing"}):
        with pytest.raises((ValueError, FileNotFoundError)):
            create_group(e, visual, **overrides)


def test_group_approval_is_fenced_by_the_approved_visual_source(world_env):
    e = world_env
    install_service_verifier(e)
    chapter = e.order[0]
    visual = approve(e, record(e, "CHARACTER_VISUAL", {"character_id": "alice", "appearance": "hair"}, 1))
    candidate = create_group(e, visual)
    e.chapters[chapter]["content"] += " changed"
    with pytest.raises(StaleSourceError):
        approve(e, candidate)


def test_mounted_group_route_rejects_manual_assets_without_original_jobs(image_client, monkeypatch):
    e = image_client
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2,world_character_engines_v2")
    world = e.experimental.world_service
    visual = world.create_record(e.nid, {"mode": "local", "novel_id": e.nid}, "writer", {
        "kind": "CHARACTER_VISUAL", "title": "Alice visual",
        "data": {"character_id": "alice", "appearance": "hair", "clothing": "coat"}})
    visual = world.review(e.nid, {"mode": "local", "novel_id": e.nid}, "reviewer", visual["id"], "approve", visual["version"])
    pin = world.character_visual_pin(e.nid, {"mode": "local", "novel_id": e.nid}, visual["id"])
    uploaded = []
    for index, color in enumerate((b"\x11\x22\x33", b"\x44\x55\x66", b"\x77\x88\x99")):
        body = {"filename": f"turnaround-{index}.png", "kind": "image",
                "content_base64": base64.b64encode(png_bytes(color)).decode(), "idempotency_key": f"turnaround-{index}"}
        uploaded.append(checked(e.client.post(e.studio_base + "/assets", headers=e.headers, json=body), 201))
    views = [{"view": ("FRONT", "SIDE", "BACK")[index], "asset_id": asset["id"], "asset_version": asset["version"],
              "asset_sha256": asset["sha256"], "request_id": f"group-view-{index + 1}", "provider_id": "image-provider",
              "model_id": "image-model", "prompt": f"view {index + 1}", "parameters": {"width": 1024},
              "reference_asset_ids": []} for index, asset in enumerate(uploaded)]
    base = e.prefix + f"/novels/{e.nid}/experimental/world"
    group = {"character_id": "alice", "visual_record_id": visual["id"], "visual_record_version": visual["version"],
             "visual_record_digest": pin["digest"], "title": "Alice turnaround", "views": views, "consistency_confirmed": True}
    response = e.client.post(base + "/character-reference-groups", headers=e.headers, json=group)
    assert response.status_code in (403, 404, 409, 422), response.text
    assert checked(e.client.get(base + "/records?kind=CHARACTER_REFERENCE_GROUP", headers=e.headers))["items"] == []
