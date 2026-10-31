"""Independent original-owner commit-window regression, preserved from M6 red case."""
from copy import deepcopy

from hashlib import sha256

import json

import pytest

from conftest import restore_global_settings

from test_studio_asset_query import rig

from test_unified_canvas_image_result import shared_approved_node, shared_owner_bytes

pytestmark = pytest.mark.file_backend_only

def test_original_asset_metadata_change_in_commit_window_is_not_adopted(
    shared_approved_node, monkeypatch
):
    from app.creative import canvas_views

    e = shared_approved_node
    before = shared_owner_bytes(e)
    request_body = deepcopy(e.body)
    original_change = canvas_views.change_row
    changed = []

    def change_asset_after_original_canvas_change(row, *args, **kwargs):
        result = original_change(row, *args, **kwargs)
        assert row['id'] == e.target['id']
        assert row['definition']['image_node_origin']['asset'] == e.pin
        assert not changed
        metadata = e.rig.assets.get(e.pin['asset_id'], branch_id=e.scope['branch_id'], actor_id='reader')
        assert metadata['version'] == e.pin['version']
        parameters = deepcopy(metadata.get('parameters', {}))
        parameters['independent_commit_window_note'] = 'original-owner-reentrant-write'
        updated = e.rig.assets.update_metadata(
            e.pin['asset_id'], {'parameters': parameters},
            branch_id=e.scope['branch_id'], actor_id='reader',
            expected_version=e.pin['version'],
        )
        assert updated['version'] == e.pin['version'] + 1
        changed.append(deepcopy(updated))
        return result

    monkeypatch.setattr(canvas_views, 'change_row', change_asset_after_original_canvas_change)
    response = e.client.post(e.canvas_url + '/image-node-result', json=request_body)
    after = shared_owner_bytes(e)
    evidence = {
        'case': 'original-asset-owner-reentrant-commit-window',
        'boundary': 'same-thread original owner API; no external-thread lease bypass claim',
        'http_status': response.status_code,
        'response': response.json(),
        'request': request_body,
        'original_asset_version': e.pin['version'],
        'updated_asset_version': changed[0]['version'] if changed else None,
        'canvas_before': json.loads(before[0]),
        'canvas_after': json.loads(after[0]),
        'owner_sha256_before': [sha256(x.encode() if isinstance(x, str) else x).hexdigest() for x in before],
        'owner_sha256_after': [sha256(x.encode() if isinstance(x, str) else x).hexdigest() for x in after],
    }
    (e.run / 'independent-asset-commit-window.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    assert len(changed) == 1, 'original metadata writer did not reach its CAS'
    assert e.body == request_body, 'test must not mutate request pins'
    assert after[1] == before[1] and after[3] == before[3], 'Job or asset binary changed'
    assert json.loads(after[2])['version'] == e.pin['version'] + 1
    assert json.loads(after[2])['parameters']['independent_commit_window_note'] == 'original-owner-reentrant-write'
    assert len(e.calls) == 1
    assert after[0] == before[0], f'Canvas committed despite changed asset; HTTP {response.status_code}'
    assert response.status_code in {404, 409}, response.text
