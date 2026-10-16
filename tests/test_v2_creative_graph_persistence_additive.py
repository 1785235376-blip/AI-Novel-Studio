"""Additive reconciliation scenarios and their minimal independent fixture support."""

from __future__ import annotations

from copy import deepcopy

from uuid import uuid4

import pytest

from app.creative.graph import CreativeGraphService

from app.experimental.common import StaleSourceError

from app.services.v1_capability_service import CapabilityVersionConflict

from support_reconciliation_test_v2_independent_workspace import rig, import_asset, decoders

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

def save(rig, graph, value=None, guard=lambda: None):
    return service(rig).save(rig.nid, rig.scope, rig.actor, graph["id"],
        {"expected_version": graph["version"], "definition": value or graph["definition"]}, guard)

def asset_node(row):
    return {"id": "asset", "definition_id": "asset_reference", "parameters": {
        "asset_id": row["id"], "version": row["version"], "digest": row["sha256"], "kind": row["kind"]}}

def test_presentation_positions_and_camera_reopen_with_original_cas_owner(rig):
    """Presentation is already graph-owned; no independent preferences store."""
    original = create(rig)
    layout = deepcopy(original['definition'])
    layout['viewport'] = {'x': 123.0, 'y': -45.0, 'zoom': 1.4}
    for index, node in enumerate(layout['nodes']):
        node['position'] = {'x': index * 336.0, 'y': 48.0}
    updated = save(rig, original, layout)
    assert updated['definition'] == layout
    assert updated['definition_digest'] != original['definition_digest']
    assert updated['execution_digest'] == original['execution_digest']
    assert updated['version'] == original['version'] + 1
    # A fresh service instance reads the durable original row by stable graph ID.
    reopened = service(rig).get(rig.nid, rig.scope, rig.actor, original['id'])
    assert reopened == updated
    alternate = deepcopy(layout)
    alternate['viewport']['x'] = -600.0
    with pytest.raises(CapabilityVersionConflict):
        save(rig, original, alternate)
    assert service(rig).get(rig.nid, rig.scope, rig.actor, original['id']) == updated
    assert alternate['viewport']['x'] == -600.0
    assert rig.raw_store.read(rig.nid, rig.scope)['collections'].keys() == {service(rig).GRAPHS}

def test_canvas_annotation_original_owner_reopen_remove_and_cas(rig):
    original = create(rig)
    assert 'presentation' not in original['definition']
    annotated = deepcopy(original['definition'])
    annotated['presentation'] = {'comment': '场景组织说明\n<script>plain author text</script>'}
    updated = save(rig, original, annotated)
    assert service(rig).get(rig.nid, rig.scope, rig.actor, original['id']) == updated
    assert updated['definition'] == annotated
    assert updated['execution_digest'] == original['execution_digest']
    assert updated['definition_digest'] != original['definition_digest']
    with pytest.raises(CapabilityVersionConflict):
        save(rig, original, annotated)
    assert service(rig).get(rig.nid, rig.scope, rig.actor, original['id']) == updated
    restored = save(rig, updated, original['definition'])
    assert restored['definition'] == original['definition']
    assert restored['definition_digest'] == original['definition_digest']
    assert restored['execution_digest'] == original['execution_digest']
    assert service(rig).get(rig.nid, rig.scope, rig.actor, original['id']) == restored
    assert rig.raw_store.read(rig.nid, rig.scope)['collections'].keys() == {service(rig).GRAPHS}

def test_visual_groups_original_owner_reopen_rename_remove_and_cas(rig):
    original = create(rig)
    grouped = deepcopy(original['definition'])
    members = [node['id'] for node in grouped['nodes']]
    assert members
    grouped['presentation'] = {'comment': 'Keep annotation', 'groups': [
        {'id': 'group_1', 'name': 'Scene 🎬', 'node_ids': members}]}
    updated = save(rig, original, grouped)
    assert service(rig).get(rig.nid, rig.scope, rig.actor, original['id']) == updated
    assert updated['execution_digest'] == original['execution_digest']
    assert updated['definition'] == grouped
    with pytest.raises(CapabilityVersionConflict):
        save(rig, original, grouped)
    renamed = deepcopy(grouped)
    renamed['presentation']['groups'][0]['name'] = 'Renamed'
    updated = save(rig, updated, renamed)
    assert service(rig).get(rig.nid, rig.scope, rig.actor, original['id'])['definition'] == renamed
    del renamed['presentation']['groups']
    updated = save(rig, updated, renamed)
    assert updated['definition']['nodes'] == original['definition']['nodes']
    assert updated['definition']['presentation'] == {'comment': 'Keep annotation'}
    restored = save(rig, updated, original['definition'])
    assert restored['definition_digest'] == original['definition_digest']
    assert rig.raw_store.read(rig.nid, rig.scope)['collections'].keys() == {service(rig).GRAPHS}

def test_selected_subgraph_copy_original_owner_reopen_and_restore(rig):
    """Copied topology uses original save/CAS; no execution or separate store."""
    original = create(rig)
    draft = deepcopy(original['definition'])
    for node in original['definition']['nodes'][:2]:
        copied = deepcopy(node)
        copied['id'] = 'copy_' + node['id']
        copied['position'] = {axis: node['position'][axis] + 32 for axis in ('x', 'y')}
        draft['nodes'].append(copied)
    edge = deepcopy(original['definition']['edges'][0])
    edge.update(id='copy_e1', source_node_id='copy_text', target_node_id='copy_prepare')
    draft['edges'].append(edge)
    updated = save(rig, original, draft)
    assert updated['definition'] == draft
    assert service(rig).get(rig.nid, rig.scope, rig.actor, original['id']) == updated
    assert updated['definition']['nodes'][:3] == original['definition']['nodes']
    assert len(updated['definition']['edges']) == 3
    with pytest.raises(CapabilityVersionConflict):
        save(rig, original, draft)
    restored = save(rig, updated, original['definition'])
    assert restored['definition'] == original['definition']
    assert rig.raw_store.read(rig.nid, rig.scope)['collections'].keys() == {service(rig).GRAPHS}

def test_cross_graph_copy_original_owner_reopen_cas_and_source_unchanged(rig):
    source = create(rig)
    target = create(rig, {"title": "Target", "nodes": [], "edges": []})
    draft = deepcopy(target['definition'])
    for node in source['definition']['nodes'][:2]:
        copied = deepcopy(node)
        copied['id'] = 'copy_' + node['id']
        draft['nodes'].append(copied)
    edge = deepcopy(source['definition']['edges'][0])
    edge.update(id='copy_e1', source_node_id='copy_text', target_node_id='copy_prepare')
    draft['edges'].append(edge)
    updated = save(rig, target, draft)
    assert service(rig).get(rig.nid, rig.scope, rig.actor, target['id']) == updated
    assert updated['definition'] == draft
    assert service(rig).get(rig.nid, rig.scope, rig.actor, source['id']) == source
    with pytest.raises(CapabilityVersionConflict):
        save(rig, target, draft)
    restored = save(rig, updated, target['definition'])
    assert restored['definition'] == target['definition']
    assert rig.raw_store.read(rig.nid, rig.scope)['collections'].keys() == {service(rig).GRAPHS}

def test_cross_graph_copy_added_source_pin_revalidated_by_original_save(rig, decoders):
    asset = import_asset(rig)
    source = create(rig, {'title': 'Source', 'nodes': [asset_node(asset)], 'edges': []})
    target = create(rig, {'title': 'Target', 'nodes': [], 'edges': []})
    draft = deepcopy(target['definition'])
    copied = deepcopy(source['definition']['nodes'][0]); copied['id'] = 'copy_asset'
    draft['nodes'].append(copied)
    # An invalid version is rejected atomically; no lifecycle/security mutation is involved.
    copied['parameters']['version'] += 1
    with pytest.raises(StaleSourceError, match='EXTERNAL_REFERENCE_CHANGED'):
        save(rig, target, draft)
    assert service(rig).get(rig.nid, rig.scope, rig.actor, target['id']) == target
    copied['parameters']['version'] = asset['version']
    updated = save(rig, target, draft)
    assert updated['definition']['nodes'][0]['parameters'] == source['definition']['nodes'][0]['parameters']
    assert service(rig).get(rig.nid, rig.scope, rig.actor, target['id']) == updated
    assert service(rig).get(rig.nid, rig.scope, rig.actor, source['id']) == source

def test_view_preferences_original_owner_reopen_cas_and_remove(rig):
    original = create(rig)
    changed = deepcopy(original['definition'])
    changed['presentation'] = {'view': {'show_grid': False, 'snap': True, 'grid_step': 16, 'show_minimap': False}}
    updated = save(rig, original, changed)
    assert updated['definition'] == changed
    assert updated['execution_digest'] == original['execution_digest']
    assert updated['definition_digest'] != original['definition_digest']
    assert service(rig).get(rig.nid, rig.scope, rig.actor, original['id']) == updated
    with pytest.raises(CapabilityVersionConflict):
        save(rig, original, original['definition'])
    assert service(rig).get(rig.nid, rig.scope, rig.actor, original['id']) == updated
    removed = save(rig, updated, original['definition'])
    assert removed['definition_digest'] == original['definition_digest']
    assert service(rig).get(rig.nid, rig.scope, rig.actor, original['id']) == removed

def test_nested_visual_groups_original_owner_reopen_remove_and_cas(rig):
    original = create(rig)
    draft = deepcopy(original['definition'])
    members = [node['id'] for node in draft['nodes']]
    draft['presentation'] = {'groups': [
        {'id': 'root', 'name': 'Root', 'node_ids': members[:1]},
        {'id': 'child', 'name': 'Child', 'node_ids': members[1:], 'parent_id': 'root'}]}
    updated = save(rig, original, draft)
    assert service(rig).get(rig.nid, rig.scope, rig.actor, original['id']) == updated
    assert updated['execution_digest'] == original['execution_digest']
    assert updated['definition']['nodes'] == original['definition']['nodes']
    assert updated['definition']['edges'] == original['definition']['edges']
    with pytest.raises(CapabilityVersionConflict):
        save(rig, original, draft)
    promoted = deepcopy(draft)
    promoted['presentation']['groups'].pop(0)
    del promoted['presentation']['groups'][0]['parent_id']
    updated = save(rig, updated, promoted)
    assert service(rig).get(rig.nid, rig.scope, rig.actor, original['id'])['definition'] == promoted
    restored = save(rig, updated, original['definition'])
    assert restored['definition_digest'] == original['definition_digest']

def test_canvas_notes_original_owner_reopen_move_remove_and_cas(rig):
    original = create(rig)
    draft = deepcopy(original['definition'])
    draft['presentation'] = {'notes': [{'id': f'n{i}', 'text': f'Scene {i} 🎬', 'position': {'x': float(i * 300), 'y': 0.0}} for i in range(128)]}
    updated = save(rig, original, draft)
    assert service(rig).get(rig.nid, rig.scope, rig.actor, original['id']) == updated
    assert updated['execution_digest'] == original['execution_digest']
    assert updated['definition']['nodes'] == original['definition']['nodes']
    with pytest.raises(CapabilityVersionConflict):
        save(rig, original, draft)
    changed = deepcopy(draft)
    changed['presentation']['notes'][0].update(text='Edited', position={'x': -800.0, 'y': 600.0})
    updated = save(rig, updated, changed)
    assert service(rig).get(rig.nid, rig.scope, rig.actor, original['id'])['definition'] == changed
    removed = save(rig, updated, original['definition'])
    assert removed['definition_digest'] == original['definition_digest']
    assert rig.raw_store.read(rig.nid, rig.scope)['collections'].keys() == {service(rig).GRAPHS}
