"""Saved video-card bridge over original File/Timeline/VideoAssembly owners.

Only a short synthetic red/blue source is processed by real installed FFmpeg
CPU. No model, provider, GPU, network, new queue or replacement storage.
"""
from copy import deepcopy
import base64
import hashlib
import json
import os
from pathlib import Path

import pytest

from app.experimental.common import StaleSourceError
from app.services import studio_timeline_export as native


# Source-only public test closure; shared File fixture is already public.
import shutil
from app.audio_production_store import AudioProductionStore
from app.creative.production_execution import ProductionExecutionService
from app.services.image_job_service import ImageJobService
from app.services.video_assembly_service import VideoAssemblyService
from app.services.studio_timeline_export import probe_media_file
from test_studio_canvas_audio_return import rig,import_asset,reopened,owner,create,reference,action,NoControl

def source(row):
    return {'kind': 'ASSET', 'asset_kind': row['kind'], 'id': row['id'], 'version': row['version'], 'digest': row['sha256']}

def production(e, workspace=None):
    workspace = workspace or e.service
    return ProductionExecutionService(workspace, ImageJobService(e.root), NoControl(),
        VideoAssemblyService(e.root, workspace.assets), {}, {}, AudioProductionStore(e.root / 'audio-production'),
        NoControl(), NoControl())

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


def definition(pin, in_ms=1000, out_ms=1600):
    return {'schema_version': 2, 'duration_ms': out_ms - in_ms, 'width': 640, 'height': 360, 'fps': 25,
        'tracks': [{'id': 'canvas-video-track', 'kind': 'VIDEO', 'order': 0, 'clips': [
            {'id': 'canvas-video-clip', 'source_snapshot': pin, 'start_ms': 0, 'in_ms': in_ms, 'out_ms': out_ms,
             'include_audio': False}]}], 'captions': []}


@pytest.fixture
def bridge(rig, tmp_path):
    e = rig; e.service.activate(e.nid, e.scope, e.actor)
    e.media = _source_video(tmp_path)
    e.source = import_asset(e, data=e.media.read_bytes(), filename='synthetic-red-blue.mp4', kind='video')
    e.production = production(e); e.graph = owner(e); e.graph.configure_media(e.production)
    e.canvas = create(e, e.graph, {'title': 'Saved synthetic video cards', 'cards': [
        {'id': 'origin-video', 'position': {'x': 44, 'y': 66}, 'asset': reference(e.source)},
        {'id': 'another-video', 'position': {'x': 760, 'y': 120}, 'asset': reference(e.source)}]})
    e.timeline = e.production.timeline_save(e.nid, e.scope, e.actor, None,
        {'expected_version': 0, 'title': 'Single saved video task', 'timeline': definition(source(e.source))}, lambda: None)
    e.command = {'contract': 'studio-canvas-video-trim/1', 'operation_id': 'm9.timeline.multitrack',
        'request_id': 'saved-video-trim', 'provider_id': None, 'model_id': None, 'prompt': '', 'allow_cloud': False,
        'license_note': '', 'parameters': {'in_ms': 1000, 'out_ms': 1600}, 'source_snapshots': [source(e.source)],
        'timeline_snapshot': {'id': e.timeline['id'], 'version': e.timeline['version'], 'digest': e.timeline['timeline_digest']},
        'canvas_return': {'contract': 'studio-canvas-return/1', 'project_id': e.nid, 'scope': e.scope,
            'incarnation': e.store.incarnation(e.nid), 'canvas_id': e.canvas['id'], 'canvas_version': e.canvas['version'],
            'canvas_digest': e.canvas['definition_digest'], 'card_id': 'origin-video', 'source': source(e.source)}}
    return e


@pytest.fixture
def render_calls(monkeypatch):
    original = native.run_guarded_process; calls = []
    def observed(command, *args, **kwargs):
        if '-filter_complex' in command: calls.append(list(command))
        return original(command, *args, **kwargs)
    monkeypatch.setattr(native, 'run_guarded_process', observed)
    return calls


def preview(e, command=None):
    return e.production.canvas_video_preview(e.nid, e.scope, e.actor, command or e.command, lambda: None)


def queue(e, command=None, captured=None):
    command = command or e.command; captured = captured or preview(e, command)
    return e.production.canvas_video_queue(e.nid, e.scope, e.actor,
        {'command': command, 'reviewed_preview_digest': captured['preview_digest']}, lambda: None)


def execute(e, row):
    return e.production.canvas_video_execute(e.nid, e.scope, e.actor, row['id'], action(row), lambda: None)


def get(e, row):
    return e.production.get(e.nid, e.scope, e.actor, 'timeline', row['id'], lambda: None)


def review(e, row):
    return e.production.review(e.nid, e.scope, e.actor, 'timeline', row['id'], action(row, True), lambda: None)


def return_result(e, approved):
    asset = e.service.asset(e.nid, e.scope, approved['output_candidate']['id'])
    value = deepcopy(e.canvas['definition']); value['cards'][0]['asset'] = reference(asset)
    return e.graph.canvas_views.save(e.nid, e.scope, e.actor, e.canvas['id'], {
        'expected_version': e.canvas['version'], 'definition': value,
        'expected_definition_digest': e.canvas['definition_digest'], 'expected_incarnation': e.store.incarnation(e.nid),
        'expected_card': {'card_id': 'origin-video', 'source': reference(e.source)}})


def change(e, mutation):
    if mutation in {'canvas-version', 'card-deleted'}:
        value = deepcopy(e.canvas['definition'])
        if mutation == 'canvas-version': value['title'] += ' changed'
        else: value['cards'] = value['cards'][1:]
        e.graph.canvas_views.save(e.nid, e.scope, e.actor, e.canvas['id'], {'expected_version': 1, 'definition': value})
    elif mutation in {'source-pin', 'source-deleted'}:
        with e.service._asset_scope(e.nid, e.scope):
            if mutation == 'source-pin': e.assets.update_metadata(e.source['id'], {'provider_id': 'synthetic-metadata-change'}, expected_version=e.source['version'])
            else: e.assets.delete(e.source['id'])
    elif mutation == 'timeline-version':
        e.production.timeline_save(e.nid, e.scope, e.actor, e.timeline['id'], {
            'expected_version': e.timeline['version'], 'title': 'Explicit task changed', 'timeline': e.timeline['timeline']}, lambda: None)
    else: raise AssertionError(mutation)


def test_real_saved_video_bridge_preview_queue_reopen_execute_review_return_and_restore(bridge, render_calls, tmp_path):
    e = bridge; captured = preview(e)
    assert set(captured) == {'contract', 'novel_id', 'branch_id', 'command', 'request_digest', 'preview_digest',
        'execution_recipe', 'execution_available', 'automatic_dispatch', 'product_acceptance'}
    assert captured['contract'] == 'studio-canvas-video-preview/1' and captured['command'] == e.command
    assert captured['execution_available'] is True and captured['automatic_dispatch'] is False
    assert captured['product_acceptance'] == 'LOCAL_REQUIRED'
    recipe = captured['execution_recipe']
    assert set(recipe) == {'contract', 'operation_id', 'adapter', 'output_profile', 'timeline', 'export_profile', 'automatic_fallback', 'recipe_digest'}
    assert recipe['adapter'] == 'LOCAL_FFMPEG' and recipe['output_profile'] == 'DELIVERY_H264_MP4'
    assert recipe['export_profile'] == {'preset': 'DELIVERY_H264_MP4', 'video_bitrate_kbps': 400,
        'audio_bitrate_kbps': 96, 'crf': 23} and recipe['automatic_fallback'] is False
    assert recipe['timeline'] == e.timeline['timeline']
    queued = queue(e, captured=captured)
    assert queued['status'] == 'QUEUED' and queued['output_candidate'] is None and queued['command'] is None
    assert queued['canvas_video'] == e.command
    repeated = queue(e, captured=captured)
    assert all(repeated[key] == queued[key] for key in ['id', 'version', 'request_digest', 'receipt_digest'])
    assert not render_calls
    e.production = production(e, reopened(e)); e.graph.configure_media(e.production)
    current = get(e, queued)
    assert current['status'] == 'QUEUED' and current['canvas_video'] == e.command and current['automatic_replay'] is False
    listed_response = e.production.list(e.nid, e.scope, e.actor, lambda: None)
    listed = listed_response['items']
    assert next(row for row in listed if row['id'] == queued['id'])['canvas_video'] == e.command
    with pytest.raises(ValueError, match='STUDIO_TIMELINE_ALREADY_RENDERED_EXPLICITLY'):
        e.production.execute(e.nid, e.scope, e.actor, 'timeline', queued['id'], action(current), lambda: None)
    assert not render_calls
    candidate = execute(e, current)
    assert candidate['status'] == 'SUCCEEDED' and candidate['canvas_video'] == e.command and candidate['command'] is None
    assert len(render_calls) == 1
    with pytest.raises(ValueError): execute(e, candidate)
    assert get(e, candidate)['status'] == 'SUCCEEDED' and len(render_calls) == 1
    _, data = e.production.candidate(e.nid, e.scope, e.actor, 'timeline', queued['id'], lambda: None)
    path = tmp_path / 'actual-selected-video.mp4'; path.write_bytes(data)
    source_proof, output = _decoded_measurement(e.media), _decoded_measurement(path)
    assert source_proof['decoded_frames'] == 20 and source_proof['duration_ms'] == 2000
    assert all(rgb[0] > 230 and rgb[2] < 20 for rgb in source_proof['center_rgb'][:10])
    assert all(rgb[2] > 230 and rgb[0] < 20 for rgb in source_proof['center_rgb'][10:])
    assert (output['decoded_frames'], output['duration_ms'], output['width'], output['height'], output['fps']) == (15, 600, 640, 360, '25/1')
    assert output['codec'] == 'h264' and all(rgb[2] > 230 and rgb[0] < 20 for rgb in output['center_rgb'])
    assert output['sha256'] == candidate['output_candidate']['digest'] and len(data) == output['byte_count']
    assert candidate['media_measurement']['profile_validation'] == 'NATIVE_FFPROBE_EXACT'
    with pytest.raises(FileNotFoundError): e.service.asset(e.nid, e.scope, candidate['output_candidate']['id'])
    approved = review(e, candidate)
    assert approved['status'] == 'APPROVED' and approved['canvas_video'] == e.command
    returned = return_result(e, approved)
    formal = e.service.asset(e.nid, e.scope, approved['output_candidate']['id'])
    assert returned['version'] == 2 and returned['definition']['cards'][0]['asset'] == reference(formal)
    assert returned['definition']['cards'][0]['position'] == e.canvas['definition']['cards'][0]['position']
    assert returned['definition']['cards'][1] == e.canvas['definition']['cards'][1]
    history = e.graph.canvas_views.history(e.nid, e.scope, e.actor, e.canvas['id'])
    restored = e.graph.canvas_views.restore(e.nid, e.scope, e.actor, e.canvas['id'], {
        'expected_version': returned['version'], 'expected_definition_digest': returned['definition_digest'],
        'expected_incarnation': history['incarnation'], 'restore_version': e.canvas['version'],
        'restore_definition_digest': e.canvas['definition_digest']})
    assert restored['version'] == 3 and restored['definition'] == e.canvas['definition']
    approved_read = get(e, approved)
    assert approved_read['status'] == 'APPROVED' and len(render_calls) == 1
    if os.environ.get('STUDIO_VIDEO_BRIDGE_EVIDENCE'):
        Path(os.environ['STUDIO_VIDEO_BRIDGE_EVIDENCE']).write_text(json.dumps({
            'contract': 'synthetic-video-card-bridge-proof/1', 'real_cpu_ffmpeg': True, 'model_called': False,
            'source': source_proof, 'output': output, 'preview': captured, 'queued': queued,
            'source_asset': e.source, 'timeline': e.timeline, 'command': e.command,
            'candidate_base64': base64.b64encode(data).decode('ascii'),
            'get_queued': current, 'list_queued': listed_response, 'get': approved_read,
            'executed': candidate, 'approved': approved, 'canvas': e.canvas, 'returned': returned, 'restored': restored,
            'history': history, 'formal_asset': formal}, ensure_ascii=False, indent=2), encoding='utf-8')


@pytest.mark.parametrize('mutation', ['contract', 'operation', 'provider', 'model', 'prompt', 'cloud', 'license',
    'negative-start', 'equal-range', 'reverse-range', 'in-grid', 'out-grid', 'bool', 'duration-limit', 'source-duration',
    'extra-parameter', 'source-pin', 'origin-pin', 'scope', 'incarnation', 'canvas-version', 'canvas-digest', 'card',
    'timeline-version', 'timeline-digest', 'extra-field'])
def test_invalid_video_bridge_preview_never_renders_or_queues(bridge, render_calls, mutation):
    e = bridge; value = deepcopy(e.command); origin = value['canvas_return']
    if mutation == 'contract': value['contract'] = 'unknown/1'
    elif mutation == 'operation': value['operation_id'] = 'm7.video.trim'
    elif mutation == 'provider': value['provider_id'] = 'some-provider'
    elif mutation == 'model': value['model_id'] = 'some-model'
    elif mutation == 'prompt': value['prompt'] = 'not a CPU trim'
    elif mutation == 'cloud': value['allow_cloud'] = True
    elif mutation == 'license': value['license_note'] = 'not the closed command'
    elif mutation == 'negative-start': value['parameters']['in_ms'] = -40
    elif mutation == 'equal-range': value['parameters']['out_ms'] = 1000
    elif mutation == 'reverse-range': value['parameters']['out_ms'] = 960
    elif mutation == 'in-grid': value['parameters']['in_ms'] = 1001
    elif mutation == 'out-grid': value['parameters']['out_ms'] = 1601
    elif mutation == 'bool': value['parameters']['in_ms'] = True
    elif mutation == 'duration-limit': value['parameters'] = {'in_ms': 0, 'out_ms': 120040}
    elif mutation == 'source-duration': value['parameters']['out_ms'] = 2040
    elif mutation == 'extra-parameter': value['parameters']['fps'] = 25
    elif mutation == 'source-pin': value['source_snapshots'][0]['digest'] = 'f' * 64
    elif mutation == 'origin-pin': origin['source']['digest'] = 'f' * 64
    elif mutation == 'scope': origin['scope'] = {**origin['scope'], 'branch_id': 'another-branch'}
    elif mutation == 'incarnation': origin['incarnation'] = 'file:00000000-0000-0000-0000-000000000000'
    elif mutation == 'canvas-version': origin['canvas_version'] += 1
    elif mutation == 'canvas-digest': origin['canvas_digest'] = 'f' * 64
    elif mutation == 'card': origin['card_id'] = 'deleted-card'
    elif mutation == 'timeline-version': value['timeline_snapshot']['version'] += 1
    elif mutation == 'timeline-digest': value['timeline_snapshot']['digest'] = 'f' * 64
    else: value['filter'] = 'arbitrary filter not supported'
    if mutation in {'source-duration', 'duration-limit', 'in-grid', 'out-grid'}:
        # The original saved timeline must otherwise match this command, so a
        # missing duration/grid guard cannot pass by hitting a stale snapshot.
        updated = e.production.timeline_save(e.nid, e.scope, e.actor, e.timeline['id'], {
            'expected_version': e.timeline['version'], 'title': 'Matching invalid command bounds',
            'timeline': definition(source(e.source), **value['parameters'])}, lambda: None)
        value['timeline_snapshot'] = {'id': updated['id'], 'version': updated['version'], 'digest': updated['timeline_digest']}
    with pytest.raises((ValueError, StaleSourceError, FileNotFoundError)): preview(e, value)
    assert not render_calls and e.production.list(e.nid, e.scope, e.actor, lambda: None)['items'] == []


@pytest.mark.parametrize('mutation', ['canvas-version', 'card-deleted', 'source-pin', 'source-deleted', 'timeline-version'])
def test_queued_video_bridge_target_change_prevents_render(bridge, render_calls, mutation):
    e = bridge; queued = queue(e); change(e, mutation)
    with pytest.raises((ValueError, StaleSourceError, FileNotFoundError)): execute(e, queued)
    current = get(e, queued)
    assert current['status'] == 'QUEUED' and current['output_candidate'] is None and not render_calls


@pytest.mark.parametrize('mutation', ['other-project', 'recreated-project'])
def test_video_bridge_cannot_execute_under_other_scope_or_incarnation(bridge, render_calls, mutation):
    e = bridge; queued = queue(e)
    if mutation == 'other-project':
        nid = e.create_project('Other neutral project'); scope = {'mode': 'local', 'novel_id': nid}
    else:
        e.novels.delete(e.nid); e.create_project('Recreated neutral project', e.nid); nid, scope = e.nid, e.scope
    e.service.activate(nid, scope, e.actor)
    with pytest.raises((ValueError, StaleSourceError, FileNotFoundError)):
        e.production.canvas_video_execute(nid, scope, e.actor, queued['id'], action(queued), lambda: None)
    assert not render_calls


def test_video_bridge_changed_request_and_preview_cannot_reuse_original_queue(bridge, render_calls):
    e = bridge; captured = preview(e); queued = queue(e, captured=captured)
    value = deepcopy(e.command); value['parameters'] = {'in_ms': 1040, 'out_ms': 1640}
    updated = e.production.timeline_save(e.nid, e.scope, e.actor, e.timeline['id'], {
        'expected_version': e.timeline['version'], 'title': 'Explicit changed task',
        'timeline': definition(source(e.source), 1040, 1640)}, lambda: None)
    value['timeline_snapshot'] = {'id': updated['id'], 'version': updated['version'], 'digest': updated['timeline_digest']}
    with pytest.raises((ValueError, StaleSourceError)): queue(e, value, captured)
    fresh = preview(e, value)
    assert fresh['preview_digest'] != captured['preview_digest']
    with pytest.raises((ValueError, StaleSourceError)): queue(e, value, fresh)
    assert get(e, queued)['request_digest'] == queued['request_digest'] and not render_calls


def test_video_bridge_original_owner_unknown_receipt_is_never_replayed(bridge, render_calls):
    e = bridge; queued = queue(e)
    base = e.production._base(e.nid, e.scope, e.actor, lambda: None)
    raw = e.production.video_owner.get_studio(e.nid, e.scope.get('branch_id'), e.actor, queued['id'], context=base, guard=lambda: None)
    e.production.video_owner._studio_mutate(e.nid, e.scope.get('branch_id'), e.actor, queued['id'], raw['version'],
        lambda value: value.update(status='UNKNOWN', phase='RENDERING', automatic_retry=False), context=raw['context'])
    current = get(e, queued)
    assert current['status'] == 'UNKNOWN' and current['automatic_replay'] is False
    with pytest.raises(ValueError): execute(e, current)
    assert get(e, queued)['status'] == 'UNKNOWN' and not render_calls


@pytest.mark.parametrize('mutation', ['canvas-version', 'card-deleted', 'source-pin', 'source-deleted'])
def test_video_bridge_review_conflict_retains_private_candidate(bridge, render_calls, mutation):
    e = bridge; candidate = execute(e, queue(e)); assert candidate['status'] == 'SUCCEEDED'
    change(e, mutation)
    with pytest.raises((ValueError, StaleSourceError, FileNotFoundError)): review(e, candidate)
    current = get(e, candidate)
    assert current['status'] == 'SUCCEEDED' and current['output_candidate'] == candidate['output_candidate']
    with pytest.raises(FileNotFoundError): e.service.asset(e.nid, e.scope, candidate['output_candidate']['id'])
    assert len(render_calls) == 1


@pytest.mark.parametrize('mutation', ['canvas-version', 'source-pin', 'source-deleted'])
def test_video_bridge_return_cas_conflict_keeps_formal_asset(bridge, render_calls, mutation):
    e = bridge; approved = review(e, execute(e, queue(e))); change(e, mutation)
    with pytest.raises((ValueError, StaleSourceError, FileNotFoundError)): return_result(e, approved)
    assert get(e, approved)['status'] == 'APPROVED'
    assert e.service.asset(e.nid, e.scope, approved['output_candidate']['id'])['kind'] == 'video'
    assert len(render_calls) == 1


def test_video_bridge_late_native_result_does_not_publish_after_target_change(bridge, monkeypatch):
    e = bridge; queued = queue(e); original = native.run_guarded_process; renders = []
    def changed(command, *args, **kwargs):
        result = original(command, *args, **kwargs)
        if '-filter_complex' in command:
            renders.append(1); change(e, 'canvas-version')
        return result
    monkeypatch.setattr(native, 'run_guarded_process', changed)
    try: execute(e, queued)
    except (ValueError, StaleSourceError, FileNotFoundError): pass
    current = get(e, queued)
    assert renders == [1] and current['status'] in {'FAILED', 'UNKNOWN'} and current['output_candidate'] is None
    assert len(e.service.list_assets(e.nid, e.scope)['items']) == 1
