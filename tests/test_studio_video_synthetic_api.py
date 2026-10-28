"""Mounted original-owner video generation using synthetic decoded MP4 bytes.

The provider is a deterministic test adapter; no model or network is called.
"""
import base64
import hashlib
import json
import shutil
import subprocess

import pytest

from app.asset_providers import VideoGenerationResult
from test_studio_backend_integration_v2 import studio, check, shot_action, action
from test_studio_asset_query import rig

pytestmark = pytest.mark.file_backend_only


class SyntheticVideoAdapter:
    supports_dispatch_guard = True
    default_model = 'synthetic-video'
    endpoint = 'http://127.0.0.1:39001'

    def __init__(self, content):
        self.content = content
        self.calls = []

    def capabilities(self):
        return {'text_to_video': True, 'image_to_video': False, 'polling': False}

    def generate(self, request):
        request.dispatch_guard()
        self.calls.append(request)
        uri = 'data:video/mp4;base64,' + base64.b64encode(self.content).decode('ascii')
        return VideoGenerationResult(request.provider_id, request.model_id, uri, status='SUCCEEDED')


def configure(e, adapter):
    e.production.video_providers['synthetic-video'] = adapter
    e.production.video_configs['synthetic-video'] = {
        'enabled': True, 'local': True, 'requires_credential': False,
        'default_model': adapter.default_model,
    }


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_storyboard_video_api_with_synthetic_adapter_and_real_media(studio, tmp_path, prefix):
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        pytest.skip('ffmpeg and ffprobe required for real video verification')
    e = studio
    e.base = f'{prefix}/projects/{e.nid}/studio'
    e.doc_url = f'{prefix}/novels/{e.nid}/experimental/creative/documents/{e.document["id"]}'
    media = tmp_path / 'synthetic-provider-result.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                    'color=c=blue:s=64x64:r=10:d=5', '-c:v', 'mpeg4', '-y', str(media)],
                   check=True, timeout=30)
    content = media.read_bytes()
    adapter = SyntheticVideoAdapter(content)
    configure(e, adapter)
    receipt = check(e.client.post(e.doc_url + '/storyboard/approve', headers=e.headers, json={
        'expected_version': e.storyboard['document_snapshot']['version'],
        'reviewed_content_digest': e.storyboard['content_digest']}))
    assert receipt['approved']
    body = {**shot_action(e, receipt), 'operation_id': 'm7.video.t2v', 'request_id': 'synthetic-video-one',
            'provider': {'operation_id': 'm7.video.t2v', 'provider_id': 'synthetic-video', 'model_id': adapter.default_model},
            'parameters': {'width': 64, 'height': 64, 'frame_rate': 10, 'duration_seconds': 5, 'seed': 7}}
    invalid = e.client.post(e.doc_url + '/shots/shot-one/video-request', headers=e.headers,
                            json={**body, 'parameters': {**body['parameters'], 'duration_seconds': 4}})
    assert invalid.status_code in (409, 422) and not adapter.calls
    prepared = check(e.client.post(e.doc_url + '/shots/shot-one/video-request', headers=e.headers, json=body))
    assert not prepared['automatic_dispatch'] and not prepared['model_called'] and not adapter.calls
    preview = check(e.client.post(e.base + '/production/preview', headers=e.headers, json=prepared['command']))
    assert not adapter.calls
    creation = {'command': prepared['command'], 'reviewed_preview_digest': preview['preview_digest']}
    queued = check(e.client.post(e.base + '/production/jobs', headers=e.headers, json=creation), 201)
    replay = check(e.client.post(e.base + '/production/jobs', headers=e.headers, json=creation), 201)
    assert replay['id'] == queued['id'] and queued['status'] == 'QUEUED' and not adapter.calls
    url = e.base + '/production/jobs/video/' + queued['id']
    stale = {**action(queued), 'expected_version': queued['version'] + 1}
    refused = e.client.post(url + '/execute', headers=e.headers, json=stale)
    assert refused.status_code == 409 and not adapter.calls
    result = check(e.client.post(url + '/execute', headers=e.headers, json=action(queued)))
    assert result['status'] == 'AWAITING_REVIEW' and len(adapter.calls) == 1
    assert adapter.calls[0].parameters['duration_seconds'] == 5
    assert result['media_measurement']['validation'] == 'DECODED'
    assert e.client.post(url + '/execute', headers=e.headers, json=action(queued)).status_code == 409
    assert len(adapter.calls) == 1
    raw = e.client.get(url + '/candidate', headers=e.headers)
    assert raw.status_code == 200 and raw.content == content
    assert result['output_candidate']['digest'] == hashlib.sha256(raw.content).hexdigest()
    candidate = tmp_path / 'candidate.mp4'; candidate.write_bytes(raw.content)
    probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                            'format=duration:stream=codec_type,codec_name,width,height,r_frame_rate',
                            '-of', 'json', str(candidate)], check=True, timeout=30, capture_output=True, text=True)
    data = json.loads(probe.stdout)
    stream = next(x for x in data['streams'] if x['codec_type'] == 'video')
    assert (stream['codec_name'], stream['width'], stream['height'], stream['r_frame_rate']) == ('mpeg4', 64, 64, '10/1')
    assert float(data['format']['duration']) == 5.0
    subprocess.run(['ffmpeg', '-v', 'error', '-i', str(candidate), '-map', '0:v:0',
                    '-f', 'null', '-'], check=True, timeout=30, capture_output=True)
    e.reopen(); configure(e, adapter)
    recovered = check(e.client.get(url, headers=e.headers))
    assert recovered['status'] == 'AWAITING_REVIEW' and len(adapter.calls) == 1
    reviewed = check(e.client.post(url + '/review', headers=e.headers, json={
        **action(recovered), 'reviewed_output_digest': recovered['output_candidate']['digest']}))
    assert reviewed['status'] == 'APPROVED' and len(adapter.calls) == 1
    pin = {key: reviewed[key] for key in ('id', 'version', 'request_digest', 'receipt_digest')}
    asset = {'asset_id': reviewed['output_candidate']['id'], 'version': reviewed['approved_asset_version'],
             'digest': reviewed['output_candidate']['digest'], 'kind': 'video'}
    adopted = check(e.client.post(e.doc_url + '/shots/shot-one/video-binding', headers=e.headers,
                                  json={**shot_action(e, receipt), 'asset': asset, 'video_job': pin}))
    assert adopted['shots'][0]['video_result']['asset'] == asset
    e.reopen(); configure(e, adapter)
    reopened = check(e.client.get(e.doc_url + '/storyboard', headers=e.headers))
    assert reopened['shots'][0]['video_result']['asset'] == asset
    assert check(e.client.get(url, headers=e.headers))['status'] == 'APPROVED'
    assert len(adapter.calls) == 1
