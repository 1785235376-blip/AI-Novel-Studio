"""Unqueued derived video inputs in the original Timeline CAS/history owner.

Only the native positive case renders the installed CPU FFmpeg path. These
checks preserve the original FAILED Job and never persist an execution proof.
File results must not be presented as PostgreSQL or real-provider acceptance.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import base64
import json
import os
from pathlib import Path
import subprocess
from threading import Barrier

import pytest

from app.creative.production_execution import TIMELINES, digest
from app.experimental.common import StaleSourceError
from app.services import studio_timeline_render
from app.services.v1_capability_service import CapabilityVersionConflict
from test_studio_canvas_video_derived_recovery import _failed, _origin, _raw
from test_studio_canvas_video_bridge import (
    bridge, change, definition, execute, get, preview, queue, render_calls,
)
from test_studio_canvas_video_cpu_owner_probe import _decoded_measurement
from test_v2_audio_editing_pipeline import production, source
from test_v2_independent_workspace import rig, reopened

REJECTED = (ValueError, StaleSourceError, FileNotFoundError, CapabilityVersionConflict)


def inputs(e, parent, *, out_ms=1800, request_id='saved-unqueued-derived-video'):
    return {'contract': 'studio-canvas-video-draft/1', 'request_id': request_id,
        'parameters': {'in_ms': 1000, 'out_ms': out_ms},
        'source_snapshots': [source(e.source)],
        'canvas_return': deepcopy(parent['canvas_video']['canvas_return']),
        'derived_from': _origin(parent)}


def body(e, value, *, version=0):
    parameters = value['parameters']
    timeline = definition(source(e.source), parameters['in_ms'], parameters['out_ms'])
    timeline['tracks'][0]['clips'][0]['include_audio'] = parameters.get('include_audio') is True
    return {'title': 'Saved unqueued derived video inputs', 'timeline': timeline,
        'expected_version': version, 'canvas_video_draft': deepcopy(value)}


def save(e, value, row=None, *, guard=lambda: None):
    return e.production.timeline_save(e.nid, e.scope, e.actor, row['id'] if row else None,
        body(e, value, version=row['version'] if row else 0), guard)


def read(e, row, *, guard=lambda: None):
    return e.production.timeline_get(e.nid, e.scope, e.actor, row['id'], guard)


def exact_saved(row, value):
    command = row['canvas_video_draft']
    assert command['contract'] == 'studio-canvas-video-trim/1'
    assert command['operation_id'] == 'm9.timeline.multitrack'
    assert command['provider_id'] is None and command['model_id'] is None
    assert command['prompt'] == command['license_note'] == '' and command['allow_cloud'] is False
    assert {k: command[k] for k in value if k != 'contract'} == {k: v for k, v in value.items() if k != 'contract'}
    assert command['timeline_snapshot'] == {'id': row['id'], 'version': row['version'], 'digest': row['timeline_digest']}
    assert row['canvas_video_draft_digest'] == digest(command)
    assert not {'proof', 'authorization', 'preview_digest', 'reviewed_preview_digest', 'confirmation'}.intersection(command)
    return command


def test_legacy_timeline_save_omits_all_draft_fields_and_creates_no_job(bridge, render_calls):
    e = bridge
    row = e.production.timeline_save(e.nid, e.scope, e.actor, None, {
        'title': 'Legacy Timeline input', 'timeline': e.timeline['timeline'], 'expected_version': 0}, lambda: None)
    assert 'canvas_video_draft' not in row and 'canvas_video_draft_digest' not in row
    assert e.production.list(e.nid, e.scope, e.actor, lambda: None)['items'] == []
    assert not render_calls


def test_unqueued_inputs_reopen_in_same_timeline_then_require_original_preview_queue_and_native_execute(
        bridge, render_calls, monkeypatch, tmp_path):
    e = bridge
    parent = _failed(e, monkeypatch); parent_raw = deepcopy(_raw(e, parent))
    original_document = deepcopy(e.store.read(e.nid, e.scope))
    value = inputs(e, parent); row = save(e, value); command = exact_saved(row, value)
    document = e.store.read(e.nid, e.scope)
    assert set(document['collections']) == set(original_document['collections'])
    assert len(document['collections'][TIMELINES]) == len(original_document['collections'][TIMELINES]) + 1
    stored = document['collections'][TIMELINES][row['id']]
    assert stored['canvas_video_draft'] == command and stored['canvas_video_draft_digest'] == digest(command)
    assert row['id'] != parent['timeline_snapshot']['id']
    assert not render_calls
    assert [item['id'] for item in e.production.list(e.nid, e.scope, e.actor, lambda: None)['items']] == [parent['id']]
    e.production = production(e, reopened(e)); e.graph.configure_media(e.production)
    listed = next(item for item in e.production.timeline_list(e.nid, e.scope, e.actor, lambda: None)['items'] if item['id'] == row['id'])
    current = read(e, listed)
    assert listed == current == row and exact_saved(current, value) == command
    assert get(e, parent) == parent and _raw(e, parent) == parent_raw and not render_calls
    # Neither saving nor re-reading carries an admission/execute confirmation.
    captured = preview(e, command)
    assert captured['command'] == command and captured['automatic_dispatch'] is False
    assert not render_calls
    with pytest.raises(REJECTED): queue(e, command, {'preview_digest': 'a' * 64})
    queued = queue(e, command, captured)
    assert queued['status'] == 'QUEUED' and queued['canvas_video'] == command and not render_calls
    candidate = execute(e, queued)
    assert candidate['status'] == 'SUCCEEDED' and len(render_calls) == 1
    _, data = e.production.candidate(e.nid, e.scope, e.actor, 'timeline', candidate['id'], lambda: None)
    output_path = tmp_path / 'saved-unqueued-video-after-reopen.mp4'; output_path.write_bytes(data)
    measured = _decoded_measurement(output_path)
    assert (measured['width'], measured['height'], measured['duration_ms'], measured['decoded_frames'], measured['fps']) == (640, 360, 800, 20, '25/1')
    assert measured['sha256'] == candidate['output_candidate']['digest']
    assert measured['byte_count'] == len(data) == candidate['media_measurement']['byte_count']
    assert get(e, parent) == parent and _raw(e, parent) == parent_raw
    if directory := os.environ.get('STUDIO_VIDEO_DRAFT_CAPTURE_DIR'):
        target = Path(directory); target.mkdir(parents=True, exist_ok=True)
        (target / 'native-saved-draft.json').write_text(json.dumps({
            'contract': 'synthetic-video-saved-draft-proof/1', 'backend': e.backend,
            'real_cpu_ffmpeg': True, 'model_called': False, 'stored_inputs_only': True,
            'source_asset': e.source, 'canvas': e.canvas, 'parent_failed': parent,
            'parent_timeline': e.timeline, 'saved_timeline': row, 'read_timeline': current,
            'draft_input': value, 'derived_command': command, 'preview': captured,
            'queued': queued, 'executed': candidate, 'output': measured,
            'candidate_base64': base64.b64encode(data).decode('ascii')}, ensure_ascii=False, indent=2), encoding='utf-8')


@pytest.mark.parametrize('mutation', ['null', 'proof', 'preview', 'extra', 'parent-proof', 'same-request'])
def test_saved_draft_input_never_accepts_reusable_authority_or_extra_fields(bridge, render_calls, monkeypatch, mutation):
    e = bridge; parent = _failed(e, monkeypatch); value = inputs(e, parent)
    if mutation == 'null': value = None
    elif mutation == 'proof': value['proof'] = {'confirmed': True}
    elif mutation == 'preview': value['reviewed_preview_digest'] = 'a' * 64
    elif mutation == 'extra': value['automatic_execute'] = True
    elif mutation == 'parent-proof': value['derived_from']['confirmation'] = True
    else: value['request_id'] = parent['request_id']
    request = body(e, inputs(e, parent)); request['canvas_video_draft'] = value
    before = deepcopy(e.store.read(e.nid, e.scope))
    with pytest.raises(REJECTED):
        e.production.timeline_save(e.nid, e.scope, e.actor, None, request, lambda: None)
    assert e.store.read(e.nid, e.scope) == before and not render_calls


def test_saved_metadata_must_compile_to_the_exact_saved_timeline(bridge, render_calls, monkeypatch):
    e = bridge; parent = _failed(e, monkeypatch); value = inputs(e, parent)
    request = body(e, value); request['canvas_video_draft']['parameters']['out_ms'] = 1840
    before = deepcopy(e.store.read(e.nid, e.scope))
    with pytest.raises(REJECTED):
        e.production.timeline_save(e.nid, e.scope, e.actor, None, request, lambda: None)
    assert e.store.read(e.nid, e.scope) == before and not render_calls


def test_draft_updates_use_original_cas_history_and_old_aba_version_cannot_overwrite(bridge, render_calls, monkeypatch):
    e = bridge; parent = _failed(e, monkeypatch); first = inputs(e, parent)
    a = save(e, first); a_command = deepcopy(exact_saved(a, first))
    second = inputs(e, parent, out_ms=1840); b = save(e, second, a)
    assert b['id'] == a['id'] and b['version'] == a['version'] + 1
    assert exact_saved(b, second)['timeline_snapshot']['version'] == 2
    history = e.production.timeline_history(e.nid, e.scope, e.actor, a['id'], lambda: None)
    old = next(item for item in history['items'] if item['version'] == a['version'])
    assert old['canvas_video_draft'] == a_command
    before = read(e, b)
    with pytest.raises(REJECTED): save(e, first, a)
    assert read(e, b) == before
    again = save(e, first, b)
    assert again['version'] == a['version'] + 2 and again['timeline_digest'] == a['timeline_digest']
    assert exact_saved(again, first)['timeline_snapshot']['version'] == 3
    with pytest.raises(REJECTED): save(e, second, a)
    assert read(e, again) == again and not render_calls


def test_two_original_cas_writers_admit_only_one_draft_update(bridge, render_calls, monkeypatch):
    e = bridge; parent = _failed(e, monkeypatch); initial = save(e, inputs(e, parent))
    barrier = Barrier(2)
    def writer(out_ms):
        barrier.wait(timeout=10)
        try: return save(e, inputs(e, parent, out_ms=out_ms), initial)
        except REJECTED as exc: return exc
    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(writer, 1840), pool.submit(writer, 1880)
        results = [a.result(timeout=20), b.result(timeout=20)]
    successes = [row for row in results if isinstance(row, dict)]
    assert len(successes) == 1 and len([x for x in results if isinstance(x, REJECTED)]) == 1
    current = read(e, initial)
    assert current == successes[0] and current['version'] == initial['version'] + 1 and not render_calls


@pytest.mark.parametrize('field', ['request-id', 'parent-version', 'parent-digest', 'other-card', 'source-pin'])
def test_saved_draft_cannot_be_rebound_even_with_current_timeline_cas(bridge, render_calls, monkeypatch, field):
    e = bridge; parent = _failed(e, monkeypatch); value = inputs(e, parent); row = save(e, value)
    changed = deepcopy(value)
    if field == 'request-id': changed['request_id'] = 'different-draft-request'
    elif field == 'parent-version': changed['derived_from']['job_version'] += 1
    elif field == 'parent-digest': changed['derived_from']['request_digest'] = 'f' * 64
    elif field == 'other-card': changed['canvas_return']['card_id'] = 'another-video'
    else:
        changed['source_snapshots'][0]['version'] += 1
        changed['canvas_return']['source'] = deepcopy(changed['source_snapshots'][0])
    with pytest.raises(REJECTED): save(e, changed, row)
    assert read(e, row) == row and not render_calls


def test_generic_original_timeline_edit_retires_old_draft_version_without_rebinding(bridge, render_calls, monkeypatch):
    e = bridge; parent = _failed(e, monkeypatch); value = inputs(e, parent); row = save(e, value)
    command = deepcopy(exact_saved(row, value))
    edited = e.production.timeline_save(e.nid, e.scope, e.actor, row['id'], {
        'expected_version': row['version'], 'title': 'Explicit generic Timeline edit',
        'timeline': row['timeline']}, lambda: None)
    assert edited['version'] == row['version'] + 1
    assert edited['canvas_video_draft'] == command
    assert edited['canvas_video_draft']['timeline_snapshot']['version'] != edited['version']
    with pytest.raises(REJECTED): preview(e, command)
    assert read(e, edited) == edited and not render_calls


@pytest.mark.parametrize('mutation', ['canvas-version', 'card-deleted', 'source-pin', 'source-deleted'])
def test_reopen_revalidates_current_canvas_and_asset_pins_without_dispatch(bridge, render_calls, monkeypatch, mutation):
    e = bridge; parent = _failed(e, monkeypatch); value = inputs(e, parent); row = save(e, value)
    change(e, mutation)
    e.production = production(e, reopened(e)); e.graph.configure_media(e.production)
    with pytest.raises(REJECTED): read(e, row)
    with pytest.raises(REJECTED): save(e, value, row)
    assert get(e, parent) == parent and not render_calls


@pytest.mark.parametrize('mutation', ['actor', 'project', 'incarnation'])
def test_saved_draft_read_and_write_cannot_cross_project_author_or_incarnation(bridge, render_calls, monkeypatch, mutation):
    e = bridge; parent = _failed(e, monkeypatch); value = inputs(e, parent); row = save(e, value)
    nid, scope, actor = e.nid, deepcopy(e.scope), e.actor
    if mutation == 'actor': actor = 'other-local-author'
    elif mutation == 'project':
        nid = e.create_project('Other saved draft project'); scope = {'mode': 'local', 'novel_id': nid}
        e.service.activate(nid, scope, actor)
    else:
        e.novels.delete(nid); e.create_project('Recreated saved draft project', nid)
        e.service.activate(nid, scope, actor)
    with pytest.raises(REJECTED): e.production.timeline_get(nid, scope, actor, row['id'], lambda: None)
    with pytest.raises(REJECTED): e.production.timeline_save(nid, scope, actor, row['id'], body(e, value, version=row['version']), lambda: None)
    assert not render_calls


def test_unknown_parent_cannot_be_saved_as_a_recoverable_failed_draft(bridge, render_calls, monkeypatch):
    e = bridge; queued = queue(e)
    def unknown_before_render(*args, **kwargs): raise subprocess.TimeoutExpired('synthetic-before-render', 1)
    with monkeypatch.context() as patch:
        patch.setattr(studio_timeline_render, 'render_studio_timeline', unknown_before_render)
        parent = execute(e, queued)
    parent = get(e, parent)
    assert parent['status'] == 'UNKNOWN' and parent['automatic_replay'] is False
    before = deepcopy(e.store.read(e.nid, e.scope))
    with pytest.raises(REJECTED): save(e, inputs(e, parent))
    assert e.store.read(e.nid, e.scope) == before and not render_calls


def test_saved_draft_reopen_rechecks_failed_parent_status_from_original_owner(bridge, render_calls, monkeypatch):
    e = bridge; parent = _failed(e, monkeypatch); row = save(e, inputs(e, parent))
    original = e.production.view; reads = []
    def unknown_view(raw, owner):
        result = original(raw, owner)
        if raw['id'] == parent['id']:
            reads.append(raw['id']); result = deepcopy(result); result['status'] = 'UNKNOWN'
        return result
    monkeypatch.setattr(e.production, 'view', unknown_view)
    with pytest.raises(REJECTED): read(e, row)
    assert reads and not render_calls


def test_denied_guard_leaves_saved_draft_and_original_failed_record_unchanged(bridge, render_calls, monkeypatch):
    e = bridge; parent = _failed(e, monkeypatch); value = inputs(e, parent); row = save(e, value)
    raw = deepcopy(_raw(e, parent)); before = deepcopy(e.store.read(e.nid, e.scope))
    def denied(): raise PermissionError('Synthetic revoked domain grant')
    with pytest.raises(PermissionError): read(e, row, guard=denied)
    with pytest.raises(PermissionError): save(e, inputs(e, parent, out_ms=1840), row, guard=denied)
    assert e.store.read(e.nid, e.scope) == before and _raw(e, parent) == raw and not render_calls


def test_corrupt_saved_draft_digest_is_not_silently_adopted(bridge, render_calls, monkeypatch):
    e = bridge; parent = _failed(e, monkeypatch); row = save(e, inputs(e, parent))
    with e.store.transaction(e.nid, e.scope) as document:
        document['collections'][TIMELINES][row['id']]['canvas_video_draft_digest'] = 'f' * 64
    with pytest.raises(REJECTED): read(e, row)
    assert not render_calls
