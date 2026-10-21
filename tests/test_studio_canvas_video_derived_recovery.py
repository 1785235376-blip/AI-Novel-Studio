"""FAILED video-card derivation over the original File/Timeline CPU owners.

The only success media comes from installed FFmpeg/ffprobe and short synthetic
sources. A known ValueError before rendering creates the FAILED parent through
the original executor; UNKNOWN is never relabelled as a successful recovery.
Run with PROJECT_ROOT and all application/temp paths inside this worktree's
.runtime. File results do not stand in for PostgreSQL acceptance.
"""
from copy import deepcopy
import base64
import json
import os
from pathlib import Path
import subprocess
from threading import Event
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.creative.canvas_video_task import CanvasVideoCommand
from app.experimental.common import StaleSourceError
from app.services import studio_timeline_export as native, studio_timeline_render
from app.services.v1_capability_service import CapabilityVersionConflict
from test_creative_canvas_views_additive import create, reference
from test_studio_canvas_video_audio import _two_tone_video, _audio_proof, _assert_tone
from test_studio_canvas_video_bridge import (
    bridge, change, definition, execute, get, preview, queue, render_calls,
    return_result, review,
)
from test_studio_canvas_video_cpu_owner_probe import (
    _context, _decoded_measurement, _owner_execute, _queue,
)
from test_v2_audio_editing_pipeline import production, source
from test_v2_audio_wav_controls import action
from test_v2_independent_workspace import rig, import_asset, reopened


REJECTED = (ValueError, StaleSourceError, FileNotFoundError, CapabilityVersionConflict)


def _raw(e, row):
    return e.production._row(e.nid, e.scope, e.actor, 'timeline', row['id'], lambda: None)[0]


def _failed(e, monkeypatch, row=None):
    """Exercise the real owner failure commit, without native output/publication."""
    row = row or queue(e)
    failures = []
    def before_render(*args, **kwargs):
        failures.append('known-before-render')
        raise ValueError('TEST_KNOWN_BEFORE_RENDER')
    with monkeypatch.context() as patch:
        patch.setattr(studio_timeline_render, 'render_studio_timeline', before_render)
        failed = execute(e, row)
    assert failures == ['known-before-render']
    assert failed['status'] == 'FAILED'
    assert failed['output_candidate'] is None and failed['media_measurement'] is None
    assert failed['automatic_replay'] is False and _raw(e, failed).get('measured') is None
    # get() adds observational reconciliation fields absent from execute().
    return get(e, failed)


def _origin(parent):
    return {'owner': 'timeline', 'job_id': parent['id'], 'job_version': parent['version'],
        'request_id': parent['request_id'], 'request_digest': parent['request_digest'],
        'receipt_digest': parent['receipt_digest']}


def _draft(e, parent, *, request_id='explicit-derived-video', in_ms=1000, out_ms=1800, option=None):
    """Explicit Apply saves a NEW original Timeline, then builds the new command."""
    value = deepcopy(e.command)
    value['request_id'] = request_id
    value['derived_from'] = _origin(parent)
    value['parameters'] = {'in_ms': in_ms, 'out_ms': out_ms}
    if option is not None:
        value['parameters']['include_audio'] = option
    timeline = definition(source(e.source), in_ms, out_ms)
    timeline['tracks'][0]['clips'][0]['include_audio'] = option is True
    saved = e.production.timeline_save(e.nid, e.scope, e.actor, None, {
        'expected_version': 0, 'title': 'Explicit new failed-video draft', 'timeline': timeline}, lambda: None)
    value['timeline_snapshot'] = {'id': saved['id'], 'version': saved['version'], 'digest': saved['timeline_digest']}
    assert saved['id'] != parent['timeline_snapshot']['id']
    return value, saved


def _unchanged(e, parent, raw):
    assert get(e, parent) == parent
    assert _raw(e, parent) == raw


def _evidence(name, value):
    if directory := os.environ.get('STUDIO_VIDEO_DERIVED_EVIDENCE'):
        target = Path(directory)
        target.mkdir(parents=True, exist_ok=True)
        (target / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


@pytest.fixture
def audio_bridge(bridge, tmp_path):
    e = bridge
    e.media = _two_tone_video(tmp_path)
    e.source = import_asset(e, data=e.media.read_bytes(), filename=e.media.name, kind='video')
    e.canvas = create(e, e.graph, {'title': 'Derived two-tone source cards', 'cards': [
        {'id': 'origin-video', 'position': {'x': 44, 'y': 66}, 'asset': reference(e.source)},
        {'id': 'another-video', 'position': {'x': 760, 'y': 120}, 'asset': reference(e.source)}]})
    e.timeline = e.production.timeline_save(e.nid, e.scope, e.actor, None, {
        'expected_version': 0, 'title': 'Frozen original two-tone task',
        'timeline': definition(source(e.source))}, lambda: None)
    e.command['source_snapshots'] = [source(e.source)]
    e.command['timeline_snapshot'] = {'id': e.timeline['id'], 'version': e.timeline['version'], 'digest': e.timeline['timeline_digest']}
    e.command['canvas_return'].update(canvas_id=e.canvas['id'], canvas_version=e.canvas['version'],
        canvas_digest=e.canvas['definition_digest'], source=source(e.source))
    return e


def test_legacy_video_wire_stays_omitted_and_known_failure_is_not_replayed(bridge, render_calls, monkeypatch):
    e = bridge
    assert CanvasVideoCommand.model_validate(e.command).model_dump() == e.command
    assert 'derived_from' not in preview(e)['command']
    parent = _failed(e, monkeypatch)
    raw = deepcopy(_raw(e, parent))
    assert queue(e)['id'] == parent['id']
    with pytest.raises(REJECTED): execute(e, parent)
    _unchanged(e, parent, raw)
    assert not render_calls


@pytest.mark.parametrize('receipt', ['digest', 'null'])
def test_derived_origin_wire_has_exact_six_fields_and_keeps_nullable_receipt(bridge, monkeypatch, receipt):
    e = bridge
    parent = _failed(e, monkeypatch)
    value, _ = _draft(e, parent)
    if receipt == 'null': value['derived_from']['receipt_digest'] = None
    assert set(value['derived_from']) == {'owner', 'job_id', 'job_version', 'request_id', 'request_digest', 'receipt_digest'}
    assert CanvasVideoCommand.model_validate(value).model_dump() == value


@pytest.mark.parametrize('field,bad', [
    ('owner', 'video'), ('job_id', ''), ('job_version', True), ('job_version', 0),
    ('job_version', 2**53), ('job_version', 1.0), ('request_id', ''),
    ('request_digest', 'not-a-digest'), ('receipt_digest', 'not-a-digest'), ('extra', 'forbidden'),
])
def test_invalid_derived_origin_schema_is_closed(bridge, monkeypatch, field, bad):
    e = bridge
    parent = _failed(e, monkeypatch)
    value, _ = _draft(e, parent)
    value['derived_from'][field] = bad
    with pytest.raises(ValueError): CanvasVideoCommand.model_validate(value)


@pytest.mark.parametrize('missing', ['owner', 'job_id', 'job_version', 'request_id', 'request_digest', 'receipt_digest'])
def test_derived_origin_requires_all_six_fields_even_for_nullable_receipt(bridge, monkeypatch, missing):
    e = bridge
    parent = _failed(e, monkeypatch); value, _ = _draft(e, parent)
    del value['derived_from'][missing]
    with pytest.raises(ValueError): CanvasVideoCommand.model_validate(value)


@pytest.mark.parametrize('option', [None, False, True], ids=['omitted-silent', 'explicit-silent', 'first-audio'])
def test_failed_video_derives_real_cpu_candidate_then_review_return_reopen_restore(
        audio_bridge, render_calls, monkeypatch, tmp_path, option):
    e = audio_bridge
    parent = _failed(e, monkeypatch)
    parent_raw = deepcopy(_raw(e, parent)); parent_timeline = deepcopy(e.timeline)
    original_canvas = deepcopy(e.canvas['definition'])
    value, child_timeline = _draft(e, parent, option=option)
    captured = preview(e, value)
    assert captured['command'] == value
    assert ('include_audio' in captured['command']['parameters']) is (option is not None)
    assert captured['execution_recipe']['timeline'] == child_timeline['timeline']
    assert captured['execution_recipe']['timeline']['tracks'][0]['clips'][0]['include_audio'] is (option is True)
    assert captured['automatic_dispatch'] is False and not render_calls
    queued = queue(e, value, captured)
    assert queued['id'] != parent['id'] and queued['request_id'] != parent['request_id']
    assert queued['request_digest'] != parent['request_digest']
    assert queued['canvas_video'] == value and queued['output_candidate'] is None
    assert queue(e, value, captured) == queued
    _unchanged(e, parent, parent_raw)
    assert e.production.timeline_get(e.nid, e.scope, e.actor, parent_timeline['id'], lambda: None) == parent_timeline
    e.production = production(e, reopened(e)); e.graph.configure_media(e.production)
    current = get(e, queued)
    assert current['status'] == 'QUEUED' and current['automatic_replay'] is False
    assert current['canvas_video']['derived_from'] == _origin(parent)
    candidate = execute(e, current)
    assert candidate['status'] == 'SUCCEEDED' and len(render_calls) == 1
    assert candidate['canvas_video'] == value and candidate['provider'] is None
    _, data = e.production.candidate(e.nid, e.scope, e.actor, 'timeline', candidate['id'], lambda: None)
    path = tmp_path / 'actual-derived-selected-video.mp4'; path.write_bytes(data)
    output = _decoded_measurement(path); audio = _audio_proof(path)
    assert (output['decoded_frames'], output['duration_ms'], output['width'], output['height'], output['fps']) == (20, 800, 640, 360, '25/1')
    assert output['codec'] == 'h264' and output['byte_count'] == len(data) > 0
    assert output['sha256'] == audio['sha256'] == candidate['output_candidate']['digest']
    assert candidate['media_measurement']['byte_count'] == len(data)
    assert candidate['media_measurement']['profile_validation'] == 'NATIVE_FFPROBE_EXACT'
    assert (audio['audio_tracks'], audio['codec'], audio['sample_rate'], audio['channels']) == (1, 'aac', 48000, 2)
    if option is True:
        _assert_tone(_audio_proof(e.media, start_ms=0, duration_ms=600), 440)
        _assert_tone(_audio_proof(e.media, track=1, start_ms=1000, duration_ms=600), 1320)
        _assert_tone(audio, 880)
    else:
        assert audio['interior_rms_pcm16'] < 1 and max(audio['amplitudes_pcm16'].values()) < 1
    with pytest.raises(FileNotFoundError): e.service.asset(e.nid, e.scope, candidate['output_candidate']['id'])
    with pytest.raises(REJECTED): execute(e, parent)
    with pytest.raises(REJECTED): execute(e, candidate)
    approved = review(e, candidate)
    returned = return_result(e, approved)
    formal = e.service.asset(e.nid, e.scope, approved['output_candidate']['id'])
    assert approved['status'] == 'APPROVED' and formal['sha256'] == output['sha256']
    assert returned['definition']['cards'][0]['asset'] == reference(formal)
    assert returned['definition']['cards'][0]['position'] == original_canvas['cards'][0]['position']
    assert returned['definition']['cards'][1] == original_canvas['cards'][1]
    history = e.graph.canvas_views.history(e.nid, e.scope, e.actor, e.canvas['id'])
    restored = e.graph.canvas_views.restore(e.nid, e.scope, e.actor, e.canvas['id'], {
        'expected_version': returned['version'], 'expected_definition_digest': returned['definition_digest'],
        'expected_incarnation': history['incarnation'], 'restore_version': e.canvas['version'],
        'restore_definition_digest': e.canvas['definition_digest']})
    assert [e.canvas['version'], returned['version'], restored['version']] == [1, 2, 3]
    assert restored['definition'] == original_canvas
    e.production = production(e, reopened(e)); e.graph.configure_media(e.production)
    assert get(e, approved)['status'] == 'APPROVED'
    _unchanged(e, parent, parent_raw)
    assert len(render_calls) == 1
    _evidence(f'cpu-derived-{str(option).lower()}.json', {
        'boundary': 'original File Timeline/Job/Review/Canvas CAS/history', 'backend': e.backend,
        'real_cpu_ffmpeg': True, 'model_called': False, 'option': option,
        'source': _decoded_measurement(e.media), 'output': output, 'audio': audio,
        'parent': parent, 'parent_unchanged': get(e, parent) == parent,
        'child_timeline': child_timeline, 'preview': captured, 'queued': queued,
        'executed': candidate, 'approved': approved,
        'canvas_versions': [e.canvas['version'], returned['version'], restored['version']],
        'native_renders': len(render_calls)})
    if option is None and (directory := os.environ.get('STUDIO_VIDEO_RECOVERY_CAPTURE_DIR')):
        target = Path(directory); target.mkdir(parents=True, exist_ok=True)
        (target / 'native-derived.json').write_text(json.dumps({
            'contract': 'synthetic-video-derived-recovery-proof/1', 'backend': e.backend,
            'real_cpu_ffmpeg': True, 'model_called': False,
            'source_asset': e.source, 'canvas': e.canvas, 'parent_failed': parent,
            'parent_timeline': parent_timeline, 'child_timeline': child_timeline,
            'derived_command': value, 'preview': captured, 'queued': queued,
            'executed': candidate, 'approved': approved, 'formal_asset': formal,
            'returned': returned, 'restored': restored, 'history': history,
            'candidate_base64': base64.b64encode(data).decode('ascii'),
            'output': output, 'audio': audio}, ensure_ascii=False, indent=2), encoding='utf-8')


def test_failed_chain_records_direct_parent_and_does_not_rewrite_ancestors(bridge, render_calls, monkeypatch):
    e = bridge
    first = _failed(e, monkeypatch); first_raw = deepcopy(_raw(e, first))
    value, _ = _draft(e, first, request_id='second-failed-video')
    second = _failed(e, monkeypatch, queue(e, value)); second_raw = deepcopy(_raw(e, second))
    third, _ = _draft(e, second, request_id='third-explicit-video', in_ms=1040, out_ms=1640)
    queued = queue(e, third)
    assert queued['canvas_video']['derived_from'] == _origin(second)
    assert queued['canvas_video']['derived_from']['job_id'] != first['id']
    assert len({first['id'], second['id'], queued['id']}) == 3
    for parent, raw in [(first, first_raw), (second, second_raw)]:
        with pytest.raises(REJECTED): execute(e, parent)
        _unchanged(e, parent, raw)
    assert not render_calls


def test_frozen_child_uses_new_timeline_after_explicit_parent_timeline_edit(bridge, render_calls, monkeypatch):
    e = bridge
    parent = _failed(e, monkeypatch); raw = deepcopy(_raw(e, parent))
    value, saved = _draft(e, parent)
    queued = queue(e, value)
    edited = e.production.timeline_save(e.nid, e.scope, e.actor, e.timeline['id'], {
        'expected_version': e.timeline['version'], 'title': 'Separate later original Timeline edit',
        'timeline': definition(source(e.source), 0, 400)}, lambda: None)
    assert edited['version'] == e.timeline['version'] + 1
    assert preview(e, value)['execution_recipe']['timeline'] == saved['timeline']
    candidate = execute(e, queued)
    assert candidate['status'] == 'SUCCEEDED' and candidate['media_measurement']['duration_ms'] == 800
    assert len(render_calls) == 1
    _unchanged(e, parent, raw)


@pytest.mark.parametrize('mutation', [
    'parent-version', 'parent-request', 'parent-request-digest', 'parent-receipt', 'parent-null-receipt',
    'old-request', 'parent-timeline', 'child-timeline-version', 'child-timeline-digest', 'recipe-range',
    'other-valid-card', 'other-valid-canvas', 'origin-source', 'provider',
])
def test_derived_preview_and_queue_reject_changed_parent_or_frozen_binding(bridge, render_calls, monkeypatch, mutation):
    e = bridge
    parent = _failed(e, monkeypatch); raw = deepcopy(_raw(e, parent))
    value, _ = _draft(e, parent)
    origin = value['derived_from']
    if mutation == 'parent-version': origin['job_version'] += 1
    elif mutation == 'parent-request': origin['request_id'] += '-wrong'
    elif mutation == 'parent-request-digest': origin['request_digest'] = 'f' * 64
    elif mutation == 'parent-receipt': origin['receipt_digest'] = 'f' * 64
    elif mutation == 'parent-null-receipt': origin['receipt_digest'] = None
    elif mutation == 'old-request': value['request_id'] = parent['request_id']
    elif mutation == 'parent-timeline':
        value['timeline_snapshot'] = deepcopy(parent['timeline_snapshot'])
        value['parameters'] = deepcopy(e.command['parameters'])
    elif mutation == 'child-timeline-version': value['timeline_snapshot']['version'] += 1
    elif mutation == 'child-timeline-digest': value['timeline_snapshot']['digest'] = 'f' * 64
    elif mutation == 'recipe-range': value['parameters']['out_ms'] = 1840
    elif mutation == 'other-valid-card': value['canvas_return']['card_id'] = 'another-video'
    elif mutation == 'other-valid-canvas':
        another = create(e, e.graph, {'title': 'Another valid canvas', 'cards': deepcopy(e.canvas['definition']['cards'])})
        value['canvas_return'].update(canvas_id=another['id'], canvas_version=another['version'], canvas_digest=another['definition_digest'])
    elif mutation == 'origin-source':
        another = import_asset(e, data=e.media.read_bytes(), filename='other-valid-video.mp4', kind='video')
        value['source_snapshots'] = [source(another)]; value['canvas_return']['source'] = source(another)
    else: value['provider_id'] = 'fake-provider'
    with pytest.raises(REJECTED): preview(e, value)
    with pytest.raises(REJECTED): queue(e, value, {'preview_digest': 'a' * 64})
    _unchanged(e, parent, raw)
    assert len(e.production.list(e.nid, e.scope, e.actor, lambda: None)['items']) == 1 and not render_calls


@pytest.mark.parametrize('mutation', ['canvas-version', 'card-deleted', 'source-pin', 'source-deleted'])
def test_derived_current_source_and_canvas_fences_apply_at_preview_and_execute(bridge, render_calls, monkeypatch, mutation):
    e = bridge
    parent = _failed(e, monkeypatch); raw = deepcopy(_raw(e, parent))
    value, _ = _draft(e, parent)
    queued = queue(e, value)
    change(e, mutation)
    with pytest.raises(REJECTED): preview(e, value)
    with pytest.raises(REJECTED): execute(e, queued)
    assert get(e, queued)['status'] == 'QUEUED' and get(e, queued)['output_candidate'] is None
    _unchanged(e, parent, raw)
    assert not render_calls


@pytest.mark.parametrize('mutation', ['other-actor', 'other-project', 'recreated-project', 'command-incarnation', 'command-scope'])
def test_derived_origin_cannot_cross_actor_scope_or_incarnation(bridge, render_calls, monkeypatch, mutation):
    e = bridge
    parent = _failed(e, monkeypatch)
    value, _ = _draft(e, parent)
    queued = queue(e, value)
    nid, scope, actor = e.nid, e.scope, e.actor
    if mutation == 'other-actor': actor = 'different-local-author'
    elif mutation == 'other-project':
        nid = e.create_project('Other derived target'); scope = {'mode': 'local', 'novel_id': nid}
        e.service.activate(nid, scope, actor)
    elif mutation == 'recreated-project':
        e.novels.delete(nid); e.create_project('Recreated derived target', nid)
        e.service.activate(nid, scope, actor)
    elif mutation == 'command-incarnation': value['canvas_return']['incarnation'] = 'file:00000000-0000-0000-0000-000000000000'
    else: value['canvas_return']['scope'] = {**scope, 'branch_id': 'other-branch'}
    with pytest.raises(REJECTED): e.production.canvas_video_preview(nid, scope, actor, value, lambda: None)
    if mutation not in {'command-incarnation', 'command-scope'}:
        with pytest.raises(REJECTED): e.production.canvas_video_execute(nid, scope, actor, queued['id'], action(queued), lambda: None)
    assert not render_calls


@pytest.mark.parametrize('status', ['QUEUED', 'CANCELLED', 'UNKNOWN'])
def test_nonfailed_parent_is_never_derived_or_automatically_replayed(bridge, render_calls, monkeypatch, status):
    e = bridge
    parent = queue(e)
    if status == 'CANCELLED':
        parent = e.production.cancel(e.nid, e.scope, e.actor, 'timeline', parent['id'], action(parent), lambda: None)
    elif status == 'UNKNOWN':
        def timeout(*args, **kwargs): raise subprocess.TimeoutExpired('synthetic-before-render', 1)
        with monkeypatch.context() as patch:
            patch.setattr(studio_timeline_render, 'render_studio_timeline', timeout)
            parent = execute(e, parent)
    parent = get(e, parent)
    assert parent['status'] == status and parent['automatic_replay'] is False
    raw = deepcopy(_raw(e, parent)); value, _ = _draft(e, parent)
    with pytest.raises(REJECTED): preview(e, value)
    with pytest.raises(REJECTED): queue(e, value, {'preview_digest': 'a' * 64})
    if status != 'QUEUED':
        with pytest.raises(REJECTED): execute(e, parent)
    assert queue(e)['status'] == status
    _unchanged(e, parent, raw)
    assert not render_calls


def test_running_original_execution_cannot_be_used_as_failed_parent(bridge, render_calls, monkeypatch):
    e = bridge
    queued = queue(e); entered, release = Event(), Event()
    def blocked_before_render(*args, **kwargs):
        entered.set()
        assert release.wait(10)
        raise ValueError('TEST_KNOWN_BEFORE_RENDER')
    monkeypatch.setattr(studio_timeline_render, 'render_studio_timeline', blocked_before_render)
    with ThreadPoolExecutor(max_workers=1) as worker:
        future = worker.submit(execute, e, queued)
        try:
            assert entered.wait(10)
            running = get(e, queued)
            assert running['status'] == 'RUNNING'
            value, _ = _draft(e, running)
            with pytest.raises(REJECTED): preview(e, value)
            assert get(e, running)['status'] == 'RUNNING' and not render_calls
        finally: release.set()
        failed = future.result(timeout=10)
    assert failed['status'] == 'FAILED' and failed['output_candidate'] is None


def test_untyped_original_timeline_failure_cannot_admit_video_derivation(bridge, render_calls, monkeypatch):
    e = bridge
    context = _context(e, 'untyped-original-failure'); queued = _queue(e, context)
    def before_render(*args, **kwargs): raise ValueError('TEST_KNOWN_BEFORE_RENDER')
    with monkeypatch.context() as patch:
        patch.setattr(studio_timeline_render, 'render_studio_timeline', before_render)
        failed = _owner_execute(e, queued, context)
    parent = get(e, failed)
    assert parent['status'] == 'FAILED' and 'canvas_video' not in parent
    raw = deepcopy(_raw(e, parent)); value, _ = _draft(e, parent)
    with pytest.raises(REJECTED): preview(e, value)
    _unchanged(e, parent, raw)
    assert not render_calls


@pytest.mark.parametrize('mutation', ['provider', 'candidate', 'measurement', 'kind', 'request-digest'])
def test_parent_owner_read_must_validate_typed_receipt_and_no_result(bridge, render_calls, monkeypatch, mutation):
    e = bridge
    parent = _failed(e, monkeypatch); value, _ = _draft(e, parent)
    original = e.production._row; parent_reads = []
    def changed(nid, scope, actor, owner, jid, guard, **kwargs):
        row, context = original(nid, scope, actor, owner, jid, guard, **kwargs)
        if jid == parent['id']:
            parent_reads.append(jid); row, context = deepcopy(row), deepcopy(context)
            if mutation == 'provider': context['provider_binding'] = {'provider_id': 'fake-provider'}
            elif mutation == 'candidate': row['output_candidate'] = {'id': 'forged-private-result'}
            elif mutation == 'measurement': row['measured'] = {'duration_ms': 800}
            elif mutation == 'kind': row['kind'] = 'LEGACY_ASSEMBLY'
            else: row['request_digest'] = 'f' * 64
            row['context'] = context
        return row, context
    monkeypatch.setattr(e.production, '_row', changed)
    with pytest.raises(REJECTED): preview(e, value)
    assert parent_reads and not render_calls


def test_derived_request_preview_and_action_proofs_keep_original_idempotency(bridge, render_calls, monkeypatch):
    e = bridge
    parent = _failed(e, monkeypatch); raw = deepcopy(_raw(e, parent))
    value, _ = _draft(e, parent)
    captured = preview(e, value); queued = queue(e, value, captured)
    current = get(e, queued)
    assert queue(e, value, captured) == queued
    with pytest.raises(REJECTED):
        e.production.canvas_video_execute(e.nid, e.scope, e.actor, queued['id'], action(parent), lambda: None)
    changed, _ = _draft(e, parent, request_id=value['request_id'], in_ms=1040, out_ms=1640)
    fresh = preview(e, changed)
    assert fresh['preview_digest'] != captured['preview_digest']
    with pytest.raises(REJECTED): queue(e, changed, captured)
    with pytest.raises(REJECTED): queue(e, changed, fresh)
    assert get(e, queued) == current and not render_calls
    _unchanged(e, parent, raw)


@pytest.mark.parametrize('phase,mutation', [
    ('review', 'canvas-version'), ('review', 'card-deleted'), ('review', 'source-pin'),
    ('return', 'canvas-version'), ('return', 'card-deleted'), ('return', 'source-pin'),
])
def test_derived_candidate_conflict_retains_original_private_or_formal_result(bridge, render_calls, monkeypatch, phase, mutation):
    e = bridge
    parent = _failed(e, monkeypatch); raw = deepcopy(_raw(e, parent))
    value, _ = _draft(e, parent)
    candidate = execute(e, queue(e, value))
    assert candidate['status'] == 'SUCCEEDED'
    result = review(e, candidate) if phase == 'return' else candidate
    change(e, mutation)
    with pytest.raises(REJECTED):
        (return_result(e, result) if phase == 'return' else review(e, result))
    current = get(e, result)
    assert current['status'] == result['status'] and current['output_candidate'] == result['output_candidate']
    if phase == 'review':
        with pytest.raises(FileNotFoundError): e.service.asset(e.nid, e.scope, candidate['output_candidate']['id'])
    else: assert e.service.asset(e.nid, e.scope, candidate['output_candidate']['id'])['kind'] == 'video'
    assert len(render_calls) == 1
    _unchanged(e, parent, raw)


@pytest.mark.parametrize('race', ['canvas-changed', 'cancelled'])
def test_late_derived_native_result_cannot_overwrite_original_target_or_job_fence(bridge, render_calls, monkeypatch, race):
    e = bridge
    parent = _failed(e, monkeypatch); raw = deepcopy(_raw(e, parent))
    value, _ = _draft(e, parent); queued = queue(e, value)
    count = len(e.service.list_assets(e.nid, e.scope)['items'])
    original = native.run_guarded_process; races = []
    def late(command, *args, **kwargs):
        result = original(command, *args, **kwargs)
        if '-filter_complex' in command:
            races.append(race)
            if race == 'canvas-changed': change(e, 'canvas-version')
            else:
                running = get(e, queued)
                cancelled = e.production.cancel(e.nid, e.scope, e.actor, 'timeline', queued['id'], action(running), lambda: None)
                assert cancelled['status'] == 'CANCELLED'
        return result
    monkeypatch.setattr(native, 'run_guarded_process', late)
    try: execute(e, queued)
    except REJECTED: pass
    current = get(e, queued)
    assert races == [race] and len(render_calls) == 1
    assert current['status'] in ({'CANCELLED'} if race == 'cancelled' else {'FAILED', 'UNKNOWN'})
    assert current['output_candidate'] is None
    assert len(e.service.list_assets(e.nid, e.scope)['items']) == count
    with pytest.raises(REJECTED): execute(e, current)
    _unchanged(e, parent, raw)
