"""Additive reconciliation scenarios and their minimal independent fixture support."""

from __future__ import annotations

import os

from pathlib import Path

from types import SimpleNamespace

from uuid import uuid4

import pytest

HARNESS_MISSING = "requires the isolated runner (scripts/run_v2_checks.py) that sets PROJECT_ROOT"

def dimensions(entry):
    return {row["field"]: row for row in entry["dimensions"]}

@pytest.fixture
def rig(tmp_path, monkeypatch):
    """A real studio router over the real File store, stub authority only."""
    root = Path(__file__).resolve().parents[1]
    if os.environ.get("PROJECT_ROOT") is None:
        pytest.skip(HARNESS_MISSING)
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.creative.bible_workspace import BibleWorkspaceService
    from app.creative.service import CreativeService
    from app.creative.workspace import IndependentWorkspaceService
    from app.experimental.media import MediaService
    from app.experimental.production_lineage import ProductionLineageService
    from app.experimental.store import ExperimentalStore
    from app.experimental.world import WorldService
    from app.repositories.factory import create_repository_bundle
    from app.services import ChapterService, NovelService
    from app.services.asset_library_service import AssetLibraryService

    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2,asset_lineage_v2,world_character_engines_v2")
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    bundle = create_repository_bundle(
        Settings(storage_backend="file", database_url="", novel_data=tmp_path,
                 enable_cloud=False, mock_provider=True), data_root=tmp_path)
    novels, chapters = NovelService(bundle.novels, bundle.chapters), ChapterService(bundle.chapters)
    nid = "round2-bible-" + uuid4().hex
    novels.create({"id": nid, "title": "Round2 bible", "genre": "悬疑科幻"})
    novels.upsert_character(nid, "c1", {"name": "林向晚", "age": 29, "role": "主角", "status": "ALIVE"})
    # The owner refuses a visual profile that names a location the project does not
    # have, so the location is created through the existing record owner first.
    # Note: that owner lower-cases a location id (`L1` is stored as `l1`), while a
    # character id is kept verbatim — so the reference below must use the stored form.
    novels.upsert_location(nid, "L1", {"name": "旧城公寓", "description": "老式砖楼"})
    assert [row["id"] for row in novels.data_set(nid, "locations")] == ["l1"]
    raw = ExperimentalStore(tmp_path, "file", "")
    creative = CreativeService(raw, novels, chapters)
    assets = AssetLibraryService(tmp_path)
    workspace = IndependentWorkspaceService(
        creative, assets, ProductionLineageService(raw, novels, chapters, assets, MediaService(raw, novels, chapters, assets)))
    world = WorldService(raw, novels, chapters)

    def authorize(project_id, token, branch, permission):
        if token != "valid-session":
            raise HTTPException(403, {"code": "CREATIVE_AUTHORITY_INVALID"})
        return "round2-author", {"mode": "local", "novel_id": project_id}

    from app.creative.workspace_api import create_independent_workspace_router
    app = FastAPI()
    app.include_router(create_independent_workspace_router(
        workspace, authorize, lambda flag: None,
        create_project=lambda body, token: (_ for _ in ()).throw(AssertionError("not used")),
        workspace_writer=lambda token: "round2-author",
        bible_service=BibleWorkspaceService(workspace, world)), prefix="/api")
    return SimpleNamespace(client=TestClient(app), nid=nid, world=world, assets=assets,
                           scope={"mode": "local", "novel_id": nid})

@pytest.mark.parametrize("kind,subject_key,subject_id,initial,edited", [
    ("CHARACTER_VISUAL", "character_id", "c1",
     {"appearance": "瘦高，短发", "clothing": "深色风衣", "distinguishing": "左手旧疤",
      "reference_asset_ids": ["declared-character-ref"]},
     {"appearance": "短发，戴眼镜", "clothing": "深色风衣", "distinguishing": "左手旧疤，右眉细痣",
      "reference_asset_ids": ["declared-character-ref"]}),
    ("SCENE_VISUAL", "location_id", "l1",
     {"architecture": "老式砖楼", "material": "砖石", "lighting": "暖光", "weather": "阴雨",
      "mood": "安静", "time_of_day": "夜", "reference_asset_ids": ["declared-scene-ref"]},
     {"architecture": "老式砖楼与拱门", "material": "砖石", "lighting": "柔和暖光", "weather": "阴雨",
      "mood": "安静", "time_of_day": "黎明", "reference_asset_ids": ["declared-scene-ref"]}),
])
def test_visual_authoring_roundtrip_uses_the_original_owner_and_history(
        rig, tmp_path, kind, subject_key, subject_id, initial, edited):
    """One synthetic profile per subject. Stub route authority is not live-auth acceptance."""
    from app.experimental.store import ExperimentalStore
    from app.experimental.world import WorldRecordEditIn, WorldRecordIn, WorldService

    def payload(data):
        return {"kind": kind, "title": "合成视觉设定", "chapter_id": None,
                "event_order": 0, "data": {subject_key: subject_id, **data}}

    created = rig.world.create_record(rig.nid, rig.scope, "round2-author",
                                     WorldRecordIn.model_validate(payload(initial)))
    assert (created["status"], created["version"], created["chapter_id"]) == ("REVIEW", 1, None)
    assert created["data"] == payload(initial)["data"]
    assert rig.world.canon(rig.nid, rig.scope) == []
    updated = rig.world.edit_record(rig.nid, rig.scope, "round2-author", created["id"],
                                   WorldRecordEditIn.model_validate({**payload(edited), "expected_version": 1}))
    assert (updated["status"], updated["version"]) == ("REVIEW", 2)
    assert updated["data"] == payload(edited)["data"]

    # A fresh service and store instance reload the same isolated file persistence.
    reopened_owner = WorldService(ExperimentalStore(tmp_path, "file", ""),
                                  rig.world.novels, rig.world.chapters)
    persisted = reopened_owner.record(rig.nid, rig.scope, created["id"])
    assert persisted["version"] == 2 and persisted["data"] == updated["data"]
    rejected = reopened_owner.review(rig.nid, rig.scope, "round2-author", created["id"], "reject", 2)
    assert (rejected["status"], rejected["version"]) == ("REJECTED", 3)
    reopened = reopened_owner.review(rig.nid, rig.scope, "round2-author", created["id"], "reopen", 3)
    assert (reopened["status"], reopened["version"]) == ("REVIEW", 4)
    history = reopened_owner.history(rig.nid, rig.scope, created["id"])
    assert [row["version"] for row in history] == [1, 2, 3]
    assert [row["status"] for row in history] == ["REVIEW", "REVIEW", "REJECTED"]
    assert history[0]["data"] == created["data"]
    assert history[1]["data"] == history[2]["data"] == updated["data"]
    assert reopened_owner.canon(rig.nid, rig.scope) == []

    # The existing read-only Bible route reads the saved owner record, including REVIEW.
    response = rig.client.get(f"/api/projects/{rig.nid}/studio/bible",
                              headers={"x-session-token": "valid-session"})
    assert response.status_code == 200, response.text
    projection = response.json()
    assert projection["advisory_only"] is True and projection["execution_authority"] is False
    bible_key = "character_bible" if kind == "CHARACTER_VISUAL" else "scene_bible"
    entry = next(row for row in projection[bible_key]["entries"] if row[subject_key] == subject_id)
    assert entry["visual_record_status"] == "REVIEW" and entry["visual_authoritative"] is False
    covered = dimensions(entry)
    for key, value in edited.items():
        if key in {"distinguishing", "reference_asset_ids"}:
            continue
        dimension = covered["time" if key == "time_of_day" else key]
        assert dimension["value"] == value and dimension["authoritative"] is False
        assert dimension["record_status"] == "REVIEW"
    if kind == "CHARACTER_VISUAL":
        assert "distinguishing" not in covered  # Stored in owner/history, not a Bible dimension.
        assert covered["behavior"]["value"] == covered["relationship"]["value"] == "UNKNOWN"
        assert covered["reference"]["unresolved_references"] == edited["reference_asset_ids"]
        assert all(ref["resolution"] == "UNRESOLVED" for ref in covered["reference"]["references"])
    else:
        # Scene refs stay declared on the owner; the seven Bible dimensions omit references.
        assert "reference" not in covered
        assert entry["reference_asset_ids"] == edited["reference_asset_ids"]
        character_entry = projection["character_bible"]["entries"][0]
        assert dimensions(character_entry)["appearance"]["value"] == "UNKNOWN"

def test_visual_schema_lengths_count_unicode_code_points():
    """The guided fields count characters the same way as their existing owner schema."""
    from app.experimental.world import WorldRecordIn

    payload = {"kind": "CHARACTER_VISUAL", "title": "🌙" * 240,
               "data": {"character_id": "🦊" * 160, "appearance": "🌙" * 4000,
                        "clothing": "雪" * 4000, "distinguishing": "🦊" * 2000}}
    assert WorldRecordIn.model_validate(payload).data["appearance"] == "🌙" * 4000
    with pytest.raises(ValueError):
        WorldRecordIn.model_validate({**payload, "data": {**payload["data"], "appearance": "🌙" * 4001}})
