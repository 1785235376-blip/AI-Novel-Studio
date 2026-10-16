"""Schema-5 Shot/Video authority through original File/PostgreSQL owners."""
from copy import deepcopy
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.creative.graph_models import parse_graph, catalog_definitions, validate_output_ports
from app.creative.graph_video_nodes import video_command_fields
from app.creative.storyboard import storyboard_receipt
from app.creative.service import document_digest
from app.experimental.common import StaleSourceError
from test_v2_independent_workspace import rig
from test_v2_graph_image_nodes import node, edge, graph_owner, create_run
from test_v2_graph_production_planning import documents, snapshot


def video_graph(board, receipt, *, generate=True):
    shot = receipt["shots"][0]
    nodes = [node("board", "storyboard_plan", {"document_snapshot": snapshot(board)}),
        node("shot", "storyboard_shot", {key: shot[key] for key in ("shot_id", "shot_version", "shot_digest")})]
    edges = [edge("board", "storyboard", "shot", "storyboard")]
    if generate:
        nodes.extend([node("video", "video_generate", {"operation_id": "m7.video.t2v",
            "provider_id": "configured", "model_id": "owned-model"}), node("review", "media_review")])
        edges.extend([edge("shot", "shot", "video", "shot"), edge("video", "candidate", "review", "candidate")])
    return {"schema_version": 5, "title": "SYNTHETIC reviewed storyboard video", "nodes": nodes, "edges": edges}


@pytest.mark.parametrize("schema", [1, 2, 3, 4])
@pytest.mark.parametrize("kind", ["storyboard_shot", "video_generate"])
def test_video_definitions_never_widen_old_graph_schemas(schema, kind):
    with pytest.raises(ValidationError):
        parse_graph({"schema_version": schema, "title": "legacy", "nodes": [node("new", kind)]})


def test_explicit_video_catalog_and_candidate_type_preserve_all_old_catalogs():
    assert len(catalog_definitions()) == 7
    previous = catalog_definitions(include_model=True, include_media=True, include_image=True, include_production=True)
    assert not {"storyboard_shot", "video_generate"} & {item["id"] for item in previous}
    values = catalog_definitions(include_media=True, include_production=True, include_video=True)
    assert {item["id"] for item in values} == {"text_input", "text_reference", "asset_reference",
        "director_plan", "storyboard_plan", "storyboard_shot", "video_generate", "media_review", "timeline_export"}
    assert next(item for item in values if item["id"] == "video_generate")["outputs"][0]["type"] == "VIDEO_CANDIDATE"
    candidate = {"owner": "image", "job_id": "synthetic", "job_version": 1, "request_digest": "a" * 64,
        "asset": {"asset_id": "synthetic", "version": 1, "digest": "b" * 64, "kind": "image"}}
    with pytest.raises(ValueError):
        validate_output_ports("video_generate", {"candidate": candidate}, schema_version=5)


def test_pinned_shot_projection_uses_original_history_without_mutating_documents(rig, monkeypatch):
    owner = graph_owner(rig, monkeypatch)
    _, board = documents(rig)
    receipt = storyboard_receipt(board)
    _, run = create_run(rig, owner, video_graph(board, receipt, generate=False))
    output = run["node_states"]["shot"]["output"]["shot"]
    assert output["shot_version"] == 1 and output["shot"] == receipt["shots"][0]["shot"]
    assert output["document_snapshot"]["digest"] == document_digest(board)
    assert not output["approved"] and not run["model_called"]
    assert rig.service.creative.get(rig.nid, rig.scope, board["id"]) == board
    changed = {key: deepcopy(board[key]) for key in ("mode", "title", "source_chapter_ids", "source_independent",
        "scenes", "director_notes", "shots", "video_plan", "visual_target") if key in board}
    changed["shots"][0]["lens"] = "50mm"
    rig.service.creative.update(rig.nid, rig.scope, rig.actor, board["id"], board["version"], changed)
    assert owner.get_run(rig.nid, rig.scope, rig.actor, run["id"])["stale"]


def test_video_preflight_requires_explicit_current_storyboard_approval(rig, monkeypatch):
    owner = graph_owner(rig, monkeypatch)
    _, board = documents(rig)
    graph = owner.create(rig.nid, rig.scope, rig.actor, {"request_id": uuid4().hex,
        "definition": video_graph(board, storyboard_receipt(board))})
    flight = owner.preflight(rig.nid, rig.scope, rig.actor, graph["id"], {"expected_version": graph["version"]})
    assert not flight["executable"]
    assert "STUDIO_STORYBOARD_APPROVAL_REQUIRED" in {issue["code"] for issue in flight["issues"]}
    approved = rig.service.creative.storyboards.approve(rig.nid, rig.scope, rig.actor, board["id"], {
        "expected_version": board["version"], "reviewed_content_digest": storyboard_receipt(board)["content_digest"]})
    current = rig.service.creative.get(rig.nid, rig.scope, board["id"])
    definition = video_graph(current, approved)
    _, run = create_run(rig, owner, definition)
    assert run["current_node_id"] == "video" and run["status"] == "WAITING_APPROVAL"
    fields = video_command_fields(next(item for item in definition["nodes"] if item["id"] == "video"),
        {"shot": run["node_states"]["shot"]["output"]["shot"]})
    assert fields["parameters"]["duration_seconds"] == current["shots"][0]["duration_seconds"]
    assert fields["source_snapshots"][0]["id"] == board["id"] and "STORYBOARD_SHOT" in fields["prompt"]
    assert not run["model_called"]


def test_shot_duration_and_reference_role_are_closed_before_original_video_admission():
    from app.creative.graph_models import ShotCard
    shot = ShotCard(id="s", number=1, scene_id="scene", duration_seconds=5).model_dump()
    ports = {"shot": {"document_snapshot": {"id": "board", "version": 1, "digest": "a" * 64},
        "shot_id": "s", "shot_version": 1, "shot_digest": "b" * 64, "shot": shot, "image_asset": None, "approved": True}}
    cfg = node("video", "video_generate", {"operation_id": "m7.video.t2v", "provider_id": "configured",
        "model_id": "owned", "parameters": {"duration_seconds": 6}})
    with pytest.raises(ValueError, match="DURATION_CONFLICT"):
        video_command_fields(cfg, ports)
    cfg["parameters"].update(parameters={}, operation_id="m7.video.v2v", reference_purpose="camera")
    reference = {"asset_id": "v", "version": 2, "digest": "c" * 64, "kind": "video"}
    value = video_command_fields(cfg, {"reference": reference})
    assert value["video_reference"]["source"]["version"] == 2 and value["video_reference"]["purpose"] == "camera"
    with pytest.raises(ValueError, match="REFERENCE"):
        video_command_fields(cfg, {"source": reference})


@pytest.mark.parametrize("operation", ["m7.video.t2v", "m7.video.i2v"])
def test_approved_storyboard_graph_to_original_video_job_private_review_and_reopen(rig, tmp_path, monkeypatch, operation):
    from test_v2_video_runtime_foundation import configured
    from test_v2_independent_workspace import reopened
    from app.creative.graph import CreativeGraphService
    e = rig
    discovery, production, adapter, wire, command = configured(e, tmp_path, monkeypatch)
    graph = graph_owner(e, monkeypatch, production)
    _, board = documents(e)
    if operation == "m7.video.i2v":
        from test_v2_independent_workspace import import_asset, png_bytes
        image = import_asset(e, data=png_bytes(), filename="synthetic-frame.png")
        shot = storyboard_receipt(board)["shots"][0]
        e.service.creative.storyboards.bind_image(e.nid, e.scope, e.actor, board["id"], shot["shot_id"], {
            "expected_version": board["version"], "shot_version": shot["shot_version"], "shot_digest": shot["shot_digest"],
            "asset": {"asset_id": image["id"], "version": image["version"], "digest": image["sha256"], "kind": "image"}})
        board = e.service.creative.get(e.nid, e.scope, board["id"])
    receipt = e.service.creative.storyboards.approve(e.nid, e.scope, e.actor, board["id"], {
        "expected_version": board["version"], "reviewed_content_digest": storyboard_receipt(board)["content_digest"]})
    board = e.service.creative.get(e.nid, e.scope, board["id"])
    value = video_graph(board, receipt)
    value["nodes"][2]["parameters"].update(operation_id=operation, provider_id=command["provider_id"], model_id=command["model_id"],
        parameters={"width": 64, "height": 64, "frame_rate": 8, "seed": 7})
    _, run = create_run(e, graph, value)
    runtime = graph.media_runtime
    run = runtime.preview(e.nid, e.scope, e.actor, run["id"], {"expected_version": run["version"], "node_id": "video"}, lambda: None)
    preview = run["media_runtime"]["nodes"][0]["preview"]
    assert preview["command"]["source_snapshots"][0]["id"] == board["id"]
    run = runtime.dispatch(e.nid, e.scope, e.actor, run["id"], {"expected_version": run["version"], "node_id": "video",
        "reviewed_preview_digest": preview["preview_digest"]}, lambda: None)
    def action(row):
        job = row["media_runtime"]["nodes"][0]["execution"]["job"]
        return {"expected_version": row["version"], "node_id": "video", "expected_job_version": job["version"],
            "expected_request_digest": job["request_digest"]}
    run = runtime.execute_job(e.nid, e.scope, e.actor, run["id"], action(run), lambda: None)
    assert run["media_runtime"]["nodes"][0]["execution"]["job"]["status"] == "REMOTE_RUNNING"
    run = runtime.refresh(e.nid, e.scope, e.actor, run["id"], action(run), lambda: None)
    job = run["media_runtime"]["nodes"][0]["execution"]["job"]
    assert run["current_node_id"] == "review" and job["status"] == "AWAITING_REVIEW"
    candidate = job["output_candidate"]
    with pytest.raises(FileNotFoundError):
        e.service.asset(e.nid, e.scope, candidate["id"])
    run = runtime.review(e.nid, e.scope, e.actor, run["id"], {"expected_version": run["version"], "node_id": "review",
        "expected_job_version": job["version"], "expected_request_digest": job["request_digest"],
        "reviewed_output_digest": candidate["digest"]}, lambda: None)
    assert run["status"] == "SUCCEEDED" and run["reviewed"]
    workspace = reopened(e)
    restarted = CreativeGraphService(workspace.store, workspace)
    production.workspace = workspace
    restarted.configure_media(production)
    assert restarted.get_run(e.nid, e.scope, e.actor, run["id"])["status"] == "SUCCEEDED"
    assert workspace.asset(e.nid, e.scope, candidate["id"])["version"] == 2
    assert sum(url.endswith("/prompt") for url, _ in wire.calls) == 1
    assert discovery.center.lifecycle.start.call_count == 0


@pytest.mark.parametrize("fault", ["edited", "disabled", "cancelled"])
def test_graph_video_poll_never_downloads_after_source_route_or_workflow_revocation(rig, tmp_path, monkeypatch, fault):
    from test_v2_video_runtime_foundation import configured
    from app.creative.models import CreativeProductionDocumentIn
    e = rig
    discovery, production, adapter, wire, command = configured(e, tmp_path, monkeypatch)
    graph = graph_owner(e, monkeypatch, production)
    _, board = documents(e)
    receipt = e.service.creative.storyboards.approve(e.nid, e.scope, e.actor, board["id"], {
        "expected_version": board["version"], "reviewed_content_digest": storyboard_receipt(board)["content_digest"]})
    board = e.service.creative.get(e.nid, e.scope, board["id"])
    value = video_graph(board, receipt)
    value["nodes"][2]["parameters"].update(provider_id=command["provider_id"], model_id=command["model_id"],
        parameters={"width": 64, "height": 64, "frame_rate": 8})
    _, run = create_run(e, graph, value)
    runtime = graph.media_runtime
    run = runtime.preview(e.nid, e.scope, e.actor, run["id"], {"expected_version": run["version"], "node_id": "video"}, lambda: None)
    preview = run["media_runtime"]["nodes"][0]["preview"]
    run = runtime.dispatch(e.nid, e.scope, e.actor, run["id"], {"expected_version": run["version"], "node_id": "video",
        "reviewed_preview_digest": preview["preview_digest"]}, lambda: None)
    job = run["media_runtime"]["nodes"][0]["execution"]["job"]
    run = runtime.execute_job(e.nid, e.scope, e.actor, run["id"], {"expected_version": run["version"], "node_id": "video",
        "expected_job_version": job["version"], "expected_request_digest": job["request_digest"]}, lambda: None)
    job = run["media_runtime"]["nodes"][0]["execution"]["job"]
    if fault == "edited":
        payload = {key: deepcopy(board[key]) for key in CreativeProductionDocumentIn.model_fields if key in board}
        payload["shots"][0]["camera_motion"] = "PAN"
        e.service.creative.update(e.nid, e.scope, e.actor, board["id"], board["version"], payload)
    elif fault == "disabled":
        discovery.disable(adapter.candidate["id"])
    else:
        run = graph.action(e.nid, e.scope, e.actor, run["id"], "cancel", {"expected_version": run["version"]})
        assert run["status"] == "CANCELLED" and run["node_states"]["shot"]["output"] is None
    before = len(wire.calls)
    with pytest.raises((ValueError, FileNotFoundError)):
        runtime.refresh(e.nid, e.scope, e.actor, run["id"], {"expected_version": run["version"], "node_id": "video",
            "expected_job_version": job["version"], "expected_request_digest": job["request_digest"]}, lambda: None)
    assert not any(url.endswith("/view") for url, _ in wire.calls[before:])
    assert sum(url.endswith("/prompt") for url, _ in wire.calls) == 1
