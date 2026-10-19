"""Schema7: real File owner persistence; no provider/GPU or full E2E claim."""
from copy import deepcopy
from uuid import uuid4

import pytest

from app.creative.graph import CreativeGraphService
from app.creative.graph_local_conditions import CONTRACT
from app.creative.graph_models import catalog_definitions, parse_graph, validate_output_ports
from app.experimental.common import StaleSourceError
from test_v2_independent_workspace import rig


@pytest.fixture(autouse=True)
def opt_in(monkeypatch):
    monkeypatch.setenv("CREATIVE_GRAPH_CONDITIONS_V1", "1")
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2")
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)


def definition(predicate=None):
    return {"schema_version": 7, "title": "Fixed local choice", "nodes": [
        {"id": "input", "definition_id": "text_input", "parameters": {"text": "Pinned authored source"}},
        {"id": "condition", "definition_id": "local_condition", "parameters": {"predicate": predicate or {"kind": "boolean", "value": True}}},
        {"id": "yes", "definition_id": "manual_transform", "parameters": {"result": "Selected A"}},
        {"id": "yes_review", "definition_id": "human_review"},
        {"id": "no", "definition_id": "draft_prepare"},
        {"id": "no_review", "definition_id": "human_review"}], "edges": [
        edge("in", "input", "text", "condition", "text"),
        edge("yes", "condition", "when_true", "yes", "text"),
        edge("yes_review", "yes", "draft", "yes_review", "draft"),
        edge("no", "condition", "when_false", "no", "text"),
        edge("no_review", "no", "draft", "no_review", "draft")]}


def edge(key, source, port, target, inp):
    return {"id": key, "source_node_id": source, "source_port": port, "target_node_id": target, "target_port": inp}


def owner(rig):
    return CreativeGraphService(rig.store, rig.service)


def create(rig, value=None):
    return owner(rig).create(rig.nid, rig.scope, rig.actor, {"request_id": uuid4().hex, "definition": value or definition()})


def admit(rig, graph, request=None):
    service = owner(rig)
    preflight = service.preflight(rig.nid, rig.scope, rig.actor, graph["id"], {"expected_version": graph["version"]})
    assert preflight["executable"]
    body = {"request_id": request or uuid4().hex, "expected_graph_version": graph["version"],
        "reviewed_preflight_digest": preflight["preflight_digest"]}
    return service.create_run(rig.nid, rig.scope, rig.actor, graph["id"], body), body


def action(rig, run, command, **extra):
    return owner(rig).action(rig.nid, rig.scope, rig.actor, run["id"], command, {"expected_version": run["version"], **extra})


@pytest.mark.parametrize("predicate,chosen,skipped", [
    ({"kind": "boolean", "value": True}, "yes", "no"),
    ({"kind": "boolean", "value": False}, "no", "yes"),
    ({"kind": "enum", "value": "A", "equals": "A"}, "yes", "no"),
    ({"kind": "enum", "value": "A", "equals": "B"}, "no", "yes")])
def test_only_selected_arm_dispatches_with_durable_skips_and_original_review(rig, monkeypatch, predicate, chosen, skipped):
    graph = create(rig, definition(predicate)); queued, body = admit(rig, graph, "stable-condition")
    assert owner(rig).create_run(rig.nid, rig.scope, rig.actor, graph["id"], body)["id"] == queued["id"]
    service = owner(rig); original = service.executor.adapter.execute; calls = []
    def observed(request):
        calls.append(request.request_id)
        assert not request.request_id.endswith(":" + skipped), "unchosen node reached adapter"
        return original(request)
    monkeypatch.setattr(service.executor.adapter, "execute", observed)
    run = service.action(rig.nid, rig.scope, rig.actor, queued["id"], "execute", {"expected_version": queued["version"]})
    assert len(calls) == 3
    assert run["status"] == "WAITING_APPROVAL" and run["review"]["node_id"] == chosen + "_review"
    assert all(v["output"] is None for v in run["node_states"].values())
    assert run["node_states"][skipped]["status"] == run["node_states"][skipped + "_review"]["status"] == "SKIPPED"
    assert run["conditional_runtime"]["contract"] == CONTRACT
    assert run["conditional_runtime"]["skipped_dispatches"] == run["conditional_runtime"]["skipped_outputs"] == 0
    raw = rig.store.read(rig.nid, rig.scope)["collections"][service.RUNS][run["id"]]
    assert {x["node_id"] for x in raw["dispatch_trace"]} == {"input", "condition", chosen, chosen + "_review"}
    assert set(raw["typed_outputs"]) == {"input", "condition", chosen}
    assert all(raw["cache_keys"][key]["cacheable"] is False for key in raw["cache_keys"])
    assert all(t["node_statuses"][skipped] == "SKIPPED" for t in raw["trace"])
    assert owner(rig).get_run(rig.nid, rig.scope, rig.actor, run["id"]) == run
    review = run["review"]
    accepted = action(rig, run, "approve", node_id=review["node_id"], reviewed_output_digest=review["output_digest"])
    assert accepted["status"] == "SUCCEEDED" and accepted["reviewed"] and not accepted["applied"]
    assert accepted["node_states"][chosen]["output"]["draft"] == review["draft"]
    assert accepted["node_states"][skipped]["output"] is None
    assert owner(rig).get_run(rig.nid, rig.scope, rig.actor, accepted["id"]) == accepted
    second, _ = admit(rig, graph); second = action(rig, second, "execute")
    assert second["cache"]["hits"] == 0
    assert rig.chapters.list(rig.nid) == []
    assert owner(rig).list(rig.nid, rig.scope, rig.actor)["items"] == []


@pytest.mark.parametrize("mutation", [
    lambda d: d["edges"].pop(),
    lambda d: d["edges"].append(edge("cross", "yes", "draft", "no_review", "draft")),
    lambda d: d["nodes"].append({"id": "orphan", "definition_id": "text_input"}),
    lambda d: d["nodes"][2].update(enabled=False),
    lambda d: d["nodes"][2].update(definition_id="local_subgraph"),
    lambda d: d["nodes"][2].update(definition_id="text_generate"),
    lambda d: d["nodes"][2].update(definition_id="asset_reference"),
    lambda d: d["edges"].append(edge("cycle", "yes", "draft", "condition", "text")),
    lambda d: d["nodes"][1]["parameters"].update(predicate={"kind": "boolean", "value": 1}),
    lambda d: d["nodes"][1]["parameters"].update(predicate={"kind": "enum", "value": "C", "equals": "A"}),
    lambda d: d["nodes"][1]["parameters"].update(script="return true")])
def test_closed_contract_rejects_invalid_topology_and_dynamic_or_external_nodes(mutation):
    value = definition(); mutation(value)
    with pytest.raises(ValueError): parse_graph(value)


def test_schema_gate_and_frozen_catalog(monkeypatch):
    original = catalog_definitions()
    assert len(original) == 7 and all(row["id"] != "local_condition" for row in original)
    for version in range(1, 7):
        value = definition(); value["schema_version"] = version
        with pytest.raises(ValueError): parse_graph(value)
        with pytest.raises(ValueError): validate_output_ports("local_condition", {"when_true": "x"}, schema_version=version)
    for setting in ["", "true", "yes", "01"]:
        monkeypatch.setenv("CREATIVE_GRAPH_CONDITIONS_V1", setting)
        with pytest.raises(ValueError): parse_graph(definition())
    monkeypatch.setenv("CREATIVE_GRAPH_CONDITIONS_V1", "1")
    monkeypatch.setenv("V1_ACCEPTANCE_MODE", "1")
    with pytest.raises(ValueError): parse_graph(definition())
    assert catalog_definitions() == original


def test_partial_targets_and_idempotency_mismatch_do_not_admit(rig):
    graph = create(rig); service = owner(rig)
    preflight = service.preflight(rig.nid, rig.scope, rig.actor, graph["id"], {"expected_version": 1, "target_node_ids": ["yes_review"]})
    assert not preflight["executable"]
    run, body = admit(rig, graph, "same-request")
    before = deepcopy(rig.raw_store.read(rig.nid, rig.scope))
    body["target_node_ids"] = [n["id"] for n in graph["definition"]["nodes"]]
    with pytest.raises(ValueError, match="REQUEST_ID_REUSED"):
        service.create_run(rig.nid, rig.scope, rig.actor, graph["id"], body)
    assert rig.raw_store.read(rig.nid, rig.scope) == before
    with pytest.raises(FileNotFoundError): service.get_run(rig.nid, rig.scope, "another-author", run["id"])


@pytest.mark.parametrize("waiting", [False, True])
def test_changed_saved_condition_invalidates_old_run_but_cancel_still_redacts(rig, waiting):
    graph = create(rig); run, body = admit(rig, graph)
    if waiting: run = action(rig, run, "execute")
    value = deepcopy(graph["definition"]); value["nodes"][1]["parameters"]["predicate"]["value"] = False
    service = owner(rig); service.save(rig.nid, rig.scope, rig.actor, graph["id"], {"expected_version": 1, "definition": value})
    before = deepcopy(rig.raw_store.read(rig.nid, rig.scope))
    with pytest.raises(StaleSourceError): action(rig, run, "approve" if waiting else "execute", **({"node_id": run["review"]["node_id"], "reviewed_output_digest": run["review"]["output_digest"]} if waiting else {}))
    assert rig.raw_store.read(rig.nid, rig.scope) == before
    masked = service.get_run(rig.nid, rig.scope, rig.actor, run["id"])
    assert masked["stale"] and masked["review"] is None and masked["conditional_runtime"]["plan"] is None
    assert all(s["output"] is None for s in masked["node_states"].values())
    cancelled = action(rig, run, "cancel")
    assert cancelled["status"] == "CANCELLED" and cancelled["review"] is None


@pytest.mark.parametrize("error_type", [PermissionError, ValueError])
def test_revoked_authority_inside_adapter_rolls_back_without_failed_write(rig, monkeypatch, error_type):
    graph = create(rig); run, _ = admit(rig, graph); service = owner(rig); allowed = True
    def guard():
        if not allowed: raise error_type("original authority revoked")
    original = service.executor.adapter.execute
    def revoke(request):
        nonlocal allowed
        result = original(request)
        if request.node_type == "local_condition": allowed = False
        return result
    monkeypatch.setattr(service.executor.adapter, "execute", revoke)
    before = deepcopy(rig.raw_store.read(rig.nid, rig.scope))
    with pytest.raises(error_type): service.action(rig.nid, rig.scope, rig.actor, run["id"], "execute", {"expected_version": 1}, guard)
    assert rig.raw_store.read(rig.nid, rig.scope) == before


def test_failure_rejection_gate_off_and_corrupt_skips_never_publish_outputs(rig, monkeypatch):
    graph = create(rig); run, _ = admit(rig, graph); service = owner(rig); original = service.executor.adapter.execute
    def fail(request):
        if request.node_type == "manual_transform": raise ValueError("local rule failed")
        return original(request)
    monkeypatch.setattr(service.executor.adapter, "execute", fail)
    failed = service.action(rig.nid, rig.scope, rig.actor, run["id"], "execute", {"expected_version": 1})
    assert failed["status"] == "FAILED" and failed["review"] is None and all(s["output"] is None for s in failed["node_states"].values())
    monkeypatch.setattr(service.executor.adapter, "execute", original)
    run, _ = admit(rig, graph); run = action(rig, run, "execute"); review = run["review"]
    rejected = action(rig, run, "reject", node_id=review["node_id"], reviewed_output_digest=review["output_digest"])
    assert rejected["status"] == "REJECTED" and all(s["output"] is None for s in rejected["node_states"].values())
    run, _ = admit(rig, graph)
    with rig.store.transaction(rig.nid, rig.scope) as state:
        state["collections"][service.RUNS][run["id"]]["node_states"]["no"]["status"] = "SUCCEEDED"
    masked = service.get_run(rig.nid, rig.scope, rig.actor, run["id"])
    assert masked["stale"] and masked["conditional_runtime"]["plan"] is None
    monkeypatch.delenv("CREATIVE_GRAPH_CONDITIONS_V1")
    masked = service.get_run(rig.nid, rig.scope, rig.actor, failed["id"])
    assert masked["stale"] and masked["review"] is None


@pytest.mark.parametrize("tamper", ["dispatch", "trace", "reviewed", "output", "plan", "unknown"])
def test_altered_audit_or_unreviewed_publication_is_stale(rig, tamper):
    graph = create(rig); run, _ = admit(rig, graph); run = action(rig, run, "execute"); service = owner(rig)
    with rig.store.transaction(rig.nid, rig.scope) as state:
        row = state["collections"][service.RUNS][run["id"]]
        if tamper == "dispatch": row["dispatch_trace"].append({"node_id": "no"})
        elif tamper == "trace": row["trace"][0]["node_statuses"]["no"] = "WORKING"
        elif tamper == "reviewed": row["reviewed"] = True
        elif tamper == "output": row["typed_outputs"]["no"] = {"draft": {"text": "Hidden", "origin": "MANUAL"}}
        elif tamper == "plan": row["conditional_plan"]["selected_port"] = "when_false"
        else: row["node_states"]["condition"]["status"] = "UNKNOWN"
    masked = service.get_run(rig.nid, rig.scope, rig.actor, run["id"])
    assert masked["stale"] and masked["review"] is None
    assert masked["conditional_runtime"]["skipped_dispatches"] is None
    assert all(s["output"] is None for s in masked["node_states"].values())
    before = deepcopy(rig.raw_store.read(rig.nid, rig.scope))
    with pytest.raises(StaleSourceError): action(rig, run, "approve", node_id=run["review"]["node_id"], reviewed_output_digest=run["review"]["output_digest"])
    assert rig.raw_store.read(rig.nid, rig.scope) == before


def test_pause_resume_timeout_and_incarnation_are_original_owner_fenced(rig):
    from datetime import datetime, timedelta, timezone
    from app.creative.project_store import BINDING
    graph = create(rig); run, _ = admit(rig, graph)
    paused = action(rig, run, "pause"); assert paused["status"] == "PAUSED"
    waiting = action(rig, paused, "resume"); assert waiting["status"] == "WAITING_APPROVAL" and waiting["review"]
    service = owner(rig)
    with rig.store.transaction(rig.nid, rig.scope) as state:
        state["collections"][service.RUNS][waiting["id"]]["started_at"] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    expired = action(rig, waiting, "approve", node_id=waiting["review"]["node_id"], reviewed_output_digest=waiting["review"]["output_digest"])
    assert expired["status"] == "FAILED" and expired["review"] is None
    assert set(expired["node_states"]) == {n["id"] for n in graph["definition"]["nodes"]}
    before = deepcopy(rig.raw_store.read(rig.nid, rig.scope))
    with pytest.raises(ValueError, match="CREATIVE_PROJECT_BINDING_INVALID"):
        with rig.store.transaction(rig.nid, rig.scope) as state:
            state["collections"][service.RUNS][expired["id"]][BINDING] = "another-incarnation"
    assert rig.raw_store.read(rig.nid, rig.scope) == before
    incarnation = rig.store.incarnation(rig.nid)
    rig.novels.delete(rig.nid); rig.create_project(nid=rig.nid)
    assert rig.store.incarnation(rig.nid) != incarnation
    with rig.raw_store.transaction(rig.nid, rig.scope) as state:
        state["collections"].update(before["collections"])
    with pytest.raises(FileNotFoundError): service.get_run(rig.nid, rig.scope, rig.actor, expired["id"])
