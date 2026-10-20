"""Original CPU Timeline owner capability probe; NOT a video-card HTTP loop.

Only short synthetic red/blue media. No model/provider/GPU/network. Production
explicitly rejects standalone queued execution; direct owner calls below are
server-only capability evidence and grant no public endpoint or card binding.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil

import pytest

from app.creative.production_execution import digest
from app.creative.production_execution_models import CanvasReturnBinding, MediaCommand
from app.services import studio_timeline_export as native
from app.services.studio_timeline_export import export_profile_digest, probe_media_file
from test_v2_independent_workspace import rig, import_asset, reopened
from test_v2_audio_editing_pipeline import production, source
from test_v2_audio_wav_controls import action


def _native(command, directory):
    native.run_guarded_process(command, cwd=directory, guard=lambda: None, timeout=20)


def _source_video(directory):
    target = directory / 'synthetic-red-blue.mp4'
    _native([shutil.which('ffmpeg'), '-nostdin', '-v', 'error', '-threads', '1',
        '-f', 'lavfi', '-i', 'color=c=red:s=64x64:r=10:d=1',
        '-f', 'lavfi', '-i', 'color=c=blue:s=64x64:r=10:d=1',
        '-filter_complex_threads', '1', '-filter_complex', '[0:v][1:v]concat=n=2:v=1:a=0,format=yuv420p[v]',
        '-map', '[v]', '-an', '-c:v', 'mpeg4', '-threads', '1', '-y', str(target)], directory)
    return target


def _decoded_measurement(path):
    probe = probe_media_file(path, guard=lambda: None)
    picture = next(row for row in probe['streams'] if row['codec_type'] == 'video')
    raw = path.with_suffix('.rgb')
    _native([shutil.which('ffmpeg'), '-nostdin', '-v', 'error', '-threads', '1',
        '-protocol_whitelist', 'file,pipe', '-i', str(path), '-map', '0:v:0', '-an',
        '-fps_mode', 'passthrough', '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-threads', '1', '-y', str(raw)], path.parent)
    data, pixels = path.read_bytes(), raw.read_bytes()
    width, height = picture['width'], picture['height']; frame_bytes = width * height * 3
    assert len(pixels) % frame_bytes == 0
    center = (height // 2 * width + width // 2) * 3
    colors = [list(pixels[offset + center:offset + center + 3]) for offset in range(0, len(pixels), frame_bytes)]
    return {'width': width, 'height': height, 'fps': picture['r_frame_rate'], 'codec': picture['codec_name'],
        'duration_ms': round(float(probe['format']['duration']) * 1000), 'decoded_frames': len(colors),
        'center_rgb': colors, 'byte_count': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def _context(e, request_id):
    # Exact existing standalone export context, assembled by server owners.
    # No Graph binding is invented to bypass the Production.execute rejection.
    preview = e.production.timeline_export_preview(e.nid, e.scope, e.actor, e.timeline['id'], {
        'expected_version': e.timeline['version'], 'reviewed_timeline_digest': e.timeline['timeline_digest'],
        'export_profile': {'preset': 'REVIEW_MP4'}}, lambda: None)
    context = e.production._base(e.nid, e.scope, e.actor, lambda: None)
    context.update(request_id=request_id, operation_id='m9.timeline.multitrack', sources=deepcopy(preview['sources']),
        timeline_snapshot=deepcopy(preview['timeline_snapshot']), provider_binding=None, license_note='', rights={'license_note': ''},
        execution_recipe=deepcopy(preview['execution_recipe']), export_profile=deepcopy(preview['export_profile']),
        export_profile_digest=export_profile_digest(preview['export_profile']), reviewed_export_digest=preview['preview_digest'])
    context['request_digest'] = digest(context)
    return context


def _queue(e, context):
    return e.production.video_owner.queue_studio(e.nid, e.scope.get('branch_id'), e.actor,
        context['execution_recipe']['timeline'], context=context, guard=lambda: None, export_profile=context['export_profile'])


def _owner_execute(e, row, context, *, publish=None):
    publication, _ = e.production._callbacks(e.nid, e.scope, e.actor, context, lambda: None)
    def current():
        actual = e.production.timeline_get(e.nid, e.scope, e.actor, e.timeline['id'], lambda: None)
        assert (actual['version'], actual['timeline_digest']) == (e.timeline['version'], e.timeline['timeline_digest'])
    return e.production.video_owner.execute_studio(e.nid, e.scope.get('branch_id'), e.actor,
        row['id'], row['version'], row['request_digest'], context=context, guard=current,
        source_guard=e.production._source_guard(e.nid, e.scope, lambda: None),
        inspect_source=e.production._source_guard(e.nid, e.scope, lambda: None), publish=publish or publication)


def test_original_single_video_cpu_owner_and_standalone_execution_boundary(rig, tmp_path, monkeypatch):
    e = rig
    assert shutil.which('ffmpeg') and shutil.which('ffprobe'), 'installed CPU media tools are required'
    original_native = native.run_guarded_process
    commands = []
    def observed(command, *args, **kwargs):
        # Preserve actual options; only temporary/executable paths become names.
        commands.append([Path(str(arg)).name if Path(str(arg)).is_absolute() else str(arg) for arg in command])
        return original_native(command, *args, **kwargs)
    monkeypatch.setattr(native, 'run_guarded_process', observed)
    e.service.activate(e.nid, e.scope, e.actor)
    media = _source_video(tmp_path); source_measurement = _decoded_measurement(media)
    assert (source_measurement['decoded_frames'], source_measurement['duration_ms']) == (20, 2000)
    assert all(rgb[0] > 230 and rgb[2] < 20 for rgb in source_measurement['center_rgb'][:10])
    assert all(rgb[2] > 230 and rgb[0] < 20 for rgb in source_measurement['center_rgb'][10:])
    asset = import_asset(e, data=media.read_bytes(), filename='synthetic-red-blue.mp4', kind='video')
    e.production = production(e)
    definition = {'schema_version': 2, 'duration_ms': 600, 'width': 64, 'height': 64, 'fps': 10,
        'tracks': [{'id': 'picture', 'kind': 'VIDEO', 'order': 0, 'clips': [
            {'id': 'selected-blue', 'source_snapshot': source(asset), 'start_ms': 0, 'in_ms': 1000, 'out_ms': 1600,
             'include_audio': False}]}], 'captions': []}
    e.timeline = e.production.timeline_save(e.nid, e.scope, e.actor, None, {
        'expected_version': 0, 'title': 'Synthetic single-video CPU probe', 'timeline': definition}, lambda: None)
    context = _context(e, 'single-video-owner-probe')
    compiled = context['execution_recipe']['timeline']['tracks'][0]['clips'][0]
    assert (compiled['in_ms'], compiled['out_ms'], compiled['start_ms'], compiled['include_audio']) == (1000, 1600, 0, False)
    assert context['sources'] == [source(asset)] and context['provider_binding'] is None
    original = native.run_guarded_process
    monkeypatch.setattr(native, 'run_guarded_process', lambda *a, **k: pytest.fail('queue/reopen/blocked public execute must not run native'))
    queued = _queue(e, context)
    assert queued['status'] == 'QUEUED' and queued['output_candidate'] is None
    assert queued['model_called'] is False and queued['automatic_retry'] is False
    assert _queue(e, context) == queued
    e.production = production(e, reopened(e))
    read = e.production.get(e.nid, e.scope, e.actor, 'timeline', queued['id'], lambda: None)
    assert read['status'] == 'QUEUED' and read['output_candidate'] is None and read['automatic_replay'] is False
    with pytest.raises(ValueError, match='STUDIO_TIMELINE_ALREADY_RENDERED_EXPLICITLY'):
        e.production.execute(e.nid, e.scope, e.actor, 'timeline', queued['id'], action(read), lambda: None)
    assert e.production.get(e.nid, e.scope, e.actor, 'timeline', queued['id'], lambda: None)['version'] == queued['version']
    monkeypatch.setattr(native, 'run_guarded_process', original)
    rendered = _owner_execute(e, queued, context)
    assert rendered['status'] == 'SUCCEEDED' and rendered['model_called'] is False
    candidate = e.production.get(e.nid, e.scope, e.actor, 'timeline', queued['id'], lambda: None)
    assert candidate['command'] is None and candidate['status'] == 'SUCCEEDED'
    with pytest.raises(FileNotFoundError): e.service.asset(e.nid, e.scope, candidate['output_candidate']['id'])
    _, data = e.production.candidate(e.nid, e.scope, e.actor, 'timeline', queued['id'], lambda: None)
    output = tmp_path / 'actual-selected-blue.mp4'; output.write_bytes(data)
    output_measurement = _decoded_measurement(output)
    assert (output_measurement['decoded_frames'], output_measurement['duration_ms']) == (6, 600)
    assert (output_measurement['width'], output_measurement['height'], output_measurement['fps']) == (64, 64, '10/1')
    # Original REVIEW_MP4 compiler explicitly selects MPEG-4/AAC.
    assert context['export_profile'] == {'preset': 'REVIEW_MP4'}
    assert output_measurement['codec'] == 'mpeg4'
    assert all(rgb[2] > 230 and rgb[0] < 20 for rgb in output_measurement['center_rgb'])
    proof = candidate['media_measurement']
    assert proof['duration_ms'] == 600 and proof['profile_validation'] == 'NATIVE_FFPROBE_EXACT'
    assert proof['byte_count'] == len(data) and candidate['output_candidate']['digest'] == output_measurement['sha256']
    monkeypatch.setattr(native, 'run_guarded_process', lambda *a, **k: pytest.fail('repeat/UNKNOWN execute or review must not render'))
    with pytest.raises(ValueError, match='STUDIO_TIMELINE_EXECUTE_NOT_QUEUED'):
        _owner_execute(e, rendered, context)
    uncertain_context = _context(e, 'single-video-unknown-probe')
    uncertain = _queue(e, uncertain_context)
    # Seed an original durable uncertain receipt, without a second render.
    # This proves the existing state gate, not an observed native failure.
    uncertain = e.production.video_owner._studio_mutate(e.nid, e.scope.get('branch_id'), e.actor,
        uncertain['id'], uncertain['version'], lambda row: row.update(status='UNKNOWN', phase='RENDERING', automatic_retry=False), context=uncertain_context)
    with pytest.raises(ValueError, match='STUDIO_TIMELINE_EXECUTE_NOT_QUEUED'):
        _owner_execute(e, uncertain, uncertain_context)
    approved = e.production.review(e.nid, e.scope, e.actor, 'timeline', candidate['id'], action(candidate, True), lambda: None)
    assert approved['status'] == 'APPROVED' and approved['approved_asset_version'] == candidate['output_candidate']['version'] + 1
    formal = e.service.asset(e.nid, e.scope, approved['output_candidate']['id'])
    assert formal['kind'] == 'video' and formal['sha256'] == output_measurement['sha256']
    assert e.production.get(e.nid, e.scope, e.actor, 'timeline', uncertain['id'], lambda: None)['status'] == 'UNKNOWN'
    if os.environ.get('STUDIO_VIDEO_CPU_PROBE_EVIDENCE'):
        evidence = {'contract': 'studio-video-cpu-owner-probe/1', 'model_called': False, 'real_cpu_ffmpeg': True,
            'video_card_http_loop_available': False, 'production_execute_boundary': 'STUDIO_TIMELINE_ALREADY_RENDERED_EXPLICITLY',
            'queue_reopen_executed_native': False, 'source': source_measurement, 'output': output_measurement,
            'selected_range_ms': {'in_ms': 1000, 'out_ms': 1600}, 'output_profile': context['export_profile'],
            'actual_owner_status': rendered['status'], 'actual_measurement': proof, 'review_status': approved['status'],
            'formal_asset': {'id': formal['id'], 'version': formal['version'], 'kind': formal['kind'], 'sha256': formal['sha256']},
            'unknown_was_seeded_without_second_render': True, 'unknown_replay_rejected': True, 'repeat_execute_rejected': True}
        evidence_path = Path(os.environ['STUDIO_VIDEO_CPU_PROBE_EVIDENCE'])
        evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
        evidence_path.with_name('native-commands.json').write_text(json.dumps({
            'path_policy': 'actual argv options; absolute executable/temp paths normalized to basename',
            'commands': commands}, ensure_ascii=False, indent=2), encoding='utf-8')


@pytest.mark.file_backend_only
def test_video_trim_and_video_canvas_return_remain_unimplemented_contracts():
    pin = {'kind': 'ASSET', 'asset_kind': 'video', 'id': 'synthetic-video', 'version': 1, 'digest': 'a' * 64}
    with pytest.raises(ValueError):
        MediaCommand.model_validate({'operation_id': 'm7.video.trim', 'request_id': 'unsupported-trim', 'provider_id': None,
            'model_id': None, 'prompt': '', 'parameters': {'in_ms': 1000, 'out_ms': 1600},
            'source_snapshots': [pin], 'allow_cloud': False, 'license_note': ''})
    origin = {'contract': 'studio-canvas-return/1', 'project_id': 'synthetic-project',
        'scope': {'mode': 'local', 'novel_id': 'synthetic-project'},
        'incarnation': 'file:00000000-0000-0000-0000-000000000000', 'canvas_id': 'synthetic-canvas',
        'canvas_version': 1, 'canvas_digest': 'b' * 64, 'card_id': 'synthetic-card', 'source': pin}
    with pytest.raises(ValueError, match='STUDIO_CANVAS_RETURN_BINDING_INVALID'):
        CanvasReturnBinding.model_validate(origin)
