"""Mounted Phase 5 original Host/File/PG pipeline, synthetic provider/CPU video."""
import json
import os
from pathlib import Path

import pytest

from test_r3_mounted_contracts import checked, mounted, prefix, scoped
from test_v2_independent_workspace_api import client, upload_body
from test_v2_discovered_image_production_api import image_client, action
from test_v2_storyboard_workspace_api import storyboard_client, get_storyboard, shot_action, bind_asset, approve_board
from test_v2_video_runtime_foundation_api import setup, queue


def capture(e, name, value):
    destination = os.getenv('PHASE5_STORYBOARD_CAPTURE')
    if not destination: return
    root = Path(__file__).resolve().parents[1]
    target = Path(destination).resolve()
    assert target.is_relative_to(root / '.runtime')
    target.mkdir(parents=True, exist_ok=True)
    filename = e.store.backend + '-' + e.prefix.strip('/').replace('/', '-') + '-' + name + '.json'
    (target / filename).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


@pytest.mark.parametrize('operation', ['m7.video.t2v', 'm7.video.i2v'])
def test_mounted_complete_shot_video_binding_create_recovery_and_timeline_adoption(storyboard_client, monkeypatch, operation):
    e = storyboard_client; discovery, adapter, wire, command = setup(e, monkeypatch)
    image = checked(e.client.post(e.studio_base + '/assets', headers=e.headers, json=upload_body('phase5-source-image')), 201)
    board = checked(bind_asset(e, get_storyboard(e), image))
    board = approve_board(e, board)
    create_body = {'expected_version': board['document_snapshot']['version'], 'reviewed_content_digest': board['content_digest'],
        'title': 'SYNTHETIC mounted production', 'shot_ids': ['shot-1'], 'request_id': 'mounted-create-phase5'}
    created = checked(e.client.post(e.board_path + '/storyboard/timeline-create', headers=e.headers, json=create_body), 201)
    capture(e, 'timeline-created', created)
    conflict = e.client.post(e.board_path + '/storyboard/timeline-create', headers=e.headers, json={**create_body, 'title': 'different'})
    assert conflict.status_code == 409 and 'IDEMPOTENCY_CONFLICT' in conflict.text
    prepared = checked(e.client.post(e.board_path + '/shots/shot-1/video-request', headers=e.headers, json={
        **shot_action(board), 'operation_id': operation, 'request_id': 'mounted-shot-video-phase5',
        'provider': {'operation_id': operation, 'provider_id': command['provider_id'], 'model_id': command['model_id']},
        'parameters': {'width': 64, 'height': 64, 'frame_rate': 8, 'seed': 7}}))
    capture(e, 'video-request', prepared)
    assert not prepared['automatic_dispatch'] and wire.calls == []
    job = queue(e, prepared['command']); path = e.base + '/jobs/video/' + job['id']
    job = checked(e.client.post(path + '/execute', headers=e.headers, json=action(job)))
    ready = checked(e.client.post(path + '/refresh', headers=e.headers, json=action(job)))
    rejected = e.client.post(e.board_path + '/shots/shot-1/video-binding', headers=e.headers, json={**shot_action(board),
        'asset': {'asset_id': ready['output_candidate']['id'], 'version': ready['output_candidate']['version'],
                  'digest': ready['output_candidate']['digest'], 'kind': 'video'},
        'video_job': {key: ready[key] for key in ('id', 'version', 'request_digest', 'receipt_digest')}})
    assert rejected.status_code == 409
    job = checked(e.client.post(path + '/review', headers=e.headers, json={
        **action(ready), 'reviewed_output_digest': ready['output_candidate']['digest']}))
    capture(e, 'video-approved', job)
    asset = {'asset_id': job['output_candidate']['id'], 'version': job['approved_asset_version'],
             'digest': job['output_candidate']['digest'], 'kind': 'video'}
    job_pin = {key: job[key] for key in ('id', 'version', 'request_digest', 'receipt_digest')}
    bound = checked(e.client.post(e.board_path + '/shots/shot-1/video-binding', headers=e.headers, json={
        **shot_action(board), 'asset': asset, 'video_job': job_pin}))
    capture(e, 'storyboard-video-bound', bound)
    assert not bound['approved'] and bound['shots'][0]['video_result']['source_shot'] == prepared['shot_pin']
    board = approve_board(e, bound)
    capture(e, 'storyboard-video-approved', board)
    timeline = created['timeline']
    adopted = checked(e.client.post(e.board_path + '/shots/shot-1/timelines/' + timeline['id'] + '/video-adoption',
        headers=e.headers, json={**shot_action(board), 'expected_timeline_version': timeline['version'],
            'reviewed_timeline_digest': timeline['timeline_digest'], 'request_id': 'mounted-adopt-phase5',
            'clip_id': 'storyboard-1', 'video_asset': asset, 'video_job': job_pin, 'in_ms': 0, 'out_ms': 500, 'include_audio': False}))
    capture(e, 'video-adopted', adopted)
    assert adopted['timeline']['version'] == 2 and adopted['timeline']['timeline']['tracks'][0]['clips'][0]['source_snapshot']['id'] == asset['asset_id']
    recovered = checked(e.client.get(e.board_path + '/storyboard/timeline-creations/' + create_body['request_id'], headers=e.headers))
    capture(e, 'timeline-recovered', recovered)
    assert recovered['creation_receipt'] == created['creation_receipt'] and recovered['timeline']['version'] == 2
    retry = checked(e.client.post(e.board_path + '/storyboard/timeline-create', headers=e.headers, json=create_body), 201)
    assert retry == recovered
    assert len(checked(e.client.get(e.base + '/timelines', headers=e.headers))['items']) == 1
    assert sum(url.endswith('/prompt') for url, _ in wire.calls) == 1 and discovery.center.lifecycle.start.call_count == 0


@pytest.mark.parametrize('fault,status', [('missing', 401), ('forged', 401), ('origin', 403), ('forwarded', 403)])
def test_new_storyboard_actions_keep_original_host_boundary(storyboard_client, fault, status):
    e = storyboard_client; board = get_storyboard(e)
    headers = {} if fault == 'missing' else {'X-Session-Token': 'forged'} if fault == 'forged' else (
        {**e.headers, 'Origin': 'https://untrusted.invalid'} if fault == 'origin' else {**e.headers, 'Forwarded': 'for=127.0.0.1'})
    pin = {'id': 'untrusted', 'version': 1, 'request_digest': '0' * 64, 'receipt_digest': '0' * 64}
    asset = {'asset_id': 'untrusted', 'version': 1, 'digest': '0' * 64, 'kind': 'video'}
    for method, suffix, body in [
        ('POST', '/shots/shot-1/video-request', {**shot_action(board), 'request_id': 'bad-video',
            'provider': {'operation_id': 'm7.video.t2v', 'provider_id': 'none', 'model_id': 'none'}}),
        ('POST', '/shots/shot-1/video-binding', {**shot_action(board), 'asset': asset, 'video_job': pin}),
        ('POST', '/storyboard/timeline-create', {'expected_version': board['document_snapshot']['version'],
            'reviewed_content_digest': board['content_digest'], 'title': 'No save', 'shot_ids': ['shot-1'], 'request_id': 'bad-create'}),
        ('GET', '/storyboard/timeline-creations/bad-create', None),
        ('POST', '/shots/shot-1/timelines/untrusted/video-adoption', {**shot_action(board), 'expected_timeline_version': 1,
            'reviewed_timeline_digest': '0' * 64, 'request_id': 'bad-adopt', 'clip_id': 'clip', 'video_asset': asset,
            'video_job': pin, 'in_ms': 0, 'out_ms': 500, 'include_audio': False}),
    ]:
        response = e.client.request(method, e.board_path + suffix, headers=headers, json=body)
        assert response.status_code == status, response.text
    assert get_storyboard(e) == board
