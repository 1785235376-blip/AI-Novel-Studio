"""Canvas envelope bridge over the original AudioJob, using real CPU FFmpeg.

Only short owned synthetic WAVs. PCM observations are computed independently of
the receipt; no provider, inference, GPU, network or alternate audio processor.
"""
from copy import deepcopy
import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import struct
import wave

import pytest

from app.creative.production_execution_models import MediaCommand
from app.experimental.common import StaleSourceError
from app.services.audiobook_service import AudiobookError
from test_creative_canvas_views_additive import owner, create, reference
from test_v2_audio_wav_controls import production, command, snapshot, preview, queue, run, get, review
from test_v2_independent_workspace import rig, import_asset, reopened


RATE = 48000
AMPLITUDE = 8000
LSB_TOLERANCE = 3  # Fixed before execution: volume/fade S16 quantization only.


def synthetic_wav():
    """Stereo source with distinct discarded regions proves the original in-point."""
    output = io.BytesIO()
    with wave.open(output, 'wb') as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(RATE)
        for milliseconds, amplitude in [(200, 1000), (1000, AMPLITUDE), (200, -2000)]:
            stream.writeframes(struct.pack('<hh', amplitude, amplitude) * (RATE * milliseconds // 1000))
    return output.getvalue()


@pytest.fixture
def envelope_canvas(rig):
    e = rig
    assert shutil.which('ffmpeg') and shutil.which('ffprobe'), 'requires installed real CPU FFmpeg tools'
    e.service.activate(e.nid, e.scope, e.actor)
    e.original_bytes = synthetic_wav()
    e.source = import_asset(e, data=e.original_bytes, filename='owned-envelope-source.wav', kind='audio')
    e.production = production(e)  # Its NoControl collaborators reject every provider action.
    e.graph = owner(e)
    e.graph.configure_media(e.production)
    e.canvas = create(e, e.graph, {'title': 'Owned envelope task', 'cards': [
        {'id': 'origin-audio', 'position': {'x': 44, 'y': 66}, 'asset': reference(e.source)},
        {'id': 'other-audio', 'position': {'x': 360, 'y': 120}, 'asset': reference(e.source)}]})
    e.command = command(snapshot(e.source), in_ms=200, out_ms=1200)
    e.command['canvas_return'] = {'contract': 'studio-canvas-return/1', 'project_id': e.nid,
        'scope': e.scope, 'incarnation': e.store.incarnation(e.nid), 'canvas_id': e.canvas['id'],
        'canvas_version': e.canvas['version'], 'canvas_digest': e.canvas['definition_digest'],
        'card_id': 'origin-audio', 'source': snapshot(e.source)}
    return e


def retain(tmp_path, label, evidence, source=None, candidate=None):
    encoded = json.dumps(evidence, indent=2, sort_keys=True) + '\n'
    (tmp_path / (label + '.json')).write_text(encoded, encoding='utf-8')
    destination = os.environ.get('STUDIO_CAPTURE_AUDIO_ENVELOPE_DIR')
    if destination:
        folder = Path(destination)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / (label + '.json')).write_text(encoded, encoding='utf-8')
        if source is not None:
            (folder / (label + '-source.wav')).write_bytes(source)
        if candidate is not None:
            (folder / (label + '-candidate.wav')).write_bytes(candidate)


def decode(e, result):
    """Read real persisted WAV frames independently with the Python PCM decoder."""
    meta, data = e.production.candidate(e.nid, e.scope, e.actor, 'audio', result['id'], lambda: None)
    measured = result['media_measurement']
    with wave.open(io.BytesIO(data), 'rb') as stream:
        assert (stream.getframerate(), stream.getnchannels(), stream.getsampwidth()) == (RATE, 2, 2)
        assert stream.getnframes() == RATE
        pcm = stream.readframes(stream.getnframes())
    samples = struct.unpack('<' + 'h' * (len(pcm) // 2), pcm)
    assert len(samples) == RATE * 2
    assert measured['duration_ms'] == 1000
    assert measured['sample_rate'] == RATE and measured['channels'] == 2 and measured['sample_width'] == 2
    assert measured['profile_validation'] == 'PCM_DECODED'
    actual_hash = hashlib.sha256(data).hexdigest()
    assert actual_hash == meta['sha256'] == measured['output_sha256'] == result['output_candidate']['digest']
    assert len(data) == measured['byte_count']
    evidence = {'real_cpu_ffmpeg': True, 'model_inference': False, 'source_sha256': e.source['sha256'],
        'candidate_sha256': actual_hash, 'independent_pcm_sha256': hashlib.sha256(pcm).hexdigest(),
        'independent_frames': len(samples) // 2, 'measurement': measured}
    return [samples[0::2], samples[1::2]], pcm, data, evidence


def return_body(e, asset):
    definition = deepcopy(e.canvas['definition'])
    definition['cards'][0]['asset'] = reference(asset)
    return {'expected_version': e.canvas['version'], 'definition': definition,
        'expected_incarnation': e.store.incarnation(e.nid), 'expected_definition_digest': e.canvas['definition_digest'],
        'expected_card': {'card_id': 'origin-audio', 'source': reference(e.source)}}


@pytest.mark.parametrize('gain_db', [-60, -6.020599913279624, -6, 6, 12])
def test_actual_gain_and_linear_fade_pcm_windows(envelope_canvas, tmp_path, gain_db):
    e = envelope_canvas
    e.command['parameters'].update(gain_db=gain_db, fade_in_ms=200, fade_out_ms=300)
    captured = preview(e)
    assert captured['provider'] is None and captured['execution_recipe']['adapter'] == 'LOCAL_FFMPEG'
    assert captured['execution_recipe']['parameters'] == e.command['parameters']
    assert captured['execution_recipe']['output_profile'] == 'PCM_S16LE_WAV_48000_STEREO'
    queued = queue(e)
    assert queued['status'] == 'QUEUED' and queued['media_measurement'] is None
    assert queue(e) == queued
    result = run(e, queued)
    assert result['status'] == 'AWAITING_REVIEW', result
    channels, _, data, evidence = decode(e, result)
    plateau = AMPLITUDE * 10 ** (gain_db / 20)
    def expected(index):
        elapsed_ms = index * 1000 / RATE
        return plateau * min(1, elapsed_ms / 200) * min(1, (1000 - elapsed_ms) / 300)
    windows = [(20, 40), (90, 110), (450, 550), (840, 860), (940, 960)]
    observations = []
    for samples in channels:
        maximum_error = max(abs(samples[index] - expected(index)) for index in range(RATE // 100, RATE * 99 // 100))
        rows = []
        for start, end in windows:
            indices = range(RATE * start // 1000, RATE * end // 1000)
            observed = sum(samples[index] for index in indices) / len(indices)
            ideal = sum(expected(index) for index in indices) / len(indices)
            rows.append({'start_ms': start, 'end_ms': end, 'observed_mean': observed, 'expected_mean': ideal})
        observations.append({'maximum_absolute_error': maximum_error, 'windows': rows})
    evidence.update(gain_db=gain_db, fade_in_ms=200, fade_out_ms=300, expected_plateau=plateau,
        absolute_lsb_tolerance=LSB_TOLERANCE, channels=observations, command=e.command,
        execution_recipe=result['execution_recipe'])
    retain(tmp_path, 'gain-' + str(gain_db).replace('.', '_'), evidence, e.original_bytes, data)
    assert all(row['maximum_absolute_error'] <= LSB_TOLERANCE for row in observations), evidence
    assert all(abs(window['observed_mean'] - window['expected_mean']) <= LSB_TOLERANCE
               for row in observations for window in row['windows']), evidence
    assert channels[0] == channels[1]
    assert e.service.download(e.nid, e.scope, e.source['id'])[1] == e.original_bytes
    with pytest.raises(FileNotFoundError):
        e.service.asset(e.nid, e.scope, result['output_candidate']['id'])
    assert e.graph.canvas_views.get(e.nid, e.scope, e.actor, e.canvas['id']) == e.canvas


def test_omitted_and_explicit_zero_keep_original_pcm_and_distinct_intent(envelope_canvas, tmp_path):
    e = envelope_canvas
    original_preview = preview(e)
    omitted = run(e, queue(e))
    _, omitted_pcm, _, first = decode(e, omitted)
    assert not {'gain_db', 'fade_in_ms', 'fade_out_ms'}.intersection(omitted['execution_recipe']['parameters'])
    e.command['parameters'].update(gain_db=0, fade_in_ms=0, fade_out_ms=0)
    zero_preview = preview(e)
    assert zero_preview['preview_digest'] != original_preview['preview_digest']
    e.command['request_id'] = 'envelope-explicit-zero'
    zero = run(e, queue(e))
    _, zero_pcm, _, second = decode(e, zero)
    assert zero['request_digest'] != omitted['request_digest']
    assert zero['execution_recipe']['parameters'] == {'in_ms': 200, 'out_ms': 1200,
        'gain_db': 0, 'fade_in_ms': 0, 'fade_out_ms': 0}
    assert omitted_pcm == zero_pcm
    assert all(abs(sample - AMPLITUDE) <= 1 for sample in struct.unpack('<' + 'h' * (len(zero_pcm) // 2), zero_pcm))
    retain(tmp_path, 'explicit-zero-compatibility', {'omitted': first, 'explicit_zero': second,
        'decoded_pcm_equal': omitted_pcm == zero_pcm})


def test_review_exact_return_and_reopen_never_automatically_dispatch(envelope_canvas, monkeypatch):
    e = envelope_canvas
    e.command['parameters'].update(gain_db=-6, fade_in_ms=200, fade_out_ms=300)
    queued = queue(e)
    from app.services import studio_timeline_export as native
    original = native.run_guarded_process
    monkeypatch.setattr(native, 'run_guarded_process', lambda *a, **k: pytest.fail('read/reopen cannot dispatch'))
    e.production = production(e, reopened(e))
    e.graph.configure_media(e.production)
    assert get(e, queued) == queued
    assert e.graph.canvas_views.get(e.nid, e.scope, e.actor, e.canvas['id']) == e.canvas
    monkeypatch.setattr(native, 'run_guarded_process', original)
    candidate = run(e, queued)
    assert candidate['status'] == 'AWAITING_REVIEW'
    assert len(e.service.list_assets(e.nid, e.scope)['items']) == 1
    monkeypatch.setattr(native, 'run_guarded_process', lambda *a, **k: pytest.fail('review/return cannot dispatch'))
    approved = review(e, candidate)
    assert approved['status'] == 'APPROVED' and review(e, approved) == approved
    asset = e.service.asset(e.nid, e.scope, approved['output_candidate']['id'])
    returned = e.graph.canvas_views.save(e.nid, e.scope, e.actor, e.canvas['id'], return_body(e, asset))
    assert returned['version'] == e.canvas['version'] + 1
    assert returned['definition']['cards'][0] == {**e.canvas['definition']['cards'][0], 'asset': reference(asset)}
    assert returned['definition']['cards'][1:] == e.canvas['definition']['cards'][1:]
    for key in set(e.canvas['definition']) - {'cards'}:
        assert returned['definition'][key] == e.canvas['definition'][key]
    e.production = production(e, reopened(e))
    assert get(e, approved) == approved
    assert len(e.service.list_assets(e.nid, e.scope)['items']) == 2


@pytest.mark.parametrize('field,replacement', [('gain_db', -5), ('fade_in_ms', 201), ('fade_out_ms', 301)])
def test_changed_envelope_invalidates_reviewed_preview_without_dispatch(envelope_canvas, monkeypatch, field, replacement):
    e = envelope_canvas
    e.command['parameters'].update(gain_db=-6, fade_in_ms=200, fade_out_ms=300)
    captured = preview(e)
    changed = deepcopy(e.command)
    changed['parameters'][field] = replacement
    from app.services import studio_timeline_export as native
    monkeypatch.setattr(native, 'run_guarded_process', lambda *a, **k: pytest.fail('preview cannot dispatch'))
    assert preview(e, changed)['preview_digest'] != captured['preview_digest']
    with pytest.raises(ValueError):
        e.production.create(e.nid, e.scope, e.actor,
            {'command': changed, 'reviewed_preview_digest': captured['preview_digest']}, lambda: None)
    audio = e.production._audio(e.scope, e.actor)
    assert audio.list(e.nid, e.production._base(e.nid, e.scope, e.actor, lambda: None), lambda: None) == []


@pytest.mark.parametrize('change', ['canvas-version', 'card-deleted', 'source-pin', 'scope', 'incarnation'])
def test_envelope_scope_pin_target_changes_block_original_dispatch(envelope_canvas, monkeypatch, change):
    e = envelope_canvas
    e.command['parameters'].update(gain_db=-6, fade_in_ms=200, fade_out_ms=300)
    if change in {'scope', 'incarnation'}:
        if change == 'scope':
            e.command['canvas_return']['scope'] = {**e.scope, 'workspace_id': 'other'}
        else:
            e.command['canvas_return']['incarnation'] = 'file:00000000-0000-0000-0000-000000000000'
        from app.services import studio_timeline_export as native
        monkeypatch.setattr(native, 'run_guarded_process', lambda *a, **k: pytest.fail('invalid binding cannot dispatch'))
        with pytest.raises((ValueError, StaleSourceError, FileNotFoundError)):
            preview(e)
        return
    queued = queue(e)
    if change == 'source-pin':
        with e.service._asset_scope(e.nid, e.scope):
            e.assets.update_metadata(e.source['id'], {'scene_id': 'new-pin'}, expected_version=e.source['version'])
    else:
        definition = deepcopy(e.canvas['definition'])
        if change == 'card-deleted':
            definition['cards'] = definition['cards'][1:]
        else:
            definition['title'] += ' changed'
        e.graph.canvas_views.save(e.nid, e.scope, e.actor, e.canvas['id'], {'expected_version': e.canvas['version'], 'definition': definition})
    from app.services import studio_timeline_export as native
    monkeypatch.setattr(native, 'run_guarded_process', lambda *a, **k: pytest.fail('stale target cannot dispatch'))
    with pytest.raises((ValueError, StaleSourceError, FileNotFoundError, AudiobookError)):
        run(e, queued)
    assert get(e, queued)['output_candidate'] is None


@pytest.mark.parametrize('change', ['missing-proof', 'false-proof', 'recipe', 'envelope'])
def test_actual_output_proof_and_envelope_binding_are_required(envelope_canvas, change):
    e = envelope_canvas
    e.command['parameters'].update(gain_db=-6, fade_in_ms=200, fade_out_ms=300)
    candidate = run(e, queue(e))
    assert candidate['status'] == 'AWAITING_REVIEW'
    audio = e.production._audio(e.scope, e.actor)
    state = audio.store.load(e.nid, include_studio=True)
    row = state['jobs'][0]
    if change == 'missing-proof':
        row.pop('measured')
    elif change == 'false-proof':
        row['measured']['output_sha256'] = 'f' * 64
    elif change == 'recipe':
        row['context']['execution_recipe']['parameters']['fade_in_ms'] = 201
    else:
        row['context']['command']['parameters']['gain_db'] = -5
    audio.store.save(e.nid, state, include_studio=True)
    with pytest.raises(AudiobookError):
        get(e, candidate)
    with pytest.raises(AudiobookError):
        review(e, candidate)
    assert len(e.service.list_assets(e.nid, e.scope)['items']) == 1


@pytest.mark.parametrize('parameters', [
    {'gain_db': None}, {'gain_db': True}, {'gain_db': '-6'}, {'gain_db': math.nan}, {'gain_db': math.inf},
    {'gain_db': -60.1}, {'gain_db': 12.1}, {'fade_in_ms': None}, {'fade_out_ms': False},
    {'fade_in_ms': 0.5}, {'fade_out_ms': -1}, {'fade_in_ms': 501, 'fade_out_ms': 500},
    {'sample_rate': 48000}, {'channels': 2}, {'output_format': 'WAV'}, {'denoise_profile': None},
    {'target_lufs': -16}, {'target_peak_dbfs': -1}, {'normalize': True},
])
def test_canvas_envelope_contract_stays_closed(envelope_canvas, parameters):
    value = deepcopy(envelope_canvas.command)
    value['parameters'].update(parameters)
    with pytest.raises(ValueError):
        MediaCommand.model_validate(value)
