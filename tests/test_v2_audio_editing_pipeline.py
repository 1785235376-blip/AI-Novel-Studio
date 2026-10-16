"""Real bounded CPU postproduction through original owners, never model acceptance.

The only media is a 64x64 color clip and an author-created sine wave. Native
encoding, FLAC decoding, mixing, video decoding, private publication, explicit
review and reopen all use the original production/Asset/Timeline services.
"""
from copy import deepcopy
import hashlib
import io
import math
import shutil
import struct
import wave

import pytest

from app.audio_production_store import AudioProductionStore
from app.creative.production_execution import ProductionExecutionService, digest
from app.creative.production_execution_models import MediaReview
from app.experimental.common import StaleSourceError
from app.services.image_job_service import ImageJobService
from app.services.studio_timeline_export import probe_media_file, run_guarded_process
from app.services.video_assembly_service import VideoAssemblyService
from test_v2_independent_workspace import rig, import_asset, reopened
from test_v2_audio_wav_controls import NoControl, command, action


def audible_wav():
    output = io.BytesIO()
    with wave.open(output, 'wb') as writer:
        writer.setnchannels(1); writer.setsampwidth(2); writer.setframerate(16000)
        writer.writeframes(b''.join(struct.pack('<h', round(5000 * math.sin(2 * math.pi * 440 * frame / 16000)))
                                    for frame in range(16000)))
    return output.getvalue()


def cpu_video(path, color='blue'):
    assert shutil.which('ffmpeg') and shutil.which('ffprobe'), 'real CPU media tools are required'
    run_guarded_process([shutil.which('ffmpeg'), '-nostdin', '-v', 'error', '-threads', '1',
        '-f', 'lavfi', '-i', f'color=c={color}:s=64x64:r=10:d=1', '-an', '-c:v', 'mpeg4',
        '-threads', '1', '-y', str(path)], cwd=path.parent, guard=lambda: None, timeout=20)
    return path.read_bytes()


def source(row):
    return {'kind': 'ASSET', 'asset_kind': row['kind'], 'id': row['id'], 'version': row['version'], 'digest': row['sha256']}


def production(e, workspace=None):
    workspace = workspace or e.service
    return ProductionExecutionService(workspace, ImageJobService(e.root), NoControl(),
        VideoAssemblyService(e.root, workspace.assets), {}, {}, AudioProductionStore(e.root / 'audio-production'),
        NoControl(), NoControl())


def timeline(video):
    return {'schema_version': 2, 'duration_ms': 1000, 'width': 64, 'height': 64, 'fps': 10,
        'tracks': [{'id': 'picture', 'kind': 'VIDEO', 'order': 0, 'clips': [
            {'id': 'picture-one', 'source_snapshot': source(video), 'start_ms': 0, 'in_ms': 0, 'out_ms': 1000}]}], 'captions': []}


def edit_body(row, operations, request_id='phase6-edit'):
    return {'expected_version': row['version'], 'reviewed_timeline_digest': row['timeline_digest'],
            'request_id': request_id, 'operations': operations}


def audio_insert(audio):
    return [{'op': 'track.insert', 'track': {'id': 'dialogue', 'kind': 'AUDIO', 'order': 1, 'clips': [], 'role': 'DIALOGUE'}},
            {'op': 'clip.insert', 'track_id': 'dialogue', 'clip': {'id': 'voice-one', 'source_snapshot': source(audio),
                'start_ms': 0, 'in_ms': 0, 'out_ms': 800, 'fade_in_ms': 20, 'fade_out_ms': 20}}]


def trimmed(e):
    value = command(source(e.audio_source), in_ms=100, out_ms=900, output_format='FLAC', sample_rate=22050, channels=1)
    p = e.production.preview(e.nid, e.scope, e.actor, value, lambda: None)[0]
    queued = e.production.create(e.nid, e.scope, e.actor,
        {'command': value, 'reviewed_preview_digest': p['preview_digest']}, lambda: None)
    ready = e.production.execute(e.nid, e.scope, e.actor, 'audio', queued['id'], action(queued), lambda: None)
    assert ready['status'] == 'AWAITING_REVIEW', ready
    with pytest.raises(FileNotFoundError): e.service.asset(e.nid, e.scope, ready['output_candidate']['id'])
    approved = e.production.review(e.nid, e.scope, e.actor, 'audio', ready['id'], action(ready, True), lambda: None)
    assert approved['status'] == 'APPROVED' and approved['media_measurement']['container'] == 'flac'
    return e.service.asset(e.nid, e.scope, approved['output_candidate']['id']), approved


@pytest.fixture
def editing(rig, tmp_path):
    e = rig
    e.service.activate(e.nid, e.scope, e.actor)
    e.video_data = cpu_video(tmp_path / 'author-blue.mp4')
    e.video_source = import_asset(e, data=e.video_data, filename='synthetic-blue.mp4', kind='video')
    e.audio_source = import_asset(e, data=audible_wav(), filename='synthetic-sine.wav', kind='audio')
    e.production = production(e)
    e.timeline = e.production.timeline_save(e.nid, e.scope, e.actor, None,
        {'expected_version': 0, 'title': 'SYNTHETIC CPU postproduction', 'timeline': timeline(e.video_source)}, lambda: None)
    return e


def measured_output(data, path):
    """Independently decode the actual composed bytes, not requested settings."""
    path.write_bytes(data)
    probe = probe_media_file(path, guard=lambda: None)
    picture = next(stream for stream in probe['streams'] if stream['codec_type'] == 'video')
    audio = next(stream for stream in probe['streams'] if stream['codec_type'] == 'audio')
    assert (picture['width'], picture['height']) == (64, 64)
    assert (int(audio['sample_rate']), audio['channels']) == (48000, 2)
    frames = path.with_suffix('.rgb')
    run_guarded_process([shutil.which('ffmpeg'), '-nostdin', '-v', 'error', '-threads', '1',
        '-protocol_whitelist', 'file,pipe', '-i', str(path), '-map', '0:v:0', '-frames:v', '10',
        '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-threads', '1', '-y', str(frames)],
        cwd=path.parent, guard=lambda: None, timeout=20)
    pixels = frames.read_bytes()
    assert len(pixels) == 64 * 64 * 3 * 10
    center = (32 * 64 + 32) * 3
    assert all(pixels[index + center + 2] > 200 and pixels[index + center] < 20
               for index in range(0, len(pixels), 64 * 64 * 3))
    decoded = path.with_suffix('.decoded.wav')
    run_guarded_process([shutil.which('ffmpeg'), '-nostdin', '-v', 'error', '-threads', '1',
        '-protocol_whitelist', 'file,pipe', '-i', str(path), '-map', '0:a:0', '-c:a', 'pcm_s16le',
        '-threads', '1', '-y', str(decoded)], cwd=path.parent, guard=lambda: None, timeout=20)
    with wave.open(str(decoded), 'rb') as result:
        assert (result.getframerate(), result.getnchannels(), result.getsampwidth()) == (48000, 2, 2)
        assert 48000 <= result.getnframes() <= 50000
        samples = struct.unpack('<' + 'h' * (result.getnframes() * 2), result.readframes(result.getnframes()))
    assert max(abs(sample) for sample in samples[4800:48000]) > 1000
    assert sum(sample * sample for sample in samples[4800:48000]) / len(samples[4800:48000]) > 100000
    return {'decoded_frames': 10, 'sample_rate': 48000, 'channels': 2,
            'output_sha256': hashlib.sha256(data).hexdigest(), 'decoded_pcm_sha256': hashlib.sha256(decoded.read_bytes()).hexdigest()}


@pytest.mark.parametrize('export', [False, True])
def test_real_flac_formal_asset_atomic_edit_cpu_render_review_bytes_and_reopen(editing, tmp_path, export):
    e = editing; audio, audio_job = trimmed(e)
    assert audio['version'] == audio_job['approved_asset_version'] == 2
    body = edit_body(e.timeline, audio_insert(audio))
    row = e.production.timeline_edit(e.nid, e.scope, e.actor, e.timeline['id'], body, lambda: None)
    assert row['version'] == 2 and row['edit_receipt']['request_digest'] == digest(body)
    assert e.production.timeline_edit(e.nid, e.scope, e.actor, row['id'], body, lambda: None) == row
    render_body = {'expected_version': row['version'], 'reviewed_timeline_digest': row['timeline_digest'],
                   'request_id': 'phase6-actual-export' if export else 'phase6-actual-render'}
    if export:
        render_body['export_profile'] = {'preset': 'DELIVERY_H264_MP4'}
        preview = e.production.timeline_export_preview(e.nid, e.scope, e.actor, row['id'],
            {key: value for key, value in render_body.items() if key != 'request_id'}, lambda: None)
        render_body['reviewed_export_digest'] = preview['preview_digest']
        render = e.production.timeline_export
    else: render = e.production.timeline_render
    created_job = render(e.nid, e.scope, e.actor, row['id'], render_body, lambda: None)
    assert created_job['status'] == 'SUCCEEDED', created_job
    job = e.production.get(e.nid, e.scope, e.actor, 'timeline', created_job['id'], lambda: None)
    # Original GET adds execution/reconciliation projection fields; it does
    # not change the durable exact receipt or cause another native render.
    assert {key: job[key] for key in ('id', 'version', 'request_digest', 'receipt_digest', 'status', 'output_candidate', 'media_measurement')} == {
        key: created_job[key] for key in ('id', 'version', 'request_digest', 'receipt_digest', 'status', 'output_candidate', 'media_measurement')}
    assert render(e.nid, e.scope, e.actor, row['id'], render_body, lambda: None) == job
    measurement = job['media_measurement']
    assert measurement['profile_validation'] == 'NATIVE_FFPROBE_EXACT'
    assert (measurement['width'], measurement['height'], measurement['fps'], measurement['sample_rate'], measurement['channels']) == (64, 64, 10, 48000, 2)
    candidate = job['output_candidate']
    with pytest.raises(FileNotFoundError): e.service.asset(e.nid, e.scope, candidate['id'])
    _, data = e.production.candidate(e.nid, e.scope, e.actor, 'timeline', job['id'], lambda: None)
    proof = measured_output(data, tmp_path / 'actual-composed.mp4')
    assert proof['output_sha256'] == candidate['digest'] and len(data) == measurement['byte_count']
    reviewed_response = e.production.review(e.nid, e.scope, e.actor, 'timeline', job['id'], action(job, True), lambda: None)
    assert reviewed_response['status'] == 'APPROVED' and reviewed_response['approved_asset_version'] == 2
    reviewed = e.production.get(e.nid, e.scope, e.actor, 'timeline', job['id'], lambda: None)
    projected = {'execution_state', 'needs_reconciliation'}
    assert {key: value for key, value in reviewed.items() if key not in projected} == {
        key: value for key, value in reviewed_response.items() if key not in projected}
    assert e.production.review(e.nid, e.scope, e.actor, 'timeline', job['id'], action(reviewed, True), lambda: None) == reviewed
    fresh = reopened(e); reopened_production = production(e, fresh)
    assert reopened_production.timeline_get(e.nid, e.scope, e.actor, row['id'], lambda: None) == row
    assert reopened_production.get(e.nid, e.scope, e.actor, 'timeline', job['id'], lambda: None) == reviewed
    assert fresh.asset(e.nid, e.scope, candidate['id'])['version'] == 2
    with fresh._asset_scope(e.nid, e.scope):
        assert fresh.assets.content(candidate['id'], branch_id=e.scope.get('branch_id')) == data


def test_original_atomic_source_edit_unknown_receipt_cas_lock_and_restore(editing):
    e = editing; audio, _ = trimmed(e)
    original = deepcopy(e.timeline); body = edit_body(original, audio_insert(audio))
    edited = e.production.timeline_edit(e.nid, e.scope, e.actor, original['id'], body, lambda: None)
    # Lost response: read proves this full original request, not just effect.
    current = e.production.timeline_get(e.nid, e.scope, e.actor, original['id'], lambda: None)
    assert current == edited and current['edit_receipt'] == {'request_id': body['request_id'], 'request_digest': digest(body),
        'input_version': 1, 'input_digest': original['timeline_digest'], 'output_digest': edited['timeline_digest']}
    with pytest.raises(StaleSourceError):
        e.production.timeline_edit(e.nid, e.scope, e.actor, original['id'], edit_body(original,
            [{'op': 'clip.update', 'clip_id': 'picture-one', 'changes': {'muted': True}}], 'stale-edit'), lambda: None)
    assert e.production.timeline_get(e.nid, e.scope, e.actor, original['id'], lambda: None) == edited
    locked = e.production.timeline_edit(e.nid, e.scope, e.actor, original['id'], edit_body(edited,
        [{'op': 'track.update', 'track_id': 'dialogue', 'changes': {'locked': True}}], 'lock-dialogue'), lambda: None)
    with pytest.raises(ValueError, match='TRACK_LOCKED'):
        e.production.timeline_edit(e.nid, e.scope, e.actor, original['id'], edit_body(locked,
            [{'op': 'clip.update', 'clip_id': 'voice-one', 'changes': {'muted': True}}], 'locked-edit'), lambda: None)
    unlocked = e.production.timeline_edit(e.nid, e.scope, e.actor, original['id'], edit_body(locked,
        [{'op': 'track.update', 'track_id': 'dialogue', 'changes': {'locked': False}}], 'unlock-dialogue'), lambda: None)
    restored = e.production.timeline_restore(e.nid, e.scope, e.actor, original['id'], {
        'expected_version': unlocked['version'], 'reviewed_timeline_digest': unlocked['timeline_digest'],
        'restore_version': original['version'], 'restore_digest': original['timeline_digest']}, lambda: None)
    assert restored['timeline'] == original['timeline'] and 'edit_receipt' not in restored
    history = e.production.timeline_history(e.nid, e.scope, e.actor, original['id'], lambda: None)
    assert next(item for item in history['items'] if item['version'] == 2)['edit_receipt'] == edited['edit_receipt']
    with pytest.raises(StaleSourceError): e.production.timeline_edit(e.nid, e.scope, e.actor, original['id'], body, lambda: None)


def test_invalid_formal_source_rolls_back_whole_track_insert(editing):
    e = editing; audio, _ = trimmed(e)
    operations = audio_insert(audio); operations[1]['clip']['source_snapshot']['version'] += 1
    with pytest.raises(StaleSourceError):
        e.production.timeline_edit(e.nid, e.scope, e.actor, e.timeline['id'], edit_body(e.timeline, operations), lambda: None)
    assert e.production.timeline_get(e.nid, e.scope, e.actor, e.timeline['id'], lambda: None) == e.timeline
    assert e.production.timeline_history(e.nid, e.scope, e.actor, e.timeline['id'], lambda: None)['items'] == []


def test_real_native_render_source_change_blocks_private_publication_outside_asset_phase(editing, monkeypatch):
    e = editing; audio, _ = trimmed(e)
    row = e.production.timeline_edit(e.nid, e.scope, e.actor, e.timeline['id'], edit_body(e.timeline, audio_insert(audio)), lambda: None)
    from app.services import studio_timeline_export as native
    original = native.run_guarded_process; observed = []
    def changed(arguments, **kwargs):
        assert not e.production.timeline_inputs.in_phase(e.nid, e.scope, e.actor)
        assert getattr(e.assets._scope, 'binding', None) is None
        result = original(arguments, **kwargs)
        if str(arguments[-1]).endswith('timeline.mp4'):
            observed.append(True)
            with e.service._asset_scope(e.nid, e.scope):
                e.assets.update_metadata(e.video_source['id'], {'scene_id': 'author-changed'}, expected_version=e.video_source['version'])
        return result
    monkeypatch.setattr(native, 'run_guarded_process', changed)
    job = e.production.timeline_render(e.nid, e.scope, e.actor, row['id'], {'expected_version': row['version'],
        'reviewed_timeline_digest': row['timeline_digest'], 'request_id': 'source-change-during-render'}, lambda: None)
    assert observed and job['status'] == 'FAILED' and job['output_candidate'] is None
    assert len(e.service.list_assets(e.nid, e.scope)['items']) == 3


def test_actual_render_cancel_cas_wins_before_private_publication(editing, monkeypatch):
    e = editing; row = e.timeline
    from app.services import studio_timeline_export as native
    original = native.run_guarded_process; observed = []
    def cancelled(arguments, **kwargs):
        result = original(arguments, **kwargs)
        if str(arguments[-1]).endswith('timeline.mp4'):
            jobs = e.production.list(e.nid, e.scope, e.actor, lambda: None)['items']
            current = next(job for job in jobs if job['owner'] == 'timeline')
            assert current['status'] == 'RUNNING'
            result_job = e.production.cancel(e.nid, e.scope, e.actor, 'timeline', current['id'], action(current), lambda: None)
            assert result_job['status'] == 'CANCELLED'; observed.append(True)
        return result
    monkeypatch.setattr(native, 'run_guarded_process', cancelled)
    body = {'expected_version': row['version'], 'reviewed_timeline_digest': row['timeline_digest'], 'request_id': 'phase6-cancel-real-render'}
    job = e.production.timeline_render(e.nid, e.scope, e.actor, row['id'], body, lambda: None)
    assert observed and job['status'] == 'CANCELLED' and job['output_candidate'] is None
    replay = e.production.timeline_render(e.nid, e.scope, e.actor, row['id'], body, lambda: None)
    assert replay['id'] == job['id'] and replay['status'] == 'CANCELLED' and len(observed) == 1
    assert len(e.service.list_assets(e.nid, e.scope)['items']) == 2


def test_actual_private_publication_unknown_is_recovered_without_render_replay(editing, monkeypatch):
    e = editing; row = e.timeline; original = e.assets.create; observed = []
    def interrupted(*args, **kwargs):
        result = original(*args, **kwargs)
        if str(args[1]).startswith('studio-timeline-'):
            observed.append(deepcopy(result))
            raise OSError('synthetic interruption after original private Asset commit')
        return result
    monkeypatch.setattr(e.assets, 'create', interrupted)
    body = {'expected_version': row['version'], 'reviewed_timeline_digest': row['timeline_digest'], 'request_id': 'phase6-publication-unknown'}
    unknown = e.production.timeline_render(e.nid, e.scope, e.actor, row['id'], body, lambda: None)
    assert unknown['status'] == 'UNKNOWN' and unknown['output_candidate'] is None and len(observed) == 1
    with pytest.raises(FileNotFoundError): e.service.asset(e.nid, e.scope, observed[0]['id'])
    replay = e.production.timeline_render(e.nid, e.scope, e.actor, row['id'], body, lambda: None)
    assert replay['status'] == 'UNKNOWN' and replay['id'] == unknown['id'] and len(observed) == 1
    recovered = e.production.reconcile(e.nid, e.scope, e.actor, 'timeline', replay['id'], action(replay), lambda: None)
    assert recovered['status'] == 'SUCCEEDED' and recovered['output_candidate']['id'] == observed[0]['id']
    assert recovered['output_candidate']['digest'] == observed[0]['sha256'] and len(observed) == 1
    approved = e.production.review(e.nid, e.scope, e.actor, 'timeline', recovered['id'], action(recovered, True), lambda: None)
    assert approved['status'] == 'APPROVED' and e.service.asset(e.nid, e.scope, observed[0]['id'])['version'] == 2
