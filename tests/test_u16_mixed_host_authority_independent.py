"""Independent route guards: synthetic requests; no model or provider calls."""
from types import SimpleNamespace
import pytest
from fastapi import HTTPException

from app.actor_context import SessionContext
from app.experimental.audiobook import AudiobookV2Service
from test_audio_history_status_readonly import snapshot
from test_studio_asset_query import rig, shared_scope
from test_u16_mixed_preflight_independent import mixed_body

FLAGS = 'narrative_production_v2,reader_preflight_v2,safe_batches_v2,audiobook_v2,voice_direction_v2'


def local(rig, monkeypatch):
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', FLAGS)
    rig.sessions.register('synthetic-host', SessionContext('synthetic-session', 'client', 'local-author', 'synthetic'))


@pytest.mark.parametrize('alias', ['', '/v1'])
def test_revoke_at_voice_gate_rechecks_host_before_response(rig, monkeypatch, alias):
    local(rig, monkeypatch)
    def revoke_and_reject():
        rig.sessions.revoke('synthetic-host')
        raise ValueError('AUDIO_CAPACITY_WRITE_UNAVAILABLE')
    monkeypatch.setattr(AudiobookV2Service, '_require_candidate_write_capacity', staticmethod(revoke_and_reject))
    before = snapshot(rig.root)
    response = rig.client.post(f'/api{alias}/novels/{rig.nid}/experimental/safe-batches/preflight',
                               headers={'X-Session-Token': 'synthetic-host'}, json=mixed_body())
    assert response.status_code in (401, 403), response.text
    assert 'AUDIO_CAPACITY_WRITE_UNAVAILABLE' not in response.text
    assert snapshot(rig.root) == before


@pytest.mark.parametrize('alias', ['', '/v1'])
def test_future_open_gate_cannot_turn_reject_path_into_authorization(rig, monkeypatch, alias):
    from app.experimental import api as experimental_api
    local(rig, monkeypatch)
    # Fault injection: this only tests the explicit reject fallback, not a
    # claim that the present production gate was ever open.
    monkeypatch.setattr(AudiobookV2Service, '_require_candidate_write_capacity', staticmethod(lambda: None))
    monkeypatch.setattr(experimental_api.safe_batches_service, 'preflight',
                        lambda *args: pytest.fail('write-capable preflight reached'))
    before = snapshot(rig.root)
    response = rig.client.post(f'/api{alias}/novels/{rig.nid}/experimental/safe-batches/preflight',
                               headers={'X-Session-Token': 'synthetic-host'}, json=mixed_body())
    assert response.status_code == 503, response.text
    assert response.json()['detail']['code'] == 'BATCH_STUDIO_HOST_INVOKER_REQUIRED'
    assert snapshot(rig.root) == before


@pytest.mark.parametrize('alias', ['', '/v1'])
def test_project_permission_precedes_any_host_check(rig, monkeypatch, alias):
    from app import main
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', FLAGS)
    scope, headers = shared_scope(rig)
    def forbidden(*args):
        pytest.fail('host checked for actor lacking project write')
    monkeypatch.setattr(main, '_local_discovery_host_authority', forbidden)
    before = snapshot(rig.root)
    response = rig.client.post(f'/api{alias}/novels/{rig.nid}/experimental/safe-batches/preflight',
                               headers=headers, json=mixed_body())
    assert response.status_code == 403, response.text
    assert 'AUDIO_CAPACITY_WRITE_UNAVAILABLE' not in response.text
    assert snapshot(rig.root) == before


@pytest.mark.parametrize('alias', ['', '/v1'])
def test_image_only_preflight_remains_on_original_host_invoker(rig, monkeypatch, alias):
    from app.experimental import api as experimental_api
    local(rig, monkeypatch)
    calls = []
    def image_original(ctx, permission, callback):
        # Routing sentinel only; it does not validate image host authority.
        calls.append((ctx.actor, permission))
        raise HTTPException(409, {'code': 'SYNTHETIC_ORIGINAL_HOST_PATH'})
    monkeypatch.setattr(experimental_api.safe_batches_service.studio_image, 'call', image_original)
    body = {'items': [mixed_body()['items'][1]]}
    before = snapshot(rig.root)
    response = rig.client.post(f'/api{alias}/novels/{rig.nid}/experimental/safe-batches/preflight',
                               headers={'X-Session-Token': 'synthetic-host'}, json=body)
    assert response.status_code == 409, response.text
    assert calls == [('local-author', 'domain.write')]
    assert snapshot(rig.root) == before
