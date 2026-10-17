"""Real File owner acceptance for the explicit Director-to-storyboard editor handoff.

This is persistence/CAS/exact-pin evidence, not browser navigation or socket E2E.
All direction is authored synthetic text; no model, renderer or media is needed.
"""
from copy import deepcopy
import hashlib
import json

import pytest

from test_v2_independent_workspace import rig, services

pytestmark = pytest.mark.file_backend_only


def fresh_file_workspace(rig):
    """Reconstruct repositories and every service owner, not just a cached view."""
    from app.config import Settings
    from app.repositories.factory import create_repository_bundle
    from app.services import ChapterService, NovelService

    bundle = create_repository_bundle(
        Settings(storage_backend="file", database_url="", novel_data=rig.root,
                 enable_cloud=False, mock_provider=True), data_root=rig.root)
    return services(rig.root, "file", "",
                    NovelService(bundle.novels, bundle.chapters), ChapterService(bundle.chapters))


def receipt_pin(receipt):
    # Independently verify the exported digest against the exact public snapshot.
    snapshot = receipt["document"]
    encoded = json.dumps(snapshot, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    assert hashlib.sha256(encoded).hexdigest() == receipt["document_digest"]
    assert "history" not in snapshot
    return {"id": snapshot["id"], "version": snapshot["version"],
            "digest": receipt["document_digest"]}


def forbid_implicit_write(*args, **kwargs):
    pytest.fail("A read attempted implicit derive, update, approval or execution")


@pytest.mark.parametrize("rig", ["file"], indirect=True)
def test_explicit_storyboard_edit_restarts_from_file_and_leaves_old_graph_pin_stale(rig, monkeypatch):
    from app.creative.graph import CreativeGraphService
    from app.creative.models import CreativeProductionDocumentIn
    from app.services.v1_capability_service import CapabilityVersionConflict

    creative = rig.service.creative
    chapter = rig.chapters.create(rig.nid, {
        "title": "Synthetic source", "content": "A visitor pauses at the doorway."})
    chapter = rig.chapters.get(chapter["id"])
    screenplay = creative.create(rig.nid, rig.scope, rig.actor, {
        "mode": "SCREENPLAY", "title": "Authored source", "source_chapter_ids": [chapter["id"]],
        "scenes": [{"id": "scene-1", "sequence": 1, "source_chapter_id": chapter["id"],
                    "heading": "INT. STUDIO", "action": "A visitor pauses at the doorway.",
                    "characters": ["visitor"]}]})
    source_pin = receipt_pin(creative.export(rig.nid, rig.scope, screenplay["id"]))
    director = creative.create_derived(rig.nid, rig.scope, rig.actor, {
        "mode": "DIRECTOR", "title": "Human-authored direction",
        "source_chapter_ids": [chapter["id"]], "scenes": screenplay["scenes"],
        "director_notes": [
            {"id": "note-2", "number": 2, "scene_id": "scene-1", "note": "Then turn",
             "shot_suggestion": "Turn toward the window", "lens": "85mm", "duration_seconds": 4},
            {"id": "note-1", "number": 1, "scene_id": "scene-1", "note": "Hold the doorway",
             "shot_suggestion": "Visitor held in negative space", "composition": "Doorway left",
             "lens": "50mm", "duration_seconds": 6, "emotion": "Hesitant"}]},
        source_documents={source_pin["id"]: {"version": source_pin["version"], "digest": source_pin["digest"]}})
    director_receipt = creative.export(rig.nid, rig.scope, director["id"])
    before_derive = json.loads(rig.raw_store.path(rig.nid, rig.scope).read_text(encoding="utf-8"))
    board = creative.derive(rig.nid, rig.scope, rig.actor, director["id"], {
        "expected_version": director["version"], "mode": "STORYBOARD", "shot_policy": "DIRECTOR_NOTES"})
    assert [shot["director_note_ids"] for shot in board["shots"]] == [["note-1"], ["note-2"]]
    assert [shot["frame_prompt"] for shot in board["shots"]] == [
        "Visitor held in negative space", "Turn toward the window"]
    assert [shot["lens"] for shot in board["shots"]] == ["50mm", "85mm"]
    assert board["source_documents"] == {director["id"]: {
        "version": director["version"], "digest": director_receipt["document_digest"]}}
    assert board["provenance"]["parameters"] == {
        "rule_version": "creative-director-shots-v1", "shot_policy": "DIRECTOR_NOTES"}
    assert board["provenance"]["model_called"] is False
    assert board["provenance"]["quality_verification"] == "HUMAN_REVIEW_REQUIRED"
    receipt = creative.export(rig.nid, rig.scope, board["id"])
    pin = receipt_pin(receipt)
    graphs = CreativeGraphService(rig.store, rig.service)
    graph = graphs.create(rig.nid, rig.scope, rig.actor, {
        "request_id": "explicit-storyboard-editor-pin", "definition": {
            "schema_version": 4, "title": "Exact storyboard handoff",
            "nodes": [{"id": "board", "definition_id": "storyboard_plan",
                       "parameters": {"document_snapshot": pin}}]}})
    assert graph["reference_states"] == [{"node_id": "board", "state": "CURRENT"}]
    path = rig.raw_store.path(rig.nid, rig.scope)
    before_edit_bytes = path.read_bytes()
    before_edit = json.loads(before_edit_bytes)
    assert before_edit["collections"][creative.COLLECTION][board["id"]] == board
    for row in (screenplay, director):
        assert before_edit["collections"][creative.COLLECTION][row["id"]] == before_derive["collections"][creative.COLLECTION][row["id"]]

    # Opening/exporting the saved draft is strictly read-only, before any edit.
    opened = fresh_file_workspace(rig)
    opened_graphs = CreativeGraphService(opened.store, opened)
    with monkeypatch.context() as guard:
        for target, name in ((opened.creative, "derive"), (opened.creative, "update"),
                             (opened.creative.proposals, "review"), (opened.creative.storyboards, "approve"),
                             (opened_graphs, "preflight"), (opened_graphs.executor, "create")):
            guard.setattr(target, name, forbid_implicit_write)
        assert opened.creative.get(rig.nid, rig.scope, pin["id"]) == board
        assert opened.creative.export(rig.nid, rig.scope, pin["id"]) == receipt
        assert opened_graphs.get(rig.nid, rig.scope, rig.actor, graph["id"]) == graph
    assert path.read_bytes() == before_edit_bytes

    edit = {key: deepcopy(board[key]) for key in CreativeProductionDocumentIn.model_fields if key in board}
    authored_fields = {"frame_prompt": "Human edit: visitor turns toward the window", "lens": "35mm",
                      "composition": "Visitor right, window left", "lighting": "Soft window light",
                      "camera_motion": "DOLLY", "duration_seconds": 8, "action": "Turn, then pause",
                      "sound": "Synthetic distant clock", "emotion": "Resolved", "characters": ["visitor"]}
    edit["shots"][0].update(authored_fields)
    changed = opened.creative.update(rig.nid, rig.scope, rig.actor, pin["id"], pin["version"], edit)
    assert changed["id"] == board["id"] and changed["version"] == board["version"] + 1
    assert changed["status"] == "DRAFT" and changed["provenance"] == board["provenance"]
    assert changed["source_documents"] == board["source_documents"]
    assert changed["shots"][1] == board["shots"][1]
    assert changed["shots"][0]["id"] == board["shots"][0]["id"]
    assert changed["shots"][0]["director_note_ids"] == ["note-1"]
    assert changed["history"] == [{key: value for key, value in board.items() if key != "history"}]
    after_edit_bytes = path.read_bytes()
    after_edit = json.loads(after_edit_bytes)
    expected = deepcopy(before_edit)
    expected["collections"][creative.COLLECTION][board["id"]] = changed
    assert after_edit == expected  # No graph repin, approval, proposal or execution row was written.
    assert after_edit_bytes != before_edit_bytes

    restarted = fresh_file_workspace(rig)
    assert restarted is not opened and restarted.creative.store is not opened.creative.store
    saved = restarted.creative.get(rig.nid, rig.scope, pin["id"])
    assert saved == after_edit["collections"][creative.COLLECTION][board["id"]] == changed
    for field, value in authored_fields.items():
        assert saved["shots"][0][field] == value
    new_receipt = restarted.creative.export(rig.nid, rig.scope, pin["id"])
    new_pin = receipt_pin(new_receipt)
    assert new_pin["id"] == pin["id"] and new_pin["version"] == 2 and new_pin["digest"] != pin["digest"]
    with pytest.raises(CapabilityVersionConflict):
        restarted.creative.update(rig.nid, rig.scope, rig.actor, pin["id"], pin["version"], edit)
    restored_graph = CreativeGraphService(restarted.store, restarted).get(rig.nid, rig.scope, rig.actor, graph["id"])
    assert restored_graph["reference_states"] == [{"node_id": "board", "state": "STALE"}]
    assert restored_graph["definition"] == graph["definition"]
    assert restored_graph["definition"]["nodes"][0]["parameters"]["document_snapshot"] == pin
    assert restarted.creative.get(rig.nid, rig.scope, director["id"]) == director
    assert restarted.creative.export(rig.nid, rig.scope, director["id"]) == director_receipt
    assert restarted.creative.get(rig.nid, rig.scope, screenplay["id"]) == screenplay
    assert restarted.creative.chapters.get(chapter["id"]) == chapter
    assert graphs.RUNS not in after_edit["collections"]
    assert path.read_bytes() == after_edit_bytes
