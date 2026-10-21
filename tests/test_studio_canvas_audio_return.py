"""Saved audio card -> original AudioJob -> real CPU WAV -> explicit return.

Short synthetic PCM only. No TTS inference, provider, GPU, or network request.
"""
from copy import deepcopy
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import struct
import wave

import pytest

from app.creative.production_execution_models import MediaCommand
from app.experimental.common import StaleSourceError
from app.services.audiobook_service import AudiobookError
from test_v2_independent_workspace import rig, import_asset, reopened
from test_creative_canvas_views_additive import owner, create, reference
from test_v2_audio_wav_controls import production, command, snapshot, preview, queue, run, review, get


def synthetic_wav():
    output = io.BytesIO()
    with wave.open(output, 'wb') as stream:
        stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(16000)
        stream.writeframes(b''.join(struct.pack('<h', amplitude) * 8000 for amplitude in [1000, 3000, 5000, 7000]))
    return output.getvalue()


@pytest.fixture
def audio_canvas(rig):
    e = rig
    assert shutil.which('ffmpeg') and shutil.which('ffprobe'), 'real CPU WAV test requires installed tools'
    e.service.activate(e.nid, e.scope, e.actor)
    e.source = import_asset(e, data=synthetic_wav(), filename='synthetic-card-source.wav', kind='audio')
    e.graph = owner(e); e.production = production(e); e.graph.configure_media(e.production)
    e.canvas = create(e, e.graph, {'title': 'Synthetic audio card', 'cards': [
        {'id': 'origin-audio', 'position': {'x': 44, 'y': 66}, 'asset': reference(e.source)},
        {'id': 'other-audio', 'position': {'x': 360, 'y': 120}, 'asset': reference(e.source)}]})
    e.command = command(snapshot(e.source), in_ms=550, out_ms=850)
    e.command['canvas_return'] = {'contract': 'studio-canvas-return/1', 'project_id': e.nid,
        'scope': e.scope, 'incarnation': e.store.incarnation(e.nid), 'canvas_id': e.canvas['id'],
        'canvas_version': e.canvas['version'], 'canvas_digest': e.canvas['definition_digest'],
        'card_id': 'origin-audio', 'source': snapshot(e.source)}
    return e


def save_result(e, approved):
    asset = e.service.asset(e.nid, e.scope, approved['output_candidate']['id'])
    definition = deepcopy(e.canvas['definition']); definition['cards'][0]['asset'] = reference(asset)
    body = {'expected_version': e.canvas['version'], 'definition': definition,
        'expected_incarnation': e.store.incarnation(e.nid), 'expected_definition_digest': e.canvas['definition_digest'],
        'expected_card': {'card_id': 'origin-audio', 'source': reference(e.source)}}
    return e.graph.canvas_views.save(e.nid, e.scope, e.actor, e.canvas['id'], body)


def test_real_wav_original_job_review_exact_return_restore_and_reopen(audio_canvas, monkeypatch):
    e = audio_canvas; captured = preview(e)
    assert captured['provider'] is None and captured['execution_recipe']['adapter'] == 'LOCAL_FFMPEG'
    assert captured['execution_recipe']['parameters'] == {'in_ms': 550, 'out_ms': 850}
    assert captured['command']['canvas_return'] == e.command['canvas_return']
    queued = queue(e)
    assert queued['status'] == 'QUEUED' and queued['command']['canvas_return'] == e.command['canvas_return']
    from app.services import studio_timeline_export as native
    original = native.run_guarded_process
    monkeypatch.setattr(native, 'run_guarded_process', lambda *a, **k: pytest.fail('reopen/get must not execute'))
    e.production = production(e, reopened(e)); e.graph.configure_media(e.production)
    assert get(e, queued) == queued
    assert e.graph.canvas_views.get(e.nid, e.scope, e.actor, e.canvas['id']) == e.canvas
    monkeypatch.setattr(native, 'run_guarded_process', original)
    executed = run(e, queued)
    assert executed['status'] == 'AWAITING_REVIEW', executed
    measurement = executed['media_measurement']
    assert measurement['duration_ms'] == 300 and measurement['container'] == 'wav'
    assert measurement['profile_validation'] == 'PCM_DECODED'
    assert measurement['sample_rate'] == 48000 and measurement['channels'] == 2
    meta, data = e.production.candidate(e.nid, e.scope, e.actor, 'audio', executed['id'], lambda: None)
    assert hashlib.sha256(data).hexdigest() == executed['output_candidate']['digest'] == measurement['output_sha256']
    with wave.open(io.BytesIO(data), 'rb') as result:
        assert result.getnframes() == 14400 and result.getnchannels() == 2
        samples = struct.unpack('<' + 'h' * (result.getnframes() * result.getnchannels()), result.readframes(result.getnframes()))
    # The 550..850ms interval lies in the synthetic 3000-amplitude segment.
    # Mono -> default stereo uses the original FFmpeg layout gain (~1/sqrt(2)).
    assert all(abs(sample - 2121) <= 2 for sample in samples[400:-400])
    with pytest.raises(FileNotFoundError): e.service.asset(e.nid, e.scope, executed['output_candidate']['id'])
    assert e.graph.canvas_views.get(e.nid, e.scope, e.actor, e.canvas['id']) == e.canvas
    approved = review(e, executed)
    assert approved['status'] == 'APPROVED' and approved['command']['canvas_return'] == e.command['canvas_return']
    output = e.service.asset(e.nid, e.scope, approved['output_candidate']['id'])
    returned = save_result(e, approved)
    assert returned['version'] == 2 and returned['definition']['cards'][0]['asset'] == reference(output)
    assert returned['definition']['cards'][0]['position'] == e.canvas['definition']['cards'][0]['position']
    assert returned['definition']['cards'][1] == e.canvas['definition']['cards'][1]
    history = e.graph.canvas_views.history(e.nid, e.scope, e.actor, e.canvas['id'])
    restored = e.graph.canvas_views.restore(e.nid, e.scope, e.actor, e.canvas['id'], {
        'expected_version': returned['version'], 'expected_definition_digest': returned['definition_digest'],
        'expected_incarnation': history['incarnation'], 'restore_version': e.canvas['version'],
        'restore_definition_digest': e.canvas['definition_digest']})
    assert restored['version'] == 3 and restored['definition'] == e.canvas['definition']
    assert get(e, approved) == approved
    if os.environ.get('STUDIO_CAPTURE_AUDIO_CANVAS'):
        value = {'contract': 'synthetic-audio-canvas-proof/1', 'model_inference': False,
            'real_cpu_ffmpeg': True, 'source': e.source, 'output': output, 'canvas': e.canvas,
            'command': e.command, 'preview': captured, 'queued': queued, 'executed': executed,
            'approved': approved, 'returned': returned, 'restored': restored, 'history': history,
            'source_wav_base64': base64.b64encode(synthetic_wav()).decode(),
            'candidate_wav_base64': base64.b64encode(data).decode()}
        Path(os.environ['STUDIO_CAPTURE_AUDIO_CANVAS']).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


@pytest.mark.parametrize('change', ['null', 'kind', 'project', 'scope', 'incarnation', 'card', 'version', 'digest', 'pin', 'cloud', 'provider', 'prompt', 'operation', 'format', 'sample-rate'])
def test_bad_or_stale_audio_return_preview_never_creates_job(audio_canvas, change, monkeypatch):
    e = audio_canvas; value = deepcopy(e.command); origin = value['canvas_return']
    if change == 'null': value['canvas_return'] = None
    elif change == 'kind': origin['source']['asset_kind'] = 'video'
    elif change == 'project': origin['project_id'] = 'another'; origin['scope'] = {'mode': 'local', 'novel_id': 'another'}
    elif change == 'scope': origin['scope'] = {**origin['scope'], 'branch_id': 'another'}
    elif change == 'incarnation': origin['incarnation'] = 'file:00000000-0000-0000-0000-000000000000'
    elif change == 'card': origin['card_id'] = 'deleted-card'
    elif change == 'version': origin['canvas_version'] += 1
    elif change == 'digest': origin['canvas_digest'] = 'f' * 64
    elif change == 'pin': origin['source']['digest'] = 'f' * 64
    elif change == 'cloud': value['allow_cloud'] = True
    elif change == 'provider': value['provider_id'] = 'invented-provider'
    elif change == 'prompt': value['prompt'] = 'generation request'
    elif change == 'operation': value['operation_id'] = 'm8.audio.music'
    elif change == 'format': value['parameters']['output_format'] = 'FLAC'
    elif change == 'sample-rate': value['parameters']['sample_rate'] = 48000
    from app.services import studio_timeline_export as native
    monkeypatch.setattr(native, 'run_guarded_process', lambda *a, **k: pytest.fail('preview cannot execute'))
    with pytest.raises((ValueError, StaleSourceError, FileNotFoundError)): preview(e, value)
    audio = e.production._audio(e.scope, e.actor)
    assert audio.list(e.nid, e.production._base(e.nid, e.scope, e.actor, lambda: None), lambda: None) == []


def change_origin(e, change):
    if change in {'version', 'deleted-card'}:
        definition = deepcopy(e.canvas['definition'])
        if change == 'version': definition['title'] += ' changed'
        else: definition['cards'] = definition['cards'][1:]
        e.graph.canvas_views.save(e.nid, e.scope, e.actor, e.canvas['id'], {'expected_version': 1, 'definition': definition})
    else:
        with e.service._asset_scope(e.nid, e.scope):
            if change == 'source-pin': e.assets.update_metadata(e.source['id'], {'provider_id': 'synthetic-new-metadata'}, expected_version=e.source['version'])
            elif change == 'source-deleted': e.assets.delete(e.source['id'])
            else: raise AssertionError(change)


@pytest.mark.parametrize('change', ['version', 'deleted-card', 'source-pin', 'source-deleted'])
def test_queued_target_change_blocks_native_dispatch(audio_canvas, change, monkeypatch):
    e = audio_canvas; queued = queue(e); change_origin(e, change)
    from app.services import studio_timeline_export as native
    monkeypatch.setattr(native, 'run_guarded_process', lambda *a, **k: pytest.fail('stale target cannot execute'))
    with pytest.raises((ValueError, StaleSourceError, FileNotFoundError, AudiobookError)): run(e, queued)
    assert get(e, queued)['status'] in {'QUEUED', 'FAILED'}
    assert get(e, queued)['output_candidate'] is None


@pytest.mark.parametrize('change', ['version', 'deleted-card', 'source-pin', 'source-deleted'])
def test_stale_target_review_is_blocked_and_private_candidate_retained(audio_canvas, change):
    e = audio_canvas; candidate = run(e, queue(e)); assert candidate['status'] == 'AWAITING_REVIEW'
    change_origin(e, change)
    with pytest.raises((ValueError, StaleSourceError, FileNotFoundError, AudiobookError)): review(e, candidate)
    current = get(e, candidate)
    assert current['status'] == 'AWAITING_REVIEW' and current['output_candidate'] == candidate['output_candidate']
    with pytest.raises(FileNotFoundError): e.service.asset(e.nid, e.scope, candidate['output_candidate']['id'])


def test_late_native_result_cannot_publish_after_card_version_changed(audio_canvas, monkeypatch):
    e = audio_canvas; queued = queue(e)
    from app.services import studio_timeline_export as native
    original = native.run_guarded_process
    def changed(*args, **kwargs):
        result = original(*args, **kwargs); change_origin(e, 'version'); return result
    monkeypatch.setattr(native, 'run_guarded_process', changed)
    current = run(e, queued)
    # Preserve the original publication-uncertainty state; never replay it.
    assert current['status'] == 'UNKNOWN' and current['output_candidate'] is None
    assert len(e.service.list_assets(e.nid, e.scope)['items']) == 1
    with pytest.raises((AudiobookError, ValueError, StaleSourceError, FileNotFoundError)): run(e, current)
    assert get(e, current)['status'] == 'UNKNOWN'


@pytest.mark.parametrize('change', ['version', 'source-pin', 'source-deleted'])
def test_return_cas_refuses_changes_and_keeps_approved_result(audio_canvas, change):
    e = audio_canvas; approved = review(e, run(e, queue(e)))
    change_origin(e, change)
    with pytest.raises((ValueError, StaleSourceError, FileNotFoundError)): save_result(e, approved)
    assert get(e, approved)['status'] == 'APPROVED'
    assert e.service.asset(e.nid, e.scope, approved['output_candidate']['id'])['id'] == approved['output_candidate']['id']


@pytest.mark.parametrize('change', ['command', 'scope', 'incarnation', 'recipe'])
def test_audio_owner_checks_original_command_context_and_recipe(audio_canvas, change):
    e = audio_canvas; queued = queue(e)
    audio = e.production._audio(e.scope, e.actor)
    row = audio.get(e.nid, queued['id'], e.production._base(e.nid, e.scope, e.actor, lambda: None), lambda: None)
    from app.services.studio_audio_execution import _binding
    context = deepcopy(row['context'])
    if change == 'command': context['command']['parameters']['out_ms'] = 900
    elif change == 'scope': context['command']['canvas_return']['scope'] = {**e.scope, 'workspace_id': 'wrong-workspace'}
    elif change == 'incarnation': context['command']['canvas_return']['incarnation'] = 'file:00000000-0000-0000-0000-000000000000'
    else: context['execution_recipe']['parameters']['out_ms'] = 900
    with pytest.raises((ValueError, AudiobookError)): _binding(context, row['_studio_body'])


def test_unknown_original_job_cannot_be_replayed(audio_canvas, monkeypatch):
    e = audio_canvas; queued = queue(e); audio = e.production._audio(e.scope, e.actor)
    def uncertain(state):
        row = audio.service.find(state, queued['id']); row['status'] = 'UNKNOWN'; row['dispatch_state'] = 'OUTCOME_UNKNOWN'
        row['version'] += 1; audio._receipt(row)
    audio.store.mutate(e.nid, uncertain)
    current = get(e, queued); assert current['status'] == 'UNKNOWN'
    from app.services import studio_timeline_export as native
    monkeypatch.setattr(native, 'run_guarded_process', lambda *a, **k: pytest.fail('UNKNOWN must not be replayed'))
    with pytest.raises(AudiobookError): run(e, current)
    assert get(e, current)['status'] == 'UNKNOWN'


def test_legacy_unbound_trim_keeps_original_wav_contract(audio_canvas):
    e = audio_canvas; e.command.pop('canvas_return')
    captured = preview(e); queued = queue(e)
    assert 'canvas_return' not in captured['command'] and 'canvas_return' not in queued['command']
    assert queued['provider'] is None and queued['execution_recipe']['output_profile'] == 'PCM_S16LE_WAV_48000_STEREO'


@pytest.mark.parametrize('change', ['other-project', 'recreated-project'])
def test_original_audio_job_is_not_rebound_to_another_scope_or_incarnation(audio_canvas, change, monkeypatch):
    e = audio_canvas; queued = queue(e)
    if change == 'other-project':
        nid = e.create_project('Other neutral owner')
        scope = {'mode': 'local', 'novel_id': nid}
    else:
        e.novels.delete(e.nid); e.create_project('Recreated neutral owner', e.nid)
        nid, scope = e.nid, e.scope
    e.service.activate(nid, scope, e.actor)
    from app.services import studio_timeline_export as native
    monkeypatch.setattr(native, 'run_guarded_process', lambda *a, **k: pytest.fail('old job cannot execute under another owner'))
    from test_v2_audio_wav_controls import action
    with pytest.raises((ValueError, AudiobookError, FileNotFoundError)):
        e.production.execute(nid, scope, e.actor, 'audio', queued['id'], action(queued), lambda: None)


def test_original_canvas_binding_requires_actual_pcm_proof(audio_canvas):
    e = audio_canvas; candidate = run(e, queue(e)); audio = e.production._audio(e.scope, e.actor)
    context = e.production._base(e.nid, e.scope, e.actor, lambda: None)
    row = deepcopy(audio.get(e.nid, candidate['id'], context, lambda: None)); row.pop('measured')
    with pytest.raises(AudiobookError, match='实际输出证明缺失'): audio._validated_job(row, context)
