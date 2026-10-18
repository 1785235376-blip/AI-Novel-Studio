"""Display hierarchy uses the same view record, unchanged Asset and Graph owners."""
from copy import deepcopy
import pytest
from app.creative.canvas_view_models import CanvasViewDefinition, CANVAS_VIEWS
from test_v2_independent_workspace import rig, import_asset
from test_creative_canvas_views_additive import owner, definition, create


def grouped(assets):
    value = definition(assets, 3)
    value['groups'] = [
        {'id': 'Root', 'name': 'Film', 'card_ids': ['card-0']},
        {'id': 'Scene', 'name': 'Scene', 'card_ids': ['card-1'], 'parent_id': 'Root'},
        {'id': 'Shot', 'name': 'Shot', 'card_ids': ['card-2'], 'parent_id': 'Scene', 'collapsed': True},
    ]
    return value


def test_nested_display_groups_persist_reopen_without_changing_legacy_digest(rig):
    e = rig; graph = owner(e); asset = import_asset(e)
    old = create(e, graph, definition([asset]), 'old-layout')
    assert 'groups' not in old['definition']
    raw = deepcopy(e.raw_store.read(e.nid, e.scope)['collections'][CANVAS_VIEWS][old['id']])
    assert create(e, owner(e), definition([asset]), 'old-layout') == old
    assert e.raw_store.read(e.nid, e.scope)['collections'][CANVAS_VIEWS][old['id']] == raw
    row = create(e, graph, grouped([asset]), 'nested-layout')
    assert owner(e).canvas_views.get(e.nid, e.scope, e.actor, row['id']) == row
    assert len(row['definition']['groups']) == 3 and row['definition']['groups'][2]['collapsed'] is True
    changed = deepcopy(row['definition']); changed['groups'][2]['collapsed'] = False
    saved = graph.canvas_views.save(e.nid, e.scope, e.actor, row['id'], {'expected_version': 1, 'definition': changed})
    assert saved['version'] == 2 and owner(e).canvas_views.get(e.nid, e.scope, e.actor, row['id']) == saved
    assert e.raw_store.read(e.nid, e.scope)['collections'][CANVAS_VIEWS][row['id']]['history'][0]['definition'] == row['definition']
    assert not e.raw_store.read(e.nid, e.scope)['collections'].get(graph.GRAPHS)
    assert not e.raw_store.read(e.nid, e.scope)['collections'].get(graph.RUNS)


@pytest.mark.parametrize('kind', ['cycle', 'orphan', 'duplicate-group', 'duplicate-member', 'unknown-card', 'depth', 'null', 'empty'])
def test_invalid_group_replacement_cannot_write(rig, kind):
    e = rig; graph = owner(e); asset = import_asset(e); row = create(e, graph, grouped([asset]))
    value = deepcopy(row['definition'])
    if kind == 'cycle': value['groups'][0]['parent_id'] = 'Shot'
    if kind == 'orphan': value['groups'][1]['parent_id'] = 'Missing'
    if kind == 'duplicate-group': value['groups'].append(deepcopy(value['groups'][0]))
    if kind == 'duplicate-member': value['groups'][1]['card_ids'] = ['card-0']
    if kind == 'unknown-card': value['groups'][1]['card_ids'] = ['missing']
    if kind == 'depth': value['groups'] = [{'id': f'G{i}', 'name': 'Group', 'card_ids': [], **({'parent_id': f'G{i-1}'} if i else {})} for i in range(9)]
    if kind == 'null': value['groups'] = None
    if kind == 'empty': value['groups'] = []
    before = deepcopy(e.raw_store.read(e.nid, e.scope))
    with pytest.raises(ValueError): graph.canvas_views.save(e.nid, e.scope, e.actor, row['id'], {'expected_version': 1, 'definition': value})
    assert e.raw_store.read(e.nid, e.scope) == before


def test_maximum_display_group_depth_is_eight_and_explicit_removal_preserves_cards():
    value = {'title': 'Nested', 'cards': [], 'groups': [{'id': f'G{i}', 'name': 'Group', 'card_ids': [], **({'parent_id': f'G{i-1}'} if i else {})} for i in range(8)]}
    assert len(CanvasViewDefinition.model_validate(value).model_dump()['groups']) == 8
    value.pop('groups'); assert 'groups' not in CanvasViewDefinition.model_validate(value).model_dump()
