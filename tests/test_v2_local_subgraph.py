"""Real original File/optional dedicated PostgreSQL scope persistence for schema6."""
from copy import deepcopy
from uuid import uuid4

import pytest
from pydantic import ValidationError
from app.creative.graph import CreativeGraphService
from app.creative.graph_models import parse_graph, validate_output_ports, catalog_definitions
from app.experimental.common import StaleSourceError
from app.creative.project_store import BINDING
from test_v2_independent_workspace import rig


def owner(rig):
    return CreativeGraphService(rig.store, rig.service)


def child_definition():
    return {"schema_version": 1, "title": "Reusable local author rule", "nodes": [
        {"id": "entry", "definition_id": "text_reference"},
        {"id": "draft", "definition_id": "draft_prepare"}], "edges": [
        {"id": "flow", "source_node_id": "entry", "source_port": "text", "target_node_id": "draft", "target_port": "text"}]}


def create(rig, definition, guard=lambda: None):
    return owner(rig).create(rig.nid, rig.scope, rig.actor,
        {"request_id": "subgraph-" + uuid4().hex, "definition": definition}, guard)


def parent_definition(child):
    return {"schema_version": 6, "title": "Explicit pinned local call", "nodes": [
        {"id": "input", "definition_id": "text_input", "parameters": {"text": "First authored beat\nSecond authored beat"}},
        {"id": "call", "definition_id": "local_subgraph", "parameters": {
            "graph_id": child["id"], "expected_version": child["version"],
            "definition_digest": child["definition_digest"], "execution_digest": child["execution_digest"],
            "input_node_id": "entry", "output_node_id": "draft"}},
        {"id": "review", "definition_id": "human_review"}], "edges": [
        {"id": "text", "source_node_id": "input", "source_port": "text", "target_node_id": "call", "target_port": "text"},
        {"id": "draft", "source_node_id": "call", "source_port": "draft", "target_node_id": "review", "target_port": "draft"}]}


def admit(rig, parent, request=None, guard=lambda: None):
    service = owner(rig)
    preflight = service.preflight(rig.nid, rig.scope, rig.actor, parent["id"], {"expected_version": parent["version"]}, guard)
    assert preflight["executable"]
    body = {"expected_graph_version": parent["version"], "reviewed_preflight_digest": preflight["preflight_digest"], "target_node_ids": [], "request_id": request or uuid4().hex}
    return service.create_run(rig.nid, rig.scope, rig.actor, parent["id"], body, guard), body


def execute(rig, run, guard=lambda: None):
    return owner(rig).action(rig.nid, rig.scope, rig.actor, run["id"], "execute", {"expected_version": run["version"]}, guard)


def approve(rig, run):
    review = run["review"]
    return owner(rig).action(rig.nid, rig.scope, rig.actor, run["id"], "approve", {
        "expected_version": run["version"], "node_id": review["node_id"], "reviewed_output_digest": review["output_digest"]})


def test_real_persistent_call_uses_original_review_and_never_reuses_child_cache(rig):
    service = owner(rig); child = create(rig, child_definition()); parent = create(rig, parent_definition(child))
    assert {row["id"] for row in service.list(rig.nid, rig.scope, rig.actor)["items"]} == {child["id"]}
    assert {row["id"] for row in service.list(rig.nid, rig.scope, rig.actor, include_local_subgraph=True)["items"]} == {child["id"], parent["id"]}
    catalog = service.catalog(rig.nid, rig.scope, rig.actor, include_local_subgraph=True)
    assert catalog["capabilities"]["local_subgraph_frontend_entry"] is False
    assert catalog["capabilities"]["model_execution"] is False
    assert {row["id"] for row in catalog["definitions"]} == {"text_input", "text_reference", "draft_prepare", "manual_transform", "director_note", "human_review", "local_subgraph"}
    partial = service.preflight(rig.nid, rig.scope, rig.actor, parent["id"], {"expected_version": 1, "target_node_ids": ["call"]})
    assert not partial["executable"] and any(issue["code"] == "CREATIVE_GRAPH_SUBGRAPH_HUMAN_REVIEW_REQUIRED" for issue in partial["issues"])
    queued, body = admit(rig, parent, "stable-request")
    assert owner(rig).create_run(rig.nid, rig.scope, rig.actor, parent["id"], body)["id"] == queued["id"]
    run = execute(rig, queued)
    assert run["status"] == "WAITING_APPROVAL" and run["review"]["node_id"] == "review"
    assert run["review"]["draft"]["origin"] == "USER_SUPPLIED"
    assert "First authored beat" in run["review"]["draft"]["text"]
    assert run["model_called"] is False and run["external_calls"] == 0 and run["applied"] is False
    assert run["cache"]["hits"] == 0 and run["cache"]["mode"] == "DISABLED_LOCAL_SUBGRAPH_V1"
    runtime = run["local_subgraph_runtime"]; assert not runtime["cache_enabled"]
    binding = runtime["bindings"]["call"]
    assert binding[BINDING] == rig.store.incarnation(rig.nid) and binding["scope"] == rig.scope and binding["actor"] == rig.actor
    assert binding["node_count"] == 2 and runtime["receipts"]["call"]["steps"] == 2
    assert owner(rig).get_run(rig.nid, rig.scope, rig.actor, run["id"]) == run
    accepted = approve(rig, run)
    assert accepted["status"] == "SUCCEEDED" and accepted["reviewed"] and not accepted["applied"]
    assert owner(rig).get_run(rig.nid, rig.scope, rig.actor, accepted["id"]) == accepted
    second, _ = admit(rig, parent); second = execute(rig, second)
    assert second["cache"]["hits"] == 0 and second["review"] == {**run["review"], "output_digest": second["review"]["output_digest"]}
    assert rig.chapters.list(rig.nid) == []


@pytest.mark.parametrize("waiting", [False, True])
def test_saved_child_change_invalidates_pin_reads_admission_execute_and_approval_but_keeps_cleanup(rig, waiting):
    child = create(rig, child_definition()); parent = create(rig, parent_definition(child)); run, body = admit(rig, parent)
    if waiting: run = execute(rig, run)
    retained = deepcopy(run["review"])
    service = owner(rig)
    service.save(rig.nid, rig.scope, rig.actor, child["id"], {"expected_version": 1, "definition": {**child["definition"], "title": "Even a title save changes the current pin"}})
    before = deepcopy(rig.raw_store.read(rig.nid, rig.scope))
    with pytest.raises(StaleSourceError): service.preflight(rig.nid, rig.scope, rig.actor, parent["id"], {"expected_version": 1})
    with pytest.raises(StaleSourceError): service.create_run(rig.nid, rig.scope, rig.actor, parent["id"], body)
    with pytest.raises(StaleSourceError): service.save(rig.nid, rig.scope, rig.actor, parent["id"], {"expected_version": 1, "definition": parent["definition"]})
    if waiting:
        with pytest.raises(StaleSourceError): approve(rig, run)
    else:
        with pytest.raises(StaleSourceError): execute(rig, run)
    assert rig.raw_store.read(rig.nid, rig.scope) == before
    masked = service.get_run(rig.nid, rig.scope, rig.actor, run["id"])
    assert masked["stale"] and masked["review"] is None and all(value["output"] is None for value in masked["node_states"].values())
    assert masked["local_subgraph_runtime"]["bindings"] == masked["local_subgraph_runtime"]["receipts"] == {}
    assert service.runs(rig.nid, rig.scope, rig.actor, parent["id"])["items"][0]["review"] is None
    action = "reject" if waiting else "cancel"
    payload = {"expected_version": run["version"]}
    if waiting: payload.update(node_id=retained["node_id"], reviewed_output_digest=retained["output_digest"])
    cleaned = service.action(rig.nid, rig.scope, rig.actor, run["id"], action, payload)
    assert cleaned["status"] == ("REJECTED" if waiting else "CANCELLED") and cleaned["review"] is None


def test_guard_revocation_during_child_evaluation_rolls_back_original_transaction_without_failed_write(rig, monkeypatch):
    child = create(rig, child_definition()); parent = create(rig, parent_definition(child)); run, _ = admit(rig, parent)
    service = owner(rig); allowed = True
    def guard():
        if not allowed: raise PermissionError("synthetic original authority revoked")
    original = service.executor.adapter.execute
    def evaluate(request):
        nonlocal allowed
        result = original(request)
        if request.node_type == "text_reference": allowed = False
        return result
    monkeypatch.setattr(service.executor.adapter, "execute", evaluate)
    before = deepcopy(rig.raw_store.read(rig.nid, rig.scope))
    with pytest.raises(PermissionError): service.action(rig.nid, rig.scope, rig.actor, run["id"], "execute", {"expected_version": 1}, guard)
    assert rig.raw_store.read(rig.nid, rig.scope) == before
    fresh = owner(rig).get_run(rig.nid, rig.scope, rig.actor, run["id"])
    assert fresh["status"] == "QUEUED" and fresh["version"] == 1 and all(row["output"] is None for row in fresh["node_states"].values())


def test_whole_child_is_pure_closed_and_requires_exact_unoccupied_boundary_and_total_capacity(rig):
    mutations = [lambda d: d["nodes"].append({"id": "hidden", "definition_id": "text_input", "parameters": {"text": "unused"}}),
        lambda d: d["nodes"][1].update(enabled=False),
        lambda d: d["edges"].clear(),
        lambda d: (d["nodes"].append({"id": "source", "definition_id": "text_input", "parameters": {"text": "occupied"}}), d["edges"].append({"id": "occupied", "source_node_id": "source", "source_port": "text", "target_node_id": "entry", "target_port": "text"})),
        lambda d: d["nodes"].append({"id": "review", "definition_id": "human_review"})]
    for mutate in mutations:
        definition = child_definition(); mutate(definition); child = create(rig, definition)
        before = deepcopy(rig.raw_store.read(rig.nid, rig.scope))
        with pytest.raises((ValueError, StaleSourceError)): create(rig, parent_definition(child))
        assert rig.raw_store.read(rig.nid, rig.scope) == before
    child = create(rig, child_definition()); parent = parent_definition(child)
    for field, value in [("input_node_id", "draft"), ("output_node_id", "entry"), ("definition_digest", "b" * 64), ("execution_digest", "c" * 64), ("expected_version", 2)]:
        invalid = deepcopy(parent); invalid["nodes"][1]["parameters"][field] = value
        with pytest.raises((ValueError, StaleSourceError)): create(rig, invalid)
    invalid = deepcopy(parent); invalid["nodes"][1]["parameters"]["server_authorized"] = True
    with pytest.raises(ValidationError): parse_graph(invalid)
    large = child_definition()
    large["nodes"] = [{"id": "entry", "definition_id": "text_reference"}, *[{"id": f"r{i}", "definition_id": "text_reference"} for i in range(14)], {"id": "draft", "definition_id": "draft_prepare"}]
    ids = [node["id"] for node in large["nodes"]]
    large["edges"] = [{"id": f"e{i}", "source_node_id": a, "source_port": "text", "target_node_id": b, "target_port": "text"} for i, (a, b) in enumerate(zip(ids, ids[1:]))]
    child = create(rig, large); parent = parent_definition(child)
    parent["nodes"].extend({"id": f"extra{i}", "definition_id": "text_input", "parameters": {"text": "author"}} for i in range(6))
    with pytest.raises(ValueError, match="TOTAL_NODE_CAPACITY"): create(rig, parent)


def test_legacy_catalog_and_output_contracts_stay_frozen_and_new_schema_rejects_models(rig):
    assert {row["id"] for row in catalog_definitions()} == {"text_input", "text_reference", "draft_prepare", "manual_transform", "director_note", "human_review", "asset_reference"}
    for version in range(1, 6): assert validate_output_ports("text_input", {"text": "Author"}, schema_version=version) == {"text": "Author"}
    with pytest.raises(ValueError): validate_output_ports("text_generate", {"draft": {"text": "not allowed", "origin": "MODEL_PROPOSAL"}}, schema_version=6)
    with pytest.raises(ValueError): validate_output_ports("local_subgraph", {"draft": {"text": "not allowed", "origin": "MODEL_PROPOSAL"}}, schema_version=6)


def test_shared_cooperative_five_second_budget_discards_all_child_output(rig, monkeypatch):
    from app.creative import graph_local_subgraph as subgraph
    child = create(rig, child_definition()); parent = create(rig, parent_definition(child)); run, _ = admit(rig, parent)
    service = owner(rig); clock = [0.0]; original = service.executor.adapter.execute
    monkeypatch.setattr(subgraph, "monotonic", lambda: clock[0])
    def step(request):
        value = original(request)
        if request.node_type in {"text_reference", "draft_prepare"}: clock[0] += 3.0
        return value
    monkeypatch.setattr(service.executor.adapter, "execute", step)
    failed = service.action(rig.nid, rig.scope, rig.actor, run["id"], "execute", {"expected_version": 1})
    assert failed["status"] == "FAILED" and failed["review"] is None
    assert failed["node_states"]["call"]["output"] is None
    assert failed["local_subgraph_runtime"]["receipts"] == {}
    assert clock[0] == 6.0


def test_missing_child_and_forged_run_binding_hide_outputs_and_keep_original_cancel(rig):
    child = create(rig, child_definition()); parent = create(rig, parent_definition(child)); queued, _ = admit(rig, parent); run = execute(rig, queued)
    with rig.raw_store.transaction(rig.nid, rig.scope) as state:
        state["collections"][owner(rig).RUNS][run["id"]]["local_subgraph_bindings"]["call"]["actor"] = "not-authorized"
    masked = owner(rig).get_run(rig.nid, rig.scope, rig.actor, run["id"])
    assert masked["stale"] and masked["review"] is None and all(v["output"] is None for v in masked["node_states"].values())
    with pytest.raises(StaleSourceError): approve(rig, run)
    with rig.raw_store.transaction(rig.nid, rig.scope) as state:
        del state["collections"][owner(rig).GRAPHS][child["id"]]
    graph = owner(rig).get(rig.nid, rig.scope, rig.actor, parent["id"])
    assert graph["reference_states"] == [{"node_id": "call", "state": "UNAVAILABLE"}]
    assert not graph["can_edit"] and graph["definition"]["nodes"][1]["parameters"] == {}
    cancelled = owner(rig).action(rig.nid, rig.scope, rig.actor, run["id"], "cancel", {"expected_version": run["version"]})
    assert cancelled["status"] == "CANCELLED" and cancelled["review"] is None


def test_foreign_actor_scope_pin_and_rebuilt_project_cannot_adopt_old_receipts(rig):
    service = owner(rig)
    foreign = service.create(rig.nid, rig.scope, "another-private-actor", {"request_id": uuid4().hex, "definition": child_definition()})
    before = deepcopy(rig.raw_store.read(rig.nid, rig.scope))
    with pytest.raises(StaleSourceError): create(rig, parent_definition(foreign))
    assert rig.raw_store.read(rig.nid, rig.scope) == before
    child = create(rig, child_definition()); parent = create(rig, parent_definition(child)); run, _ = admit(rig, parent)
    old = deepcopy(rig.raw_store.read(rig.nid, rig.scope)); incarnation = rig.store.incarnation(rig.nid)
    rig.novels.delete(rig.nid); rig.novels.create({"id": rig.nid, "title": "New owner same public slug"})
    assert owner(rig).store.incarnation(rig.nid) != incarnation
    # Deliberately transplant old durable rows, without replacing the new marker.
    with rig.raw_store.transaction(rig.nid, rig.scope) as state: state["collections"].update(old["collections"])
    with pytest.raises(FileNotFoundError): owner(rig).get_run(rig.nid, rig.scope, rig.actor, run["id"])
    with pytest.raises(FileNotFoundError): owner(rig).get(rig.nid, rig.scope, rig.actor, parent["id"])
    with pytest.raises(StaleSourceError): create(rig, parent_definition(child))


def test_child_output_and_server_receipt_caps_and_required_resolver_context_fail_closed(rig, monkeypatch):
    from app.creative import graph_local_subgraph as subgraph
    child = create(rig, child_definition()); parent = create(rig, parent_definition(child)); run, _ = admit(rig, parent)
    with pytest.raises(ValueError, match="REAL_CONTEXT_REQUIRED"):
        owner(rig)._preflight(owner(rig)._owned(rig.nid, rig.scope, rig.actor, owner(rig).GRAPHS, parent["id"]), {"expected_version": 1}, rig.actor)
    monkeypatch.setattr(subgraph, "MAX_OUTPUT_BYTES", 64)
    failed = execute(rig, run)
    assert failed["status"] == "FAILED" and failed["review"] is None and failed["local_subgraph_runtime"]["receipts"] == {}
    monkeypatch.setattr(subgraph, "MAX_SUBGRAPH_RECEIPT_BYTES", 64)
    before = deepcopy(rig.raw_store.read(rig.nid, rig.scope))
    with pytest.raises((ValueError, StaleSourceError)): create(rig, parent_definition(child))
    assert rig.raw_store.read(rig.nid, rig.scope) == before


@pytest.mark.parametrize("point", ["text_input", "text_reference"])
def test_observed_guard_value_error_is_never_converted_into_a_durable_failed_run(rig, monkeypatch, point):
    class AuthorityRevoked(ValueError): pass
    child = create(rig, child_definition()); parent = create(rig, parent_definition(child)); run, _ = admit(rig, parent)
    service = owner(rig); deny_once = [False]; original = service.executor.adapter.execute
    def guard():
        if deny_once[0]:
            deny_once[0] = False
            raise AuthorityRevoked("one observed original authority failure")
    def step(request):
        value = original(request)
        if request.node_type == point: deny_once[0] = True
        return value
    monkeypatch.setattr(service.executor.adapter, "execute", step)
    before = deepcopy(rig.raw_store.read(rig.nid, rig.scope))
    with pytest.raises(AuthorityRevoked): service.action(rig.nid, rig.scope, rig.actor, run["id"], "execute", {"expected_version": 1}, guard)
    assert rig.raw_store.read(rig.nid, rig.scope) == before


def test_original_parent_deadline_prevents_child_admission_and_publishes_no_output(rig, monkeypatch):
    from datetime import datetime, timedelta, timezone
    from app.creative import graph_local_subgraph as subgraph
    child = create(rig, child_definition()); parent = create(rig, parent_definition(child)); run, _ = admit(rig, parent)
    calls = []; original = subgraph.evaluate
    def evaluate(*args, **kwargs): calls.append(1); return original(*args, **kwargs)
    monkeypatch.setattr(subgraph, "evaluate", evaluate)
    with rig.raw_store.transaction(rig.nid, rig.scope) as state:
        row = state["collections"][owner(rig).RUNS][run["id"]]
        row["started_at"] = (datetime.now(timezone.utc) - timedelta(seconds=row["timeout_seconds"] + 2)).isoformat()
    expired = execute(rig, run)
    assert expired["status"] == "FAILED" and expired["review"] is None and calls == []
    assert all(v["output"] is None for v in expired["node_states"].values())
