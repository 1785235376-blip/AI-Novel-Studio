"""Minimal real product mount smoke, original File + trusted Host invoker.

The author's module suite is not repeated. Permission denials are injected at
the original resolver boundary, not asserted as real collaboration-role proof.
"""
import base64
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.actor_context import SessionContext
from app.audio_production_store import AudioProductionStore
from app.services.image_job_service import ImageJobService
from app.services.video_assembly_service import VideoAssemblyService
from test_r3_mounted_contracts import checked, mounted, prefix
from test_v2_independent_workspace_api import client
from test_v2_audio_editing_pipeline import audible_wav, source
from test_v2_audio_wav_controls import NoControl


@pytest.fixture
def audio(client, monkeypatch):
    e = client
    e.host = 'manifest-mount-' + uuid4().hex
    e.sessions.register(e.host, SessionContext(e.host, e.host, 'fixture-author', 'fixture-workspace'))
    e.headers = {'X-Session-Token': e.host}
    checked(e.client.post(e.studio_base + '/activate', headers=e.headers))
    e.production = e.experimental.studio_production_service
    for name, value in (('workspace', e.studio), ('store', e.studio.store), ('image_jobs', ImageJobService(e.root)),
            ('audio_store', AudioProductionStore(e.root / 'audio-production')), ('image_registry', NoControl()),
            ('video_owner', VideoAssemblyService(e.root, e.assets)), ('vault', NoControl()), ('transport', NoControl())):
        monkeypatch.setattr(e.production, name, value)
    with e.studio._asset_scope(e.nid, e.scope):
        e.audio_source = e.assets.create(e.nid, 'owned-fixture.wav', base64.b64encode(audible_wav()).decode(),
            'audio/wav', 'audio', 'manifest-mount-source', required_features=('narrative_production_v2',))
    command = {'operation_id': 'm8.audio.trim', 'request_id': 'manifest-mount-trim', 'provider_id': None,
        'model_id': None, 'prompt': '', 'parameters': {'in_ms': 100, 'out_ms': 900},
        'allow_cloud': False, 'license_note': 'synthetic owned audio', 'source_snapshots': [source(e.audio_source)]}
    base = e.studio_base + '/production'
    captured = checked(e.client.post(base + '/preview', headers=e.headers, json=command))
    job = checked(e.client.post(base + '/jobs', headers=e.headers,
        json={'command': command, 'reviewed_preview_digest': captured['preview_digest']}), 201)
    def action(j): return {'expected_version': j['version'], 'expected_request_digest': j['request_digest']}
    job = checked(e.client.post(base + '/jobs/audio/' + job['id'] + '/execute', headers=e.headers, json=action(job)))
    e.job = checked(e.client.post(base + '/jobs/audio/' + job['id'] + '/review', headers=e.headers,
        json={**action(job), 'reviewed_output_digest': job['output_candidate']['digest']}))
    e.manifest_base = e.prefix + f'/novels/{e.nid}/experimental/production/audio-manifests'
    e.authorize = e.api._workbench_authorize
    return e


def test_actual_product_mount_read_record_reopen_and_export(audio):
    e = audio
    results = checked(e.client.get(e.manifest_base + '/results', headers=e.headers))
    assert results['items'][0]['id'] == e.job['id']
    preview = checked(e.client.get(e.manifest_base + '/results/' + e.job['id'], headers=e.headers))
    body = {'job_id': e.job['id'], 'expected_job_version': e.job['version'],
        'reviewed_capture_digest': preview['capture_digest'], 'request_id': 'mount-manifest-record', 'confirmed': True}
    row = checked(e.client.post(e.manifest_base, headers=e.headers, json=body), 201)
    exported = e.client.get(e.manifest_base + '/' + row['id'] + '/export', headers=e.headers)
    assert exported.status_code == 200 and exported.json() == row and exported.headers['cache-control'] == 'no-store'
    assert checked(e.client.get(e.manifest_base + '/' + row['id'], headers=e.headers)) == row
    assert row['replayable'] is False


@pytest.mark.parametrize('permission', ['domain.read', 'domain.write'])
def test_mounted_record_rechecks_both_original_permissions(audio, monkeypatch, permission):
    e = audio
    captured = checked(e.client.get(e.manifest_base + '/results/' + e.job['id'], headers=e.headers))
    seen = []
    def denied(nid, token, branch, requested):
        seen.append(requested)
        if requested == permission: raise HTTPException(403, {'code': 'TEST_ORIGINAL_OWNER_DENIED'})
        return e.authorize(nid, token, branch, requested)
    monkeypatch.setattr(e.api, '_workbench_authorize', denied)
    response = e.client.post(e.manifest_base, headers=e.headers, json={'job_id': e.job['id'],
        'expected_job_version': e.job['version'], 'reviewed_capture_digest': captured['capture_digest'],
        'request_id': 'denied-record', 'confirmed': True})
    assert response.status_code == 403 and permission in seen
    if permission == 'domain.write': assert 'domain.read' in seen


@pytest.mark.parametrize('change', ['missing', 'origin', 'revoke'])
def test_mounted_manifest_reads_retain_original_host_boundary(audio, change):
    e = audio
    headers = dict(e.headers)
    if change == 'missing': headers = {}
    elif change == 'origin': headers['Origin'] = 'https://untrusted.invalid'
    else: e.sessions.revoke(e.host)
    assert e.client.get(e.manifest_base + '/results', headers=headers).status_code in {401, 403}
