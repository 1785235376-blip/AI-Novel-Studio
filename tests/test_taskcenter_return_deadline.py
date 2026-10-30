"""Final HTTP observation must not outlive the cursor's fixed deadline."""
import socket
import threading
import time
import httpx
import uvicorn
import pytest
from test_taskcenter_local_mixed_http import mixed, get, snapshot
from test_taskcenter_lifecycle_http import cursor_rig, rig
from app.experimental.taskcenter_cursor import TaskCenterCursorEngine

pytestmark = pytest.mark.file_backend_only

@pytest.fixture
def tcp_client():
    from app.main import app
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level='error', lifespan='off'))
    thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
    thread.start()
    try:
        end = time.monotonic() + 10
        while not server.started:
            assert thread.is_alive() and time.monotonic() < end
            time.sleep(.01)
        with httpx.Client(base_url=f'http://127.0.0.1:{port}', trust_env=False) as client:
            yield client
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()
        assert not thread.is_alive()


@pytest.mark.parametrize('prefix' , ['/api', '/api/v1'])
@pytest.mark.parametrize('transport', ['mounted', 'tcp'])
@pytest.mark.parametrize('page_kind', ['first', 'continuation', 'last', 'single', 'empty'])
def test_deadline_elapsed_inside_final_capture_refuses(mixed, prefix, page_kind, transport, request):
    e = mixed
    if transport == 'tcp':
        e.monkeypatch.setattr(e.rig, 'client', request.getfixturevalue('tcp_client'))
    now = [100.0]
    e.monkeypatch.setattr(e.adapter, 'engine', TaskCenterCursorEngine(ttl_seconds=10, clock=lambda: now[0]))
    params = {}
    if page_kind == 'single': params['limit'] = 100
    if page_kind == 'empty': params['q'] = 'nothing-matches'
    if page_kind in ('continuation', 'last'):
        first = get(e, prefix=prefix); assert first.status_code == 200
        params['cursor'] = first.json()['next_cursor']
        if page_kind == 'last':
            second = get(e, params, prefix); assert second.status_code == 200
            params['cursor'] = second.json()['next_cursor']
    original = e.adapter._checked_capture
    calls = []
    def final_delay(*args, **kwargs):
        result = original(*args, **kwargs)
        calls.append(True)
        if len(calls) == 3: now[0] = 110.0
        return result
    e.monkeypatch.setattr(e.adapter, '_checked_capture', final_delay)
    before = snapshot(e.rig.root)
    result = get(e, params, prefix)
    assert len(calls) == 3
    assert result.status_code == 409, result.text
    assert result.json()['detail']['code'] == 'TASKCENTER_CURSOR_RESTART_REQUIRED'
    assert result.headers['cache-control'] == 'no-store'
    assert snapshot(e.rig.root) == before
