"""Source-bound Storyboard operations using original File/real PG owners.

Synthetic authored scenes and tiny CPU PNGs only; no model or render runs.
"""
from copy import deepcopy

import pytest

from test_v2_independent_workspace import rig, import_asset, png_bytes, reopened
from test_v2_discovered_image_production import owner


def board_value(**changes):
    return {"mode": "STORYBOARD", "title": "SYNTHETIC two-shot plan", "source_independent": True,
        "scenes": [{"id": "scene-1", "sequence": 1, "heading": "INT. SYNTHETIC ROOM"}],
        "shots": [{"id": "shot-1", "number": 1, "scene_id": "scene-1", "duration_seconds": 3,
            "frame_prompt": "Synthetic character in a blue jacket", "lighting": "Soft key",
            "continuity": {"next_shot_id": "shot-2", "characters": "visitor", "outfit": "blue jacket"}},
            {"id": "shot-2", "number": 2, "scene_id": "scene-1", "duration_seconds": 2,
             "frame_prompt": "Same synthetic visitor looking up", "continuity": {"previous_shot_id": "shot-1"}}], **changes}


def content(row):
    from app.creative.models import CreativeProductionDocumentIn
    return {key: deepcopy(row[key]) for key in CreativeProductionDocumentIn.model_fields if key in row}


def configured(e, monkeypatch):
    from app.asset_providers import AssetProviderRegistry
    production = owner(AssetProviderRegistry(), monkeypatch, e)
    e.service.creative.configure_storyboard_production(production)
    return e.service.creative, production


def approve(creative, e, rid):
    view = creative.storyboards.get(e.nid, e.scope, e.actor, rid)
    return creative.storyboards.approve(e.nid, e.scope, e.actor, rid, {
        "expected_version": view["document_snapshot"]["version"], "reviewed_content_digest": view["content_digest"]})


def bind(creative, e, rid, shot_id, asset):
    view = creative.storyboards.get(e.nid, e.scope, e.actor, rid)
    shot = next(item for item in view["shots"] if item["shot_id"] == shot_id)
    return creative.storyboards.bind_image(e.nid, e.scope, e.actor, rid, shot_id, {
        "expected_version": view["document_snapshot"]["version"], "shot_version": shot["shot_version"],
        "shot_digest": shot["shot_digest"], "asset": {"asset_id": asset["id"], "kind": "image",
                                                     "version": asset["version"], "digest": asset["sha256"]}})


def test_shot_revisions_follow_original_history_not_document_only_updates(rig, monkeypatch):
    creative, _ = configured(rig, monkeypatch)
    row = creative.create(rig.nid, rig.scope, rig.actor, board_value())
    first = creative.storyboards.get(rig.nid, rig.scope, rig.actor, row["id"])
    assert [shot["shot_version"] for shot in first["shots"]] == [1, 1]
    value = content(row); value["title"] = "Changed title"
    row = creative.update(rig.nid, rig.scope, rig.actor, row["id"], 1, value)
    assert [shot["shot_version"] for shot in creative.storyboards.get(rig.nid, rig.scope, rig.actor, row["id"])["shots"]] == [1, 1]
    value = content(row); value["shots"][0]["lens"] = "50mm"
    row = creative.update(rig.nid, rig.scope, rig.actor, row["id"], 2, value)
    changed = creative.storyboards.get(rig.nid, rig.scope, rig.actor, row["id"])
    assert [shot["shot_version"] for shot in changed["shots"]] == [2, 1]
    assert changed["shots"][0]["shot_digest"] != first["shots"][0]["shot_digest"]
    restored = creative.restore(rig.nid, rig.scope, rig.actor, row["id"], 3, 1)
    assert [shot["shot_version"] for shot in creative.storyboards.get(rig.nid, rig.scope, rig.actor, restored["id"])["shots"]] == [3, 1]
    assert len(restored["history"]) == 3


@pytest.mark.parametrize("change", ["self", "nonadjacent", "unknownnote", "badscene", "unknownfield"])
def test_shot_relationship_and_director_bindings_are_closed(rig, change):
    value = board_value()
    if change == "self": value["shots"][0]["continuity"]["next_shot_id"] = "shot-1"
    elif change == "nonadjacent": value["shots"][0]["continuity"]["previous_shot_id"] = "shot-2"
    elif change == "unknownnote": value["shots"][0]["director_note_ids"] = ["missing"]
    elif change == "badscene": value["shots"][0]["scene_id"] = "foreign"
    else: value["shots"][0]["continuity"]["guarantee_identity"] = True
    with pytest.raises(ValueError):
        rig.service.creative.create(rig.nid, rig.scope, rig.actor, value)
    assert rig.service.creative.list(rig.nid, rig.scope) == []


def test_approval_cas_edit_and_restore_revoke_without_changing_shot_version(rig, monkeypatch):
    from app.experimental.common import StaleSourceError
    from app.services.v1_capability_service import CapabilityVersionConflict
    creative, _ = configured(rig, monkeypatch)
    row = creative.create(rig.nid, rig.scope, rig.actor, board_value())
    before = creative.storyboards.get(rig.nid, rig.scope, rig.actor, row["id"])
    with pytest.raises(StaleSourceError):
        creative.storyboards.approve(rig.nid, rig.scope, rig.actor, row["id"], {"expected_version": 1, "reviewed_content_digest": "0" * 64})
    approved = approve(creative, rig, row["id"])
    assert approved["approved"] and approved["document_snapshot"]["version"] == 2
    assert approved["shots"] == before["shots"]
    with pytest.raises(CapabilityVersionConflict):
        creative.storyboards.approve(rig.nid, rig.scope, rig.actor, row["id"], {"expected_version": 1, "reviewed_content_digest": before["content_digest"]})
    row = creative.get(rig.nid, rig.scope, row["id"])
    creative.update(rig.nid, rig.scope, rig.actor, row["id"], 2, content(row))
    assert not creative.storyboards.get(rig.nid, rig.scope, rig.actor, row["id"])["approved"]
    creative.restore(rig.nid, rig.scope, rig.actor, row["id"], 3, 2)
    assert not creative.storyboards.get(rig.nid, rig.scope, rig.actor, row["id"])["approved"]


def test_formal_image_binding_reuses_asset_bytes_and_invalidates_on_shot_edit(rig, monkeypatch):
    from app.experimental.common import StaleSourceError
    creative, production = configured(rig, monkeypatch)
    row = creative.create(rig.nid, rig.scope, rig.actor, board_value())
    asset = import_asset(rig, data=png_bytes(), filename="synthetic-board.png", kind="image")
    attached = bind(creative, rig, row["id"], "shot-1", asset)
    assert attached["shots"][0]["image_asset"]["asset_id"] == asset["id"]
    assert len(rig.service.list_assets(rig.nid, rig.scope)["items"]) == 1
    with rig.service._asset_scope(rig.nid, rig.scope):
        assert rig.assets.content(asset["id"], branch_id=rig.scope.get("branch_id")) == png_bytes()
    row = creative.get(rig.nid, rig.scope, row["id"])
    value = content(row); value["shots"][0]["action"] = "Changed action"
    creative.update(rig.nid, rig.scope, rig.actor, row["id"], row["version"], value)
    changed = creative.storyboards.get(rig.nid, rig.scope, rig.actor, row["id"])
    assert changed["shots"][0]["image_asset"] is None and changed["shots"][0]["shot_version"] == 2
    assert rig.service.asset(rig.nid, rig.scope, asset["id"])["version"] == asset["version"]
    old = attached["shots"][0]
    with pytest.raises(StaleSourceError):
        creative.storyboards.bind_image(rig.nid, rig.scope, rig.actor, row["id"], "shot-1", {
            "expected_version": changed["document_snapshot"]["version"], "shot_version": old["shot_version"],
            "shot_digest": old["shot_digest"], "asset": old["image_asset"]})


def test_approved_storyboard_creates_original_timeline_draft_without_job_or_render(rig, monkeypatch):
    from app.experimental.common import StaleSourceError
    creative, production = configured(rig, monkeypatch)
    row = creative.create(rig.nid, rig.scope, rig.actor, board_value())
    asset = import_asset(rig, data=png_bytes(), filename="synthetic-board.png", kind="image")
    bind(creative, rig, row["id"], "shot-1", asset)
    unapproved = bind(creative, rig, row["id"], "shot-2", asset)
    body = {"expected_version": unapproved["document_snapshot"]["version"], "reviewed_content_digest": unapproved["content_digest"],
            "title": "Synthetic timeline", "shot_ids": ["shot-2", "shot-1"]}
    with pytest.raises(StaleSourceError, match="APPROVAL_REQUIRED"):
        creative.storyboards.timeline_draft(rig.nid, rig.scope, rig.actor, row["id"], body)
    reviewed = approve(creative, rig, row["id"])
    body["expected_version"] = reviewed["document_snapshot"]["version"]
    result = creative.storyboards.timeline_draft(rig.nid, rig.scope, rig.actor, row["id"], body)
    assert result["model_called"] is result["rendered"] is result["automatic_dispatch"] is False
    timeline = result["timeline"]
    assert timeline["version"] == 1 and timeline["timeline"]["duration_ms"] == 5000
    clips = timeline["timeline"]["tracks"][0]["clips"]
    assert [clip["start_ms"] for clip in clips] == [0, 3000]
    assert {clip["source_snapshot"]["id"] for clip in clips} == {asset["id"]}
    assert [shot["shot_id"] for shot in result["storyboard_origin"]["shots"]] == ["shot-1", "shot-2"]
    assert production.timeline_get(rig.nid, rig.scope, rig.actor, timeline["id"], lambda: None) == timeline
    assert len(rig.service.list_assets(rig.nid, rig.scope)["items"]) == 1
    assert creative.get(rig.nid, rig.scope, row["id"])["version"] == reviewed["document_snapshot"]["version"]


def test_director_advice_projects_authored_camera_style_rhythm_without_overwrite(rig, monkeypatch):
    from test_v2_director_storyboard_production import independent_direction, rich_note
    creative, _ = configured(rig, monkeypatch)
    row = creative.create(rig.nid, rig.scope, rig.actor, independent_direction(director_notes=[rich_note(
        lighting="Soft key", color_palette="Blue", material="Brushed metal", transition="Cut on action")]))
    advice = creative.storyboards.director_advice(rig.nid, rig.scope, row["id"])
    assert advice["advice_only"] and not advice["automatic_apply"] and not advice["model_called"]
    assert advice["notes"][0]["camera"]["lens"] == "50mm"
    assert advice["notes"][0]["visual_style"]["lighting"] == "Soft key"
    assert advice["notes"][0]["rhythm"]["transition"] == "Cut on action"
    assert creative.get(rig.nid, rig.scope, row["id"]) == row
    board = creative.derive(rig.nid, rig.scope, rig.actor, row["id"], {"expected_version": 1, "mode": "STORYBOARD", "shot_policy": "DIRECTOR_NOTES"})
    assert board["shots"][0]["lighting"] == "Soft key" and board["shots"][0]["color"] == "Blue"
    assert board["shots"][0]["director_note_ids"] == [row["director_notes"][0]["id"]]


def test_binding_and_approval_revoke_rolls_back_original_transaction(rig, monkeypatch):
    creative, _ = configured(rig, monkeypatch)
    row = creative.create(rig.nid, rig.scope, rig.actor, board_value())
    receipt = creative.storyboards.get(rig.nid, rig.scope, rig.actor, row["id"])
    before = rig.store.read(rig.nid, rig.scope)
    calls = []
    def revoked():
        calls.append(1)
        if len(calls) == 5:
            raise PermissionError("synthetic-revocation")
    with pytest.raises(PermissionError):
        creative.storyboards.approve(rig.nid, rig.scope, rig.actor, row["id"], {
            "expected_version": 1, "reviewed_content_digest": receipt["content_digest"]}, revoked)
    assert rig.store.read(rig.nid, rig.scope) == before


def test_timeline_creation_provenance_survives_multiple_edits_history_and_restore(rig, monkeypatch):
    from app.creative.production_execution import TIMELINES
    creative, production = configured(rig, monkeypatch)
    row = creative.create(rig.nid, rig.scope, rig.actor, board_value())
    asset = import_asset(rig, data=png_bytes(), filename="synthetic-original.png", kind="image")
    bind(creative, rig, row["id"], "shot-1", asset)
    reviewed = approve(creative, rig, row["id"])
    draft = creative.storyboards.timeline_draft(rig.nid, rig.scope, rig.actor, row["id"], {
        "expected_version": reviewed["document_snapshot"]["version"], "reviewed_content_digest": reviewed["content_digest"],
        "title": "Original draft", "shot_ids": ["shot-1"]})
    original = draft["timeline"]
    latest = original
    for title in ("Independent edit one", "Independent edit two"):
        timeline = deepcopy(latest["timeline"])
        timeline["tracks"][0]["clips"][0]["opacity"] = 0.8 if latest["version"] == 1 else 0.6
        latest = production.timeline_save(rig.nid, rig.scope, rig.actor, original["id"], {
            "expected_version": latest["version"], "title": title, "timeline": timeline}, lambda: None)
    assert latest["version"] == 3 and latest["timeline_digest"] != original["timeline_digest"]
    history = production.timeline_history(rig.nid, rig.scope, rig.actor, original["id"], lambda: None)
    assert [item["version"] for item in history["items"]] == [2, 1]
    assert all(item["storyboard_origin"] == draft["storyboard_origin"] for item in history["items"])
    assert all("history" not in item for item in history["items"])
    restored = production.timeline_restore(rig.nid, rig.scope, rig.actor, original["id"], {
        "expected_version": 3, "reviewed_timeline_digest": latest["timeline_digest"],
        "restore_version": 1, "restore_digest": original["timeline_digest"]}, lambda: None)
    assert restored["version"] == 4 and restored["timeline"] == original["timeline"]
    assert restored["storyboard_origin"] == draft["storyboard_origin"]
    persisted = rig.store.read(rig.nid, rig.scope)["collections"][TIMELINES][original["id"]]
    assert persisted["storyboard_origin"]["timeline_snapshot"] == {"id": original["id"], "version": 1, "digest": original["timeline_digest"]}
    assert len(persisted["history"]) == 3
