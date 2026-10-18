"""Opt-in schema-1 historical dependency proof through real original owners."""
from copy import deepcopy
from uuid import uuid4

import pytest

from app.creative.graph_execution import DEPENDENCY_CACHE_MODE, digest
from app.creative.graph_models import GraphRunCreate
from app.experimental.common import StaleSourceError
from app.creative.project_store import BINDING
from test_v2_independent_workspace import rig
from test_v2_creative_graph_persistence import service, create, run, save, definition
from test_v2_creative_graph_execution import action, approve


def reuse(rig, graph, request_id=None, **kwargs):
    owner = service(rig)
    preview = owner.preflight(rig.nid, rig.scope, rig.actor, graph["id"], {"expected_version": graph["version"]})
    return owner.create_run(rig.nid, rig.scope, rig.actor, graph["id"], {
        "expected_graph_version": graph["version"], "reviewed_preflight_digest": preview["preflight_digest"],
        "request_id": request_id or uuid4().hex, "reuse_reviewed_local_dependencies": True, **kwargs})


def done(rig, graph):
    row = action(rig, reuse(rig, graph), "execute")
    while row["status"] == "WAITING_APPROVAL":
        row = approve(rig, row)
    return row


def test_default_wire_and_strict_opt_in():
    value = {"expected_graph_version": 1, "reviewed_preflight_digest": "a" * 64, "request_id": "test"}
    baseline = {**value, "target_node_ids": []}
    assert GraphRunCreate.model_validate(value).model_dump() == baseline
    assert GraphRunCreate.model_validate({**value, "reuse_reviewed_local_dependencies": False}).model_dump() == baseline
    for invalid in (1, "true", None):
        with pytest.raises(ValueError):
            GraphRunCreate.model_validate({**value, "reuse_reviewed_local_dependencies": invalid})


@pytest.mark.parametrize("edit", ["noop", "display", "reorder"])
def test_reviewed_cross_version_keeps_new_approval_and_exact_old_fence(rig, edit):
    graph = create(rig); source = done(rig, graph)
    admitted = reuse(rig, graph)
    value = deepcopy(graph["definition"])
    if edit == "display":
        value["title"] = "New display title"
        value["nodes"][0]["position"] = {"x": 50, "y": 80}
    if edit == "reorder":
        value["nodes"].reverse(); value["edges"].reverse()
    graph = save(rig, graph, value)
    with pytest.raises(StaleSourceError): action(rig, admitted, "execute")
    waiting = action(rig, reuse(rig, graph), "execute")
    assert waiting["cache"] == {"hits": 2, "misses": 0, "mode": DEPENDENCY_CACHE_MODE}
    assert waiting["status"] == "WAITING_APPROVAL" and not waiting["reviewed"]
    assert service(rig).get_run(rig.nid, rig.scope, rig.actor, source["id"])["stale"]
    raw = rig.raw_store.read(rig.nid, rig.scope)["collections"][service(rig).RUNS]
    assert raw[waiting["id"]]["cache_keys"]["prepare"]["key"] != raw[source["id"]]["cache_keys"]["prepare"]["key"]
    assert "dependency_signature" in raw[waiting["id"]]["cache_keys"]["prepare"]
    assert approve(rig, waiting)["status"] == "SUCCEEDED"


def test_independent_branch_and_same_bytes_ancestor_invalidate(rig):
    value = definition()
    value["nodes"][1].update(definition_id="manual_transform", parameters={"result": "Fixed"})
    other = definition()
    for node in other["nodes"]: node["id"] += "b"
    for edge in other["edges"]:
        edge["id"] += "b"; edge["source_node_id"] += "b"; edge["target_node_id"] += "b"
    value["nodes"] += other["nodes"]; value["edges"] += other["edges"]
    graph = create(rig, value); done(rig, graph)
    value["nodes"][0]["parameters"]["text"] = "Changed ancestor, same manual result"
    graph = save(rig, graph, value)
    result = done(rig, graph)
    assert result["cache"]["hits"] == 2 and result["cache"]["misses"] == 2


def test_equal_text_rewire_invalidates_descendant(rig):
    value = definition()
    value["nodes"].append({**deepcopy(value["nodes"][0]), "id": "other"})
    graph = create(rig, value); done(rig, graph)
    value["edges"][0]["source_node_id"] = "other"
    graph = save(rig, graph, value)
    waiting = action(rig, reuse(rig, graph), "execute")
    assert waiting["cache"]["hits"] == 1  # Original reviewed source only.
    assert waiting["cache"]["misses"] == 2


@pytest.mark.parametrize("corruption", ["actor", "scope", "project", "incarnation", "history", "graph_digest",
    "output", "engine", "receipt", "review_actor", "review_trace", "review_history", "review_delta", "review_draft", "source_version", "rejected", "unreviewed"])
def test_bad_historical_proof_is_a_miss(rig, corruption):
    graph = create(rig); source = done(rig, graph); graph = save(rig, graph)
    owner = service(rig)
    with rig.raw_store.transaction(rig.nid, rig.scope) as state:
        old = state["collections"][owner.RUNS][source["id"]]
        historical = state["collections"][owner.GRAPHS][graph["id"]]["history"][0]
        if corruption == "actor": old["created_by"] = "other"
        elif corruption == "scope": old["scope"] = {"mode": "local", "novel_id": "foreign"}
        elif corruption == "project": old["novel_id"] = "foreign"
        elif corruption == "incarnation": old[BINDING] = "foreign"
        elif corruption == "history": state["collections"][owner.GRAPHS][graph["id"]]["history"] = []
        elif corruption == "graph_digest": historical["definition_digest"] = "0" * 64
        elif corruption == "output": old["typed_outputs"]["text"] = {"text": "Forged"}
        elif corruption == "engine": old["node_states"]["text"]["output"]["result"]["ports"] = {"text": "Forged"}
        elif corruption == "receipt": old["cache_keys"]["text"]["key"] = "0" * 64
        elif corruption == "review_actor": old["node_states"]["review"]["output"]["approved_by"] = "other"
        elif corruption == "review_trace": old["trace"] = []
        elif corruption == "review_history": old["history"] = []
        elif corruption == "review_delta":
            event = next(item for item in old["trace"] if item["action"] == "WORKFLOW_NODE_APPROVED")
            event["node_statuses"]["text"] = "PENDING"
        elif corruption == "review_draft":
            waiting = next(item for item in old["history"] if item["status"] == "WAITING_APPROVAL")
            waiting["typed_outputs"]["prepare"]["draft"]["text"] = "Other review"
        elif corruption == "source_version": old["version"] = 0
        elif corruption == "rejected": old["status"] = "REJECTED"
        elif corruption == "unreviewed": old["reviewed"] = False
    assert action(rig, reuse(rig, graph), "execute")["cache"]["hits"] == 0


def test_revoke_cache_lookup_rolls_back_original_transitions(rig, monkeypatch):
    graph = create(rig); done(rig, graph); graph = save(rig, graph)
    queued = reuse(rig, graph); owner = service(rig)
    original = owner.executor._cached; revoked = False
    def lookup(*args, **kwargs):
        nonlocal revoked
        result = original(*args, **kwargs); revoked = True; return result
    def guard():
        if revoked: raise PermissionError("revoked")
    monkeypatch.setattr(owner.executor, "_cached", lookup)
    with pytest.raises(PermissionError):
        owner.action(rig.nid, rig.scope, rig.actor, queued["id"], "execute", {"expected_version": 1}, guard)
    assert service(rig).get_run(rig.nid, rig.scope, rig.actor, queued["id"])["status"] == "QUEUED"


def test_opt_in_replay_and_default_digest_unchanged(rig):
    graph = create(rig)
    first = reuse(rig, graph, request_id="opt-replay")
    assert reuse(rig, graph, request_id="opt-replay") == first
    old = run(rig, graph, request_id="default-replay")
    assert run(rig, graph, request_id="default-replay") == old
    raw = rig.raw_store.read(rig.nid, rig.scope)["collections"][service(rig).RUNS][old["id"]]
    assert "reuse_reviewed_local_dependencies" not in raw


@pytest.mark.parametrize("schema", [2, 3, 4, 5])
def test_other_schema_opt_in_is_rejected_even_all_local(rig, monkeypatch, schema):
    from app.creative.ai_execution import FLAGS
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", ",".join(FLAGS))
    value = definition() if schema in {2, 3} else {"title": "Local text", "nodes": [definition()["nodes"][0]], "edges": []}
    graph = create(rig, {**value, "schema_version": schema})
    with pytest.raises(ValueError, match="LOCAL_REUSE_SCHEMA1_REQUIRED"):
        reuse(rig, graph)


def test_schema2_missing_run_schema_is_not_historical_schema1_proof(rig, monkeypatch):
    from app.creative.ai_execution import FLAGS
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", ",".join(FLAGS))
    graph = create(rig, {**definition(), "schema_version": 2})
    old = approve(rig, action(rig, run(rig, graph), "execute"))
    stored = rig.raw_store.read(rig.nid, rig.scope)["collections"][service(rig).RUNS][old["id"]]
    assert "graph_schema_version" not in stored
    graph = save(rig, graph, definition())
    assert action(rig, reuse(rig, graph), "execute")["cache"]["hits"] == 0


def test_restart_and_legacy_source_still_require_host_claim_complete(rig, monkeypatch):
    from test_v2_independent_workspace import reopened
    from app.creative.graph import CreativeGraphService
    from app.services.v1_capability_service import V1CapabilityService
    graph = create(rig)
    approve(rig, action(rig, run(rig, graph), "execute"))
    graph = save(rig, graph)
    calls = []
    for name in ("trigger_agent_node", "claim_agent_task", "complete_agent_task", "approve_workflow_node"):
        original = getattr(V1CapabilityService, name)
        def capture(*args, _name=name, _original=original, **kwargs):
            calls.append(_name); return _original(*args, **kwargs)
        monkeypatch.setattr(V1CapabilityService, name, capture)
    queued = reuse(rig, graph)
    workspace = reopened(rig); owner = CreativeGraphService(workspace.store, workspace)
    waiting = owner.action(rig.nid, rig.scope, rig.actor, queued["id"], "execute", {"expected_version": 1})
    assert waiting["cache"]["hits"] == 2
    assert calls == ["trigger_agent_node", "claim_agent_task", "complete_agent_task"] * 2
    assert waiting["status"] == "WAITING_APPROVAL"


def test_forged_persisted_signature_never_overrides_ancestor_change(rig):
    graph = create(rig); source = done(rig, graph)
    value = deepcopy(graph["definition"]); value["nodes"][0]["parameters"]["text"] = "Changed"
    graph = save(rig, graph, value)
    owner = service(rig)
    with rig.raw_store.transaction(rig.nid, rig.scope) as state:
        state["collections"][owner.RUNS][source["id"]]["cache_keys"]["prepare"]["dependency_signature"] = {"malformed": True}
    assert action(rig, reuse(rig, graph), "execute")["cache"]["hits"] == 0


def test_live_value_error_guard_is_not_a_corrupt_candidate_miss(rig, monkeypatch):
    import app.creative.graph_local_reuse as reuse_module
    graph = create(rig); done(rig, graph); graph = save(rig, graph)
    queued = reuse(rig, graph); owner = service(rig)
    original = reuse_module._proof
    observed = False
    def proof(executor, target, source, actor, state, guard):
        nonlocal observed
        if source["id"] != target["id"]:
            observed = True
            guard()
        return original(executor, target, source, actor, state, guard)
    def guard():
        nonlocal observed
        if observed:
            observed = False  # A one-shot guard failure must still propagate.
            raise StaleSourceError("revoked during candidate proof")
    monkeypatch.setattr(reuse_module, "_proof", proof)
    with pytest.raises(StaleSourceError, match="revoked during"):
        owner.action(rig.nid, rig.scope, rig.actor, queued["id"], "execute", {"expected_version": 1}, guard)
    assert service(rig).get_run(rig.nid, rig.scope, rig.actor, queued["id"])["status"] == "QUEUED"


@pytest.mark.parametrize("field,value", [("reuse_reviewed_local_dependencies", None),
    ("reuse_reviewed_local_dependencies", False), ("reuse_reviewed_local_dependencies", "true"),
    ("reuse_reviewed_local_dependencies", 1), ("graph_schema_version", 2), ("cache_mode", "SAME_GRAPH_VERSION_REVIEWED_LOCAL_ONLY")])
def test_persisted_opt_in_binding_fails_closed(rig, field, value):
    graph = create(rig); queued = reuse(rig, graph); owner = service(rig)
    with rig.raw_store.transaction(rig.nid, rig.scope) as state:
        row = state["collections"][owner.RUNS][queued["id"]]
        if field == "cache_mode": row["cache"]["mode"] = value
        elif value is None: row.pop(field)
        else: row[field] = value
    with pytest.raises(StaleSourceError, match="LOCAL_REUSE_BINDING_CHANGED"):
        action(rig, queued, "execute")


@pytest.mark.parametrize("field", ["id", "created_by", "scope", BINDING, "graph_digest", "execution_digest", "version", "review_state", "empty_trace", "trace_status"])
def test_corrupt_waiting_history_envelope_is_a_miss(rig, field):
    graph = create(rig); source = done(rig, graph); graph = save(rig, graph); owner = service(rig)
    with rig.raw_store.transaction(rig.nid, rig.scope) as state:
        old = state["collections"][owner.RUNS][source["id"]]
        waiting = next(item for item in old["history"] if item["status"] == "WAITING_APPROVAL")
        if field == "review_state": waiting["node_states"]["review"]["status"] = "PENDING"
        elif field == "empty_trace": waiting["trace"] = []
        elif field == "trace_status": waiting["trace"][-1]["node_statuses"]["review"] = "PENDING"
        else: waiting[field] = 0 if field == "version" else "corrupt"
    assert action(rig, reuse(rig, graph), "execute")["cache"]["hits"] == 0


def test_destination_deadline_during_proof_stops_original_host(rig, monkeypatch):
    from datetime import datetime, timedelta
    import app.creative.graph_local_reuse as reuse_module
    import app.services.v1_capability_service as engine
    graph = create(rig); done(rig, graph); graph = save(rig, graph); queued = reuse(rig, graph)
    original = reuse_module._proof
    class Later(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.now(tz) + timedelta(hours=2)
    def proof(*args, **kwargs):
        monkeypatch.setattr(engine, "datetime", Later)
        return original(*args, **kwargs)
    monkeypatch.setattr(reuse_module, "_proof", proof)
    stopped = action(rig, queued, "execute")
    assert stopped["status"] == "FAILED" and stopped["cache"]["hits"] == 0
    stored = rig.raw_store.read(rig.nid, rig.scope)["collections"][service(rig).RUNS][queued["id"]]
    assert stored["error"]["code"] == "WORKFLOW_TIMEOUT" and stored["typed_outputs"] == {}
    assert any(item["action"] == "WORKFLOW_TIMED_OUT" for item in stored["trace"])
