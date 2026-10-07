"""Real File + PostgreSQL owner contracts, including mounted trusted authority."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.experimental.flags import RUNTIME_FLAGS
from app.finding_review_api import create_finding_review_router
from app.services.continuity_finding_service import ContinuityFindingService
from app.services.narrative_finding_service import NarrativeFindingService
from app.services.finding_review_service import FindingReviewService, FindingCheckIn, FindingDecisionIn, FindingReviewConflict
from app.services.branch_manuscript_service import BranchManuscriptService
from test_r3_mounted_contracts import mounted, prefix, scoped, checked


@pytest.fixture
def review_env(mounted, monkeypatch):
    e = mounted
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(RUNTIME_FLAGS))
    e.continuity = ContinuityFindingService(e.bundle.continuity, enabled=True)
    e.narrative = NarrativeFindingService(e.bundle.narrative)
    e.review = FindingReviewService(e.continuity, e.narrative, e.chapters, e.novels)
    app = FastAPI()
    app.include_router(create_finding_review_router(e.review, e.api._workbench_authorize), prefix=e.prefix)
    e.review_client = TestClient(app)
    e.review_base = e.prefix + f'/projects/{e.nid}'
    yield e
    e.review_client.close()


def facts(nid, kind='continuity'):
    if kind == 'continuity':
        return {'events': [{'id': 'time', 'project_id': nid, 'event_type': 'SCENE', 'title': 'Clock',
                           'start_time': 'day-3', 'end_time': 'day-1', 'evidence_ids': ['clock-evidence']}]}
    return {'current_chapter': 3, 'expectations': [{'id': 'expect', 'project_id': nid,
            'subject_type': 'FORESHADOWING', 'subject_id': 'seed', 'expectation_type': 'FORESHADOWING_PAYOFF_BY',
            'deadline_chapter': 2, 'evidence_ids': ['seed-evidence']}]}


def run(e, kind='continuity', chapter=None, scope=None, data=None):
    chapter = chapter or e.chapters.get(e.chapter['id'])
    return e.review.check(e.nid, scope or e.scope, 'author', kind,
        FindingCheckIn(chapter_id=chapter['id'], expected_source_version=chapter['version'], facts=data or facts(e.nid, kind)))['items'][0]


def decision(row, action='intentional', **extra):
    return FindingDecisionIn(expected_version=row['review_version'], source_digest=row['source_digest'],
        finding_fingerprint=row['finding_fingerprint'], action=action, reason='Intentional nonlinear chronology',
        operation_id=uuid4().hex, confirmed=True, **extra)


@pytest.mark.parametrize('kind', ['continuity', 'narrative'])
def test_source_bound_intentional_cas_history_recovery_and_restart(review_env, kind):
    e = review_env
    row = run(e, kind)
    request = decision(row)
    accepted = e.review.review(e.nid, e.scope, 'author', kind, row['id'], request)
    assert accepted['suppression_active'] and accepted['review_version'] == 2
    assert accepted['review_history'][0]['action'] == 'INTENTIONAL'
    assert run(e, kind)['status'] == 'INTENTIONAL'
    assert e.review.review(e.nid, e.scope, 'author', kind, row['id'], request)['review_version'] == 2
    with pytest.raises(FindingReviewConflict, match='FINDING_VERSION_CONFLICT'):
        e.review.review(e.nid, e.scope, 'author', kind, row['id'], decision(row))
    restarted = FindingReviewService(e.continuity, e.narrative, e.chapters, e.novels)
    assert restarted.get(e.nid, e.scope, kind, row['id'])['suppression_active']
    original = e.chapters.get(e.chapter['id'])
    e.chapters.save(original['id'], {'content': 'Changed source after review.', 'version': original['version']})
    stale = restarted.get(e.nid, e.scope, kind, row['id'])
    assert stale['effective_status'] == 'REVIEW_REQUIRED' and not stale['suppression_active']
    with pytest.raises(FindingReviewConflict, match='FINDING_SOURCE_STALE'):
        restarted.review(e.nid, e.scope, 'author', kind, row['id'], decision(accepted))
    changed = run(e, kind)
    assert changed['id'] == row['id'] and changed['status'] == 'OPEN' and changed['review_version'] == 3
    assert changed['source_digest'] != row['source_digest']
    assert changed['review_history'][-1]['action'] == 'SOURCE_RECHECKED'
    feedback = e.review.review(e.nid, e.scope, 'author', kind, row['id'], decision(changed, 'feedback'))
    assert feedback['status'] == 'OPEN' and feedback['feedback_reason']
    assert e.novels.data_set(e.nid, 'canon') == [] if hasattr(e.novels, 'data_set') else True


def test_exact_evidence_snapshot_and_changed_fact_invalidation(review_env):
    e = review_env; original = e.chapters.get(e.chapter['id']); row = run(e)
    current = e.review.evidence(e.nid, e.scope, 'continuity', row['id'])
    assert current['chapter']['version'] == original['version']
    assert current['chapter']['content'] == original['content']
    e.chapters.save(original['id'], {'content': 'A newer chapter.', 'version': original['version']})
    historical = e.review.evidence(e.nid, e.scope, 'continuity', row['id'])
    assert historical['stale_source'] and historical['chapter']['content'] == original['content']
    assert historical['navigation']['chapter_version'] == original['version']
    revised = facts(e.nid); revised['events'][0]['end_time'] = 'day-2'
    updated = run(e, data=revised)
    assert updated['id'] == row['id'] and updated['source_digest'] != row['source_digest']


def test_stored_facts_stale_without_chapter_change_and_cancel_does_not_write(review_env):
    e = review_env
    from app.lore.continuity import TimelineEvent
    event = TimelineEvent.model_validate(facts(e.nid)['events'][0])
    e.bundle.continuity.create('timeline', event.model_dump(mode='json'))
    body = FindingCheckIn(chapter_id=e.chapter['id'], expected_source_version=e.chapter['version'])
    row = e.review.check(e.nid, e.scope, 'author', 'continuity', body)['items'][0]
    assert row['provenance'] == 'STORED_CONTINUITY_FACTS'
    e.review.review(e.nid, e.scope, 'author', 'continuity', row['id'], decision(row))
    event2 = event.model_copy(update={'id': 'second-clock', 'title': 'A changed timeline'})
    e.bundle.continuity.create('timeline', event2.model_dump(mode='json'))
    assert e.review.get(e.nid, e.scope, 'continuity', row['id'])['stale_source']
    before = deepcopy(e.bundle.continuity.list_by_project('findings', e.nid))
    def cancelled(): raise RuntimeError('CANCELLED_BEFORE_COMMIT')
    with pytest.raises(RuntimeError, match='CANCELLED'):
        e.review.review(e.nid, e.scope, 'author', 'continuity', row['id'], decision(e.review.get(e.nid, e.scope, 'continuity', row['id']), 'reopen'), cancelled)
    assert before == e.bundle.continuity.list_by_project('findings', e.nid)


@pytest.mark.parametrize('kind', ['continuity', 'narrative'])
def test_competing_review_has_one_cas_winner_and_original_resolve_cannot_bypass(review_env, kind):
    e = review_env; row = run(e, kind)
    def worker(i):
        try: return e.review.review(e.nid, e.scope, f'actor-{i}', kind, row['id'], decision(row))
        except FindingReviewConflict as exc: return exc.code
    with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(worker, [1, 2]))
    assert sum(isinstance(result, dict) for result in results) == 1
    assert results.count('FINDING_VERSION_CONFLICT') == 1
    service = e.continuity if kind == 'continuity' else e.narrative
    with pytest.raises(KeyError): service.resolve(e.nid, row['id'])
    assert service.list_findings(e.nid) == []


def test_mounted_validation_flag_off_and_scope_mismatch(review_env, monkeypatch):
    e = review_env; client = e.review_client; base = e.review_base + '/continuity'
    body = {'chapter_id': e.chapter['id'], 'expected_source_version': e.chapter['version'], 'facts': facts(e.nid)}
    row = checked(client.post(base + '/review-checks', json=body))['items'][0]
    assert client.post(base + f"/review-findings/{row['id']}/review", json={'action': 'intentional'}).status_code == 422
    accepted = checked(client.post(base + f"/review-findings/{row['id']}/review", json=decision(row).model_dump()))
    assert accepted['review_version'] == 2
    assert client.post(base + f"/review-findings/{row['id']}/review", json=decision(row).model_dump()).status_code == 409
    assert len(checked(client.get(base + f"/review-findings/{row['id']}/history"))['items']) == 1
    assert checked(client.get(base + f"/review-findings/{row['id']}/evidence"))['navigation']['exact']
    wrong = deepcopy(body); wrong['facts'] = facts('wrong-project')
    assert client.post(base + '/review-checks', json=wrong).status_code == 422
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    assert client.get(base + '/review-findings').status_code == 404
    assert client.post(base + f"/review-findings/{row['id']}/review", json=decision(accepted).model_dump()).status_code == 404


def test_mounted_branch_authority_cross_scope_revoke_and_late_revoke(review_env, monkeypatch):
    e = review_env
    local = run(e)
    scoped(e, monkeypatch)
    owner = BranchManuscriptService(e.store, e.novels, e.chapters, e.scopes)
    monkeypatch.setattr(e.chapters, 'branch_authority', owner.for_scope, raising=False)
    branch_chapter = owner.for_scope(e.scope).create(e.nid, {'title': 'Branch', 'content': 'Branch words'})
    client = e.review_client; base = e.review_base + '/continuity'
    assert client.get(base + '/review-findings').status_code == 400
    assert client.get(base + '/review-findings', headers={'X-Branch-ID': e.branch}).status_code == 401
    assert client.get(base + f"/review-findings/{local['id']}", headers=e.headers).status_code == 404
    assert checked(client.get(base + '/review-findings', headers=e.headers))['items'] == []
    body = {'chapter_id': branch_chapter['id'], 'expected_source_version': 1, 'facts': facts(e.nid)}
    assert client.post(base + '/review-checks', headers=e.viewer_headers, json=body).status_code == 403
    mainline_body = {**body, 'chapter_id': e.chapter['id']}
    assert client.post(base + '/review-checks', headers=e.headers, json=mainline_body).status_code == 404
    row = checked(client.post(base + '/review-checks', headers=e.headers, json=body))['items'][0]
    assert row['scope'] == e.scope and row['source']['scope'] == e.scope
    assert client.post(base + f"/review-findings/{row['id']}/review", headers=e.viewer_headers, json=decision(row).model_dump()).status_code == 403
    assert client.get(base + f"/review-findings/{row['id']}", headers={**e.headers, 'X-Branch-ID': e.other_branch}).status_code in {403, 404}
    # The source and authorization are checked again inside the owner mutation.
    original = e.review._public; calls = []
    def revoke_after_source(*args):
        result = original(*args)
        if not calls:
            calls.append(True); e.authorization.revoke_role(e.role, e.lead)
        return result
    monkeypatch.setattr(e.review, '_public', revoke_after_source)
    assert client.post(base + f"/review-findings/{row['id']}/review", headers=e.headers, json=decision(row).model_dump()).status_code == 403
    saved = e.bundle.continuity.get_by_id('findings', row['id'])
    assert saved['review_version'] == 1 and saved['status'] == 'OPEN'
    assert client.get(base + '/review-findings', headers=e.headers).status_code == 403


def test_actual_main_findings_composition_middleware_alias_and_v1(review_env, monkeypatch):
    e = review_env
    captured = e.api.finding_review_service
    for name, value in [('continuity', e.continuity), ('narrative', e.narrative), ('chapters', e.chapters), ('novels', e.novels)]:
        monkeypatch.setattr(captured, name, value)
    base = e.review_base + '/continuity'
    row = checked(e.client.post(base + '/review-checks', json={'chapter_id': e.chapter['id'], 'expected_source_version': e.chapter['version'], 'facts': facts(e.nid)}))['items'][0]
    assert checked(e.client.get(base + '/review-findings'))['items'][0]['id'] == row['id']
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    assert e.client.get(base + '/review-findings').status_code == 404
    monkeypatch.delenv('V1_ACCEPTANCE_MODE')
    scoped(e, monkeypatch)
    assert e.client.get(base + '/review-findings', headers={'X-Branch-ID': e.branch}).status_code == 401
    assert checked(e.client.get(base + '/review-findings', headers=e.headers))['items'] == []
    assert e.client.get(base + f"/review-findings/{row['id']}", headers=e.headers).status_code == 404
    e.authorization.revoke_role(e.role, e.lead)
    assert e.client.get(base + '/review-findings', headers=e.headers).status_code == 403


def test_actual_main_findings_withhold_read_after_feature_off(review_env, monkeypatch):
    e = review_env; row = run(e)
    captured = e.api.finding_review_service
    for name, value in [('continuity', e.continuity), ('narrative', e.narrative), ('chapters', e.chapters), ('novels', e.novels)]: monkeypatch.setattr(captured, name, value)
    original = captured.evidence
    def turn_off(*args):
        result = original(*args); monkeypatch.setenv('EXPERIMENTAL_FEATURES', ''); return result
    monkeypatch.setattr(captured, 'evidence', turn_off)
    response = e.client.get(e.review_base + f"/continuity/review-findings/{row['id']}/evidence")
    assert response.status_code == 404
    assert e.chapter['content'] not in response.text


def test_stored_narrative_foreshadowing_expectation_is_reviewable_and_facts_invalidate(review_env):
    from app.narrative_detection import NarrativeExpectation
    e = review_env
    chapter = e.chapters.create(e.nid, {'title': 'Second chapter', 'content': 'Earlier seed returns.'})
    chapter = e.chapters.get(chapter['id'])
    expectation = NarrativeExpectation('seed-expectation', e.nid, 'FORESHADOWING', 'seed', 'FORESHADOWING_PAYOFF_BY', 1)
    e.narrative.create_expectation(expectation)
    body = FindingCheckIn(chapter_id=chapter['id'], expected_source_version=chapter['version'])
    row = e.review.check(e.nid, e.scope, 'author', 'narrative', body)['items'][0]
    assert row['finding_type'] == 'FORESHADOWING_OVERDUE' and row['provenance'] == 'STORED_NARRATIVE_FACTS'
    e.review.review(e.nid, e.scope, 'author', 'narrative', row['id'], decision(row))
    e.narrative.create_expectation(NarrativeExpectation('second-expectation', e.nid, 'THREAD', 'thread', 'THREAD_PROGRESS_BY', 1))
    assert e.review.get(e.nid, e.scope, 'narrative', row['id'])['stale_source']


@pytest.mark.parametrize('kind', ['continuity', 'narrative'])
def test_archived_finding_source_is_stale_and_exact_evidence_is_withheld(review_env, kind):
    e = review_env; row = run(e, kind)
    e.review.review(e.nid, e.scope, 'author', kind, row['id'], decision(row))
    e.chapters.archive(e.chapter['id'], e.chapter['version'])
    stale = e.review.get(e.nid, e.scope, kind, row['id'])
    assert stale['stale_source'] and not stale['suppression_active']
    with pytest.raises(FileNotFoundError): e.review.evidence(e.nid, e.scope, kind, row['id'])
    with pytest.raises(FindingReviewConflict, match='FINDING_SOURCE_STALE'):
        e.review.review(e.nid, e.scope, 'author', kind, row['id'], decision(stale))


@pytest.mark.parametrize('path,method', [('', 'list'), ('/finding', 'get'), ('/finding/history', 'get')])
def test_actual_main_findings_withhold_all_reads_after_late_revoke(review_env, monkeypatch, path, method):
    e = review_env; scoped(e, monkeypatch)
    owner = BranchManuscriptService(e.store, e.novels, e.chapters, e.scopes)
    monkeypatch.setattr(e.chapters, 'branch_authority', owner.for_scope, raising=False)
    chapter = owner.for_scope(e.scope).create(e.nid, {'title': 'Scoped source', 'content': 'Private scoped source'})
    row = run(e, chapter=chapter)
    service = e.api.finding_review_service
    for name, value in [('continuity', e.continuity), ('narrative', e.narrative), ('chapters', e.chapters), ('novels', e.novels)]: monkeypatch.setattr(service, name, value)
    original = getattr(service, method)
    def revoke(*args):
        value = original(*args); e.authorization.revoke_role(e.role, e.lead); return value
    monkeypatch.setattr(service, method, revoke)
    response = e.client.get(e.review_base + '/continuity/review-findings' + path.replace('finding', row['id']), headers=e.headers)
    assert response.status_code == 403 and row['description'] not in response.text


def test_actual_main_branch_check_review_evidence_and_no_mainline_fallback(review_env, monkeypatch):
    e = review_env; scoped(e, monkeypatch)
    owner = BranchManuscriptService(e.store, e.novels, e.chapters, e.scopes)
    monkeypatch.setattr(e.chapters, 'branch_authority', owner.for_scope, raising=False)
    chapter = owner.for_scope(e.scope).create(e.nid, {'title': 'Actual main branch', 'content': 'ACTUAL_BRANCH_EVIDENCE'})
    service = e.api.finding_review_service
    for name, value in [('continuity', e.continuity), ('narrative', e.narrative), ('chapters', e.chapters), ('novels', e.novels)]: monkeypatch.setattr(service, name, value)
    base = e.review_base + '/continuity'
    body = {'chapter_id': chapter['id'], 'expected_source_version': chapter['version'], 'facts': facts(e.nid)}
    assert e.client.post(base + '/review-checks', json=body, headers=e.viewer_headers).status_code == 403
    assert e.client.post(base + '/review-checks', json={**body, 'chapter_id': e.chapter['id']}, headers=e.headers).status_code == 404
    row = checked(e.client.post(base + '/review-checks', json=body, headers=e.headers))['items'][0]
    accepted = checked(e.client.post(base + f"/review-findings/{row['id']}/review", json=decision(row).model_dump(), headers=e.headers))
    assert accepted['suppression_active'] and accepted['scope'] == e.scope
    evidence = checked(e.client.get(base + f"/review-findings/{row['id']}/evidence", headers=e.headers))
    assert evidence['chapter']['content'] == chapter['content'] and evidence['navigation']['scope'] == e.scope
    assert e.client.get(base + f"/review-findings/{row['id']}/evidence", headers={**e.headers, 'X-Branch-ID': e.other_branch}).status_code in {403, 404}
