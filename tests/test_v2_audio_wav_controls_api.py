"""Mounted original audio trim API, real PCM processing and trusted Host fences."""
from copy import deepcopy
import hashlib
import json
import os
from uuid import uuid4

import pytest

from app.actor_context import SessionContext
from app.services.image_job_service import ImageJobService
from test_r3_mounted_contracts import checked, mounted, prefix, scoped
from test_v2_independent_workspace_api import client
from test_v2_independent_workspace import upload
from test_v2_audio_wav_controls import NoControl, command, snapshot, wav_bytes


@pytest.fixture
def audio_client(client, monkeypatch):
    e = client
    e.host = 'audio-wav-host-' + uuid4().hex
    e.session = SessionContext('session-' + e.host, 'client-' + e.host, 'audio-author', 'audio-workspace')
    e.sessions.register(e.host, e.session); e.headers = {'X-Session-Token': e.host}
    checked(e.client.post(e.studio_base + '/activate', headers=e.headers))
    e.source = checked(e.client.post(e.studio_base + '/assets', headers=e.headers,
        json=upload(wav_bytes(), kind='audio', filename='owned-fixture.wav')), 201)
    e.production = e.experimental.studio_production_service
    for name, value in (('workspace', e.studio), ('store', e.studio.store), ('audio_store', e.audio),
        ('image_jobs', ImageJobService(e.root)), ('image_registry', NoControl()), ('vault', NoControl()), ('transport', NoControl())):
        monkeypatch.setattr(e.production, name, value)
    e.base = e.studio_base + '/production'
    e.command = command(snapshot(e.source), gain_db=-6.020599913279624, sample_rate=22050, channels=1)
    return e


def preview(e): return e.client.post(e.base + '/preview', headers=e.headers, json=e.command)


def queue(e):
    captured = checked(preview(e))
    return captured, checked(e.client.post(e.base + '/jobs', headers=e.headers,
        json={'command': e.command, 'reviewed_preview_digest': captured['preview_digest']}), 201)


def action(row): return {'expected_version': row['version'], 'expected_request_digest': row['request_digest']}


def run(e, row): return e.client.post(e.base + '/jobs/audio/' + row['id'] + '/execute', headers=e.headers, json=action(row))


def test_mounted_real_pcm_proof_private_candidate_explicit_review_and_fixture(audio_client, tmp_path):
    e = audio_client; captured, queued = queue(e)
    executed = checked(run(e, queued)); assert executed['status'] == 'AWAITING_REVIEW', executed
    asset = executed['output_candidate']; measurement = executed['media_measurement']
    assert measurement['sample_rate'] == 22050 and measurement['channels'] == 1 and measurement['duration_ms'] == 700
    assert measurement['output_sha256'] == asset['digest'] and measurement['profile_validation'] == 'PCM_DECODED'
    assert e.client.get(e.studio_base + '/assets/' + asset['id'], headers=e.headers).status_code == 404
    downloaded = e.client.get(e.base + '/jobs/audio/' + queued['id'] + '/candidate', headers=e.headers)
    assert downloaded.status_code == 200 and downloaded.headers['content-type'].startswith('audio/wav')
    assert hashlib.sha256(downloaded.content).hexdigest() == measurement['output_sha256'] == downloaded.headers['x-asset-sha256']
    assert len(downloaded.content) == measurement['byte_count']
    approved = checked(e.client.post(e.base + '/jobs/audio/' + queued['id'] + '/review', headers=e.headers,
        json={**action(executed), 'reviewed_output_digest': asset['digest']}))
    assert approved['status'] == 'APPROVED' and approved['media_measurement'] == measurement
    assert checked(e.client.get(e.studio_base + '/assets/' + asset['id'], headers=e.headers))['provenance']['origin'] == 'DERIVED_PROCESSING'
    assert checked(e.client.get(e.base + '/jobs/audio/' + queued['id'], headers=e.headers)) == approved
    if os.environ.get('STUDIO_CAPTURE_AUDIO_WAV') == '1':
        fixture = {'command': e.command, 'source': e.source, 'preview': captured, 'queued': queued, 'executed': executed, 'approved': approved}
        # Response-only evidence: no Host token, private paths, queue or environment.
        (tmp_path / 'audio-wav-response.json').write_text(json.dumps(fixture))
    for response in (preview(e), downloaded):
        assert response.headers['cache-control'] == 'no-store' and response.headers['x-content-type-options'] == 'nosniff'


@pytest.mark.parametrize('change', ['missing', 'forged', 'origin', 'forwarded', 'feature', 'acceptance'])
def test_host_features_and_v1_acceptance_remain_fail_closed(audio_client, monkeypatch, change):
    e = audio_client
    if change == 'missing': e.headers = {}
    elif change == 'forged': e.headers = {'X-Session-Token': 'forged'}
    elif change == 'origin': e.headers = {**e.headers, 'Origin': 'https://untrusted.invalid'}
    elif change == 'forwarded': e.headers = {**e.headers, 'Forwarded': 'for=127.0.0.1'}
    elif change == 'feature': monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    else: monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    response = preview(e)
    assert response.status_code in {401, 403, 404}, response.text
    assert len(list(e.assets.root.glob('*.bin'))) == 1


@pytest.mark.parametrize('change', ['revoke', 'aba', 'rebind'])
def test_actual_native_completion_does_not_bypass_late_host_revocation(audio_client, monkeypatch, change):
    e = audio_client; _, queued = queue(e)
    import app.services.studio_timeline_export as native
    original = native.run_guarded_process
    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        e.sessions.revoke(e.host)
        if change == 'aba': e.sessions.register(e.host, e.session)
        elif change == 'rebind': e.sessions.register(e.host, SessionContext('other', 'other', 'other', 'other'))
        return result
    monkeypatch.setattr(native, 'run_guarded_process', changed)
    response = run(e, queued)
    assert response.status_code in {401, 403, 404}, response.text
    assert len(list(e.assets.root.glob('*.bin'))) == 1


def test_pcm_capacity_and_unknown_controls_are_structured_errors(audio_client):
    e = audio_client
    e.command['parameters'] = {'in_ms': 0, 'out_ms': 120000, 'sample_rate': 96000, 'channels': 2}
    result = preview(e)
    assert result.status_code == 400 and result.json()['detail']['code'] == 'STUDIO_AUDIO_TRIM_BYTES_BUDGET_EXCEEDED'
    for parameters in ({'gain_db': 13}, {'sample_rate': 48000.0}, {'channels': True}, {'normalize': True}, {'codec': 'flac'}):
        e.command['parameters'] = {'in_ms': 100, 'out_ms': 800, **parameters}
        assert preview(e).status_code == 422
    assert len(list(e.assets.root.glob('*.bin'))) == 1
