"""A10 native File/real-PG persistence, source authority, no automatic promotion."""
import base64
import copy
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.experimental import research_library as module
from app.experimental.common import StaleSourceError
from app.experimental.research_library import ResearchLibraryService
from app.experimental.research_library_api import create_research_library_router
from app.experimental.store import ExperimentalStore
from app.experimental.world import WorldService
from app.experimental.story_graph import StoryGraphService
from app.services.v1_capability_service import CapabilityVersionConflict, V1CapabilityService, ResearchRecordIn
from test_r3_planning import planning_env


def payload(text='Tidal gates close at dusk.\n\nUse lanterns after sunset.', **extra):
    return {'title': 'Synthetic tide archive', 'author': 'Synthetic author', 'source': 'Public synthetic fixture', 'source_version': 'edition 1', 'usage_notes': 'World-building reference', 'filename': 'tide.txt', 'content_base64': base64.b64encode(text.encode()).decode(), **extra}


@pytest.fixture
def research(planning_env):
    e = planning_env
    e.legacy = V1CapabilityService(e.root, e.novels, e.chapter_service, SimpleNamespace())
    e.world = WorldService(e.store, e.novels, e.chapter_service)
    e.research = ResearchLibraryService(e.store, e.novels, e.chapter_service, legacy=e.legacy, world=e.world)
    return e


def imported(e, **extra):
    return e.research.import_file(e.nid, e.scope, 'author', payload(**extra), guard=lambda: None)


def citation(row): return row['paragraphs'][0]['citation']


def note(e, ref):
    return e.research.create_note(e.nid, e.scope, 'author', {'title': 'Field note', 'text': 'Adapt the harbor timing.', 'citations': [ref]}, guard=lambda: None)


def adopt(e, ref):
    return e.research.adopt(e.nid, e.scope, 'author', {'title': 'Lantern gates', 'original_setting': 'In this fictional harbor, gates answer only to blue lanterns.', 'citations': [ref], 'confirm_original': True}, guard=lambda: None)


def test_native_import_restart_metadata_exact_citation_original_and_no_legacy_copy(research):
    e = research; before = copy.deepcopy((e.chapters, e.rows)); row = imported(e)
    restored = ResearchLibraryService(ExperimentalStore(e.root, e.backend, e.url), e.novels, e.chapter_service, legacy=e.legacy, world=e.world)
    source = restored.source(e.nid, e.scope, 'author', row['id'])
    assert source['author'] == 'Synthetic author' and source['source_version'] == 'edition 1' and source['accessed_at']
    proof = restored.resolve(e.nid, e.scope, 'author', citation(row))
    assert proof['paragraph'] == 1 and proof['text'] == 'Tidal gates close at dusk.'
    assert restored.original(e.nid, e.scope, 'author', row['id']) == (base64.b64decode(payload()['content_base64']), 'tide.txt')
    assert e.legacy.list_research(e.nid)['items'] == [] and (e.chapters, e.rows) == before


def test_private_sources_hide_titles_counts_and_cross_branch_project(research):
    e = research; row = imported(e)
    assert e.research.sources(e.nid, e.scope, 'other')['total'] == 0
    assert e.research.search(e.nid, e.scope, 'other', 'Tidal')['items'] == []
    with pytest.raises(FileNotFoundError): e.research.resolve(e.nid, e.scope, 'other', citation(row))
    branch = {'mode': 'collaboration', 'novel_id': e.nid, 'workspace_id': 'w', 'storyline_id': 's', 'branch_id': 'b'}
    assert e.research.sources(e.nid, branch, 'author')['items'] == []
    with pytest.raises(FileNotFoundError): e.research.source('different-project', e.scope, 'author', row['id'])
    shared = imported(e, access='PROJECT')
    assert [item['id'] for item in e.research.sources(e.nid, e.scope, 'other')['items']] == [shared['id']]
    with pytest.raises(FileNotFoundError): e.research.transition_source(e.nid, e.scope, 'other', shared['id'], 1, 'delete', guard=lambda: None)


def test_notes_backrefs_preview_and_original_reviewed_setting_remain_separate(research):
    e = research; row = imported(e); ref = citation(row)
    saved_note = note(e, ref); draft = adopt(e, ref)
    assert e.research.backrefs(e.nid, e.scope, 'author', row['id'])['total'] == 2
    assert e.research.context(e.nid, e.scope, 'author', [ref])['automatic_injection'] is False
    assert e.world.records(e.nid, e.scope) == [] and e.world.canon(e.nid, e.scope) == []
    for method in [e.world.record, e.world.history]:
        with pytest.raises(FileNotFoundError): method(e.nid, e.scope, draft['id'])
    with pytest.raises(FileNotFoundError): e.world.review(e.nid, e.scope, 'author', draft['id'], 'approve', 1)
    current = e.research.review_draft(e.nid, e.scope, 'author', draft['id'], 1, 'review', guard=lambda: None)
    assert current['status'] == 'RESEARCH_REVIEWED' and current['canon_state'] == 'CANDIDATE'
    graph = StoryGraphService(e.store, e.novels, e.chapter_service)
    assert draft['title'] not in json.dumps(graph.catalog(e.nid, e.scope))
    assert e.research.notes(e.nid, e.scope, 'author')['items'][0]['id'] == saved_note['id']
    assert e.research.drafts(e.nid, e.scope, 'other')['total'] == 0
    assert e.research.review_draft(e.nid, e.scope, 'author', draft['id'], 2, 'reopen', guard=lambda: None)['status'] == 'REVIEW'


@pytest.mark.parametrize('action', ['revoke', 'delete'])
def test_source_invalidation_removes_context_index_notes_draft_titles_and_counts(research, action):
    e = research; row = imported(e); ref = citation(row); note(e, ref); draft = adopt(e, ref)
    with e.store.transaction(e.nid, e.scope) as state:
        for name in ('research_index', 'research_contexts', 'research_vectors', 'research_summaries'):
            state['collections'][name] = {'cache': {'source_ids': [row['id']], 'secret': 'never return'}}
    e.research.transition_source(e.nid, e.scope, 'author', row['id'], 1, action, guard=lambda: None)
    assert e.research.search(e.nid, e.scope, 'author', 'Tidal')['items'] == []
    assert e.research.sources(e.nid, e.scope, 'author')['total'] == 0
    assert e.research.notes(e.nid, e.scope, 'author')['total'] == 0
    assert e.research.drafts(e.nid, e.scope, 'author')['total'] == 0
    with pytest.raises(FileNotFoundError): e.research.context(e.nid, e.scope, 'author', [ref])
    with pytest.raises(FileNotFoundError): e.research.review_draft(e.nid, e.scope, 'author', draft['id'], 1, 'review', guard=lambda: None)
    for name in ('research_index', 'research_contexts', 'research_vectors', 'research_summaries'):
        assert e.store.read(e.nid, e.scope)['collections'][name] == {}


def test_versions_conflicts_stale_quotes_and_metadata_edit(research):
    e = research; row = imported(e); ref = citation(row)
    with pytest.raises(StaleSourceError): e.research.resolve(e.nid, e.scope, 'author', {**ref, 'quote_sha256': '0' * 64})
    body = {key: row[key] for key in ['title', 'author', 'source', 'source_version', 'usage_notes', 'access']}
    updated = e.research.edit_source(e.nid, e.scope, 'author', row['id'], {**body, 'title': 'Updated title', 'expected_version': 1}, guard=lambda: None)
    assert updated['version'] == 2
    with pytest.raises(StaleSourceError): e.research.resolve(e.nid, e.scope, 'author', ref)
    with pytest.raises(CapabilityVersionConflict): e.research.transition_source(e.nid, e.scope, 'author', row['id'], 1, 'delete', guard=lambda: None)


def test_existing_offline_sidecar_live_reference_edit_delete_invalidation_no_fetch(research, monkeypatch):
    e = research
    monkeypatch.setattr(module, 'fetch_webpage', lambda *args: pytest.fail('existing URLs must not fetch'))
    old = e.legacy.create_research(e.nid, ResearchRecordIn(title='Original research', excerpt='Tidal facts.', url='https://example.org'))
    view = e.research.source(e.nid, e.scope, 'author', 'legacy:' + old['id']); ref = citation(view)
    assert view['origin'] == 'LEGACY_LIVE' and view['storage'] == 'durable_sidecar'
    note(e, ref)
    e.legacy.update_research(e.nid, old['id'], ResearchRecordIn(title='Changed research', excerpt='Tidal facts.'), 1)
    assert e.research.notes(e.nid, e.scope, 'author')['total'] == 0
    assert e.research.sources(e.nid, e.scope, 'author')['items'][0]['title'] == 'Changed research'
    e.legacy.delete_research(e.nid, old['id'], 2)
    assert e.research.sources(e.nid, e.scope, 'author')['total'] == 0
    assert not e.store.read(e.nid, e.scope)['collections'].get('research_sources')


def test_disable_or_revoke_during_extraction_blocks_commit(research, monkeypatch):
    e = research; allowed = [True]; original = module.extract_document
    def extraction(*args): result = original(*args); allowed[0] = False; return result
    monkeypatch.setattr(module, 'extract_document', extraction)
    def guard():
        if not allowed[0]: raise HTTPException(403, 'revoked')
    with pytest.raises(HTTPException): e.research.import_file(e.nid, e.scope, 'author', payload(), guard=guard)
    assert e.research.sources(e.nid, e.scope, 'author')['total'] == 0


def test_guard_failure_inside_adoption_transaction_rolls_back(research):
    e = research; ref = citation(imported(e)); calls = []
    def guard():
        calls.append(1)
        if len(calls) == 2: raise HTTPException(403, 'revoked')
    with pytest.raises(HTTPException): e.research.adopt(e.nid, e.scope, 'author', {'title': 'New', 'original_setting': 'Entirely new synthetic rule', 'citations': [ref], 'confirm_original': True}, guard=guard)
    assert e.research.drafts(e.nid, e.scope, 'author')['total'] == 0


def test_api_reauthorizes_after_projection_before_return_and_source_not_leaked(research, monkeypatch):
    e = research; allowed = [True]
    def authorize(nid, token, branch, permission):
        if token != 'valid' or not allowed[0]: raise HTTPException(403, {'code': 'DENIED'})
        return 'author', e.scope
    app = FastAPI(); app.include_router(create_research_library_router(e.research, authorize, lambda name: None))
    client = TestClient(app); base = f'/novels/{e.nid}/experimental/research-library'
    imported(e)
    original = e.research.sources
    def project(*args): result = original(*args); allowed[0] = False; return result
    monkeypatch.setattr(e.research, 'sources', project)
    response = client.get(base + '/sources', headers={'X-Session-Token': 'valid'})
    assert response.status_code == 403 and 'Synthetic tide archive' not in response.text


def test_scoped_api_full_local_journey_and_unsupported_actions(research):
    e = research
    app = FastAPI(); app.include_router(create_research_library_router(e.research, lambda *args: ('author', e.scope), lambda name: None))
    client = TestClient(app); base = f'/novels/{e.nid}/experimental/research-library'
    row = client.post(base + '/sources/import', json=payload()).json()
    assert client.get(base + '/sources').json()['total'] == 1
    assert client.get(base + '/search?q=Tidal').json()['items'][0]['citation'] == citation(row)
    assert client.post(base + '/sources/fetch-webpage', json={'title': 'No consent', 'url': 'https://example.org'}).status_code == 422
    assert client.post(base + f"/sources/{row['id']}/execute-plugin", json={'expected_version': 1}).status_code == 422
    original = client.get(base + f"/sources/{row['id']}/original")
    assert original.status_code == 200 and original.headers['content-type'] == 'application/octet-stream'
    assert original.headers['x-content-type-options'] == 'nosniff'


def test_image_page_citation_supports_manual_note_without_invented_text(research):
    import io
    from PIL import Image
    e = research; stream = io.BytesIO(); Image.new('RGB', (12, 12), 'blue').save(stream, 'PNG')
    row = e.research.import_file(e.nid, e.scope, 'author', {**payload(), 'filename': 'blue.png', 'content_base64': base64.b64encode(stream.getvalue()).decode()}, guard=lambda: None)
    assert row['paragraphs'] == [] and row['extraction_status'] == 'OCR_NOT_CONFIGURED'
    ref = row['page_citations'][0]
    proof = e.research.resolve(e.nid, e.scope, 'author', ref)
    assert proof['not_understood'] and proof['text'] == '' and proof['page'] == 1
    note(e, ref)
    assert e.research.notes(e.nid, e.scope, 'author')['total'] == 1
    with pytest.raises(StaleSourceError): e.research.resolve(e.nid, e.scope, 'author', {**ref, 'page': 2})


def test_request_body_limit_and_unauthorized_before_extraction(research, monkeypatch):
    e = research; allowed = [True]
    def auth(*args):
        if not allowed[0]: raise HTTPException(403, 'denied')
        return 'author', e.scope
    app = FastAPI(); app.include_router(create_research_library_router(e.research, auth, lambda name: None))
    client = TestClient(app); base = f'/novels/{e.nid}/experimental/research-library'
    monkeypatch.setattr(module, 'extract_document', lambda *args: pytest.fail('no parsing on oversized or unauthorized input'))
    response = client.post(base + '/sources/import', content=b'x' * (6 * 1024 * 1024 + 1), headers={'Content-Type': 'application/json'})
    assert response.status_code == 413
    allowed[0] = False
    assert client.post(base + '/sources/import', json=payload()).status_code == 403


def test_scope_access_reduction_hides_downstream_content_and_counts(research):
    e = research; source = imported(e, access='PROJECT'); ref = citation(source)
    e.research.create_note(e.nid, e.scope, 'other', {'title': 'Derived private title', 'text': 'Tidal note', 'citations': [ref]}, guard=lambda: None)
    assert e.research.notes(e.nid, e.scope, 'other')['total'] == 1
    body = {key: source[key] for key in ['title', 'author', 'source', 'source_version', 'usage_notes', 'access']}
    e.research.edit_source(e.nid, e.scope, 'author', source['id'], {**body, 'access': 'PRIVATE', 'expected_version': 1}, guard=lambda: None)
    assert e.research.sources(e.nid, e.scope, 'other')['total'] == 0
    assert e.research.notes(e.nid, e.scope, 'other')['total'] == 0
    with pytest.raises(FileNotFoundError): e.research.context(e.nid, e.scope, 'other', [ref])


def test_fetch_current_authority_rechecked_on_each_dispatch_and_real_text_saved(research, monkeypatch):
    e = research; calls = []
    def fetch(url, *, guard):
        guard(); calls.append(url); guard()
        return {'format': 'WEB', 'paragraphs': [{'paragraph': 1, 'page': None, 'text': 'A synthetic public tide table.'}], 'extraction_status': 'TEXT_EXTRACTED', 'warnings': [], 'content_sha256': 'b' * 64, 'final_url': url, 'content_type': 'text/plain'}
    monkeypatch.setattr(module, 'fetch_webpage', fetch)
    row = e.research.import_web(e.nid, e.scope, 'author', {'title': 'Public synthetic table', 'url': 'https://source.example/table', 'confirm_fetch': True}, guard=lambda: None)
    assert calls == ['https://source.example/table'] and row['origin'] == 'EXPLICIT_WEB_FETCH'
    assert e.research.resolve(e.nid, e.scope, 'author', citation(row))['text'] == 'A synthetic public tide table.'
    assert 'content_base64' not in row
