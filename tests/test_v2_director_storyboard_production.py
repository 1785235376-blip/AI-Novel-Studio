"""Additive visual direction and shot planning on original Creative owners.

All works and model output are synthetic. File and real PostgreSQL profiles
exercise the same API, scope-atomic storage, CAS, review and source guards.
"""
import copy
import hashlib
import json

import pytest

from test_v2_creative_foundation import rig, client, payload, public
from test_r3_mounted_contracts import mounted, prefix, checked, scoped
from test_v2_creative_workflows import (
    broker_app, creative_model, note, review_body, route, model_action,
    model_dispatch, model_settle,
)


def target(**changes):
    return {"style": "Ink illustration", "atmosphere": "Quiet uncertainty",
            "reference_works": ["Synthetic visual study"], "color": "Blue and ochre",
            "rhythm": "Hold, then cut", **changes}


def rich_note(**changes):
    return note(**{"shot_suggestion": "The visitor framed beyond a doorway", "composition": "Negative space on the left",
                "lens": "50mm", "character_state": "Alert but hesitant",
                "performances": [{"character": "visitor", "action": "Pause at the doorway",
                               "expression": "Tense eyes", "state": "Listening"}], **changes})


def independent_direction(**changes):
    return {"mode": "DIRECTOR", "title": "Synthetic short commercial", "source_independent": True,
            "scenes": [{"id": "scene-1", "sequence": 1, "heading": "INT. STUDIO",
                        "action": "A visitor pauses.", "characters": ["visitor"], "emotion": "Uncertain"}],
            "visual_target": target(), "director_notes": [rich_note()], **changes}


def production_input(row):
    from app.creative.models import CreativeProductionDocumentIn
    return {key: copy.deepcopy(row[key]) for key in CreativeProductionDocumentIn.model_fields if key in row}


def test_legacy_default_serialization_and_director_request_schema_are_unchanged():
    from app.creative.models import CreativeDocumentIn, CreativeProductionDocumentIn, DirectorSceneNote, ShotCard
    from app.creative.generation import director_output_schema
    from app.experimental.store import canonical
    original = {"mode": "DIRECTOR", "title": "Legacy", "source_independent": True,
                "scenes": [{"id": "scene-1", "sequence": 1, "heading": "ROOM"}], "director_notes": [note()]}
    assert CreativeProductionDocumentIn.model_validate(original).model_dump() == CreativeDocumentIn.model_validate(original).model_dump()
    old = DirectorSceneNote.model_validate(note()).model_dump()
    explicit_null = DirectorSceneNote.model_validate({**note(), "shot_suggestion": None, "composition": None,
        "lens": None, "character_state": None, "performances": None}).model_dump()
    assert old == explicit_null and set(old) == set(note())
    shot = ShotCard(id="s", number=1, scene_id="scene-1").model_dump()
    assert "characters" not in shot and "emotion" not in shot
    legacy_schema = director_output_schema()
    # Captured from a79b7f9's original DirectorModelOutput, independently
    # evaluated before this extension; prevents default request digest drift.
    assert hashlib.sha256(canonical(legacy_schema).encode("utf-8")).hexdigest() == "b582b2a9e4ec8839103f1557e7002e326a17ad3090824cd62fc422b40fa1199d"
    assert "DirectorPerformance" not in legacy_schema["$defs"]
    assert not {"shot_suggestion", "composition", "lens", "character_state", "performances"} & set(legacy_schema["$defs"]["DirectorModelNote"]["properties"])
    assert "DirectorPerformance" in director_output_schema(production=True)["$defs"]


def test_shot_identity_visual_target_mode_and_explicit_policy_are_closed():
    from app.creative.models import CreativeProductionDocumentIn, CreativeDocumentDerive, ShotCard
    with pytest.raises(ValueError, match="DUPLICATE_SHOT_CHARACTER"):
        ShotCard(id="shot-1", number=1, scene_id="scene-1", characters=["visitor", "visitor"])
    with pytest.raises(ValueError, match="VISUAL_TARGET_MODE_REQUIRED"):
        CreativeProductionDocumentIn(mode="SCREENPLAY", title="Only screenplay", source_independent=True, visual_target=target())
    with pytest.raises(ValueError, match="SHOT_POLICY_MODE_REQUIRED"):
        CreativeDocumentDerive(expected_version=1, mode="PRODUCTION", shot_policy="DIRECTOR_NOTES")
    with pytest.raises(ValueError):
        CreativeDocumentDerive(expected_version=1, mode="STORYBOARD", shot_policy="ARBITRARY")


@pytest.mark.parametrize("changes", [
    {"visual_target": {"style": "x" * 2001}},
    {"visual_target": {"reference_works": ["x"] * 21}},
    {"visual_target": {"download_model": True}},
    {"director_notes": [rich_note(performances=[{"character": "visitor"}, {"character": "visitor"}])]},
    {"director_notes": [rich_note(performances=[{"character": "visitor", "state": "x" * 2001}])]},
])
def test_strict_bounded_visual_direction_rejects_invalid_data(rig, changes):
    with pytest.raises(ValueError):
        rig.service.create(rig.nid, rig.scope, rig.actor, independent_direction(**changes))
    assert rig.service.list(rig.nid, rig.scope) == []


def test_independent_director_and_storyboard_persist_without_novel_source(rig):
    from app.creative.service import CreativeService
    from app.experimental.store import ExperimentalStore
    before = copy.deepcopy(rig.chapters.get(rig.chapter["id"]))
    director = rig.service.create(rig.nid, rig.scope, rig.actor, independent_direction())
    storyboard = rig.service.create(rig.nid, rig.scope, rig.actor, {
        "mode": "STORYBOARD", "title": "Independent image sequence", "source_independent": True,
        "scenes": director["scenes"], "shots": [{"id": "shot-1", "number": 1, "scene_id": "scene-1",
            "characters": ["visitor"], "emotion": "Curious", "lens": "35mm", "composition": "Centered",
            "camera_motion": "DOLLY", "duration_seconds": 4, "action": "Look up", "sound": "Synthetic rain"}]})
    assert director["source_evidence"] == director["source_documents"] == {}
    assert storyboard["source_evidence"] == storyboard["source_documents"] == {}
    reopened = CreativeService(ExperimentalStore(rig.root, rig.backend, rig.url), rig.novels, rig.chapters)
    assert reopened.get(rig.nid, rig.scope, director["id"]) == director
    assert reopened.get(rig.nid, rig.scope, storyboard["id"]) == storyboard
    assert rig.chapters.get(rig.chapter["id"]) == before


def test_explicit_director_note_derivation_keeps_each_shot_and_source_immutable(rig):
    source = rig.service.create(rig.nid, rig.scope, rig.actor, independent_direction(director_notes=[
        rich_note(id="direction-2", number=2, lens="85mm", emotion="Relieved"), rich_note()]))
    result = rig.service.derive(rig.nid, rig.scope, rig.actor, source["id"], {
        "expected_version": 1, "mode": "STORYBOARD", "shot_policy": "DIRECTOR_NOTES"})
    assert source == rig.service.get(rig.nid, rig.scope, source["id"])
    assert result["id"] != source["id"] and len(result["shots"]) == 2
    assert result["visual_target"] == source["visual_target"]
    assert [shot["number"] for shot in result["shots"]] == [1, 2]
    assert [shot["lens"] for shot in result["shots"]] == ["50mm", "85mm"]
    assert [shot["emotion"] for shot in result["shots"]] == ["Hesitant", "Relieved"]
    assert all(shot["characters"] == ["visitor"] and shot["composition"] == "Negative space on the left" for shot in result["shots"])
    assert result["shots"][0]["frame_prompt"] == source["director_notes"][0]["shot_suggestion"]
    assert all(len(shot["director_notes"]) == 1 for shot in result["shots"])
    assert result["shots"][0]["director_notes"][0]["performances"][0]["expression"] == "Tense eyes"
    assert result["source_documents"] == {source["id"]: {"version": 1, "digest": rig.service.document_digest(source)}}
    assert result["provenance"]["model_called"] is False
    assert result["provenance"]["quality_verification"] == "HUMAN_REVIEW_REQUIRED"


def test_default_derivation_remains_one_shot_per_scene_and_keeps_old_provenance(rig):
    value = {**payload(rig), "mode": "DIRECTOR", "director_notes": [note(), note(id="direction-2", number=2)]}
    source = rig.service.create(rig.nid, rig.scope, rig.actor, value)
    result = rig.service.derive(rig.nid, rig.scope, rig.actor, source["id"], {"expected_version": 1, "mode": "STORYBOARD"})
    assert len(result["shots"]) == 1 and len(result["shots"][0]["director_notes"]) == 2
    assert "characters" not in result["shots"][0] and "emotion" not in result["shots"][0]
    assert result["provenance"]["parameters"] == {"rule_version": "creative-stage-copy-v1"}


@pytest.mark.parametrize("mode,notes", [("SCREENPLAY", []), ("DIRECTOR", [])])
def test_explicit_note_policy_rejects_missing_director_notes(rig, mode, notes):
    source = rig.service.create(rig.nid, rig.scope, rig.actor, {**payload(rig), "mode": mode, "director_notes": notes})
    before = rig.store.read(rig.nid, rig.scope)
    with pytest.raises(ValueError, match="DIRECTOR_SHOT_NOTES_REQUIRED"):
        rig.service.derive(rig.nid, rig.scope, rig.actor, source["id"], {"expected_version": 1, "mode": "STORYBOARD", "shot_policy": "DIRECTOR_NOTES"})
    assert rig.store.read(rig.nid, rig.scope) == before


def test_rich_derivation_cas_reauthorization_and_parent_edit_guards(rig):
    from app.experimental.common import StaleSourceError
    from app.services.v1_capability_service import CapabilityVersionConflict
    source = rig.service.create(rig.nid, rig.scope, rig.actor, independent_direction())
    body = {"expected_version": 1, "mode": "STORYBOARD", "shot_policy": "DIRECTOR_NOTES"}
    with pytest.raises(CapabilityVersionConflict):
        rig.service.derive(rig.nid, rig.scope, rig.actor, source["id"], {**body, "expected_version": 2})
    before = rig.store.read(rig.nid, rig.scope)
    calls = []
    def revoked():
        calls.append(1)
        if len(calls) == 2:
            raise PermissionError("synthetic-revocation")
    with pytest.raises(PermissionError):
        rig.service.derive(rig.nid, rig.scope, rig.actor, source["id"], body, reauthorize=revoked)
    assert rig.store.read(rig.nid, rig.scope) == before
    child = rig.service.derive(rig.nid, rig.scope, rig.actor, source["id"], body)
    rig.service.update(rig.nid, rig.scope, rig.actor, source["id"], 1, production_input(source))
    with pytest.raises(StaleSourceError):
        rig.service.get(rig.nid, rig.scope, child["id"])


def test_visual_goal_clear_restore_and_export_use_original_version_owner(rig):
    original = rig.service.create(rig.nid, rig.scope, rig.actor, independent_direction(visual_target=None))
    assert "visual_target" not in original
    changed = rig.service.update(rig.nid, rig.scope, rig.actor, original["id"], 1, {**production_input(original), "visual_target": target()})
    assert changed["visual_target"] == target()
    restored = rig.service.restore(rig.nid, rig.scope, rig.actor, original["id"], 2, 1)
    assert "visual_target" not in restored and restored["version"] == 3
    restored_goal = rig.service.restore(rig.nid, rig.scope, rig.actor, original["id"], 3, 2)
    assert restored_goal["visual_target"] == target()
    cleared = rig.service.update(rig.nid, rig.scope, rig.actor, original["id"], 4, {**production_input(restored_goal), "visual_target": None})
    assert "visual_target" not in cleared
    exported = rig.service.export(rig.nid, rig.scope, original["id"])
    assert exported["document"]["director_notes"][0]["performances"][0]["state"] == "Listening"


def test_proposal_visual_target_is_exact_reviewed_and_rich_output_preserves_source(rig):
    from app.creative.proposals import director_output_digest
    source = rig.service.create(rig.nid, rig.scope, rig.actor, payload(rig))
    row = rig.service.proposals.create(rig.nid, rig.scope, rig.actor, {
        "source_document_id": source["id"], "expected_source_version": 1, "visual_target": target()})
    assert row["output_digest"] == director_output_digest(row["director_notes"], target())
    reviewed = rig.service.proposals.review(rig.nid, rig.scope, rig.actor, row["id"],
        review_body(row, director_notes=[rich_note()], visual_target=target(color="Warm ochre")))
    result = reviewed["document"]
    assert result["visual_target"]["color"] == "Warm ochre"
    assert result["director_notes"][0]["composition"] == "Negative space on the left"
    assert result["provenance"]["reviewed_output_digest"] == director_output_digest(result["director_notes"], result["visual_target"])
    assert rig.service.get(rig.nid, rig.scope, source["id"]) == source


def test_changed_proposal_goal_cannot_bypass_exact_review(rig):
    source = rig.service.create(rig.nid, rig.scope, rig.actor, payload(rig))
    row = rig.service.proposals.create(rig.nid, rig.scope, rig.actor, {
        "source_document_id": source["id"], "expected_source_version": 1, "visual_target": target()})
    with rig.store.transaction(rig.nid, rig.scope) as state:
        state["collections"][rig.service.proposals.COLLECTION][row["id"]]["visual_target"]["style"] = "Changed after preview"
    with pytest.raises(ValueError, match="EXACT_REVIEW"):
        rig.service.proposals.review(rig.nid, rig.scope, rig.actor, row["id"], review_body(row))
    assert len(rig.service.list(rig.nid, rig.scope)) == 1


def test_production_fields_api_owner_private_response_and_derive(rig, client):
    base = f"/api/novels/{rig.nid}/experimental/creative"
    headers = {"X-Session-Token": "owner"}
    assert client.post(base + "/documents", headers={"X-Session-Token": "reader"}, json=independent_direction()).status_code == 403
    source = checked(client.post(base + "/documents", headers=headers, json=independent_direction()), 201)
    response = client.get(base + "/documents/" + source["id"], headers=headers)
    assert response.headers["cache-control"] == "no-store" and checked(response)["visual_target"] == target()
    result = checked(client.post(base + "/documents/" + source["id"] + "/derive", headers=headers,
        json={"expected_version": 1, "mode": "STORYBOARD", "shot_policy": "DIRECTOR_NOTES"}), 201)
    assert result["shots"][0]["characters"] == ["visitor"] and result["visual_target"] == target()
    assert client.post(base + "/documents", headers=headers,
        json={**independent_direction(), "visual_target": {"arbitrary": True}}).status_code == 422


def test_original_synthetic_director_executor_carries_goal_rich_notes_and_review(creative_model, monkeypatch):
    from app.runtime import runtime
    e = creative_model
    calls = []
    def stream(prompt, model, **kwargs):
        calls.append(prompt)
        yield json.dumps({"director_notes": [rich_note()]})
    monkeypatch.setattr(runtime.providers["mock"], "stream", stream)
    before = copy.deepcopy(e.chapters.get(e.chapter["id"]))
    source = checked(e.client.post(e.creative_base + "/documents", headers=e.headers, json={
        "mode": "SCREENPLAY", "title": "Synthetic screenplay", "source_chapter_ids": [e.chapter["id"]],
        "scenes": [{"id": "scene-1", "sequence": 1, "heading": "ROOM", "action": "Visitor pauses."}]}), 201)
    row = checked(e.client.post(e.creative_base + "/director-proposals", headers=e.headers,
        json={"source_document_id": source["id"], "expected_source_version": 1, "visual_target": target()}), 201)
    preview = model_action(e, row, "preview", route_id=route(e)["route_id"])
    assert not calls and "visual_target" in preview["model_preview"]["author"]["instruction"]
    result = model_settle(e, model_dispatch(e, preview))
    assert result["status"] == "NEEDS_REVIEW" and len(calls) == 1
    assert result["provenance"]["synthetic"] is True
    adopted = checked(e.client.post(e.creative_base + f'/director-proposals/{row["id"]}/review',
        headers=e.headers, json=review_body(result)))["document"]
    assert adopted["visual_target"] == target()
    assert adopted["director_notes"][0]["performances"][0]["expression"] == "Tense eyes"
    assert e.chapters.get(e.chapter["id"]) == before
    assert e.creative.get(e.nid, source["scope"], source["id"]) == source


def test_model_preview_fences_changed_visual_goal_without_dispatch(creative_model):
    e = creative_model
    source = checked(e.client.post(e.creative_base + "/documents", headers=e.headers, json={
        "mode": "SCREENPLAY", "title": "Synthetic screenplay", "source_chapter_ids": [e.chapter["id"]],
        "scenes": [{"id": "scene-1", "sequence": 1, "heading": "ROOM"}]}), 201)
    row = checked(e.client.post(e.creative_base + "/director-proposals", headers=e.headers,
        json={"source_document_id": source["id"], "expected_source_version": 1, "visual_target": target()}), 201)
    preview = model_action(e, row, "preview", route_id=route(e)["route_id"])
    with e.creative.store.transaction(e.nid, source["scope"]) as state:
        state["collections"][e.creative.proposals.COLLECTION][row["id"]]["visual_target"]["rhythm"] = "Changed after preview"
    response = e.client.post(e.creative_base + f'/director-proposals/{row["id"]}/dispatch', headers=e.headers,
        json={"expected_version": preview["version"], "reviewed_preview_digest": preview["model_preview"]["preview_digest"]})
    assert response.status_code == 409 and "VISUAL_TARGET_CHANGED" in response.text
    assert not e.manager.jobs
