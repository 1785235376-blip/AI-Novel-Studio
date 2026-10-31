import hashlib

import pytest

from test_studio_asset_query import rig, shared_scope
from test_studio_workspace_identity_history_contract import audio_history
from test_audio_history_status_readonly import snapshot
from studio_asset_usage_meter import ReadMeter

pytestmark = pytest.mark.file_backend_only


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
@pytest.mark.parametrize('missing', [None, 'asset_lock', 'marker'])
def test_original_storage_owner_is_observational(audio_history, monkeypatch, prefix, missing):
    e = audio_history
    if missing == 'asset_lock':
        target = e.rig.assets.root / '.workspace-mutation-locks' / (hashlib.sha256(b'asset-library').hexdigest() + '.lock')
        target.unlink()
    elif missing == 'marker':
        target = e.rig.root / 'novels' / e.rig.nid / 'creative_project_v2.json'
        target.unlink()
    before = snapshot(e.rig.root)
    meter = ReadMeter(e.rig.root)
    with monkeypatch.context() as patch:
        meter.install(patch)
        response = e.client.get(f'{prefix}/projects/{e.rig.nid}/studio/storage', headers=e.headers)
    assert response.status_code == (200 if missing is None else 409), response.text
    if missing is None:
        assert response.json()['assets']['bytes'] == len(e.content)
    else:
        assert response.json()['detail']['code'] == 'STUDIO_STORAGE_READ_ONLY_UNAVAILABLE'
        assert not target.exists()
    assert meter.write_calls == 0
    assert snapshot(e.rig.root) == before


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_revoked_collaborative_read_returns_no_counts(rig, monkeypatch, prefix):
    scope, headers = shared_scope(rig)
    rig.seed('synthetic.wav', 'audio', scope_value=scope)
    original_list = rig.assets.list
    def revoke_during_read(*args, **kwargs):
        result = original_list(*args, **kwargs)
        rig.sessions.revoke(headers['X-Session-Token'])
        return result
    monkeypatch.setattr(rig.assets, 'list', revoke_during_read)
    before = snapshot(rig.root)
    response = rig.client.get(f'{prefix}/projects/{rig.nid}/studio/storage', headers=headers)
    assert response.status_code in (401, 403), response.text
    assert 'assets' not in response.json()
    assert snapshot(rig.root) == before
