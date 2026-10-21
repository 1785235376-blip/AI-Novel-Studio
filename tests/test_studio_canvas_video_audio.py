"""Optional video-card audio over the original CPU Timeline/Job/Review owners.

The baseline owner probe is deliberately separate from the mounted HTTP loop.
Only installed FFmpeg processes short synthetic media; PCM measurements are
independent of request fields, renderer metadata and UI capability messages.
"""
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import wave

import pytest

from app.services import studio_timeline_export as native, video_assembly_service as assembly
from test_creative_canvas_views_additive import reference
from test_r3_mounted_contracts import checked, mounted, prefix
from test_studio_canvas_video_bridge import definition, render_calls
from test_studio_canvas_video_bridge_api import video_client
from test_studio_canvas_video_cpu_owner_probe import _context, _native, _owner_execute, _queue
from test_v2_audio_editing_pipeline import production, source
from test_v2_audio_wav_controls import action
from test_v2_independent_workspace import rig, import_asset, upload
from test_v2_independent_workspace_api import client


def _two_tone_video(directory):
    """First audio track: 440 Hz then 880 Hz; second track: 1320 Hz."""
    assert shutil.which('ffmpeg') and shutil.which('ffprobe'), 'installed CPU FFmpeg tools are required'
    path = directory / 'synthetic-two-tone-two-tracks.mp4'
    _native([shutil.which('ffmpeg'), '-nostdin', '-v', 'error', '-threads', '1',
        '-f', 'lavfi', '-i', 'color=c=blue:s=64x64:r=25:d=2',
        '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=1',
        '-f', 'lavfi', '-i', 'sine=frequency=880:sample_rate=48000:duration=1',
        '-f', 'lavfi', '-i', 'sine=frequency=1320:sample_rate=48000:duration=2',
        '-filter_complex_threads', '1', '-filter_complex', '[1:a][2:a]concat=n=2:v=0:a=1[first]',
        '-map', '0:v:0', '-map', '[first]', '-map', '3:a:0', '-c:v', 'mpeg4', '-c:a', 'aac',
        '-ar', '48000', '-ac', '2', '-threads', '1', '-y', str(path)], directory)
    return path


def _audio_proof(path, *, track=0, start_ms=0, duration_ms=None):
    probe = native.probe_media_file(path, guard=lambda: None)
    streams = [row for row in probe['streams'] if row['codec_type'] == 'audio']
    decoded = path.with_name(path.stem + f'-track{track}-{start_ms}.wav')
    command = [shutil.which('ffmpeg'), '-nostdin', '-v', 'error', '-threads', '1',
        '-protocol_whitelist', 'file,pipe', '-i', str(path), '-map', f'0:a:{track}',
        '-ss', str(start_ms / 1000)]
    if duration_ms is not None:
        command += ['-t', str(duration_ms / 1000)]
    _native(command + ['-vn', '-ac', '1', '-ar', '48000', '-c:a', 'pcm_s16le', '-threads', '1', '-y', str(decoded)], path.parent)
    with wave.open(str(decoded), 'rb') as reader:
        assert (reader.getnchannels(), reader.getsampwidth(), reader.getframerate()) == (1, 2, 48000)
        raw = reader.readframes(reader.getnframes())
    values = struct.unpack('<' + 'h' * (len(raw) // 2), raw)
    # Measure the interior, avoiding AAC boundary padding and fixture join edges.
    samples = values[4800:24000]
    assert len(samples) == 19200
    rms = math.sqrt(sum(value * value for value in samples) / len(samples))
    amplitudes = {}
    for frequency in (440, 880, 1320):
        real = sum(value * math.cos(2 * math.pi * frequency * index / 48000) for index, value in enumerate(samples))
        imaginary = sum(value * math.sin(2 * math.pi * frequency * index / 48000) for index, value in enumerate(samples))
        amplitudes[str(frequency)] = 2 * math.hypot(real, imaginary) / len(samples)
    return {'audio_tracks': len(streams), 'codec': streams[track]['codec_name'],
        'sample_rate': int(streams[track]['sample_rate']), 'channels': streams[track]['channels'],
        'decoded_samples': len(values), 'interior_rms_pcm16': rms, 'amplitudes_pcm16': amplitudes,
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def _assert_tone(proof, frequency):
    assert proof['interior_rms_pcm16'] > 300
    selected = proof['amplitudes_pcm16'][str(frequency)]
    assert selected > 500
    assert all(selected > other * 20 for tone, other in proof['amplitudes_pcm16'].items() if tone != str(frequency))


def _evidence(name, value):
    if directory := os.environ.get('STUDIO_VIDEO_AUDIO_EVIDENCE'):
        target = Path(directory); target.mkdir(parents=True, exist_ok=True)
        (target / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def _timeline(pin, include_audio):
    value = definition(pin)
    value['tracks'][0]['clips'][0]['include_audio'] = include_audio
    return value


def _select_option(e, option):
    # None represents omission; explicit false is kept in the command wire.
    parameters = {'in_ms': 1000, 'out_ms': 1600}
    if option is not None:
        parameters['include_audio'] = option
    e.timeline = checked(e.client.put(e.base + '/timelines/' + e.timeline['id'], headers=e.headers, json={
        'expected_version': e.timeline['version'], 'title': 'Explicit video source audio choice',
        'timeline': _timeline(source(e.source), option is True)}))
    e.command['parameters'] = parameters
    e.command['timeline_snapshot'] = {'id': e.timeline['id'], 'version': e.timeline['version'], 'digest': e.timeline['timeline_digest']}
    return e.command


@pytest.fixture
def audio_client(video_client, tmp_path):
    e = video_client
    e.media = _two_tone_video(tmp_path)
    e.source = checked(e.client.post(e.studio_base + '/assets', headers=e.headers,
        json=upload(e.media.read_bytes(), kind='video', filename=e.media.name)), 201)
    e.canvas = checked(e.client.post(e.canvas_base, headers=e.headers, json={
        'request_id': 'two-tone-canvas', 'definition': {'title': 'Two-tone source cards', 'cards': [
            {'id': 'origin-video', 'position': {'x': 40, 'y': 60}, 'asset': reference(e.source)},
            {'id': 'other-video', 'position': {'x': 700, 'y': 120}, 'asset': reference(e.source)}]}}), 201)
    e.command['source_snapshots'] = [source(e.source)]
    e.command['canvas_return'].update(canvas_id=e.canvas['id'], canvas_version=e.canvas['version'],
        canvas_digest=e.canvas['definition_digest'], source=source(e.source))
    _select_option(e, True)
    return e


def _preview(e, command=None):
    return checked(e.client.post(e.base + '/canvas-video/preview', headers=e.headers, json=command or e.command))


def _queued(e, captured=None):
    captured = captured or _preview(e)
    return checked(e.client.post(e.base + '/canvas-video/queue', headers=e.headers,
        json={'command': e.command, 'reviewed_preview_digest': captured['preview_digest']}), 201)


def _execute(e, row, proof=None):
    return e.client.post(e.base + '/canvas-video/jobs/' + row['id'] + '/execute', headers=e.headers,
        json=proof or action(row).model_dump())


def _read(e, row):
    return checked(e.client.get(e.base + '/jobs/timeline/' + row['id'], headers=e.headers))


def test_baseline_original_timeline_owner_supports_first_selected_audio_track(rig, tmp_path):
    """Server-only baseline capability evidence, not a card API acceptance claim."""
    e = rig; e.service.activate(e.nid, e.scope, e.actor)
    media = _two_tone_video(tmp_path)
    first, second, alternate = (_audio_proof(media, start_ms=0, duration_ms=600),
        _audio_proof(media, start_ms=1000, duration_ms=600), _audio_proof(media, track=1, start_ms=1000, duration_ms=600))
    _assert_tone(first, 440); _assert_tone(second, 880); _assert_tone(alternate, 1320)
    asset = import_asset(e, data=media.read_bytes(), filename=media.name, kind='video')
    e.production = production(e)
    e.timeline = e.production.timeline_save(e.nid, e.scope, e.actor, None, {
        'expected_version': 0, 'title': 'Original audio owner capability probe', 'timeline': _timeline(source(asset), True)}, lambda: None)
    context = _context(e, 'baseline-first-audio-probe')
    queued = _queue(e, context); candidate = _owner_execute(e, queued, context)
    assert candidate['status'] == 'SUCCEEDED' and candidate['model_called'] is False
    _, data = e.production.candidate(e.nid, e.scope, e.actor, 'timeline', candidate['id'], lambda: None)
    path = tmp_path / 'baseline-first-audio-output.mp4'; path.write_bytes(data)
    measured = _audio_proof(path); _assert_tone(measured, 880)
    assert measured['audio_tracks'] == 1 and measured['codec'] == 'aac'
    _evidence('baseline-owner.json', {'boundary': 'server-only original Timeline owner capability probe',
        'source_first_segment': first, 'source_selected_segment': second, 'source_second_track': alternate,
        'output': measured, 'status': candidate['status'], 'model_called': False, 'real_cpu_ffmpeg': True})


@pytest.mark.parametrize('option', [None, False, True], ids=['legacy-omitted', 'explicit-silent', 'retain-first-audio'])
def test_mounted_video_audio_option_changes_decoded_output_and_preserves_review_cas_history(audio_client, render_calls, tmp_path, option):
    e = audio_client; _select_option(e, option)
    original = deepcopy(e.canvas['definition']); captured = _preview(e)
    assert captured['command'] == e.command
    assert ('include_audio' in captured['command']['parameters']) == (option is not None)
    assert captured['execution_recipe']['timeline']['tracks'][0]['clips'][0]['include_audio'] is (option is True)
    assert not render_calls
    queued = _queued(e, captured)
    assert queued['canvas_video'] == e.command and queued['output_candidate'] is None
    assert _read(e, queued)['automatic_replay'] is False and not render_calls
    candidate = checked(_execute(e, queued))
    assert candidate['status'] == 'SUCCEEDED' and len(render_calls) == 1
    assert candidate['canvas_video'] == e.command
    job_path = e.base + '/jobs/timeline/' + candidate['id']
    response = e.client.get(job_path + '/candidate', headers=e.headers)
    assert response.status_code == 200
    path = tmp_path / 'mounted-source-audio-option.mp4'; path.write_bytes(response.content)
    measured = _audio_proof(path)
    assert measured['sha256'] == candidate['output_candidate']['digest']
    assert (measured['audio_tracks'], measured['codec'], measured['sample_rate'], measured['channels']) == (1, 'aac', 48000, 2)
    if option is True:
        _assert_tone(_audio_proof(e.media, start_ms=0, duration_ms=600), 440)
        _assert_tone(_audio_proof(e.media, track=1, start_ms=1000, duration_ms=600), 1320)
        _assert_tone(measured, 880)
    else:
        assert measured['interior_rms_pcm16'] < 1
        assert max(measured['amplitudes_pcm16'].values()) < 1
    assert _execute(e, candidate).status_code == 422 and len(render_calls) == 1
    asset_path = e.studio_base + '/assets/' + candidate['output_candidate']['id']
    assert e.client.get(asset_path, headers=e.headers).status_code == 404
    approved = checked(e.client.post(job_path + '/review', headers=e.headers, json=action(candidate, True).model_dump()))
    assert approved['status'] == 'APPROVED'
    formal = checked(e.client.get(asset_path, headers=e.headers))
    assert formal['sha256'] == measured['sha256']
    changed = deepcopy(original); changed['cards'][0]['asset'] = reference(formal)
    canvas_path = e.canvas_base + '/' + e.canvas['id']
    returned = checked(e.client.put(canvas_path, headers=e.headers, json={
        'expected_version': e.canvas['version'], 'definition': changed,
        'expected_definition_digest': e.canvas['definition_digest'], 'expected_incarnation': e.studio.store.incarnation(e.nid),
        'expected_card': {'card_id': 'origin-video', 'source': reference(e.source)}}))
    assert returned['version'] == e.canvas['version'] + 1
    assert returned['definition']['cards'][1] == original['cards'][1]
    assert returned['definition']['cards'][0]['position'] == original['cards'][0]['position']
    history = checked(e.client.get(canvas_path + '/history', headers=e.headers))
    restored = checked(e.client.post(canvas_path + '/restore', headers=e.headers, json={
        'expected_version': returned['version'], 'expected_definition_digest': returned['definition_digest'],
        'expected_incarnation': history['incarnation'], 'restore_version': e.canvas['version'],
        'restore_definition_digest': e.canvas['definition_digest']}))
    assert restored['version'] == returned['version'] + 1 and restored['definition'] == original
    assert _read(e, approved)['status'] == 'APPROVED' and len(render_calls) == 1
    _evidence(f'mounted-{e.prefix.strip("/").replace("/", "-")}-{str(option).lower()}.json', {
        'boundary': 'real mounted HTTP card API with original Job/Review/CAS/history', 'option': option,
        'wire_parameters': captured['command']['parameters'], 'output': measured, 'preview': captured,
        'queued_status': queued['status'], 'executed_status': candidate['status'], 'review_status': approved['status'],
        'canvas_versions': [e.canvas['version'], returned['version'], restored['version']], 'native_renders': len(render_calls),
        'model_called': False, 'real_cpu_ffmpeg': True})


def test_mounted_requested_audio_without_source_track_is_rejected_by_original_owner(video_client, render_calls, monkeypatch):
    e = video_client; _select_option(e, True)
    from app.services import studio_timeline_render
    failures = []; original_render = studio_timeline_render.render_studio_timeline
    def observed(*args, **kwargs):
        try:
            return original_render(*args, **kwargs)
        except Exception as error:
            failures.append(str(error))
            raise
    monkeypatch.setattr(studio_timeline_render, 'render_studio_timeline', observed)
    queued = _queued(e)
    response = _execute(e, queued)
    # The native owner rejects during pre-render inspection, before publication.
    current = _read(e, queued)
    assert current['status'] == 'FAILED' and current['output_candidate'] is None
    assert response.status_code == 200
    assert failures == ['STUDIO_TIMELINE_VIDEO_AUDIO_STREAM_REQUIRED']
    assert not render_calls
    assert e.client.get(e.base + '/jobs/timeline/' + queued['id'] + '/candidate', headers=e.headers).status_code != 200
    assert _execute(e, current).status_code == 422 and not render_calls


@pytest.mark.parametrize('invalid', [None, 'true', 'false', 0, 1, {}, []])
def test_mounted_audio_option_is_strict_and_invalid_values_cannot_queue(video_client, render_calls, invalid):
    e = video_client; value = deepcopy(e.command); value['parameters']['include_audio'] = invalid
    response = e.client.post(e.base + '/canvas-video/preview', headers=e.headers, json=value)
    assert response.status_code == 422
    response = e.client.post(e.base + '/canvas-video/queue', headers=e.headers,
        json={'command': value, 'reviewed_preview_digest': 'a' * 64})
    assert response.status_code == 422 and not render_calls
    assert e.production.list(e.nid, e.scope, 'local-author', lambda: None)['items'] == []


@pytest.mark.parametrize('mutation', ['canvas-stale', 'source-pin', 'action-proof', 'preview-proof', 'unknown'])
def test_mounted_audio_retention_preserves_stale_pin_proof_unknown_fences(audio_client, render_calls, mutation):
    e = audio_client; captured = _preview(e)
    if mutation == 'preview-proof':
        _select_option(e, False)
        fresh = _preview(e)
        assert fresh['preview_digest'] != captured['preview_digest']
        response = e.client.post(e.base + '/canvas-video/queue', headers=e.headers,
            json={'command': e.command, 'reviewed_preview_digest': captured['preview_digest']})
        assert response.status_code == 409 and response.json()['detail']['code']=='EXPERIMENTAL_SOURCE_STALE' and not render_calls
        assert e.production.list(e.nid, e.scope, 'local-author', lambda: None)['items'] == []
        return
    queued = _queued(e, captured)
    if mutation == 'canvas-stale':
        value = deepcopy(e.canvas['definition']); value['title'] += ' changed'
        checked(e.client.put(e.canvas_base + '/' + e.canvas['id'], headers=e.headers,
            json={'expected_version': e.canvas['version'], 'definition': value}))
    elif mutation == 'source-pin':
        with e.studio._asset_scope(e.nid, e.scope):
            e.assets.update_metadata(e.source['id'], {'provider_id': 'fixture-metadata-change'}, expected_version=e.source['version'])
    elif mutation == 'unknown':
        base = e.production._base(e.nid, e.scope, 'local-author', lambda: None)
        raw = e.production.video_owner.get_studio(e.nid, e.scope.get('branch_id'), 'local-author', queued['id'], context={**base,'request_digest':queued['request_digest']}, guard=lambda: None)
        # Seed a durable uncertain state, without claiming a native failure occurred.
        e.production.video_owner._studio_mutate(e.nid, e.scope.get('branch_id'), 'local-author', queued['id'], raw['version'],
            lambda row: row.update(status='UNKNOWN', phase='RENDERING', automatic_retry=False), context=raw['context'])
        queued = _read(e, queued)
        assert queued['status'] == 'UNKNOWN' and queued['automatic_replay'] is False
    proof = action(queued).model_dump()
    if mutation == 'action-proof': proof['expected_request_digest'] = 'f' * 64
    response = _execute(e, queued, proof)
    assert response.status_code in {409, 422} and not render_calls
    current = _read(e, queued)
    assert current['status'] == ('UNKNOWN' if mutation == 'unknown' else 'QUEUED')
    assert current['output_candidate'] is None and current['automatic_replay'] is False
