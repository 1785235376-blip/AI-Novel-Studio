"""Three-level media graph: upstream reviewed bytes, digests and failure fences.

Deterministic provider stand-ins; no real model inference.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json

from PIL import Image

from app.asset_providers import AssetGenerationResult
from app.creative.graph import CreativeGraphService
from test_studio_asset_query import rig
from test_studio_backend_integration_v2 import studio

pytestmark = __import__("pytest").mark.file_backend_only


def image_bytes(color):
    image = io.BytesIO()
    Image.new("RGB", (64, 64), color).save(image, format="PNG")
    return image.getvalue()


def edge(name, source, output, target, input_port):
    return {"id": name, "source_node_id": source, "source_port": output,
            "target_node_id": target, "target_port": input_port}


def entry(run, node):
    return next(item for item in run["media_runtime"]["nodes"] if item["node_id"] == node)


def job(run, node):
    return entry(run, node)["execution"]["job"]


def build(e, monkeypatch, calls, *, fail_third):
    generated = {name: image_bytes(color) for name, color in
                 (("first", (220, 40, 30)), ("second", (20, 120, 200)), ("third", (30, 200, 90)))}
    def generate(request, *, operation, images, reference_weights, mask=None):
        request.dispatch_guard()
        received = []
        for value in images:
            assert value.startswith("data:image/png;base64,")
            received.append(base64.b64decode(value.split(",", 1)[1], validate=True))
        calls.append({"operation": operation, "images": received})
        index = len(calls)
        if fail_third and index == 2:  # first t2i uses the fixture provider; this is the third node
            raise RuntimeError("synthetic third reply lost after dispatch")
        payload = generated[("first", "second", "third")[index - 1]]
        return AssetGenerationResult(request.provider_id, request.model_id,
                                     "data:image/png;base64," + base64.b64encode(payload).decode("ascii"))
    monkeypatch.setattr(e.provider, "image_recipe_descriptor", {
        "recipe_id": "automatic1111-img2img-v1", "components": {"model": "synthetic.safetensors"},
        "operations": ["t2i", "i2i", "inpaint"], "reference_limit": 1,
        "reference_semantics": "SINGLE_IMAGE_INITIALIZATION",
        "mask_semantics": "WHITE_KEEP_BLACK_REPAINT",
        "structural_only": True, "inference_verified": False}, raising=False)
    monkeypatch.setattr(e.provider, "generate_image", generate)
    graph = CreativeGraphService(e.workspace.store, e.workspace)
    graph.configure_media(e.production)
    params = {"provider_id": "automatic1111", "model_id": "synthetic.safetensors",
              "parameters": {"width": 64, "height": 64, "steps": 1, "seed": 7}}
    nodes = [
        {"id": "text", "definition_id": "text_input", "parameters": {"text": "three media levels"}},
        {"id": "prompt_a", "definition_id": "image_prompt"},
        {"id": "prompt_b", "definition_id": "image_prompt"},
        {"id": "prompt_c", "definition_id": "image_prompt"},
        {"id": "first", "definition_id": "image_generate", "parameters": {"operation_id": "m5.image.t2i", **params}},
        {"id": "review_a", "definition_id": "media_review"},
        {"id": "second", "definition_id": "image_generate", "parameters": {**params, "operation_id": "m5.image.i2i", "parameters": {"steps": 1, "seed": 7}}},
        {"id": "review_b", "definition_id": "media_review"},
        {"id": "third", "definition_id": "image_generate", "parameters": {**params, "operation_id": "m5.image.i2i", "parameters": {"steps": 1, "seed": 7}}},
        {"id": "review_c", "definition_id": "media_review"},
    ]
    edges = [
        edge("a", "text", "text", "prompt_a", "text"),
        edge("b", "text", "text", "prompt_b", "text"),
        edge("c", "text", "text", "prompt_c", "text"),
        edge("d", "prompt_a", "prompt", "first", "prompt"),
        edge("e", "first", "candidate", "review_a", "candidate"),
        edge("f", "review_a", "asset", "second", "source"),
        edge("g", "prompt_b", "prompt", "second", "prompt"),
        edge("h", "second", "candidate", "review_b", "candidate"),
        edge("i", "review_b", "asset", "third", "source"),
        edge("j", "prompt_c", "prompt", "third", "prompt"),
        edge("k", "third", "candidate", "review_c", "candidate"),
    ]
    saved = graph.create(e.nid, e.scope, e.actor, {"request_id": "three-media-levels",
        "definition": {"schema_version": 4, "title": "Three level media graph", "nodes": nodes, "edges": edges}})
    plan = graph.preflight(e.nid, e.scope, e.actor, saved["id"], {"expected_version": saved["version"]})
    assert plan["executable"], plan
    run = graph.create_run(e.nid, e.scope, e.actor, saved["id"], {
        "expected_graph_version": saved["version"], "reviewed_preflight_digest": plan["preflight_digest"],
        "request_id": "three-media-levels-run"})
    run = graph.action(e.nid, e.scope, e.actor, run["id"], "execute", {"expected_version": run["version"]})
    assert run["current_node_id"] == "first"
    return graph, generated, run


def drive(graph, e, run, node, review, *, expect_unknown=False):
    rid, rt = run["id"], graph.media_runtime
    run = rt.preview(e.nid, e.scope, e.actor, rid, {"node_id": node, "expected_version": run["version"]}, lambda: None)
    preview = entry(run, node)["preview"]
    run = rt.dispatch(e.nid, e.scope, e.actor, rid, {"node_id": node, "expected_version": run["version"],
        "reviewed_preview_digest": preview["preview_digest"]}, lambda: None)
    current = job(run, node)
    run = rt.execute_job(e.nid, e.scope, e.actor, rid, {"node_id": node, "expected_version": run["version"],
        "expected_job_version": current["version"], "expected_request_digest": current["request_digest"]}, lambda: None)
    current = job(run, node)
    if expect_unknown:
        assert current["status"] == "UNKNOWN"
        return run
    assert current["status"] == "AWAITING_REVIEW", current
    assert run["current_node_id"] == review
    return rt.review(e.nid, e.scope, e.actor, rid, {"node_id": review, "expected_version": run["version"],
        "expected_job_version": current["version"], "expected_request_digest": current["request_digest"],
        "reviewed_output_digest": current["output_candidate"]["digest"]}, lambda: None)


def stored(graph, e, run):
    return e.workspace.store.read(e.nid, e.scope)["collections"][graph.RUNS][run["id"]]


def test_three_level_media_chain_carries_reviewed_bytes_and_digests(studio, monkeypatch):
    e = studio
    calls = []
    graph, generated, run = build(e, monkeypatch, calls, fail_third=False)
    run = drive(graph, e, run, "first", "review_a")
    saved = stored(graph, e, run)
    first = saved["typed_outputs"]["review_a"]["asset"]
    first_bytes = e.workspace.assets._bin_path(first["asset_id"]).read_bytes()
    assert first_bytes == e.png
    assert hashlib.sha256(first_bytes).hexdigest() == first["digest"]
    run = drive(graph, e, run, "second", "review_b")
    saved = stored(graph, e, run)
    second = saved["typed_outputs"]["review_b"]["asset"]
    second_bytes = e.workspace.assets._bin_path(second["asset_id"]).read_bytes()
    assert hashlib.sha256(second_bytes).hexdigest() == second["digest"]
    assert calls[0]["operation"] == "i2i" and calls[0]["images"] == [first_bytes]
    assert saved["media_previews"]["second"]["command"]["source_snapshots"][0]["digest"] == first["digest"]
    run = drive(graph, e, run, "third", "review_c")
    saved = stored(graph, e, run)
    third = saved["typed_outputs"]["review_c"]["asset"]
    third_bytes = e.workspace.assets._bin_path(third["asset_id"]).read_bytes()
    assert hashlib.sha256(third_bytes).hexdigest() == third["digest"]
    assert calls[1]["images"] == [second_bytes]
    assert saved["media_previews"]["third"]["command"]["source_snapshots"][0]["digest"] == second["digest"]


def test_third_level_unknown_blocks_downstream_and_cannot_replay(studio, monkeypatch):
    e = studio
    calls = []
    graph, generated, run = build(e, monkeypatch, calls, fail_third=True)
    run = drive(graph, e, run, "first", "review_a")
    run = drive(graph, e, run, "second", "review_b")
    stored_after_second = stored(graph, e, run)
    second_asset = stored_after_second["typed_outputs"]["review_b"]["asset"]
    second_bytes = e.workspace.assets._bin_path(second_asset["asset_id"]).read_bytes()
    assert hashlib.sha256(second_bytes).hexdigest() == second_asset["digest"]
    run = drive(graph, e, run, "third", "review_c", expect_unknown=True)
    saved = stored(graph, e, run)
    assert "third" not in saved["typed_outputs"] and "review_c" not in saved["typed_outputs"]
    assert entry(run, "third")["execution"]["send_reserved"] is True
    unknown_job = job(run, "third")
    with __import__("pytest").raises(ValueError):
        graph.media_runtime.execute_job(e.nid, e.scope, e.actor, run["id"], {
            "node_id": "third", "expected_version": run["version"],
            "expected_job_version": unknown_job["version"],
            "expected_request_digest": unknown_job["request_digest"]}, lambda: None)
    for _ in range(3):
        observed = graph.get_run(e.nid, e.scope, e.actor, run["id"])
        assert job(observed, "third")["status"] == "UNKNOWN"
    assert calls[1]["images"] == [second_bytes]
    stopped = graph.action(e.nid, e.scope, e.actor, observed["id"], "cancel",
                           {"expected_version": observed["version"]})
    assert stopped["status"] == "CANCELLED"
    after = stored(graph, e, stopped)
    assert "third" not in after["typed_outputs"] and "review_c" not in after["typed_outputs"]
