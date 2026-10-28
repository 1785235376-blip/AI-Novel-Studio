"""Synthetic provider result arriving after original VIDEO cancellation."""
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from threading import Event

import pytest

from app.asset_providers import VideoGenerationResult
from test_studio_asset_query import rig
from test_studio_backend_integration_v2 import studio, check, shot_action, action
from test_studio_video_synthetic_api import SyntheticVideoAdapter, configure

pytestmark = pytest.mark.file_backend_only


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_cancel_fences_late_video_result_and_reopen(studio, tmp_path, prefix):
    if not shutil.which('ffmpeg'):
        pytest.skip('ffmpeg required to construct a real synthetic MP4')
    e = studio
    e.base = f'{prefix}/projects/{e.nid}/studio'
    e.doc_url = f'{prefix}/novels/{e.nid}/experimental/creative/documents/{e.document["id"]}'
    media = tmp_path / 'late-result.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
        'color=c=blue:s=64x64:r=10:d=5', '-c:v', 'mpeg4', '-threads', '1', '-y', str(media)],
        check=True, timeout=30)
    entered, release = Event(), Event()

    class DelayedAdapter(SyntheticVideoAdapter):
        def generate(self, request):
            request.dispatch_guard()
            self.calls.append(request)
            entered.set()
            if not release.wait(15):
                raise TimeoutError('synthetic result gate timed out')
            uri = 'data:video/mp4;base64,' + base64.b64encode(self.content).decode('ascii')
            return VideoGenerationResult(request.provider_id, request.model_id, uri, status='SUCCEEDED')

    adapter = DelayedAdapter(media.read_bytes())
    configure(e, adapter)
    storyboard = check(e.client.post(e.doc_url + '/storyboard/approve', headers=e.headers, json={
        'expected_version': e.storyboard['document_snapshot']['version'],
        'reviewed_content_digest': e.storyboard['content_digest']}))
    body = {**shot_action(e, storyboard), 'operation_id': 'm7.video.t2v', 'request_id': 'late-cancel-video',
        'provider': {'operation_id': 'm7.video.t2v', 'provider_id': 'synthetic-video', 'model_id': adapter.default_model},
        'parameters': {'width': 64, 'height': 64, 'frame_rate': 10, 'duration_seconds': 5, 'seed': 7}}
    prepared = check(e.client.post(e.doc_url + '/shots/shot-one/video-request', headers=e.headers, json=body))
    preview = check(e.client.post(e.base + '/production/preview', headers=e.headers, json=prepared['command']))
    queued = check(e.client.post(e.base + '/production/jobs', headers=e.headers,
        json={'command': prepared['command'], 'reviewed_preview_digest': preview['preview_digest']}), 201)
    url = e.base + '/production/jobs/video/' + queued['id']
    before = check(e.client.get(e.doc_url + '/storyboard', headers=e.headers))
    with e.workspace._asset_scope(e.nid, e.scope):
        original_assets = e.workspace.assets.list(e.nid, actor_id=e.actor)

    with ThreadPoolExecutor(max_workers=2) as pool:
        run = pool.submit(e.client.post, url + '/execute', headers=e.headers, json=action(queued))
        try:
            assert entered.wait(10) and len(adapter.calls) == 1
            inflight = check(e.client.get(url, headers=e.headers))
            assert inflight['status'] == 'SEND_RESERVED'
            cancel = pool.submit(e.client.post, url + '/cancel', headers=e.headers, json=action(inflight))
            cancelled = check(cancel.result(timeout=5))
            assert cancelled['status'] == 'CANCELLED' and cancelled['output_candidate'] is None
            assert cancelled['cancellation_mode'] == 'LOCAL_RESULT_DISCARD'
            assert cancelled['remote_compute_may_continue'] is True
        finally:
            release.set()
        response = run.result(timeout=15)
    assert response.status_code == 422
    assert check(e.client.get(url, headers=e.headers))['status'] == 'CANCELLED'
    assert e.client.get(url + '/candidate', headers=e.headers).status_code == 404
    assert check(e.client.get(e.doc_url + '/storyboard', headers=e.headers)) == before
    with e.workspace._asset_scope(e.nid, e.scope):
        assert e.workspace.assets.list(e.nid, actor_id=e.actor) == original_assets
    e.reopen(); configure(e, adapter)
    reopened = check(e.client.get(url, headers=e.headers))
    assert reopened['status'] == 'CANCELLED' and reopened['output_candidate'] is None
    replay = e.client.post(url + '/execute', headers=e.headers, json=action(reopened))
    assert replay.status_code == 422
    review = e.client.post(url + '/review', headers=e.headers, json={
        **action(reopened), 'reviewed_output_digest': hashlib.sha256(adapter.content).hexdigest()})
    assert review.status_code == 409
    assert check(e.client.get(e.doc_url + '/storyboard', headers=e.headers)) == before
    assert len(adapter.calls) == 1
    if directory := os.getenv('STUDIO_VIDEO_CANCEL_EVIDENCE'):
        target = Path(directory); target.mkdir(parents=True, exist_ok=True)
        (target / ('api-v1.json' if prefix.endswith('/v1') else 'api.json')).write_text(json.dumps({
            'prefix': prefix, 'provider_calls': len(adapter.calls), 'cancel_state': cancelled['status'],
            'cancel_mode': cancelled['cancellation_mode'], 'remote_compute_may_continue': cancelled['remote_compute_may_continue'],
            'late_execute_http_status': response.status_code, 'replay_http_status': replay.status_code,
            'forged_review_http_status': review.status_code, 'reopen_state': reopened['status'],
            'output_candidate': reopened['output_candidate'], 'assets_unchanged': True, 'storyboard_unchanged': True,
            'provider_media_sha256': hashlib.sha256(adapter.content).hexdigest(), 'model_called': False,
        }, indent=2), encoding='utf-8')
