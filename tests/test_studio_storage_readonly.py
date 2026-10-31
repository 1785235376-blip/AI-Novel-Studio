"""Mounted File storage observations must not initialize any on-disk owner."""
import hashlib

import pytest

from test_studio_asset_query import rig, shared_scope
from test_studio_workspace_identity_history_contract import audio_history
from test_audio_history_status_readonly import snapshot

pytestmark = pytest.mark.file_backend_only


def url(e, alias):
    return f"/api{'/v1' if alias else ''}/projects/{e.rig.nid}/studio/storage"


@pytest.mark.parametrize('alias', [False, True])
def test_initialized_storage_keeps_existing_shape_without_writes(audio_history, alias):
    e = audio_history
    before = snapshot(e.rig.root)
    response = e.client.get(url(e, alias), headers=e.headers)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['assets']['count'] == 1
    assert result['assets']['bytes'] == len(e.content)
    assert {'assets', 'trash', 'limits', 'admission'} <= set(result)
    assert snapshot(e.rig.root) == before


@pytest.mark.parametrize('alias', [False, True])
def test_missing_asset_lock_fails_closed_without_initializing(audio_history, alias):
    e = audio_history
    lock = e.rig.assets.root / '.workspace-mutation-locks' / (hashlib.sha256(b'asset-library').hexdigest() + '.lock')
    assert lock.is_file()
    lock.unlink()
    before = snapshot(e.rig.root)
    response = e.client.get(url(e, alias), headers=e.headers)
    assert response.status_code == 409, response.text
    assert response.json()['detail']['code'] == 'STUDIO_STORAGE_READ_ONLY_UNAVAILABLE'
    assert snapshot(e.rig.root) == before
    assert not lock.exists()


@pytest.mark.parametrize('alias', [False, True])
def test_missing_marker_fails_closed_without_initializing(audio_history, alias):
    e = audio_history
    marker = e.rig.root / 'novels' / e.rig.nid / 'creative_project_v2.json'
    assert marker.is_file()
    marker.unlink()
    before = snapshot(e.rig.root)
    response = e.client.get(url(e, alias), headers=e.headers)
    assert response.status_code == 409, response.text
    assert response.json()['detail']['code'] == 'STUDIO_STORAGE_READ_ONLY_UNAVAILABLE'
    assert snapshot(e.rig.root) == before
    assert not marker.exists()


@pytest.mark.parametrize('alias', [False, True])
def test_collaboration_original_permissions_and_revocation(rig, alias):
    scope, headers = shared_scope(rig)
    rig.seed('collaborative.wav', 'audio', scope_value=scope)
    path = f"/api{'/v1' if alias else ''}/projects/{rig.nid}/studio/storage"
    before = snapshot(rig.root)
    allowed = rig.client.get(path, headers=headers)
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()['assets']['count'] == 1
    denied = rig.client.get(path, headers={**headers, 'X-Session-Token': 'token-no-grants'})
    assert denied.status_code == 403, denied.text
    assert snapshot(rig.root) == before
    rig.sessions.revoke(headers['X-Session-Token'])
    revoked = rig.client.get(path, headers=headers)
    assert revoked.status_code in (401, 403), revoked.text
    assert snapshot(rig.root) == before


def test_collaboration_revocation_during_read_does_not_return_result(rig, monkeypatch):
    scope, headers = shared_scope(rig)
    rig.seed('collaborative.wav', 'audio', scope_value=scope)
    original_list = rig.assets.list
    def revoke(*args, **kwargs):
        result = original_list(*args, **kwargs)
        rig.sessions.revoke(headers['X-Session-Token'])
        return result
    monkeypatch.setattr(rig.assets, 'list', revoke)
    before = snapshot(rig.root)
    response = rig.client.get(f'/api/projects/{rig.nid}/studio/storage', headers=headers)
    assert response.status_code in (401, 403), response.text
    assert 'assets' not in response.json()
    assert snapshot(rig.root) == before
