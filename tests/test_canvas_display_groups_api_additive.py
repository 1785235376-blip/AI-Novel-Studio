"""Mounted group persistence stays on display schema one, without model authority."""
from copy import deepcopy
from test_canvas_view_api_additive import canvas, graph_client, client, mounted, prefix
from test_v2_independent_workspace_api import upload_body
from test_r3_mounted_contracts import checked


def test_nested_group_api_save_reopen_keeps_display_authority(canvas):
    e = canvas
    asset = checked(e.client.post(e.studio_base + '/assets', json=upload_body()), 201)
    reference = {'asset_id': asset['id'], 'version': asset['version'], 'digest': asset['sha256'], 'kind': asset['kind']}
    value = {'schema_version': 1, 'title': 'Nested display', 'cards': [{'id': 'Card', 'position': {'x': 30, 'y': 40}, 'asset': reference}],
        'groups': [{'id': 'Root', 'name': 'Root', 'card_ids': []}, {'id': 'Child', 'name': 'Child', 'card_ids': ['Card'], 'parent_id': 'Root', 'collapsed': True}]}
    row = checked(e.client.post(e.canvas_base, json={'request_id': 'grouped-create', 'definition': value}), 201)
    assert row['execution_authority'] is False and row['definition']['schema_version'] == 1
    path = e.canvas_base + '/' + row['id']
    assert checked(e.client.get(path)) == row
    changed = deepcopy(row['definition']); changed['groups'][1]['collapsed'] = False
    saved = checked(e.client.put(path, json={'expected_version': 1, 'definition': changed}))
    assert saved['version'] == 2 and checked(e.client.get(path)) == saved
    invalid = deepcopy(changed); invalid['groups'][0]['parent_id'] = 'Child'
    response = e.client.put(path, json={'expected_version': 2, 'definition': invalid})
    assert response.status_code == 422 and 'Nested display' not in response.text
    assert checked(e.client.get(path)) == saved
    assert checked(e.client.get(e.graph_base)) == {'items': []}
