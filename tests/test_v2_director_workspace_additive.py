"""Additive reconciliation scenarios and their minimal independent fixture support."""

from __future__ import annotations

import os

from pathlib import Path

from types import SimpleNamespace

from uuid import uuid4

import pytest

from app.creative import director_intent as director

HARNESS_MISSING = "requires the isolated runner (scripts/run_v2_checks.py) that sets PROJECT_ROOT"

@pytest.fixture
def rig(tmp_path, monkeypatch):
    """A real studio router over the real File store, stub authority only.

    Mirrors `tests/test_v2_production_workflow_api.py`: the permission string, the
    scope admission and the error mapping are exercised end to end.
    """
    root = Path(__file__).resolve().parents[1]
    if os.environ.get("PROJECT_ROOT") is None:
        pytest.skip(HARNESS_MISSING)
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.creative.service import CreativeService
    from app.creative.workspace import IndependentWorkspaceService
    from app.experimental.media import MediaService
    from app.experimental.production_lineage import ProductionLineageService
    from app.experimental.store import ExperimentalStore
    from app.repositories.factory import create_repository_bundle
    from app.services import ChapterService, NovelService
    from app.services.asset_library_service import AssetLibraryService

    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2,asset_lineage_v2")
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    bundle = create_repository_bundle(
        Settings(storage_backend="file", database_url="", novel_data=tmp_path,
                 enable_cloud=False, mock_provider=True), data_root=tmp_path)
    novels, chapters = NovelService(bundle.novels, bundle.chapters), ChapterService(bundle.chapters)
    nid = "phase14a-director-" + uuid4().hex
    novels.create({"id": nid, "title": "Phase14-A director", "genre": "悬疑科幻"})
    raw = ExperimentalStore(tmp_path, "file", "")
    assets = AssetLibraryService(tmp_path)
    creative = CreativeService(raw, novels, chapters)
    lineage = ProductionLineageService(raw, novels, chapters, assets, MediaService(raw, novels, chapters, assets))
    workspace = IndependentWorkspaceService(creative, assets, lineage)

    def authorize(project_id, token, branch, permission):
        if token != "valid-session":
            raise HTTPException(403, {"code": "CREATIVE_AUTHORITY_INVALID"})
        return "phase14a-author", {"mode": "local", "novel_id": project_id}

    from app.creative.workspace_api import create_independent_workspace_router
    app = FastAPI()
    app.include_router(create_independent_workspace_router(
        workspace, authorize, lambda flag: None,
        create_project=lambda body, token: (_ for _ in ()).throw(AssertionError("not used")),
        workspace_writer=lambda token: "phase14a-author"), prefix="/api")
    return SimpleNamespace(client=TestClient(app), nid=nid, creative=creative,
                           scope={"mode": "local", "novel_id": nid})

_DIRECTOR_DOCUMENT = {
    "mode": "STORYBOARD", "title": "旧城回声 分镜", "source_independent": True,
    "visual_target": {"style": "冷峻写实", "atmosphere": "压抑", "genre": "悬疑科幻",
                      "color": "青蓝低饱和", "rhythm": "缓—急—缓", "reference_works": ["《银翼杀手》"]},
    "scenes": [
        {"id": "scene-1", "sequence": 1, "heading": "INT. 旧城公寓 - 夜", "time": "夜",
         "location": "旧城公寓", "characters": ["林向晚"]},
        {"id": "scene-2", "sequence": 2, "heading": "EXT. 天台 - 日", "time": "日",
         "location": "天台", "characters": ["林向晚"]},
    ],
    "shots": [
        {"number": 1, "scene_id": "scene-1", "shot_size": "WIDE", "camera_motion": "STATIC",
         "lens": "NORMAL", "composition": "CENTER", "lighting": "暖光", "characters": ["林向晚"],
         "action": "推门", "emotion": "迟疑", "sound": "雨声", "duration_seconds": 6,
         "continuity": {"outfit": "红色外套", "environment": "旧城公寓", "time": "夜"}},
        {"number": 2, "scene_id": "scene-2", "shot_size": "CLOSE_UP", "camera_motion": "DOLLY",
         "lens": "TELEPHOTO", "composition": "RULE_OF_THIRDS", "lighting": "冷光", "characters": ["林向晚"],
         "action": "回头", "emotion": "警觉", "sound_effect": "风声", "duration_seconds": 4,
         "continuity": {"outfit": "蓝色外套", "environment": "旧城公寓", "time": "日"}},
    ],
}

def test_authored_genre_and_time_survive_file_owner_reopen_history_and_restore(rig):
    import copy

    from app.creative.models import CreativeProductionDocumentIn
    from app.creative.service import CreativeService
    from app.experimental.store import ExperimentalStore

    def content(row):
        return copy.deepcopy({key: row[key] for key in CreativeProductionDocumentIn.model_fields if key in row})

    original = copy.deepcopy(_DIRECTOR_DOCUMENT)
    original["visual_target"].pop("genre")
    for index, row in enumerate(original["shots"], 1):
        row["id"] = f"authored-shot-{index}"
        row["continuity"].pop("time")
    original["shots"][0]["continuity"]["next_shot_id"] = "authored-shot-2"
    original["shots"][1]["continuity"]["previous_shot_id"] = "authored-shot-1"
    created = rig.creative.create(rig.nid, rig.scope, "author", original)
    assert created["version"] == 1
    assert "genre" not in created["visual_target"]
    assert all("time" not in row["continuity"] for row in created["shots"])
    initial_time = next(row for row in director.project_continuity(created)["dimensions"] if row["field"] == "time")
    assert initial_time["compared_pairs"] == 0 and initial_time["unknown_pairs"] == 1

    edited = content(created)
    edited["visual_target"]["genre"] = " 作者题材 🎬 "
    edited["shots"][0]["continuity"]["time"] = "夜 🌙"
    edited["shots"][1]["continuity"]["time"] = "晨 🌅"
    updated = rig.creative.update(rig.nid, rig.scope, "author", created["id"], 1, edited)
    assert updated["version"] == 2
    assert content(updated) == edited
    fresh = CreativeService(ExperimentalStore(rig.creative.store.root, "file", ""), rig.creative.novels, rig.creative.chapters)
    reloaded = fresh.get(rig.nid, rig.scope, created["id"])
    assert content(reloaded) == edited
    assert fresh.history(rig.nid, rig.scope, created["id"])["items"] == [
        {key: value for key, value in row.items() if key != "history"} for row in (created, updated)
    ]
    projection = director.project_director_workspace(reloaded)
    genre = projection["director_intent"]["dimensions"]["genre"]
    assert genre["value"] == "作者题材 🎬" and genre["source"] == "visual_target.genre"
    assert genre["authored"] is True and genre["authored_scope"] == "DOCUMENT"
    assert {warning["code"] for warning in projection["continuity"]["warnings"]} >= {
        "CONTINUITY_TIME_CHANGED", "CONTINUITY_LIGHTING_CHANGED"
    }
    assert all("lighting" not in row["continuity"] for row in reloaded["shots"])
    assert projection["auto_modify"] is False

    # Clearing one optional value keeps the full sibling object and explicit links.
    cleared = content(reloaded)
    cleared["visual_target"]["genre"] = ""
    cleared["shots"][1]["continuity"]["time"] = ""
    blank = fresh.update(rig.nid, rig.scope, "author", created["id"], 2, cleared)
    assert blank["version"] == 3 and content(blank) == cleared
    continuity = director.project_continuity(blank)
    assert "CONTINUITY_TIME_CHANGED" not in {warning["code"] for warning in continuity["warnings"]}
    time = next(row for row in continuity["dimensions"] if row["field"] == "time")
    assert time["compared_pairs"] == 0 and time["unknown_pairs"] == 1
    assert blank["shots"][1]["continuity"]["previous_shot_id"] == "authored-shot-1"
    restored = fresh.restore(rig.nid, rig.scope, "author", created["id"], 3, 1)
    assert restored["version"] == 4 and content(restored) == content(created)
    assert [row["version"] for row in fresh.history(rig.nid, rig.scope, created["id"])["items"]] == [1, 2, 3, 4]
    assert "genre" not in restored["visual_target"]
    assert all("time" not in row["continuity"] for row in restored["shots"])

def test_original_director_owner_accepts_genre_without_shots(rig):
    created = rig.creative.create(rig.nid, rig.scope, "author", {
        "mode": "DIRECTOR", "title": "独立导演目标", "source_independent": True,
        "visual_target": {"genre": "悬疑 🎬"},
    })
    reread = rig.creative.get(rig.nid, rig.scope, created["id"])
    assert reread["visual_target"]["genre"] == "悬疑 🎬" and reread["shots"] == []
    assert director.project_director_intent(reread)["dimensions"]["genre"]["value"] == "悬疑 🎬"

@pytest.mark.parametrize("owner,field,maximum", [("DirectorVisualTarget", "genre", 2000), ("ShotContinuity", "time", 4000)])
def test_genre_and_time_owner_limits_count_unicode_code_points(owner, field, maximum):
    from app.creative import models
    from pydantic import ValidationError

    model = getattr(models, owner)
    exact = "🎬" * maximum
    assert model.model_validate({field: exact}).model_dump()[field] == exact
    with pytest.raises(ValidationError):
        model.model_validate({field: exact + "多"})
