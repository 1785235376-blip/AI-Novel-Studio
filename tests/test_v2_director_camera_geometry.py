"""Original File/PG owner geometry bridge; deterministic evidence, no model call."""
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace

import pytest

from test_v2_creative_foundation import rig
from test_v2_director_workspace_additive import rig as api_rig


def geometry(y=2, **patch):
    from app.experimental.director import CameraGrammar
    return CameraGrammar(coordinate_system="room-metres", axis=["a", "b"],
        character_positions={"a": {"x": 0, "y": 0}, "b": {"x": 4, "y": 0}},
        camera_position={"x": 2, "y": y}, **patch).model_dump()


def content(mode="DIRECTOR", authored=True):
    rows = [{"id": f"row-{n}", "number": n, "scene_id": "scene", "shot_size": "MEDIUM",
             "camera_angle": "EYE_LEVEL", "camera_motion": "STATIC",
             **({"camera_grammar": geometry(2 if n == 1 else -2)} if authored else {})} for n in (1, 2)]
    return {"mode": mode, "title": "Explicit authored geometry", "source_independent": True,
            "scenes": [{"id": "scene", "sequence": 1, "heading": "ROOM"}],
            "director_notes" if mode == "DIRECTOR" else "shots": rows}


def author_content(row):
    from app.creative.models import CreativeProductionDocumentIn
    return deepcopy({key: row[key] for key in CreativeProductionDocumentIn.model_fields if key in row})


def workspace(rig, creative=None):
    from app.creative.director_workspace import DirectorWorkspaceService
    owner = creative or rig.service
    return DirectorWorkspaceService(SimpleNamespace(store=owner.store, novels=rig.novels), owner)


def test_legacy_model_schemas_keep_exact_prebridge_hashes():
    from app.creative.models import DirectorModelOutput
    from app.creative.adaptation_models import AdaptationOutput
    from app.creative.storyboard_model import DirectorStoryboardModelOutput
    from app.creative.screenplay_model import DirectorScreenplaySceneOutput
    expected = {
        DirectorModelOutput: "78402bc5eff3e3cb81834c5d4cc0ccc5e33d630b059054ae9185a54852b73ca8",
        AdaptationOutput: "7a3a9a3f79e694d445b5a3ad289bbfed6f0a0caaf8b367a77e7e1c8aea4ed3df",
        DirectorStoryboardModelOutput: "674333af0f67d90f8d7af6284093b80b1ea591439b41c8281dcf835b826cae23",
        DirectorScreenplaySceneOutput: "7263335febb5d68396dcf63e4830265a7af7a6f1bf9b8687e288bdbdd084c241",
    }
    for cls, digest in expected.items():
        raw = json.dumps(cls.model_json_schema(), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        assert hashlib.sha256(raw.encode()).hexdigest() == digest
        assert "camera_grammar" not in raw


@pytest.mark.parametrize("field", ["absent", "null"])
def test_unset_geometry_keeps_legacy_serialization(field):
    from app.creative.models import DirectorSceneNote, ShotCard
    for cls in (DirectorSceneNote, ShotCard):
        original = {"id": "row", "number": 1, "scene_id": "scene"}
        legacy = cls.model_validate(original).model_dump()
        candidate = {**original, **({"camera_grammar": None} if field == "null" else {})}
        assert cls.model_validate(candidate).model_dump() == legacy
        assert "camera_grammar" not in legacy


@pytest.mark.parametrize("value", [None, {}, geometry()])
def test_model_director_and_scene_outputs_reject_authored_geometry(value):
    from app.creative.models import DirectorModelNote
    from app.creative.storyboard_model import DirectorStoryboardModelNote
    from app.creative.screenplay_model import DirectorScreenplaySceneNote
    planning = {"rationale": "Choice", "sequence_reason": "Order", "duration_reason": "Estimate",
                "uncertainty": "Human review", "assumptions": ["Staged fiction"]}
    for cls in (DirectorModelNote, DirectorStoryboardModelNote, DirectorScreenplaySceneNote):
        raw = {"id": "note", "number": 1, "scene_id": "scene", "planning": planning, "camera_grammar": value}
        if cls is DirectorStoryboardModelNote: raw["source_shot_id"] = "shot"
        with pytest.raises(ValueError, match="extra_forbidden"):
            cls.model_validate(raw, strict=True)
    from app.creative.adaptation_models import AdaptedScene
    with pytest.raises(ValueError, match="ADAPTATION_HOST_SOURCE_AND_CHARACTER_BINDING_REQUIRED"):
        AdaptedScene.model_validate({"id": "scene", "sequence": 1, "heading": "ROOM",
                                    "director_notes": [{"id": "nested", "camera_grammar": value}]})


@pytest.mark.parametrize("patch", [
    {"camera_position": {"x": "1", "y": 0}}, {"camera_position": {"x": True, "y": 0}},
    {"camera_position": {"x": float("nan"), "y": 0}}, {"camera_position": {"x": 1000001, "y": 0}},
    {"camera_position": {"x": 1, "y": 0, "z": 1}}, {"axis": ["a"]}, {"axis": ["a", "a"]},
    {"axis": ["a", "missing"]}, {"intentional_axis_crossing": True}, {"intentions": ["JUMP_CUT"]},
    {"inferred_from_text": True}, {"intentional_axis_crossing": "true"},
])
def test_original_closed_grammar_refuses_invalid_or_coerced_geometry(patch):
    from app.creative.models import DirectorSceneNote, ShotCard
    for cls in (DirectorSceneNote, ShotCard):
        with pytest.raises(ValueError):
            cls.model_validate({"id": "r", "number": 1, "scene_id": "scene", "camera_grammar": {**geometry(), **patch}})


@pytest.mark.parametrize("label", ["", "   ", "a" * 241, "a\n"])
def test_new_creative_position_labels_are_bounded_without_changing_legacy_grammar(label):
    from app.creative.models import ShotCard
    from app.experimental.director import CameraGrammar
    raw = {**geometry(), "axis": [], "character_positions": {label: {"x": 0, "y": 0}}}
    # Legacy grammar remains independently accepted; only this new bridge is stricter.
    CameraGrammar.model_validate(raw)
    with pytest.raises(ValueError, match="CREATIVE_CAMERA_POSITION_LABEL_INVALID"):
        ShotCard.model_validate({"id": "r", "number": 1, "scene_id": "scene", "camera_grammar": raw})


def test_new_creative_position_labels_reject_normalization_collisions():
    from app.creative.models import ShotCard
    raw = {**geometry(), "axis": [], "character_positions": {"a": {"x": 0, "y": 0}, " a ": {"x": 1, "y": 0}}}
    with pytest.raises(ValueError, match="CREATIVE_CAMERA_POSITION_LABEL_DUPLICATE"):
        ShotCard.model_validate({"id": "r", "number": 1, "scene_id": "scene", "camera_grammar": raw})


@pytest.mark.parametrize("mode", ["DIRECTOR", "STORYBOARD"])
def test_original_owner_save_cas_reopen_history_and_exact_source_projection(rig, mode):
    from app.creative.service import CreativeService, document_digest
    from app.experimental.store import ExperimentalStore
    from app.services.v1_capability_service import CapabilityVersionConflict
    row = rig.service.create(rig.nid, rig.scope, rig.actor, content(mode, authored=False))
    assert "camera_geometry" not in workspace(rig).projection(rig.nid, rig.scope, row["id"])
    edited = author_content(row)
    field = "director_notes" if mode == "DIRECTOR" else "shots"
    for n, item in enumerate(edited[field]): item["camera_grammar"] = geometry(2 if n == 0 else -2)
    saved = rig.service.update(rig.nid, rig.scope, rig.actor, row["id"], 1, edited)
    other = CreativeService(ExperimentalStore(rig.root, rig.backend, rig.url), rig.novels, rig.chapters)
    assert other.get(rig.nid, rig.scope, row["id"])[field] == saved[field]
    with pytest.raises(CapabilityVersionConflict): other.update(rig.nid, rig.scope, "other", row["id"], 1, edited)
    before = rig.store.read(rig.nid, rig.scope)
    result = workspace(rig, other).projection(rig.nid, rig.scope, row["id"])["camera_geometry"]
    assert result["document_snapshot"] == {"id": row["id"], "version": 2, "digest": document_digest(saved)}
    assert result["source_field"] == field and result["evidence_kind"] == "SUPPLEMENTARY_AUTHORED_GEOMETRY"
    assert result["model_called"] is result["visual_analysis"] is result["auto_modify"] is False
    assert result["findings"][0]["state"] == "AXIS_CROSSING"
    assert result["findings"][0]["cross_products"] == ["8", "-8"]
    assert rig.store.read(rig.nid, rig.scope) == before
    unrelated = author_content(saved); unrelated["title"] = "Retitled only"
    revised = other.update(rig.nid, rig.scope, rig.actor, row["id"], 2, unrelated)
    assert revised[field] == saved[field]
    history = other.history(rig.nid, rig.scope, row["id"])
    assert [v["version"] for v in history["items"]] == [1, 2, 3]
    assert all("camera_grammar" not in item for item in history["items"][0][field])


def test_original_checker_reused_and_incomplete_geometry_stays_unknown(rig, monkeypatch):
    from app.creative import director_camera_geometry as bridge
    from app.experimental.director import camera_checks
    calls = []
    def checked(rows): calls.append(deepcopy(rows)); return camera_checks(rows)
    monkeypatch.setattr(bridge, "camera_checks", checked)
    raw = content(); raw["director_notes"][1].pop("camera_grammar")
    row = rig.service.create(rig.nid, rig.scope, rig.actor, raw)
    result = workspace(rig).projection(rig.nid, rig.scope, row["id"])["camera_geometry"]
    assert len(calls) == 1 and calls[0][1]["director"] is None
    assert result["findings"][0]["state"] == "INSUFFICIENT_EVIDENCE"
    malformed = deepcopy(row); malformed["scenes"] = []
    malformed["director_notes"][1]["camera_grammar"] = geometry(-2)
    result = bridge.project_camera_geometry(malformed, "a" * 64)
    assert result["findings"][0]["state"] == "INSUFFICIENT_EVIDENCE"
    for note in malformed["director_notes"]: note.pop("scene_id")
    assert bridge.project_camera_geometry(malformed, "a" * 64)["findings"][0]["state"] == "INSUFFICIENT_EVIDENCE"


@pytest.mark.parametrize("scene", [None, "", "unowned"])
def test_original_storyboard_does_not_allow_unbound_shot_scenes(scene):
    from app.creative.models import CreativeProductionDocumentIn
    raw = content("STORYBOARD")
    if scene is None: raw["shots"][0].pop("scene_id")
    else: raw["shots"][0]["scene_id"] = scene
    with pytest.raises(ValueError): CreativeProductionDocumentIn.model_validate(raw)


@pytest.mark.parametrize("change", ["scene", "coordinate_system", "position", "axis", "on_axis", "same_side", "override"])
def test_scene_geometry_and_authored_override_are_not_guessed(rig, change):
    raw = content(); g = raw["director_notes"][1]["camera_grammar"]
    expected = "INSUFFICIENT_EVIDENCE"
    if change == "scene":
        raw["scenes"].append({"id": "other", "sequence": 2, "heading": "HALL"}); raw["director_notes"][1]["scene_id"] = "other"
    elif change == "coordinate_system": g["coordinate_system"] = "other"
    elif change == "position": g["character_positions"]["a"]["x"] = 1
    elif change == "axis": g["axis"] = ["b", "a"]
    elif change == "on_axis": g["camera_position"]["y"] = 0
    elif change == "same_side": g["camera_position"]["y"] = 4; expected = "SAME_SIDE"
    else:
        g["intentional_axis_crossing"] = True; g["override_reason"] = "Deliberate spatial rupture"; expected = "INTENTIONAL_OVERRIDE"
    row = rig.service.create(rig.nid, rig.scope, rig.actor, raw)
    result = workspace(rig).projection(rig.nid, rig.scope, row["id"])["camera_geometry"]
    assert result["findings"][0]["state"] == expected
    assert rig.service.get(rig.nid, rig.scope, row["id"])["director_notes"][1]["camera_grammar"] == g


def test_geometry_survives_original_review_and_director_to_storyboard_derivation(rig):
    source = rig.service.create(rig.nid, rig.scope, rig.actor, {"mode": "SCREENPLAY", "title": "Authored script", "source_independent": True,
        "scenes": [{"id": "scene", "sequence": 1, "heading": "ROOM"}]})
    proposal = rig.service.proposals.create(rig.nid, rig.scope, rig.actor, {"source_document_id": source["id"], "expected_source_version": 1})
    notes = deepcopy(proposal["director_notes"]); notes[0]["camera_grammar"] = geometry()
    adopted = rig.service.proposals.review(rig.nid, rig.scope, rig.actor, proposal["id"], {"expected_version": proposal["version"],
        "reviewed_output_digest": proposal["output_digest"], "title": "Human authored geometry", "director_notes": notes})["document"]
    assert adopted["director_notes"][0]["camera_grammar"] == geometry()
    board = rig.service.derive(rig.nid, rig.scope, rig.actor, adopted["id"], {"expected_version": 1, "mode": "STORYBOARD", "shot_policy": "DIRECTOR_NOTES"})
    assert board["shots"][0]["camera_grammar"] == geometry()
    assert board["shots"][0]["director_notes"][0]["camera_grammar"] == geometry()
    assert rig.service.get(rig.nid, rig.scope, adopted["id"]) == adopted


def test_workspace_keeps_original_archive_scope_and_project_incarnation_fences(rig, monkeypatch):
    from app.experimental.common import StaleSourceError
    row = rig.service.create(rig.nid, rig.scope, rig.actor, content())
    owner = workspace(rig)
    with pytest.raises((FileNotFoundError, ValueError, StaleSourceError)):
        owner.projection(rig.nid, {**rig.scope, "branch_id": "foreign"}, row["id"])
    original = rig.service.store.incarnation
    monkeypatch.setattr(rig.service.store, "incarnation", lambda _: "file:00000000-0000-0000-0000-000000000000")
    with pytest.raises(StaleSourceError): owner.projection(rig.nid, rig.scope, row["id"])
    monkeypatch.setattr(rig.service.store, "incarnation", original)
    rig.service.archive(rig.nid, rig.scope, rig.actor, row["id"], 1)
    with pytest.raises(FileNotFoundError): owner.projection(rig.nid, rig.scope, row["id"])


@pytest.mark.file_backend_only
def test_mounted_original_save_and_workspace_route_reopen_geometry_with_authority(api_rig):
    from fastapi import HTTPException
    from app.creative.api import create_creative_router
    def authorize(nid, token, branch, permission):
        if token != "valid-session": raise HTTPException(403, {"code": "CREATIVE_AUTHORITY_INVALID"})
        return "phase14a-author", {"mode": "local", "novel_id": nid}
    api_rig.client.app.include_router(create_creative_router(api_rig.creative, authorize, lambda flag: None), prefix="/api")
    headers = {"x-session-token": "valid-session"}
    base = f"/api/projects/{api_rig.nid}/studio"
    documents = f"/api/novels/{api_rig.nid}/experimental/creative/documents"
    created = api_rig.client.post(documents, headers=headers, json=content())
    assert created.status_code == 201, created.text
    row = created.json(); assert row["director_notes"][0]["camera_grammar"] == geometry()
    url = base + "/director/workspace/" + row["id"]
    read = api_rig.client.get(url, headers=headers); assert read.status_code == 200, read.text
    assert read.json()["camera_geometry"]["findings"][0]["state"] == "AXIS_CROSSING"
    denied = api_rig.client.get(url, headers={"x-session-token": "other"}); assert denied.status_code == 403
    changed = author_content(row); changed["director_notes"][1]["camera_grammar"] = geometry(-2, intentional_axis_crossing=True, override_reason="Intentional reversal")
    saved = api_rig.client.put(documents + "/" + row["id"], headers=headers, json={**changed, "expected_version": 1})
    assert saved.status_code == 200, saved.text
    stale = api_rig.client.put(documents + "/" + row["id"], headers=headers, json={**changed, "expected_version": 1})
    assert stale.status_code == 409, stale.text
    reopened = api_rig.client.get(url, headers=headers).json()["camera_geometry"]
    assert reopened["document_snapshot"]["version"] == 2
    assert reopened["findings"][0]["state"] == "INTENTIONAL_OVERRIDE"
