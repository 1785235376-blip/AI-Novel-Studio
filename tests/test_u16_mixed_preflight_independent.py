"""Actual mounted route evidence with synthetic batch inputs; no model calls."""
import pytest

from app.actor_context import SessionContext
from test_studio_asset_query import rig
from test_audio_history_status_readonly import snapshot


@pytest.mark.parametrize('alias', ['', '/v1'])
def test_mixed_preflight_must_not_initialize_project_before_voice_gate(rig, monkeypatch, alias):
    from app.experimental import api as experimental_api
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,reader_preflight_v2,safe_batches_v2,audiobook_v2,voice_direction_v2')
    rig.sessions.register('synthetic-host', SessionContext('synthetic-session', 'client', 'local-author', 'synthetic'))
    monkeypatch.setattr(experimental_api.safe_batches_service, 'store', rig.workspace.store.store)
    body = {'items': [
        {'kind': 'VOICE_REDO', 'voice_job_id': 'synthetic-job', 'expected_voice_digest': 'a' * 64,
         'broker_preview_id': 'synthetic-preview', 'expected_broker_version': 1},
        {'kind': 'STUDIO_IMAGE', 'studio_image': {
            'request_id': 'synthetic',
            'image': {'id': 'synthetic-a', 'kind': 'ASSET', 'asset_kind': 'image', 'version': 1, 'digest': 'a' * 64},
            'mask': {'id': 'synthetic-b', 'kind': 'ASSET', 'asset_kind': 'image', 'version': 1, 'digest': 'b' * 64}}},
    ]}
    marker = rig.root / 'novels' / rig.nid / 'creative_project_v2.json'
    assert not marker.exists()
    before = snapshot(rig.root)
    response = rig.client.post(f'/api{alias}/novels/{rig.nid}/experimental/safe-batches/preflight',
                               headers={'X-Session-Token': 'synthetic-host'}, json=body)
    print('observed', alias, response.status_code, response.json())
    assert response.status_code in {403, 422}, response.text
    assert not marker.exists()
    assert snapshot(rig.root) == before


def mixed_body():
    return {'items': [
        {'kind': 'VOICE_REDO', 'voice_job_id': 'synthetic-job', 'expected_voice_digest': 'a' * 64,
         'broker_preview_id': 'synthetic-preview', 'expected_broker_version': 1},
        {'kind': 'STUDIO_IMAGE', 'studio_image': {'request_id': 'synthetic',
         'image': {'id': 'synthetic-a', 'kind': 'ASSET', 'asset_kind': 'image', 'version': 1, 'digest': 'a' * 64},
         'mask': {'id': 'synthetic-b', 'kind': 'ASSET', 'asset_kind': 'image', 'version': 1, 'digest': 'b' * 64}}}]}


@pytest.mark.parametrize('alias', ['', '/v1'])
def test_mixed_preflight_preserves_host_checks_and_no_file_writes(rig, monkeypatch, alias):
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,reader_preflight_v2,safe_batches_v2,audiobook_v2,voice_direction_v2')
    rig.sessions.register('synthetic-host', SessionContext('synthetic-session', 'client', 'local-author', 'synthetic'))
    url = f'/api{alias}/novels/{rig.nid}/experimental/safe-batches/preflight'
    before = snapshot(rig.root)
    assert rig.client.post(url, json=mixed_body()).status_code == 401
    forwarded = rig.client.post(url, json=mixed_body(), headers={'X-Session-Token': 'synthetic-host', 'X-Forwarded-For': '127.0.0.1'})
    assert forwarded.status_code == 403 and 'AUDIO_CAPACITY_WRITE_UNAVAILABLE' not in forwarded.text
    invalid_origin = rig.client.post(url, json=mixed_body(), headers={'X-Session-Token': 'synthetic-host', 'Origin': 'https://invalid.example'})
    assert invalid_origin.status_code == 403 and 'AUDIO_CAPACITY_WRITE_UNAVAILABLE' not in invalid_origin.text
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,reader_preflight_v2,safe_batches_v2')
    disabled = rig.client.post(url, json=mixed_body(), headers={'X-Session-Token': 'synthetic-host'})
    assert disabled.status_code == 404 and 'AUDIO_CAPACITY_WRITE_UNAVAILABLE' not in disabled.text
    assert snapshot(rig.root) == before


@pytest.mark.parametrize('alias', ['', '/v1'])
def test_mixed_preflight_rechecks_original_host_revocation(rig, monkeypatch, alias):
    from app import main
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,reader_preflight_v2,safe_batches_v2,audiobook_v2,voice_direction_v2')
    rig.sessions.register('synthetic-host', SessionContext('synthetic-session', 'client', 'local-author', 'synthetic'))
    original = main._local_discovery_host_authority
    def revoke_after_resolve(request, token):
        authority = original(request, token)
        rig.sessions.revoke(token)
        return authority
    monkeypatch.setattr(main, '_local_discovery_host_authority', revoke_after_resolve)
    before = snapshot(rig.root)
    url = f'/api{alias}/novels/{rig.nid}/experimental/safe-batches/preflight'
    response = rig.client.post(url, json=mixed_body(), headers={'X-Session-Token': 'synthetic-host'})
    assert response.status_code in (401, 403), response.text
    assert 'AUDIO_CAPACITY_WRITE_UNAVAILABLE' not in response.text
    assert snapshot(rig.root) == before
