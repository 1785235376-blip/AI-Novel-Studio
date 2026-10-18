"""Optional presentation settings persist under the original canvas owner."""
from copy import deepcopy
import pytest
from app.creative.canvas_view_models import CanvasViewDefinition, CANVAS_VIEWS
from test_v2_independent_workspace import rig, import_asset
from test_creative_canvas_views_additive import owner, definition, create


def test_grid_save_reopen_keeps_asset_pins_and_legacy_records(rig):
    e = rig; graph = owner(e); asset = import_asset(e)
    legacy = create(e, graph, definition([asset]), 'legacy-grid')
    assert 'view_options' not in legacy['definition']
    before = deepcopy(e.raw_store.read(e.nid, e.scope)['collections'][CANVAS_VIEWS][legacy['id']])
    assert create(e, owner(e), definition([asset]), 'legacy-grid') == legacy
    assert e.raw_store.read(e.nid, e.scope)['collections'][CANVAS_VIEWS][legacy['id']] == before
    value = deepcopy(legacy['definition']); value['view_options'] = {'grid': True, 'snap_step': 24}
    saved = graph.canvas_views.save(e.nid, e.scope, e.actor, legacy['id'], {'expected_version': 1, 'definition': value})
    assert owner(e).canvas_views.get(e.nid, e.scope, e.actor, saved['id']) == saved
    assert saved['definition']['cards'] == legacy['definition']['cards']
    assert saved['definition']['view_options'] == value['view_options']
    raw = e.raw_store.read(e.nid, e.scope)['collections'][CANVAS_VIEWS][saved['id']]
    assert raw['history'][0]['definition'] == legacy['definition']
    value['view_options'] = {'grid': False, 'snap_step': None}
    disabled = graph.canvas_views.save(e.nid, e.scope, e.actor, saved['id'], {'expected_version': 2, 'definition': value})
    assert owner(e).canvas_views.get(e.nid, e.scope, e.actor, saved['id']) == disabled
    assert not e.raw_store.read(e.nid, e.scope)['collections'].get(graph.RUNS)


@pytest.mark.parametrize('options', [None, {}, {'grid': 1, 'snap_step': 16}, {'grid': True, 'snap_step': True}, {'grid': True, 'snap_step': 16.0}, {'grid': True, 'snap_step': '16'}, {'grid': True, 'snap_step': 17}, {'grid': True, 'snap_step': None, 'execute': True}])
def test_grid_options_are_strict(options):
    with pytest.raises(ValueError): CanvasViewDefinition.model_validate({'title': 'Grid', 'view_options': options})


@pytest.mark.parametrize('step', [8, 16, 24, 32, None])
def test_grid_step_contract(step):
    assert CanvasViewDefinition.model_validate({'title': 'Grid', 'view_options': {'grid': False, 'snap_step': step}}).model_dump()['view_options'] == {'grid': False, 'snap_step': step}
