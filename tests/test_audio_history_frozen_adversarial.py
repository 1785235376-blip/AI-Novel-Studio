import os
from pathlib import Path
import pytest
from fastapi import HTTPException
from test_studio_asset_query import rig, shared_scope
from test_studio_workspace_identity_history_contract import audio_history


def test_postgres_collaboration_observation_fails_closed_without_io(rig, monkeypatch):
    from app.creative.audio_history_authority import file_collaboration_observation
    scope, headers = shared_scope(rig)
    # Simulate the backend capability switch only: no PostgreSQL service is used.
    store = rig.workspace.store.store
    monkeypatch.setattr(store, 'backend', 'postgres')
    with pytest.raises(HTTPException) as caught:
        file_collaboration_observation(rig.workspace, rig.nid, scope, 'reader', headers['X-Session-Token'])
    assert caught.value.status_code == 409
    assert caught.value.detail['code'] == 'AUDIO_HISTORY_AUTHORITY_OBSERVATION_UNAVAILABLE'


@pytest.mark.skipif(os.name != 'nt', reason='Windows native path race')
@pytest.mark.parametrize('alias', ['', '/v1'])
def test_path_replaced_between_lstat_and_native_open_rejects(audio_history, monkeypatch, alias):
    from app.services import asset_bounded_file_windows as native
    e = audio_history
    path = e.rig.assets._bin_path(e.asset['id'])
    replacement = path.with_name('synthetic-replacement.tmp')
    replacement.write_bytes(b'X' * len(e.content))
    original = native._Kernel.open
    changed = []
    def replace_before_open(self, candidate, access, guard):
        if Path(candidate) == path and not changed:
            os.replace(replacement, path)
            changed.append(True)
        return original(self, candidate, access, guard)
    monkeypatch.setattr(native._Kernel, 'open', replace_before_open)
    url=f'/api{alias}/projects/{e.rig.nid}/studio/assets/{e.asset["id"]}/history'
    response=e.client.get(url,headers=e.headers)
    assert changed == [True]
    assert response.status_code == 409, response.text
    assert 'UNCAPTURED' not in response.text

@pytest.mark.skipif(os.name != 'nt', reason='Windows native sharing semantics')
def test_windows_native_open_blocks_competing_binary_write(audio_history, monkeypatch):
    from app.services import asset_bounded_file_windows as native
    e=audio_history
    path=e.rig.assets._bin_path(e.asset['id'])
    original=native._Kernel.read
    attempts=[]
    def competing_write(self, handle, count, guard):
        data=original(self, handle, count, guard)
        if not attempts:
            try:
                with path.open('r+b') as stream:
                    stream.write(b'X')
            except PermissionError:
                attempts.append('denied')
            else:
                attempts.append('unexpected-write')
        return data
    monkeypatch.setattr(native._Kernel,'read',competing_write)
    response=e.client.get(e.base + '/assets/' + e.asset['id'] + '/history', headers=e.headers)
    assert attempts == ['denied']
    assert response.status_code == 200, response.text
    assert response.json()['coverage'] == 'UNCAPTURED'
    assert path.read_bytes() == e.content
