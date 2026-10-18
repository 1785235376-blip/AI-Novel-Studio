"""Mounted color edit/export routes on actual File/PG owners and CPU media."""
from copy import deepcopy
import hashlib

import pytest

from app.creative.graph_asset_inputs import GraphAssetInputs
from app.services.video_assembly_service import VideoAssemblyService
from test_r3_mounted_contracts import checked, mounted, prefix, scoped
from test_v2_independent_workspace_api import client
from test_v2_independent_workspace import upload
from test_v2_audio_wav_controls_api import audio_client, action
from test_v2_audio_editing_pipeline import source, edit_body
from test_v2_timeline_basic_color import pixels_png, timeline, change, clip, reviewed, decode, ADJUSTED, NEUTRAL


@pytest.fixture
def color_client(audio_client, monkeypatch):
    e = audio_client
    monkeypatch.setattr(e.production, 'video_owner', VideoAssemblyService(e.root, e.assets))
    monkeypatch.setattr(e.production, 'timeline_inputs', GraphAssetInputs(e.production))
    image = checked(e.client.post(e.studio_base + '/assets', headers=e.headers,
        json=upload(pixels_png(), kind='image', filename='author-swatches.png')), 201)
    e.saved = checked(e.client.post(e.base + '/timelines', headers=e.headers,
        json={'expected_version': 0, 'title': 'Mounted basic color', 'timeline': timeline(source(image))}), 201)
    e.timeline_base = e.base + '/timelines/' + e.saved['id']
    return e


def test_color_http_exact_edit_closed_fields_cas_export_review_and_download(color_client, tmp_path):
    e = color_client
    assert e.client.post(e.timeline_base + '/edit', json=edit_body(e.saved, change(ADJUSTED))).status_code == 401
    for invalid in ({**NEUTRAL, 'brightness': 2}, {**NEUTRAL, 'lut': '/host/path.cube'}, {**NEUTRAL, 'contrast': True}):
        response = e.client.post(e.timeline_base + '/edit', headers=e.headers, json=edit_body(e.saved, change(invalid)))
        assert response.status_code == 422 and response.json()['detail']['code'] == 'EXPERIMENTAL_INVALID'
        assert checked(e.client.get(e.timeline_base, headers=e.headers)) == e.saved
    body = edit_body(e.saved, change(ADJUSTED), 'color-http-edit')
    edited = checked(e.client.post(e.timeline_base + '/edit', headers=e.headers, json=body))
    assert checked(e.client.get(e.timeline_base, headers=e.headers)) == edited
    assert checked(e.client.post(e.timeline_base + '/edit', headers=e.headers, json=body)) == edited
    assert clip(edited['timeline'])['color_adjustment'] == ADJUSTED
    stale = e.client.post(e.timeline_base + '/edit', headers=e.headers, json=edit_body(e.saved, change(None), 'stale'))
    assert stale.status_code == 409
    profile = {'preset': 'DELIVERY_H264_MP4'}
    preview = checked(e.client.post(e.timeline_base + '/export-preview', headers=e.headers, json={**reviewed(edited), 'export_profile': profile}))
    assert clip(preview['execution_recipe']['timeline'])['color_adjustment'] == ADJUSTED
    assert not checked(e.client.get(e.base + '/jobs', headers=e.headers))['items']
    job = checked(e.client.post(e.timeline_base + '/export', headers=e.headers, json={**reviewed(edited), 'export_profile': profile, 'reviewed_export_digest': preview['preview_digest'], 'request_id': 'color-http-export'}))
    assert job['status'] == 'SUCCEEDED', job
    candidate = job['output_candidate']; job_base = e.base + '/jobs/timeline/' + job['id']
    assert e.client.get(e.studio_base + '/assets/' + candidate['id'], headers=e.headers).status_code == 404
    result = e.client.get(job_base + '/candidate', headers=e.headers)
    assert result.status_code == 200 and result.headers['content-type'].startswith('video/mp4')
    assert result.headers['cache-control'] == 'no-store' and result.headers['x-content-type-options'] == 'nosniff'
    assert result.headers['x-asset-sha256'] == hashlib.sha256(result.content).hexdigest() == candidate['digest']
    proof = decode(result.content, tmp_path / 'color-delivery.mp4')
    assert all(max(rgb) - min(rgb) <= 6 for rgb in proof['rgb_samples'])
    approved = checked(e.client.post(job_base + '/review', headers=e.headers, json={**action(job), 'reviewed_output_digest': candidate['digest']}))
    assert approved['status'] == 'APPROVED'
    download = e.client.get(e.studio_base + '/assets/' + candidate['id'] + '/download', headers=e.headers)
    assert download.status_code == 200 and download.content == result.content
    assert checked(e.client.get(e.timeline_base, headers=e.headers)) == edited
    e.sessions.revoke(e.host)
    assert e.client.post(e.timeline_base + '/export-preview', headers=e.headers, json={**reviewed(edited), 'export_profile': profile}).status_code == 401
