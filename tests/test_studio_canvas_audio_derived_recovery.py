"""Explicit derivation from real File AudioJob failure, never original request replay.

The additive derived_from integration cases require root's shared command/owner
implementation. Baseline-compatible tests are named test_baseline_*. Synthetic
PCM and original owner persistence only; no inference/provider/network calls.
"""
from copy import deepcopy

import pytest

from app.creative.production_execution_models import MediaCommand
from app.experimental.common import StaleSourceError
from app.services.audiobook_service import AudiobookError
from app.services.studio_audio_execution import StudioAudioExecution
from test_studio_canvas_audio_return import audio_canvas, change_origin, save_result
from test_v2_independent_workspace import rig, reopened
from test_v2_audio_wav_controls import production, preview, queue, run, get, review


@pytest.fixture
def failed_audio(audio_canvas, monkeypatch):
    e = audio_canvas
    queued = queue(e)

    def fail_local_trim(*_args, **_kwargs):
        raise AudiobookError('TEST_LOCAL_TRIM_FAILED', 'synthetic local failure before output', 502)

    # Real execute claim -> native known-failure transition -> original File receipt.
    # Only the bounded local processing call fails; no invented ProductionJob DTO.
    with monkeypatch.context() as local:
        local.setattr(StudioAudioExecution, '_trim', fail_local_trim)
        failed = run(e, queued)
    assert failed['status'] == 'FAILED' and failed['owner'] == 'audio'
    assert failed['output_candidate'] is None and failed['provider'] is None
    assert failed['remote_compute_may_continue'] is False and failed['automatic_replay'] is False
    e.failed = failed
    return e


def derived_command(e, failed=None, request='explicit-derived-trim'):
    row = failed or e.failed
    value = deepcopy(e.command)
    value['request_id'] = request
    value['derived_from'] = {'owner': 'audio', 'job_id': row['id'], 'job_version': row['version'],
        'request_id': row['request_id'], 'request_digest': row['request_digest'], 'receipt_digest': row['receipt_digest']}
    return value


def rows(e):
    audio = e.production._audio(e.scope, e.actor)
    return audio.list(e.nid, e.production._base(e.nid, e.scope, e.actor, lambda: None), lambda: None)


def test_baseline_real_failed_owner_receipt_reopens_and_never_replays(failed_audio):
    e = failed_audio
    assert 'derived_from' not in e.failed['command']
    original = deepcopy(e.failed)
    e.production = production(e, reopened(e))
    e.graph.configure_media(e.production)
    assert get(e, e.failed) == original
    with pytest.raises(AudiobookError):
        run(e, e.failed)
    assert get(e, e.failed) == original and len(rows(e)) == 1
    assert e.graph.canvas_views.get(e.nid, e.scope, e.actor, e.canvas['id']) == e.canvas


@pytest.mark.parametrize('controls', [{}, {'gain_db': 0, 'fade_in_ms': 0, 'fade_out_ms': 0}])
def test_baseline_old_command_omits_derived_from_and_keeps_optional_controls(audio_canvas, controls):
    e = audio_canvas
    e.command['parameters'].update(controls)
    captured = preview(e)
    queued = queue(e)
    assert 'derived_from' not in captured['command'] and 'derived_from' not in queued['command']
    for key in ('gain_db', 'fade_in_ms', 'fade_out_ms'):
        assert (key in queued['command']['parameters']) == (key in controls)
    assert queued['execution_recipe']['parameters'] == e.command['parameters']


@pytest.mark.parametrize('controls', [{}, {'gain_db': 0, 'fade_in_ms': 0, 'fade_out_ms': 0},
    {'gain_db': -6, 'fade_in_ms': 75, 'fade_out_ms': 125}])
def test_derived_preview_and_queue_preserve_failure_and_exact_envelope(audio_canvas, monkeypatch, controls):
    e = audio_canvas
    e.command['parameters'].update(controls)
    queued = queue(e)

    def fail(*_args, **_kwargs):
        raise AudiobookError('TEST_LOCAL_TRIM_FAILED', 'synthetic known failure', 502)

    with monkeypatch.context() as local:
        local.setattr(StudioAudioExecution, '_trim', fail)
        e.failed = run(e, queued)
    assert e.failed['status'] == 'FAILED'
    value = derived_command(e)
    original = deepcopy(e.failed)
    monkeypatch.setattr(StudioAudioExecution, '_trim', lambda *a, **k: pytest.fail('derive/preview/queue must not execute'))
    captured = preview(e, value)
    assert len(rows(e)) == 1 and get(e, original) == original
    assert captured['command']['derived_from'] == value['derived_from']
    assert {k: v for k, v in captured['command']['parameters'].items() if v is not None} == e.command['parameters']
    assert captured['command']['canvas_return'] == original['command']['canvas_return']
    derived = queue(e, value)
    assert derived['id'] != original['id'] and derived['request_id'] != original['request_id']
    assert derived['status'] == 'QUEUED' and derived['output_candidate'] is None
    assert derived['command']['derived_from'] == value['derived_from']
    assert derived['execution_recipe']['parameters'] == original['execution_recipe']['parameters']
    assert get(e, original) == original and len(rows(e)) == 2
    assert e.graph.canvas_views.get(e.nid, e.scope, e.actor, e.canvas['id']) == e.canvas
    e.production = production(e, reopened(e))
    e.graph.configure_media(e.production)
    assert get(e, derived)['command']['derived_from'] == value['derived_from']
    assert get(e, original) == original


def test_explicit_derived_job_still_requires_execute_review_and_canvas_cas(failed_audio):
    e = failed_audio
    original = deepcopy(e.failed)
    derived = queue(e, derived_command(e))
    assert derived['status'] == 'QUEUED' and len(e.service.list_assets(e.nid, e.scope)['items']) == 1
    candidate = run(e, derived)
    assert candidate['status'] == 'AWAITING_REVIEW'
    assert candidate['media_measurement']['profile_validation'] == 'PCM_DECODED'
    assert candidate['command']['derived_from']['job_id'] == original['id']
    assert e.graph.canvas_views.get(e.nid, e.scope, e.actor, e.canvas['id']) == e.canvas
    approved = review(e, candidate)
    saved = save_result(e, approved)
    assert saved['version'] == e.canvas['version'] + 1
    assert saved['definition']['cards'][0]['asset']['asset_id'] == approved['output_candidate']['id']
    assert saved['definition']['cards'][1] == e.canvas['definition']['cards'][1]
    assert get(e, original) == original


@pytest.mark.parametrize('change', ['owner', 'job', 'version', 'old-request', 'request-digest', 'receipt-digest',
    'missing-receipt', 'extension', 'null', 'reused-request', 'source', 'return-card'])
def test_forged_or_changed_failed_origin_refuses_before_new_job(failed_audio, change, monkeypatch):
    e = failed_audio
    value = derived_command(e)
    origin = value['derived_from']
    if change == 'owner': origin['owner'] = 'video'
    elif change == 'job': origin['job_id'] = 'other-job'
    elif change == 'version': origin['job_version'] += 1
    elif change == 'old-request': origin['request_id'] = 'other-request'
    elif change == 'request-digest': origin['request_digest'] = 'f' * 64
    elif change == 'receipt-digest': origin['receipt_digest'] = 'f' * 64
    elif change == 'missing-receipt': origin.pop('receipt_digest')
    elif change == 'extension': origin['credential'] = 'must-not-be-admitted'
    elif change == 'null': value['derived_from'] = None
    elif change == 'reused-request': value['request_id'] = e.failed['request_id']
    elif change == 'source': value['source_snapshots'][0]['version'] += 1
    elif change == 'return-card': value['canvas_return']['card_id'] = 'other-audio'
    monkeypatch.setattr(StudioAudioExecution, '_trim', lambda *a, **k: pytest.fail('invalid derivation must not execute'))
    with pytest.raises((ValueError, AudiobookError, FileNotFoundError, StaleSourceError)):
        preview(e, value)
    assert get(e, e.failed) == e.failed and len(rows(e)) == 1


@pytest.mark.parametrize('status', ['UNKNOWN', 'RUNNING', 'QUEUED', 'CANCELLED'])
def test_only_original_failed_status_can_supply_derivation(failed_audio, status):
    e = failed_audio
    audio = e.production._audio(e.scope, e.actor)

    def update(state):
        row = audio.service.find(state, e.failed['id'])
        row['status'] = status
        row['dispatch_state'] = 'OUTCOME_UNKNOWN' if status == 'UNKNOWN' else 'NOT_SENT'
        row['version'] += 1
        audio._receipt(row)

    audio.store.mutate(e.nid, update)
    current = get(e, e.failed)
    assert current['status'] == status
    with pytest.raises((ValueError, AudiobookError, FileNotFoundError, StaleSourceError)):
        preview(e, derived_command(e, current))
    assert get(e, current) == current and len(rows(e)) == 1


@pytest.mark.parametrize('change', ['version', 'deleted-card', 'source-pin', 'source-deleted'])
def test_changed_or_replaced_target_cannot_be_derived(failed_audio, change):
    e = failed_audio
    value = derived_command(e)
    change_origin(e, change)
    with pytest.raises((ValueError, AudiobookError, FileNotFoundError, StaleSourceError)):
        preview(e, value)
    assert get(e, e.failed) == e.failed and len(rows(e)) == 1


@pytest.mark.parametrize('change', ['other-project', 'recreated-project'])
def test_original_failed_job_cannot_cross_scope_or_project_incarnation(failed_audio, change):
    e = failed_audio
    value = derived_command(e)
    if change == 'other-project':
        nid = e.create_project('Other neutral owner')
        scope = {'mode': 'local', 'novel_id': nid}
    else:
        e.novels.delete(e.nid)
        e.create_project('Recreated neutral owner', e.nid)
        nid, scope = e.nid, e.scope
    e.service.activate(nid, scope, e.actor)
    with pytest.raises((ValueError, AudiobookError, FileNotFoundError, StaleSourceError)):
        e.production.preview(nid, scope, e.actor, value, lambda: None)


@pytest.mark.parametrize('patch', [{'job_version': True}, {'job_version': 0}, {'job_version': 1.5},
    {'request_digest': 'bad'}, {'receipt_digest': 'bad'}, {'owner': 'timeline'}])
def test_derived_origin_wire_fields_remain_closed_strict_and_bounded(patch):
    value = {'owner': 'audio', 'job_id': 'failed', 'job_version': 4, 'request_id': 'original',
        'request_digest': 'a' * 64, 'receipt_digest': None, **patch}
    from test_v2_audio_wav_controls import command
    with pytest.raises(ValueError):
        MediaCommand.model_validate({**command(), 'derived_from': value})




def test_derived_draft_can_explicitly_change_local_envelope_before_new_preview(failed_audio):
    e = failed_audio
    value = derived_command(e)
    value['parameters'].update(in_ms=500, out_ms=900, gain_db=-3, fade_in_ms=25, fade_out_ms=75)
    original = deepcopy(e.failed)
    captured = preview(e, value)
    assert captured['command']['derived_from'] == value['derived_from']
    assert {k: v for k, v in captured['command']['parameters'].items() if v is not None} == value['parameters']
    assert captured['execution_recipe']['parameters'] == value['parameters']
    assert captured['command']['canvas_return'] == original['command']['canvas_return']
    assert get(e, original) == original and len(rows(e)) == 1


def test_failed_derived_job_can_supply_the_next_explicit_origin_link(failed_audio, monkeypatch):
    e = failed_audio
    original = deepcopy(e.failed)
    first = queue(e, derived_command(e))

    def fail(*_args, **_kwargs):
        raise AudiobookError('TEST_LOCAL_TRIM_FAILED', 'synthetic second known failure', 502)

    with monkeypatch.context() as local:
        local.setattr(StudioAudioExecution, '_trim', fail)
        failed_child = run(e, first)
    assert failed_child['status'] == 'FAILED'
    assert failed_child['command']['derived_from']['job_id'] == original['id']
    value = derived_command(e, failed_child, 'explicit-next-derived-trim')
    next_job = queue(e, value)
    assert next_job['command']['derived_from']['job_id'] == failed_child['id']
    assert next_job['command']['derived_from']['request_id'] == failed_child['request_id']
    assert next_job['command']['canvas_return'] == original['command']['canvas_return']
    assert next_job['status'] == 'QUEUED' and next_job['output_candidate'] is None
    assert get(e, original) == original and get(e, failed_child) == failed_child
    assert len(rows(e)) == 3
