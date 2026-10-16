"""Continuation regression: real persistent CRUD, history and vector authority.

Fixtures contain only synthetic references. PostgreSQL uses the inherited real
backend fixture without changing its availability gate.
"""
import base64
import copy
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.experimental.common import StaleSourceError
from app.experimental.embeddings import EmbeddingService, MockEmbeddingProvider
from app.experimental.embeddings_api import create_embeddings_router
from app.experimental.research_library import ResearchLibraryService
from app.experimental.research_library_api import create_research_library_router
from app.experimental.store import ExperimentalStore
from app.services.v1_capability_service import CapabilityVersionConflict
from test_r3_planning import planning_env
from test_r4_research_library import research, imported, payload, citation, note


def replace(e, row, text='Replacement synthetic archive.', **kwargs):
    return e.research.replace_file(e.nid, e.scope, 'author', row['id'],
        {**payload(text=text), 'expected_version': row['version'], **kwargs}, guard=lambda: None)


def embeddings(e, provider=None):
    return EmbeddingService(e.store, e.novels, e.chapter_service, provider=provider, research=e.research)


def index(e, service, source):
    return service.create_index(e.nid, e.scope, 'author', {'title': 'Private research vectors',
        'entities': [{'entity_type': 'RESEARCH', 'entity_id': source['id']}]})


def test_source_replace_full_history_owner_restore_private_and_restart(research):
    e = research; row = imported(e, access='PROJECT'); before = copy.deepcopy(e.rows)
    revised = replace(e, row, access='PROJECT')
    assert revised['version'] == 2 and revised['content_sha256'] != row['content_sha256']
    history = e.research.source_history(e.nid, e.scope, 'author', row['id'])
    assert [r['version'] for r in history['items']] == [1, 2]
    assert 'content_base64' not in str(history) and 'paragraphs' not in str(history)
    with pytest.raises(FileNotFoundError): e.research.source_history(e.nid, e.scope, 'other', row['id'])
    with pytest.raises(CapabilityVersionConflict): replace(e, row)
    with pytest.raises(StaleSourceError): e.research.resolve(e.nid, e.scope, 'author', citation(row))
    revoked = e.research.transition_source(e.nid, e.scope, 'author', row['id'], 2, 'revoke', guard=lambda: None)
    assert e.research.archived_sources(e.nid, e.scope, 'other')['items'] == []
    reopened = ResearchLibraryService(ExperimentalStore(e.root, e.backend, e.url), e.novels, e.chapter_service)
    assert reopened.archived_sources(e.nid, e.scope, 'author')['items'][0]['id'] == row['id']
    restored = reopened.restore_source(e.nid, e.scope, 'author', row['id'], {'expected_version': revoked['version'], 'restore_version': 1}, guard=lambda: None)
    assert restored['version'] == 4 and restored['access'] == 'PRIVATE' and restored['status'] == 'ACTIVE'
    assert restored['content_sha256'] == row['content_sha256'] and restored['restored_from_version'] == 1
    assert reopened.original(e.nid, e.scope, 'author', row['id'])[0] == base64.b64decode(payload()['content_base64'])
    assert reopened.sources(e.nid, e.scope, 'other')['items'] == []
    assert e.rows == before and reopened.resolve(e.nid, e.scope, 'author', citation(restored))['source_digest'] == restored['content_sha256']


def test_notes_real_update_history_delete_and_citation_repair(research):
    e = research; row = imported(e); saved = note(e, citation(row))
    body = {'title': 'Edited note', 'text': 'An original annotation.', 'citations': [citation(row)], 'expected_version': 1}
    edited = e.research.edit_note(e.nid, e.scope, 'author', saved['id'], body, guard=lambda: None)
    assert edited['version'] == 2 and 'history' not in edited
    assert len(e.research.note_history(e.nid, e.scope, 'author', saved['id'])['items']) == 2
    with pytest.raises(FileNotFoundError): e.research.edit_note(e.nid, e.scope, 'other', saved['id'], body, guard=lambda: None)
    with pytest.raises(CapabilityVersionConflict): e.research.edit_note(e.nid, e.scope, 'author', saved['id'], body, guard=lambda: None)
    updated = replace(e, row)
    assert not e.research.notes(e.nid, e.scope, 'author')['items']
    assert not e.research.note_history(e.nid, e.scope, 'author', saved['id'])['items']
    repaired = e.research.edit_note(e.nid, e.scope, 'author', saved['id'], {**body, 'expected_version': 2, 'citations': [citation(updated)]}, guard=lambda: None)
    assert repaired['version'] == 3 and repaired['research_stale'] is False
    assert e.research.notes(e.nid, e.scope, 'author')['total'] == 1
    e.research.delete_note(e.nid, e.scope, 'author', saved['id'], 3, guard=lambda: None)
    assert not e.research.notes(e.nid, e.scope, 'author')['items']


def test_quota_or_permission_failure_rolls_back_history_and_contents(research, monkeypatch):
    e = research; row = imported(e)
    from app.experimental import research_library as module
    previous = e.store.read(e.nid, e.scope)
    monkeypatch.setattr(module, 'MAX_STORED_BYTES', 1)
    with pytest.raises(ValueError, match='STORAGE_LIMIT'): replace(e, row)
    assert e.store.read(e.nid, e.scope) == previous
    monkeypatch.setattr(module, 'MAX_STORED_BYTES', 32 * 1024 * 1024)
    calls = [0]
    def revoke():
        calls[0] += 1
        if calls[0] == 3: raise HTTPException(403, 'revoked')
    with pytest.raises(HTTPException):
        e.research.replace_file(e.nid, e.scope, 'author', row['id'], {**payload(text='new'), 'expected_version': 1}, guard=revoke)
    assert e.store.read(e.nid, e.scope) == previous


def test_research_vector_rebuild_query_atomic_source_revoke_and_author_isolation(research):
    e = research; source = imported(e); service = embeddings(e, MockEmbeddingProvider()); row = index(e, service, source)
    ready = service.rebuild(e.nid, e.scope, 'author', row['id'], 1)
    result = service.query(e.nid, e.scope, {'index_id': row['id'], 'text': 'tide'}, actor='author')
    assert result['items'][0]['source_digest'] == source['content_sha256']
    assert result['items'][0]['verification'] == 'MOCK_ONLY' and result['lexical_fallback'] is False
    assert service.indexes(e.nid, e.scope, 'other') == []
    for callback in (lambda: service.query(e.nid, e.scope, {'index_id': row['id'], 'text': 'tide'}, actor='other'),
                     lambda: service.records(e.nid, e.scope, row['id'], 'other')):
        with pytest.raises(FileNotFoundError): callback()
    e.research.transition_source(e.nid, e.scope, 'author', source['id'], 1, 'delete', guard=lambda: None)
    assert service.owned_index(e.nid, e.scope, row['id'], 'author')['status'] == 'INVALIDATED'
    assert all(not v['vector'] for v in service.list(e.nid, e.scope, service.VECTORS))
    with pytest.raises(StaleSourceError): service.query(e.nid, e.scope, {'index_id': row['id'], 'text': 'tide'}, actor='author')
    assert service.records(e.nid, e.scope, row['id'], 'author')[0]['status'] == 'INVALIDATED'


def test_research_invalidation_fences_late_embedding_and_restart_requires_explicit_rebuild(research):
    e = research; source = imported(e); started, finish = Event(), Event()
    class Slow(MockEmbeddingProvider):
        def embed(self, inputs):
            started.set(); assert finish.wait(5)
            return super().embed(inputs)
    service = embeddings(e, Slow()); row = index(e, service, source)
    with ThreadPoolExecutor() as pool:
        pending = pool.submit(service.rebuild, e.nid, e.scope, 'author', row['id'], 1)
        assert started.wait(5)
        replace(e, source)
        finish.set()
        assert pending.result(timeout=10)['status'] == 'INVALIDATED'
    assert service.records(e.nid, e.scope, row['id'], 'author') == []
    reopened = EmbeddingService(ExperimentalStore(e.root, e.backend, e.url), e.novels, e.chapter_service, provider=MockEmbeddingProvider(), research=e.research)
    persisted = reopened.owned_index(e.nid, e.scope, row['id'], 'author')
    assert persisted['status'] == 'INVALIDATED'
    ready = reopened.rebuild(e.nid, e.scope, 'author', row['id'], persisted['version'])
    assert ready['status'] == 'ACTIVE'


def test_vector_index_edit_and_cancel_keep_cas_and_no_automatic_replay(research):
    e = research; source = imported(e); service = embeddings(e, MockEmbeddingProvider()); row = index(e, service, source)
    ready = service.rebuild(e.nid, e.scope, 'author', row['id'], 1)
    updated = service.edit_index(e.nid, e.scope, 'author', row['id'], {'title': 'Revised', 'entities': row['entities'], 'expected_version': ready['version']})
    assert updated['status'] == 'INVALIDATED' and updated['history'][-1]['title'] == row['title']
    assert all(not v['vector'] for v in service.list(e.nid, e.scope, service.VECTORS))
    with pytest.raises(CapabilityVersionConflict): service.edit_index(e.nid, e.scope, 'author', row['id'], {'title': 'Lost update', 'entities': row['entities'], 'expected_version': 1})
    with e.store.transaction(e.nid, e.scope) as doc:
        doc['collections'][service.INDEXES][row['id']].update(status='BUILDING', execution_token='old-process')
    cancelled = service.transition(e.nid, e.scope, 'author', row['id'], 'cancel', updated['version'])
    assert cancelled['status'] == 'INVALIDATED' and cancelled['execution_token'] is None


def test_mounted_new_crud_routes_require_flags_and_current_authority(research):
    e = research; flags = {'visual_embeddings', 'research_library_v2'}; allowed = [True]
    def flag(name):
        if name not in flags: raise HTTPException(404, 'disabled')
    def authorize(nid, token, branch, permission):
        if token != 'valid' or not allowed[0]: raise HTTPException(403, 'denied')
        return 'author', e.scope
    service = embeddings(e, MockEmbeddingProvider())
    app = FastAPI(); app.include_router(create_research_library_router(e.research, authorize, flag)); app.include_router(create_embeddings_router(service, authorize, flag))
    client = TestClient(app); base = f'/novels/{e.nid}/experimental'; headers = {'X-Session-Token': 'valid'}
    row = client.post(base + '/research-library/sources/import', json=payload(), headers=headers).json()
    source_url = base + '/research-library/sources/' + row['id']
    assert client.put(source_url + '/file', json={**payload('new'), 'expected_version': 1}, headers=headers).status_code == 200
    assert client.get(source_url + '/history', headers=headers).headers['cache-control'] == 'no-store'
    assert client.post(source_url + '/restore', json={'expected_version': 2, 'restore_version': 1}, headers=headers).json()['version'] == 3
    catalog = client.get(base + '/embeddings/sources', headers=headers).json()
    assert any(r['entity']['entity_type'] == 'RESEARCH' and r['entity']['entity_id'] == row['id'] for r in catalog['items'])
    response = client.post(base + '/embeddings/indexes', headers=headers, json={'title': 'Reference', 'entities': [{'entity_type': 'RESEARCH', 'entity_id': row['id']}]})
    assert response.status_code == 201, response.text
    created = response.json()
    flags.remove('research_library_v2')
    assert client.post(base + '/embeddings/indexes/' + created['id'] + '/rebuild', headers=headers, json={'expected_version': 1}).status_code == 404
    assert client.get(base + '/embeddings/sources', headers=headers).json()['unavailable'][-1] == 'RESEARCH_FEATURE_DISABLED'
    flags.clear()
    assert client.get(base + '/embeddings/indexes', headers=headers).status_code == 404
    allowed[0] = False
    assert client.get(source_url + '/history', headers=headers).status_code in {403, 404}


def test_revision_quota_never_prevents_revocation_and_archived_bytes_stay_owner_only(research, monkeypatch):
    e = research; row = imported(e)
    from app.experimental import research_library as module
    monkeypatch.setattr(module, 'MAX_SOURCE_REVISIONS', 0)
    monkeypatch.setattr(module, 'MAX_STORED_BYTES', 1)
    revoked = e.research.transition_source(e.nid, e.scope, 'author', row['id'], 1, 'revoke', guard=lambda: None)
    assert revoked['status'] == 'REVOKED'
    assert e.research.historical_original(e.nid, e.scope, 'author', row['id'], 1)[0] == base64.b64decode(payload()['content_base64'])
    with pytest.raises(FileNotFoundError): e.research.historical_original(e.nid, e.scope, 'other', row['id'], 1)


def test_citation_repair_queue_only_returns_authors_own_stale_reference_work(research):
    e = research; own = imported(e); saved = note(e, citation(own)); replace(e, own)
    recoverable = e.research.note_repairs(e.nid, e.scope, 'author')['items']
    assert len(recoverable) == 1 and recoverable[0]['id'] == saved['id']
    assert recoverable[0]['citations'] == [] and recoverable[0]['text'] == saved['text']
    shared = e.research.import_file(e.nid, e.scope, 'other', payload(access='PROJECT'), guard=lambda: None)
    note(e, citation(shared))
    e.research.replace_file(e.nid, e.scope, 'other', shared['id'], {**payload('changed', access='PROJECT'), 'expected_version': 1}, guard=lambda: None)
    assert len(e.research.note_repairs(e.nid, e.scope, 'author')['items']) == 1


def test_stale_vector_query_never_returns_late_private_matches_after_revoke(research):
    e = research; source = imported(e); service = embeddings(e, MockEmbeddingProvider()); row = index(e, service, source)
    service.rebuild(e.nid, e.scope, 'author', row['id'], 1)
    class Revoking(MockEmbeddingProvider):
        def embed(self, inputs):
            e.research.transition_source(e.nid, e.scope, 'author', source['id'], 1, 'revoke', guard=lambda: None)
            return super().embed(inputs)
    service.provider = Revoking()
    with pytest.raises(StaleSourceError): service.query(e.nid, e.scope, {'index_id': row['id'], 'text': 'Synthetic'}, actor='author')
    assert not any(r['vector'] for r in service.list(e.nid, e.scope, service.VECTORS))
