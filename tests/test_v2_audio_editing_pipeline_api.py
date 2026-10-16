"""Mounted original postproduction API with actual bounded CPU media proof."""
from copy import deepcopy
import hashlib
import json
import os

import pytest

from app.services.video_assembly_service import VideoAssemblyService
from app.creative.graph_asset_inputs import GraphAssetInputs
from test_r3_mounted_contracts import checked, mounted, prefix, scoped
from test_v2_independent_workspace_api import client
from test_v2_independent_workspace import upload
from test_v2_audio_wav_controls_api import audio_client, action, queue, run
from test_v2_audio_editing_pipeline import audible_wav, cpu_video, source, timeline, audio_insert, edit_body, measured_output


@pytest.fixture
def editing_client(audio_client, tmp_path, monkeypatch):
    e = audio_client
    monkeypatch.setattr(e.production, 'video_owner', VideoAssemblyService(e.root, e.assets))
    # The original audio-only fixture patches workspace/store. Timeline input
    # leases capture those owners at construction, so bind the test's real
    # isolated owners rather than retaining the application-global reference.
    monkeypatch.setattr(e.production, 'timeline_inputs', GraphAssetInputs(e.production))
    data = cpu_video(tmp_path / 'api-synthetic-blue.mp4')
    e.video = checked(e.client.post(e.studio_base + '/assets', headers=e.headers,
        json=upload(data, kind='video', filename='synthetic-blue.mp4')), 201)
    e.audible = checked(e.client.post(e.studio_base + '/assets', headers=e.headers,
        json=upload(audible_wav(), kind='audio', filename='synthetic-sine.wav')), 201)
    e.command['source_snapshots'] = [source(e.audible)]
    e.command['parameters'] = {'in_ms': 100, 'out_ms': 900, 'output_format': 'FLAC', 'sample_rate': 22050, 'channels': 1}
    e.created = checked(e.client.post(e.base + '/timelines', headers=e.headers,
        json={'expected_version': 0, 'title': 'SYNTHETIC CPU postproduction', 'timeline': timeline(e.video)}), 201)
    e.timeline_base = e.base + '/timelines/' + e.created['id']
    return e


def formal_audio(e):
    preview, queued = queue(e)
    ready = checked(run(e, queued)); assert ready['status'] == 'AWAITING_REVIEW', ready
    assert e.client.get(e.studio_base + '/assets/' + ready['output_candidate']['id'], headers=e.headers).status_code == 404
    approved = checked(e.client.post(e.base + '/jobs/audio/' + ready['id'] + '/review', headers=e.headers,
        json={**action(ready), 'reviewed_output_digest': ready['output_candidate']['digest']}))
    assert approved['status'] == 'APPROVED' and approved['media_measurement']['container'] == 'flac'
    row = checked(e.client.get(e.studio_base + '/assets/' + ready['output_candidate']['id'], headers=e.headers))
    assert row['version'] == approved['approved_asset_version'] == 2
    return row, {'command': e.command, 'preview': preview, 'queued': queued, 'executed': ready, 'approved': approved}


def test_mounted_flac_review_atomic_edit_lost_reply_read_render_review_reopen_capture(editing_client, tmp_path):
    e = editing_client; audio, audio_receipts = formal_audio(e)
    insert_body = edit_body(e.created, audio_insert(audio), 'phase6-api-add-audio')
    inserted = checked(e.client.post(e.timeline_base + '/edit', headers=e.headers, json=insert_body))
    assert inserted['version'] == 2
    # Deliberately discard the mutation response as a UI could lose it. The
    # original GET receipt independently proves this exact body and effect.
    recovered_response = e.client.get(e.timeline_base, headers=e.headers)
    recovered = checked(recovered_response)
    assert recovered == inserted and recovered['edit_receipt']['request_id'] == insert_body['request_id']
    assert recovered['timeline']['tracks'][1]['clips'][0]['source_snapshot'] == source(audio)
    assert checked(e.client.post(e.timeline_base + '/edit', headers=e.headers, json=insert_body)) == recovered
    replacement = checked(e.client.post(e.studio_base + '/assets', headers=e.headers,
        json=upload(cpu_video(tmp_path / 'api-replacement-blue.mp4'), kind='video', filename='synthetic-replacement-blue.mp4')), 201)
    replacement_body = edit_body(recovered, [{'op': 'clip.update', 'clip_id': 'picture-one',
        'changes': {'source_snapshot': source(replacement), 'in_ms': 0, 'out_ms': 1000}}], 'phase6-api-replace-picture')
    replaced = checked(e.client.post(e.timeline_base + '/edit', headers=e.headers, json=replacement_body))
    replacement_recovered = checked(e.client.get(e.timeline_base, headers=e.headers))
    assert replaced == replacement_recovered and replaced['version'] == 3
    assert replaced['timeline']['tracks'][0]['clips'][0]['source_snapshot'] == source(replacement)
    assert replaced['edit_receipt']['request_id'] != recovered['edit_receipt']['request_id']
    render_body = {'expected_version': replaced['version'], 'reviewed_timeline_digest': replaced['timeline_digest'], 'request_id': 'phase6-api-render'}
    rendered = checked(e.client.post(e.timeline_base + '/render', headers=e.headers, json=render_body))
    assert rendered['status'] == 'SUCCEEDED', rendered
    candidate = rendered['output_candidate']; job_base = e.base + '/jobs/timeline/' + rendered['id']
    assert e.client.get(e.studio_base + '/assets/' + candidate['id'], headers=e.headers).status_code == 404
    downloaded = e.client.get(job_base + '/candidate', headers=e.headers)
    assert downloaded.status_code == 200 and downloaded.headers['content-type'].startswith('video/mp4')
    assert downloaded.headers['x-asset-sha256'] == candidate['digest'] == hashlib.sha256(downloaded.content).hexdigest()
    proof = measured_output(downloaded.content, tmp_path / 'api-real-render.mp4')
    approved = checked(e.client.post(job_base + '/review', headers=e.headers,
        json={**action(rendered), 'reviewed_output_digest': candidate['digest']}))
    assert approved['status'] == 'APPROVED' and approved['approved_asset_version'] == 2
    formal = checked(e.client.get(e.studio_base + '/assets/' + candidate['id'], headers=e.headers))
    assert formal['version'] == 2 and formal['sha256'] == candidate['digest']
    approved_get = checked(e.client.get(job_base, headers=e.headers))
    projected = {'execution_state', 'needs_reconciliation'}
    assert {key: value for key, value in approved_get.items() if key not in projected} == {
        key: value for key, value in approved.items() if key not in projected}
    # New original owner objects read persisted media, not a TestClient cache.
    from app.creative.workspace import IndependentWorkspaceService
    from app.creative.service import CreativeService
    from app.experimental.store import ExperimentalStore
    reopened = IndependentWorkspaceService(CreativeService(ExperimentalStore(e.root, e.backend, e.url),
        e.novels, e.chapters), e.assets, e.experimental.production_lineage_service)
    scope = {'mode': 'local', 'novel_id': e.nid}
    assert reopened.asset(e.nid, scope, candidate['id']) == formal
    with reopened._asset_scope(e.nid, scope):
        assert reopened.assets.content(candidate['id']) == downloaded.content
    for response in (recovered_response, downloaded):
        assert response.headers['cache-control'] == 'no-store' and response.headers['x-content-type-options'] == 'nosniff'
    if os.environ.get('STUDIO_CAPTURE_PHASE6_EDITING') == '1':
        captured = {'audio_receipts': audio_receipts, 'video_source': e.video, 'audio_formal': audio,
            'created': e.created, 'insert_body': insert_body, 'inserted': inserted, 'insert_recovered': recovered,
            'replacement_asset': replacement, 'replacement_body': replacement_body, 'replaced': replaced,
            'replacement_recovered': replacement_recovered, 'render_body': render_body, 'rendered': rendered,
            'approved': approved, 'approved_get': approved_get, 'formal_result': formal, 'decoded_proof': proof}
        # Public DTOs only: no Host/session token, physical path or environment.
        text = json.dumps(captured, ensure_ascii=False, indent=2) + '\n'
        assert str(e.root) not in text and e.host not in text
        (tmp_path / 'phase6-editing-response.json').write_text(text, encoding='utf-8')


def test_mounted_edit_wrong_source_cas_and_current_history_restore_receipts(editing_client):
    e = editing_client; audio, _ = formal_audio(e)
    bad = audio_insert(audio); bad[1]['clip']['source_snapshot']['version'] += 1
    assert e.client.post(e.timeline_base + '/edit', headers=e.headers, json=edit_body(e.created, bad)).status_code == 409
    assert checked(e.client.get(e.timeline_base, headers=e.headers)) == e.created
    body = edit_body(e.created, audio_insert(audio), 'phase6-api-cas')
    inserted = checked(e.client.post(e.timeline_base + '/edit', headers=e.headers, json=body))
    stale = deepcopy(body); stale['request_id'] = 'different-request'
    assert e.client.post(e.timeline_base + '/edit', headers=e.headers, json=stale).status_code == 409
    restored = checked(e.client.post(e.timeline_base + '/restore', headers=e.headers, json={
        'expected_version': inserted['version'], 'reviewed_timeline_digest': inserted['timeline_digest'],
        'restore_version': e.created['version'], 'restore_digest': e.created['timeline_digest']}))
    assert restored['version'] == 3 and 'edit_receipt' not in restored and restored['timeline'] == e.created['timeline']
    history = checked(e.client.get(e.timeline_base + '/history', headers=e.headers))
    assert next(row for row in history['items'] if row['version'] == 2)['edit_receipt'] == inserted['edit_receipt']
    assert checked(e.client.get(e.timeline_base, headers=e.headers)) == restored
    assert e.client.post(e.timeline_base + '/edit', headers=e.headers, json=body).status_code == 409


@pytest.mark.parametrize('change', ['revoke', 'aba', 'rebind'])
def test_mounted_actual_cpu_render_late_host_change_never_promotes(editing_client, monkeypatch, change):
    from app.actor_context import SessionContext
    from app.services import studio_timeline_export as native
    e = editing_client; row = e.created; native_run = native.run_guarded_process; observed = []
    def changed(arguments, **kwargs):
        result = native_run(arguments, **kwargs)
        if str(arguments[-1]).endswith('timeline.mp4'):
            observed.append(True); e.sessions.revoke(e.host)
            if change == 'aba': e.sessions.register(e.host, e.session)
            elif change == 'rebind': e.sessions.register(e.host, SessionContext('other', 'other', 'other', 'other'))
        return result
    monkeypatch.setattr(native, 'run_guarded_process', changed)
    response = e.client.post(e.timeline_base + '/render', headers=e.headers, json={
        'expected_version': row['version'], 'reviewed_timeline_digest': row['timeline_digest'], 'request_id': 'phase6-host-' + change})
    assert observed and response.status_code in {401, 403, 404}, response.text
    assert len(list(e.assets.root.glob('*.bin'))) == 3
