"""New saved-video routes mounted with original Host authority and CPU owner."""
from copy import deepcopy
import hashlib
from uuid import uuid4

import pytest

from app.actor_context import SessionContext
from app.creative.canvas_views import CreativeCanvasViews
from app.creative.graph_asset_inputs import GraphAssetInputs
from app.services.image_job_service import ImageJobService
from app.services.video_assembly_service import VideoAssemblyService
from test_r3_mounted_contracts import checked, mounted, prefix
from test_studio_canvas_video_bridge import definition, render_calls
from test_studio_canvas_video_cpu_owner_probe import _source_video, _decoded_measurement
from test_v2_audio_editing_pipeline import source
from test_v2_audio_wav_controls import NoControl, action
from test_v2_independent_workspace import upload
from test_v2_independent_workspace_api import client


@pytest.fixture
def video_client(client, monkeypatch, tmp_path):
    e = client
    e.host = 'video-canvas-host-' + uuid4().hex
    session = SessionContext('session-' + e.host, 'client-' + e.host, 'video-author', 'video-workspace')
    e.sessions.register(e.host, session); e.headers = {'X-Session-Token': e.host}
    checked(e.client.post(e.studio_base + '/activate', headers=e.headers))
    e.production = e.experimental.studio_production_service
    for name, value in (('workspace', e.studio), ('store', e.studio.store), ('audio_store', e.audio),
            ('image_jobs', ImageJobService(e.root)), ('image_registry', NoControl()), ('vault', NoControl()),
            ('transport', NoControl()), ('video_owner', VideoAssemblyService(e.root, e.assets))):
        monkeypatch.setattr(e.production, name, value)
    monkeypatch.setattr(e.production, 'timeline_inputs', GraphAssetInputs(e.production))
    e.graphs = e.experimental.creative_graph_service
    monkeypatch.setattr(e.graphs, 'store', e.studio.store)
    monkeypatch.setattr(e.graphs, 'workspace', e.studio)
    monkeypatch.setattr(e.graphs, 'asset_inputs', GraphAssetInputs(e.graphs))
    monkeypatch.setattr(e.graphs, 'canvas_views', CreativeCanvasViews(e.graphs))
    e.graphs.configure_media(e.production)
    media = _source_video(tmp_path)
    e.source = checked(e.client.post(e.studio_base + '/assets', headers=e.headers,
        json=upload(media.read_bytes(), kind='video', filename='synthetic-red-blue.mp4')), 201)
    pin = source(e.source)
    e.base = e.studio_base + '/production'; e.canvas_base = e.studio_base + '/canvas-views'
    e.canvas = checked(e.client.post(e.canvas_base, headers=e.headers, json={
        'request_id': 'saved-video-origin', 'definition': {'title': 'Saved video origin', 'cards': [
            {'id': 'origin-video', 'position': {'x': 40, 'y': 60}, 'asset': {
                'asset_id': pin['id'], 'version': pin['version'], 'digest': pin['digest'], 'kind': 'video'}}]}}), 201)
    e.timeline = checked(e.client.post(e.base + '/timelines', headers=e.headers, json={
        'expected_version': 0, 'title': 'Explicit saved video trim', 'timeline': definition(pin)}), 201)
    e.command = {'contract': 'studio-canvas-video-trim/1', 'operation_id': 'm9.timeline.multitrack',
        'request_id': 'saved-video-http', 'provider_id': None, 'model_id': None, 'prompt': '',
        'allow_cloud': False, 'license_note': '', 'parameters': {'in_ms': 1000, 'out_ms': 1600},
        'source_snapshots': [pin], 'timeline_snapshot': {'id': e.timeline['id'], 'version': e.timeline['version'],
            'digest': e.timeline['timeline_digest']}, 'canvas_return': {'contract': 'studio-canvas-return/1',
            'project_id': e.nid, 'scope': e.scope, 'incarnation': e.studio.store.incarnation(e.nid),
            'canvas_id': e.canvas['id'], 'canvas_version': e.canvas['version'],
            'canvas_digest': e.canvas['definition_digest'], 'card_id': 'origin-video', 'source': pin}}
    return e


def test_mounted_video_bridge_explicit_routes_process_and_review_original_candidate(video_client, render_calls, tmp_path):
    e = video_client
    response = e.client.post(e.base + '/canvas-video/preview', headers=e.headers, json=e.command)
    captured = checked(response)
    assert captured['command'] == e.command and captured['automatic_dispatch'] is False
    assert response.headers['cache-control'] == 'no-store' and response.headers['x-content-type-options'] == 'nosniff'
    queued = checked(e.client.post(e.base + '/canvas-video/queue', headers=e.headers,
        json={'command': e.command, 'reviewed_preview_digest': captured['preview_digest']}), 201)
    assert queued['status'] == 'QUEUED' and queued['canvas_video'] == e.command and not render_calls
    path = e.base + '/jobs/timeline/' + queued['id']
    assert checked(e.client.get(path, headers=e.headers))['status'] == 'QUEUED'
    old = e.client.post(path + '/execute', headers=e.headers, json=action(queued).model_dump())
    # The original common.api_call projects ValueError as 422/EXPERIMENTAL_INVALID.
    assert old.status_code == 422 and old.json()['detail'] == {
        'code': 'EXPERIMENTAL_INVALID', 'message': 'STUDIO_TIMELINE_ALREADY_RENDERED_EXPLICITLY'}
    assert not render_calls
    executed = checked(e.client.post(e.base + '/canvas-video/jobs/' + queued['id'] + '/execute',
        headers=e.headers, json=action(queued).model_dump()))
    assert executed['status'] == 'SUCCEEDED' and executed['command'] is None and executed['canvas_video'] == e.command
    assert len(render_calls) == 1
    candidate = e.client.get(path + '/candidate', headers=e.headers)
    assert candidate.status_code == 200 and candidate.headers['content-type'].startswith('video/mp4')
    assert hashlib.sha256(candidate.content).hexdigest() == executed['output_candidate']['digest']
    media = tmp_path / 'mounted-candidate.mp4'; media.write_bytes(candidate.content)
    proof = _decoded_measurement(media)
    assert (proof['decoded_frames'], proof['duration_ms'], proof['width'], proof['height'], proof['fps']) == (15, 600, 640, 360, '25/1')
    assert proof['codec'] == 'h264'
    assert all(rgb[2] > 230 and rgb[0] < 20 for rgb in proof['center_rgb'])
    asset_path = e.studio_base + '/assets/' + executed['output_candidate']['id']
    assert e.client.get(asset_path, headers=e.headers).status_code == 404
    approved = checked(e.client.post(path + '/review', headers=e.headers, json=action(executed, True).model_dump()))
    assert approved['status'] == 'APPROVED' and len(render_calls) == 1
    assert checked(e.client.get(asset_path, headers=e.headers))['kind'] == 'video'
    # Original VideoAssembly GET enriches these two fields; review projects
    # its write receipt. All other persisted fields must remain identical.
    assert approved['execution_state'] is None and approved['needs_reconciliation'] is None
    assert checked(e.client.get(path, headers=e.headers)) == {
        **approved, 'execution_state': 'APPROVED', 'needs_reconciliation': False}


def test_mounted_video_bridge_host_and_closed_command_fences_do_not_render(video_client, render_calls):
    e = video_client
    for headers in ({}, {'X-Session-Token': 'forged'}, {**e.headers, 'Origin': 'https://untrusted.invalid'},
            {**e.headers, 'Forwarded': 'for=127.0.0.1'}):
        response = e.client.post(e.base + '/canvas-video/preview', headers=headers, json=e.command)
        assert response.status_code in {401, 403}, response.text
    invalid = deepcopy(e.command); invalid['parameters']['in_ms'] = True
    response = e.client.post(e.base + '/canvas-video/preview', headers=e.headers, json=invalid)
    assert response.status_code == 422
    captured = checked(e.client.post(e.base + '/canvas-video/preview', headers=e.headers, json=e.command))
    queued = checked(e.client.post(e.base + '/canvas-video/queue', headers=e.headers,
        json={'command': e.command, 'reviewed_preview_digest': captured['preview_digest']}), 201)
    e.sessions.revoke(e.host)
    response = e.client.post(e.base + '/canvas-video/jobs/' + queued['id'] + '/execute',
        headers=e.headers, json=action(queued).model_dump())
    assert response.status_code == 401 and not render_calls
    assert len(list(e.assets.root.glob('*.bin'))) == 1
