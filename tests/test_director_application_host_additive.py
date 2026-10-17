"""Actual application composition and original Host authority; mocked provider wire."""
from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from creative_director_execution_fixture import lifecycle
from test_v2_independent_director_adoption import board, review_body, raw_bytes
from test_director_model_transport_additive import pending, preview_request

pytestmark = pytest.mark.file_backend_only


@pytest.fixture(params=['/api', '/api/v1'])
def application_host(lifecycle, monkeypatch, request):
    import app.main as main
    import app.api as legacy
    import app.experimental.api as experimental
    e = lifecycle
    # Keep the actual local workbench resolver: its original actor is local-author.
    # Do not replace authorize(), Host guards, origin checks or session resolution.
    e.actor = 'local-author'
    e.ctx.actor = e.actor
    board(e)
    monkeypatch.setattr(main, 'settings', replace(main.settings,
        enable_packaged_runtime=False, enable_collaboration_runtime=False,
        frontend_origin=e.host_settings.frontend_origin))
    monkeypatch.setattr(legacy, 'settings', replace(legacy.settings,
        enable_packaged_runtime=False, enable_collaboration_runtime=False))
    monkeypatch.setattr(main, 'trusted_session_resolver', e.sessions)
    monkeypatch.setattr(legacy, 'novel_service', e.novels)
    # Existing mounted route closures keep this original service object.
    captured = experimental.creative_service
    for name, value in vars(e.documents).items():
        monkeypatch.setattr(captured, name, value)
    client = TestClient(main.app, client=('127.0.0.1', 41000), base_url='http://127.0.0.1:8000')
    base = request.param + f'/novels/{e.nid}/experimental/creative/director-proposals'
    m = SimpleNamespace(client=client, url=base + f'/{e.row["id"]}/model-v1',
                        headers={'X-Session-Token': e.token}, base=base)
    return e, m


def test_actual_application_advertises_only_original_supported_actions(application_host):
    e, m = application_host
    before = raw_bytes(e)
    result = m.client.get(m.base + '/model-capabilities', headers=m.headers)
    assert result.status_code == 200, result.text
    assert result.json().get('independent_director_contract') == 'CREATIVE_DIRECTOR_MODEL_V1'
    assert raw_bytes(e) == before and e.requests == [] and e.persistence.load_all() == []


def test_actual_application_preview_to_review_uses_existing_owners(application_host):
    e, m = application_host
    candidate = pending(e, m)
    body = review_body(candidate)
    body['director_notes'][0]['note'] = 'Explicit application-level human review.'
    result = m.client.post(m.url + '/review', headers=m.headers, json=body)
    assert result.status_code == 200, result.text
    receipt = result.json()['receipt']
    assert receipt['document']['status'] == 'DRAFT'
    before = raw_bytes(e)
    reopened = m.client.get(m.url + '/adopted-draft', headers=m.headers)
    assert reopened.status_code == 200 and reopened.json()['receipt'] == receipt
    assert raw_bytes(e) == before
    assert len(e.requests) == len(e.persistence.load_all()) == 1
    document = e.documents.get(e.nid, e.scope, receipt['document']['document_id'])
    assert document['director_notes'][0]['note'] == body['director_notes'][0]['note']


@pytest.mark.parametrize('change', ['missing_token', 'revoked_token', 'origin', 'forwarded', 'remote', 'collaboration_host', 'flag', 'v1', 'missing_marker'])
def test_actual_application_keeps_original_host_and_feature_denials(application_host, monkeypatch, change):
    import app.main as main
    e, m = application_host
    headers = dict(m.headers)
    if change == 'missing_token': headers = {}
    if change == 'revoked_token': e.sessions.revoke(e.token)
    if change == 'origin': headers['Origin'] = 'https://untrusted.example'
    if change == 'forwarded': headers['X-Forwarded-For'] = '127.0.0.1'
    if change == 'remote':
        m.client = TestClient(main.app, client=('192.0.2.20', 41000), base_url='http://127.0.0.1:8000')
    if change == 'collaboration_host':
        monkeypatch.setattr(main, 'settings', replace(main.settings, enable_collaboration_runtime=True))
    if change == 'flag': monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    if change == 'v1': monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    marker = e.root / 'novels' / e.nid / 'creative_project_v2.json'
    if change == 'missing_marker': marker.unlink()  # Owned synthetic fixture only.
    before = raw_bytes(e)
    response = m.client.post(m.url + '/preview', headers=headers, json=preview_request(e))
    assert response.status_code in (401, 403, 404, 409), response.text
    assert raw_bytes(e) == before and e.requests == [] and e.persistence.load_all() == []
    if change == 'remote':
        # The original application middleware rejects before any route handler.
        assert response.json() == {'detail': {'code': 'LOCAL_RUNTIME_LOOPBACK_REQUIRED'}}
    else:
        assert response.headers['cache-control'] == 'no-store'
    if change == 'missing_marker': assert not marker.exists()


def test_actual_application_over_loopback_tcp_keeps_manual_review(application_host):
    """Native HTTP transport, real File owners; provider response remains a fixture."""
    import socket
    import threading
    import time
    import httpx
    import uvicorn
    import app.main as main
    e, m = application_host
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(('127.0.0.1', 0))
    listener.listen(32)
    port = listener.getsockname()[1]
    # Do not start optional interop workers; exercise the already composed app.
    server = uvicorn.Server(uvicorn.Config(main.app, loop='asyncio', lifespan='off',
        access_log=False, log_level='warning'))
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    try:
        thread.start()
        deadline = time.monotonic() + 10
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(.01)
        assert server.started, 'Native loopback server did not start'
        with httpx.Client(base_url=f'http://127.0.0.1:{port}', trust_env=False, timeout=10) as client:
            m.client = client
            candidate = pending(e, m)
            assert len(e.requests) == 1
            before_review = raw_bytes(e)
            status = client.get(m.url + '/status', headers=m.headers)
            assert status.status_code == 200, status.text
            assert status.json()['receipt']['phase'] == 'PENDING_REVIEW'
            assert status.json()['receipt']['adoption'] is None
            assert client.get(m.url + '/adopted-draft', headers=m.headers).status_code == 409
            assert raw_bytes(e) == before_review
            body = review_body(candidate)
            response = client.post(m.url + '/review', headers=m.headers, json=body)
            assert response.status_code == 200, response.text
            receipt = response.json()['receipt']
            assert receipt['document']['status'] == 'DRAFT'
            before = raw_bytes(e)
            reopened = client.get(m.url + '/adopted-draft', headers=m.headers)
            assert reopened.status_code == 200 and reopened.json()['receipt'] == receipt
            assert raw_bytes(e) == before and len(e.requests) == 1
    finally:
        server.should_exit = True
        if thread.ident is not None:
            thread.join(10)
        listener.close()
        assert not thread.is_alive(), 'Native loopback server leaked'
