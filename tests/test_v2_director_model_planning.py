"""Simulated model planning contracts; these tests do not evaluate AI quality."""
import copy
import json
from types import SimpleNamespace

import pytest

from app.creative.generation import DirectorModelCoordinator, MARKER, director_output_schema
from app.creative.models import CreativeDocumentIn, DirectorSceneNote
from app.creative.proposals import director_output_digest


def planning():
    return dict(rationale="Reveal hesitation before the answer", sequence_reason="Establish then isolate",
                duration_reason="Estimated reaction beat", uncertainty="Physical axis unknown",
                assumptions=["Assume enough room for the camera"],
                evidence=[dict(scene_id="scene-1", field="action", dialogue_index=None, excerpt="visitor waits")],
                alternatives=[dict(choice="Hold wide", tradeoff="Less access to expression")])


def source():
    return dict(title="Exact screenplay", source_chapter_ids=["chapter-1"], scenes=[
        dict(id="scene-1", sequence=1, heading="Courtyard", action="The visitor waits."),
        dict(id="scene-2", sequence=2, heading="Door", action="A door opens.")])


def note(**changes):
    return dict(id="n1", number=1, scene_id="scene-1", shot_size="WIDE", duration_seconds=8,
                planning=planning(), **changes)


def coordinator():
    src = source()
    proposals = SimpleNamespace(_current=lambda *args: src,
        documents=SimpleNamespace(chapters_for=lambda scope: SimpleNamespace(get=lambda ident: {"id": ident, "version": 7})))
    return DirectorModelCoordinator(proposals, None, None, None), SimpleNamespace(novel_id="novel", scope="scope"), src


def test_captured_input_exact_source_and_goal_no_implicit_context():
    owner, ctx, src = coordinator()
    goal = dict(style="Restrained", rhythm="Hold then cut", genre="Mystery")
    row = dict(title="Candidate", visual_target=goal)
    author = owner._author(ctx, row, dict(provider_id="mock", model_id="fake-local"))
    data = json.loads(author.instruction.removeprefix(MARKER))
    assert data["screenplay"] == {"title": src["title"], "scenes": src["scenes"]}
    assert data["visual_target"] == goal
    assert data["planning_contract"] == "SCENE_EVIDENCED_CANDIDATES_V1"
    assert data["output_schema"] == director_output_schema(production=True, planning=True)
    assert author.profile == "LOCAL_ONLY" and author.chapter_version == 7
    assert author.request_scope.source_mode == "NONE"


def test_mock_structured_sequence_preserves_rationale_assumptions_and_exact_digest():
    owner, ctx, _ = coordinator()
    first = note()
    second = dict(id="n2", number=2, scene_id="scene-2", shot_size="CLOSE_UP", duration_seconds=3,
                  planning={**planning(), "evidence": [dict(scene_id="scene-2", field="action", excerpt="door opens")]})
    notes = owner._parse(ctx, {"title": "Candidate"}, json.dumps({"director_notes": [second, first]}))
    assert [item["shot_size"] for item in notes] == ["WIDE", "CLOSE_UP"]
    assert sum(item["duration_seconds"] for item in notes) == 11
    assert notes[0]["planning"]["assumptions"] == planning()["assumptions"]
    edited = copy.deepcopy(notes)
    edited[0]["planning"]["rationale"] = "Human revision"
    assert director_output_digest(notes) != director_output_digest(edited)


@pytest.mark.parametrize("evidence", [
    dict(scene_id="missing", field="action", excerpt="visitor waits"),
    dict(scene_id="scene-2", field="action", excerpt="door opens"),
    dict(scene_id="scene-1", field="action", excerpt="invented event"),
    dict(scene_id="scene-1", field="action", excerpt=" "),
    dict(scene_id="scene-1", field="dialogue", dialogue_index=0, excerpt="hello"),
    dict(scene_id="scene-1", field="action", dialogue_index=0, excerpt="visitor waits"),
    dict(scene_id="scene-1", field="geometry", excerpt="visitor waits"),
])
def test_malformed_or_nonexistent_evidence_rejected(evidence):
    owner, ctx, _ = coordinator()
    candidate = note()
    candidate["planning"]["evidence"] = [evidence]
    with pytest.raises(ValueError):
        owner._parse(ctx, {"title": "Candidate"}, json.dumps({"director_notes": [candidate]}))


def test_legacy_payload_stays_identical_and_geometry_is_not_inferred():
    old = DirectorSceneNote(id="old", number=1, scene_id="scene-1").model_dump()
    assert "planning" not in old
    assert DirectorSceneNote.model_validate({**old, "planning": None}).model_dump() == old
    assert "planning" not in director_output_schema()["$defs"]["DirectorModelNote"]["properties"]
    candidate = CreativeDocumentIn(mode="DIRECTOR", **source(), director_notes=[note()])
    assert candidate.director_notes[0].planning.uncertainty == "Physical axis unknown"


def test_nested_evidence_is_validated_and_unreferenced_choices_need_assumptions():
    scene = source()["scenes"][0]
    bad = planning()
    bad["evidence"][0]["excerpt"] = "fabricated quote"
    with pytest.raises(ValueError):
        CreativeDocumentIn(mode="SCREENPLAY", title="Nested", scenes=[{**scene, "director_notes": [{"planning": bad}]}])
    with pytest.raises(ValueError):
        DirectorSceneNote(id="n", number=1, scene_id="scene-1", planning={**planning(), "evidence": [], "assumptions": []})


from test_v2_creative_foundation import rig, payload
from test_v2_creative_workflows import review_body


def test_original_explicit_adoption_keeps_planning_and_source_immutable(rig):
    source_payload = payload(rig)
    source_payload["scenes"][0]["id"] = "scene-1"
    source_payload["scenes"][0]["action"] = "The visitor waits."
    src = rig.service.create(rig.nid, rig.scope, rig.actor, source_payload)
    proposal = rig.service.proposals.create(rig.nid, rig.scope, rig.actor,
        dict(source_document_id=src["id"], expected_source_version=src["version"]))
    assert rig.service.list(rig.nid, rig.scope) == [src]
    accepted = rig.service.proposals.review(rig.nid, rig.scope, rig.actor, proposal["id"],
        review_body(proposal, director_notes=[note()]))
    assert accepted["document"]["director_notes"][0]["planning"] == planning()
    assert rig.service.get(rig.nid, rig.scope, src["id"]) == src


from test_v2_creative_workflows import broker_app, creative_model, model_ready, model_dispatch, model_settle
from test_r3_mounted_contracts import mounted, prefix, checked, scoped


def test_fake_transport_planning_uses_original_model_review_adoption(creative_model, monkeypatch):
    e = creative_model
    before = copy.deepcopy(e.chapters.get(e.chapter["id"]))
    src, row, calls = model_ready(e, monkeypatch, json.dumps({"director_notes": [note()]}))
    assert not calls
    ready = model_settle(e, model_dispatch(e, row))
    assert ready["status"] == "NEEDS_REVIEW" and len(calls) == 1
    assert ready["director_notes"][0]["planning"] == planning()
    result = checked(e.client.post(e.creative_base + f'/director-proposals/{row["id"]}/review',
        headers=e.headers, json=review_body(ready)))
    assert result["document"]["director_notes"][0]["planning"] == planning()
    assert e.creative.get(e.nid, src["scope"], src["id"]) == src
    assert e.chapters.get(e.chapter["id"]) == before
