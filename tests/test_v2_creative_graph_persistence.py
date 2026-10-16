"""M2-A real File/PostgreSQL private scope and incarnation persistence.

Run in the owned V2 profile; the shared M1 fixture verifies genuine PostgreSQL.
"""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest

from app.creative.graph import CreativeGraphService
from app.experimental.common import StaleSourceError
from app.services.v1_capability_service import CapabilityVersionConflict
from test_v2_independent_workspace import rig, import_asset, decoders, branch_scope


def service(rig):
    return CreativeGraphService(rig.store, rig.service)


def definition():
    return {"title": "Independent local graph", "nodes": [
        {"id": "text", "definition_id": "text_input", "parameters": {"text": "First beat\nSecond beat"}},
        {"id": "prepare", "definition_id": "draft_prepare"},
        {"id": "review", "definition_id": "human_review"}], "edges": [
        {"id": "e1", "source_node_id": "text", "source_port": "text", "target_node_id": "prepare", "target_port": "text"},
        {"id": "e2", "source_node_id": "prepare", "source_port": "draft", "target_node_id": "review", "target_port": "draft"}]}


def create(rig, graph=None, **kw):
    return service(rig).create(rig.nid, rig.scope, rig.actor,
        {"request_id": "create-" + uuid4().hex, "definition": graph or definition()}, **kw)


def run(rig, graph, targets=None, request_id=None):
    owner = service(rig)
    preview = owner.preflight(rig.nid, rig.scope, rig.actor, graph["id"],
        {"expected_version": graph["version"], "target_node_ids": targets or []})
    return owner.create_run(rig.nid, rig.scope, rig.actor, graph["id"], {
        "expected_graph_version": graph["version"], "reviewed_preflight_digest": preview["preflight_digest"],
        "target_node_ids": targets or [], "request_id": request_id or "run-" + uuid4().hex})


def save(rig, graph, value=None, guard=lambda: None):
    return service(rig).save(rig.nid, rig.scope, rig.actor, graph["id"],
        {"expected_version": graph["version"], "definition": value or graph["definition"]}, guard)


def asset_node(row):
    return {"id": "asset", "definition_id": "asset_reference", "parameters": {
        "asset_id": row["id"], "version": row["version"], "digest": row["sha256"], "kind": row["kind"]}}


def test_empty_disconnected_graphs_reopen_without_chapter_or_model(rig):
    owner = service(rig)
    for value in ({"title": "Empty", "nodes": [], "edges": []}, definition()):
        row = create(rig, value)
        assert service(rig).get(rig.nid, rig.scope, rig.actor, row["id"]) == row
        assert row["project_id"] == rig.nid and row["scope"] == rig.scope and row["can_edit"]
        assert rig.chapters.list(rig.nid) == []
    assert len(owner.list(rig.nid, rig.scope, rig.actor)["items"]) == 2
    assert owner.catalog(rig.nid, rig.scope, rig.actor)["capabilities"]["model_execution"] is False
    assert rig.raw_store.read(rig.nid, rig.scope)["collections"].keys() == {owner.GRAPHS}


def test_create_idempotency_and_cas_conflicts_preserve_input(rig):
    owner = service(rig)
    body = {"request_id": "same-request", "definition": definition()}
    first = owner.create(rig.nid, rig.scope, rig.actor, body)
    assert owner.create(rig.nid, rig.scope, rig.actor, body) == first
    with pytest.raises(ValueError, match="REQUEST_ID_REUSED"):
        owner.create(rig.nid, rig.scope, rig.actor, {**body, "definition": {**definition(), "title": "Other"}})
    edited = save(rig, first, {**first["definition"], "title": "Updated"})
    assert edited["version"] == 2
    with pytest.raises(CapabilityVersionConflict):
        save(rig, first)
    assert owner.get(rig.nid, rig.scope, rig.actor, first["id"]) == edited


def test_concurrent_save_has_one_real_cas_winner(rig):
    row = create(rig)
    barrier = Barrier(2)
    def update(index):
        barrier.wait(timeout=10)
        try:
            return save(rig, row, {**row["definition"], "title": str(index)})
        except CapabilityVersionConflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(update, (1, 2)))
    assert sum(isinstance(item, dict) for item in results) == 1
    assert results.count("conflict") == 1


def test_actor_scope_and_project_identity_are_not_interchangeable(rig):
    owner = service(rig)
    row = create(rig)
    queued = run(rig, row)
    assert owner.list(rig.nid, rig.scope, "other-actor") == {"items": []}
    for operation in (
        lambda: owner.get(rig.nid, rig.scope, "other-actor", row["id"]),
        lambda: owner.get_run(rig.nid, rig.scope, "other-actor", queued["id"]),
        lambda: owner.get(rig.nid, branch_scope(rig), rig.actor, row["id"]),
    ):
        with pytest.raises(FileNotFoundError): operation()
    raw = deepcopy(rig.raw_store.read(rig.nid, rig.scope))
    rig.novels.delete(rig.nid)
    rig.create_project(nid=rig.nid)
    assert owner.list(rig.nid, rig.scope, rig.actor) == {"items": []}
    with pytest.raises(FileNotFoundError): owner.get_run(rig.nid, rig.scope, rig.actor, queued["id"])
    assert rig.raw_store.read(rig.nid, rig.scope) == raw


def test_failed_current_authority_guard_aborts_graph_commit(rig):
    owner = service(rig)
    before = rig.raw_store.read(rig.nid, rig.scope)
    calls = 0
    def guard():
        nonlocal calls
        calls += 1
        if calls >= 4:
            raise PermissionError("revoked")
    with pytest.raises(PermissionError):
        owner.create(rig.nid, rig.scope, rig.actor, {"request_id": "denied", "definition": definition()}, guard)
    assert rig.raw_store.read(rig.nid, rig.scope) == before


def test_definition_change_invalidates_pending_run_without_exposing_old_output(rig):
    owner = service(rig)
    graph = create(rig)
    queued = run(rig, graph)
    save(rig, graph, {**graph["definition"], "title": "New version"})
    view = owner.get_run(rig.nid, rig.scope, rig.actor, queued["id"])
    assert view["stale"] and view["review"] is None
    with pytest.raises(StaleSourceError):
        owner.action(rig.nid, rig.scope, rig.actor, queued["id"], "execute", {"expected_version": 1})
    cancelled = owner.action(rig.nid, rig.scope, rig.actor, queued["id"], "cancel", {"expected_version": 1})
    assert cancelled["status"] == "CANCELLED"


def test_asset_reference_is_nonexecuting_and_outside_scope_transaction(rig, decoders, monkeypatch):
    asset = import_asset(rig)
    value = definition(); value["nodes"].append(asset_node(asset))
    owner = service(rig)
    original = rig.service._row
    def outside(*args, **kwargs):
        assert not getattr(rig.store._local, "active", {})
        return original(*args, **kwargs)
    monkeypatch.setattr(rig.service, "_row", outside)
    row = create(rig, value)
    assert row["reference_states"] == [{"node_id": "asset", "state": "CURRENT"}]
    preview = owner.preflight(rig.nid, rig.scope, rig.actor, row["id"], {"expected_version": 1})
    assert not preview["executable"]
    with pytest.raises(ValueError, match="EXECUTION_BLOCKED"):
        run(rig, row)
    # An unrelated component is eligible without touching the asset owner.
    monkeypatch.setattr(rig.service, "_row", lambda *args, **kwargs: pytest.fail("execution touched asset owner"))
    queued = run(rig, row, ["review"])
    assert queued["status"] == "QUEUED"
    result = owner.action(rig.nid, rig.scope, rig.actor, queued["id"], "execute", {"expected_version": 1})
    assert result["status"] == "WAITING_APPROVAL"


def test_unavailable_reference_redaction_cannot_drop_binding_on_full_put(rig, decoders):
    asset = import_asset(rig)
    value = definition(); value["nodes"].append(asset_node(asset))
    owner = service(rig)
    graph = create(rig, value)
    replacement = deepcopy(graph["definition"]); replacement["nodes"] = replacement["nodes"][:-1]
    with pytest.raises(ValueError, match="EXTERNAL_DETACH_UNAVAILABLE"):
        save(rig, graph, replacement)
    rig.service.lifecycle(rig.nid, rig.scope, asset["id"], asset["version"])
    projected = owner.get(rig.nid, rig.scope, rig.actor, graph["id"])
    assert projected["can_edit"] is False
    assert projected["definition"]["nodes"][-1]["parameters"] == {}
    assert asset["id"] not in str(projected)
    with pytest.raises(ValueError, match="EXTERNAL_BINDING_READ_ONLY"):
        save(rig, graph, replacement)
    assert owner._owned(rig.nid, rig.scope, rig.actor, owner.GRAPHS, graph["id"])["definition"] == graph["definition"]


def test_graph_current_snapshot_corruption_is_fail_closed(rig):
    graph = create(rig)
    with rig.store.transaction(rig.nid, rig.scope) as state:
        state["collections"][service(rig).GRAPHS][graph["id"]]["definition"]["title"] = "tampered"
    with pytest.raises(ValueError, match="CORRUPT"):
        service(rig).get(rig.nid, rig.scope, rig.actor, graph["id"])


def test_late_recreated_owner_suppresses_old_graph_projection(rig, monkeypatch):
    owner = service(rig); graph = create(rig)
    original = owner._view
    def recreate_after_projection(*args, **kwargs):
        result = original(*args, **kwargs)
        rig.novels.delete(rig.nid); rig.create_project(nid=rig.nid)
        return result
    monkeypatch.setattr(owner, "_view", recreate_after_projection)
    with pytest.raises(StaleSourceError, match="AUTHORITY_CHANGED"):
        owner.get(rig.nid, rig.scope, rig.actor, graph["id"])


def test_failed_scope_write_preserves_previous_complete_definition(rig, monkeypatch):
    graph = create(rig)
    old = deepcopy(rig.raw_store.read(rig.nid, rig.scope))
    # The real capacity guard is inside the scope transaction, so a failing
    # update must not publish even a changed title or history snapshot.
    owner = service(rig)
    monkeypatch.setattr(owner, "_capacity", lambda state: (_ for _ in ()).throw(ValueError("bounded capacity")))
    with pytest.raises(ValueError, match="bounded capacity"):
        owner.save(rig.nid, rig.scope, rig.actor, graph["id"], {
            "expected_version": 1, "definition": {**graph["definition"], "title": "Not committed"}})
    assert rig.raw_store.read(rig.nid, rig.scope) == old
