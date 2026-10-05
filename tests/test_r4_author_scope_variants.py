"""U08 removals and exact bounded variants: synthetic adapter capture, no provider IO."""
import copy
import json
import threading
import uuid

import pytest

from test_r4_author_context import rig, preview, generate, url


def scope(**changes):
    return dict(source_mode='AUTO', include_automatic_context=True, include_style_reference=True,
                include_plan_reference=True, **{}) | changes


@pytest.mark.parametrize('mode', ['SELECTION_ONLY', 'NONE'])
def test_reduced_source_omits_whole_derived_bundle_and_never_falls_back(rig, mode):
    rig.chapter['content'] = 'PRIVATE_TAIL ' + rig.chapter['content']
    rig.sources['summaries'] = [{'text': 'PRIVATE_DERIVED'}]
    rig.sources['novel']['title'] = 'PRIVATE_POLICY_COPY'
    rig.manager.contexts.for_chapter = lambda *_: pytest.fail('excluded automatic sources must not even be resolved')
    body = {**rig.body, 'request_scope': scope(source_mode=mode)}
    value = preview(rig, body)
    assert value['request']['context'] == {} and value['context_sections'] == []
    assert value['scope_effects']['references_omitted_for_source_isolation']
    assert 'PRIVATE_' not in json.dumps(value['request'])
    assert value['source_characters'] == (len('selection') if mode == 'SELECTION_ONLY' else 0)
    assert ('SOURCE:' in value['request']['prompt']) == (mode == 'SELECTION_ONLY')
    assert generate(rig, value, body).json()['status'] == 'COMPLETED'
    assert rig.state.sent == [value['request']]


def test_remove_automatic_bundle_keeps_explicit_source_and_receipt_binds_every_option(rig):
    body = {**rig.body, 'request_scope': scope(include_automatic_context=False)}
    value = preview(rig, body)
    assert value['request']['context'] == {} and value['source_characters'] == len('selection')
    assert generate(rig, value, {**body, 'request_scope': scope(include_automatic_context=False, include_plan_reference=False)}).status_code == 409
    assert not rig.state.sent
    # Even an excluded reference ID is an input change, not a reusable receipt.
    body['request_scope']['include_plan_reference'] = False
    value = preview(rig, body)
    assert generate(rig, value, {**body, 'plot_plan_id': 'changed-excluded-reference'}).status_code == 409


@pytest.mark.parametrize('change', ['scope', 'selection', 'tail'])
def test_last_dispatch_rechecks_scope_and_source(rig, change):
    body = {**rig.body, 'request_scope': scope(source_mode='SELECTION_ONLY')}
    value = preview(rig, body)
    def mutate():
        if change == 'scope': rig.state.created[0].request_scope['source_mode'] = 'AUTO'
        elif change == 'selection': rig.state.created[0].source = 'Saved'
        else: rig.chapter['content'] += 'new text with same version'
    rig.state.before_send = mutate
    assert generate(rig, value, body).json()['status'] == 'FAILED'
    assert not rig.state.sent


@pytest.mark.parametrize('body', [
    {'request_scope': scope(source_mode='SELECTION_ONLY'), 'source': '', 'selected_text': ''},
    {'request_scope': scope(source_mode='NONE'), 'operation': 'rewrite'},
    {'request_scope': scope(include_automatic_context='false')},
    {'request_scope': scope(unknown_option=True)},
])
def test_scope_controls_reject_invalid_or_unsupported_inputs(rig, body):
    assert rig.client.post(url('preview'), json={**rig.body, **body}, headers=rig.headers).status_code == 422
    assert not rig.state.sent


@pytest.fixture
def batch_rig(rig):
    rig.manager.jobs = {}; rig.manager.lock = threading.Lock()
    rig.batch = {'author': {**rig.body, 'request_scope': scope(source_mode='SELECTION_ONLY')},
                 'count': 3, 'group_id': str(uuid.uuid4())}
    return rig


def batch_preview(rig):
    response = rig.client.post(url('preview-variants'), json=rig.batch, headers=rig.headers)
    assert response.status_code == 200, response.text
    value = response.json()
    rig.batch['receipts'] = [{'variant_index': index + 1, 'preview_digest': row['preview_digest']}
                             for index, row in enumerate(value['variants'])]
    return value


def batch_generate(rig, body=None):
    return rig.client.post(url('generate-variants'), json=body or rig.batch, headers=rig.headers)


def test_each_variant_has_exact_reviewed_instruction_payload_digest_and_persisted_job_id(batch_rig):
    rig = batch_rig; value = batch_preview(rig)
    assert not rig.state.sent and not rig.manager.jobs
    assert len({row['preview_digest'] for row in value['variants']}) == 3
    for index, row in enumerate(value['variants']):
        assert f'候选方案 {index+1}' in row['request']['prompt']
    response = batch_generate(rig)
    assert response.status_code == 202, response.text
    assert response.json()['batch_state'] == 'COMPLETED'
    assert rig.state.sent == [row['request'] for row in value['variants']]
    assert [job.id for job in rig.state.created] == [row['variant']['job_id'] for row in value['variants']]
    assert len(rig.manager.variants(rig.batch['group_id'])) == 3
    assert batch_generate(rig).json() == response.json() and len(rig.state.sent) == 3
    for job in rig.state.created:
        assert job.public()['reviewed_variant']['count'] == 3
        assert job.public()['expected_request_digest']


@pytest.mark.parametrize('change', ['missing', 'reorder', 'duplicate', 'count', 'group', 'instruction', 'scope', 'model'])
def test_variant_review_cannot_be_reused_for_another_request_or_incomplete_batch(batch_rig, change):
    rig = batch_rig; batch_preview(rig); body = copy.deepcopy(rig.batch)
    if change == 'missing': body['receipts'].pop()
    elif change == 'reorder': body['receipts'].reverse()
    elif change == 'duplicate': body['receipts'][1] = body['receipts'][0]
    elif change == 'count': body['count'] = 2; body['receipts'].pop()
    elif change == 'group': body['group_id'] = str(uuid.uuid4())
    elif change == 'scope': body['author']['request_scope']['include_plan_reference'] = False
    elif change == 'model': body['author']['model_id'] = 'different-model'
    else: body['author']['instruction'] = 'changed'
    assert batch_generate(rig, body).status_code in {409, 422}
    assert not rig.state.sent and not rig.manager.jobs


def test_late_mutation_cancels_only_affected_variant_without_hidden_fallback(batch_rig):
    rig = batch_rig; value = batch_preview(rig)
    def mutate():
        job = rig.state.created[-1]
        if job.variant_index == 2: job.cancelled.set()
    rig.state.before_send = mutate
    response = batch_generate(rig).json()
    assert response['batch_state'] == 'PARTIAL'
    assert [row['status'] for row in response['variants']] == ['COMPLETED', 'CANCELLED', 'COMPLETED']
    assert rig.state.sent == [value['variants'][0]['request'], value['variants'][2]['request']]
    assert batch_generate(rig).json() == response and len(rig.state.sent) == 2


def test_start_failure_preserves_all_ids_and_does_not_retry_remaining_variants(batch_rig):
    rig = batch_rig; batch_preview(rig)
    original = rig.manager.start_prepared
    def start(job):
        if job.variant_index == 2: raise RuntimeError('synthetic start failed')
        return original(job)
    rig.manager.start_prepared = start
    response = batch_generate(rig).json()
    assert response['batch_state'] == 'PARTIAL'
    assert len(response['variants']) == 3 and len(rig.state.sent) == 1
    assert [row['status'] for row in response['variants']] == ['COMPLETED', 'CANCELLED', 'CANCELLED']
    assert batch_generate(rig).json() == response and len(rig.state.sent) == 1


def test_incomplete_persisted_group_reports_unknown_never_refills_missing_job(batch_rig):
    rig = batch_rig; batch_preview(rig); response = batch_generate(rig).json()
    rig.manager.jobs.pop(response['variants'][1]['job_id'])
    replay = batch_generate(rig).json()
    assert replay['batch_state'] == 'UNKNOWN' and replay['variants'][1]['receipt_state'] == 'UNKNOWN_NO_AUTOMATIC_REPLAY'
    assert len(rig.state.sent) == 3 and len(rig.manager.jobs) == 2


def test_batch_stage_failure_starts_no_provider_and_remains_once_only(batch_rig):
    rig = batch_rig; batch_preview(rig)
    rig.manager._persist = lambda job: (_ for _ in ()).throw(OSError('synthetic persistence failure'))
    response = batch_generate(rig).json()
    assert response['batch_state'] == 'UNKNOWN' and len(response['variants']) == 3
    assert all(row['receipt_state'] == 'PERSISTENCE_UNCERTAIN' for row in response['variants'])
    assert not rig.state.sent
    assert batch_generate(rig).json() == response and not rig.state.sent


def test_cloud_or_unbounded_variants_cannot_bypass_budget(batch_rig):
    rig = batch_rig
    for count in [0, 1, 4, True]:
        assert rig.client.post(url('preview-variants'), json={**rig.batch, 'count': count}, headers=rig.headers).status_code == 422
    rig.state.cloud = True
    assert rig.client.post(url('preview-variants'), json=rig.batch, headers=rig.headers).status_code == 409
    assert not rig.state.sent


def test_variant_policy_receipt_change_between_preview_and_generation_blocks_entire_batch(batch_rig):
    rig = batch_rig; batch_preview(rig)
    rig.state.variant_policy = lambda: {'policy': 'CHANGED_BUDGET'}
    assert batch_generate(rig).status_code == 409
    assert not rig.state.sent and not rig.manager.jobs


def test_last_dispatch_variant_policy_change_prevents_adapter_call(batch_rig):
    rig = batch_rig; batch_preview(rig)
    rig.state.before_send = lambda: setattr(rig.state, 'variant_policy', lambda: {'policy': 'CHANGED_BUDGET'})
    response = batch_generate(rig).json()
    assert response['batch_state'] == 'PARTIAL'
    assert not rig.state.sent


def test_missing_policy_guard_fails_closed_before_any_context_resolution(rig):
    from fastapi import HTTPException
    from app.experimental.author_context_api import AuthorPreparer, AuthorPreviewInput
    preparer = AuthorPreparer(rig.manager, lambda *_: ('actor', {}), lambda *_: None, lambda *_: (None, None), lambda body, *_: body.model_dump())
    with pytest.raises(HTTPException) as error:
        preparer.prepare_preview('n', AuthorPreviewInput.model_validate(rig.body), variant={'count': 2})
    assert error.value.detail['code'] == 'AUTHOR_VARIANT_POLICY_GUARD_UNAVAILABLE'
    assert not rig.state.sent


def test_changed_policy_immediately_before_group_staging_records_no_authorized_jobs(batch_rig):
    rig = batch_rig; batch_preview(rig)
    calls = 0
    def policy():
        nonlocal calls
        calls += 1
        return {'policy': 'SYNTHETIC_NO_BUDGET' if calls <= 6 else 'NEW_POLICY'}
    rig.state.variant_policy = policy
    assert batch_generate(rig).status_code == 409
    assert not rig.state.sent and not rig.manager.jobs
