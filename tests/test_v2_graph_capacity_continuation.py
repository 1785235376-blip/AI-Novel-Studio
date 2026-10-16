"""Ordinary original-owner capacity receipts and explicit independent graph copies."""
from copy import deepcopy
from uuid import uuid4
import pytest
from app.creative.graph import CreativeGraphService
from app.creative.graph_models import parse_graph
from app.creative.service import document_digest
from app.experimental.store import canonical
from app.experimental.common import StaleSourceError
from test_v2_independent_workspace import rig, reopened


def owner(rig):
    workspace = reopened(rig)
    return CreativeGraphService(workspace.store, workspace)


@pytest.mark.parametrize('schema,limit', [(1, 20), (3, 80)])
def test_capacity_is_exact_original_stored_record_metadata(rig, schema, limit):
    service = owner(rig)
    row = service.create(rig.nid, rig.scope, rig.actor, {'request_id': 'receipt-' + uuid4().hex,
        'definition': {'schema_version': schema, 'title': 'Capacity receipt'}})
    stored = rig.raw_store.read(rig.nid, rig.scope)['collections'][service.GRAPHS][row['id']]
    assert row['capacity'] == {'history_used': 0, 'history_limit': limit,
        'record_bytes': len(canonical(stored).encode()), 'record_limit_bytes': 2_000_000}
    assert 'capacity' not in stored
    changed = deepcopy(row['definition']); changed['title'] = 'Changed once'
    updated = service.save(rig.nid, rig.scope, rig.actor, row['id'], {'expected_version': 1, 'definition': changed})
    stored = rig.raw_store.read(rig.nid, rig.scope)['collections'][service.GRAPHS][row['id']]
    assert updated['capacity']['history_used'] == 1
    assert updated['capacity']['record_bytes'] == len(canonical(stored).encode())
    assert owner(rig).get(rig.nid, rig.scope, rig.actor, row['id']) == updated


def test_explicit_full_draft_create_keeps_original_history_and_exact_pins_after_restart(rig):
    creative = rig.service.creative
    source = creative.create(rig.nid, rig.scope, rig.actor, {'mode': 'DIRECTOR', 'title': 'Original director', 'source_independent': True})
    pin = {'id': source['id'], 'version': source['version'], 'digest': document_digest(source)}
    definition = parse_graph({'schema_version': 4, 'title': 'Full original author graph',
        'nodes': [{'id': 'director', 'definition_id': 'director_plan', 'parameters': {'document_snapshot': pin}}],
        'presentation': {'comment': 'Original annotation', 'groups': [{'id': 'scene', 'name': 'Scene', 'node_ids': ['director']}],
          'view': {'show_grid': False, 'snap': True, 'grid_step': 32, 'show_minimap': False},
          'notes': [{'id': f'n{i}', 'text': f'雨夜·镜头{i:04d}', 'position': {'x': (i % 40) * 320, 'y': (i // 40) * 220}} for i in range(1000)]},
        'viewport': {'x': -250, 'y': 500, 'zoom': 0.75}}).model_dump()
    service = owner(rig)
    original = service.create(rig.nid, rig.scope, rig.actor, {'request_id': 'original-' + uuid4().hex, 'definition': definition})
    stored_before = deepcopy(rig.raw_store.read(rig.nid, rig.scope)['collections'][service.GRAPHS][original['id']])
    draft = deepcopy(definition); draft['presentation']['notes'][-1]['text'] = '人工尚未保存修改'
    request = {'request_id': 'independent-' + uuid4().hex, 'expected_version': 0, 'definition': draft}
    independent = service.create(rig.nid, rig.scope, rig.actor, request)
    assert independent['id'] != original['id'] and independent['version'] == 1
    assert independent['definition'] == draft and independent['capacity']['history_used'] == 0
    assert service.create(rig.nid, rig.scope, rig.actor, request) == independent
    restored = owner(rig)
    assert restored.get(rig.nid, rig.scope, rig.actor, independent['id']) == independent
    assert restored.get(rig.nid, rig.scope, rig.actor, original['id']) == original
    state = rig.raw_store.read(rig.nid, rig.scope)['collections']
    assert state[service.GRAPHS][original['id']] == stored_before
    assert service.RUNS not in state
    assert independent['definition']['nodes'][0]['parameters']['document_snapshot'] == pin
    # Source mutation remains the original owner's reason to refuse a new copy.
    from app.creative.models import CreativeProductionDocumentIn
    changed = {key: deepcopy(source[key]) for key in CreativeProductionDocumentIn.model_fields if key in source}
    changed['title'] = 'Changed original director'
    creative.update(rig.nid, rig.scope, rig.actor, source['id'], source['version'], changed)
    with pytest.raises(StaleSourceError, match='CREATIVE_GRAPH_EXTERNAL_REFERENCE_CHANGED'):
        restored.create(rig.nid, rig.scope, rig.actor, {**request, 'request_id': 'stale-' + uuid4().hex})
    assert len(restored.list(rig.nid, rig.scope, rig.actor)['items']) == 2
    assert restored.get(rig.nid, rig.scope, rig.actor, original['id'])['reference_states'][0]['state'] == 'STALE'


def test_history_capacity_declines_atomically_then_independent_full_draft_reopens(rig):
    service = owner(rig)
    definition = parse_graph({'title': 'Full history board', 'presentation': {'comment': 'Original comment',
        'notes': [{'id': f'n{i}', 'text': f'雨夜·镜头{i:04d}', 'position': {'x': i % 40, 'y': i // 40}} for i in range(1000)]},
        'viewport': {'x': -100, 'y': 50, 'zoom': 0.75}}).model_dump()
    original = service.create(rig.nid, rig.scope, rig.actor, {'request_id': 'full-' + uuid4().hex, 'definition': definition})
    for revision in range(20):
        draft = deepcopy(definition); draft['presentation']['notes'][0]['text'] = f'人工修订{revision}'
        original = service.save(rig.nid, rig.scope, rig.actor, original['id'], {'expected_version': original['version'], 'definition': draft})
    assert original['version'] == 21 and original['capacity']['history_used'] == original['capacity']['history_limit'] == 20
    before = deepcopy(rig.raw_store.read(rig.nid, rig.scope)['collections'][service.GRAPHS][original['id']])
    unsaved = deepcopy(draft); unsaved['presentation']['notes'][-1]['text'] = '配额后仍保留的人工输入'
    with pytest.raises(ValueError, match='CREATIVE_GRAPH_HISTORY_CAPACITY'):
        service.save(rig.nid, rig.scope, rig.actor, original['id'], {'expected_version': 21, 'definition': unsaved})
    assert rig.raw_store.read(rig.nid, rig.scope)['collections'][service.GRAPHS][original['id']] == before
    independent = service.create(rig.nid, rig.scope, rig.actor, {'request_id': 'after-quota-' + uuid4().hex, 'expected_version': 0, 'definition': unsaved})
    restored = owner(rig)
    assert restored.get(rig.nid, rig.scope, rig.actor, original['id']) == original
    assert restored.get(rig.nid, rig.scope, rig.actor, independent['id'])['definition'] == unsaved
    assert independent['id'] != original['id'] and independent['version'] == 1 and independent['capacity']['history_used'] == 0
    assert rig.raw_store.read(rig.nid, rig.scope)['collections'][service.GRAPHS][original['id']] == before
