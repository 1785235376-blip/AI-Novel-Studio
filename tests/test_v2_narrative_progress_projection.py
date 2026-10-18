"""Blank-facts review checks must project only original, source-bound progress."""
from copy import deepcopy

import pytest

from app.narrative import (ChapterNarrativeLink, Foreshadowing, NarrativeEntityType,
                           NarrativeProgressType, PlotThread)
from app.narrative_detection import NarrativeExpectation
from app.services.narrative_state_service import NarrativeStateService
from app.services.finding_review_service import FindingCheckIn, FindingReviewConflict
from test_r3_mounted_contracts import mounted, prefix, checked, scoped
from test_surface_finding_review import review_env, decision


def owner_fixture(e, thread_number=5, payoff_number=4, last_number=6, unpaid=True, default_scope=True):
    """Use the real atomic owner, including the legacy default-scope adapter."""
    chapters = [e.chapter]
    for number in range(2, last_number + 1):
        row = e.chapters.create(e.nid, {'title': f'Chapter {number}', 'content': f'Chapter {number} words'})
        chapters.append(e.chapters.get(row['id']))
    repository = e.bundle.narrative
    if default_scope:
        scope = e.scopes.ensure_default_scope(e.nid)
        repository = e.scopes.scoped_narrative(scope, repository)
    state = NarrativeStateService(repository, e.chapters, e.novels)
    ids = {name: e.nid + '-' + name for name in ('thread', 'seed', 'unpaid')}
    state.create_thread(PlotThread(ids['thread'], e.nid, 'Reviewed thread'))
    state.create_foreshadowing(Foreshadowing(ids['seed'], e.nid, 'Reviewed seed'))
    state.create_foreshadowing(Foreshadowing(ids['unpaid'], e.nid, 'Still unpaid'))
    links = []
    for name, kind, progress, number in (
        ('thread', NarrativeEntityType.PLOT_THREAD, NarrativeProgressType.ADVANCED, thread_number),
        ('seed', NarrativeEntityType.FORESHADOWING, NarrativeProgressType.DEVELOPED, 2),
        ('seed', NarrativeEntityType.FORESHADOWING, NarrativeProgressType.PAYOFF, payoff_number),
    ):
        chapter = chapters[number - 1]
        lid = e.nid + f'-{name}-{progress}'
        link = ChapterNarrativeLink(lid, e.nid, chapter['id'], chapter['version'], kind,
                                   ids[name], progress, 'Human-reviewed progress', event_id=lid + '-event')
        links.append(state.record_chapter_narrative_progress(link))
    for name, kind, rule in (('thread', 'THREAD', 'THREAD_PROGRESS_BY'),
                             ('seed', 'FORESHADOWING', 'FORESHADOWING_PAYOFF_BY'),
                             ('unpaid', 'FORESHADOWING', 'FORESHADOWING_PAYOFF_BY')):
        if name == 'unpaid' and not unpaid:
            continue
        e.narrative.create_expectation(NarrativeExpectation(e.nid + '-' + name + '-expect', e.nid,
                                      kind, ids[name], rule, 5))
    return chapters, ids, state.list_chapter_progress(e.nid), state


def check(e, chapter, facts=None):
    return e.review.check(e.nid, e.scope, 'author', 'narrative', FindingCheckIn(
        chapter_id=chapter['id'], expected_source_version=chapter['version'], facts=facts or {}))


def test_blank_facts_actual_route_uses_original_reviewed_progress(review_env, monkeypatch):
    e = review_env
    chapters, ids, links, state = owner_fixture(e)
    captured = e.api.finding_review_service
    for name in ('continuity', 'narrative', 'chapters', 'novels'):
        monkeypatch.setattr(captured, name, getattr(e, name))
    response = checked(e.client.post(e.review_base + '/narrative/review-checks', json={
        'chapter_id': chapters[-1]['id'], 'expected_source_version': chapters[-1]['version'], 'facts': {},
    }))
    assert response['provenance'] == 'STORED_NARRATIVE_FACTS'
    assert [(row['finding_type'], row['subject_id']) for row in response['items']] == [
        ('FORESHADOWING_OVERDUE', ids['unpaid'])]
    # Advisory review must never alter the original facts or automatically resolve them.
    assert state.list_chapter_progress(e.nid) == links
    assert all(row['status'] == 'OPEN' for row in response['items'])


@pytest.mark.parametrize('thread_number,payoff_number,last_number,overdue', [
    (4, 4, 6, 'thread'), (7, 4, 7, 'thread'), (5, 6, 6, 'seed'), (5, 7, 7, 'seed'),
])
def test_early_thread_late_payoff_and_future_progress_remain_overdue(
        review_env, thread_number, payoff_number, last_number, overdue):
    e = review_env
    chapters, ids, _, _ = owner_fixture(e, thread_number, payoff_number, last_number)
    result = check(e, chapters[5])
    assert {row['subject_id'] for row in result['items']} == {ids[overdue], ids['unpaid']}


@pytest.mark.parametrize('change', ['edit', 'archive', 'delete'])
def test_contributing_chapter_changes_invalidate_review_and_progress(review_env, change):
    e = review_env
    chapters, ids, _, _ = owner_fixture(e)
    row = check(e, chapters[-1])['items'][0]
    accepted = e.review.review(e.nid, e.scope, 'author', 'narrative', row['id'], decision(row))
    chapter = chapters[3]
    if change == 'edit':
        e.chapters.save(chapter['id'], {'content': 'The earlier payoff was removed.', 'version': chapter['version']})
    elif change == 'archive':
        e.chapters.archive(chapter['id'], chapter['version'])
    else:
        e.chapters.delete(chapter['id'])
    stale = e.review.get(e.nid, e.scope, 'narrative', row['id'])
    assert stale['stale_source'] and not stale['suppression_active']
    with pytest.raises(FindingReviewConflict, match='FINDING_SOURCE_STALE'):
        e.review.review(e.nid, e.scope, 'author', 'narrative', row['id'], decision(accepted))
    assert {row['subject_id'] for row in check(e, chapters[-1])['items']} == {ids['seed'], ids['unpaid']}


def test_reordering_does_not_rebind_chapter_identity_or_progress_number(review_env):
    e = review_env
    chapters, ids, _, _ = owner_fixture(e)
    first = check(e, chapters[-1])
    e.chapters.move(chapters[3]['id'], 'up')
    second = check(e, chapters[-1])
    assert [row['subject_id'] for row in second['items']] == [ids['unpaid']]
    assert second['source_digest'] == first['source_digest']


def overwrite(e, kind, row):
    """Corruption fixture only: keep real storage, deliberately damage one row."""
    repository = e.bundle.narrative
    if e.backend == 'file':
        data = repository._read(e.nid)
        data[kind] = [deepcopy(row) if item['id'] == row['id'] else item for item in data[kind]]
        repository._write(e.nid, data)
    else:
        import json
        from app.repositories.postgres.narrative import TABLES
        with repository.connection_factory() as connection:
            connection.execute(f'UPDATE {TABLES[kind]} SET payload=%s WHERE project_id=%s AND id=%s',
                               (json.dumps(row), e.nid, row['id']))
            connection.commit()


@pytest.mark.parametrize('damage', ['event_subject', 'event_version', 'event_type', 'event_link',
                                    'link_scope', 'link_project', 'subject_association'])
def test_unverified_or_cross_scope_progress_cannot_hide_overdue_findings(review_env, damage):
    e = review_env
    chapters, ids, links, _ = owner_fixture(e)
    link = next(row for row in links if row['progress_type'] == 'PAYOFF')
    if damage.startswith('event_'):
        row = e.bundle.narrative.get(e.nid, 'events', link['event_id'])
        if damage == 'event_subject': row['subject_id'] = ids['unpaid']
        elif damage == 'event_version': row['chapter_version_id'] += '9'
        elif damage == 'event_type': row['event_type'] = 'FREE_FORM_PAYOFF'
        else: row['payload']['link_id'] = 'another-link'
        overwrite(e, 'events', row)
    elif damage.startswith('link_'):
        row = e.bundle.narrative.get(e.nid, 'chapter_links', link['id'])
        if damage == 'link_scope': row['branch_id'] = 'unsupported-branch'
        else: row['project_id'] = 'another-project'
        overwrite(e, 'chapter_links', row)
    else:
        row = e.bundle.narrative.get(e.nid, 'foreshadowing', ids['seed'])
        row['payoff_event_id'] = 'unrelated-event'
        overwrite(e, 'foreshadowing', row)
    assert {row['subject_id'] for row in check(e, chapters[-1])['items']} == {ids['seed'], ids['unpaid']}


def test_status_and_arbitrary_event_prose_are_not_reviewed_chapter_progress(review_env):
    from app.narrative import NarrativeEvent
    e = review_env
    chapters, ids, _, state = owner_fixture(e)
    state.transition_foreshadowing(e.nid, ids['unpaid'], 'DEVELOPING', NarrativeEvent(
        e.nid + '-free-development', e.nid, 'FORESHADOWING:DEVELOPED', ids['unpaid'],
        chapters[1]['id'] + ':v1', payload={'summary': 'It developed.'}))
    state.transition_foreshadowing(e.nid, ids['unpaid'], 'PAYOFF', NarrativeEvent(
        e.nid + '-free-payoff', e.nid, 'FORESHADOWING:PAYOFF', ids['unpaid'],
        chapters[3]['id'] + ':v1', payload={'summary': 'Paid off before the deadline.'}))
    assert [row['subject_id'] for row in check(e, chapters[-1])['items']] == [ids['unpaid']]


def test_supporting_changes_with_same_derived_numbers_still_invalidate_review(review_env):
    e = review_env
    chapters, ids, links, _ = owner_fixture(e)
    row = check(e, chapters[-1])['items'][0]
    e.review.review(e.nid, e.scope, 'author', 'narrative', row['id'], decision(row))
    thread = e.bundle.narrative.get(e.nid, 'threads', ids['thread'])
    thread['title'] = 'The same reviewed progress, amended subject snapshot'
    overwrite(e, 'threads', thread)
    stale = e.review.get(e.nid, e.scope, 'narrative', row['id'])
    assert stale['stale_source'] and not stale['suppression_active']
    assert [row['subject_id'] for row in check(e, chapters[-1])['items']] == [ids['unpaid']]


@pytest.mark.parametrize('unpaid', [True, False])
def test_progress_source_change_during_evaluation_fails_before_write(review_env, monkeypatch, unpaid):
    e = review_env
    chapters, _, _, _ = owner_fixture(e, unpaid=unpaid)
    evaluate = e.review._facts
    def changed(*args):
        findings = evaluate(*args)
        e.chapters.save(chapters[3]['id'], {'content': 'Payoff removed during checking.', 'version': 1})
        return findings
    monkeypatch.setattr(e.review, '_facts', changed)
    with pytest.raises(FindingReviewConflict, match='FINDING_SOURCE_STALE'):
        check(e, chapters[-1])
    assert e.bundle.narrative.list(e.nid, 'findings') == []


def test_explicit_facts_keep_their_own_progress_maps(review_env):
    e = review_env
    chapters, ids, _, _ = owner_fixture(e)
    facts = {'current_chapter': 6, 'expectations': e.bundle.narrative.list(e.nid, 'expectations'),
             'thread_last_progress': {}, 'foreshadowing_payoff_chapter': {}}
    result = check(e, chapters[-1], facts)
    assert result['provenance'] == 'AUTHOR_SUPPLIED_FACTS'
    assert {row['subject_id'] for row in result['items']} == set(ids.values())
    facts['thread_last_progress'] = {ids['thread']: 5}
    facts['foreshadowing_payoff_chapter'] = {ids['seed']: 4}
    assert [row['subject_id'] for row in check(e, chapters[-1], facts)['items']] == [ids['unpaid']]


def test_branch_blank_facts_still_require_explicit_observations(review_env, monkeypatch):
    from app.services.branch_manuscript_service import BranchManuscriptService
    e = review_env
    owner_fixture(e, default_scope=False)
    scoped(e, monkeypatch)
    owner = BranchManuscriptService(e.store, e.novels, e.chapters, e.scopes)
    monkeypatch.setattr(e.chapters, 'branch_authority', owner.for_scope, raising=False)
    chapter = owner.for_scope(e.scope).create(e.nid, {'title': 'Branch', 'content': 'Independent branch source'})
    response = e.review_client.post(e.review_base + '/narrative/review-checks', headers=e.headers, json={
        'chapter_id': chapter['id'], 'expected_source_version': 1, 'facts': {}})
    assert response.status_code == 422
    assert response.json()['detail']['message'] == 'BRANCH_FACTS_REQUIRED'
