"""Mounted U08 scope and bounded variants on File / opt-in real PostgreSQL."""
import copy
import os
import time
import uuid

import pytest
from app.jobs import JobManager
from app.services.context_service import ContextService
from app.services.generation_service import GenerationService
from test_r3_mounted_contracts import mounted, prefix, checked
from test_r4_author_scope_variants import scope


@pytest.fixture
def author_app(mounted, monkeypatch):
    e = mounted; e.manager = e.api.jobs
    # This direct batch profile deliberately has no broker policy. Combined A06
    # policy cases below verify fail-closed behavior rather than bypass its ledger.
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(flag for flag in os.environ['EXPERIMENTAL_FEATURES'].split(',')
        if flag not in {'model_broker_v2', 'model_benchmark_v2'}))
    for name, value in [('chapters', e.chapters), ('contexts', ContextService(e.bundle.novels, e.bundle.chapters,
            enable_lore_context=False, enable_narrative_context=False, enable_context_pack_v2=False)),
            ('persistence', GenerationService(e.bundle.generations)), ('snapshot_required', False), ('jobs', {})]:
        monkeypatch.setattr(e.manager, name, value)
    return e


def author(e, **options):
    return {'novel_id': e.nid, 'chapter_id': e.chapter['id'], 'chapter_version': e.chapter['version'],
        'operation': 'continue', 'provider_id': 'mock', 'model_id': 'mock-writer', 'profile': 'LOCAL_ONLY',
        'instruction': 'Software synthetic protocol check', 'request_scope': scope(**options)}


def wait_jobs(e, ids):
    deadline = time.monotonic() + 10
    while any(e.manager.get(id).status not in e.manager.terminal for id in ids):
        if time.monotonic() > deadline: pytest.fail('original jobs failed to reach terminal')
        time.sleep(.01)
    return [e.manager.get(id) for id in ids]


def test_mounted_removed_source_has_no_auto_context_and_persists_exact_scope(author_app, monkeypatch):
    e = author_app; body = author(e, source_mode='NONE')
    monkeypatch.setattr(e.manager.contexts, 'for_chapter', lambda *_: pytest.fail('omitted context resolver must not run'))
    value = checked(e.client.post(e.base + '/author-context/preview', json=body))
    assert value['request']['context'] == {} and value['source_characters'] == 0
    assert value['source_strategy'] == 'NO_MANUSCRIPT' and value['truncation'] == 'NONE'
    assert e.chapter['content'] not in value['request']['prompt']
    generated = checked(e.client.post(e.base + '/author-context/generate', json={**body, 'preview_digest': value['preview_digest']}), 202)
    job = wait_jobs(e, [generated['job_id']])[0]
    assert job.status == 'COMPLETED'
    stored = e.manager.persistence.get(job.id)
    assert stored['request_scope'] == body['request_scope'] and stored['author_input_digest']
    assert e.chapters.get(e.chapter['id'])['content'] == e.chapter['content']


def test_mounted_each_variant_reuses_original_persistent_group_and_restart_never_replays(author_app, monkeypatch):
    e = author_app
    body = {'author': author(e, source_mode='NONE'), 'count': 2, 'group_id': str(uuid.uuid4())}
    value = checked(e.client.post(e.base + '/author-context/preview-variants', json=body))
    body['receipts'] = [{'variant_index': row['variant']['variant_index'], 'preview_digest': row['preview_digest']} for row in value['variants']]
    generated = checked(e.client.post(e.base + '/author-context/generate-variants', json=body), 202)
    ids = [row['job_id'] for row in generated['variants']]
    assert ids == [row['variant']['job_id'] for row in value['variants']]
    jobs = wait_jobs(e, ids)
    assert all(job.status == 'COMPLETED' for job in jobs)
    for index, job in enumerate(jobs):
        stored = e.manager.persistence.get(job.id)
        assert stored['variant_group_id'] == body['group_id'] and stored['variant_index'] == index + 1
        assert stored['reviewed_variant']['job_id'] == job.id
        assert stored['expected_request_digest'] == value['variants'][index]['preview_digest']
    group = checked(e.client.get(e.prefix + '/generation-groups/' + body['group_id']))
    assert [job['id'] for job in group['variants']] == ids
    restarted = JobManager(generations=e.manager.persistence, chapters=e.chapters, contexts=e.manager.contexts,
                           canon=e.manager.canon, snapshot_required=False)
    monkeypatch.setattr(e.manager, 'jobs', restarted.jobs)
    monkeypatch.setattr(e.manager, 'start_prepared', lambda *_: pytest.fail('a reopened group must not be resent'))
    repeated = checked(e.client.post(e.base + '/author-context/generate-variants', json=body), 202)
    assert [row['job_id'] for row in repeated['variants']] == ids and repeated['batch_state'] == 'COMPLETED'
    assert e.chapters.get(e.chapter['id'])['content'] == e.chapter['content']
    changed = copy.deepcopy(body); changed['author']['instruction'] = 'new'
    assert e.client.post(e.base + '/author-context/generate-variants', json=changed).status_code == 409


def test_mounted_pins_use_current_approved_authority_and_removals_do_not_resolve_missing_references(author_app):
    e = author_app; body = author(e, include_style_reference=False, include_plan_reference=False)
    body.update(style_profile_id='not-an-existing-style', plot_plan_id='not-an-existing-plan')
    value = checked(e.client.post(e.base + '/author-context/preview', json=body))
    assert value['creation_records'] == []
    body['request_scope']['include_style_reference'] = True
    assert e.client.post(e.base + '/author-context/preview', json=body).status_code in {404, 422}
    body['request_scope']['source_mode'] = 'NONE'
    assert checked(e.client.post(e.base + '/author-context/preview', json=body))['creation_records'] == []


def test_mounted_approved_pin_is_removed_physically_and_current_version_revocation_invalidates_receipt(author_app):
    e = author_app
    profile = checked(e.client.post(e.base + '/style-analysis/profiles', json={
        'title': 'Synthetic pinned reference', 'instructions': 'PINNED_REFERENCE_CANARY use concise sentences.',
        'chapter_ids': [e.chapter['id']]}), 201)
    approved = checked(e.client.post(e.base + '/style-analysis/profiles/' + profile['id'] + '/approve', json={'expected_version': 1}))
    body = {**author(e, include_automatic_context=False), 'style_profile_id': profile['id']}
    preview = checked(e.client.post(e.base + '/author-context/preview', json=body))
    assert preview['creation_records'] == [{'id': profile['id'], 'version': approved['version']}]
    assert 'PINNED_REFERENCE_CANARY' in preview['request']['prompt']
    removed = {**body, 'request_scope': scope(include_automatic_context=False, include_style_reference=False)}
    omitted = checked(e.client.post(e.base + '/author-context/preview', json=removed))
    assert omitted['creation_records'] == [] and 'PINNED_REFERENCE_CANARY' not in omitted['request']['prompt']
    assert e.client.post(e.base + '/author-context/generate', json={**removed, 'preview_digest': preview['preview_digest']}).status_code == 409
    checked(e.client.put(e.base + '/style-analysis/profiles/' + profile['id'], json={
        'expected_version': approved['version'], 'title': 'Changed pin', 'instructions': 'Different instructions.',
        'chapter_ids': [e.chapter['id']]}))
    assert e.client.post(e.base + '/author-context/generate', json={**body, 'preview_digest': preview['preview_digest']}).status_code in {409, 422}
    assert not e.manager.jobs


def test_mounted_active_a06_policy_blocks_direct_variants_without_reservations(author_app, monkeypatch):
    e = author_app
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', os.environ['EXPERIMENTAL_FEATURES'] + ',model_broker_v2')
    response = e.client.post(e.base + '/author-context/preview-variants', json={
        'author': author(e), 'count': 2, 'group_id': str(uuid.uuid4())})
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'AUTHOR_VARIANTS_BROKER_POLICY_REQUIRES_RESERVATION'
    assert not e.manager.jobs


def test_mounted_persisted_a06_budget_still_blocks_after_flag_disable(author_app):
    from app.experimental.model_broker import BudgetInput
    e = author_app
    e.experimental.model_broker_service.configure_budget(e.nid, e.scope, 'local-author',
        BudgetInput(expected_version=0, limit_microusd=0, max_inflight=1, require_known_estimate=True))
    assert 'model_broker_v2' not in os.environ['EXPERIMENTAL_FEATURES'].split(',')
    response = e.client.post(e.base + '/author-context/preview-variants', json={
        'author': author(e), 'count': 2, 'group_id': str(uuid.uuid4())})
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'AUTHOR_VARIANTS_BROKER_POLICY_REQUIRES_RESERVATION'
    assert not e.manager.jobs


def test_mounted_a06_enabled_after_preview_blocks_all_variant_starts(author_app, monkeypatch):
    e = author_app
    body = {'author': author(e), 'count': 2, 'group_id': str(uuid.uuid4())}
    preview = checked(e.client.post(e.base + '/author-context/preview-variants', json=body))
    body['receipts'] = [{'variant_index': row['variant']['variant_index'], 'preview_digest': row['preview_digest']} for row in preview['variants']]
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', os.environ['EXPERIMENTAL_FEATURES'] + ',model_broker_v2')
    response = e.client.post(e.base + '/author-context/generate-variants', json=body)
    assert response.status_code == 409 and not e.manager.jobs


def test_mounted_new_budget_at_adapter_boundary_blocks_all_calls_even_with_broker_disabled(author_app, monkeypatch):
    import threading
    from app.experimental.model_broker import BudgetInput
    import app.jobs as jobs_module
    e = author_app
    body = {'author': author(e), 'count': 2, 'group_id': str(uuid.uuid4())}
    preview = checked(e.client.post(e.base + '/author-context/preview-variants', json=body))
    body['receipts'] = [{'variant_index': row['variant']['variant_index'], 'preview_digest': row['preview_digest']} for row in preview['variants']]
    prepare = jobs_module.runtime.prepare_text_route
    changed = []; lock = threading.Lock()
    class DelayedNode:
        def __init__(self, delegate): self.delegate = delegate
        def stream(self, value):
            with lock:
                if not changed:
                    e.experimental.model_broker_service.configure_budget(e.nid, e.scope, 'local-author',
                        BudgetInput(expected_version=0, limit_microusd=0, max_inflight=1, require_known_estimate=True))
                    changed.append(True)
            yield from self.delegate.stream(value)
    monkeypatch.setattr(jobs_module.runtime, 'prepare_text_route', lambda *args: DelayedNode(prepare(*args)))
    provider = jobs_module.runtime.providers['mock']
    adapter_calls = []
    def unexpected(*_args, **_kwargs):
        adapter_calls.append(True)
        raise RuntimeError('budget change must stop adapter transport')
    monkeypatch.setattr(provider, 'generate', unexpected)
    monkeypatch.setattr(provider, 'stream', unexpected)
    generated = checked(e.client.post(e.base + '/author-context/generate-variants', json=body), 202)
    jobs = wait_jobs(e, [row['job_id'] for row in generated['variants']])
    assert changed and not adapter_calls and all(job.status == 'FAILED' and not job.output for job in jobs)
    assert 'model_broker_v2' not in os.environ['EXPERIMENTAL_FEATURES'].split(',')
