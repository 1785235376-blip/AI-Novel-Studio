"""Multi-shot graph admission through original File/PostgreSQL owners, without dispatch."""
from copy import deepcopy
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.creative.graph import CreativeGraphService
from app.creative.graph_models import parse_graph
from app.creative.models import CreativeProductionDocumentIn
from app.creative.storyboard import storyboard_receipt
from test_v2_graph_image_nodes import edge, graph_owner, node
from test_v2_graph_production_planning import documents, snapshot
from test_v2_independent_workspace import reopened, rig
from test_v2_video_runtime_foundation import configured


def multishot_graph(e, command, count):
    _, board = documents(e)
    payload = {key: deepcopy(board[key])
        for key in CreativeProductionDocumentIn.model_fields if key in board}
    template = payload["shots"][0]
    payload["shots"] = [dict(deepcopy(template), id=f"shot-{index}", number=index)
        for index in range(1, count + 1)]
    board = e.service.creative.update(e.nid, e.scope, e.actor,
        board["id"], board["version"], payload)
    receipt = e.service.creative.storyboards.approve(e.nid, e.scope, e.actor, board["id"], {
        "expected_version": board["version"],
        "reviewed_content_digest": storyboard_receipt(board)["content_digest"]})
    board = e.service.creative.get(e.nid, e.scope, board["id"])
    nodes = [node("board", "storyboard_plan", {"document_snapshot": snapshot(board)})]
    edges = []
    for index, shot in enumerate(receipt["shots"], start=1):
        shot_id, video_id, review_id = f"shot-{index}", f"video-{index}", f"review-{index}"
        nodes.extend([
            node(shot_id, "storyboard_shot", {key: shot[key]
                for key in ("shot_id", "shot_version", "shot_digest")}),
            node(video_id, "video_generate", {"operation_id": "m7.video.t2v",
                "provider_id": command["provider_id"], "model_id": command["model_id"],
                "bind_shot": True, "allow_cloud": False, "prompt": "",
                "parameters": {}, "license_note": ""}),
            node(review_id, "media_review"),
        ])
        edges.extend([edge("board", "storyboard", shot_id, "storyboard"),
            edge(shot_id, "shot", video_id, "shot"),
            edge(video_id, "candidate", review_id, "candidate")])
    return {"schema_version": 5, "title": "SYNTHETIC multi-shot starter",
        "nodes": nodes, "edges": edges}, board


def test_four_branches_save_and_reopen_through_original_owner(rig, tmp_path, monkeypatch):
    discovery, production, _, wire, command = configured(rig, tmp_path, monkeypatch)
    owner = graph_owner(rig, monkeypatch, production)
    value, board = multishot_graph(rig, command, 4)
    expected = parse_graph(value).model_dump()
    assert len(expected["nodes"]) == 13 and len(expected["edges"]) == 12
    created = owner.create(rig.nid, rig.scope, rig.actor,
        {"request_id": uuid4().hex, "definition": value})
    saved = owner.save(rig.nid, rig.scope, rig.actor, created["id"],
        {"expected_version": created["version"], "definition": value})
    assert saved["version"] == created["version"] + 1
    assert owner.get(rig.nid, rig.scope, rig.actor, saved["id"])["definition"] == expected
    workspace = reopened(rig)
    restarted = CreativeGraphService(workspace.store, workspace)
    production.workspace = workspace
    restarted.configure_media(production)
    readback = restarted.get(rig.nid, rig.scope, rig.actor, saved["id"])
    assert readback["definition"] == expected and readback["version"] == saved["version"]
    assert workspace.creative.get(rig.nid, rig.scope, board["id"]) == board
    assert not wire.calls
    assert discovery.center.lifecycle.start.call_count == 0


def test_fifth_generator_still_rejected_without_persisting_graph(rig, tmp_path, monkeypatch):
    discovery, production, _, wire, command = configured(rig, tmp_path, monkeypatch)
    owner = graph_owner(rig, monkeypatch, production)
    value, _ = multishot_graph(rig, command, 5)
    assert len(value["nodes"]) == 16 and len(value["edges"]) == 15
    before = owner.list(rig.nid, rig.scope, rig.actor)
    with pytest.raises(ValidationError, match="CREATIVE_GRAPH_MEDIA_NODE_CAPACITY"):
        parse_graph(value)
    with pytest.raises(ValidationError, match="CREATIVE_GRAPH_MEDIA_NODE_CAPACITY"):
        owner.create(rig.nid, rig.scope, rig.actor,
            {"request_id": uuid4().hex, "definition": value})
    assert owner.list(rig.nid, rig.scope, rig.actor) == before
    assert not wire.calls
    assert discovery.center.lifecycle.start.call_count == 0
