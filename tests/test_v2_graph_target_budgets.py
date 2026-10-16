"""Saved-schema target allowances preserve the original DTOs and media closure.

Run with the original isolated V2 harness and real File/PostgreSQL rig. These
graphs execute only original local rules, never a provider or model transport.
"""
from copy import deepcopy
from contextlib import contextmanager
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.creative.graph import CreativeGraphService
from app.creative.graph_execution import digest
from app.creative.graph_models import (
    GraphPreflight, GraphRunCreate, GraphMediaPreflight, GraphMediaRunCreate,
    parse_graph_preflight, parse_graph_run_create,
)
from app.creative.project_store import BINDING
from app.experimental.common import StaleSourceError
from app.services.v1_capability_service import CapabilityVersionConflict
from test_v2_independent_workspace import rig, reopened, branch_scope


DIGEST = "a" * 64
FLAGS = "narrative_production_v2,asset_lineage_v2,ai_execution_v2,model_broker_v2,author_context_inspector_v2"


def definition(schema=3, count=24, *, chain=False):
    return {"schema_version": schema, "title": "Saved-schema target budget", "nodes": [
        {"id": f"n{i}", "definition_id": "text_reference" if chain and i else "text_input",
         "parameters": {} if chain and i else {"text": "Local authored text"}}
        for i in range(count)], "edges": [
        {"id": f"e{i}", "source_node_id": f"n{i - 1}", "source_port": "text",
         "target_node_id": f"n{i}", "target_port": "text"}
        for i in range(1, count)] if chain else []}


def owner(rig):
    workspace = reopened(rig)
    return CreativeGraphService(workspace.store, workspace)


def create(e, rig, value):
    return e.create(rig.nid, rig.scope, rig.actor,
        {"request_id": uuid4().hex, "definition": value})


def preflight(e, rig, graph, targets):
    return e.preflight(rig.nid, rig.scope, rig.actor, graph["id"],
        {"expected_version": graph["version"], "target_node_ids": targets})


def run_body(graph, flight, targets):
    return {"expected_graph_version": graph["version"], "reviewed_preflight_digest": flight["preflight_digest"],
            "target_node_ids": targets, "request_id": uuid4().hex}


@pytest.mark.parametrize("base,media,payload", [
    (GraphPreflight, GraphMediaPreflight, {"expected_version": 1}),
    (GraphRunCreate, GraphMediaRunCreate,
     {"expected_graph_version": 1, "reviewed_preflight_digest": DIGEST, "request_id": "bounded"}),
])
def test_original_and_media_envelopes_have_identical_fields_and_distinct_limits(base, media, payload):
    assert set(base.model_fields) == set(media.model_fields)
    assert base.model_json_schema()["properties"]["target_node_ids"]["maxItems"] == 16
    assert media.model_json_schema()["properties"]["target_node_ids"]["maxItems"] == 24
    for count in (0, 16):
        value = {**payload, "target_node_ids": [f"n{i}" for i in range(count)]}
        assert base.model_validate(value).model_dump() == media.model_validate(value).model_dump()
    for count in (17, 24):
        value = {**payload, "target_node_ids": [f"n{i}" for i in range(count)]}
        with pytest.raises(ValidationError): base.model_validate(value)
        assert media.model_validate(value).target_node_ids == value["target_node_ids"]
    for value in ([f"n{i}" for i in range(25)], ["bad id"], [1], None, "n0"):
        with pytest.raises(ValidationError): media.model_validate({**payload, "target_node_ids": value})
    with pytest.raises(ValidationError, match="extra_forbidden"):
        media.model_validate({**payload, "schema_version": 3})


@pytest.mark.parametrize("schema", [1, 2])
def test_parsed_media_instances_cannot_grant_old_schema_a_larger_budget(schema):
    saved = definition(schema, 16)
    flight = GraphMediaPreflight(expected_version=1, target_node_ids=[f"n{i}" for i in range(17)])
    body = GraphMediaRunCreate(expected_graph_version=1, reviewed_preflight_digest=DIGEST,
                              request_id="bounded", target_node_ids=flight.target_node_ids)
    with pytest.raises(ValidationError, match="too_long"): parse_graph_preflight(flight, saved)
    with pytest.raises(ValidationError, match="too_long"): parse_graph_run_create(body, saved)
    assert parse_graph_preflight(flight, definition()).model_dump() == flight.model_dump()
    assert parse_graph_run_create(body, definition()).model_dump() == body.model_dump()


@pytest.mark.parametrize("schema,count", [(1, 16), (2, 16), (3, 17), (3, 24)])
def test_saved_schema_targets_empty_expansion_digest_and_reopen(rig, monkeypatch, schema, count):
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", FLAGS)
    e = owner(rig)
    graph = create(e, rig, definition(schema, count))
    # The frontend posts this expanded list, even when the author selected [].
    flight = preflight(e, rig, graph, [])
    targets = [f"n{i}" for i in range(count)]
    assert flight["executable"] and flight["target_node_ids"] == targets
    assert preflight(e, rig, graph, targets) == flight
    body = run_body(graph, flight, flight["target_node_ids"])
    queued = e.create_run(rig.nid, rig.scope, rig.actor, graph["id"], body)
    raw = e._owned(rig.nid, rig.scope, rig.actor, e.RUNS, queued["id"])
    assert raw["request_digest"] == digest([graph["id"], body, raw[BINDING], rig.scope, rig.actor])
    assert e.create_run(rig.nid, rig.scope, rig.actor, graph["id"], body) == queued
    loaded = owner(rig)
    assert loaded.get_run(rig.nid, rig.scope, rig.actor, queued["id"]) == queued
    done = loaded.action(rig.nid, rig.scope, rig.actor, queued["id"], "execute", {"expected_version": queued["version"]})
    assert done["status"] == "SUCCEEDED" and not done["stale"]
    assert len(done["node_states"]) == count and done["external_calls"] == 0 and not done["model_called"]
    assert owner(rig).get_run(rig.nid, rig.scope, rig.actor, done["id"]) == done


@pytest.mark.parametrize("schema", [1, 2, 3])
def test_service_rejects_overflow_instances_duplicates_invalid_ids_and_caller_schema(rig, monkeypatch, schema):
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", FLAGS)
    e = owner(rig)
    count = 24 if schema == 3 else 16
    graph = create(e, rig, definition(schema, count))
    flight = preflight(e, rig, graph, [])
    before = deepcopy(rig.raw_store.read(rig.nid, rig.scope))
    for targets in ([f"n{i}" for i in range(count + 1)], ["n0", "n0"], ["absent"], ["bad id"], [1]):
        with pytest.raises((ValidationError, ValueError)):
            preflight(e, rig, graph, targets)
        with pytest.raises((ValidationError, ValueError)):
            e.create_run(rig.nid, rig.scope, rig.actor, graph["id"], run_body(graph, flight, targets))
    if schema != 3:
        targets = [f"n{i}" for i in range(17)]
        for envelope in (GraphMediaPreflight(expected_version=1, target_node_ids=targets),
                         GraphPreflight.model_construct(expected_version=1, target_node_ids=targets)):
            with pytest.raises(ValidationError, match="too_long"):
                e.preflight(rig.nid, rig.scope, rig.actor, graph["id"], envelope)
            with pytest.raises(ValidationError, match="too_long"):
                e._preflight(e._owned(rig.nid, rig.scope, rig.actor, e.GRAPHS, graph["id"]), envelope, rig.actor)
        with pytest.raises(ValidationError, match="too_long"):
            e.executor.create(rig.nid, rig.scope, rig.actor, graph["id"],
                GraphMediaRunCreate(**run_body(graph, flight, targets)), lambda: None)
    for method, value in ((e.preflight, {"expected_version": 1}),
                          (e.create_run, run_body(graph, flight, []))):
        with pytest.raises(ValidationError, match="extra_forbidden"):
            method(rig.nid, rig.scope, rig.actor, graph["id"], {**value, "schema_version": 3})
    assert rig.raw_store.read(rig.nid, rig.scope) == before


def test_one_target_with_twenty_four_node_closure_reopens_and_executes(rig):
    e = owner(rig)
    graph = create(e, rig, definition(chain=True))
    flight = preflight(e, rig, graph, ["n23"])
    assert flight["target_node_ids"] == ["n23"] and len(flight["selected_closure"]) == 24
    body = GraphRunCreate(**run_body(graph, flight, ["n23"]))
    queued = e.create_run(rig.nid, rig.scope, rig.actor, graph["id"], body)
    loaded = owner(rig)
    assert loaded.get_run(rig.nid, rig.scope, rig.actor, queued["id"]) == queued
    done = loaded.action(rig.nid, rig.scope, rig.actor, queued["id"], "execute", {"expected_version": 1})
    assert done["status"] == "SUCCEEDED" and not done["stale"]
    assert done["node_states"]["n23"]["output"] == {"text": "Local authored text"}
    assert owner(rig).get_run(rig.nid, rig.scope, rig.actor, done["id"]) == done


def test_media_budget_retains_scope_revocation_and_cas(rig, monkeypatch):
    e = owner(rig)
    graph = create(e, rig, definition())
    flight = preflight(e, rig, graph, [])
    body = GraphMediaRunCreate(**run_body(graph, flight, flight["target_node_ids"]))
    before = deepcopy(rig.raw_store.read(rig.nid, rig.scope))
    for actor, scope in (("another-actor", rig.scope), (rig.actor, branch_scope(rig))):
        with pytest.raises(FileNotFoundError): e.create_run(rig.nid, scope, actor, graph["id"], body)
    with pytest.raises(CapabilityVersionConflict):
        e.create_run(rig.nid, rig.scope, rig.actor, graph["id"], {**body.model_dump(), "expected_graph_version": 2})
    with pytest.raises(StaleSourceError, match="EXACT_PREFLIGHT"):
        e.create_run(rig.nid, rig.scope, rig.actor, graph["id"], {**body.model_dump(), "reviewed_preflight_digest": DIGEST})
    original = e._preflight
    revoked = False
    def revoke_after_plan(*args, **kwargs):
        nonlocal revoked
        result = original(*args, **kwargs)
        revoked = True
        return result
    def guard():
        if revoked: raise PermissionError("revoked")
    monkeypatch.setattr(e, "_preflight", revoke_after_plan)
    with pytest.raises(PermissionError):
        e.create_run(rig.nid, rig.scope, rig.actor, graph["id"], body, guard)
    assert rig.raw_store.read(rig.nid, rig.scope) == before


@pytest.mark.parametrize("schema", [1, 2])
def test_schema_downgrade_retains_stale_cas_before_current_target_budget(rig, monkeypatch, schema):
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", FLAGS)
    e = owner(rig)
    graph = create(e, rig, definition())
    flight = preflight(e, rig, graph, [])
    body = GraphMediaRunCreate(**run_body(graph, flight, flight["target_node_ids"]))
    changed = e.save(rig.nid, rig.scope, rig.actor, graph["id"],
        {"expected_version": 1, "definition": definition(schema, 16)})
    before = deepcopy(rig.raw_store.read(rig.nid, rig.scope))
    with pytest.raises(CapabilityVersionConflict): preflight(e, rig, graph, flight["target_node_ids"])
    with pytest.raises(CapabilityVersionConflict):
        e.create_run(rig.nid, rig.scope, rig.actor, graph["id"], body)
    with pytest.raises(ValidationError, match="too_long"):
        preflight(e, rig, changed, flight["target_node_ids"])
    with pytest.raises(ValidationError, match="too_long"):
        e.create_run(rig.nid, rig.scope, rig.actor, graph["id"], {**body.model_dump(), "expected_graph_version": 2})
    assert rig.raw_store.read(rig.nid, rig.scope) == before


@pytest.mark.parametrize("schema", [1, 2])
def test_admission_uses_schema_reread_inside_original_transaction(rig, monkeypatch, schema):
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", FLAGS)
    e = owner(rig)
    graph = create(e, rig, definition())
    flight = preflight(e, rig, graph, [])
    body = {**run_body(graph, flight, flight["target_node_ids"]), "expected_graph_version": 2}
    transaction = e.asset_inputs.transaction
    @contextmanager
    def changed_before_lock(*args, **kwargs):
        e.save(rig.nid, rig.scope, rig.actor, graph["id"],
            {"expected_version": 1, "definition": definition(schema, 16)})
        with transaction(*args, **kwargs) as state:
            yield state
    monkeypatch.setattr(e.asset_inputs, "transaction", changed_before_lock)
    with pytest.raises(ValidationError, match="too_long"):
        e.create_run(rig.nid, rig.scope, rig.actor, graph["id"], body)
    persisted = owner(rig)
    assert persisted.get(rig.nid, rig.scope, rig.actor, graph["id"])["definition"]["schema_version"] == schema
    assert persisted.runs(rig.nid, rig.scope, rig.actor, graph["id"]) == {"items": []}
