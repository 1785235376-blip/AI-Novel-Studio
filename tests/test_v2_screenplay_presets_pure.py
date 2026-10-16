"""Pure starter contracts; no app runtime, persistence, or provider is needed.

Run this file with the repository's owned run_v2_checks.py profile and
``pytest --noconftest`` to avoid unrelated application autouse fixtures.
These checks are not integrated service, API, UI, or PostgreSQL acceptance.
"""
from copy import deepcopy
import builtins
import hashlib
import io
import json
from pathlib import Path
import socket

import pytest

from app.creative import models, screenplay_presets


EXPECTED = {
    "FEATURE_FILM": (8, ("开场", "诱发事件", "主动决定", "阻力升级", "中点转折", "低谷与抉择", "高潮", "余波")),
    "SHORT_FILM": (4, ("建立处境", "打断", "关键选择", "收束")),
    "ANIMATION": (6, ("世界规则", "角色愿望", "动作尝试", "视觉意外", "行动转变", "视觉回环")),
    "ADVERTISEMENT": (5, ("注意力入口", "需求", "展示", "依据", "行动邀请")),
}
DOCUMENT_KEYS = {
    "mode", "title", "source_chapter_ids", "source_independent", "scenes", "shots",
    "director_notes", "video_plan", "script",
}
SCENE_KEYS = {
    "id", "sequence", "source_chapter_id", "heading", "time", "location",
    "characters", "action", "dialogue", "emotion", "director_notes",
}


def test_imports_resolve_only_to_this_checkout():
    root = Path(__file__).resolve().parents[1]
    assert Path(screenplay_presets.__file__).resolve() == root / "app/creative/screenplay_presets.py"
    assert Path(models.__file__).resolve() == root / "app/creative/models.py"


def test_exact_closed_four_template_catalog_and_versions():
    result = screenplay_presets.catalog()
    assert set(result) == {"schema_version", "templates"}
    assert type(result["schema_version"]) is int and result["schema_version"] == 1
    assert type(result["templates"]) is list
    assert [item["id"] for item in result["templates"]] == list(EXPECTED)
    for item in result["templates"]:
        assert set(item) == {"id", "version", "title", "description", "document"}
        assert type(item["version"]) is int and item["version"] == 1
        assert 1 <= len(item["title"]) <= 80
        assert 20 <= len(item["description"]) <= 240
        assert item["document"]["title"] == item["title"]
    assert len(json.dumps(result, ensure_ascii=False).encode("utf-8")) < 32_000


@pytest.mark.parametrize("preset_id", EXPECTED)
def test_each_template_validates_original_models_and_stays_source_independent(preset_id):
    value = next(item["document"] for item in screenplay_presets.catalog()["templates"]
                 if item["id"] == preset_id)
    assert set(value) == DOCUMENT_KEYS
    document = models.CreativeDocumentIn.model_validate(value)
    assert document.model_dump(mode="json") == value
    assert document.mode == "SCREENPLAY"
    assert document.source_independent is True
    assert document.source_chapter_ids == []
    assert document.shots == document.director_notes == []
    assert document.video_plan is document.script is None
    for scene in value["scenes"]:
        assert set(scene) == SCENE_KEYS
        assert models.Scene.model_validate(scene).model_dump(mode="json") == scene
        assert scene["source_chapter_id"] is None
        assert scene["characters"] == scene["dialogue"] == scene["director_notes"] == []
        assert scene["time"] == scene["location"] == scene["emotion"] == ""


@pytest.mark.parametrize("preset_id", EXPECTED)
def test_distinct_bounded_linear_guidance_and_stable_ordered_prototype_ids(preset_id):
    item = next(item for item in screenplay_presets.catalog()["templates"] if item["id"] == preset_id)
    scenes = item["document"]["scenes"]
    count, beats = EXPECTED[preset_id]
    assert len(scenes) == count
    assert [scene["sequence"] for scene in scenes] == list(range(1, count + 1))
    assert [scene["id"] for scene in scenes] == [
        f"starter-{preset_id.lower()}-v1-scene-{index:02d}" for index in range(1, count + 1)
    ]
    assert len({scene["heading"] for scene in scenes}) == count
    for beat, scene in zip(beats, scenes):
        assert scene["action"].startswith(f"【写作提示：{beat}】")
        assert 35 <= len(scene["action"]) <= 300
        assert scene["heading"].startswith("INT./EXT. [")
        assert scene["heading"].endswith("] - [日/夜]")
        assert len(scene["heading"]) <= 80


def test_all_scene_identifiers_and_guides_are_unique_across_templates():
    scenes = [scene for item in screenplay_presets.catalog()["templates"] for scene in item["document"]["scenes"]]
    assert len(scenes) == 23
    assert len({scene["id"] for scene in scenes}) == len(scenes)
    assert len({scene["action"] for scene in scenes}) == len(scenes)


def _mutable_ids(value):
    if isinstance(value, dict):
        return {id(value)} | set().union(*(_mutable_ids(item) for item in value.values()))
    if isinstance(value, list):
        return {id(value)} | set().union(*(_mutable_ids(item) for item in value))
    return set()


def test_every_nested_result_is_detached_across_calls_and_templates():
    baseline = screenplay_presets.catalog()
    changed = screenplay_presets.catalog()
    assert _mutable_ids(baseline).isdisjoint(_mutable_ids(changed))
    per_template = [_mutable_ids(item) for item in changed["templates"]]
    for index, owned in enumerate(per_template):
        assert all(owned.isdisjoint(other) for other in per_template[index + 1:])
    for item in changed["templates"]:
        item["title"] = "Changed"
        item["document"]["source_chapter_ids"].append("foreign")
        item["document"]["director_notes"].append({"note": "foreign"})
        item["document"]["shots"].append({"id": "foreign"})
        for scene in item["document"]["scenes"]:
            scene["action"] = "Changed"
            scene["characters"].append("foreign")
            scene["dialogue"].append({"speaker": "foreign", "text": "changed"})
            scene["director_notes"].append({"note": "foreign"})
        item["document"]["scenes"].clear()
    changed["templates"].clear()
    changed["schema_version"] = 2
    assert screenplay_presets.catalog() == baseline


def test_original_model_validation_cannot_mutate_catalog_or_other_calls():
    result = screenplay_presets.catalog()
    original = deepcopy(result)
    document = models.CreativeDocumentIn.model_validate(result["templates"][0]["document"])
    document.scenes[0].action = "Author edit"
    document.scenes[0].characters.append("Author character")
    document.scenes.clear()
    assert result == original == screenplay_presets.catalog()


def test_catalog_needs_no_file_network_or_fresh_identifier(monkeypatch):
    expected = screenplay_presets.catalog()

    def forbidden(*args, **kwargs):
        raise AssertionError("A pure catalog must not perform external work")

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", forbidden)
        patch.setattr(io, "open", forbidden)
        patch.setattr(socket, "socket", forbidden)
        patch.setattr(socket, "create_connection", forbidden)
        patch.setattr(models, "uuid4", forbidden)
        assert screenplay_presets.catalog() == expected


def test_catalog_has_no_external_references_execution_or_saved_identity_fields():
    result = screenplay_presets.catalog()
    serialized = json.dumps(result, ensure_ascii=False).lower()
    for forbidden in ("https://", "http://", "file://", "provider_id", "model_id", "route_id",
                      "job_id", "graph_id", "source_evidence", "source_documents", "novel_id",
                      "document_id", "created_by", "created_at", "status", "branch", "prompt"):
        assert forbidden not in serialized


def test_v1_content_identity_is_pinned():
    # Update an existing identity only when deliberately versioning its content.
    expected = {
        "FEATURE_FILM": "ccf25c8535d3480780409bcbb47551042e9a3c2eb8b60b03381368f8fe7def35",
        "SHORT_FILM": "12c649e6121b02e6cb14480ea0cea24e2b5a7d93f76914984815bf9f5f3bc0b4",
        "ANIMATION": "623726385e133f50d834d527611cde00f9e389bdf50ada033ff59749794dd60c",
        "ADVERTISEMENT": "31dfb39c66138638d180c70a466fa0937d1e89e584a9b5e525607f0a9f62a105",
    }
    for item in screenplay_presets.catalog()["templates"]:
        canonical = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        assert hashlib.sha256(canonical.encode("utf-8")).hexdigest() == expected[item["id"]]
