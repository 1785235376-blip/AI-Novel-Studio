"""Audience slice against mounted production routes and real chapter repositories.

Parametrized File / genuine PostgreSQL and /api /api/v1. Reuse the production
composition fixture: original services and authorization, disposable repository
bindings only. PostgreSQL is opt-in and is not simulated by this test.
"""
from copy import deepcopy

from test_r3_mounted_contracts import mounted, prefix, checked
from test_r4_style_judge_mounted import style_judge
from app.repositories.factory import create_repository_bundle
from app.services import ChapterService
from app.source_privacy import content_digest


def test_mounted_audience_real_chapter_preview_disposition_and_stale_source(style_judge):
    e = style_judge
    cid = e.chapter['id']
    e.chapters.save(cid, {'version': e.chapter['version'],
                         'content': '甲🙂 乙。\n\nA second saved paragraph.'})
    current = e.chapters.get(cid)
    # Read through a newly constructed original repository, not a copied dict or
    # an invented canonical digest. The same exercise reaches actual PG storage.
    reopened = create_repository_bundle(e.config, data_root=e.root)
    try:
        persisted = ChapterService(reopened.chapters).get(cid)
        assert persisted == current
    finally:
        if e.backend == 'postgres': reopened.novels.database.engine.dispose()
    original = deepcopy(persisted)
    base = e.base + '/narrative-judge'
    source_path = base + f'/audience/source/{cid}'
    prepared = checked(e.client.post(source_path + '/prepare', json={'expected_version': current['version']}))
    source_response = e.client.get(source_path, params={'expected_version': current['version']})
    assert source_response.headers['cache-control'] == 'no-store'
    source = checked(source_response)
    assert source == prepared
    assert source['chapter_version'] == persisted['version']
    paragraph = source['paragraphs'][0]
    assert persisted['content'][paragraph['start']:paragraph['end']] == paragraph['quote']
    assert '🙂' in paragraph['quote']
    evidence = {**paragraph, 'chapter_id': cid, 'chapter_version': persisted['version']}
    body = {'chapter_id': cid, 'expected_version': persisted['version'],
            'expected_source_digest': source['source_digest'],
            'profiles': [
                {'name': 'Introductory target', 'genre_experience': 'NOVICE',
                 'target_age_group': 'GENERAL', 'language_habit': 'Modern Chinese', 'reading_speed': 120},
                {'name': 'Experienced target', 'genre_experience': 'EXPERIENCED',
                 'target_age_group': 'ADULTS', 'language_habit': 'Bilingual prose', 'reading_speed': 240},
            ],
            'comparison': 'DIFFERENT_ADVICE',
            'observations': [
                {'profile_index': index, 'evidence': evidence,
                 'observation': f'Author observation for target {index}',
                 'suggestion': f'Author suggestion for target {index}'}
                for index in (0, 1)
            ]}
    row = checked(e.client.post(base + '/audience/comparisons', json=body), 201)
    assert row['audience']['source_digest'] == content_digest(persisted)
    assert row['model_called'] is False
    assert all(finding['origin'] == 'AUTHOR_ENTERED' for finding in row['findings'])
    finding = row['findings'][0]
    review_path = base + f'/findings/{finding["id"]}/review'
    accepted = checked(e.client.post(review_path, json={
        'expected_version': finding['version'], 'action': 'accept', 'reason': 'Author accepts for this exact saved source'}))
    assert accepted['decision'] == 'ACCEPTED'
    reopened_finding = checked(e.client.post(review_path, json={
        'expected_version': accepted['version'], 'action': 'reopen', 'reason': 'Author requests another look'}))
    assert reopened_finding['decision'] == 'PENDING'
    assert [event['action'] for event in reopened_finding['review_history']][-2:] == ['ACCEPT', 'REOPEN']
    history = checked(e.client.get(base + '/audience/comparisons'))['items']
    saved = next(item for item in history if item['id'] == row['id'])
    assert saved['findings'][0]['version'] == reopened_finding['version']
    assert e.chapters.get(cid) == original  # Decisions never rewrite the chapter.
    threads = e.creation._rows('review_threads')
    assert next(thread for thread in threads if thread['id'] == finding['id'])['narrative_judge']['decision'] == 'PENDING'

    # A real original ChapterService save advances the actual stored source.
    updated = e.chapters.save(cid, {'version': persisted['version'], 'content': 'A new stored source.'})
    assert updated['version'] > persisted['version']
    stale = next(item for item in checked(e.client.get(base + '/audience/comparisons'))['items'] if item['id'] == row['id'])
    assert stale['stale'] and stale['findings'] == [] and 'audience' not in stale
    rejected = e.client.post(review_path, json={
        'expected_version': reopened_finding['version'], 'action': 'accept', 'reason': 'Old evidence cannot be reused'})
    assert rejected.status_code == 409 and paragraph['quote'] not in rejected.text
    assert e.client.post(base + '/audience/comparisons', json=body).status_code == 409
