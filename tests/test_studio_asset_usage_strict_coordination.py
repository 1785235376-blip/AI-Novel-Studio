"""Strict queries reuse original facilities and original locks, without init."""
from pathlib import Path
import os

import pytest
from studio_asset_usage_fixture import usage_rig, audio_history, rig, graph_create, create_timeline

pytestmark = pytest.mark.file_backend_only


@pytest.mark.parametrize('owner', ['graph', 'timeline', 'asset'])
@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_strict_mode_preserves_original_selected_owner_contract(usage_rig, owner, prefix):
    e = usage_rig
    graph_create(e, 1)
    create_timeline(e)
    url = e.usage_base.replace('/api/', prefix + '/', 1) + '/studio-' + owner + '-usages'
    response = e.client.get(url, headers=e.headers, params={'limit': 100, 'strict_read_only': 'true'})
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body['items']) == (2 if owner == 'asset' else 1)
    assert body['filesystem_mode'] == 'STRICT_EXISTING_COORDINATION'
    assert body['other_dependencies'] == 'UNKNOWN'
    assert body['consistency_limits']['strong_aba'] is False
    assert response.headers['cache-control'] == 'no-store'


def test_original_coordinator_strict_reentrancy_retains_one_original_file_lock(tmp_path, monkeypatch):
    from app.repositories.file import mutation_coordinator as owner
    with owner.workspace_mutation(tmp_path, 'synthetic'):
        pass
    locks = dict(owner._locks)
    original = owner._lock_file
    acquisitions = []
    def acquire(handle, **kwargs):
        acquisitions.append(kwargs)
        return original(handle, **kwargs)
    monkeypatch.setattr(owner, '_lock_file', acquire)
    with owner.existing_coordination_only(), owner.workspace_mutation(tmp_path, 'synthetic'):
        with owner.workspace_mutation(tmp_path, 'synthetic'):
            assert owner.strict_coordination_active()
    assert acquisitions == [{'initialize': False}]
    assert owner._locks == locks
    assert not owner.strict_coordination_active()


@pytest.mark.skipif(os.name != 'nt', reason='Windows original populated byte-range lock requirement')
def test_strict_empty_windows_lock_cannot_initialize_a_byte(tmp_path):
    from app.repositories.file import mutation_coordinator as owner
    with owner.workspace_mutation(tmp_path, 'synthetic'):
        pass
    lock = next((tmp_path / '.workspace-mutation-locks').glob('*.lock'))
    lock.write_bytes(b'')
    with owner.existing_coordination_only():
        with pytest.raises(owner.ReadOnlyCoordinationUnavailable):
            with owner.workspace_mutation(tmp_path, 'synthetic'):
                pytest.fail('empty Windows lock admitted')
    assert lock.read_bytes() == b''


def test_cursor_modes_cannot_borrow_each_others_observations(usage_rig):
    e = usage_rig
    graph_create(e, 3)
    url = e.usage_base + '/studio-asset-usages'
    plain = e.client.get(url, headers=e.headers, params={'limit': 1}).json()
    response = e.client.get(url, headers=e.headers, params={
        'limit': 1, 'cursor': plain['next_cursor'], 'strict_read_only': 'true'})
    assert response.status_code == 409
    strict = e.client.get(url, headers=e.headers, params={'limit': 1, 'strict_read_only': 'true'}).json()
    response = e.client.get(url, headers=e.headers, params={'limit': 1, 'cursor': strict['next_cursor']})
    assert response.status_code == 409


def test_strict_option_values_are_closed_after_original_authority(usage_rig):
    e = usage_rig
    graph_create(e)
    for value in ('false', '1', ''):
        response = e.client.get(e.usage_base + '/studio-asset-usages', headers=e.headers,
                                params={'limit': 1, 'strict_read_only': value})
        assert response.status_code == 409
        assert response.headers['cache-control'] == 'no-store'
        assert 'items' not in response.json()


@pytest.mark.parametrize('stage', ['lock', 'unlock'])
def test_strict_native_coordination_failure_is_private_and_releases_handle(usage_rig, monkeypatch, stage):
    from app.repositories.file import mutation_coordinator as owner
    e = usage_rig
    graph_create(e)
    original = owner._lock_file if stage == 'lock' else owner._unlock_file
    fired = []
    def fail(handle, **kwargs):
        if not fired:
            fired.append(True)
            if stage == 'unlock':
                original(handle, **kwargs)
            raise OSError('PRIVATE_SYNTHETIC_LOCK_PATH')
        return original(handle, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(owner, '_lock_file' if stage == 'lock' else '_unlock_file', fail)
        response = e.client.get(e.usage_base + '/studio-asset-usages', headers=e.headers,
                                params={'limit': 1, 'strict_read_only': 'true'})
    assert fired and response.status_code == 409, response.text
    assert response.json()['code'] == 'STUDIO_USAGE_STRICT_READ_ONLY_UNAVAILABLE'
    assert 'PRIVATE_SYNTHETIC' not in response.text
    assert response.headers['cache-control'] == 'no-store'
    response = e.client.get(e.usage_base + '/studio-asset-usages', headers=e.headers,
                            params={'limit': 1, 'strict_read_only': 'true'})
    assert response.status_code == 200, response.text
