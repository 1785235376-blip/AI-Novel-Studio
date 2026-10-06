"""Actual mounted API, authoritative File/PG chapters and trusted role stack."""
import pytest
from test_r3_mounted_contracts import mounted, prefix, scoped, checked
from app.experimental.revision_intelligence import text_blocks


@pytest.fixture
def revisions(mounted, monkeypatch):
    e = mounted
    for name, value in [('store', e.store), ('novels', e.novels), ('chapters', e.chapters)]:
        monkeypatch.setattr(e.experimental.revision_intelligence_service, name, value)
    return e


def picked(e):
    current = e.chapters.get(e.chapter['id']); blocks = text_blocks(current['document']); b = blocks[-1]
    return {'chapter_id': current['id'], 'chapter_version': current['version'], 'from_pos': b['start'], 'to_pos': b['end'], 'text': b['text']}


def test_mounted_reviewed_apply_and_lock_enforcement_after_off_v1(revisions, monkeypatch):
    e = revisions; base = e.base + '/revisions'; value = picked(e)
    snapshot = checked(e.client.post(base + '/selection', json=value))
    lock = checked(e.client.post(base + '/locks', json={'selection': value, 'selection_digest': snapshot['selection_digest'], 'action': 'lock'}))
    for flags, v1 in [('', 'false'), ('revision_intelligence_v2', 'true')]:
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', flags); monkeypatch.setenv('V1_ACCEPTANCE_MODE', v1)
        denied = e.client.put(e.prefix + '/chapters/' + value['chapter_id'], json={'version': lock['version'], 'content': 'Do not bypass locks', 'source': 'AI_ACCEPT'})
        assert denied.status_code == 409 and denied.json()['code'] == 'AI_PARAGRAPH_LOCKED_OR_STALE'
        assert e.chapters.get(value['chapter_id']) == lock
        assert e.client.get(base + '/catalog').status_code == 404
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'revision_intelligence_v2'); monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'false')
    value = picked(e); snapshot = checked(e.client.post(base + '/selection', json=value))
    unlocked = checked(e.client.post(base + '/locks', json={'selection': value, 'selection_digest': snapshot['selection_digest'], 'action': 'unlock'}))
    value = picked(e); snapshot = checked(e.client.post(base + '/selection', json=value))
    p = checked(e.client.post(base + '/proposals', json={'selection': value, 'selection_digest': snapshot['selection_digest'], 'replacements': [{'anchor_id': snapshot['blocks'][0]['anchor_id'], 'text': '合成已审核🙂é段落'}]}), 201)
    decision = {'expected_version': p['version'], 'accept_ids': [p['blocks'][0]['anchor_id']]}
    receipt = checked(e.client.post(base + '/proposals/' + p['id'] + '/preview', json=decision))
    saved = checked(e.client.post(base + '/proposals/' + p['id'] + '/apply', json={**decision, 'preview_digest': receipt['preview_digest']}))
    assert saved['chapter']['version'] == unlocked['version'] + 1
    assert e.chapters.history(value['chapter_id'])[0]['document'] == unlocked['document']


def test_mounted_real_reader_cannot_view_author_selection_or_candidates(revisions, monkeypatch):
    e = scoped(revisions, monkeypatch); base = e.base + '/revisions'
    for path in ['/catalog', '/proposals', '/milestones']:
        response = e.client.get(base + path, headers=e.viewer_headers)
        assert response.status_code == 403
    response = e.client.post(base + '/selection', json=picked(e), headers=e.viewer_headers)
    assert response.status_code == 403


def test_mounted_branch_authority_is_honest_not_main_manuscript_projection(revisions, monkeypatch):
    e = scoped(revisions, monkeypatch)
    response = e.client.get(e.base + '/revisions/catalog', headers=e.headers)
    value = checked(response)
    assert not value['branch_sources_available'] and value['chapters'] == []
    response = e.client.post(e.base + '/revisions/selection', json=picked(e), headers=e.headers)
    assert response.status_code == 422
