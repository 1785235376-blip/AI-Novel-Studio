"""Both original mounts, current Host authority and offline transfer fixtures."""
from dataclasses import replace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.actor_context import SessionContext
from app.trusted_sessions import TrustedSessionResolver
from app.model_center.transfer_api import create_model_transfer_router
from test_model_center_transfers import service, settled


@pytest.fixture
def host(monkeypatch):
    import app.main as main
    monkeypatch.setattr(main, 'settings', replace(main.settings, enable_collaboration_runtime=False,
        enable_packaged_runtime=False, frontend_origin='http://127.0.0.1:5173'))
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2')
    monkeypatch.delenv('V1_ACCEPTANCE_MODE', raising=False)
    sessions = TrustedSessionResolver()
    session = SessionContext('transfer-host-session', 'transfer-client', 'transfer-actor', 'transfer-workspace')
    sessions.register('synthetic-transfer-host', session)
    monkeypatch.setattr(main, 'trusted_session_resolver', sessions)
    return main, sessions, session


HEADERS = {'X-Session-Token': 'synthetic-transfer-host'}
PREFIXES = ['/api/model-center/transfers', '/api/v1/model-center/transfers']


@pytest.mark.parametrize('prefix', PREFIXES)
def test_mounted_production_catalog_is_empty_and_sources_cannot_be_supplied(host, prefix):
    main, _, _ = host
    client = TestClient(main.app)
    response = client.get(prefix, headers=HEADERS)
    assert response.status_code == 200
    assert response.json()['sources'] == response.json()['items'] == []
    assert not response.json()['configured']
    assert response.headers['Cache-Control'] == 'no-store'
    rejected = client.post(prefix + '/preview', headers=HEADERS, json={'source_id': 'synthetic-fixture',
        'url': 'https://untrusted.example.test/secret.gguf', 'destination': '/private/user-files'})
    assert rejected.status_code == 422 and 'secret.gguf' not in rejected.text and '/private/' not in rejected.text
    unavailable = client.post(prefix + '/preview', headers=HEADERS, json={'source_id': 'synthetic-fixture'})
    assert unavailable.status_code == 409 and 'DOWNLOAD_SOURCE_NOT_CONFIGURED' in unavailable.text


@pytest.mark.parametrize('prefix', PREFIXES)
@pytest.mark.parametrize('method,suffix,body', [('GET','',None), ('POST','/preview',{'source_id':'synthetic-fixture'}),
    ('POST','/start',{'preview_id':'a'*32,'preview_digest':'b'*64,'confirmed':True}),
    ('POST','/'+'a'*32+'/pause',{'expected_version':1}),
    ('POST','/'+'a'*32+'/resume',{'expected_version':1,'confirmed':True}),
    ('POST','/'+'a'*32+'/cancel',{'expected_version':1}),
    ('POST','/'+'a'*32+'/cleanup-preview',{'expected_version':1}),
    ('POST','/'+'a'*32+'/cleanup',{'expected_version':1,'preview_id':'a'*32,'preview_digest':'b'*64,'confirmed':True})])
def test_every_transfer_route_requires_host_and_private_headers(host, prefix, method, suffix, body):
    main, _, _ = host
    response = TestClient(main.app).request(method, prefix + suffix, json=body)
    assert response.status_code == 401 and response.headers['Cache-Control'] == 'no-store'


@pytest.mark.parametrize('extra', [{'Forwarded': 'for=127.0.0.1'}, {'X-Forwarded-For':'127.0.0.1'},
    {'X-Real-IP':'127.0.0.1'}, {'X-Forwarded-Host':'localhost'}, {'X-Forwarded-Proto':'http'},
    {'Origin':'https://untrusted.example.test'}])
def test_forwarded_or_foreign_origin_never_becomes_host_authority(host, extra):
    main, _, _ = host
    response = TestClient(main.app).get(PREFIXES[0], headers=HEADERS | extra)
    assert response.status_code == 403 and response.headers['Cache-Control'] == 'no-store'


@pytest.mark.parametrize('prefix', PREFIXES)
def test_collaboration_membership_is_not_host_authority(host, monkeypatch, prefix):
    main, _, _ = host
    monkeypatch.setattr(main, 'settings', replace(main.settings, enable_collaboration_runtime=True))
    response = TestClient(main.app).get(prefix, headers=HEADERS)
    assert response.status_code == 403 and 'LOCAL_AI_HOST_AUTHORITY_UNAVAILABLE' in response.text


def test_feature_revocation_is_independent_of_valid_host(host, monkeypatch):
    main, _, _ = host
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    response = TestClient(main.app).get(PREFIXES[0], headers=HEADERS)
    assert response.status_code == 404 and 'EXPERIMENTAL_FEATURE_DISABLED' in response.text


@pytest.mark.parametrize('prefix', PREFIXES)
def test_original_host_guard_plus_synthetic_transfer_complete_without_register_or_launch(host, tmp_path, prefix):
    main, _, _ = host
    owner = service(tmp_path)
    app = FastAPI(); app.include_router(create_model_transfer_router(owner, prefix=prefix,
        host_authorization=main._local_discovery_host_authority))
    client = TestClient(app)
    preview = client.post(prefix + '/preview', headers=HEADERS, json={'source_id':'synthetic-fixture'})
    assert preview.status_code == 200
    value = preview.json()
    result = client.post(prefix + '/start', headers=HEADERS,
        json={'preview_id':value['preview_id'],'preview_digest':value['preview_digest'],'confirmed':True})
    assert result.status_code == 200
    assert settled(owner, result.json()['id'])['state'] == 'COMPLETED'
    assert client.get(prefix, headers=HEADERS).json()['items'][0]['state'] == 'COMPLETED'


def test_rebound_session_cannot_consume_previous_preview(host, tmp_path):
    main, sessions, session = host
    owner = service(tmp_path)
    app = FastAPI(); app.include_router(create_model_transfer_router(owner,
        host_authorization=main._local_discovery_host_authority))
    client = TestClient(app)
    value = client.post(PREFIXES[0] + '/preview', headers=HEADERS, json={'source_id':'synthetic-fixture'}).json()
    sessions.revoke('synthetic-transfer-host'); sessions.register('synthetic-transfer-host', session)
    result = client.post(PREFIXES[0] + '/start', headers=HEADERS,
        json={'preview_id':value['preview_id'],'preview_digest':value['preview_digest'],'confirmed':True})
    assert result.status_code == 409 and not owner._transport.calls
    assert list(owner.files.root.iterdir()) == []
