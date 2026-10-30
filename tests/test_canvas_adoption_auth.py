"""Real original File owners and Mock PNG execution, no manufactured approvals."""
from copy import deepcopy
import hashlib
from contextlib import contextmanager
import socket
from threading import Thread
import time

import httpx
import pytest
import uvicorn

from test_studio_asset_query import rig
from test_studio_backend_integration_v2 import studio, check, queue, execute, review, job_url
from test_cloud_formal_canvas_node import command

pytestmark = pytest.mark.file_backend_only


@pytest.fixture
def canvas_studio(studio, monkeypatch):
    from app.creative.graph import CreativeGraphService
    from app.experimental import api
    e = studio
    original_reopen = e.reopen

    def mount_graph():
        graph = CreativeGraphService(e.workspace.store, e.workspace)
        graph.configure_media(e.production)
        for name, value in graph.__dict__.items():
            monkeypatch.setattr(api.creative_graph_service, name, value, raising=False)
        e.graph = graph

    def reopen():
        original_reopen()
        mount_graph()
    mount_graph()
    e.reopen = reopen
    return e


def approved_canvas(e, *, request_id='canvas-auth-positive'):
    target = check(e.client.post(e.base + '/canvas-views', headers=e.headers, json={
        'request_id': request_id, 'expected_version': 0,
        'definition': {'schema_version': 1, 'title': 'Synthetic canvas auth', 'cards': [],
                       'viewport': {'x': 0, 'y': 0, 'zoom': 1}}}), 201)
    value = command(e, target, request_id=request_id+'-job')
    value['model_id'] = 'synthetic.safetensors'
    row, _ = queue(e, {'command': value})
    assert row['status'] == 'QUEUED' and len(e.calls) == 0
    row = execute(e, row)
    assert row['status'] == 'AWAITING_REVIEW' and len(e.calls) == 1
    candidate = e.client.get(job_url(e, row)+'/candidate', headers=e.headers)
    assert candidate.status_code == 200 and candidate.content == e.png
    assert check(e.client.get(e.base+'/canvas-views/'+target['id'], headers=e.headers))['definition']['cards'] == []
    row = review(e, row)
    assert row['status'] == 'APPROVED'
    pin = {'asset_id': row['output_candidate']['id'], 'version': row['approved_asset_version'],
           'digest': row['output_candidate']['digest'], 'kind': 'image'}
    body = {'confirmed': True, 'expected_incarnation': value['canvas_image_node']['incarnation'],
            'expected_version': target['version'], 'expected_definition_digest': target['definition_digest'],
            'job_id': row['id'], 'job_version': row['version'], 'job_request_digest': row['request_digest'], 'asset': pin}
    return target, row, body


def snapshot(e):
    return {p.relative_to(e.rig.root).as_posix(): (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())
            for p in e.rig.root.rglob('*') if p.is_file() and '.workspace-mutation-locks' not in p.parts}


@contextmanager
def tcp_client():
    """Actual loopback HTTP using the same mounted original application."""
    from app.main import app
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='error', lifespan='off'))
    thread = Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic()+15
        while not server.started:
            assert thread.is_alive() and time.monotonic()<deadline
            time.sleep(.01)
        with httpx.Client(base_url=f'http://127.0.0.1:{port}', trust_env=False, timeout=30) as client:
            yield client
    finally:
        server.should_exit = True
        thread.join(10)
        sock.close()
        assert not thread.is_alive()


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_first_empty_canvas_adoption_replay_reopens_over_tcp(canvas_studio, prefix):
    e = canvas_studio
    e.base = prefix + f'/projects/{e.nid}/studio'
    with tcp_client() as client:
        e.client = client
        target, row, body = approved_canvas(e)
        url = e.base+'/canvas-views/'+target['id']
        result = check(client.post(url+'/image-node-result', headers=e.headers, json=body))
        assert result['version'] == target['version']+1
        assert result['definition']['cards'][0]['asset'] == body['asset']
        assert result['definition']['image_node_origin']['job_id'] == row['id']
        before = snapshot(e)
        assert check(client.post(url+'/image-node-result', headers=e.headers, json=body)) == result
        assert snapshot(e) == before
        e.reopen()
        assert check(client.get(url, headers=e.headers)) == result
        assert check(client.get(job_url(e,row), headers=e.headers))['status'] == 'APPROVED'
        assert len(e.calls) == 1 and snapshot(e) == before


@pytest.mark.parametrize('token', [None, 'invalid-local-token'])
def test_local_unhosted_canvas_association_keeps_original_local_contract(canvas_studio, token):
    e = canvas_studio
    target, row, body = approved_canvas(e)
    headers = {} if token is None else {'X-Session-Token': token}
    # Original nonpackaged/noncollaboration canvas owner does not require a
    # Host session. Execution/review above still used the original Host gate.
    result = check(e.client.post(e.base+'/canvas-views/'+target['id']+'/image-node-result', headers=headers, json=body))
    assert result['version'] == 2 and len(e.calls) == 1
