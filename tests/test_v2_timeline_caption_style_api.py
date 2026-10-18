"""Mounted original caption styling/export routes, real File/PG owners."""
import hashlib

import pytest

from app.creative.graph_asset_inputs import GraphAssetInputs
from app.services.video_assembly_service import VideoAssemblyService
from test_r3_mounted_contracts import checked, mounted, prefix, scoped
from test_v2_independent_workspace_api import client
from test_v2_independent_workspace import upload
from test_v2_audio_wav_controls_api import audio_client, action
from test_v2_audio_editing_pipeline import source, edit_body, cpu_video
from test_v2_timeline_caption_style import timeline, change, reviewed, decode, STYLE


@pytest.fixture
def caption_client(audio_client, monkeypatch, tmp_path):
    e = audio_client
    monkeypatch.setattr(e.production, 'video_owner', VideoAssemblyService(e.root, e.assets))
    monkeypatch.setattr(e.production, 'timeline_inputs', GraphAssetInputs(e.production))
    video = checked(e.client.post(e.studio_base + '/assets', headers=e.headers,
        json=upload(cpu_video(tmp_path / 'blue.mp4'), kind='video', filename='blue.mp4')), 201)
    e.saved = checked(e.client.post(e.base + '/timelines', headers=e.headers,
        json={'expected_version': 0, 'title': 'Mounted caption style', 'timeline': timeline(source(video))}), 201)
    e.timeline_base = e.base + '/timelines/' + e.saved['id']
    return e


def test_style_http_closed_edit_export_private_review_download(caption_client, tmp_path):
    e = caption_client
    assert e.client.post(e.timeline_base + '/edit', json=edit_body(e.saved, change(STYLE))).status_code == 401
    for invalid in ({**STYLE, 'font_size': True}, {**STYLE, 'font_name': '/host/file'}, {**STYLE, 'primary_color': "#FFFFFF';movie=/etc/passwd"}):
        result = e.client.post(e.timeline_base + '/edit', headers=e.headers, json=edit_body(e.saved, change(invalid)))
        assert result.status_code == 422 and checked(e.client.get(e.timeline_base, headers=e.headers)) == e.saved
    body = edit_body(e.saved, change(STYLE), 'style-http-edit')
    edited = checked(e.client.post(e.timeline_base + '/edit', headers=e.headers, json=body))
    assert checked(e.client.post(e.timeline_base + '/edit', headers=e.headers, json=body)) == edited
    assert edited['timeline']['caption_style'] == STYLE
    assert e.client.post(e.timeline_base + '/edit', headers=e.headers, json=edit_body(e.saved, change(None), 'stale')).status_code == 409
    profile = {'preset': 'DELIVERY_H264_MP4'}
    preview = checked(e.client.post(e.timeline_base + '/export-preview', headers=e.headers, json={**reviewed(edited), 'export_profile': profile}))
    assert preview['execution_recipe']['timeline']['caption_style'] == STYLE
    assert not checked(e.client.get(e.base + '/jobs', headers=e.headers))['items']
    job = checked(e.client.post(e.timeline_base + '/export', headers=e.headers, json={**reviewed(edited), 'export_profile': profile, 'reviewed_export_digest': preview['preview_digest'], 'request_id': 'style-http-export'}))
    assert job['status'] == 'SUCCEEDED', job
    candidate = job['output_candidate']; job_base = e.base + '/jobs/timeline/' + job['id']
    assert e.client.get(e.studio_base + '/assets/' + candidate['id'], headers=e.headers).status_code == 404
    result = e.client.get(job_base + '/candidate', headers=e.headers)
    assert result.status_code == 200 and result.headers['content-type'].startswith('video/mp4')
    assert result.headers['cache-control'] == 'no-store' and result.headers['x-content-type-options'] == 'nosniff'
    assert result.headers['x-asset-sha256'] == hashlib.sha256(result.content).hexdigest() == candidate['digest']
    proof = decode(result.content, tmp_path / 'style-delivery.mp4'); assert proof['frames']['5']['red_pixels'] > 10
    assert checked(e.client.post(job_base + '/review', headers=e.headers, json={**action(job), 'reviewed_output_digest': candidate['digest']}))['status'] == 'APPROVED'
    download = e.client.get(e.studio_base + '/assets/' + candidate['id'] + '/download', headers=e.headers)
    assert download.status_code == 200 and download.content == result.content
    assert checked(e.client.get(e.timeline_base, headers=e.headers)) == edited
    e.sessions.revoke(e.host)
    assert e.client.post(e.timeline_base + '/export-preview', headers=e.headers, json={**reviewed(edited), 'export_profile': profile}).status_code == 401
