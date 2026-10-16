"""Original WorkflowRun transitions and deterministic local receipt boundaries."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.experimental.common import StaleSourceError
from app.services.v1_capability_service import CapabilityVersionConflict, V1CapabilityService
from test_v2_independent_workspace import rig
from test_v2_creative_graph_persistence import service, create, run, save, definition


def action(rig, row, name, **extra):
    return service(rig).action(rig.nid, rig.scope, rig.actor, row["id"], name,
        {"expected_version": row["version"], **extra})


def approve(rig, row):
    return action(rig, row, "approve", node_id=row["review"]["node_id"],
                  reviewed_output_digest=row["review"]["output_digest"])


def test_original_host_owns_claim_complete_and_explicit_review(rig, monkeypatch):
    calls = []
    for name in ("trigger_agent_node", "claim_agent_task", "complete_agent_task", "approve_workflow_node"):
        original = getattr(V1CapabilityService, name)
        def capture(*args, _name=name, _original=original, **kwargs):
            calls.append(_name)
            return _original(*args, **kwargs)
        monkeypatch.setattr(V1CapabilityService, name, capture)
    graph = create(rig)
    queued = run(rig, graph)
    waiting = action(rig, queued, "execute")
    assert waiting["status"] == "WAITING_APPROVAL"
    assert waiting["review"]["draft"]["text"] == "First beat\nSecond beat"
    assert not waiting["reviewed"] and waiting["cache"]["hits"] == 0
    done = approve(rig, waiting)
    assert done["status"] == "SUCCEEDED" and done["reviewed"]
    assert all(done[key] is False for key in ("model_called", "applied")) and done["external_calls"] == 0
    assert calls.count("trigger_agent_node") == calls.count("claim_agent_task") == calls.count("complete_agent_task") == 2
    assert calls[-1] == "approve_workflow_node"
    assert rig.chapters.list(rig.nid) == []
    assert set(rig.raw_store.read(rig.nid, rig.scope)["collections"]) == {service(rig).GRAPHS, service(rig).RUNS}


def test_exact_review_cas_cancel_reject_and_late_actions(rig):
    graph = create(rig)
    waiting = action(rig, run(rig, graph), "execute")
    for fields in ({}, {"node_id": "text", "reviewed_output_digest": waiting["review"]["output_digest"]},
                   {"node_id": "review", "reviewed_output_digest": "0" * 64}):
        with pytest.raises(StaleSourceError, match="EXACT_REVIEW"):
            action(rig, waiting, "approve", **fields)
    rejected = action(rig, waiting, "reject", node_id="review", reviewed_output_digest=waiting["review"]["output_digest"])
    assert rejected["status"] == "REJECTED" and all(item["output"] is None for item in rejected["node_states"].values())
    with pytest.raises(CapabilityVersionConflict): approve(rig, waiting)
    with pytest.raises(StaleSourceError):
        action(rig, rejected, "approve", node_id="review", reviewed_output_digest=waiting["review"]["output_digest"])
    queued = run(rig, graph)
    cancelled = action(rig, queued, "cancel")
    assert cancelled["status"] == "CANCELLED"
    with pytest.raises(ValueError): action(rig, cancelled, "execute")


def test_pause_resume_and_empty_required_inputs_are_explicit(rig):
    graph = create(rig)
    queued = run(rig, graph)
    paused = action(rig, queued, "pause")
    assert paused["status"] == "PAUSED"
    resumed = action(rig, paused, "resume")
    assert resumed["status"] == "WAITING_APPROVAL"
    for value, code in (({"title": "Empty"}, "EMPTY_SELECTION"),
                        ({"title": "Incomplete", "nodes": [{"id": "draft", "definition_id": "draft_prepare"}]}, "REQUIRED_INPUT_MISSING")):
        incomplete = create(rig, value)
        preflight = service(rig).preflight(rig.nid, rig.scope, rig.actor, incomplete["id"], {"expected_version": 1})
        assert not preflight["executable"] and any(code in item["code"] for item in preflight["issues"])
        with pytest.raises(ValueError, match="EXECUTION_BLOCKED"): run(rig, incomplete)


def test_director_is_optional_removable_and_does_not_generate_text(rig):
    value = definition()
    value["nodes"].append({"id": "director", "definition_id": "director_note", "parameters": {"note": "Slow camera"}})
    value["edges"].append({"id": "direction", "source_node_id": "director", "source_port": "direction",
                           "target_node_id": "prepare", "target_port": "direction"})
    graph = create(rig, value)
    waiting = action(rig, run(rig, graph), "execute")
    assert waiting["review"]["draft"]["direction"] == {"note": "Slow camera"}
    assert waiting["review"]["draft"]["text"] == "First beat\nSecond beat"
    independent = save(rig, graph, {**definition(), "nodes": definition()["nodes"] + [
        {"id": "second", "definition_id": "text_input", "parameters": {"text": "Independent"}}]})
    single = action(rig, run(rig, independent, ["second"]), "execute")
    assert single["status"] == "SUCCEEDED" and single["review"] is None and not single["reviewed"]
    assert set(single["node_states"]) == {"second"}


def test_disabled_dependency_blocks_only_its_selected_component(rig):
    value = definition(); value["nodes"][0]["enabled"] = False
    value["nodes"].append({"id": "free", "definition_id": "text_input", "parameters": {"text": "Independent"}})
    graph = create(rig, value)
    with pytest.raises(ValueError, match="EXECUTION_BLOCKED"): run(rig, graph)
    assert action(rig, run(rig, graph, ["free"]), "execute")["status"] == "SUCCEEDED"


def test_manual_transform_keeps_exact_author_result(rig):
    value = definition(); value["nodes"][1].update(definition_id="manual_transform", parameters={"result": "Exact manual replacement"})
    graph = create(rig, value)
    waiting = action(rig, run(rig, graph), "execute")
    assert waiting["review"]["draft"] == {"text": "Exact manual replacement", "origin": "MANUAL"}


def test_reviewed_local_cache_never_reuses_approval_or_foreign_actor(rig):
    graph = create(rig)
    done = approve(rig, action(rig, run(rig, graph), "execute"))
    assert done["status"] == "SUCCEEDED"
    cached = action(rig, run(rig, graph), "execute")
    assert cached["cache"]["hits"] == 2 and cached["cache"]["misses"] == 0
    assert cached["status"] == "WAITING_APPROVAL" and not cached["reviewed"]
    with pytest.raises(FileNotFoundError):
        service(rig).get_run(rig.nid, rig.scope, "other", done["id"])
    newer = save(rig, graph)
    uncached = action(rig, run(rig, newer), "execute")
    assert uncached["cache"]["hits"] == 0


def test_unreviewed_component_receipts_are_not_promoted_by_another_review(rig):
    value = definition(); value["nodes"].append({"id": "unreviewed", "definition_id": "text_input", "parameters": {"text": "No review"}})
    graph = create(rig, value)
    completed = approve(rig, action(rig, run(rig, graph), "execute"))
    assert completed["status"] == "SUCCEEDED" and not completed["node_states"]["unreviewed"]["reviewed"]
    second = action(rig, run(rig, graph), "execute")
    second = approve(rig, second)
    assert second["cache"]["hits"] == 2 and second["cache"]["misses"] == 1


def test_rejected_and_failed_results_never_seed_cache(rig):
    graph = create(rig)
    waiting = action(rig, run(rig, graph), "execute")
    action(rig, waiting, "reject", node_id="review", reviewed_output_digest=waiting["review"]["output_digest"])
    assert action(rig, run(rig, graph), "execute")["cache"]["hits"] == 0
    bad = definition(); bad["nodes"][0]["parameters"]["text"] = "line\n" * 101
    failed = action(rig, run(rig, create(rig, bad)), "execute")
    assert failed["status"] == "FAILED" and failed["node_states"]["review"]["status"] == "PENDING"


def test_run_admission_idempotency_and_exact_preflight(rig):
    graph = create(rig)
    first = run(rig, graph, request_id="same")
    assert run(rig, graph, request_id="same") == first
    with pytest.raises(ValueError, match="REQUEST_ID_REUSED"):
        run(rig, graph, ["text"], request_id="same")
    with pytest.raises(StaleSourceError, match="EXACT_PREFLIGHT"):
        service(rig).create_run(rig.nid, rig.scope, rig.actor, graph["id"], {
            "expected_graph_version": 1, "request_id": uuid4().hex, "reviewed_preflight_digest": "0" * 64})


def test_revoke_during_local_operation_aborts_all_engine_transitions(rig, monkeypatch):
    owner = service(rig)
    graph = create(rig); queued = run(rig, graph)
    original = owner.executor.adapter.execute
    revoked = False
    def execute(request):
        nonlocal revoked
        result = original(request); revoked = True; return result
    def guard():
        if revoked: raise PermissionError("revoked")
    monkeypatch.setattr(owner.executor.adapter, "execute", execute)
    with pytest.raises(PermissionError):
        owner.action(rig.nid, rig.scope, rig.actor, queued["id"], "execute", {"expected_version": 1}, guard)
    current = service(rig).get_run(rig.nid, rig.scope, rig.actor, queued["id"])
    assert current["status"] == "QUEUED" and current["version"] == 1
    assert all(item["status"] == "PENDING" for item in current["node_states"].values())


def test_restart_preserves_review_and_does_not_automatically_replay(rig, monkeypatch):
    graph = create(rig); waiting = action(rig, run(rig, graph), "execute")
    owner = service(rig)
    monkeypatch.setattr(owner.executor.adapter, "execute", lambda *_: pytest.fail("unexpected replay"))
    assert owner.get_run(rig.nid, rig.scope, rig.actor, waiting["id"]) == waiting
    done = owner.action(rig.nid, rig.scope, rig.actor, waiting["id"], "approve", {
        "expected_version": waiting["version"], "node_id": "review", "reviewed_output_digest": waiting["review"]["output_digest"]})
    assert done["status"] == "SUCCEEDED"


def test_timeout_prevents_late_review_through_original_owner(rig):
    graph = create(rig); waiting = action(rig, run(rig, graph), "execute")
    with rig.store.transaction(rig.nid, rig.scope) as state:
        state["collections"][service(rig).RUNS][waiting["id"]]["started_at"] = "2000-01-01T00:00:00+00:00"
    timed = approve(rig, waiting)
    assert timed["status"] == "FAILED" and timed["review"] is None
    assert timed["node_states"]["review"]["status"] == "WAITING_APPROVAL"


def test_persisted_engine_definition_cannot_turn_node_into_checkpoint(rig):
    graph = create(rig); queued = run(rig, graph)
    with rig.store.transaction(rig.nid, rig.scope) as state:
        raw = state["collections"][service(rig).RUNS][queued["id"]]
        raw["definition_snapshot"]["nodes"][0]["type"] = "checkpoint"
    with pytest.raises(StaleSourceError, match="ENGINE_BINDING_CHANGED"):
        action(rig, queued, "execute")
    view = service(rig).get_run(rig.nid, rig.scope, rig.actor, queued["id"])
    assert view["stale"] and all(item["output"] is None for item in view["node_states"].values())


def test_invalid_adapter_output_cannot_enter_typed_review_or_cache(rig, monkeypatch):
    graph = create(rig); queued = run(rig, graph)
    owner = service(rig)
    monkeypatch.setattr(owner.executor.adapter, "execute", lambda *_: {"unknown": "untrusted schema"})
    result = owner.action(rig.nid, rig.scope, rig.actor, queued["id"], "execute", {"expected_version": 1})
    assert result["status"] == "FAILED" and result["review"] is None and not result["reviewed"]
    assert result["cache"]["hits"] == result["cache"]["misses"] == 0


def test_persisted_output_requires_original_host_and_cache_receipts(rig):
    graph = create(rig); waiting = action(rig, run(rig, graph), "execute")
    with rig.store.transaction(rig.nid, rig.scope) as state:
        raw = state["collections"][service(rig).RUNS][waiting["id"]]
        raw["typed_outputs"]["text"]["text"] = "different source"
    with pytest.raises(ValueError, match="OUTPUT_RECEIPT_INVALID"):
        service(rig).get_run(rig.nid, rig.scope, rig.actor, waiting["id"])


def test_multiple_independent_components_require_each_review(rig):
    value = definition()
    other = definition()
    for node in other["nodes"]:
        node["id"] += "2"
    for edge in other["edges"]:
        edge["id"] += "2"; edge["source_node_id"] += "2"; edge["target_node_id"] += "2"
    value["nodes"].extend(other["nodes"]); value["edges"].extend(other["edges"])
    graph = create(rig, value)
    first = action(rig, run(rig, graph), "execute")
    next_review = approve(rig, first)
    assert next_review["status"] == "WAITING_APPROVAL" and not next_review["reviewed"]
    assert next_review["review"]["node_id"] != first["review"]["node_id"]
    done = approve(rig, next_review)
    assert done["status"] == "SUCCEEDED" and done["reviewed"]


def test_original_hour_deadline_is_fixed_at_admission_and_public_exactly(rig, monkeypatch):
    from app.creative import graph_execution
    from app.services.v1_capability_service import WorkflowRunIn
    admitted = (datetime.now(timezone.utc) - timedelta(seconds=61)).isoformat()
    monkeypatch.setattr(graph_execution, "now", lambda: admitted)
    graph = create(rig); queued = run(rig, graph)
    assert queued["timeout_seconds"] == WorkflowRunIn.model_fields["timeout_seconds"].default == 3600
    assert queued["deadline_at"] == (datetime.fromisoformat(admitted) + timedelta(seconds=3600)).isoformat()
    waiting = action(rig, queued, "execute")
    # A human review after more than the removed 30-second adapter timeout is
    # still valid under the existing original WorkflowRun owner's hour budget.
    assert waiting["status"] == "WAITING_APPROVAL" and waiting["deadline_at"] == queued["deadline_at"]
    done = approve(rig, waiting)
    assert done["status"] == "SUCCEEDED" and done["deadline_at"] == queued["deadline_at"]
    raw = service(rig)._owned(rig.nid, rig.scope, rig.actor, service(rig).RUNS, done["id"])
    assert raw["started_at"] == admitted
    limits = service(rig).catalog(rig.nid, rig.scope, rig.actor)["limits"]
    assert limits["runtime_timeout_seconds"] == 3600 and limits["node_timeout_seconds"] == 5


def test_queued_expiry_cannot_be_reset_by_execute(rig, monkeypatch):
    from app.creative import graph_execution
    admitted = (datetime.now(timezone.utc) - timedelta(seconds=3601)).isoformat()
    monkeypatch.setattr(graph_execution, "now", lambda: admitted)
    graph = create(rig); queued = run(rig, graph)
    before = queued["deadline_at"]
    expired = action(rig, queued, "execute")
    assert expired["status"] == "FAILED" and expired["deadline_at"] == before
    assert all(node["status"] == "PENDING" for node in expired["node_states"].values())
    assert expired["cache"]["hits"] == expired["cache"]["misses"] == 0
    raw = service(rig)._owned(rig.nid, rig.scope, rig.actor, service(rig).RUNS, expired["id"])
    assert raw["started_at"] == admitted


def test_pause_and_resume_never_extend_admission_deadline(rig, monkeypatch):
    from app.creative import graph_execution
    admitted = (datetime.now(timezone.utc) - timedelta(seconds=65)).isoformat()
    monkeypatch.setattr(graph_execution, "now", lambda: admitted)
    graph = create(rig); queued = run(rig, graph)
    paused = action(rig, queued, "pause")
    assert paused["status"] == "PAUSED" and paused["deadline_at"] == queued["deadline_at"]
    resumed = action(rig, paused, "resume")
    assert resumed["status"] == "WAITING_APPROVAL" and resumed["deadline_at"] == queued["deadline_at"]
    paused_review = action(rig, resumed, "pause")
    assert paused_review["deadline_at"] == queued["deadline_at"]
    with rig.store.transaction(rig.nid, rig.scope) as state:
        state["collections"][service(rig).RUNS][paused_review["id"]]["started_at"] = "2000-01-01T00:00:00+00:00"
    expired = action(rig, paused_review, "resume")
    assert expired["status"] == "FAILED"
    assert expired["deadline_at"] == "2000-01-01T01:00:00+00:00"


@pytest.mark.parametrize("field,value", [
    ("timeout_seconds", True), ("timeout_seconds", 3600.0), ("timeout_seconds", "3600"),
    ("timeout_seconds", 30), ("timeout_seconds", 3601), ("timeout_seconds", 0),
    ("started_at", None), ("started_at", True), ("started_at", 0),
    ("started_at", "2026-10-09T13:00:00"), ("started_at", "2026-10-09T13:00:00+01:00"),
    ("started_at", "invalid"), ("started_at", "9999-12-31T23:59:59+00:00"),
])
def test_persisted_runtime_timing_never_coerces_or_extends_limits(rig, field, value):
    graph = create(rig); queued = run(rig, graph)
    with rig.store.transaction(rig.nid, rig.scope) as state:
        state["collections"][service(rig).RUNS][queued["id"]][field] = value
    with pytest.raises(ValueError, match="RUNTIME_TIMING_INVALID"):
        service(rig).get_run(rig.nid, rig.scope, rig.actor, queued["id"])
    with pytest.raises(ValueError, match="RUNTIME_TIMING_INVALID"):
        action(rig, queued, "execute")
