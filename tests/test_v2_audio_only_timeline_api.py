"""Actual mounted audio-only timeline routes, original Host and File/PG owners."""
import hashlib
import io
import wave

import pytest

from app.creative.graph_asset_inputs import GraphAssetInputs
from app.services.video_assembly_service import VideoAssemblyService
from test_r3_mounted_contracts import checked, mounted, prefix, scoped
from test_v2_independent_workspace_api import client
from test_v2_independent_workspace import upload
from test_v2_audio_wav_controls_api import audio_client, action
from test_v2_audio_only_timeline import tone, timeline, PROFILE


@pytest.fixture
def audio_mix_client(audio_client, monkeypatch):
    e = audio_client
    monkeypatch.setattr(e.production, 'video_owner', VideoAssemblyService(e.root, e.assets))
    monkeypatch.setattr(e.production, 'timeline_inputs', GraphAssetInputs(e.production))
    assets = [checked(e.client.post(e.studio_base + '/assets', headers=e.headers,
        json=upload(tone(hz), kind='audio', filename=f'author-{hz}.wav')), 201) for hz in (440, 880)]
    e.saved = checked(e.client.post(e.base + '/timelines', headers=e.headers, json={
        'expected_version': 0, 'title': 'Mounted independent audio mix', 'timeline': timeline(*assets)}), 201)
    e.timeline_base = e.base + '/timelines/' + e.saved['id']
    e.reviewed = {'expected_version': e.saved['version'], 'reviewed_timeline_digest': e.saved['timeline_digest']}
    return e


def test_audio_http_explicit_preview_build_attest_review_download(audio_mix_client):
    e = audio_mix_client
    assert checked(e.client.get(e.timeline_base, headers=e.headers)) == e.saved
    preview = checked(e.client.post(e.timeline_base + '/playback-preview', headers=e.headers, json=e.reviewed))
    assert preview['cache_state'] == 'MISSING' and preview['export_preview']['export_profile'] == PROFILE
    assert checked(e.client.get(e.base + '/jobs', headers=e.headers))['items'] == []
    built = checked(e.client.post(e.timeline_base + '/playback-build', headers=e.headers,
        json={**e.reviewed, 'reviewed_playback_digest': preview['playback_digest']}))
    job = built['job']; assert job['status'] == 'SUCCEEDED', job
    candidate = job['output_candidate']; assert candidate['kind'] == 'audio'
    job_base = e.base + '/jobs/timeline/' + job['id']
    response = e.client.get(job_base + '/candidate', headers=e.headers)
    assert response.status_code == 200 and response.headers['content-type'].startswith('audio/wav')
    assert response.headers['cache-control'] == 'no-store' and response.headers['x-content-type-options'] == 'nosniff'
    assert response.headers['x-asset-sha256'] == candidate['digest'] == hashlib.sha256(response.content).hexdigest()
    with wave.open(io.BytesIO(response.content), 'rb') as wav:
        assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth(), wav.getnframes()) == (48000, 2, 2, 96000)
    assert e.client.get(e.studio_base + '/assets/' + candidate['id'], headers=e.headers).status_code == 404
    attested = checked(e.client.post(e.timeline_base + '/playback-attestation', headers=e.headers, json={
        **e.reviewed, 'reviewed_playback_digest': preview['playback_digest'],
        'expected_job_version': job['version'], 'expected_request_digest': job['request_digest']}))
    assert attested['media_type'] == 'audio/wav'
    approved = checked(e.client.post(job_base + '/review', headers=e.headers,
        json={**action(job), 'reviewed_output_digest': candidate['digest']}))
    assert approved['status'] == 'APPROVED'
    download = e.client.get(e.studio_base + '/assets/' + candidate['id'] + '/download', headers=e.headers)
    assert download.status_code == 200 and download.content == response.content
    assert '.wav' in download.headers['content-disposition']


@pytest.mark.parametrize('change', ['missing', 'forged', 'revoke', 'origin', 'feature'])
def test_audio_http_host_authority_remains_fail_closed(audio_mix_client, monkeypatch, change):
    e = audio_mix_client
    if change == 'missing': e.headers = {}
    elif change == 'forged': e.headers = {'X-Session-Token': 'forged-audio-timeline'}
    elif change == 'revoke': e.sessions.revoke(e.host)
    elif change == 'origin': e.headers = {**e.headers, 'Origin': 'https://untrusted.invalid'}
    else: monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    response = e.client.post(e.timeline_base + '/playback-preview', headers=e.headers, json=e.reviewed)
    assert response.status_code in {401, 403, 404}, response.text
    assert len(list(e.assets.root.glob('*.bin'))) == 3


def test_audio_http_rejects_video_profile_and_capacity_before_job(audio_mix_client):
    e = audio_mix_client
    response = e.client.post(e.timeline_base + '/export-preview', headers=e.headers,
        json={**e.reviewed, 'export_profile': {'preset': 'REVIEW_MP4'}})
    assert response.status_code == 422 and response.json()['detail']['code'] == 'EXPERIMENTAL_INVALID'
    definition = e.saved['timeline'].copy(); definition['duration_ms'] = 600000
    row = checked(e.client.put(e.timeline_base, headers=e.headers, json={
        'expected_version': e.saved['version'], 'title': e.saved['title'], 'timeline': definition}))
    response = e.client.post(e.timeline_base + '/export-preview', headers=e.headers, json={
        'expected_version': row['version'], 'reviewed_timeline_digest': row['timeline_digest'], 'export_profile': PROFILE})
    assert response.status_code == 422 and response.json()['detail']['code'] == 'EXPERIMENTAL_INVALID'
    assert checked(e.client.get(e.base + '/jobs', headers=e.headers))['items'] == []
