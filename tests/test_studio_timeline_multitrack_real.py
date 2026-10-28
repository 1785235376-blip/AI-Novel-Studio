"""File-owned audio-only Timeline exports with real FFmpeg and decoded tones."""
import hashlib
import io
import json
import math
import os
from pathlib import Path
import struct
import wave

import pytest

from app.services.studio_timeline_export import probe_media_file
from test_studio_canvas_audio_return import rig, import_asset, action
from test_studio_canvas_video_bridge import production


def tone_wav(frequency):
    samples = [int(4000 * math.sin(2 * math.pi * frequency * n / 48000)) for n in range(48000)]
    stereo = b''.join(struct.pack('<hh', sample, sample) for sample in samples)
    output = io.BytesIO()
    with wave.open(output, 'wb') as writer:
        writer.setnchannels(2); writer.setsampwidth(2); writer.setframerate(48000)
        writer.writeframes(stereo)
    return output.getvalue()


def amplitude(samples, frequency):
    size = len(samples)
    real = sum(value * math.cos(2 * math.pi * frequency * n / 48000) for n, value in enumerate(samples))
    imaginary = sum(value * math.sin(2 * math.pi * frequency * n / 48000) for n, value in enumerate(samples))
    return 2 * math.hypot(real, imaginary) / size


@pytest.mark.parametrize('second_muted', [False, True], ids=['mixed', 'muted'])
def test_file_audio_timeline_mixes_and_mutes_pinned_tracks(rig, tmp_path, second_muted):
    e = rig
    e.service.activate(e.nid, e.scope, e.actor)
    originals = {frequency: tone_wav(frequency) for frequency in (440, 880)}
    assets = {frequency: import_asset(e, data=data, filename=f'synthetic-{frequency}.wav', kind='audio')
              for frequency, data in originals.items()}
    def track(frequency, order, muted, gain):
        asset = assets[frequency]
        return {'id': f'track-{frequency}', 'kind': 'AUDIO', 'order': order, 'muted': muted, 'gain_db': gain,
                'clips': [{'id': f'clip-{frequency}', 'source_snapshot': {'kind': 'ASSET', 'asset_kind': 'audio',
                    'id': asset['id'], 'version': asset['version'], 'digest': asset['sha256']},
                    'start_ms': 0, 'in_ms': 0, 'out_ms': 1000}]}
    value = {'schema_version': 3, 'media_kind': 'AUDIO', 'duration_ms': 1000,
             'tracks': [track(440, 0, False, 0), track(880, 1, second_muted, -6.020599913279624)]}
    e.production = production(e)
    saved = e.production.timeline_save(e.nid, e.scope, e.actor, None,
        {'expected_version': 0, 'title': 'Synthetic actual two-track mix', 'timeline': value}, lambda: None)
    body = {'expected_version': saved['version'], 'reviewed_timeline_digest': saved['timeline_digest'],
            'export_profile': {'preset': 'AUDIO_WAV_PCM16'}}
    preview = e.production.timeline_export_preview(e.nid, e.scope, e.actor, saved['id'], body, lambda: None)
    result = e.production.timeline_export(e.nid, e.scope, e.actor, saved['id'],
        {**body, 'request_id': 'synthetic-mix', 'reviewed_export_digest': preview['preview_digest']}, lambda: None)
    assert result['status'] == 'SUCCEEDED' and result['output_candidate']['kind'] == 'audio'
    metadata, data = e.production.candidate(e.nid, e.scope, e.actor, 'timeline', result['id'], lambda: None)
    assert hashlib.sha256(data).hexdigest() == metadata['sha256'] == result['output_candidate']['digest']
    rendered = tmp_path / 'decoded-result.wav'
    rendered.write_bytes(data)
    probe = probe_media_file(rendered, guard=lambda: None)
    streams = [row for row in probe['streams'] if row.get('codec_type') == 'audio']
    assert len(streams) == 1 and streams[0]['codec_name'] == 'pcm_s16le'
    assert int(streams[0]['sample_rate']) == 48000 and streams[0]['channels'] == 2
    with wave.open(io.BytesIO(data), 'rb') as reader:
        assert (reader.getnchannels(), reader.getsampwidth(), reader.getframerate(), reader.getnframes()) == (2, 2, 48000, 48000)
        pcm = struct.unpack('<' + 'h' * 96000, reader.readframes(48000))
    left = pcm[9600:86400:2]  # Exclude the first/last 100 ms.
    levels = {frequency: amplitude(left, frequency) for frequency in (440, 880)}
    assert 3900 < levels[440] < 4100
    assert levels[880] < 15 if second_muted else 1900 < levels[880] < 2100
    approved = e.production.review(e.nid, e.scope, e.actor, 'timeline', result['id'], action(result, True), lambda: None)
    assert approved['status'] == 'APPROVED'
    formal = e.service.asset(e.nid, e.scope, result['output_candidate']['id'])
    assert formal['sha256'] == hashlib.sha256(data).hexdigest()
    with e.service._asset_scope(e.nid, e.scope):
        assert e.service.assets.content(formal['id'], branch_id=e.scope.get('branch_id')) == data
    if directory := os.getenv('STUDIO_M7_MIX_EVIDENCE'):
        root = Path(directory); root.mkdir(parents=True, exist_ok=True)
        label = 'muted' if second_muted else 'mixed'
        for frequency, original in originals.items():
            (root / f'{label}-source-{frequency}.wav').write_bytes(original)
        (root / f'{label}-output.wav').write_bytes(data)
        (root / f'{label}-measurement.json').write_text(json.dumps({
            'source_sha256': {str(key): hashlib.sha256(value).hexdigest() for key, value in originals.items()},
            'output_sha256': hashlib.sha256(data).hexdigest(), 'decoded_frames': 48000,
            'sample_rate': 48000, 'channels': 2, 'ffprobe_codec': streams[0]['codec_name'],
            'amplitude_pcm16': levels, 'second_track_muted': second_muted,
            'second_track_gain_db': -6.020599913279624, 'human_review_simulated': True}, indent=2), encoding='utf-8')
