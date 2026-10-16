import pytest
from dataclasses import replace
from fastapi.testclient import TestClient
from app.main import app
from app import api as api_module
from app import main as main_module
from app.config import settings
from app.actor_context import SessionContext
from app.trusted_sessions import TrustedSessionResolver


@pytest.fixture
def local_client(monkeypatch):
    local_settings = replace(settings, enable_collaboration_runtime=False, enable_packaged_runtime=False)
    monkeypatch.setattr(api_module, 'settings', local_settings)
    monkeypatch.setattr(main_module, 'settings', local_settings)
    sessions = TrustedSessionResolver()
    sessions.register('synthetic-local-host', SessionContext('s', 'host', 'verified-author', 'w'))
    monkeypatch.setattr(api_module, 'trusted_session_resolver', sessions)
    return TestClient(app)


@pytest.mark.parametrize('path', ['/api/local-session', '/api/v1/local-session'])
def test_explicit_local_host_validation_uses_existing_actor_registry_without_echoing_credentials(local_client, path):
    response = local_client.get(path, headers={'X-Session-Token': 'synthetic-local-host', 'Origin': settings.frontend_origin})
    assert response.status_code == 200
    assert response.json() == {'session_mode': 'LOCAL_HOST', 'actor_id': 'verified-author'}
    assert response.headers['Cache-Control'] == 'no-store'
    assert response.headers['Referrer-Policy'] == 'no-referrer'
    assert 'synthetic-local-host' not in response.text
    # The binding endpoint does not mint sessions or grant anonymous job access.
    assert local_client.get('/api/agent-jobs').status_code == 401


@pytest.mark.parametrize('token', ['', 'invalid-opaque-credential'])
def test_local_host_binding_rejects_absent_or_unregistered_tokens(local_client, token):
    headers = {'X-Session-Token': token} if token else {}
    response = local_client.get('/api/local-session', headers=headers)
    assert response.status_code == 401
    assert response.json()['code'] == ('INVALID_SESSION' if token else 'SESSION_REQUIRED')
    assert token not in response.text if token else True


def test_local_host_binding_rejects_wrong_origin(local_client):
    response = local_client.get('/api/local-session', headers={'X-Session-Token': 'synthetic-local-host', 'Origin': 'https://untrusted.example'})
    assert response.status_code == 403
    assert response.json()['code'] == 'LOCAL_HOST_ORIGIN_DENIED'


def test_local_host_binding_keeps_remote_development_requests_denied(local_client):
    remote = TestClient(app, client=('203.0.113.2', 41000))
    response = remote.get('/api/local-session', headers={'X-Session-Token': 'synthetic-local-host'})
    assert response.status_code == 403


@pytest.mark.parametrize('mode', ['enable_collaboration_runtime', 'enable_packaged_runtime'])
def test_local_host_endpoint_never_falls_back_across_collaboration_or_packaged_boundaries(local_client, monkeypatch, mode):
    restricted_settings = replace(api_module.settings, **{mode: True})
    monkeypatch.setattr(api_module, 'settings', restricted_settings)
    monkeypatch.setattr(main_module, 'settings', restricted_settings)
    response = local_client.get('/api/local-session', headers={'X-Session-Token': 'synthetic-local-host'})
    assert response.status_code == 501
    assert response.json().get('session_mode') != 'LOCAL_HOST'


def test_revoked_local_token_is_rejected_by_existing_resolver(local_client):
    api_module.trusted_session_resolver.revoke('synthetic-local-host')
    assert local_client.get('/api/local-session', headers={'X-Session-Token': 'synthetic-local-host'}).status_code == 401
