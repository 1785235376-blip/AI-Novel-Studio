"""Selected real shared-store consumers, not an all-consumer certification.

Exercise WorldService, PlanningService and CreativeGraphService schema 1/2
through their actual File writers. Graph definitions remain authored drafts:
no model, workflow, generation, provider, or execution entry point is invoked.
"""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.creative.graph import CreativeGraphService
from app.experimental.planning import PlanningService
from app.experimental.store import LIFECYCLE, canonical
from app.experimental.world import WorldService
from app.services.v1_capability_service import CapabilityVersionConflict
from app.storage import atomic_write
from test_studio_asset_query import rig, shared_scope
from test_studio_asset_query_authority import source_snapshot

pytestmark = pytest.mark.file_backend_only
ACTOR = "local-author"


def ability(title="Authored ability"):
    return {"kind": "ABILITY", "title": title,
            "data": {"name": title, "description": "Authored synthetic test rule", "limits": {"range": 2.0}}}


@pytest.fixture(params=["legacy", "protected", "collaboration"])
def consumer(rig, request):
    raw = rig.workspace.store.store
    creative = rig.workspace.store
    creative.incarnation(rig.nid)
    world = WorldService(raw, rig.novels, rig.workspace.creative.chapters)
    planning = PlanningService(raw, rig.novels, rig.workspace.creative.chapters)
    mode = request.param
    if mode == "legacy":
        atomic_write(raw.path(rig.nid, rig.scope), canonical(raw.empty(rig.nid, rig.scope)))
        scope = rig.scope
        local_before = None
        metadata = None
    else:
        # Establish a protected local document with a real original consumer,
        # not metadata injection. All later unrelated consumers must preserve it.
        world.create_record(rig.nid, rig.scope, ACTOR, ability("Existing local world fact"))
        metadata = deepcopy(raw.read(rig.nid, rig.scope)[LIFECYCLE])
        local_before = raw.path(rig.nid, rig.scope).read_bytes()
        scope = shared_scope(rig)[0] if mode == "collaboration" else rig.scope
    return SimpleNamespace(rig=rig, raw=raw, creative=creative, world=world, planning=planning,
        mode=mode, scope=scope, metadata=metadata, local_before=local_before,
        actor="reader" if mode == "collaboration" else ACTOR)


def assert_scope_contract(case):
    document = case.raw.read(case.rig.nid, case.scope)
    if case.mode == "protected":
        assert document[LIFECYCLE] == case.metadata
    else:
        assert LIFECYCLE not in document
    if case.mode == "collaboration":
        assert case.raw.path(case.rig.nid, case.rig.scope).read_bytes() == case.local_before
        other_scope = {**case.scope, "branch_id": "query-branch-b"}
        assert case.raw.read(case.rig.nid, other_scope)["collections"] == {}
        assert not case.raw.path(case.rig.nid, other_scope).exists()


def assert_read_only_and_noop(case, read):
    before = source_snapshot(case.rig.root)
    read()
    with case.raw.transaction(case.rig.nid, case.scope):
        pass
    with case.creative.existing_owner_only(), case.creative.source_lease(case.rig.nid, case.scope):
        pass
    assert source_snapshot(case.rig.root) == before
    assert_scope_contract(case)


def test_real_world_ability_create_edit_reads_and_late_exception_rollback(consumer):
    case = consumer
    nid, scope, actor, world = case.rig.nid, case.scope, case.actor, case.world
    created = world.create_record(nid, scope, actor, ability())
    assert created["version"] == 1 and created["scope"] == scope
    edited = world.edit_record(nid, scope, actor, created["id"],
        {**ability("Edited authored ability"), "expected_version": 1})
    assert edited["version"] == 2 and len(edited["history"]) == 1
    assert edited["data"]["name"] == "Edited authored ability"
    assert world.record(nid, scope, created["id"])["stale"] is False
    assert_read_only_and_noop(case, lambda: world.records(nid, scope))
    before = source_snapshot(case.rig.root)
    calls = []

    def deny_after_mutation():
        calls.append(True)
        if len(calls) == 2:
            raise RuntimeError("injected final original reauthorization refusal")

    with pytest.raises(RuntimeError, match="final original reauthorization"):
        world.edit_record(nid, scope, actor, created["id"],
            {**ability("Must roll back"), "expected_version": 2}, reauthorize=deny_after_mutation)
    assert len(calls) == 2
    assert source_snapshot(case.rig.root) == before
    with pytest.raises(CapabilityVersionConflict):
        world.edit_record(nid, scope, actor, created["id"],
            {**ability("Stale edit"), "expected_version": 1})
    assert source_snapshot(case.rig.root) == before
    assert_scope_contract(case)


def test_real_planning_graph_volume_create_edit_and_original_transition_failure(consumer):
    case = consumer
    nid, scope, actor, planning = case.rig.nid, case.scope, case.actor, case.planning
    graph = planning.create_graph(nid, scope, actor, {"title": "Authored planning graph"})
    volume = planning.create_node(nid, scope, actor,
        {"title": "First volume", "graph_id": graph["id"], "parent_id": graph["root_node_id"], "level": "VOLUME"})
    edited = planning.edit_node(nid, scope, actor, volume["id"],
        {"title": "Edited first volume", "expected_version": 1, "fields": {"goal": "A manually authored goal"}})
    assert edited["version"] == 2 and edited["scope"] == scope and len(edited["history"]) == 1
    readback = planning.graph(nid, scope, graph["id"])
    assert {node["id"] for node in readback["nodes"]} == {graph["root_node_id"], volume["id"]}
    assert_read_only_and_noop(case, lambda: (planning.list_graphs(nid, scope), planning.graph(nid, scope, graph["id"])))
    before = source_snapshot(case.rig.root)
    with pytest.raises(ValueError, match="invalid graph transition"):
        planning.transition_graph(nid, scope, actor, graph["id"], "not-an-action", 1)
    with pytest.raises(CapabilityVersionConflict):
        planning.edit_node(nid, scope, actor, volume["id"], {"title": "Stale edit", "expected_version": 1})
    assert source_snapshot(case.rig.root) == before
    assert_scope_contract(case)


def graph_definition(schema):
    return {"schema_version": schema, "title": "Authored legacy graph draft",
        "nodes": [{"id": "AuthoredText", "definition_id": "text_input", "parameters": {"text": "Manually written"}}],
        "edges": []}


@pytest.mark.parametrize("schema", [1, 2])
def test_real_creative_graph_legacy_schemas_draft_idempotence_save_and_rollback(consumer, monkeypatch, schema):
    case = consumer
    # Schema 2 retains its original feature gate even for pure authored nodes.
    # Enabling that gate does not execute a model or configure a runtime.
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2,asset_lineage_v2,ai_execution_v2,model_broker_v2,author_context_inspector_v2")
    graph = CreativeGraphService(case.raw, case.rig.workspace)
    def execution_is_forbidden(*args, **kwargs):
        pytest.fail("Draft-only consumer regression must never execute a workflow or model")
    monkeypatch.setattr(graph.executor, "create", execution_is_forbidden)
    monkeypatch.setattr(graph.executor, "action", execution_is_forbidden)
    assert graph.model_runtime is None and graph.media_runtime is None
    nid, scope, actor = case.rig.nid, case.scope, case.actor
    body = {"request_id": "legacy-draft-create", "definition": graph_definition(schema)}
    created = graph.create(nid, scope, actor, body)
    assert created["definition"]["schema_version"] == schema and created["version"] == 1
    before = source_snapshot(case.rig.root)
    assert graph.create(nid, scope, actor, body) == created
    assert source_snapshot(case.rig.root) == before
    assert_read_only_and_noop(case, lambda: (graph.get(nid, scope, actor, created["id"]), graph.list(nid, scope, actor)))
    definition = deepcopy(created["definition"])
    definition["nodes"][0]["parameters"]["text"] = "Edited authored text"
    saved = graph.save(nid, scope, actor, created["id"], {"expected_version": 1, "definition": definition})
    assert saved["version"] == 2 and saved["definition"]["nodes"][0]["parameters"]["text"] == "Edited authored text"
    assert_scope_contract(case)
    before = source_snapshot(case.rig.root)
    with pytest.raises(CapabilityVersionConflict):
        graph.save(nid, scope, actor, created["id"], {"expected_version": 1, "definition": definition})
    with monkeypatch.context() as fault:
        def reject_mutated_capacity(state):
            # This original post-mutation capacity boundary runs before commit.
            assert state["collections"][graph.GRAPHS][created["id"]]["version"] == 3
            raise ValueError("injected original graph capacity refusal")
        fault.setattr(graph, "_capacity", reject_mutated_capacity)
        with pytest.raises(ValueError, match="original graph capacity refusal"):
            graph.save(nid, scope, actor, created["id"], {"expected_version": 2, "definition": definition})
    assert source_snapshot(case.rig.root) == before
    raw = case.raw.read(nid, scope)
    assert raw["collections"].get(graph.RUNS, {}) == {}
    assert_scope_contract(case)


@pytest.mark.parametrize("consumer_name", ["world", "planning"])
def test_real_raw_consumers_without_project_marker_do_not_create_or_claim_it(rig, consumer_name):
    raw = rig.workspace.store.store
    marker = rig.root / "novels" / rig.nid / "creative_project_v2.json"
    assert not marker.exists()
    if consumer_name == "world":
        service = WorldService(raw, rig.novels, rig.workspace.creative.chapters)
        saved = service.create_record(rig.nid, rig.scope, ACTOR, ability())
        service.edit_record(rig.nid, rig.scope, ACTOR, saved["id"], {**ability("Edited"), "expected_version": 1})
    else:
        service = PlanningService(raw, rig.novels, rig.workspace.creative.chapters)
        saved = service.create_graph(rig.nid, rig.scope, ACTOR, {"title": "Original unprotected graph"})
        service.edit_node(rig.nid, rig.scope, ACTOR, saved["root_node_id"], {"title": "Edited root", "expected_version": 1})
    assert not marker.exists()
    assert LIFECYCLE not in raw.read(rig.nid, rig.scope)
