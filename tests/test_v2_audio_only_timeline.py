"""Independent audio timelines using actual File/PG owners and CPU PCM proof.

Synthetic owned tones only. This is not browser, Windows, microphone, model,
quality or whole-V2 acceptance. Every output is decoded and spectrally checked.
"""
from copy import deepcopy
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import wave

import pytest

from app.experimental.common import StaleSourceError
from app.services.studio_timeline_edit import apply_timeline_edits
from app.services.studio_timeline_export import (compiler_profile, normalize_export_profile,
    validate_export_admission, export_profile_digest, bound_timeline_output_kind, probe_media_file)
from app.services.studio_timeline_render import normalize_studio_timeline, timeline_digest
from test_v2_independent_workspace import rig, import_asset, reopened
from test_v2_audio_editing_pipeline import production, source, edit_body
from test_v2_audio_wav_controls import action

PROFILE = {'preset': 'AUDIO_WAV_PCM16'}
CAP = 25 * 1024 * 1024


def tone(frequency, duration_ms=2000):
    out = io.BytesIO()
    with wave.open(out, 'wb') as writer:
        writer.setnchannels(1); writer.setsampwidth(2); writer.setframerate(48000)
        writer.writeframes(b''.join(struct.pack('<h', round(4000 * math.sin(2 * math.pi * frequency * i / 48000)))
            for i in range(duration_ms * 48)))
    return out.getvalue()


def timeline(first, second):
    return {'schema_version': 3, 'media_kind': 'AUDIO', 'duration_ms': 2000, 'tracks': [
        {'id': 'voice', 'kind': 'AUDIO', 'order': 0, 'role': 'DIALOGUE', 'clips': [
            {'id': 'low', 'source_snapshot': source(first), 'start_ms': 0, 'in_ms': 0, 'out_ms': 1500}]},
        {'id': 'music', 'kind': 'AUDIO', 'order': 1, 'role': 'MUSIC', 'gain_db': -6, 'clips': [
            {'id': 'high', 'source_snapshot': source(second), 'start_ms': 500, 'in_ms': 200, 'out_ms': 1700}]}]}


@pytest.fixture
def audio_timeline(rig):
    e = rig
    e.service.activate(e.nid, e.scope, e.actor)
    e.first = import_asset(e, data=tone(440), filename='author-440.wav', kind='audio')
    e.second = import_asset(e, data=tone(880), filename='author-880.wav', kind='audio')
    e.production = production(e)
    e.row = e.production.timeline_save(e.nid, e.scope, e.actor, None,
        {'expected_version': 0, 'title': 'Independent two-tone AUDIO', 'timeline': timeline(e.first, e.second)}, lambda: None)
    return e


def reviewed(e):
    return {'expected_version': e.row['version'], 'reviewed_timeline_digest': e.row['timeline_digest']}


def proof(data, path):
    path.write_bytes(data)
    measured = probe_media_file(path, guard=lambda: None)
    assert [s['codec_type'] for s in measured['streams']] == ['audio']
    with wave.open(io.BytesIO(data), 'rb') as wav:
        assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth(), wav.getnframes()) == (48000, 2, 2, 96000)
        samples = struct.unpack('<' + 'h' * 192000, wav.readframes(96000))
    assert samples[::2] == samples[1::2]
    mono = samples[::2]
    def amplitude(hz, start_ms, end_ms):
        values = mono[start_ms * 48:end_ms * 48]
        return 2 * abs(sum(v * complex(math.cos(2*math.pi*hz*i/48000), math.sin(2*math.pi*hz*i/48000))
            for i, v in enumerate(values))) / len(values)
    early_low, early_high = amplitude(440, 300, 450), amplitude(880, 300, 450)
    mixed_low, mixed_high = amplitude(440, 800, 1100), amplitude(880, 800, 1100)
    late_low, late_high = amplitude(440, 1650, 1800), amplitude(880, 1650, 1800)
    assert early_low > 1000 and early_high < 15
    assert mixed_low > 1000 and mixed_high > 700
    assert late_low < 15 and late_high > 700
    assert mixed_low / mixed_high == pytest.approx(10 ** (3 / 20), rel=.02)
    assert mixed_low == pytest.approx(4000 / math.sqrt(2) * 10 ** (-3 / 20), rel=.02)
    assert amplitude(440, 5, 25) < early_low / 3
    assert amplitude(440, 1460, 1490) < early_low / 2
    assert len(data) == 44 + 96000 * 4
    return {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data), 'samples': 96000,
        'mix_440_amplitude': mixed_low, 'mix_880_amplitude': mixed_high, 'video_streams': 0}


def test_audio_edit_reopen_actual_playback_wav_review_and_export(audio_timeline, tmp_path):
    e = audio_timeline
    e.row = e.production.timeline_edit(e.nid, e.scope, e.actor, e.row['id'], edit_body(e.row, [
        {'op': 'clip.trim', 'clip_id': 'low', 'in_ms': 100, 'out_ms': 1600, 'ripple': False},
        {'op': 'clip.update', 'clip_id': 'low', 'changes': {'gain_db': -3, 'fade_in_ms': 100, 'fade_out_ms': 100}},
        {'op': 'clip.update', 'clip_id': 'high', 'changes': {'fade_in_ms': 100, 'fade_out_ms': 100}},
    ], 'audio-edit'), lambda: None)
    fresh = production(e, reopened(e))
    assert fresh.timeline_get(e.nid, e.scope, e.actor, e.row['id'], lambda: None) == e.row
    assert set(e.row['timeline']) == {'schema_version', 'media_kind', 'duration_ms', 'tracks'}
    preview = fresh.timeline_playback_preview(e.nid, e.scope, e.actor, e.row['id'], reviewed(e), lambda: None)
    assert preview['cache_state'] == 'MISSING' and preview['job'] is None
    assert preview['export_preview']['export_profile'] == PROFILE
    assert not fresh.list(e.nid, e.scope, e.actor, lambda: None)['items']
    built = fresh.timeline_playback_build(e.nid, e.scope, e.actor, e.row['id'],
        {**reviewed(e), 'reviewed_playback_digest': preview['playback_digest']}, lambda: None)
    job = built['job']; assert job['status'] == 'SUCCEEDED', job
    assert job['output_candidate']['kind'] == 'audio'
    assert job['execution_recipe']['export_profile'] == PROFILE
    assert job['media_measurement']['sample_count'] == 96000
    assert not {'width', 'height', 'fps', 'video_codec'} & set(job['media_measurement'])
    with pytest.raises(FileNotFoundError): e.service.asset(e.nid, e.scope, job['output_candidate']['id'])
    asset, data = fresh.candidate(e.nid, e.scope, e.actor, 'timeline', job['id'], lambda: None)
    assert asset['media_type'] == 'audio/wav'
    measured = proof(data, tmp_path / 'actual-mixed.wav')
    attested = fresh.timeline_playback_attest(e.nid, e.scope, e.actor, e.row['id'], {
        **reviewed(e), 'reviewed_playback_digest': preview['playback_digest'],
        'expected_job_version': job['version'], 'expected_request_digest': job['request_digest']}, lambda: None)
    assert attested['sha256'] == measured['sha256'] and attested['media_type'] == 'audio/wav'
    # Stable cache replay is the same original job, never a second mix.
    again = fresh.timeline_playback_build(e.nid, e.scope, e.actor, e.row['id'],
        {**reviewed(e), 'reviewed_playback_digest': preview['playback_digest']}, lambda: None)
    assert again['job']['id'] == job['id'] and len(fresh.list(e.nid, e.scope, e.actor, lambda: None)['items']) == 1
    approved = fresh.review(e.nid, e.scope, e.actor, 'timeline', job['id'], action(job, True), lambda: None)
    assert approved['status'] == 'APPROVED' and approved['approved_asset_version'] == 2
    formal = reopened(e).asset(e.nid, e.scope, job['output_candidate']['id'])
    assert formal['kind'] == 'audio' and formal['sha256'] == measured['sha256']
    _, output = production(e, reopened(e)).candidate(e.nid, e.scope, e.actor, 'timeline', job['id'], lambda: None)
    assert output == data
    (tmp_path / 'actual-audio-proof.json').write_text(json.dumps(measured, indent=2))


def test_audio_publication_unknown_recovers_original_kind_without_render_replay(audio_timeline, monkeypatch):
    e = audio_timeline; original = e.assets.create; published = []
    def interrupted(*args, **kwargs):
        result = original(*args, **kwargs)
        if str(args[1]).startswith('studio-timeline-'):
            published.append(result)
            raise OSError('owned synthetic post-publication interruption')
        return result
    monkeypatch.setattr(e.assets, 'create', interrupted)
    body = {**reviewed(e), 'request_id': 'audio-unknown'}
    job = e.production.timeline_render(e.nid, e.scope, e.actor, e.row['id'], body, lambda: None)
    assert job['status'] == 'UNKNOWN' and job['output_candidate'] is None
    assert len(published) == 1 and published[0]['kind'] == 'audio'
    repeated = e.production.timeline_render(e.nid, e.scope, e.actor, e.row['id'], body, lambda: None)
    assert repeated['id'] == job['id'] and repeated['status'] == 'UNKNOWN' and len(published) == 1
    recovered = e.production.reconcile(e.nid, e.scope, e.actor, 'timeline', repeated['id'], action(repeated), lambda: None)
    assert recovered['status'] == 'SUCCEEDED' and recovered['output_candidate']['kind'] == 'audio'
    approved = e.production.review(e.nid, e.scope, e.actor, 'timeline', recovered['id'], action(recovered, True), lambda: None)
    assert approved['status'] == 'APPROVED' and len(published) == 1


def test_audio_original_cas_lock_and_stale_source_protect_preview(audio_timeline):
    e = audio_timeline; old = e.row
    locked = e.production.timeline_edit(e.nid, e.scope, e.actor, old['id'], edit_body(old,
        [{'op': 'track.update', 'track_id': 'voice', 'changes': {'locked': True}}]), lambda: None)
    with pytest.raises(ValueError, match='TRACK_LOCKED'):
        e.production.timeline_edit(e.nid, e.scope, e.actor, old['id'], edit_body(locked,
            [{'op': 'clip.update', 'clip_id': 'low', 'changes': {'gain_db': -2}}], 'locked'), lambda: None)
    with pytest.raises(StaleSourceError):
        e.production.timeline_playback_preview(e.nid, e.scope, e.actor, old['id'], reviewed(e), lambda: None)
    e.row = locked
    with e.service._asset_scope(e.nid, e.scope):
        e.assets.update_metadata(e.first['id'], {'scene_id': 'changed'}, expected_version=e.first['version'])
    with pytest.raises(StaleSourceError):
        e.production.timeline_playback_preview(e.nid, e.scope, e.actor, old['id'], reviewed(e), lambda: None)
    assert not e.production.list(e.nid, e.scope, e.actor, lambda: None)['items']


def bare():
    asset = {'id': 'tone', 'kind': 'audio', 'version': 1, 'sha256': 'a' * 64}
    return timeline(asset, {**asset, 'id': 'other'})


@pytest.mark.file_backend_only
@pytest.mark.parametrize('field,value', [('width', 640), ('height', 360), ('fps', 24), ('captions', []), ('schema_version', 2), ('media_kind', 'VIDEO')])
def test_audio_closed_shape_rejects_video_and_unknown_fields(field, value):
    row = bare(); row[field] = value
    with pytest.raises(ValueError): normalize_studio_timeline(row)


@pytest.mark.file_backend_only
@pytest.mark.parametrize('field,value', [('x', 0), ('opacity', 1), ('include_audio', False), ('crop', {}), ('transition_out', {})])
def test_audio_clip_rejects_all_video_only_fields(field, value):
    row = bare(); row['tracks'][0]['clips'][0][field] = value
    with pytest.raises(ValueError): normalize_studio_timeline(row)


@pytest.mark.file_backend_only
def test_audio_profile_sample_budget_exact_kind_and_legacy_digests():
    row = normalize_studio_timeline(bare())
    assert normalize_studio_timeline(row) == row
    assert compiler_profile(PROFILE, duration_ms=2000, max_bytes=CAP)['estimated_max_bytes'] == 384044
    boundary = (CAP - 44) // 192
    assert compiler_profile(PROFILE, duration_ms=boundary, max_bytes=CAP)['estimated_max_bytes'] <= CAP
    with pytest.raises(ValueError, match='BYTES_BUDGET_EXCEEDED'): compiler_profile(PROFILE, duration_ms=boundary+1, max_bytes=CAP)
    with pytest.raises(ValueError): normalize_export_profile({**PROFILE, 'sample_rate': 44100})
    with pytest.raises(ValueError, match='MEDIA_KIND_MISMATCH'): validate_export_admission(row, {'preset': 'REVIEW_MP4'}, CAP)
    assert bound_timeline_output_kind({'export_profile': PROFILE, 'export_profile_digest': export_profile_digest(PROFILE)}) == 'audio'
    assert bound_timeline_output_kind({'kind': 'audio'}) == 'video'
    with pytest.raises(ValueError): bound_timeline_output_kind({'export_profile': PROFILE, 'export_profile_digest': '0' * 64})
    fixture = json.loads((Path(__file__).resolve().parents[1] / 'frontend/src/creative/fixtures/phase5.capture.timeline-created.json').read_text())['timeline']
    normalized = normalize_studio_timeline(fixture['timeline'])
    assert normalized == fixture['timeline'] and timeline_digest(normalized) == fixture['timeline_digest']
    with pytest.raises(ValueError, match='MEDIA_KIND_MISMATCH'): validate_export_admission(normalized, PROFILE, CAP)
    for version in (None, 2):
        audio = bare(); audio.pop('media_kind')
        if version: audio['schema_version'] = version
        else:
            audio.pop('schema_version')
            for track in audio['tracks']: track.pop('role', None)
        with pytest.raises(ValueError, match='VIDEO_TRACK_REQUIRED'): normalize_studio_timeline(audio)
    with pytest.raises(ValueError): apply_timeline_edits(row, [{'op': 'caption.insert', 'caption': {'start_ms': 0, 'end_ms': 10, 'text': 'no'}}])


def test_audio_all_muted_is_exact_silence_without_any_video_input_or_map(audio_timeline, monkeypatch):
    e = audio_timeline
    e.row = e.production.timeline_edit(e.nid, e.scope, e.actor, e.row['id'], edit_body(e.row,
        [{'op': 'track.update', 'track_id': identity, 'changes': {'muted': True}} for identity in ('voice', 'music')]), lambda: None)
    from app.services import studio_timeline_export as native
    run = native.run_guarded_process; commands = []
    def observe(arguments, **kwargs):
        if Path(arguments[0]).name == 'ffmpeg' and str(arguments[-1]).endswith('timeline.wav'): commands.append(arguments)
        return run(arguments, **kwargs)
    monkeypatch.setattr(native, 'run_guarded_process', observe)
    job = e.production.timeline_render(e.nid, e.scope, e.actor, e.row['id'],
        {**reviewed(e), 'request_id': 'all-muted'}, lambda: None)
    assert job['status'] == 'SUCCEEDED' and len(commands) == 1
    assert '-vn' in commands[0] and '-pix_fmt' not in commands[0]
    assert not any('color=c=' in str(arg) or '[vbase]' in str(arg) for arg in commands[0])
    _, data = e.production.candidate(e.nid, e.scope, e.actor, 'timeline', job['id'], lambda: None)
    with wave.open(io.BytesIO(data), 'rb') as wav:
        assert wav.getnframes() == 96000 and not any(wav.readframes(96000))


@pytest.mark.parametrize('change', ['source', 'cancel'])
def test_audio_actual_native_finish_respects_original_source_and_cancel_fences(audio_timeline, monkeypatch, change):
    e = audio_timeline
    from app.services import studio_timeline_export as native
    run = native.run_guarded_process; observed = []
    def interrupt(arguments, **kwargs):
        result = run(arguments, **kwargs)
        if Path(arguments[0]).name == 'ffmpeg' and str(arguments[-1]).endswith('timeline.wav'):
            observed.append(True)
            if change == 'source':
                with e.service._asset_scope(e.nid, e.scope):
                    e.assets.update_metadata(e.first['id'], {'scene_id': 'changed-during-render'}, expected_version=e.first['version'])
            else:
                job = e.production.list(e.nid, e.scope, e.actor, lambda: None)['items'][0]
                assert e.production.cancel(e.nid, e.scope, e.actor, 'timeline', job['id'], action(job), lambda: None)['status'] == 'CANCELLED'
        return result
    monkeypatch.setattr(native, 'run_guarded_process', interrupt)
    job = e.production.timeline_render(e.nid, e.scope, e.actor, e.row['id'],
        {**reviewed(e), 'request_id': 'native-fence'}, lambda: None)
    assert observed == [True] and job['status'] == ('FAILED' if change == 'source' else 'CANCELLED')
    assert job['output_candidate'] is None and len(e.service.list_assets(e.nid, e.scope)['items']) == 2
