"""Export one synthetic mounted response for original frontend decoders."""
import json
import os
from pathlib import Path
import hashlib
import pytest

from test_studio_asset_query import rig, shared_scope
from test_studio_workspace_identity_history_contract import audio_history
from test_audio_history_status_readonly import snapshot


def test_export_synthetic_storage_response(audio_history):
    e = audio_history
    response = e.client.get(f'/api/projects/{e.rig.nid}/studio/storage', headers=e.headers)
    assert response.status_code == 200
    output = os.environ.get('CAPACITY_PROJECTION_OUTPUT')
    if output:
        Path(output).write_text(json.dumps(response.json(), ensure_ascii=False), encoding='utf-8')


@pytest.mark.parametrize('alias', ['', '/v1'])
def test_unavailable_shape_and_existing_bytes_never_probe_disk(audio_history, alias, monkeypatch):
    e = audio_history
    def forbidden():
        raise AssertionError('disk free bytes cannot establish project quota')
    monkeypatch.setattr(e.rig.workspace.storage_admission, 'available', forbidden)
    before = snapshot(e.rig.root)
    response = e.client.get(f'/api{alias}/projects/{e.rig.nid}/studio/storage', headers=e.headers)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['assets'] == {'count': 1, 'bytes': len(e.content)}
    admission = result['admission']
    assert set(admission) == {'state', 'available_import_bytes', 'reserve_bytes', 'measurement', 'paths',
        'external_model_scan', 'automatic_cleanup', 'automatic_migration'}
    assert admission['state'] == 'UNAVAILABLE' and admission['available_import_bytes'] is None
    assert snapshot(e.rig.root) == before


@pytest.mark.parametrize('alias', ['', '/v1'])
def test_missing_lock_denies_without_recreating_it(audio_history, alias):
    e = audio_history
    lock = e.rig.assets.root / '.workspace-mutation-locks' / (hashlib.sha256(b'asset-library').hexdigest() + '.lock')
    assert lock.is_file()
    lock.unlink()
    before = snapshot(e.rig.root)
    response = e.client.get(f'/api{alias}/projects/{e.rig.nid}/studio/storage', headers=e.headers)
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'STUDIO_STORAGE_READ_ONLY_UNAVAILABLE'
    assert snapshot(e.rig.root) == before and not lock.exists()


@pytest.mark.parametrize('alias', ['', '/v1'])
def test_denied_scope_does_not_leak_status(rig, alias):
    scope, headers = shared_scope(rig)
    rig.seed('fixture.wav', 'audio', scope_value=scope)
    before = snapshot(rig.root)
    response = rig.client.get(f'/api{alias}/projects/{rig.nid}/studio/storage',
                              headers={**headers, 'X-Session-Token': 'token-no-grants'})
    assert response.status_code == 403
    assert 'admission' not in response.text
    assert snapshot(rig.root) == before
