"""Bounded original-domain receipt lifecycle; File/real PostgreSQL, both mounts.

No provider admission, eviction, worker, or substitute PostgreSQL fixture.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import copy

import pytest

from app.experimental.common import change_row
from app.experimental.embeddings import EmbeddingService, MockEmbeddingProvider
from app.experimental.research_library import ResearchLibraryService
from app.experimental.research_vision import SyntheticResearchVisionProvider
from app.experimental.review_adapter_jobs import (
    MAX_HISTORY, MAX_RECEIPT_BYTES, MAX_RESULT_BYTES, MAX_SNAPSHOT_BYTES,
    HEADROOM, bounded_change, preflight,
)
from app.experimental.store import ExperimentalStore, canonical
from test_r3_mounted_contracts import mounted, prefix, checked, scoped
from test_surface_search_visual_research import (
    surfaces, image_source, analysis, reference, check_request,
)
from test_r4_research_library import payload


@pytest.fixture(params=['research', 'visual'])
def receipt(surfaces, monkeypatch, request):
    e = surfaces
    if request.param == 'research':
        e.source = image_source(e)
        row = analysis(e, e.source)
        e.owner, e.collection = e.research, 'research_analysis_jobs'
        e.path = e.lib + '/analysis/jobs/' + row['id']
        e.provider_attr, e.provider_type = 'vision_provider', SyntheticResearchVisionProvider
    else:
        asset, profile = reference(e)
        e.asset, e.profile = asset, profile
        row = checked(e.client.post(e.emb + '/visual-identity/checks', json=check_request(asset, profile)), 201)
        e.owner, e.collection = e.embedding, 'visual_identity_checks'
        e.path = e.emb + '/visual-identity/checks/' + row['id']
        e.provider_attr, e.provider_type = 'provider', MockEmbeddingProvider
    e.rid = row['id']
    monkeypatch.setattr(e.owner, e.provider_attr, e.provider_type())
    return e


def stored(e):
    return e.store.read(e.nid, e.scope)['collections'][e.collection][e.rid]


def at_history(e, count):
    with e.store.transaction(e.nid, e.scope) as state:
        row = state['collections'][e.collection][e.rid]
        for _ in range(count):
            change_row(row, 'local-author', row['version'], lambda target: target.update(status='DRAFT'))
    return stored(e)


def action(e, operation, version, status=200):
    return checked(e.client.post(e.path + '/' + operation, json={'expected_version': version}), status)


def reopened(e):
    store = ExperimentalStore(e.root, e.backend, e.url)
    if e.collection == 'research_analysis_jobs':
        owner = ResearchLibraryService(store, e.novels, e.chapters)
        return owner.analysis_job(e.nid, e.scope, 'local-author', e.rid)
    owner = EmbeddingService(store, e.novels, e.chapters, provider=e.embedding.provider, assets=e.assets)
    owner.visual_memory = e.capabilities
    return owner.visual_check(e.nid, e.scope, 'local-author', e.rid)


@pytest.mark.parametrize('count', [95, 99, 100])
def test_run_reserves_complete_control_tail_before_dispatch(receipt, monkeypatch, count):
    e = receipt; original = at_history(e, count); called = []
    provider = getattr(e.owner, e.provider_attr)
    name = 'analyze' if e.collection == 'research_analysis_jobs' else 'embed'
    monkeypatch.setattr(provider, name, lambda *args: called.append(True))
    response = e.client.post(e.path + '/run', json={'expected_version': original['version']})
    assert response.status_code == 422 and 'ADAPTER_REVISION_LIMIT' in response.text
    assert not called and stored(e) == original
    assert e.client.post(e.path + '/run', json={'expected_version': 1}).status_code == 409


def test_last_admitted_run_keeps_review_cancel_recovery_and_invalidation(receipt):
    e = receipt; before = at_history(e, MAX_HISTORY - 1 - HEADROOM['RUNNING'])
    ready = action(e, 'run', before['version'])
    assert ready['status'] == 'REVIEW_REQUIRED' and ready['capacity']['history_used'] == 96
    assert ready['capacity']['cancel_available'] is True
    assert reopened(e) == ready
    reviewed = action(e, 'review', ready['version'])
    cancelled = action(e, 'cancel', reviewed['version'])
    assert cancelled['status'] == 'CANCELLED' and not {'request', 'source_snapshot', 'model', 'result_digest'} & cancelled.keys()
    assert action(e, 'cancel', cancelled['version']) == cancelled
    recovered = action(e, 'recover', cancelled['version'])
    assert recovered['status'] == 'DRAFT' and recovered['capacity']['history_used'] == 99
    assert recovered['capacity']['cancel_available'] is False
    original = stored(e)
    assert e.client.post(e.path + '/run', json={'expected_version': recovered['version']}).status_code == 422
    assert stored(e) == original
    invalidated = action(e, 'invalidate', recovered['version'])
    assert invalidated['status'] == 'INVALIDATED' and invalidated['capacity']['history_used'] == MAX_HISTORY
    assert action(e, 'invalidate', invalidated['version']) == invalidated
    final = stored(e)
    assert len(final['history']) == MAX_HISTORY and final['history'][:94] == before['history']
    assert len(canonical(final).encode()) <= MAX_RECEIPT_BYTES


@pytest.mark.parametrize('failure', ['provider', 'oversized', 'non_json'])
def test_last_admitted_run_failure_preserves_sanitized_recovery(receipt, monkeypatch, failure):
    e = receipt; original = at_history(e, 94)
    from app.experimental import review_adapter_jobs
    original_execute = review_adapter_jobs.ReviewAdapterJobs.__init__
    def altered(self, service, name, source_reader, provider_reader, execute):
        def failed(*args):
            if failure == 'provider': raise RuntimeError('synthetic private provider detail')
            if failure == 'oversized': return {'text': 'x' * (MAX_RESULT_BYTES + 1)}
            return {'non_json': object()}
        original_execute(self, service, name, source_reader, provider_reader, failed)
    monkeypatch.setattr(review_adapter_jobs.ReviewAdapterJobs, '__init__', altered)
    # Execute via the owner to observe non-HTTP provider failures without weakening
    # the mounted TestClient's raise_server_exceptions setting.
    call = e.owner.analysis_action if e.collection == 'research_analysis_jobs' else e.owner.visual_action
    with pytest.raises((ValueError, TypeError, RuntimeError)):
        call(e.nid, e.scope, 'local-author', e.rid, 'run', original['version'],
             **{'guard' if e.collection == 'research_analysis_jobs' else 'check_authority': lambda: None})
    row = stored(e)
    assert row['status'] == 'FAILED' and row['result'] is None and row['execution_token'] is None
    assert row['error_code'] == 'ADAPTER_EXECUTION_FAILED' and len(row['history']) == 96
    assert 'synthetic private provider detail' not in canonical(row)
    assert reopened(e)['status'] == 'FAILED'
    cancelled = action(e, 'cancel', row['version'])
    recovered = action(e, 'recover', cancelled['version'])
    assert recovered['status'] == 'DRAFT'
    assert action(e, 'invalidate', recovered['version'])['status'] == 'INVALIDATED'
    assert len(stored(e)['history']) <= MAX_HISTORY


def test_byte_preflight_blocks_dispatch_without_eviction(receipt, monkeypatch):
    e = receipt; original = at_history(e, 8)
    # Fill real persisted historical revisions with bounded snapshots. The total
    # is legal on disk, but cannot admit worst-case terminal/recovery snapshots.
    with e.store.transaction(e.nid, e.scope) as state:
        row = state['collections'][e.collection][e.rid]
        for item in row['history']:
            item['synthetic_capacity_fixture'] = 'x' * (MAX_SNAPSHOT_BYTES - 4096)
    original = stored(e); assert len(canonical(original).encode()) < MAX_RECEIPT_BYTES
    called = []; provider = getattr(e.owner, e.provider_attr)
    monkeypatch.setattr(provider, 'analyze' if e.collection == 'research_analysis_jobs' else 'embed', lambda *args: called.append(True))
    response = e.client.post(e.path + '/run', json={'expected_version': original['version']})
    assert response.status_code == 422 and 'ADAPTER_RECEIPT_BYTE_LIMIT' in response.text
    assert not called and stored(e) == original


def test_capacity_cancel_race_and_restart_never_publish_late_results(receipt, monkeypatch):
    e = receipt; original = at_history(e, 94); entered, release = Event(), Event()
    provider = getattr(e.owner, e.provider_attr)
    name = 'analyze' if e.collection == 'research_analysis_jobs' else 'embed'
    execute = getattr(provider, name)
    def slow(*args):
        result = execute(*args); entered.set(); assert release.wait(20); return result
    monkeypatch.setattr(provider, name, slow)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(e.client.post, e.path + '/run', json={'expected_version': original['version']})
        try:
            assert entered.wait(20)
            orphan = reopened(e)
            assert orphan['status'] == 'RUNNING' and orphan['recovery_required'] and not orphan['automatic_resume']
            cancelled = action(e, 'cancel', orphan['version'])
            recovered = action(e, 'recover', cancelled['version'])
            assert recovered['status'] == 'DRAFT'
        finally: release.set()
        response = pending.result(timeout=20)
        assert response.status_code in {200, 409}
    final = stored(e)
    assert final['status'] == 'DRAFT' and final['result'] is None and final['execution_token'] is None
    assert final['version'] == recovered['version'] and len(final['history']) == 97


def test_research_repeated_invalidation_at_hard_limit_is_noop_and_cancel_is_private(surfaces, monkeypatch):
    e = surfaces; e.source = image_source(e); row = analysis(e, e.source)
    e.collection, e.rid = 'research_analysis_jobs', row['id']
    e.path = e.lib + '/analysis/jobs/' + e.rid
    at_history(e, 99)
    replacement = checked(e.client.put(e.lib + f"/sources/{e.source['id']}/file", json=payload('First replacement', expected_version=e.source['version'])))
    before = stored(e); assert before['status'] == 'INVALIDATED' and len(before['history']) == MAX_HISTORY
    checked(e.client.put(e.lib + f"/sources/{e.source['id']}/file", json=payload('Second replacement', expected_version=replacement['version'])))
    assert stored(e) == before


def test_cancel_after_source_revocation_returns_no_captured_lineage(surfaces, monkeypatch):
    e = scoped(surfaces, monkeypatch)
    source = image_source(e, e.headers); row = analysis(e, source, headers=e.headers)
    path = e.lib + '/analysis/jobs/' + row['id']
    checked(e.client.post(e.lib + f"/sources/{source['id']}/revoke", headers=e.headers, json={'expected_version': source['version']}))
    assert e.client.get(path, headers=e.headers).status_code == 404
    conflict = e.client.post(path + '/cancel', headers=e.headers, json={'expected_version': row['version']})
    assert conflict.status_code == 409 and set(conflict.json()['detail']['current']) == {'id', 'version', 'status'}
    assert source['id'] not in conflict.text and source['content_sha256'] not in conflict.text
    cancelled = checked(e.client.post(path + '/cancel', headers=e.headers, json={'expected_version': row['version'] + 1}))
    assert cancelled['status'] == 'CANCELLED' and cancelled['result'] is None
    assert not {'request', 'source_snapshot', 'result_digest', 'model', 'history', 'execution_token'} & cancelled.keys()
    assert source['id'] not in canonical(cancelled) and source['content_sha256'] not in canonical(cancelled)
    assert e.client.post(path + '/recover', headers=e.headers, json={'expected_version': cancelled['version']}).status_code == 404
    assert e.client.get(e.lib + '/analysis/jobs', headers=e.headers).json()['items'] == []


def test_bounded_change_preflight_never_mutates_argument_on_failure():
    from app.experimental.common import new_row
    row = new_row('fixture', {'mode': 'local', 'novel_id': 'fixture'}, 'actor', {'status': 'DRAFT'})
    original = copy.deepcopy(row)
    with pytest.raises(ValueError, match='ADAPTER_SNAPSHOT_LIMIT'):
        bounded_change(row, 'actor', 1, {'status': 'DRAFT', 'result': 'x' * MAX_SNAPSHOT_BYTES})
    assert row == original
    row['history'] = [{'version': index} for index in range(MAX_HISTORY)]
    with pytest.raises(ValueError, match='ADAPTER_REVISION_LIMIT'): preflight(row, 1)


def test_byte_headroom_admits_maximum_result_and_full_control_tail(receipt, monkeypatch):
    e = receipt; at_history(e, 4)
    with e.store.transaction(e.nid, e.scope) as state:
        row = state['collections'][e.collection][e.rid]
        for item in row['history']:
            item['synthetic_capacity_fixture'] = 'x' * (MAX_SNAPSHOT_BYTES - 4096)
    before = stored(e)
    from app.experimental import review_adapter_jobs
    original_init = review_adapter_jobs.ReviewAdapterJobs.__init__
    result = {'text': 'x' * (MAX_RESULT_BYTES - len(canonical({'text': ''}).encode()))}
    assert len(canonical(result).encode()) == MAX_RESULT_BYTES
    def altered(self, service, name, source_reader, provider_reader, execute):
        original_init(self, service, name, source_reader, provider_reader, lambda *args: result)
    monkeypatch.setattr(review_adapter_jobs.ReviewAdapterJobs, '__init__', altered)
    ready = action(e, 'run', before['version'])
    assert ready['status'] == 'REVIEW_REQUIRED'
    reviewed = action(e, 'review', ready['version'])
    cancelled = action(e, 'cancel', reviewed['version'])
    recovered = action(e, 'recover', cancelled['version'])
    invalidated = action(e, 'invalidate', recovered['version'])
    assert invalidated['status'] == 'INVALIDATED'
    final = stored(e)
    assert final['history'][:4] == before['history'] and len(canonical(final).encode()) <= MAX_RECEIPT_BYTES


def test_capacity_preclaim_authority_loss_rolls_back_without_dispatch(receipt, monkeypatch):
    e = receipt; before = at_history(e, 94); calls, dispatched = [], []
    provider = getattr(e.owner, e.provider_attr)
    monkeypatch.setattr(provider, 'analyze' if e.collection == 'research_analysis_jobs' else 'embed', lambda *args: dispatched.append(True))
    def guard():
        calls.append(True)
        if len(calls) == 3: raise PermissionError('synthetic authority revoked before claim commit')
    from app.experimental.research_vision import research_analysis_jobs
    from app.experimental.visual_identity import visual_identity_jobs
    jobs = research_analysis_jobs(e.owner) if e.collection == 'research_analysis_jobs' else visual_identity_jobs(e.owner)
    with pytest.raises(PermissionError): jobs.run(e.nid, e.scope, 'local-author', e.rid, before['version'], guard)
    assert not dispatched and stored(e) == before


def test_visual_cancel_and_conflict_after_approved_reference_revoke_are_minimal(surfaces):
    from app.services.v1_capability_service import VisualMemoryIn
    e = surfaces; asset, profile = reference(e)
    row = checked(e.client.post(e.emb + '/visual-identity/checks', json=check_request(asset, profile)), 201)
    e.capabilities.update_visual_memory(e.nid, profile['id'], VisualMemoryIn(entity_type='CHARACTER',
        entity_id='alice', asset_id=asset['id'], appearance={'hair': 'changed'}), profile['version'])
    path = e.emb + '/visual-identity/checks/' + row['id']
    assert e.client.get(path).status_code == 404
    conflict = e.client.post(path + '/cancel', json={'expected_version': row['version'] + 1})
    assert conflict.status_code == 409 and set(conflict.json()['detail']['current']) == {'id', 'version', 'status'}
    assert profile['id'] not in conflict.text and asset['id'] not in conflict.text
    cancelled = checked(e.client.post(path + '/cancel', json={'expected_version': row['version']}))
    assert cancelled['status'] == 'CANCELLED' and cancelled['result'] is None
    assert not {'request', 'source_snapshot', 'model', 'result_digest'} & cancelled.keys()
    assert profile['id'] not in canonical(cancelled) and asset['id'] not in canonical(cancelled)
    assert checked(e.client.get(e.emb + '/visual-identity/checks'))['items'] == []


def test_source_revoke_wins_late_result_at_admission_boundary(receipt, monkeypatch):
    e = receipt; original = at_history(e, 94); entered, release = Event(), Event()
    provider = getattr(e.owner, e.provider_attr)
    name = 'analyze' if e.collection == 'research_analysis_jobs' else 'embed'
    execute = getattr(provider, name)
    def slow(*args):
        result = execute(*args); entered.set(); assert release.wait(20); return result
    monkeypatch.setattr(provider, name, slow)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(e.client.post, e.path + '/run', json={'expected_version': original['version']})
        try:
            assert entered.wait(20)
            if e.collection == 'research_analysis_jobs':
                checked(e.client.post(e.lib + f"/sources/{e.source['id']}/revoke", json={'expected_version': e.source['version']}))
            else:
                from app.services.v1_capability_service import VisualMemoryIn
                e.capabilities.update_visual_memory(e.nid, e.profile['id'], VisualMemoryIn(entity_type='CHARACTER',
                    entity_id='alice', asset_id=e.asset['id'], appearance={'hair': 'changed'}), e.profile['version'])
        finally: release.set()
        response = pending.result(timeout=20)
        assert response.status_code in {404, 409} and 'similarities' not in response.text and 'Synthetic contract result' not in response.text
    row = stored(e)
    assert row['status'] == ('INVALIDATED' if e.collection == 'research_analysis_jobs' else 'FAILED')
    assert row['result'] is None and row['execution_token'] is None and len(row['history']) == 96
    assert e.client.get(e.path).status_code == 404
    if e.collection == 'visual_identity_checks':
        cancelled = action(e, 'cancel', row['version'])
        assert cancelled['status'] == 'CANCELLED' and 'source_snapshot' not in cancelled


def test_late_provider_result_after_recovery_returns_only_minimal_receipt(surfaces, monkeypatch):
    e = surfaces; asset, profile = reference(e)
    row = checked(e.client.post(e.emb + '/visual-identity/checks', json=check_request(asset, profile)), 201)
    monkeypatch.setattr(e.embedding, 'provider', MockEmbeddingProvider())
    from app.experimental import review_adapter_jobs
    from app.services.v1_capability_service import VisualMemoryIn
    original_init = review_adapter_jobs.ReviewAdapterJobs.__init__
    def altered(self, service, name, source_reader, provider_reader, execute):
        def late(*args):
            current = service.get(e.nid, e.scope, name, row['id'])
            cancelled = self.action(e.nid, e.scope, 'local-author', row['id'], 'cancel', current['version'], lambda: None)
            self.action(e.nid, e.scope, 'local-author', row['id'], 'recover', cancelled['version'], lambda: None)
            e.capabilities.update_visual_memory(e.nid, profile['id'], VisualMemoryIn(entity_type='CHARACTER',
                entity_id='alice', asset_id=asset['id'], appearance={'hair': 'changed'}), profile['version'])
            # Even an adapter that forgets its final dispatch_guard cannot publish
            # after the original receipt's token was cancelled and recovered.
            return {'private_late_result': 'must never be returned'}
        original_init(self, service, name, source_reader, provider_reader, late)
    monkeypatch.setattr(review_adapter_jobs.ReviewAdapterJobs, '__init__', altered)
    path = e.emb + '/visual-identity/checks/' + row['id']
    response = checked(e.client.post(path + '/run', json={'expected_version': row['version']}))
    assert response['status'] == 'DRAFT' and response['result'] is None
    assert not {'request', 'source_snapshot', 'model', 'result_digest'} & response.keys()
    assert profile['id'] not in canonical(response) and asset['id'] not in canonical(response)
    assert 'private_late_result' not in canonical(response)
    assert e.client.get(path).status_code == 404
