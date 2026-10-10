"""Additive M4 contracts: old seven-node graph catalog and bounded TEXT→DRAFT."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.creative.ai_execution import ModelPreview, ModelDispatch, ModelRefresh
from app.creative.graph_models import GraphInput, GraphModelInput, catalog_definitions, validate_output_ports
from app.model_execution import APIProvider, guard_local_provider
from app.model_runtime import ModelDescriptor, Modality, ModelRuntimeError, ProviderDescriptor
from test_v2_independent_workspace import rig
from test_v2_ai_execution_runtime import (model_rig, FLAGS, CONTRACT, create_graph, definition,
    admit, preview, dispatch, spy_transport, generation_delta, owned_jobs)

OLD_IDS = {"text_input", "text_reference", "draft_prepare", "manual_transform",
           "director_note", "human_review", "asset_reference"}


def test_default_seven_node_catalog_is_unchanged_and_model_is_explicit():
    old = catalog_definitions()
    assert {row["id"] for row in old} == OLD_IDS and len(old) == 7
    extended = catalog_definitions(include_model=True)
    assert [row for row in extended if row["id"] != "text_generate"] == old
    item = next(row for row in extended if row["id"] == "text_generate")
    assert item["version"] == 1 and item["model_called"] is False
    assert item["inputs"] == [
        {"id": "text", "type": "TEXT", "required": True, "multiple": False},
        {"id": "direction", "type": "DIRECTOR_NOTES", "required": False, "multiple": False}]
    assert item["outputs"] == [{"id": "draft", "type": "DRAFT", "required": False, "multiple": False}]
    assert item["default_parameters"] == {"instruction": "", "max_output_tokens": 512}
    assert item["parameters_schema"]["additionalProperties"] is False
    assert item["parameters_schema"]["properties"]["max_output_tokens"]["maximum"] == 2048


@pytest.mark.parametrize("parameters", [
    {"max_output_tokens": True}, {"max_output_tokens": 0}, {"max_output_tokens": 2049},
    {"max_output_tokens": "128"}, {"instruction": "x" * 4001},
    {"provider_id": "remote"}, {"chapter_id": "hidden-anchor"}, {"endpoint": "https://example.invalid"},
    {"automatic_retry": True}, {"timeout_seconds": 3600}, {"code": "exec(data)"},
])
def test_model_node_parameters_cannot_smuggle_owner_or_runtime_controls(parameters):
    value = definition(); value["nodes"][1]["parameters"] = parameters
    with pytest.raises(ValidationError): GraphModelInput.model_validate(value)


@pytest.mark.parametrize("model,body", [
    (ModelPreview, {"expected_version": 1, "route_id": "a" * 64, "allow_synthetic": "true"}),
    (ModelPreview, {"expected_version": True, "route_id": "a" * 64}),
    (ModelPreview, {"expected_version": 1, "route_id": "a" * 64, "prompt": "override"}),
    (ModelDispatch, {"expected_version": 1, "reviewed_preview_digest": "a" * 64, "output": "injected"}),
    (ModelDispatch, {"expected_version": 1, "reviewed_preview_digest": "a" * 64, "retry": True}),
    (ModelRefresh, {"expected_version": 1, "job_id": "foreign-job"}),
])
def test_model_wire_contract_forbids_caller_authority_and_output(model, body):
    with pytest.raises(ValidationError): model.model_validate(body)


def test_model_draft_origin_cannot_masquerade_as_human_authorship():
    assert validate_output_ports("text_generate", {"draft": {"text": "Proposed", "origin": "MODEL_PROPOSAL"}}) == {
        "draft": {"text": "Proposed", "origin": "MODEL_PROPOSAL"}}
    for origin in ("MANUAL", "USER_SUPPLIED"):
        with pytest.raises(ValidationError):
            validate_output_ports("text_generate", {"draft": {"text": "Proposed", "origin": origin}})
    with pytest.raises(ValidationError):
        validate_output_ports("manual_transform", {"draft": {"text": "Proposed", "origin": "MODEL_PROPOSAL"}})


@pytest.mark.parametrize("missing", FLAGS.split(","))
def test_every_model_flag_is_explicit_and_missing_flag_keeps_old_catalog(model_rig, monkeypatch, missing):
    e = model_rig
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", ",".join(flag for flag in FLAGS.split(",") if flag != missing))
    catalog = e.graphs.catalog(e.nid, e.scope, e.actor)
    assert len(catalog["definitions"]) == 7
    assert catalog["capabilities"]["model_execution"] is False
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as caught: create_graph(e)
    assert caught.value.status_code == 404
    assert not owned_jobs(e) and not generation_delta(e)


def test_single_model_with_mandatory_selected_human_review(model_rig):
    e = model_rig
    values = [(definition(review=False), "CREATIVE_MODEL_HUMAN_REVIEW_REQUIRED")]
    duplicate = definition()
    duplicate["nodes"] += [{"id": "Generate2", "definition_id": "text_generate"},
                           {"id": "Review2", "definition_id": "human_review"}]
    duplicate["edges"] += [
        {"id": "Source2", "source_node_id": "Input", "source_port": "text", "target_node_id": "Generate2", "target_port": "text"},
        {"id": "Check2", "source_node_id": "Generate2", "source_port": "draft", "target_node_id": "Review2", "target_port": "draft"}]
    values.append((duplicate, "CREATIVE_MODEL_SINGLE_NODE_REQUIRED"))
    for value, code in values:
        graph = create_graph(e, value)
        preflight = e.graphs.preflight(e.nid, e.scope, e.actor, graph["id"], {"expected_version": graph["version"]})
        assert not preflight["executable"] and code in {item["code"] for item in preflight["issues"]}
    graph = create_graph(e)
    partial = e.graphs.preflight(e.nid, e.scope, e.actor, graph["id"], {
        "expected_version": graph["version"], "target_node_ids": ["Generate"]})
    assert not partial["executable"]
    assert "CREATIVE_MODEL_HUMAN_REVIEW_REQUIRED" in {item["code"] for item in partial["issues"]}
    assert not owned_jobs(e)


def test_capabilities_disclose_original_owners_zero_cost_and_reserved_api(model_rig):
    e = model_rig
    value = e.models.catalog(e.nid, e.scope, e.actor, e.guard)
    assert value["contract"] == CONTRACT and value["local_only"]
    assert value["adapter_owner"] == "TextModelNode" and value["router_owner"] == "ModelBroker"
    assert value["scheduler_owner"] == "JobManager+WorkflowRun"
    assert value["automatic_fallback"] is False and value["quality_verification"] == "NOT_RUN"
    assert value["api_provider"]["status"] == "RESERVED" and not value["api_provider"]["execution_available"]
    assert value["limits"] == {"model_nodes": 1, "max_output_tokens": 2048, "timeout_seconds": 180}
    mock = next(row for row in value["routes"] if row["provider_id"] == "mock")
    assert mock["available"] and mock["synthetic"]
    assert e.chapters.list(e.nid) == [] and not generation_delta(e)
    assert APIProvider.available is False
    with pytest.raises(ModelRuntimeError): APIProvider().stream_text(None)


def test_unknown_price_is_blocked_at_preview_without_inference(model_rig, monkeypatch):
    e = model_rig; spy_transport(e, monkeypatch)
    monkeypatch.setattr(e.broker, "_price", lambda *_: None)
    routes = e.models.catalog(e.nid, e.scope, e.actor, e.guard)["routes"]
    mock = next(route for route in routes if route["provider_id"] == "mock")
    assert not mock["available"] and "KNOWN_ZERO_PRICE_REQUIRED" in mock["reasons"]
    row = preview(e, admit(e))
    assert not row["model_runtime"]["preview"]["execution_available"]
    from app.experimental.common import StaleSourceError
    with pytest.raises(StaleSourceError): dispatch(e, row)
    assert not e.calls and not owned_jobs(e) and not generation_delta(e)


def test_synthetic_needs_reviewed_opt_in_and_remote_descriptor_is_blocked(model_rig, monkeypatch):
    e = model_rig; spy_transport(e, monkeypatch)
    row = preview(e, admit(e), allow_synthetic=False)
    assert not row["model_runtime"]["preview"]["execution_available"]
    descriptor = next(item for item in e.runtime.provider_registry.descriptors() if item.provider_id == "mock")
    adapter = e.runtime.provider_registry.resolve("mock")
    e.runtime.provider_registry.register(replace(descriptor, provider_type="cloud"), adapter, replace=True)
    with pytest.raises(ValueError, match="LOCAL_ONLY"):
        guard_local_provider(e.runtime, "mock", "mock-writer", synthetic_allowed=True)
    assert not e.calls and not generation_delta(e)


@pytest.mark.parametrize("management", ["MANAGED", "REMOTE", None])
def test_managed_or_unproven_runtime_never_launches(model_rig, management):
    from app.model_center.discovery_bridge import LocalTextAdapter
    e = model_rig
    candidate = {"id": "local-model", "provider_id": "local-provider", "source_locality": "LOCAL_VERIFIED",
        "model_evidence_fingerprint": "fixture-evidence", "runtime_config": {"management": management, "type": "LLAMA_CPP"}}
    bridge = SimpleNamespace(guard=lambda *_: candidate, launch_on_demand=lambda *_: pytest.fail("Managed model launch forbidden"))
    e.runtime.provider_registry.register(ProviderDescriptor("local-provider", "Local", "local",
        frozenset({Modality.TEXT}), True, True), LocalTextAdapter(bridge, candidate))
    e.runtime.model_registry.register(ModelDescriptor("local-model", "local-provider", "Local", Modality.TEXT,
        frozenset({"generate", "stream"}), streaming=True))
    with pytest.raises(ValueError, match="EXTERNAL_LOCAL_RUNTIME_REQUIRED"):
        guard_local_provider(e.runtime, "local-provider", "local-model")
    assert not owned_jobs(e) and not generation_delta(e)


def test_schema_one_does_not_adopt_model_node_without_explicit_schema_two():
    value = definition()
    assert GraphModelInput.model_validate(value).schema_version == 2
    old = deepcopy(value); old.pop("schema_version")
    with pytest.raises(ValidationError): GraphInput.model_validate(old)
    with pytest.raises(ValidationError): GraphModelInput.model_validate(old)
    assert "text_generate" not in GraphInput.model_json_schema()["$defs"]["NodeInstance"]["properties"]["definition_id"]["enum"]
