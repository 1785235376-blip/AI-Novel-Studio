"""GRAPH-21 bounded retry through genuine File owners, never a model or queue."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier
from uuid import uuid4

import pytest

from app.creative.graph import CreativeGraphService
from app.experimental.common import StaleSourceError
from app.services.v1_capability_service import CapabilityVersionConflict
from test_v2_independent_workspace import rig, reopened, branch_scope, import_asset
from test_v2_creative_graph_persistence import service, create, run, save, definition, asset_node
from test_v2_creative_graph_execution import action


def failed(rig):
    value = definition()
    # Real deterministic rule failure: the existing draft recipe limits lines.
    value["nodes"][0]["parameters"]["text"] = "line\n" * 101
    graph = create(rig, value)
    source = action(rig, run(rig, graph, targets=["review"]), "execute")
    assert source["status"] == "FAILED"
    return graph, source


def request(rig, graph, source, key=None):
    flight = service(rig).preflight(rig.nid, rig.scope, rig.actor, graph["id"], {
        "expected_version": graph["version"], "target_node_ids": sorted(source["node_states"])})
    return {"expected_version": source["version"], "expected_graph_version": graph["version"],
        "reviewed_preflight_digest": flight["preflight_digest"], "request_id": key or "retry-" + uuid4().hex}


def retry(rig, source, body, owner=None, **kwargs):
    return (owner or service(rig)).executor.retry_failed_local(rig.nid, rig.scope, rig.actor, source["id"], body,
        kwargs.get("guard", lambda: None))


def test_file_reopen_same_key_preserves_failure_and_only_queues_new_attempt(rig, monkeypatch):
    graph, source = failed(rig)
    body = request(rig, graph, source)
    owner = service(rig)
    before = deepcopy(rig.raw_store.read(rig.nid, rig.scope))
    monkeypatch.setattr(owner.executor.adapter, "execute", lambda *_: pytest.fail("retry executed a node"))
    new = retry(rig, source, body, owner)
    assert new["id"] != source["id"] and new["status"] == "QUEUED"
    assert new["retry_of"] == source["id"] and new["attempt"] == 2
    assert new["version"] == 1 and not new["reviewed"] and new["review"] is None
    assert not new["model_called"] and new["external_calls"] == 0
    assert all(node["status"] == "PENDING" and node["output"] is None for node in new["node_states"].values())
    fresh_workspace = reopened(rig)
    fresh = CreativeGraphService(fresh_workspace.store, fresh_workspace)
    # Simulates an admission reply lost after commit: reopen the physical File
    # owner and resubmit the exact request, without copying or restoring state.
    assert retry(rig, source, body, fresh) == new
    after = rig.raw_store.read(rig.nid, rig.scope)
    old = before["collections"][owner.RUNS][source["id"]]
    assert after["collections"][owner.RUNS][source["id"]] == old
    assert len(after["collections"][owner.RUNS]) == 2
    child = after["collections"][owner.RUNS][new["id"]]
    assert child["selected_closure"] == old["selected_closure"]
    assert child["typed_nodes"] == old["typed_nodes"] and child["input"] == old["input"]
    assert child["trace"] == child["dispatch_trace"] == child["history"] == []
    # Execution is still a separate command. Failure can itself be retried,
    # retaining the immediate parent rather than replacing the first attempt.
    again_failed = fresh.action(rig.nid, rig.scope, rig.actor, new["id"], "execute", {"expected_version": 1})
    third = retry(rig, again_failed, request(rig, graph, again_failed), fresh)
    assert third["attempt"] == 3 and third["retry_of"] == new["id"]
    assert source["id"] in rig.raw_store.read(rig.nid, rig.scope)["collections"][owner.RUNS]


def test_file_concurrent_duplicate_clicks_share_one_admission(rig):
    graph, source = failed(rig)
    body = request(rig, graph, source)
    barrier = Barrier(2)
    def admit(_):
        barrier.wait(timeout=10)
        return retry(rig, source, body)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(admit, (1, 2)))
    assert results[0] == results[1]
    assert len(rig.raw_store.read(rig.nid, rig.scope)["collections"][service(rig).RUNS]) == 2


def test_allowlist_applies_to_the_entire_graph_not_just_selected_nodes(rig):
    value = definition()
    value["nodes"][0]["parameters"]["text"] = "line\n" * 101
    value["nodes"].append(asset_node(import_asset(rig)))
    graph = create(rig, value)
    source = action(rig, run(rig, graph, targets=["review"]), "execute")
    assert source["status"] == "FAILED" and "asset" not in source["node_states"]
    before = rig.raw_store.path(rig.nid, rig.scope).read_bytes()
    with pytest.raises(ValueError, match="SCHEMA1_LOCAL_REQUIRED"):
        retry(rig, source, request(rig, graph, source))
    assert rig.raw_store.path(rig.nid, rig.scope).read_bytes() == before


@pytest.mark.parametrize("status", ["QUEUED", "RUNNING", "PAUSED", "WAITING_APPROVAL", "SUCCEEDED", "CANCELLED", "REJECTED", "UNKNOWN"])
def test_only_confirmed_failed_is_eligible(rig, status):
    graph, source = failed(rig)
    body = request(rig, graph, source)
    with rig.store.transaction(rig.nid, rig.scope) as state:
        state["collections"][service(rig).RUNS][source["id"]]["status"] = status
    before = rig.raw_store.path(rig.nid, rig.scope).read_bytes()
    with pytest.raises(ValueError, match="RETRY_FAILED_REQUIRED"):
        retry(rig, source, body)
    assert rig.raw_store.path(rig.nid, rig.scope).read_bytes() == before


@pytest.mark.parametrize("patch", [
    {"input": {"text": "changed"}}, {"model_execution_contract": "creative-graph-model/1"},
    {"model_execution": {"status": "UNKNOWN"}}, {"media_executions": {"x": {"status": "UNKNOWN"}}},
    {"graph_schema_version": 6}, {"attempt": True}, {"attempt": 100},
])
def test_input_external_runtime_and_invalid_attempt_are_rejected(rig, patch):
    graph, source = failed(rig)
    body = request(rig, graph, source)
    with rig.store.transaction(rig.nid, rig.scope) as state:
        state["collections"][service(rig).RUNS][source["id"]].update(patch)
    before = rig.raw_store.path(rig.nid, rig.scope).read_bytes()
    with pytest.raises(ValueError, match="RETRY_"):
        retry(rig, source, body)
    assert rig.raw_store.path(rig.nid, rig.scope).read_bytes() == before


def test_source_version_graph_definition_preflight_and_request_key_are_exact(rig):
    graph, source = failed(rig)
    body = request(rig, graph, source)
    with pytest.raises(CapabilityVersionConflict):
        retry(rig, source, {**body, "expected_version": source["version"] + 1})
    with pytest.raises(StaleSourceError, match="EXACT_PREFLIGHT"):
        retry(rig, source, {**body, "reviewed_preflight_digest": "0" * 64})
    new = retry(rig, source, body)
    # An ordinary creation cannot borrow the retry's idempotency key.
    with pytest.raises(ValueError, match="REQUEST_ID_REUSED"):
        run(rig, graph, targets=sorted(source["node_states"]), request_id=body["request_id"])
    other = action(rig, run(rig, graph), "execute")
    with pytest.raises(ValueError, match="REQUEST_ID_REUSED"):
        retry(rig, other, request(rig, graph, other, body["request_id"]))
    changed = deepcopy(graph["definition"])
    changed["nodes"][0]["parameters"]["text"] = "corrected input"
    latest = save(rig, graph, changed)
    # Neither network recovery nor a newly read preflight may refresh old pins.
    with pytest.raises(CapabilityVersionConflict): retry(rig, source, body)
    with pytest.raises(StaleSourceError, match="DEFINITION_CHANGED"):
        retry(rig, source, request(rig, latest, source))
    assert new["id"] in rig.raw_store.read(rig.nid, rig.scope)["collections"][service(rig).RUNS]


def test_actor_scope_incarnation_and_late_permission_revocation(rig, monkeypatch):
    graph, source = failed(rig)
    body = request(rig, graph, source)
    owner = service(rig)
    for scope, actor in ((rig.scope, "other-author"), (branch_scope(rig), rig.actor)):
        with pytest.raises(FileNotFoundError):
            owner.executor.retry_failed_local(rig.nid, scope, actor, source["id"], body, lambda: None)
    before = rig.raw_store.path(rig.nid, rig.scope).read_bytes()
    revoked = False
    original_capacity = owner._capacity
    def capacity(state):
        nonlocal revoked
        original_capacity(state)
        revoked = True
    def guard():
        if revoked: raise PermissionError("revoked before commit")
    monkeypatch.setattr(owner, "_capacity", capacity)
    with pytest.raises(PermissionError, match="revoked"):
        retry(rig, source, body, owner, guard=guard)
    assert rig.raw_store.path(rig.nid, rig.scope).read_bytes() == before
    rig.novels.delete(rig.nid)
    rig.create_project(nid=rig.nid)
    with pytest.raises(FileNotFoundError): retry(rig, source, body)
