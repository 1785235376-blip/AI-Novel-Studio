"""Actual mounted A10 routes and native authority, File + real PostgreSQL."""
import json

import pytest

from app.experimental import research_library as module
from app.experimental.flags import FLAGS
from test_r3_mounted_contracts import mounted, prefix, checked, scoped
from test_r4_research_library import payload


@pytest.fixture
def research_mounted(mounted, monkeypatch):
    e = mounted
    service = e.experimental.research_library_service
    for key, value in [('store', e.store), ('novels', e.novels), ('chapters', e.chapters), ('legacy', e.capabilities), ('world', e.experimental.world_service)]:
        monkeypatch.setattr(service, key, value)
    e.research = service
    e.path = e.base + '/research-library'
    return e


def test_mounted_source_citation_notes_reviewed_setting_and_delete_journey(research_mounted):
    e = research_mounted; before = e.chapters.get(e.chapter['id'])
    row = checked(e.client.post(e.path + '/sources/import', json=payload()), 201)
    ref = row['paragraphs'][0]['citation']
    note = checked(e.client.post(e.path + '/notes', json={'title': 'Port note', 'text': 'Original fictional adaptation.', 'citations': [ref]}), 201)
    assert checked(e.client.post(e.path + '/citation', json=ref))['text'] == 'Tidal gates close at dusk.'
    draft = checked(e.client.post(e.path + '/setting-drafts', json={'title': 'Secret lantern rule', 'original_setting': 'A blue lantern opens the fictional tidal gate.', 'citations': [ref], 'confirm_original': True}), 201)
    reviewed = checked(e.client.post(e.path + f"/setting-drafts/{draft['id']}/review", json={'expected_version': 1}))
    assert reviewed['status'] == 'RESEARCH_REVIEWED' and not reviewed['canon_promotion_available']
    assert checked(e.client.get(e.path + f"/sources/{row['id']}/backrefs"))['total'] == 2
    assert e.client.get(e.base + f"/world/records/{draft['id']}").status_code == 404
    assert e.client.post(e.base + f"/world/records/{draft['id']}/approve", json={'expected_version': 2}).status_code == 404
    assert e.client.get(e.prefix + f"/novels/{e.nid}/research/{row['id']}").status_code == 404
    assert checked(e.client.get(e.base + '/world/canon'))['items'] == []
    checked(e.client.post(e.path + f"/sources/{row['id']}/delete", json={'expected_version': 1}))
    for endpoint in ['/sources', '/notes', '/setting-drafts', '/search?q=Tidal']:
        response = checked(e.client.get(e.path + endpoint))
        assert response['items'] == []
        assert 'Secret lantern rule' not in json.dumps(response) and note['id'] not in json.dumps(response)
    assert e.client.post(e.path + '/context-preview', json={'citations': [ref]}).status_code == 404
    assert e.chapters.get(e.chapter['id']) == before


def test_exact_default_off_dependencies_v1_override_and_old_routes(research_mounted, monkeypatch):
    e = research_mounted
    all_flags = ','.join(FLAGS)
    for flags, v1 in [('', 'false'), ('*', 'false'), ('research_library_v2', 'false'), (all_flags, 'true')]:
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', flags); monkeypatch.setenv('V1_ACCEPTANCE_MODE', v1)
        for endpoint in ['/sources', '/notes', '/setting-drafts', '/search?q=secret']:
            assert e.client.get(e.path + endpoint).status_code == 404
        assert e.client.post(e.path + '/sources/import', json=payload()).status_code == 404
    assert not e.store.read(e.nid, e.scope)['collections'].get('research_sources')


def test_native_scoped_reader_wrong_branch_and_missing_session_never_get_private_metadata(research_mounted, monkeypatch):
    e = scoped(research_mounted, monkeypatch)
    row = checked(e.client.post(e.path + '/sources/import', json=payload(), headers=e.headers), 201)
    for endpoint in ['/sources', f"/sources/{row['id']}", '/notes', '/setting-drafts', '/search?q=Tidal']:
        for headers in [e.viewer_headers, {}, {**e.headers, 'X-Branch-ID': e.other_branch}]:
            response = e.client.get(e.path + endpoint, headers=headers)
            assert response.status_code in {401, 403, 404}
            assert row['title'] not in response.text and 'Tidal gates' not in response.text
    assert e.client.get(e.path + '/sources', headers=e.headers).json()['total'] == 1


@pytest.mark.parametrize('revocation', ['role', 'session'])
def test_native_authority_rechecked_after_private_projection(research_mounted, monkeypatch, revocation):
    e = scoped(research_mounted, monkeypatch)
    checked(e.client.post(e.path + '/sources/import', json=payload(), headers=e.headers), 201)
    original = e.research.sources
    def projection(*args):
        result = original(*args)
        if revocation == 'role': e.authorization.revoke_role(e.role, e.lead)
        else: e.sessions.revoke(e.lead)
        return result
    monkeypatch.setattr(e.research, 'sources', projection)
    response = e.client.get(e.path + '/sources', headers=e.headers)
    assert response.status_code in {401, 403} and 'Synthetic tide archive' not in response.text


@pytest.mark.parametrize('change', ['role', 'flag', 'v1'])
def test_native_extraction_rechecks_before_persist_and_returns_no_secret(research_mounted, monkeypatch, change):
    e = scoped(research_mounted, monkeypatch)
    original = module.extract_document
    def extract(*args):
        result = original(*args)
        if change == 'role': e.authorization.revoke_role(e.role, e.lead)
        elif change == 'flag': monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
        else: monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
        return result
    monkeypatch.setattr(module, 'extract_document', extract)
    response = e.client.post(e.path + '/sources/import', json=payload(), headers=e.headers)
    assert response.status_code in {403, 404} and 'Tidal gates' not in response.text
    assert not e.store.read(e.nid, e.scope)['collections'].get('research_sources')
