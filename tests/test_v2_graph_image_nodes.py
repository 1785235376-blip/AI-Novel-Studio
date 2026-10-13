"""Schema-4 image composition over original owners, never real model inference."""
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4
import base64
import hashlib
import json
import os
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from app.creative.graph import CreativeGraphService
from app.creative.graph_image_nodes import execute_image_local, image_command_fields
from app.creative.graph_models import (GraphImageInput, MediaNodeParameters, catalog_definitions,
    parse_graph, parse_graph_preflight, validate_output_ports)
from app.experimental.common import StaleSourceError
from test_v2_independent_workspace import rig, reopened, import_asset, png_bytes, branch_scope
from test_v2_manual_mask_owner import mask


DIGEST = "a" * 64
FLAGS = "narrative_production_v2,asset_lineage_v2,ai_execution_v2,model_broker_v2,author_context_inspector_v2"


def image_asset(asset_id="asset-one", **changes):
    return {"asset_id": asset_id, "version": 1, "digest": DIGEST, "kind": "image", **changes}


def node(node_id, definition_id, parameters=None):
    return {"id": node_id, "definition_id": definition_id, "parameters": parameters or {}}


def edge(source, source_port, target, target_port):
    return {"id": source + "_" + target + "_" + target_port, "source_node_id": source,
        "source_port": source_port, "target_node_id": target, "target_port": target_port}


def definition(assets=(), operation="m5.image.reference", provider="configured", model="owned-model"):
    values = [node("asset" + str(index), "asset_reference", asset) for index, asset in enumerate(assets)]
    links = []
    if assets:
        values.append(node("references", "image_reference", {"bindings": [
            {"port": "source_" + str(index + 1), "weight": 1.0 / (index + 1)} for index in range(len(assets))]}))
        links.extend(edge("asset" + str(index), "asset", "references", "source_" + str(index + 1))
            for index in range(len(assets)))
        links.append(edge("references", "references", "prompt", "references"))
    values.extend([node("prompt", "image_prompt", {"prompt": "SYNTHETIC authored image prompt"}),
        node("generate", "image_generate", {"operation_id": operation, "provider_id": provider,
            "model_id": model, "parameters": {"width": 64, "height": 64, "seed": 3}}),
        node("review", "media_review")])
    links.extend([edge("prompt", "prompt", "generate", "prompt"), edge("generate", "candidate", "review", "candidate")])
    return {"schema_version": 4, "title": "Independent image workflow", "nodes": values, "edges": links}


def graph_owner(e, monkeypatch, production=None):
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", FLAGS)
    e.service.activate(e.nid, e.scope, e.actor)
    result = CreativeGraphService(e.service.store, e.service)
    result.configure_media(production or SimpleNamespace())
    return result


def create_run(e, owner, value):
    graph = owner.create(e.nid, e.scope, e.actor, {"request_id": "graph-" + uuid4().hex, "definition": value})
    flight = owner.preflight(e.nid, e.scope, e.actor, graph["id"], {"expected_version": graph["version"]})
    assert flight["executable"], flight["issues"]
    row = owner.create_run(e.nid, e.scope, e.actor, graph["id"], {"expected_graph_version": graph["version"],
        "reviewed_preflight_digest": flight["preflight_digest"], "target_node_ids": flight["target_node_ids"],
        "request_id": "run-" + uuid4().hex})
    return graph, owner.action(e.nid, e.scope, e.actor, row["id"], "execute", {"expected_version": row["version"]})


@pytest.mark.parametrize("schema", [1, 2, 3])
@pytest.mark.parametrize("kind", ["image_reference", "image_prompt", "image_generate"])
def test_old_schemas_remain_closed_to_new_image_nodes(schema, kind):
    value = definition(operation="m5.image.t2i")
    value.update(schema_version=schema, nodes=[node("new", kind)], edges=[])
    with pytest.raises(ValidationError):
        parse_graph(value)


@pytest.mark.parametrize("kind", ["media_generate", "timeline_export", "text_generate", "human_review", "director_note"])
def test_schema4_is_image_only_and_does_not_admit_other_execution(kind):
    with pytest.raises(ValidationError):
        GraphImageInput.model_validate({"schema_version": 4, "title": "closed", "nodes": [node("other", kind)]})


def test_catalog_expansion_is_explicit_and_old_graph_parameters_remain_closed():
    old = catalog_definitions(include_model=True, include_media=True)
    expanded = catalog_definitions(include_model=True, include_media=True, include_image=True)
    new = {value["id"] for value in expanded} - {value["id"] for value in old}
    assert new == {"image_reference", "image_prompt", "image_generate"}
    assert len(catalog_definitions()) == 7 and [value for value in expanded if value["id"] not in new] == old
    with pytest.raises(ValidationError):
        MediaNodeParameters.model_validate({"operation_id": "m5.image.i2i", "provider_id": "owned",
            "model_id": "model", "parameters": {"denoising_strength": 0.5}})


@pytest.mark.parametrize("weight", [0.0, -1.0, 1.001, float("nan"), float("inf"), True, "0.5"])
def test_reference_weights_are_bounded_finite_and_not_coerced(weight):
    value = definition([image_asset()])
    value["nodes"][1]["parameters"]["bindings"][0]["weight"] = weight
    with pytest.raises(ValidationError):
        parse_graph(value)


def test_schema4_capacity_and_old_saved_schema_target_budget_are_preserved():
    value = {"schema_version": 4, "title": "24 local image-stage nodes",
        "nodes": [node("n" + str(index), "text_input", {"text": "owned"}) for index in range(24)], "edges": []}
    parsed = parse_graph(value).model_dump()
    targets = [value["id"] for value in parsed["nodes"]]
    assert parse_graph_preflight({"expected_version": 1, "target_node_ids": targets}, parsed).target_node_ids == targets
    for schema in [1, 2]:
        with pytest.raises(ValidationError):
            parse_graph_preflight({"expected_version": 1, "target_node_ids": targets}, {"schema_version": schema})
    value["nodes"].append(node("overflow", "text_input", {"text": "owned"}))
    with pytest.raises(ValidationError):
        parse_graph(value)


def test_reference_output_preserves_order_weights_and_exact_version():
    config = node("refs", "image_reference", {"bindings": [{"port": "source_2", "weight": 0.25},
        {"port": "source_1", "weight": 0.75}]})
    a, b = image_asset("first"), image_asset("second", version=3, digest="b" * 64)
    output = execute_image_local(config, {"source_1": a, "source_2": b})
    assert output == {"references": [{"asset": b, "weight": 0.25}, {"asset": a, "weight": 0.75}]}
    prompt = execute_image_local(node("prompt", "image_prompt", {"prompt": "Exact author prompt"}), output)
    fields = image_command_fields(node("gen", "image_generate", {"operation_id": "m5.image.reference"}), prompt)
    assert fields["prompt"] == "Exact author prompt"
    assert [value["source"]["id"] for value in fields["image_references"]] == ["second", "first"]
    assert [value["version"] for value in fields["source_snapshots"]] == [3, 1]


def test_reference_cannot_duplicate_assets_or_introduce_unbound_ports():
    config = node("refs", "image_reference", {"bindings": [{"port": "source_1", "weight": 1.0},
        {"port": "source_2", "weight": 0.5}]})
    with pytest.raises(ValueError, match="DUPLICATE"):
        execute_image_local(config, {"source_1": image_asset(), "source_2": image_asset()})
    with pytest.raises(ValueError, match="BINDING_REQUIRED"):
        execute_image_local(config, {"source_1": image_asset()})
    with pytest.raises(ValidationError):
        execute_image_local(config, {"source_1": image_asset(), "source_2": image_asset("video", kind="video")})


def test_prompt_uses_one_explicit_source_and_rejects_ambiguous_or_empty_text():
    value = node("prompt", "image_prompt", {"prompt": "author"})
    with pytest.raises(ValueError, match="AMBIGUOUS"):
        execute_image_local(value, {"text": "another"})
    value["parameters"]["prompt"] = ""
    assert execute_image_local(value, {"text": "exact connected text"})["prompt"]["prompt"] == "exact connected text"
    with pytest.raises((ValidationError, ValueError)):
        execute_image_local(value, {"text": " "})


@pytest.mark.parametrize("operation,ports,code", [
    ("m5.image.t2i", {"source": image_asset()}, "T2I_UNUSED"),
    ("m5.image.reference", {}, "REFERENCE_INPUT"),
    ("m5.image.i2i", {}, "SOURCE_REQUIRED"),
    ("m5.image.inpaint", {"source": image_asset()}, "INPAINT_INPUT"),
    ("m5.image.inpaint", {"source": image_asset(), "mask": image_asset()}, "MASK_SOURCE_ALIAS"),
])
def test_image_operation_ports_fail_closed(operation, ports, code):
    value = {"prompt": {"prompt": "owned", "references": []}, **ports}
    with pytest.raises(ValueError, match=code):
        image_command_fields(node("gen", "image_generate", {"operation_id": operation}), value)


def test_image_source_reference_aliases_and_version_conflicts_are_rejected():
    a = image_asset()
    ports = {"prompt": {"prompt": "owned", "references": [{"asset": a, "weight": 0.5}]}, "source": a}
    config = node("gen", "image_generate", {"operation_id": "m5.image.i2i"})
    with pytest.raises(ValueError, match="REFERENCE_DUPLICATE"):
        image_command_fields(config, ports)
    ports["prompt"]["references"][0]["asset"] = image_asset(version=2)
    with pytest.raises(ValueError, match="VERSION_CONFLICT"):
        image_command_fields(config, ports)


def test_image_generate_candidate_rejects_nonimage_owner():
    output = {"candidate": {"owner": "video", "job_id": "owned", "job_version": 1,
        "request_digest": DIGEST, "asset": image_asset(kind="video")}}
    with pytest.raises(ValueError, match="KIND_INVALID"):
        validate_output_ports("image_generate", output, schema_version=4)


def test_original_asset_reference_prompt_nodes_execute_and_reopen_without_model_call(rig, monkeypatch):
    owners = graph_owner(rig, monkeypatch)
    assets = [import_asset(rig, data=png_bytes(color), filename="synthetic.png", kind="image")
        for color in (b"\x11\x22\x33", b"\x44\x55\x66")]
    references = [image_asset(asset["id"], version=asset["version"], digest=asset["sha256"]) for asset in assets]
    graph, row = create_run(rig, owners, definition(references))
    assert row["current_node_id"] == "generate" and row["status"] == "WAITING_APPROVAL"
    raw = owners._owned(rig.nid, rig.scope, rig.actor, owners.RUNS, row["id"])
    assert raw["graph_schema_version"] == 4 and not raw["model_called"] and raw["external_calls"] == 0
    assert raw["typed_outputs"]["references"]["references"] == [{"asset": ref, "weight": 1.0 / (index + 1)}
        for index, ref in enumerate(references)]
    assert raw["typed_outputs"]["prompt"]["prompt"]["references"] == raw["typed_outputs"]["references"]["references"]
    assert raw["media_previews"] == raw["media_executions"] == {} and "generate" not in raw["typed_outputs"]
    original = deepcopy(raw)
    workspace = reopened(rig)
    new = CreativeGraphService(workspace.store, workspace)
    new.configure_media(SimpleNamespace())
    assert new.get_run(rig.nid, rig.scope, rig.actor, row["id"])["version"] == row["version"]
    assert new._owned(rig.nid, rig.scope, rig.actor, new.RUNS, row["id"]) == original
    for actor, scope in [("foreign-author", rig.scope), (rig.actor, branch_scope(rig))]:
        with pytest.raises(FileNotFoundError):
            new.get_run(rig.nid, scope, actor, row["id"])


def test_actual_image_catalog_retains_original_shape_and_opt_in_capabilities(rig, monkeypatch):
    owners = graph_owner(rig, monkeypatch)
    original = owners.catalog(rig.nid, rig.scope, rig.actor)
    expanded = owners.catalog(rig.nid, rig.scope, rig.actor, include_image=True)
    assert "image_graph" not in original["capabilities"]
    assert expanded["capabilities"]["image_graph_schema_version"] == 4
    assert expanded["capabilities"]["image_reference_semantics"] == "WEIGHTED_PIXEL_INITIALIZATION"
    # A test-owned observation can feed front-end decoder fixtures. No project,
    # authored content, endpoint, asset IDs or actor metadata enter the catalog.
    target = os.getenv("IMAGE_GRAPH_CATALOG_FIXTURE_PATH")
    if target:
        path = Path(target).resolve()
        assert path.is_relative_to(Path(os.environ["PROJECT_ROOT"]).resolve() / ".runtime")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(expanded, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


@pytest.mark.parametrize("count", [17, 24])
def test_schema4_expanded_targets_execute_original_workflow_and_keep_old_limits(rig, monkeypatch, count):
    owners = graph_owner(rig, monkeypatch)
    value = {"schema_version": 4, "title": "Explicit image-stage local nodes", "nodes": [
        node("text" + str(index), "text_input", {"text": "Owned local input " + str(index)}) for index in range(count)],
        "edges": []}
    graph, row = create_run(rig, owners, value)
    raw = owners._owned(rig.nid, rig.scope, rig.actor, owners.RUNS, row["id"])
    assert row["status"] == "SUCCEEDED" and not row["stale"] and not row["model_called"]
    assert raw["graph_schema_version"] == 4 and len(raw["selected_closure"]) == count and raw["step_limit"] == count
    assert len(raw["typed_outputs"]) == count and raw["external_calls"] == 0 and not raw["reviewed"]
    assert owners.get_run(rig.nid, rig.scope, rig.actor, row["id"])["status"] == "SUCCEEDED"


@pytest.mark.parametrize("change,code", [("review", "MEDIA_REVIEW_REQUIRED"),
    ("reference", "REFERENCE_INPUT_REQUIRED"), ("ambiguous", "PROMPT_AMBIGUOUS")])
def test_schema4_static_wiring_blocks_dispatch_without_original_review_or_inputs(rig, monkeypatch, change, code):
    owners = graph_owner(rig, monkeypatch)
    value = definition(operation="m5.image.t2i")
    if change == "review":
        value["edges"] = [link for link in value["edges"] if link["target_node_id"] != "review"]
    elif change == "reference":
        value["nodes"][1]["parameters"]["operation_id"] = "m5.image.reference"
    else:
        value["nodes"].append(node("text", "text_input", {"text": "Another prompt"}))
        value["edges"].append(edge("text", "text", "prompt", "text"))
    graph = owners.create(rig.nid, rig.scope, rig.actor, {"request_id": "blocked-" + change, "definition": value})
    flight = owners.preflight(rig.nid, rig.scope, rig.actor, graph["id"], {"expected_version": graph["version"]})
    assert not flight["executable"] and any(code in issue["code"] for issue in flight["issues"])
    with pytest.raises(ValueError, match="EXECUTION_BLOCKED"):
        owners.create_run(rig.nid, rig.scope, rig.actor, graph["id"], {"expected_graph_version": graph["version"],
            "reviewed_preflight_digest": flight["preflight_digest"], "request_id": "never-dispatch"})
    assert owners.runs(rig.nid, rig.scope, rig.actor, graph["id"])["items"] == []


def test_reference_asset_change_blocks_existing_graph_preview(rig, monkeypatch):
    owners = graph_owner(rig, monkeypatch)
    asset = import_asset(rig, data=png_bytes(), filename="synthetic.png", kind="image")
    _, row = create_run(rig, owners, definition([image_asset(asset["id"], version=asset["version"], digest=asset["sha256"])]))
    with rig.service._asset_scope(rig.nid, rig.scope):
        rig.assets.delete(asset["id"])
    before = deepcopy(owners._owned(rig.nid, rig.scope, rig.actor, owners.RUNS, row["id"]))
    with pytest.raises((StaleSourceError, FileNotFoundError, ValueError)):
        owners.media_runtime.preview(rig.nid, rig.scope, rig.actor, row["id"],
            {"expected_version": row["version"], "node_id": "generate"}, lambda: None)
    assert owners._owned(rig.nid, rig.scope, rig.actor, owners.RUNS, row["id"]) == before


def test_reference_guard_revocation_propagates_without_mutation(rig, monkeypatch):
    owners = graph_owner(rig, monkeypatch)
    asset = import_asset(rig, data=png_bytes(), filename="synthetic.png", kind="image")
    value = definition([image_asset(asset["id"], version=asset["version"], digest=asset["sha256"])])
    graph = owners.create(rig.nid, rig.scope, rig.actor, {"request_id": "guarded", "definition": value})
    before = deepcopy(rig.raw_store.read(rig.nid, rig.scope))
    denied = PermissionError("SYNTHETIC_GRAPH_AUTHORITY_REVOKED")
    def revoked():
        raise denied
    with pytest.raises(PermissionError) as raised:
        owners.preflight(rig.nid, rig.scope, rig.actor, graph["id"], {"expected_version": graph["version"]}, revoked)
    assert raised.value is denied and rig.raw_store.read(rig.nid, rig.scope) == before


def test_original_t2i_job_private_bytes_explicit_review_and_final_graph_asset(rig, monkeypatch):
    from test_v2_discovered_image_production import discovery, owner
    original, registry, adapter = discovery(rig.root, "AUTOMATIC1111")
    production = owner(registry, monkeypatch, rig)
    owners = graph_owner(rig, monkeypatch, production)
    data, posts = png_bytes(), []
    def post(url, **kwargs):
        posts.append((url, deepcopy(kwargs)))
        return httpx.Response(200, json={"images": [base64.b64encode(data).decode()]}, request=httpx.Request("POST", url))
    monkeypatch.setattr(adapter.delegate.transport, "post", post)
    value = definition(operation="m5.image.t2i", provider=adapter.candidate["provider_id"], model=adapter.candidate["id"])
    _, row = create_run(rig, owners, value)
    runtime = owners.media_runtime
    row = runtime.preview(rig.nid, rig.scope, rig.actor, row["id"],
        {"expected_version": row["version"], "node_id": "generate"}, lambda: None)
    preview = row["media_runtime"]["nodes"][0]["preview"]
    assert posts == [] and preview["command"]["prompt"] == value["nodes"][0]["parameters"]["prompt"]
    row = runtime.dispatch(rig.nid, rig.scope, rig.actor, row["id"], {"expected_version": row["version"],
        "node_id": "generate", "reviewed_preview_digest": preview["preview_digest"]}, lambda: None)
    job = row["media_runtime"]["nodes"][0]["execution"]["job"]
    row = runtime.execute_job(rig.nid, rig.scope, rig.actor, row["id"], {"expected_version": row["version"],
        "node_id": "generate", "expected_job_version": job["version"], "expected_request_digest": job["request_digest"]}, lambda: None)
    job = row["media_runtime"]["nodes"][0]["execution"]["job"]
    assert row["current_node_id"] == "review" and job["status"] == "AWAITING_REVIEW" and len(posts) == 1
    candidate = job["output_candidate"]
    assert candidate["digest"] == hashlib.sha256(data).hexdigest()
    with pytest.raises(FileNotFoundError):
        rig.service.asset(rig.nid, rig.scope, candidate["id"])
    with pytest.raises((ValueError, FileNotFoundError)):
        owners.create(rig.nid, rig.scope, rig.actor, {"request_id": "cannot-launder", "definition": {
            "schema_version": 4, "title": "Unreviewed", "nodes": [node("private", "asset_reference",
                image_asset(candidate["id"], version=candidate["version"], digest=candidate["digest"]))]}})
    assert "review" not in owners._owned(rig.nid, rig.scope, rig.actor, owners.RUNS, row["id"])["typed_outputs"]
    with pytest.raises((ValueError, StaleSourceError)):
        owners.action(rig.nid, rig.scope, rig.actor, row["id"], "approve", {"expected_version": row["version"],
            "node_id": "review", "reviewed_output_digest": candidate["digest"]})
    row = runtime.review(rig.nid, rig.scope, rig.actor, row["id"], {"expected_version": row["version"],
        "node_id": "review", "expected_job_version": job["version"], "expected_request_digest": job["request_digest"],
        "reviewed_output_digest": candidate["digest"]}, lambda: None)
    raw = owners._owned(rig.nid, rig.scope, rig.actor, owners.RUNS, row["id"])
    assert row["status"] == "SUCCEEDED" and row["reviewed"]
    assert raw["typed_outputs"]["review"]["asset"] == image_asset(candidate["id"], version=2, digest=candidate["digest"])
    assert rig.service.asset(rig.nid, rig.scope, candidate["id"])["sha256"] == candidate["digest"]
    assert len(posts) == 1 and row["media_runtime"]["product_acceptance"] == "LOCAL_REQUIRED"


@pytest.mark.parametrize("kind", ["COMFYUI", "AUTOMATIC1111"])
def test_schema4_authored_inpaint_original_job_review_asset_and_reopen(mask, tmp_path, monkeypatch, kind):
    """Real File/PG owners and real PNG validation; synthetic model HTTP only."""
    from test_v2_image_runtime_owner import runtime
    from test_v2_discovered_image_production import owner
    e = mask
    discovery, adapter, production, wire, command = runtime(e, tmp_path, monkeypatch, "inpaint", kind)
    owners = graph_owner(e, monkeypatch, production)
    base, painted = command["image_source"], command["mask_source"]
    with e.service._asset_scope(e.nid, e.scope):
        original_base = deepcopy(e.assets.get(base["id"]))
        original_mask = deepcopy(e.assets.get(painted["id"]))
        original_base_bytes = e.assets.content(base["id"])
        original_mask_bytes = e.assets.content(painted["id"])
    value = {"schema_version": 4, "title": "Authored mask image workflow", "nodes": [
        node("base", "asset_reference", image_asset(base["id"], version=base["version"], digest=base["digest"])),
        node("mask", "asset_reference", image_asset(painted["id"], version=painted["version"], digest=painted["digest"])),
        node("prompt", "image_prompt", {"prompt": "SYNTHETIC repaint only the authored black region"}),
        node("generate", "image_generate", {"operation_id": "m5.image.inpaint",
            "provider_id": adapter.candidate["provider_id"], "model_id": adapter.candidate["id"],
            "parameters": {"steps": 12, "seed": 3, "denoising_strength": .4}}),
        node("review", "media_review")], "edges": [
        edge("base", "asset", "generate", "source"), edge("mask", "asset", "generate", "mask"),
        edge("prompt", "prompt", "generate", "prompt"), edge("generate", "candidate", "review", "candidate")]}
    graph, row = create_run(e, owners, value)
    media = owners.media_runtime
    row = media.preview(e.nid, e.scope, e.actor, row["id"],
        {"expected_version": row["version"], "node_id": "generate"}, lambda: None)
    preview = row["media_runtime"]["nodes"][0]["preview"]
    assert wire.calls == [] and preview["command"]["image_source"] == {**base, "reference_only": True}
    assert preview["command"]["mask_source"] == {**painted, "reference_only": True}
    assert preview["command"]["source_snapshots"] == [{**base, "reference_only": True}, {**painted, "reference_only": True}]
    assert preview["production_preview"]["execution_recipe"]["mask_semantics"] == "WHITE_KEEP_BLACK_REPAINT"
    row = media.dispatch(e.nid, e.scope, e.actor, row["id"], {"expected_version": row["version"],
        "node_id": "generate", "reviewed_preview_digest": preview["preview_digest"]}, lambda: None)
    job = row["media_runtime"]["nodes"][0]["execution"]["job"]
    assert job["status"] == "QUEUED" and wire.calls == []
    binding = owners._owned(e.nid, e.scope, e.actor, owners.RUNS, row["id"])["media_executions"]["generate"]["graph_binding"]
    assert binding["graph_id"] == graph["id"] and binding["graph_version"] == graph["version"]
    row = media.execute_job(e.nid, e.scope, e.actor, row["id"], {"expected_version": row["version"], "node_id": "generate",
        "expected_job_version": job["version"], "expected_request_digest": job["request_digest"]}, lambda: None)
    job = row["media_runtime"]["nodes"][0]["execution"]["job"]
    assert row["current_node_id"] == "review" and job["status"] == "AWAITING_REVIEW" and job["approved_asset_version"] is None
    candidate = job["output_candidate"]
    with pytest.raises(FileNotFoundError):
        e.service.asset(e.nid, e.scope, candidate["id"])
    meta, data = media.candidate(e.nid, e.scope, e.actor, row["id"], "generate", lambda: None)
    assert hashlib.sha256(data).hexdigest() == candidate["digest"] == meta["sha256"]
    raw_job, context = production._row(e.nid, e.scope, e.actor, "image", job["id"], lambda: None, graph_binding=binding)
    assert context["sources"] == [base, painted] and context["graph_binding"] == binding
    assert raw_job["body"]["image_source"] == {**base, "reference_only": True}
    assert raw_job["body"]["mask_source"] == {**painted, "reference_only": True}
    assert "processing_proof" not in raw_job  # CPU cutout proof is a different original operation.
    sends = [(url, payload) for url, payload in wire.calls if url.endswith("/prompt") or url.endswith("/sdapi/v1/img2img")]
    assert len(sends) == 1
    if kind == "COMFYUI":
        submitted = sends[0][1]["json"]["prompt"]
        assert submitted["5"]["inputs"]["mask"] == ["27", 0]
        assert submitted["9"]["inputs"]["images"] == ["28", 0]
    else:
        assert sends[0][1]["json"]["inpainting_mask_invert"] == 1

    # Reopen the original owners while the result is still private. Neither a
    # read nor a new service instance may resend, approve or refresh any source.
    reopened_workspace = reopened(e)
    restarted_production = owner(production.image_registry, monkeypatch, SimpleNamespace(
        service=reopened_workspace, nid=e.nid, scope=e.scope, actor=e.actor, root=e.root))
    restarted = CreativeGraphService(reopened_workspace.store, reopened_workspace)
    restarted.configure_media(restarted_production)
    assert restarted.get_run(e.nid, e.scope, e.actor, row["id"])["current_node_id"] == "review"
    row = restarted.media_runtime.review(e.nid, e.scope, e.actor, row["id"], {"expected_version": row["version"],
        "node_id": "review", "expected_job_version": job["version"], "expected_request_digest": job["request_digest"],
        "reviewed_output_digest": candidate["digest"]}, lambda: None)
    assert row["status"] == "SUCCEEDED" and row["reviewed"]
    formal = reopened_workspace.asset(e.nid, e.scope, candidate["id"])
    assert formal["version"] == candidate["version"] + 1 and formal["sha256"] == candidate["digest"]
    assert {parent["id"] for parent in formal["provenance"]["parents"]} == {base["id"], painted["id"]}
    output = restarted._owned(e.nid, e.scope, e.actor, restarted.RUNS, row["id"])["typed_outputs"]["review"]["asset"]
    assert output == image_asset(candidate["id"], version=formal["version"], digest=candidate["digest"])
    assert restarted.get_run(e.nid, e.scope, e.actor, row["id"])["status"] == "SUCCEEDED"
    with reopened_workspace._asset_scope(e.nid, e.scope):
        assert reopened_workspace.assets.get(base["id"]) == original_base
        assert reopened_workspace.assets.get(painted["id"]) == original_mask
        assert reopened_workspace.assets.content(base["id"]) == original_base_bytes
        assert reopened_workspace.assets.content(painted["id"]) == original_mask_bytes
    assert len([url for url, _ in wire.calls if url.endswith("/prompt") or url.endswith("/sdapi/v1/img2img")]) == 1
    assert discovery.center.lifecycle.start.call_count == 0 and row["media_runtime"]["product_acceptance"] == "LOCAL_REQUIRED"
