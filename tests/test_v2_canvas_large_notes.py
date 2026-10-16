"""Original File-owner large display notes; no model or lifecycle/security task."""
from copy import deepcopy
import json
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError
from app.creative.graph import CreativeGraphService, digest, execution_definition
from app.creative.graph_models import parse_graph
from app.experimental.store import canonical
from app.services.v1_capability_service import CapabilityVersionConflict
from test_v2_independent_workspace import rig, reopened


def notes(count):
    return [{'id': f'note_{i + 1}', 'text': f'雨夜·镜头{i + 1:04d}',
             'position': {'x': float((i % 40) * 320), 'y': float((i // 40) * 220)}} for i in range(count)]


def owner(rig):
    workspace = reopened(rig)
    return CreativeGraphService(workspace.store, workspace)


@pytest.mark.parametrize('count', [1000, 1024])
def test_thousand_meaningful_notes_create_save_restart_history_and_legacy_digest(rig, count):
    service = owner(rig)
    legacy = parse_graph({'title': 'Original saved graph'}).model_dump()
    before = service.create(rig.nid, rig.scope, rig.actor, {'request_id': 'legacy-' + uuid4().hex, 'definition': legacy})
    definition = {**legacy, 'presentation': {'notes': notes(count)}}
    created = service.create(rig.nid, rig.scope, rig.actor, {'request_id': 'notes-' + uuid4().hex, 'definition': definition})
    assert created['definition'] == definition and len(canonical(definition).encode()) < 96_000
    assert created['execution_digest'] == before['execution_digest']
    changed = deepcopy(definition)
    changed['presentation']['notes'][-1].update(text='人工修改·镜头终点', position={'x': -200.5, 'y': 400.0})
    updated = service.save(rig.nid, rig.scope, rig.actor, created['id'], {'expected_version': 1, 'definition': changed})
    restored = owner(rig)
    assert restored.get(rig.nid, rig.scope, rig.actor, created['id']) == updated
    assert restored.get(rig.nid, rig.scope, rig.actor, before['id']) == before
    assert updated['execution_digest'] == created['execution_digest']
    assert updated['definition_digest'] != created['definition_digest']
    assert updated['definition']['nodes'] == [] and updated['definition']['edges'] == []
    with pytest.raises(CapabilityVersionConflict):
        restored.save(rig.nid, rig.scope, rig.actor, created['id'], {'expected_version': 1, 'definition': definition})
    assert owner(rig).get(rig.nid, rig.scope, rig.actor, created['id']) == updated
    stored = rig.raw_store.read(rig.nid, rig.scope)['collections'][service.GRAPHS][created['id']]
    assert len(stored['history']) == 1 and stored['history'][0]['definition'] == definition
    removed = restored.save(rig.nid, rig.scope, rig.actor, created['id'], {'expected_version': 2, 'definition': legacy})
    assert removed['definition_digest'] == before['definition_digest'] == digest(legacy)
    assert owner(rig).get(rig.nid, rig.scope, rig.actor, created['id']) == removed
    assert rig.raw_store.read(rig.nid, rig.scope)['collections'].keys() == {service.GRAPHS}


def test_thousand_note_original_history_quota_stays_atomic(rig):
    service = owner(rig)
    definition = parse_graph({'title': 'Bounded note history', 'presentation': {'notes': notes(1000)}}).model_dump()
    row = service.create(rig.nid, rig.scope, rig.actor, {'request_id': 'history-' + uuid4().hex, 'definition': definition})
    for revision in range(20):
        changed = deepcopy(definition); changed['presentation']['notes'][0]['text'] = f'人工备注·修订{revision:02d}'
        row = service.save(rig.nid, rig.scope, rig.actor, row['id'], {'expected_version': row['version'], 'definition': changed})
    assert row['version'] == 21
    with pytest.raises(ValueError, match='CREATIVE_GRAPH_HISTORY_CAPACITY'):
        service.save(rig.nid, rig.scope, rig.actor, row['id'], {'expected_version': row['version'], 'definition': definition})
    assert owner(rig).get(rig.nid, rig.scope, rig.actor, row['id']) == row
    stored = rig.raw_store.read(rig.nid, rig.scope)['collections'][service.GRAPHS][row['id']]
    assert len(stored['history']) == 20 and len(canonical(stored).encode()) <= 2_000_000
    assert row['execution_digest'] == digest(execution_definition(definition))


def test_large_notes_keep_exact_utf8_owner_boundary_and_all_original_budgets():
    from app.creative.graph_models import MAX_NODES, MAX_MEDIA_NODES, MAX_EDGES, MAX_DEFINITION_BYTES, MAX_RECORD_BYTES, MAX_SCOPE_BYTES
    assert (MAX_NODES, MAX_MEDIA_NODES, MAX_EDGES, MAX_DEFINITION_BYTES, MAX_RECORD_BYTES, MAX_SCOPE_BYTES) == (16, 24, 40, 96000, 2000000, 8000000)
    definition = parse_graph({'title': '中文🎬"\\\n', 'nodes': [
        {'id': 'first', 'definition_id': 'text_input', 'parameters': {'text': '中文🎬"\\\n'}},
        {'id': 'second', 'definition_id': 'text_input', 'parameters': {'text': ''}}],
        'presentation': {'notes': notes(1000)}}).model_dump()
    remaining = 96_000 - len(canonical(definition).encode())
    first = min(7000, remaining); definition['nodes'][0]['parameters']['text'] += 'a' * first
    definition['nodes'][1]['parameters']['text'] = 'a' * (remaining - first)
    assert len(canonical(definition).encode()) == 96_000
    assert parse_graph(definition).model_dump() == definition
    definition['nodes'][1]['parameters']['text'] += 'a'
    with pytest.raises(ValidationError, match='CREATIVE_GRAPH_DEFINITION_CAPACITY'):
        parse_graph(definition)


def test_original_python_canonical_matches_node_wire_number_fixtures():
    rows = json.loads((Path(__file__).parent / 'fixtures/v2_graph_note_numbers.json').read_text())
    for row in rows:
        actual = canonical(parse_graph(json.loads(row['input_json'])).model_dump())
        assert actual == row['canonical_json'] and len(actual.encode()) == row['canonical_bytes']
