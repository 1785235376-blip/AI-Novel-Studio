"""Round 2 — Character & Scene Bible.

The properties that matter, beyond the individual dimensions:

* **no second system** — the bible is a projection over the project's existing
  `characters`/`locations` records, the `WorldService` semantic records, the asset
  index and the creative documents; a test asserts the projection module defines no
  model and imports no application model;
* **unknown is a value** — an unauthored dimension is `UNKNOWN`, never an empty
  string that could read as "nothing to say", and never filled in from prose;
* **draft is not canon** — a `DRAFT` visual record is reported as a draft and is
  not `authoritative`;
* **declared is not verified** — an asset reference is `RESOLVED` only against an
  index the caller supplied.

The pure projection tests run anywhere. The route test needs the isolated runner
(`scripts/run_v2_checks.py`), which is what sets `PROJECT_ROOT`; without it the
route test skips rather than reporting a pass it did not earn.
"""
from __future__ import annotations

import inspect
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.creative import bible_projection as bible

HARNESS_MISSING = "requires the isolated runner (scripts/run_v2_checks.py) that sets PROJECT_ROOT"


# --------------------------------------------------------------- fixtures --

def character(**overrides):
    row = {"id": "c1", "name": "林向晚", "age": 29, "role": "主角", "status": "ALIVE", "branch_id": None}
    row.update(overrides)
    return row


def location(**overrides):
    row = {"id": "L1", "name": "旧城公寓", "branch_id": None}
    row.update(overrides)
    return row


def record(kind, data, status="APPROVED", **extra):
    row = {"id": f"{kind.lower()}-1", "kind": kind, "status": status, "data": data}
    row.update(extra)
    return row


CHARACTER_VISUAL = record("CHARACTER_VISUAL", {
    "character_id": "c1", "appearance": "瘦高，短发", "clothing": "深色风衣",
    "distinguishing": "左手有旧疤", "reference_asset_ids": ["a1", "a2"],
})
SCENE_VISUAL = record("SCENE_VISUAL", {
    "location_id": "L1", "architecture": "老式砖楼", "material": "水泥与铁",
    "lighting": "暖光", "weather": "阴雨", "mood": "压抑", "time_of_day": "夜",
    "reference_asset_ids": [],
})
PSYCHOLOGY = record("PSYCHOLOGY", {
    "character_id": "c1", "state": "克制", "motivation": "查明真相",
}, id="psy-1", chapter_id="ch1")
RELATIONSHIP = record("RELATIONSHIP", {
    "source_character_id": "c1", "target_character_id": "c2", "state": "旧识",
}, id="rel-1", chapter_id="ch1")
DOCUMENT = {
    "id": "d1", "mode": "STORYBOARD",
    "scenes": [{"id": "s1", "characters": ["c1"], "location": "L1"}],
    "shots": [{"id": "sh1", "characters": ["c1"],
               "continuity": {"characters": "c1, c2"}, "scene_id": "s1"}],
}


def dimensions(entry):
    return {row["field"]: row for row in entry["dimensions"]}


# ------------------------------------------------------- required fields --

def test_the_six_character_bible_dimensions_are_the_required_set():
    assert bible.CHARACTER_BIBLE_FIELDS == (
        "identity", "appearance", "clothing", "reference", "behavior", "relationship")


def test_the_seven_scene_bible_dimensions_are_the_required_set():
    assert bible.SCENE_BIBLE_FIELDS == (
        "location", "architecture", "material", "lighting", "weather", "time", "mood")


def test_every_dimension_declares_the_owner_it_reads_from():
    for field, source in bible.CHARACTER_SOURCES.items():
        assert field in bible.CHARACTER_BIBLE_FIELDS and source
    for field, source in bible.SCENE_SOURCES.items():
        assert field in bible.SCENE_BIBLE_FIELDS and source


# ----------------------------------------------- no second system, no writes --

def test_projection_module_defines_no_model_and_imports_no_app_model():
    source = inspect.getsource(bible)
    for forbidden in ("from app", "import app", "class Character(", "class Scene(",
                      "class Project(", "class Asset(", "class Location(", "class Task("):
        assert forbidden not in source, f"the bible must reuse owners, not {forbidden}"


def test_projection_module_has_no_write_path():
    source = inspect.getsource(bible)
    for forbidden in ("def create", "def update", "def write", "def save", "def commit", "def delete"):
        assert forbidden not in source, f"the bible projection is read-only, not {forbidden}"


# ------------------------------------------------------------ character bible --

def test_character_bible_carries_all_six_dimensions():
    entries = bible.project_character_bible(
        [character()], world_records=[CHARACTER_VISUAL, PSYCHOLOGY, RELATIONSHIP])["entries"]
    assert len(entries) == 1
    assert [row["field"] for row in entries[0]["dimensions"]] == list(bible.CHARACTER_BIBLE_FIELDS)


def test_character_identity_comes_from_the_existing_character_record():
    covered = dimensions(bible.project_character_bible([character()])["entries"][0])
    assert covered["identity"]["authored"] is True
    assert "林向晚" in covered["identity"]["value"] and "主角" in covered["identity"]["value"]
    assert covered["identity"]["source"] == "characters.name/age/role"


def test_behaviour_and_relationship_come_from_the_existing_world_records():
    covered = dimensions(bible.project_character_bible(
        [character()], world_records=[PSYCHOLOGY, RELATIONSHIP])["entries"][0])
    assert covered["behavior"]["authored"] is True and "克制" in covered["behavior"]["value"]
    assert covered["relationship"]["authored"] is True
    assert covered["relationship"]["relationships"][0]["target_character_id"] == "c2"
    assert covered["relationship"]["relationships"][0]["state"] == "旧识"


def test_visual_dimensions_come_from_the_new_authored_visual_record():
    covered = dimensions(bible.project_character_bible(
        [character()], world_records=[CHARACTER_VISUAL])["entries"][0])
    assert covered["appearance"]["value"] == "瘦高，短发"
    assert covered["clothing"]["value"] == "深色风衣"
    assert covered["appearance"]["authoritative"] is True
    assert covered["appearance"]["record_status"] == "APPROVED"


def test_an_unauthored_dimension_is_the_explicit_unknown_value():
    """Not an empty string: the surface must be able to tell 'missing' from 'blank'."""
    covered = dimensions(bible.project_character_bible([character()])["entries"][0])
    for field in ("appearance", "clothing", "reference", "behavior", "relationship"):
        assert covered[field]["authored"] is False, field
        assert covered[field]["state"] == bible.UNKNOWN, field
        assert covered[field]["value"] == bible.UNKNOWN, field


def test_a_draft_visual_record_is_reported_as_a_draft_not_canon():
    entries = bible.project_character_bible(
        [character()], world_records=[record("CHARACTER_VISUAL",
            {"character_id": "c1", "appearance": "草稿外形"}, status="DRAFT")])["entries"]
    assert entries[0]["visual_authoritative"] is False
    assert entries[0]["visual_record_status"] == "DRAFT"
    covered = dimensions(entries[0])
    assert covered["appearance"]["authoritative"] is False
    # The draft text is still shown, but never as canon.
    assert covered["appearance"]["value"] == "草稿外形"


def test_an_approved_record_wins_over_a_draft_for_the_same_subject():
    entries = bible.project_character_bible([character()], world_records=[
        record("CHARACTER_VISUAL", {"character_id": "c1", "appearance": "草稿"}, status="DRAFT", id="v-draft"),
        record("CHARACTER_VISUAL", {"character_id": "c1", "appearance": "定稿"}, status="APPROVED", id="v-approved"),
    ])["entries"]
    assert dimensions(entries[0])["appearance"]["value"] == "定稿"
    assert entries[0]["visual_authoritative"] is True


# ------------------------------------------------------------- references --

def test_references_are_declared_not_assumed_without_an_index():
    covered = dimensions(bible.project_character_bible(
        [character()], world_records=[CHARACTER_VISUAL])["entries"][0])
    assert covered["reference"]["verification"] == "NO_INDEX_SUPPLIED"
    assert covered["reference"]["unresolved_references"] == ["a1", "a2"]


def test_references_are_resolved_only_against_a_supplied_index():
    covered = dimensions(bible.project_character_bible(
        [character()], world_records=[CHARACTER_VISUAL], assets=[{"id": "a1"}])["entries"][0])
    assert covered["reference"]["verification"] == "INDEX_SUPPLIED"
    assert covered["reference"]["references"] == [
        {"asset_id": "a1", "resolution": "RESOLVED"},
        {"asset_id": "a2", "resolution": "UNRESOLVED"}]
    assert covered["reference"]["unresolved_references"] == ["a2"]


# ------------------------------------------------------------- scene bible --

def test_scene_bible_carries_all_seven_dimensions():
    entries = bible.project_scene_bible([location()], world_records=[SCENE_VISUAL])["entries"]
    assert [row["field"] for row in entries[0]["dimensions"]] == list(bible.SCENE_BIBLE_FIELDS)


def test_scene_visual_dimensions_come_from_the_authored_record():
    covered = dimensions(bible.project_scene_bible([location()], world_records=[SCENE_VISUAL])["entries"][0])
    assert covered["architecture"]["value"] == "老式砖楼"
    assert covered["material"]["value"] == "水泥与铁"
    assert covered["lighting"]["value"] == "暖光"
    assert covered["weather"]["value"] == "阴雨"
    assert covered["time"]["value"] == "夜"
    assert covered["mood"]["value"] == "压抑"


def test_scene_location_identity_comes_from_the_existing_location_record():
    covered = dimensions(bible.project_scene_bible([location()])["entries"][0])
    assert covered["location"]["authored"] is True and "旧城公寓" in covered["location"]["value"]


def test_an_unauthored_scene_dimension_is_unknown():
    covered = dimensions(bible.project_scene_bible([location()])["entries"][0])
    for field in ("architecture", "material", "lighting", "weather", "time", "mood"):
        assert covered[field]["value"] == bible.UNKNOWN, field


# ------------------------------------------------------------------ usage --

def test_usage_is_built_only_from_authored_references_in_real_documents():
    entries = bible.project_character_bible([character()], documents=[DOCUMENT])["entries"]
    roles = {row["role"] for row in entries[0]["used_in"]}
    assert roles == {"SCENE_CAST", "SHOT_CAST", "SHOT_CONTINUITY"}
    assert {row["document_id"] for row in entries[0]["used_in"]} == {"d1"}


def test_a_character_with_no_reference_anywhere_has_no_usage():
    entries = bible.project_character_bible([character(id="c-orphan")], documents=[DOCUMENT])["entries"]
    assert entries[0]["used_in"] == []


def test_usage_never_links_by_name_similarity():
    """Only authored ids/names that actually appear are linked; nothing is guessed."""
    entries = bible.project_character_bible([character(id="林向晚", name="林向晚")],
                                            documents=[DOCUMENT])["entries"]
    assert entries[0]["used_in"] == []


# ---------------------------------------------------------------- whole bible --

def test_whole_bible_composes_both_halves_and_grants_nothing():
    projected = bible.project_bible(characters=[character()], locations=[location()],
                                    world_records=[CHARACTER_VISUAL, SCENE_VISUAL],
                                    assets=[{"id": "a1"}], documents=[DOCUMENT])
    assert projected["contract"] == "studio-bible/1"
    assert projected["advisory_only"] is True
    assert projected["execution_authority"] is False
    assert projected["auto_modify"] is False
    assert projected["unknown_is_explicit"] is True
    assert projected["character_bible"]["character_count"] == 1
    assert projected["scene_bible"]["location_count"] == 1


def test_gaps_enumerate_exactly_the_unknown_dimensions():
    projected = bible.project_bible(characters=[character()], locations=[location()],
                                    world_records=[CHARACTER_VISUAL], assets=[{"id": "a1"}])
    character_gaps = {row["field"] for row in projected["gaps"]["characters"]}
    assert character_gaps == {"behavior", "relationship"}
    scene_gaps = {row["field"] for row in projected["gaps"]["scenes"]}
    assert scene_gaps == {"architecture", "material", "lighting", "weather", "time", "mood"}


def test_projection_never_mutates_its_inputs():
    characters = [character()]
    records = [CHARACTER_VISUAL, SCENE_VISUAL]
    before = repr(characters) + repr(records)
    bible.project_bible(characters=characters, locations=[location()], world_records=records,
                        assets=[{"id": "a1"}], documents=[DOCUMENT])
    assert repr(characters) + repr(records) == before


def test_an_empty_project_projects_empty_bibles_rather_than_failing():
    projected = bible.project_bible(characters=[], locations=[], world_records=[],
                                    assets=[], documents=[])
    assert projected["character_bible"]["entries"] == []
    assert projected["scene_bible"]["entries"] == []
    assert projected["gaps"] == {"characters": [], "scenes": []}


# ------------------------------------------------ the reused owner extension --

def test_the_two_visual_kinds_are_registered_on_the_existing_world_owner():
    from app.experimental.world import DATA_MODELS, WorldRecordIn

    for kind, subject_field in (("CHARACTER_VISUAL", "character_id"), ("SCENE_VISUAL", "location_id")):
        assert kind in DATA_MODELS
        fields = DATA_MODELS[kind].model_fields
        assert subject_field in fields
        assert "appearance" in fields or "architecture" in fields
        # Registered on the owner's own typed dispatch, so the existing version,
        # review, CAS and history machinery applies unchanged.
        assert kind in WorldRecordIn.model_fields["kind"].annotation.__args__


def test_the_eight_pre_existing_world_kinds_are_unchanged():
    from app.experimental.world import DATA_MODELS

    assert set(DATA_MODELS) == {
        "HISTORY", "GEOGRAPHY", "CIVILIZATION", "ABILITY", "ABILITY_USE",
        "PSYCHOLOGY", "RELATIONSHIP", "CHARACTER_EVENT", "CHARACTER_VISUAL", "SCENE_VISUAL"}


def test_visual_records_validate_and_refuse_unknown_keys():
    from app.experimental.world import WorldRecordIn

    for kind, key, value in (("CHARACTER_VISUAL", "character_id", "c1"), ("SCENE_VISUAL", "location_id", "L1")):
        WorldRecordIn.model_validate({"kind": kind, "title": "t", "data": {key: value}})
        with pytest.raises(Exception):
            WorldRecordIn.model_validate({"kind": kind, "title": "t", "data": {key: value, "not_a_field": 1}})
        with pytest.raises(Exception):
            WorldRecordIn.model_validate({"kind": kind, "title": "t", "data": {}})


def test_visual_records_do_not_require_a_chapter_reference():
    """A visual profile is project-level; requiring a chapter would be wrong."""
    from app.experimental.world import WorldRecordIn

    for kind, key in (("CHARACTER_VISUAL", "character_id"), ("SCENE_VISUAL", "location_id")):
        validated = WorldRecordIn.model_validate({"kind": kind, "title": "t", "data": {key: "x"}})
        assert validated.chapter_id is None


def test_an_unhandled_typed_kind_fails_closed_instead_of_misreading_references():
    """The reference dispatch must never silently treat a new kind as another one."""
    from app.experimental.world import WorldService

    source = inspect.getsource(WorldService._references)
    assert "unhandled world record kind" in source
    assert "CHARACTER_VISUAL" in source and "SCENE_VISUAL" in source
    # The pre-existing CHARACTER_EVENT branch is now explicit rather than the fallback.
    assert 'kind == "CHARACTER_EVENT"' in source


# ------------------------------------------------------- route admission ----

def test_only_the_declared_methods_reach_the_bible_path():
    from app.creative.workspace_api import is_independent_studio_route

    assert is_independent_studio_route("GET", "/api/projects/P1/studio/bible")
    for method, path in (("POST", "/api/projects/P1/studio/bible"),
                         ("PUT", "/api/projects/P1/studio/bible"),
                         ("DELETE", "/api/projects/P1/studio/bible"),
                         ("GET", "/api/projects/P1/studio/bible/extra")):
        assert not is_independent_studio_route(method, path), (method, path)


# ------------------------------------------------------ route integration ---

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


def _authorize_record(rig, kind, data):
    from app.experimental.world import WorldRecordIn

    created = rig.world.create_record(
        rig.nid, rig.scope, "round2-author",
        WorldRecordIn.model_validate({"kind": kind, "title": f"{kind} record", "data": data}))
    rig.world.review(rig.nid, rig.scope, "round2-author", created["id"], "approve", created["version"])
    return created


def test_bible_route_projects_real_owners_and_extension_records(rig):
    _authorize_record(rig, "CHARACTER_VISUAL",
                      {"character_id": "c1", "appearance": "瘦高，短发", "clothing": "深色风衣"})
    _authorize_record(rig, "SCENE_VISUAL",
                      {"location_id": "l1", "architecture": "老式砖楼", "mood": "压抑"})
    response = rig.client.get(f"/api/projects/{rig.nid}/studio/bible",
                              headers={"x-session-token": "valid-session"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["contract"] == "studio-bible/1"
    assert body["advisory_only"] is True and body["execution_authority"] is False
    assert body["unknown_is_explicit"] is True
    entry = next(row for row in body["character_bible"]["entries"] if row["character_id"] == "c1")
    covered = {row["field"]: row for row in entry["dimensions"]}
    assert covered["identity"]["authored"] is True
    assert covered["appearance"]["value"] == "瘦高，短发"
    assert covered["appearance"]["authoritative"] is True
    # Nothing authored behaviour or relationships, so those stay explicitly unknown.
    assert covered["behavior"]["value"] == "UNKNOWN"
    assert covered["relationship"]["value"] == "UNKNOWN"


def test_bible_route_requires_authority(rig):
    response = rig.client.get(f"/api/projects/{rig.nid}/studio/bible", headers={"x-session-token": "nope"})
    assert response.status_code == 403


def test_bible_route_is_get_only(rig):
    spec = rig.client.get("/openapi.json").json()
    assert set(spec["paths"]["/api/projects/{nid}/studio/bible"]) == {"get"}
