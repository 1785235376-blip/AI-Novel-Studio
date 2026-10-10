"""Mounted aliases, actual repository sources, explicit opt-in and membership."""
import pytest

from test_r3_mounted_contracts import mounted, prefix, checked, scoped


@pytest.fixture
def style_judge(mounted, monkeypatch):
    e = mounted
    for service in (e.experimental.style_analysis_service, e.experimental.narrative_judge_service):
        for name, value in (("store", e.store), ("novels", e.novels), ("chapters", e.chapters), ("creation", e.creation)):
            monkeypatch.setattr(service, name, value)
    monkeypatch.setattr(e.experimental.narrative_judge_service, 'world', e.experimental.world_service)
    monkeypatch.setattr(e.experimental.narrative_judge_service, 'planning', e.experimental.planning_service)
    return e


def test_mounted_style_and_judge_use_current_real_repositories(style_judge):
    e = style_judge
    current = e.chapters.save(e.chapter['id'], {'content': 'The gate was closed.\n\nThe gate was closed.', 'version': e.chapter['version']})
    cid = current['id']; before = e.chapters.get(cid)
    profile = checked(e.client.post(e.base + '/style-analysis/profiles', json={'title': 'A measured voice', 'instructions': 'Use concrete verbs.', 'chapter_ids': [cid]}), 201)
    result = checked(e.client.post(e.base + '/style-analysis/analyses', json={'style_id': profile['id'], 'expected_style_version': 1, 'language': 'en', 'samples': [{'chapter_id': cid, 'expected_version': current['version']}]}), 201)
    assert result['metrics']['paragraph_count'] == 2
    approved = checked(e.client.post(e.base + '/style-analysis/profiles/' + profile['id'] + '/approve', json={'expected_version': 1}))
    preview = checked(e.client.post(e.base + '/style-analysis/profiles/' + profile['id'] + '/preview', json={'expected_version': approved['version'], 'operation': 'continue'}))
    assert preview['instructions'] == 'Use concrete verbs.' and preview['model_called'] is False
    # Approving a profile changes its source authority version; old receipt is not silently carried forward.
    assert checked(e.client.get(e.base + '/style-analysis/analyses'))['items'][0]['stale']
    run = checked(e.client.post(e.base + '/narrative-judge/runs', json={'chapter_ids': [cid], 'expected_versions': {cid: current['version']}, 'rubric_id': 'narrative-rules-v1'}), 201)
    finding = run['findings'][0]
    reviewed = checked(e.client.post(e.base + '/narrative-judge/findings/' + finding['id'] + '/review', json={'expected_version': 1, 'action': 'ignore', 'reason': 'Intentional refrain'}))
    assert reviewed['decision'] == 'IGNORED'
    assert e.chapters.get(cid) == before
    e.chapters.save(cid, {'content': 'Changed current text', 'version': current['version']})
    stale = checked(e.client.get(e.base + '/narrative-judge/runs/' + run['id']))
    assert stale['stale'] and stale['findings'] == []
    rejected = e.client.post(e.base + '/narrative-judge/findings/' + finding['id'] + '/review', json={'expected_version': 2, 'action': 'reopen', 'reason': 'Old evidence'})
    assert rejected.status_code == 409 and 'The gate was closed' not in rejected.text


def test_mounted_exact_flags_dependencies_and_v1_stop_all_reads_writes(style_judge, monkeypatch):
    e = style_judge
    paths = ['/style-analysis/catalog', '/style-analysis/analyses', '/narrative-judge/catalog', '/narrative-judge/runs']
    for config, v1 in [('', 'false'), ('*', 'false'), ('style_dna_v2,narrative_quality_judge_v2,advanced_planning_v2,world_character_engines_v2,unified_review_inbox', 'true')]:
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', config); monkeypatch.setenv('V1_ACCEPTANCE_MODE', v1)
        for path in paths: assert e.client.get(e.base + path).status_code == 404
        assert e.client.post(e.base + '/style-analysis/profiles', json={'title': 'Denied', 'instructions': 'Not created'}).status_code == 404
        assert e.client.post(e.base + '/narrative-judge/runs', json={'chapter_ids': [e.chapter['id']], 'expected_versions': {e.chapter['id']: e.chapter['version']}}).status_code == 404
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'false'); monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_quality_judge_v2')
    assert e.client.get(e.base + '/narrative-judge/catalog').status_code == 404
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'style_dna_v2')
    assert e.client.get(e.base + '/style-analysis/catalog').status_code == 200
    assert not e.creation.list_records(e.nid, e.scope)['items']


def test_mounted_reader_cannot_access_author_judge_or_inbox_projection(style_judge, monkeypatch):
    e = scoped(style_judge, monkeypatch)
    for path in ('/style-analysis/catalog', '/style-analysis/analyses', '/narrative-judge/catalog', '/narrative-judge/runs'):
        assert e.client.get(e.base + path, headers=e.viewer_headers).status_code == 403
    calls = []
    def private_projection(*args):
        calls.append(args)
        return [{'id': 'private', 'title': 'UNKNOWN_SECRET_TITLE', 'version': 1}]
    monkeypatch.setattr(e.experimental.narrative_judge_service, 'list_review_items', private_projection)
    inbox = e.client.get(e.base + '/review-inbox?domain=narrative_judge', headers=e.viewer_headers)
    assert inbox.status_code == 200
    assert not calls and inbox.json()['items'] == [] and 'UNKNOWN_SECRET_TITLE' not in inbox.text


@pytest.mark.parametrize('revocation', ['role', 'session'])
@pytest.mark.parametrize('surface', ['style', 'judge', 'inbox'])
def test_mounted_rechecks_real_authority_after_read(style_judge, monkeypatch, revocation, surface):
    e = scoped(style_judge, monkeypatch)
    def revoke():
        if revocation == 'role': e.authorization.revoke_role(e.role, e.lead)
        else: e.sessions.revoke(e.lead)
    if surface == 'inbox':
        def projection(*args):
            revoke()
            return [{'id': 'private', 'title': 'REVOKED_PRIVATE_RESULT', 'version': 1}]
        monkeypatch.setattr(e.experimental.narrative_judge_service, 'list_review_items', projection)
        result = e.client.get(e.base + '/review-inbox?domain=narrative_judge', headers=e.headers)
        assert result.status_code in {200, 401, 403}
        if result.status_code == 200: assert result.json()['items'] == []
    else:
        service = e.experimental.style_analysis_service if surface == 'style' else e.experimental.narrative_judge_service
        original = service.catalog
        def catalog(*args):
            value = original(*args); value['private_test_marker'] = 'REVOKED_PRIVATE_RESULT'; revoke(); return value
        monkeypatch.setattr(service, 'catalog', catalog)
        path = '/style-analysis/catalog' if surface == 'style' else '/narrative-judge/catalog'
        result = e.client.get(e.base + path, headers=e.headers)
        assert result.status_code in {401, 403}
    assert 'REVOKED_PRIVATE_RESULT' not in result.text
