"""New Graph paths through original jobs/assets/review; synthetic HTTP only."""
from copy import deepcopy
import base64
import httpx
import pytest

from test_v2_graph_production_planning import documents, planning_graph
from test_v2_graph_image_nodes import node, edge, graph_owner, create_run, image_asset
from test_v2_independent_workspace import rig, png_bytes, reopened
from test_v2_manual_mask_owner import mask
from test_v2_discovered_image_production import discovery, owner
from test_v2_image_upscale import configured


def complete(e, graph, run, generate):
    runtime = graph.media_runtime
    run = runtime.preview(e.nid, e.scope, e.actor, run["id"],
        {"expected_version": run["version"], "node_id": generate}, lambda: None)
    preview = run["media_runtime"]["nodes"][0]["preview"]
    run = runtime.dispatch(e.nid, e.scope, e.actor, run["id"], {"expected_version": run["version"],
        "node_id": generate, "reviewed_preview_digest": preview["preview_digest"]}, lambda: None)
    job = run["media_runtime"]["nodes"][0]["execution"]["job"]
    run = runtime.execute_job(e.nid, e.scope, e.actor, run["id"], {"expected_version": run["version"],
        "node_id": generate, "expected_job_version": job["version"], "expected_request_digest": job["request_digest"]}, lambda: None)
    job = run["media_runtime"]["nodes"][0]["execution"]["job"]
    assert run["current_node_id"] == "review" and job["status"] == "AWAITING_REVIEW"
    candidate = job["output_candidate"]
    with pytest.raises(FileNotFoundError): e.service.asset(e.nid, e.scope, candidate["id"])
    run = runtime.review(e.nid, e.scope, e.actor, run["id"], {"expected_version": run["version"],
        "node_id": "review", "expected_job_version": job["version"], "expected_request_digest": job["request_digest"],
        "reviewed_output_digest": candidate["digest"]}, lambda: None)
    assert run["status"] == "SUCCEEDED" and run["reviewed"]
    return run, job, preview


def test_graph_director_storyboard_style_image_job_review_binds_document_provenance(rig, monkeypatch):
    e = rig
    _, registry, adapter = discovery(e.root, "AUTOMATIC1111")
    production = owner(registry, monkeypatch, e)
    graph = graph_owner(e, monkeypatch, production)
    director, board = documents(e)
    value = planning_graph(director, board)
    value["nodes"].extend([node("generate", "image_generate", {"operation_id": "m5.image.t2i",
        "provider_id": adapter.candidate["provider_id"], "model_id": adapter.candidate["id"]}), node("review", "media_review")])
    value["edges"].extend([edge("style", "prompt", "generate", "prompt"), edge("generate", "candidate", "review", "candidate")])
    data, posts = png_bytes(), []
    def post(url, **kwargs):
        posts.append(deepcopy(kwargs))
        return httpx.Response(200, json={"images": [base64.b64encode(data).decode()]}, request=httpx.Request("POST", url))
    monkeypatch.setattr(adapter.delegate.transport, "post", post)
    _, run = create_run(e, graph, value)
    run, job, preview = complete(e, graph, run, "generate")
    assert len(posts) == 1 and "35mm" in posts[0]["json"]["prompt"]
    assert preview["command"]["source_snapshots"][0]["id"] == board["id"]
    formal = e.service.asset(e.nid, e.scope, job["output_candidate"]["id"])
    assert formal["version"] == 2
    with e.service._asset_scope(e.nid, e.scope):
        origin = e.assets.get(formal["id"], actor_id=e.actor)["_studio_result_origin"]
    assert origin["sources"][0]["id"] == board["id"]
    assert e.service.creative.get(e.nid, e.scope, director["id"]) == director


@pytest.mark.parametrize("scale", [2, 4])
def test_graph_upscale_uses_original_job_private_review_proof_and_reopen(mask, tmp_path, monkeypatch, scale):
    e = mask
    discovery, adapter, production, wire, command = configured(e, tmp_path, monkeypatch, scale)
    graph = graph_owner(e, monkeypatch, production)
    source = command["image_source"]
    value = {"schema_version": 4, "title": "SYNTHETIC graph upscale", "nodes": [
        node("source", "asset_reference", image_asset(source["id"], version=source["version"], digest=source["digest"])),
        node("upscale", "image_upscale", {"provider_id": adapter.candidate["provider_id"],
            "model_id": adapter.candidate["id"], "parameters": {"scale": scale}}), node("review", "media_review")],
        "edges": [edge("source", "asset", "upscale", "source"), edge("upscale", "candidate", "review", "candidate")]}
    _, run = create_run(e, graph, value)
    run, job, preview = complete(e, graph, run, "upscale")
    assert preview["command"]["operation_id"] == "m5.image.upscale" and preview["command"]["prompt"] == ""
    assert job["processing_proof"]["scale"] == scale
    assert job["processing_proof"]["output_width"] == 64 * scale
    assert len([url for url, _ in wire.calls if url.endswith("/prompt")]) == 1
    from app.creative.graph import CreativeGraphService
    workspace = reopened(e)
    restarted_production = owner(production.image_registry, monkeypatch, type("Env", (), {
        "service": workspace, "nid": e.nid, "scope": e.scope, "actor": e.actor, "root": e.root})())
    restarted = CreativeGraphService(workspace.store, workspace)
    restarted.configure_media(restarted_production)
    assert restarted.get_run(e.nid, e.scope, e.actor, run["id"])["status"] == "SUCCEEDED"
    assert discovery.center.lifecycle.start.call_count == 0
