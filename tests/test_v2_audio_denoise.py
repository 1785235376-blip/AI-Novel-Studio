"""AUDIO-06 fixed FFT profile through original admission/jobs/private review/assets.

Synthetic signal, real CPU FFmpeg and mounted File persistence. No model quality claim.
"""
from copy import deepcopy
import hashlib
import io
import json
import math
import os
from pathlib import Path
import random
import struct
import wave

import pytest
from app.creative.graph_models import MediaNodeParameters
from app.creative.production_execution import ProductionExecutionService
from app.creative.production_execution_models import MediaCommand, MediaParameters
from app.services.audiobook_service import AudiobookError
from app.services.studio_audio_denoise import PROFILE, validate_proof
from app.services.studio_audio_execution import _body
from test_r3_mounted_contracts import checked, mounted, prefix
from test_v2_independent_workspace_api import client
from test_v2_audio_wav_controls_api import audio_client, preview, queue, run, action
from test_v2_audio_wav_controls import command, snapshot
from test_v2_audio_fade_contract import captured
from test_v2_audio_peak_contract import pcm
from test_v2_independent_workspace import upload


def value(**options): return command(in_ms=500, out_ms=4500, denoise_profile=PROFILE, **options)


@pytest.mark.parametrize('options', [
    {'denoise_profile': None}, {'denoise_profile': True}, {'denoise_profile': 'afftdn=nr=90'},
    {'out_ms': 1499}, {'gain_db': 1}, {'fade_in_ms': 1}, {'fade_out_ms': 1},
    {'target_lufs': -23}, {'target_peak_dbfs': -6}, {'output_format': 'FLAC'}, {'output_format': 'MP3'},
])
def test_denoise_rejects_invalid_or_conflicting_requests_before_dispatch(options):
    raw = value(); raw['parameters'].update(options)
    with pytest.raises(ValueError): MediaCommand.model_validate(raw)
    with pytest.raises(AudiobookError): _body({key: val for key, val in raw.items() if key not in {'request_id', 'allow_cloud', 'license_note'}})


def test_fixed_profile_standalone_recipe_and_graph_boundary():
    raw = value(gain_db=0, fade_in_ms=0, fade_out_ms=0)
    projected, _, parsed, _ = captured(raw)
    assert parsed.parameters.denoise_profile == PROFILE
    assert projected['execution_recipe']['parameters']['denoise_profile'] == PROFILE
    assert 'denoise_profile' not in MediaCommand.model_validate(command()).model_dump()['parameters']
    with pytest.raises(ValueError): MediaParameters.model_validate({'denoise_profile': PROFILE})
    with pytest.raises(ValueError): MediaNodeParameters.model_validate({'operation_id': 'm8.audio.trim', 'parameters': raw['parameters']})
    with pytest.raises(ValueError): MediaCommand.model_validate({**raw, 'operation_id': 'm8.audio.music'})
    with pytest.raises(ValueError, match='STUDIO_AUDIO_CONTROLS_STANDALONE_ONLY'):
        object.__new__(ProductionExecutionService).preview('project', {}, 'author', raw, lambda: None, graph_binding={})


def setup(e, **options):
    rate = 16000; rng = random.Random(60119)
    samples = []
    for i in range(rate * 5):
        # The first/last .5s are excluded. In the selected 4s, tone occupies the
        # middle 2s; noise-only tails permit a bounded signal-level assertion.
        tone = 5000 * math.sin(2 * math.pi * 1000 * i / rate) if rate * 1.5 <= i < rate * 3.5 else 0
        samples.append(round(tone + rng.uniform(-220, 220)))
    e.original = pcm(samples, rate)
    e.source = checked(e.client.post(e.studio_base + '/assets', headers=e.headers,
        json=upload(e.original, kind='audio', filename='stationary-noise.wav')), 201)
    e.command = value(sample_rate=rate, channels=1, **options)
    e.command['source_snapshots'] = [snapshot(e.source)]
    return e


def raw_samples(data):
    with wave.open(io.BytesIO(data), 'rb') as reader:
        assert reader.getframerate() == 16000 and reader.getnchannels() == 1 and reader.getsampwidth() == 2
        raw = reader.readframes(reader.getnframes())
    return [item[0] for item in struct.iter_unpack('<h', raw)], raw


def test_real_file_import_denoise_private_candidate_review_saved_asset(audio_client):
    e = setup(audio_client); projected, queued = queue(e)
    assert queued['status'] == 'QUEUED' and queued['media_measurement'] is None
    result = checked(run(e, queued)); assert result['status'] == 'AWAITING_REVIEW', result
    proof = result['media_measurement']['noise_reduction']; candidate = result['output_candidate']
    assert e.client.get(e.studio_base + '/assets/' + candidate['id'], headers=e.headers).status_code == 404
    downloaded = e.client.get(e.base + '/jobs/audio/' + result['id'] + '/candidate', headers=e.headers)
    assert downloaded.status_code == 200
    output, raw = raw_samples(downloaded.content); selected, selected_raw = raw_samples(e.original)
    selected = selected[8000:72000]; selected_raw = selected_raw[16000:144000]
    assert len(output) == len(selected) == proof['selected_frames'] == proof['output_frames'] == 64000
    assert hashlib.sha256(raw).hexdigest() == proof['output_pcm_sha256']
    assert hashlib.sha256(selected_raw).hexdigest() == proof['selected_pcm_sha256']
    assert hashlib.sha256(downloaded.content).hexdigest() == proof['output_sha256'] == candidate['digest']
    assert downloaded.headers['x-asset-sha256'] == proof['output_sha256']
    assert downloaded.headers['cache-control'] == 'no-store'
    def rms(samples): return math.sqrt(sum(x*x for x in samples) / len(samples))
    # Genuine filter execution: less stationary noise, while preserving a tone;
    # this is a synthetic level check, not a real speech/quality acceptance.
    assert rms(output[56000:64000]) < rms(selected[56000:64000]) * 0.8
    assert rms(output[24000:40000]) > rms(selected[24000:40000]) * 0.7
    assert e.client.get(e.studio_base + '/assets/' + e.source['id'] + '/download', headers=e.headers).content == e.original
    validate_proof(proof, e.command['parameters'], candidate['digest'], e.command['source_snapshots'][0])
    for key in ('source_sha256', 'output_sha256', 'selected_frames', 'profile', 'output_rms_s16'):
        bad = deepcopy(proof)
        bad[key] = 'b' * 64 if key.endswith('sha256') else 'wrong' if key == 'profile' else float('nan') if key.endswith('s16') else bad[key] + 1
        with pytest.raises(AudiobookError): validate_proof(bad, e.command['parameters'], candidate['digest'], e.command['source_snapshots'][0])
    approved = checked(e.client.post(e.base + '/jobs/audio/' + result['id'] + '/review', headers=e.headers,
        json={**action(result), 'reviewed_output_digest': candidate['digest']}))
    assert approved['status'] == 'APPROVED' and approved['media_measurement'] == result['media_measurement']
    asset = checked(e.client.get(e.studio_base + '/assets/' + candidate['id'], headers=e.headers))
    assert asset['provenance']['origin'] == 'DERIVED_PROCESSING'
    assert [parent['id'] for parent in asset['provenance']['parents']] == [e.source['id']]
    assert e.client.get(e.studio_base + '/assets/' + candidate['id'] + '/download', headers=e.headers).content == downloaded.content
    assert checked(e.client.get(e.base + '/jobs/audio/' + result['id'], headers=e.headers)) == approved
    folder = os.environ.get('DENOISE_EVIDENCE_DIR')
    if folder:
        folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
        (folder / 'actual-file.json').write_text(json.dumps({'command': e.command, 'source': e.source, 'preview': projected,
            'queued': queued, 'executed': result, 'approved': approved, 'asset': asset}, indent=2), encoding='utf-8')
        (folder / 'source.wav').write_bytes(e.original)
        (folder / 'denoised.wav').write_bytes(downloaded.content)


def test_denoise_observes_original_host_fence_after_actual_filter(audio_client, monkeypatch):
    e = setup(audio_client); _, queued = queue(e)
    import app.services.studio_timeline_export as native
    original = native.run_guarded_process
    def revoked(*args, **kwargs):
        result = original(*args, **kwargs); e.sessions.revoke(e.host); return result
    monkeypatch.setattr(native, 'run_guarded_process', revoked)
    assert run(e, queued).status_code in {401, 403, 404}
    assert len(list(e.assets.root.glob('*.bin'))) == 2
