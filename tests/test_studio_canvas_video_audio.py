"""Source-only CPU checks for the original saved-card video audio bridge.

Short synthetic media only. No recorded output, Host harness, model or provider.
The tone generators/independent measurements are unchanged reviewed helpers.
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
from app.services import studio_timeline_export as native
from test_studio_canvas_audio_return import rig, import_asset, create, reference
from test_studio_canvas_video_bridge import bridge, render_calls, source, definition, _native, preview, queue, execute, get, review, return_result

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

@pytest.fixture
def two_tone_media(tmp_path):
    return _two_tone_video(tmp_path)


@pytest.mark.parametrize('option', [None, False, True], ids=['omitted-silent','explicit-silent','first-source-audio'])
def test_public_canvas_video_audio_native_selection_and_manual_return(bridge, two_tone_media, render_calls, tmp_path, option):
    e = bridge
    media = two_tone_media
    e.source = import_asset(e, data=media.read_bytes(), filename=media.name, kind='video')
    e.canvas = create(e, e.graph, {'title': 'Synthetic source audio task', 'cards': [
        {'id': 'origin-video', 'position': {'x': 44, 'y': 66}, 'asset': reference(e.source)},
        {'id': 'another-video', 'position': {'x': 760, 'y': 120}, 'asset': reference(e.source)}]})
    e.timeline = e.production.timeline_save(e.nid, e.scope, e.actor, e.timeline['id'], {
        'expected_version': e.timeline['version'], 'title': 'Explicit source audio choice',
        'timeline': _timeline(source(e.source), option is True)}, lambda: None)
    parameters = {'in_ms': 1000, 'out_ms': 1600}
    if option is not None: parameters['include_audio'] = option
    e.command.update(parameters=parameters, source_snapshots=[source(e.source)],
        timeline_snapshot={'id': e.timeline['id'], 'version': e.timeline['version'], 'digest': e.timeline['timeline_digest']})
    e.command['canvas_return'].update(canvas_id=e.canvas['id'], canvas_version=e.canvas['version'],
        canvas_digest=e.canvas['definition_digest'], source=source(e.source))
    captured = preview(e); assert captured['command'] == e.command and not render_calls
    assert captured['execution_recipe']['timeline']['tracks'][0]['clips'][0]['include_audio'] is (option is True)
    queued = queue(e, captured=captured); assert queued['status'] == 'QUEUED' and not render_calls
    assert get(e, queued)['canvas_video']['parameters'] == parameters
    candidate = execute(e, queued); assert candidate['status'] == 'SUCCEEDED' and len(render_calls) == 1
    _, data = e.production.candidate(e.nid, e.scope, e.actor, 'timeline', candidate['id'], lambda: None)
    output = tmp_path / 'public-source-audio-output.mp4'; output.write_bytes(data); measured = _audio_proof(output)
    assert measured['sha256'] == candidate['output_candidate']['digest']
    assert (measured['audio_tracks'], measured['codec'], measured['sample_rate'], measured['channels']) == (1, 'aac', 48000, 2)
    if option is True:
        _assert_tone(_audio_proof(media, start_ms=0, duration_ms=600), 440)
        _assert_tone(_audio_proof(media, track=1, start_ms=1000, duration_ms=600), 1320)
        _assert_tone(measured, 880)
    else: assert measured['interior_rms_pcm16'] < 1 and max(measured['amplitudes_pcm16'].values()) < 1
    with pytest.raises(ValueError): execute(e, candidate)
    original = deepcopy(e.canvas['definition']); approved = review(e, candidate); returned = return_result(e, approved)
    assert returned['version'] == e.canvas['version'] + 1
    assert returned['definition']['cards'][0]['position'] == original['cards'][0]['position']
    assert returned['definition']['cards'][1] == original['cards'][1]
    assert get(e, approved)['status'] == 'APPROVED' and len(render_calls) == 1
    _evidence('public-' + str(option).lower() + '.json', {'option': option, 'parameters': parameters, 'output': measured,
        'native_renders': len(render_calls), 'manual_review_and_original_card_return': True, 'model_called': False})
