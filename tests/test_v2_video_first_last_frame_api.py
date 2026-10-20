"""Mounted two-image first/last-frame video production on the original owners.

Synthetic provider only: it proves the exact two image bytes and their ordered
role binding reach the adapter, not model quality. Unsupported adapters must
reject rather than silently drop the last frame.
"""
import base64
import json
from uuid import uuid4

import pytest

from app.asset_providers import VideoGenerationResult
from test_r3_mounted_contracts import checked, mounted, prefix
from test_v2_independent_workspace_api import client
from test_v2_discovered_image_production_api import image_client, action, assert_success_private_headers
from test_v2_independent_workspace import png_bytes
from test_v2_video_runtime_foundation import cpu_video


class FrameProvider:
    supports_dispatch_guard = True
    endpoint = 'http://127.0.0.1:9/v1'
    default_model = 'frame-model'

    def __init__(self, video_bytes, *, end_frame=True):
        self.video_bytes = video_bytes
        self.requests = []
        self.end_frame = end_frame

    def capabilities(self):
        return {'text_to_video': False, 'image_to_video': True, 'video_to_video': False,
                'start_frame': True, 'end_frame': self.end_frame, 'polling': False, 'cancellation': False}

    def health_check(self):
        return True

    def generate(self, request):
        self.requests.append(request)
        if request.dispatch_guard is not None: request.dispatch_guard()
        return VideoGenerationResult('frame-video', 'frame-model',
            video_uri='data:video/webm;base64,' + base64.b64encode(self.video_bytes).decode(), status='SUCCEEDED')


def configure(e, provider):
    e.production.video_providers = {'frame-video': provider}
    e.production.video_configs = {'frame-video': {'enabled': True, 'local': True, 'default_model': 'frame-model',
        'model_id': 'frame-model', 'endpoint': provider.endpoint, 'capabilities': ['VIDEO'],
        'video_to_video': False}}


def upload(e, color, key):
    body = {'filename': key + '.png', 'kind': 'image',
            'content_base64': base64.b64encode(png_bytes(color)).decode(), 'idempotency_key': key}
    return checked(e.client.post(e.studio_base + '/assets', headers=e.headers, json=body), 201)


def command(provider, assets, *, frames=True, operation='m7.video.i2v'):
    sources = [{'id': row['id'], 'kind': 'ASSET', 'version': row['version'], 'digest': row['sha256'], 'asset_kind': 'image'} for row in assets]
    value = {'operation_id': operation, 'request_id': 'mounted-first-last-' + operation.split('.')[-1],
             'provider_id': 'frame-video', 'model_id': 'frame-model', 'prompt': 'FIRST TO LAST SYNTHETIC',
             'parameters': {'width': 64, 'height': 64, 'duration_seconds': 1, 'frame_rate': 8, 'seed': 7},
             'source_snapshots': sources}
    if frames:
        value['video_frames'] = [{'role': 'FIRST', 'source': sources[0]}, {'role': 'LAST', 'source': sources[1]}]
    return value


def test_mounted_two_frames_reach_adapter_as_two_exact_images(image_client, tmp_path):
    e = image_client
    video = cpu_video(tmp_path)
    provider = FrameProvider(video)
    configure(e, provider)
    first = upload(e, b'\x11\x22\x33', 'frame-first')
    last = upload(e, b'\x44\x55\x66', 'frame-last')
    value = command(provider, [first, last])
    providers = checked(e.client.get(e.base + '/providers', headers=e.headers))
    row = next(item for item in providers['items'] if item['operation_id'] == 'm7.video.i2v')
    assert row['video_frame_capabilities'] == {'start_frame': True, 'end_frame': True, 'multi_reference': False}
    preview_response = e.client.post(e.base + '/preview', headers=e.headers, json=value)
    assert_success_private_headers(preview_response)
    preview = checked(preview_response)
    assert [frame['role'] for frame in preview['command']['video_frames']] == ['FIRST', 'LAST']
    assert [source['id'] for source in preview['command']['source_snapshots']] == [first['id'], last['id']]
    assert [source['digest'] for source in preview['command']['source_snapshots']] == [first['sha256'], last['sha256']]
    job = checked(e.client.post(e.base + '/jobs', headers=e.headers,
        json={'command': value, 'reviewed_preview_digest': preview['preview_digest']}), 201)
    assert job['status'] == 'QUEUED' and provider.requests == []
    path = e.base + '/jobs/video/' + job['id']
    running = checked(e.client.post(path + '/execute', headers=e.headers, json=action(job)))
    assert len(provider.requests) == 1
    request = provider.requests[0]
    assert request.start_frame.startswith('data:image/png;base64,')
    assert request.end_frame.startswith('data:image/png;base64,')
    assert request.start_frame != request.end_frame
    assert base64.b64decode(request.start_frame.split(',', 1)[1]) == png_bytes(b'\x11\x22\x33')
    assert base64.b64decode(request.end_frame.split(',', 1)[1]) == png_bytes(b'\x44\x55\x66')
    assert request.frame_bindings == (
        {'role': 'FIRST', 'id': first['id'], 'version': first['version'], 'digest': first['sha256'], 'order': 0},
        {'role': 'LAST', 'id': last['id'], 'version': last['version'], 'digest': last['sha256'], 'order': 1},
    )
    assert running['status'] == 'AWAITING_REVIEW'
    candidate = running['output_candidate']
    assert candidate['kind'] == 'video'
    approved = checked(e.client.post(path + '/review', headers=e.headers,
        json={**action(running), 'reviewed_output_digest': candidate['digest']}))
    assert approved['status'] == 'APPROVED' and approved['approved_asset_version'] == 2
    stored = checked(e.client.get(e.studio_base + '/assets/' + candidate['id'], headers=e.headers))
    assert stored['sha256'] == candidate['digest'] and stored['media_type'] == 'video/webm'
    reopened = checked(e.client.get(path, headers=e.headers))
    assert reopened['status'] == 'APPROVED'
    assert [source['id'] for source in reopened['sources']] == [first['id'], last['id']]
    # A repeated explicit execute cannot dispatch the already-advanced job again.
    repeated = e.client.post(path + '/execute', headers=e.headers, json=action(job))
    assert repeated.status_code in {409, 422}
    assert len(provider.requests) == 1


def test_mounted_unsupported_adapter_rejects_last_frame_before_any_send(image_client):
    e = image_client
    provider = FrameProvider(b'not-used', end_frame=False)
    configure(e, provider)
    first = upload(e, b'\x11\x22\x33', 'unsupported-first')
    last = upload(e, b'\x44\x55\x66', 'unsupported-last')
    preview = e.client.post(e.base + '/preview', headers=e.headers, json=command(provider, [first, last]))
    assert preview.status_code == 422
    assert 'STUDIO_VIDEO_END_FRAME_UNSUPPORTED' in preview.text
    assert provider.requests == []
    # A two-asset command without explicit roles is rejected, never treated as single image.
    missing_roles = command(provider, [first, last], frames=False)
    preview = e.client.post(e.base + '/preview', headers=e.headers, json=missing_roles)
    assert preview.status_code == 422
    assert 'STUDIO_VIDEO_FRAME_COUNT_REQUIRED' in preview.text
    # Frames are only valid for image-to-video.
    wrong_operation = command(provider, [first, last], operation='m7.video.t2v')
    preview = e.client.post(e.base + '/preview', headers=e.headers, json=wrong_operation)
    assert preview.status_code == 422
    assert provider.requests == []


def test_mounted_single_first_frame_stays_backward_compatible(image_client, tmp_path):
    e = image_client
    provider = FrameProvider(cpu_video(tmp_path))
    configure(e, provider)
    first = upload(e, b'\x11\x22\x33', 'single-first')
    value = command(provider, [first, first], frames=False)
    value['source_snapshots'] = value['source_snapshots'][:1]
    preview = checked(e.client.post(e.base + '/preview', headers=e.headers, json=value))
    assert 'video_frames' not in preview['command']
    job = checked(e.client.post(e.base + '/jobs', headers=e.headers,
        json={'command': value, 'reviewed_preview_digest': preview['preview_digest']}), 201)
    checked(e.client.post(e.base + '/jobs/video/' + job['id'] + '/execute', headers=e.headers, json=action(job)))
    assert provider.requests[0].start_frame.startswith('data:image/png;base64,')
    assert provider.requests[0].end_frame == ''
    assert provider.requests[0].frame_bindings == ()


class UnknownAfterDispatchProvider(FrameProvider):
    def generate(self, request):
        self.requests.append(request)
        if request.dispatch_guard is not None: request.dispatch_guard()
        raise RuntimeError('synthetic transport failure after dispatch guard')


def test_mounted_source_change_before_execute_never_dispatches(image_client, tmp_path):
    e = image_client
    provider = FrameProvider(cpu_video(tmp_path))
    configure(e, provider)
    first = upload(e, b'\x11\x22\x33', 'stale-first')
    last = upload(e, b'\x44\x55\x66', 'stale-last')
    value = command(provider, [first, last])
    preview = checked(e.client.post(e.base + '/preview', headers=e.headers, json=value))
    job = checked(e.client.post(e.base + '/jobs', headers=e.headers,
        json={'command': value, 'reviewed_preview_digest': preview['preview_digest']}), 201)
    changed = e.client.put(e.studio_base + '/assets/' + first['id'] + '/lineage', headers=e.headers,
        json={'expected_version': first['version'], 'origin': 'EXTERNAL_IMPORT', 'license': {'label': 'Synthetic'}})
    assert changed.status_code == 200, changed.text
    response = e.client.post(e.base + '/jobs/video/' + job['id'] + '/execute', headers=e.headers, json=action(job))
    assert response.status_code in {409, 422}
    assert provider.requests == []
    assert checked(e.client.get(e.base + '/jobs/video/' + job['id'], headers=e.headers))['status'] == 'QUEUED'


def test_mounted_revoked_host_before_execute_never_dispatches(image_client, tmp_path):
    e = image_client
    provider = FrameProvider(cpu_video(tmp_path))
    configure(e, provider)
    first = upload(e, b'\x11\x22\x33', 'revoked-first')
    last = upload(e, b'\x44\x55\x66', 'revoked-last')
    value = command(provider, [first, last])
    preview = checked(e.client.post(e.base + '/preview', headers=e.headers, json=value))
    job = checked(e.client.post(e.base + '/jobs', headers=e.headers,
        json={'command': value, 'reviewed_preview_digest': preview['preview_digest']}), 201)
    e.sessions.revoke(e.host)
    response = e.client.post(e.base + '/jobs/video/' + job['id'] + '/execute', headers=e.headers, json=action(job))
    assert response.status_code in {401, 403, 404}
    assert provider.requests == []


def test_mounted_unknown_submission_never_replays_automatically(image_client, tmp_path):
    e = image_client
    provider = UnknownAfterDispatchProvider(cpu_video(tmp_path))
    configure(e, provider)
    first = upload(e, b'\x11\x22\x33', 'unknown-first')
    last = upload(e, b'\x44\x55\x66', 'unknown-last')
    value = command(provider, [first, last])
    preview = checked(e.client.post(e.base + '/preview', headers=e.headers, json=value))
    job = checked(e.client.post(e.base + '/jobs', headers=e.headers,
        json={'command': value, 'reviewed_preview_digest': preview['preview_digest']}), 201)
    path = e.base + '/jobs/video/' + job['id']
    with pytest.raises(RuntimeError, match='synthetic transport failure'):
        e.client.post(path + '/execute', headers=e.headers, json=action(job))
    assert len(provider.requests) == 1
    current = checked(e.client.get(path, headers=e.headers))
    assert current['status'] == 'UNKNOWN'
    again = e.client.post(path + '/execute', headers=e.headers, json=action(current))
    assert again.status_code in {409, 422}
    assert len(provider.requests) == 1


def test_mounted_cross_project_asset_cannot_be_used_as_a_frame(image_client, tmp_path):
    e = image_client
    provider = FrameProvider(cpu_video(tmp_path))
    configure(e, provider)
    first = upload(e, b'\x11\x22\x33', 'cross-project-first')
    other = checked(e.client.post(e.prefix + '/experimental/projects', json={
        'title': 'Other video project', 'id': 'cross-project-' + uuid4().hex}), 201)
    other_base = e.prefix + '/projects/' + other['id'] + '/studio'
    body = {'filename': 'other.png', 'kind': 'image', 'content_base64': base64.b64encode(png_bytes(b'\x44\x55\x66')).decode(),
            'idempotency_key': 'cross-project-other'}
    foreign = checked(e.client.post(other_base + '/assets', headers=e.headers, json=body), 201)
    value = command(provider, [first, foreign])
    response = e.client.post(e.base + '/preview', headers=e.headers, json=value)
    assert response.status_code in {403, 404, 409, 422}, response.text
    assert provider.requests == []
