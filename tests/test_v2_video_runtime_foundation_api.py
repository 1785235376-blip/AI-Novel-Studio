"""Mounted trusted Host and original File/PG API; synthetic video provider only."""
from copy import deepcopy
import json
import os
from pathlib import Path

import pytest

from app.services.video_assembly_service import VideoAssemblyService
from app.services.studio_video_execution import StudioVideoExecution
from test_r3_mounted_contracts import checked, mounted, prefix, scoped
from test_v2_independent_workspace_api import client
from test_v2_discovered_image_production_api import image_client, action, assert_success_private_headers
from test_v2_video_runtime_foundation import enabled, Wire, cpu_video


def capture(e, name, value):
    destination = os.getenv('PHASE4_VIDEO_CAPTURE')
    if not destination: return
    root = Path(__file__).resolve().parents[1]
    target = Path(destination).resolve()
    assert target.is_relative_to(root / '.runtime'), 'capture must remain within the isolated test checkout'
    target.mkdir(parents=True, exist_ok=True)
    # Only already-public original API JSON; no session/header/runtime path or
    # source bytes are added. File and PG profile captures remain separate.
    profile = getattr(e, 'backend', 'profile')
    prefix = e.prefix.replace('/', '-').strip('-')
    (target / f'{profile}-{prefix}-{name}.json').write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def setup(e, monkeypatch):
    original, _, videos, adapter, _ = enabled(e.root)
    owner = VideoAssemblyService(e.root, e.assets)
    monkeypatch.setattr(e.production, 'video_owner', owner)
    monkeypatch.setattr(e.production, 'video', StudioVideoExecution(owner))
    monkeypatch.setattr(e.production, 'video_providers', videos)
    wire = Wire(cpu_video(e.root)); adapter.delegate.transport = wire
    value = {'operation_id': 'm7.video.t2v', 'request_id': 'mounted-synthetic-video',
        'provider_id': adapter.candidate['provider_id'], 'model_id': adapter.candidate['id'], 'prompt': 'SYNTHETIC PRIVATE VIDEO',
        'parameters': {'width': 64, 'height': 64, 'duration_seconds': 1, 'frame_rate': 8, 'seed': 7}}
    return original, adapter, wire, value


def queue(e, value):
    preview_response = e.client.post(e.base + '/preview', headers=e.headers, json=value)
    assert_success_private_headers(preview_response)
    preview = checked(preview_response)
    return checked(e.client.post(e.base + '/jobs', headers=e.headers,
        json={'command': value, 'reviewed_preview_digest': preview['preview_digest']}), 201)


def test_mounted_original_video_task_private_refresh_review(image_client, monkeypatch):
    e = image_client; original, adapter, wire, value = setup(e, monkeypatch)
    before = list(original.client.calls)
    result = checked(e.client.get(e.base + '/providers', headers=e.headers))
    video_rows = [r for r in result['items'] if r['operation_id'].startswith('m7.')]
    assert {r['operation_id'] for r in video_rows} == {'m7.video.t2v', 'm7.video.i2v'}
    assert original.client.calls == before and wire.calls == []
    capture(e, 'providers', result)
    row = queue(e, value); path = e.base + '/jobs/video/' + row['id']
    capture(e, 'job-queued', row)
    preview = checked(e.client.post(e.base + '/preview', headers=e.headers, json=value))
    capture(e, 'preview', preview)
    result = e.client.post(path + '/execute', headers=e.headers, json=action(row))
    assert_success_private_headers(result)
    running = checked(result)
    assert running['status'] == 'REMOTE_RUNNING'
    capture(e, 'job-running', running)
    ready = checked(e.client.post(path + '/refresh', headers=e.headers, json=action(running)))
    assert ready['status'] == 'AWAITING_REVIEW'
    capture(e, 'job-candidate', ready)
    aid = ready['output_candidate']['id']
    assert e.client.get(e.studio_base + '/assets/' + aid, headers=e.headers).status_code == 404
    denied = e.client.post(path + '/review', headers=e.headers, json={**action(ready), 'reviewed_output_digest': '0' * 64})
    assert denied.status_code == 409
    assert 'STUDIO_REVIEW_OUTPUT_CHANGED' in denied.text
    reviewed = checked(e.client.post(path + '/review', headers=e.headers,
        json={**action(ready), 'reviewed_output_digest': ready['output_candidate']['digest']}))
    assert reviewed['status'] == 'APPROVED' and reviewed['approved_asset_version'] == 2
    capture(e, 'job-reviewed', reviewed)
    assert checked(e.client.get(e.studio_base + '/assets/' + aid, headers=e.headers))['media_type'] == 'video/webm'
    assert original.center.lifecycle.start.call_count == 0


@pytest.mark.parametrize('change', ['untrusted', 'disabled', 'wrong_model', 'workflow', 'end_frame', 'reference'])
def test_mounted_video_rejects_untrusted_or_nonclosed_requests_before_send(image_client, monkeypatch, change):
    e = image_client; original, adapter, wire, value = setup(e, monkeypatch)
    headers = e.headers
    if change == 'untrusted': headers = {'X-Session-Token': 'untrusted'}
    elif change == 'disabled': original.disable(adapter.candidate['id'])
    elif change == 'wrong_model': value['model_id'] = 'unconfigured'
    elif change == 'workflow': value['parameters']['workflow'] = {'command': 'unbounded'}
    elif change == 'end_frame': value['end_frame'] = 'unexpected'
    else: value['video_reference'] = {'source': {'id': 'absent', 'version': 1, 'digest': 'a' * 64, 'kind': 'ASSET', 'asset_kind': 'video'}, 'purpose': 'action'}
    result = e.client.post(e.base + '/preview', headers=headers, json=value)
    assert result.status_code == (401 if change == 'untrusted' else 422), result.text
    assert wire.calls == []


def test_mounted_host_revocation_between_dispatch_and_refresh_never_downloads(image_client, monkeypatch):
    e = image_client; _, _, wire, value = setup(e, monkeypatch)
    row = queue(e, value); path = e.base + '/jobs/video/' + row['id']
    running = checked(e.client.post(path + '/execute', headers=e.headers, json=action(row)))
    e.sessions.revoke(e.host)
    before = len(wire.calls)
    response = e.client.post(path + '/refresh', headers=e.headers, json=action(running))
    assert response.status_code in {401, 403, 404}
    assert len(wire.calls) == before
