"""Actual original File/PG planning authority; no model/GPU acceptance claim."""
from copy import deepcopy
import pytest
from pydantic import ValidationError

from app.creative.graph_models import parse_graph, catalog_definitions, validate_output_ports
from app.creative.graph_image_nodes import execute_image_local, image_command_fields
from app.creative.service import document_digest
from app.experimental.common import StaleSourceError
from test_v2_independent_workspace import rig, reopened
from test_v2_graph_image_nodes import node, edge, graph_owner, create_run, image_asset


def snapshot(row):
    return {"id": row["id"], "version": row["version"], "digest": document_digest(row)}


def documents(e):
    director = e.service.creative.create(e.nid, e.scope, e.actor, {
        "mode": "DIRECTOR", "title": "SYNTHETIC Director visual target", "source_independent": True,
        "visual_target": {"style": "watercolor", "atmosphere": "quiet", "color": "blue", "rhythm": "slow"},
        "scenes": [{"id": "scene-one", "sequence": 1, "heading": "SYNTHETIC garden", "characters": ["A"]}],
        "director_notes": [{"id": "note-one", "number": 1, "scene_id": "scene-one", "note": "author direction",
            "composition": "thirds", "lens": "35mm", "emotion": "hope", "performance": "pause"}]})
    board = e.service.creative.derive(e.nid, e.scope, e.actor, director["id"], {
        "expected_version": director["version"], "mode": "STORYBOARD"})
    return director, board


def planning_graph(director, board):
    return {"schema_version": 4, "title": "SYNTHETIC planning only", "nodes": [
        node("director", "director_plan", {"document_snapshot": snapshot(director)}),
        node("board", "storyboard_plan", {"document_snapshot": snapshot(board)}),
        node("prompt", "storyboard_prompt", {"shot_id": board["shots"][0]["id"]}),
        node("style", "image_style", {"style": "ink"})], "edges": [
        edge("director", "direction", "board", "direction"),
        edge("board", "storyboard", "prompt", "storyboard"),
        edge("prompt", "prompt", "style", "prompt")]}


@pytest.mark.parametrize("schema", [1, 2, 3])
@pytest.mark.parametrize("kind", ["image_style", "image_upscale", "director_plan", "storyboard_plan", "storyboard_prompt"])
def test_production_nodes_do_not_widen_old_schemas(schema, kind):
    with pytest.raises(ValidationError):
        parse_graph({"schema_version": schema, "title": "old", "nodes": [node("new", kind)]})


def test_original_catalog_is_exact_and_production_opt_in_is_finite():
    original = catalog_definitions(include_model=True, include_media=True, include_image=True)
    production = catalog_definitions(include_model=True, include_media=True, include_image=True, include_production=True)
    added = {row["id"] for row in production} - {row["id"] for row in original}
    assert added == {"image_style", "image_upscale", "director_plan", "storyboard_plan", "storyboard_prompt"}
    assert [row for row in production if row["id"] not in added] == original
    assert len(catalog_definitions()) == 7


def test_style_is_explicit_typed_and_preserves_bound_reference_metadata():
    refs = execute_image_local(node("refs", "image_reference", {"bindings": [{
        "port": "source_1", "weight": .4, "purpose": "character", "source_note": "SYNTHETIC authored"}]}),
        {"source_1": image_asset()})
    prompt = execute_image_local(node("prompt", "image_prompt", {"prompt": "garden"}), refs)
    styled = execute_image_local(node("style", "image_style", {"style": "ink"}), prompt)
    assert styled["prompt"]["prompt"] == "garden\nStyle: ink"
    assert styled["prompt"]["references"] == prompt["prompt"]["references"]
    command = image_command_fields(node("gen", "image_generate", {"operation_id": "m5.image.reference"}), styled)
    assert command["image_references"][0]["purpose"] == "character"
    assert command["image_references"][0]["source_note"] == "SYNTHETIC authored"
    with pytest.raises(ValidationError):
        execute_image_local(node("style", "image_style", {"style": "ink", "arbitrary": "data"}), prompt)


def test_upscale_is_separate_source_only_node_with_exact_original_snapshot():
    asset = image_asset(version=4)
    fields = image_command_fields(node("scale", "image_upscale"), {"source": asset})
    assert fields == {"prompt": "", "source_snapshots": [{"kind": "ASSET", "id": asset["asset_id"],
        "version": 4, "digest": asset["digest"], "asset_kind": "image"}],
        "image_source": {"kind": "ASSET", "id": asset["asset_id"], "version": 4, "digest": asset["digest"], "asset_kind": "image"}}
    with pytest.raises(ValueError):
        image_command_fields(node("scale", "image_upscale"), {"source": asset, "prompt": "unknown"})


@pytest.mark.parametrize("scale", [True, "2", 3, 8])
def test_upscale_scale_is_bounded_and_strict(scale):
    with pytest.raises(ValidationError):
        parse_graph({"schema_version": 4, "title": "scale", "nodes": [node("scale", "image_upscale", {
            "provider_id": "owned", "model_id": "owned", "parameters": {"scale": scale}})]})


def test_original_director_storyboard_graph_executes_and_reopens_without_mutating_sources(rig, monkeypatch):
    owner = graph_owner(rig, monkeypatch)
    director, board = documents(rig)
    before = deepcopy(rig.service.creative.get(rig.nid, rig.scope, director["id"]))
    graph, run = create_run(rig, owner, planning_graph(director, board))
    assert run["status"] == "SUCCEEDED" and not run["model_called"]
    row = owner._owned(rig.nid, rig.scope, rig.actor, owner.RUNS, run["id"])
    prompt = row["typed_outputs"]["style"]["prompt"]
    assert "35mm" in prompt["prompt"] and "watercolor" in prompt["prompt"] and "Style: ink" in prompt["prompt"]
    assert prompt["document_sources"][0]["id"] == board["id"]
    assert prompt["document_sources"][0]["digest"] == document_digest(board)
    assert rig.service.creative.get(rig.nid, rig.scope, director["id"]) == before
    import os, json
    from pathlib import Path
    capture = os.getenv("PHASE3_PLANNING_CAPTURE")
    if capture:
        path = Path(capture).resolve()
        assert path.is_relative_to(Path(__file__).resolve().parents[1] / ".runtime")
        path.write_text(json.dumps({"graph": graph, "run": run}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    from app.creative.graph import CreativeGraphService
    workspace = reopened(rig)
    restarted = CreativeGraphService(workspace.store, workspace)
    restarted.configure_media(owner.media_runtime.production)
    assert restarted.get_run(rig.nid, rig.scope, rig.actor, run["id"])["status"] == "SUCCEEDED"
    assert owner.planning_documents(rig.nid, rig.scope, rig.actor)["documents"] == [
        {"id": row["id"], "title": row["title"], "mode": row["mode"], "version": row["version"], "digest": document_digest(row)}
        for row in sorted((director, board), key=lambda row: (row["created_at"], row["id"]))]


def test_planning_edit_stales_graph_and_redacts_prior_outputs(rig, monkeypatch):
    owner = graph_owner(rig, monkeypatch)
    director, board = documents(rig)
    graph, run = create_run(rig, owner, planning_graph(director, board))
    from app.creative.models import CreativeProductionDocumentIn
    edit = {key: director[key] for key in CreativeProductionDocumentIn.model_fields if key in director}
    rig.service.creative.update(rig.nid, rig.scope, rig.actor, director["id"], director["version"], {
        **edit, "title": "SYNTHETIC changed"})
    stale = owner.get_run(rig.nid, rig.scope, rig.actor, run["id"])
    assert stale["stale"] is True and all(node["output"] is None for node in stale["node_states"].values())
    flight = owner.preflight(rig.nid, rig.scope, rig.actor, graph["id"], {"expected_version": graph["version"]})
    assert not flight["executable"]


def test_planning_ports_reject_unknown_and_wrong_modality():
    with pytest.raises(ValueError):
        validate_output_ports("storyboard_plan", {"storyboard": {"arbitrary": True}}, schema_version=4)
    with pytest.raises(ValueError):
        validate_output_ports("director_plan", {"direction": {"document_snapshot": {"id": "doc", "version": 1, "digest": "a"*64},
            "content": {"mode": "STORYBOARD", "title": "wrong"}}}, schema_version=4)


def test_preflight_blocks_missing_shot_without_original_job_admission(rig, monkeypatch):
    owner = graph_owner(rig, monkeypatch)
    director, board = documents(rig)
    value = planning_graph(director, board)
    value["nodes"][2]["parameters"]["shot_id"] = "missing-shot"
    graph = owner.create(rig.nid, rig.scope, rig.actor, {"request_id": "missing-shot", "definition": value})
    flight = owner.preflight(rig.nid, rig.scope, rig.actor, graph["id"], {"expected_version": graph["version"]})
    assert not flight["executable"]
    assert {"code": "CREATIVE_GRAPH_PLANNING_INPUT_CHANGED_OR_INVALID", "node_id": "prompt"} in flight["issues"]
    assert not owner.store.read(rig.nid, rig.scope)["collections"].get(owner.RUNS)


@pytest.mark.parametrize("invalid_version", [True, 1.0])
def test_planning_projection_rejects_corrupt_original_version_type(rig, monkeypatch, invalid_version):
    from app.creative.graph_planning_nodes import read_document
    owner = graph_owner(rig, monkeypatch)
    director, _ = documents(rig)
    with owner.store.transaction(rig.nid, rig.scope) as state:
        row = state["collections"][rig.service.creative.COLLECTION][director["id"]]
        row["version"] = invalid_version
        corrupt_digest = document_digest(row)
    value = node("director", "director_plan", {"document_snapshot": {
        "id": director["id"], "version": 1, "digest": corrupt_digest}})
    with pytest.raises(ValueError, match="CREATIVE_DOCUMENT_CORRUPT"):
        read_document(owner, rig.nid, rig.scope, value, lambda: None)


@pytest.mark.parametrize("source_note", ["", "x" * 501])
def test_graph_reference_note_uses_same_bounds_as_original_image_command(source_note):
    with pytest.raises(ValidationError):
        parse_graph({"schema_version": 4, "title": "bounded", "nodes": [node("refs", "image_reference", {
            "bindings": [{"port": "source_1", "weight": 1.0, "source_note": source_note}]})]})
