"""Phase 5 original owner pipeline; synthetic transport and real tiny CPU video.

This is not local-model, GPU, Windows Application or movie quality acceptance.
"""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.creative.models import ShotCard
from app.creative.production_execution_models import MediaReview, MediaCommand
from app.creative.production_execution import TIMELINES
from app.creative.storyboard import storyboard_receipt
from app.experimental.common import StaleSourceError
from test_v2_independent_workspace import rig, import_asset, png_bytes, reopened
from test_v2_storyboard_workspace import board_value, content, approve, bind
from test_v2_video_runtime_foundation import configured, queued, action


def job_pin(job):
    return {key: job[key] for key in ('id', 'version', 'request_digest', 'receipt_digest')}


def shot_action(view, shot_id='shot-1'):
    shot = next(item for item in view['shots'] if item['shot_id'] == shot_id)
    return {'expected_version': view['document_snapshot']['version'],
            'shot_version': shot['shot_version'], 'shot_digest': shot['shot_digest']}


@pytest.fixture
def pipeline(rig, tmp_path, monkeypatch):
    e = rig
    discovery, production, adapter, wire, configured_command = configured(e, tmp_path, monkeypatch)
    creative = e.service.creative
    value = board_value(); value['shots'][0]['video_generation_hint'] = 'Keep the jacket and a gentle camera pan'
    row = creative.create(e.nid, e.scope, e.actor, value)
    image = import_asset(e, data=png_bytes(), filename='synthetic-board-reference.png')
    bind(creative, e, row['id'], 'shot-1', image)
    bind(creative, e, row['id'], 'shot-2', image)
    view = approve(creative, e, row['id'])
    body = {'expected_version': view['document_snapshot']['version'], 'reviewed_content_digest': view['content_digest'],
            'title': 'SYNTHETIC production draft', 'shot_ids': ['shot-1', 'shot-2'], 'request_id': 'phase5-timeline'}
    created = creative.storyboards.timeline_create(e.nid, e.scope, e.actor, row['id'], body)
    return SimpleNamespace(e=e, creative=creative, production=production, discovery=discovery, adapter=adapter,
                           wire=wire, command=configured_command, row=row, view=view, create_body=body, created=created)


def generated(p, operation='m7.video.t2v'):
    e = p.e
    prepared = p.creative.storyboards.video_request(e.nid, e.scope, e.actor, p.row['id'], 'shot-1', {
        **shot_action(p.view), 'operation_id': operation, 'request_id': 'phase5-shot-video-' + operation.rsplit('.', 1)[-1],
        'provider': {'operation_id': operation, 'provider_id': p.command['provider_id'], 'model_id': p.command['model_id']},
        'parameters': {'width': 64, 'height': 64, 'frame_rate': 8, 'seed': 7}})
    _, job = queued(e, p.production, prepared['command'])
    job = p.production.execute(e.nid, e.scope, e.actor, 'video', job['id'], action(job), lambda: None)
    assert job['status'] == 'REMOTE_RUNNING'
    ready = p.production.refresh_video(e.nid, e.scope, e.actor, job['id'], action(job), lambda: None)
    with pytest.raises(FileNotFoundError): e.service.asset(e.nid, e.scope, ready['output_candidate']['id'])
    job = p.production.review(e.nid, e.scope, e.actor, 'video', ready['id'],
        MediaReview(**action(ready).model_dump(), reviewed_output_digest=ready['output_candidate']['digest']), lambda: None)
    asset = {'asset_id': job['output_candidate']['id'], 'version': job['approved_asset_version'],
             'digest': job['output_candidate']['digest'], 'kind': 'video'}
    return prepared, job, asset


def attached(p, operation='m7.video.t2v'):
    prepared, job, asset = generated(p, operation)
    view = p.creative.storyboards.bind_video(p.e.nid, p.e.scope, p.e.actor, p.row['id'], 'shot-1', {
        **shot_action(p.view), 'asset': asset, 'video_job': job_pin(job)})
    return prepared, job, asset, view


def adoption(p, view, job, asset):
    timeline = p.created['timeline']
    return {**shot_action(view), 'expected_timeline_version': timeline['version'],
        'reviewed_timeline_digest': timeline['timeline_digest'], 'request_id': 'phase5-adopt-video',
        'clip_id': 'storyboard-1', 'video_asset': asset, 'video_job': job_pin(job),
        'in_ms': 0, 'out_ms': 500, 'include_audio': False}


def test_optional_hint_and_pin_do_not_widen_legacy_commands():
    shot = {'id': 'shot', 'number': 1, 'scene_id': 'scene'}
    assert ShotCard.model_validate(shot).model_dump() == ShotCard.model_validate({**shot, 'video_generation_hint': None}).model_dump()
    assert 'video_generation_hint' not in ShotCard.model_validate(shot).model_dump()
    with pytest.raises(ValidationError): ShotCard.model_validate({**shot, 'video_generation_hint': 'x' * 4001})
    value = {'operation_id': 'm7.video.t2v', 'request_id': 'legacy', 'provider_id': 'provider', 'model_id': 'model', 'prompt': 'legacy'}
    assert MediaCommand.model_validate(value).model_dump() == MediaCommand.model_validate({**value, 'storyboard_shot': None}).model_dump()
    assert 'storyboard_shot' not in MediaCommand.model_validate(value).model_dump()


@pytest.mark.parametrize('operation', ['m7.video.t2v', 'm7.video.i2v'])
def test_exact_shot_video_original_private_review_bind_reapprove_timeline_and_reopen(pipeline, operation):
    p = pipeline; e = p.e
    prepared, job, asset, bound = attached(p, operation)
    assert 'video_generation_hint: Keep the jacket' in prepared['command']['prompt']
    assert job['command']['storyboard_shot'] == prepared['shot_pin']
    assert bound['document_snapshot']['version'] == p.view['document_snapshot']['version'] + 1
    assert bound['shots'][0]['shot_version'] == p.view['shots'][0]['shot_version']
    assert not bound['approved']
    result = bound['shots'][0]['video_result']
    assert result['source_shot'] == prepared['shot_pin'] and result['asset'] == asset
    reviewed = approve(p.creative, e, p.row['id'])
    body = adoption(p, reviewed, job, asset)
    adopted = p.creative.storyboards.adopt_video(e.nid, e.scope, e.actor, p.row['id'], 'shot-1', p.created['timeline']['id'], body)
    assert adopted['timeline']['version'] == 2 and adopted['timeline']['storyboard_origin'] == p.created['storyboard_origin']
    clip = adopted['timeline']['timeline']['tracks'][0]['clips'][0]
    assert clip['source_snapshot']['id'] == asset['asset_id'] and clip['out_ms'] == 500 and not clip['include_audio']
    assert p.creative.storyboards.adopt_video(e.nid, e.scope, e.actor, p.row['id'], 'shot-1', p.created['timeline']['id'], body) == adopted
    recovered = p.creative.storyboards.timeline_creation(e.nid, e.scope, e.actor, p.row['id'], p.create_body['request_id'])
    assert recovered['timeline']['version'] == 2 and recovered['creation_receipt']['creation_snapshot']['version'] == 1
    assert p.creative.storyboards.timeline_create(e.nid, e.scope, e.actor, p.row['id'], p.create_body) == recovered
    raw = p.production.video.get(e.nid, e.scope.get('branch_id'), e.actor, job['id'], context=p.production._base(e.nid, e.scope, e.actor, lambda: None), guard=lambda: None)
    assert raw['context']['storyboard_shot'] == prepared['shot_pin']
    with p.production.timeline_inputs.phase(e.nid, e.scope, e.actor, lambda: None):
        meta = e.assets.get(asset['asset_id'], branch_id=e.scope.get('branch_id'))
        assert meta['_studio_result_origin']['storyboard_shot'] == prepared['shot_pin']
    restored = reopened(e)
    assert restored.asset(e.nid, e.scope, asset['asset_id'])['version'] == asset['version']
    with restored._asset_scope(e.nid, e.scope):
        assert restored.assets.content(asset['asset_id'], branch_id=e.scope.get('branch_id')) == p.wire.data
    assert p.discovery.center.lifecycle.start.call_count == 0


@pytest.mark.parametrize('field', ['request_id', 'asset', 'job', 'source_pin'])
def test_binding_does_not_accept_wrong_or_legacy_proof(pipeline, field):
    p = pipeline; e = p.e; _, job, asset = generated(p)
    body = {**shot_action(p.view), 'asset': asset, 'video_job': job_pin(job)}
    if field == 'asset': body['asset'] = {**asset, 'version': 1}
    elif field == 'job': body['video_job']['receipt_digest'] = '0' * 64
    elif field == 'request_id': body['video_job']['request_digest'] = '0' * 64
    else:
        _, legacy = queued(e, p.production, p.command)
        legacy = p.production.execute(e.nid, e.scope, e.actor, 'video', legacy['id'], action(legacy), lambda: None)
        legacy = p.production.refresh_video(e.nid, e.scope, e.actor, legacy['id'], action(legacy), lambda: None)
        legacy = p.production.review(e.nid, e.scope, e.actor, 'video', legacy['id'],
            MediaReview(**action(legacy).model_dump(), reviewed_output_digest=legacy['output_candidate']['digest']), lambda: None)
        body['video_job'] = job_pin(legacy)
        body['asset'] = {'asset_id': legacy['output_candidate']['id'], 'version': legacy['approved_asset_version'],
                         'digest': legacy['output_candidate']['digest'], 'kind': 'video'}
    with pytest.raises((ValueError, StaleSourceError)):
        p.creative.storyboards.bind_video(e.nid, e.scope, e.actor, p.row['id'], 'shot-1', body)
    assert p.creative.storyboards.get(e.nid, e.scope, e.actor, p.row['id']) == p.view


def test_create_retry_conflict_capacity_and_shot_edit_leave_truthful_history(pipeline):
    p = pipeline; e = p.e
    retry = p.creative.storyboards.timeline_create(e.nid, e.scope, e.actor, p.row['id'], p.create_body)
    assert retry['replayed'] and retry['timeline'] == p.created['timeline']
    with pytest.raises(ValueError, match='IDEMPOTENCY_CONFLICT'):
        p.creative.storyboards.timeline_create(e.nid, e.scope, e.actor, p.row['id'], {**p.create_body, 'title': 'changed'})
    assert len(p.creative.store.read(e.nid, e.scope)['collections'][TIMELINES]) == 1
    _, _, _, bound = attached(p)
    row = p.creative.get(e.nid, e.scope, p.row['id']); value = content(row); value['shots'][0]['video_generation_hint'] = 'Different action'
    p.creative.update(e.nid, e.scope, e.actor, row['id'], row['version'], value)
    edited = p.creative.storyboards.get(e.nid, e.scope, e.actor, row['id'])
    assert 'video_result' not in edited['shots'][0] and edited['shots'][0]['shot_version'] == bound['shots'][0]['shot_version'] + 1
    assert p.creative.storyboards.timeline_creation(e.nid, e.scope, e.actor, row['id'], p.create_body['request_id'])['creation_receipt'] == p.created['creation_receipt']


def test_create_owner_namespace_and_atomic_receipt_rollback(pipeline, monkeypatch):
    p = pipeline; e = p.e
    with pytest.raises(FileNotFoundError):
        p.creative.storyboards.timeline_creation(e.nid, e.scope, 'another-author', p.row['id'], p.create_body['request_id'])
    before = e.raw_store.read(e.nid, e.scope)
    response = p.creative.storyboards._creation_response
    def interrupted(row, scope, **kwargs):
        if row['storyboard_create_receipt']['request_id'] == 'interrupted-create':
            raise PermissionError('synthetic authority revoked after Timeline/receipt construction')
        return response(row, scope, **kwargs)
    monkeypatch.setattr(p.creative.storyboards, '_creation_response', interrupted)
    with pytest.raises(PermissionError):
        p.creative.storyboards.timeline_create(e.nid, e.scope, e.actor, p.row['id'], {**p.create_body, 'request_id': 'interrupted-create'})
    assert e.raw_store.read(e.nid, e.scope) == before
    with pytest.raises(FileNotFoundError):
        p.creative.storyboards.timeline_creation(e.nid, e.scope, e.actor, p.row['id'], 'interrupted-create')


def test_adoption_full_request_identity_and_original_history_restore_remain_distinct(pipeline):
    p = pipeline; e = p.e; _, job, asset, _ = attached(p)
    view = approve(p.creative, e, p.row['id']); body = adoption(p, view, job, asset)
    result = p.creative.storyboards.adopt_video(e.nid, e.scope, e.actor, p.row['id'], 'shot-1', p.created['timeline']['id'], body)
    view = approve(p.creative, e, p.row['id'])
    changed_semantics = {**body, **shot_action(view)}
    with pytest.raises(StaleSourceError, match='IDEMPOTENCY_CONFLICT'):
        p.creative.storyboards.adopt_video(e.nid, e.scope, e.actor, p.row['id'], 'shot-1', p.created['timeline']['id'], changed_semantics)
    assert p.production.timeline_get(e.nid, e.scope, e.actor, p.created['timeline']['id'], lambda: None) == result['timeline']
    edited = p.production.timeline_edit(e.nid, e.scope, e.actor, result['timeline']['id'], {
        'expected_version': 2, 'reviewed_timeline_digest': result['timeline']['timeline_digest'], 'request_id': 'later-author-edit',
        'operations': [{'op': 'track.update', 'track_id': 'storyboard-video', 'changes': {'muted': True}}]}, lambda: None)
    assert edited['version'] == 3 and 'video_adoption_receipt' not in edited
    history = p.production.timeline_history(e.nid, e.scope, e.actor, edited['id'], lambda: None)
    prior = {row['version']: row for row in history['items']}
    assert prior[2]['video_adoption_receipt'] == result['adoption_receipt']
    assert 'video_adoption_receipt' not in prior[1]
    restored = p.production.timeline_restore(e.nid, e.scope, e.actor, edited['id'], {
        'expected_version': 3, 'reviewed_timeline_digest': edited['timeline_digest'], 'restore_version': 2,
        'restore_digest': result['timeline']['timeline_digest']}, lambda: None)
    assert restored['version'] == 4 and restored['timeline'] == result['timeline']['timeline']
    assert 'video_adoption_receipt' not in restored
    assert p.creative.storyboards.timeline_creation(e.nid, e.scope, e.actor, p.row['id'], p.create_body['request_id'])['timeline'] == restored


def test_creation_does_not_borrow_deleted_recreated_project(pipeline, monkeypatch):
    from app.creative.graph_asset_inputs import GraphAssetInputs
    p = pipeline; e = p.e; identity = e.store.incarnation(e.nid)
    e.novels.delete(e.nid); e.create_project('Recreated isolated test project', nid=e.nid)
    fresh = reopened(e)
    fresh.activate(e.nid, e.scope, e.actor)
    assert fresh.store.incarnation(e.nid) != identity
    monkeypatch.setattr(p.production, 'workspace', fresh); monkeypatch.setattr(p.production, 'store', fresh.store)
    monkeypatch.setattr(p.production, 'timeline_inputs', GraphAssetInputs(p.production))
    fresh.creative.configure_storyboard_production(p.production)
    with pytest.raises(FileNotFoundError):
        fresh.creative.storyboards.timeline_creation(e.nid, e.scope, e.actor, p.row['id'], p.create_body['request_id'])


def test_native_adoption_probe_is_outside_asset_phase_and_late_revoke_rolls_back(pipeline, monkeypatch):
    p = pipeline; e = p.e; _, job, asset, _ = attached(p)
    view = approve(p.creative, e, p.row['id']); body = adoption(p, view, job, asset)
    import app.services.studio_timeline_export as native
    real = native.run_guarded_process; calls = []; revoked = [False]
    def current():
        if revoked[0]: raise PermissionError('synthetic revoked authority after actual probe')
    def observed(*args, **kwargs):
        assert not p.production.timeline_inputs.in_phase(e.nid, e.scope, e.actor)
        assert getattr(e.assets._scope, 'binding', None) is None
        calls.append(True)
        result = real(*args, **kwargs)
        revoked[0] = True; kwargs['guard']()
        return result
    monkeypatch.setattr(native, 'run_guarded_process', observed)
    with pytest.raises(PermissionError):
        p.creative.storyboards.adopt_video(e.nid, e.scope, e.actor, p.row['id'], 'shot-1', p.created['timeline']['id'], body, current)
    assert calls and p.production.timeline_get(e.nid, e.scope, e.actor, p.created['timeline']['id'], lambda: None) == p.created['timeline']


@pytest.mark.parametrize('fault', ['range', 'unapproved', 'locked', 'source_version'])
def test_video_adoption_rejects_range_review_track_and_asset_changes(pipeline, fault):
    p = pipeline; e = p.e; _, job, asset, bound = attached(p)
    view = bound if fault == 'unapproved' else approve(p.creative, e, p.row['id'])
    body = adoption(p, view, job, asset)
    if fault == 'range': body['out_ms'] = 501
    elif fault == 'source_version': body['video_asset'] = {**asset, 'version': 1}
    elif fault == 'locked':
        row = p.created['timeline']
        p.production.timeline_edit(e.nid, e.scope, e.actor, row['id'], {'expected_version': row['version'],
            'reviewed_timeline_digest': row['timeline_digest'], 'request_id': 'lock-track',
            'operations': [{'op': 'track.update', 'track_id': 'storyboard-video', 'changes': {'locked': True}}]}, lambda: None)
        current = p.production.timeline_get(e.nid, e.scope, e.actor, row['id'], lambda: None)
        body.update(expected_timeline_version=current['version'], reviewed_timeline_digest=current['timeline_digest'])
    with pytest.raises((ValueError, StaleSourceError)):
        p.creative.storyboards.adopt_video(e.nid, e.scope, e.actor, p.row['id'], 'shot-1', p.created['timeline']['id'], body)
    row = p.production.timeline_get(e.nid, e.scope, e.actor, p.created['timeline']['id'], lambda: None)
    assert row['timeline']['tracks'][0]['clips'][0]['source_snapshot']['asset_kind'] == 'image'
