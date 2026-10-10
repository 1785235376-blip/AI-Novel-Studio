"""Scoped mixed-index dependency toggles, using unchanged File/real-PG fixtures."""
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.experimental.embeddings import EmbeddingService, MockEmbeddingProvider
from app.experimental.embeddings_api import create_embeddings_router
from app.experimental.flags import require_flag
from test_r3_planning import planning_env
from test_r4_research_library import research, imported

FEATURES = 'visual_embeddings,semantic_import_v2,world_character_engines_v2,temporal_story_graph_v2,research_library_v2'


def mixed_api(e, monkeypatch):
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', FEATURES)
    monkeypatch.delenv('V1_ACCEPTANCE_MODE', raising=False)
    source = imported(e)
    service = EmbeddingService(e.store, e.novels, e.chapter_service, provider=MockEmbeddingProvider(), research=e.research)
    private = service.create_index(e.nid, e.scope, 'author', {'title': 'Private Research Index', 'entities': [{'entity_type': 'RESEARCH', 'entity_id': source['id']}]})
    character = service.create_index(e.nid, e.scope, 'author', {'title': 'Independent Character Index', 'entities': [{'entity_type': 'CHARACTER', 'entity_id': 'alice'}]})
    character = service.rebuild(e.nid, e.scope, 'author', character['id'], character['version'])
    permitted = [True]
    def authorize(nid, token, branch, permission):
        if token != 'valid' or not permitted[0]: raise HTTPException(403, {'code': 'PROJECT_DENIED'})
        return 'author', e.scope
    app = FastAPI(); app.include_router(create_embeddings_router(service, authorize, require_flag))
    return service, private, character, permitted, TestClient(app), f'/novels/{e.nid}/experimental/embeddings', {'X-Session-Token': 'valid'}


def test_research_flag_off_hides_only_dependent_index_and_direct_access_stays_closed(research, monkeypatch):
    e = research; service, private, character, allowed, client, base, headers = mixed_api(e, monkeypatch)
    both = client.get(base + '/indexes', headers=headers)
    assert both.status_code == 200
    assert {r['id'] for r in both.json()['items']} == {private['id'], character['id']}
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'visual_embeddings')
    independent = client.get(base + '/indexes', headers=headers)
    assert independent.status_code == 200 and independent.headers['Cache-Control'] == 'no-store'
    assert [r['id'] for r in independent.json()['items']] == [character['id']]
    assert private['title'] not in independent.text and private['id'] not in independent.text
    assert client.get(base + '/sources', headers=headers).status_code == 200
    result = client.post(base + '/query', headers=headers, json={'index_id': character['id'], 'text': 'Alice'})
    assert result.status_code == 200 and result.json()['items'][0]['entity']['entity_id'] == 'alice'
    assert client.get(base + f"/indexes/{private['id']}/records", headers=headers).status_code == 404
    for action in ['rebuild', 'invalidate', 'remove', 'cancel']:
        assert client.post(base + f"/indexes/{private['id']}/{action}", headers=headers, json={'expected_version': private['version']}).status_code == 404
    assert client.put(base + f"/indexes/{private['id']}", headers=headers, json={'title': 'Must not edit', 'entities': private['entities'], 'expected_version': private['version']}).status_code == 404
    assert client.post(base + '/query', headers=headers, json={'index_id': private['id'], 'text': 'Reference'}).status_code == 404
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', FEATURES)
    restored = client.get(base + '/indexes', headers=headers)
    assert restored.status_code == 200 and {r['id'] for r in restored.json()['items']} == {private['id'], character['id']}
    assert service.get(e.nid, e.scope, service.INDEXES, private['id'])['version'] == private['version']


@pytest.mark.parametrize('when', ['during_source_read', 'after_stale_check'])
def test_research_toggle_during_stale_check_cannot_hide_independent_index(research, monkeypatch, when):
    e = research; service, private, character, allowed, client, base, headers = mixed_api(e, monkeypatch)
    ready = service.rebuild(e.nid, e.scope, 'author', private['id'], private['version'])
    if when == 'during_source_read':
        original = service._source
        def toggle(nid, scope, ref, actor=None):
            if ref['entity_type'] == 'RESEARCH': monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'visual_embeddings')
            return original(nid, scope, ref, actor)
        monkeypatch.setattr(service, '_source', toggle)
    else:
        original = service._index_stale
        def toggle(nid, scope, row, actor=None):
            result = original(nid, scope, row, actor)
            if row['id'] == private['id']: monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'visual_embeddings')
            return result
        monkeypatch.setattr(service, '_index_stale', toggle)
    response = client.get(base + '/indexes', headers=headers)
    assert response.status_code == 200 and [r['id'] for r in response.json()['items']] == [character['id']]
    assert ready['id'] not in response.text


@pytest.mark.parametrize('status,detail', [(401, {'code': 'SESSION_REQUIRED'}), (403, {'code': 'PROJECT_DENIED'}),
    (404, {'code': 'PROJECT_NOT_FOUND'}), (404, {'code': 'EXPERIMENTAL_FEATURE_DISABLED', 'feature': 'visual_embeddings'})])
def test_index_listing_does_not_swallow_other_authority_failures(research, monkeypatch, status, detail):
    service, private, character, allowed, client, base, headers = mixed_api(research, monkeypatch)
    def deny(): raise HTTPException(status, detail)
    service.research_guard = deny
    response = client.get(base + '/indexes', headers=headers)
    assert response.status_code == status and response.json()['detail'] == detail
    assert character['title'] not in response.text and private['title'] not in response.text


def test_global_project_denial_remains_authoritative_before_and_after_filtered_list(research, monkeypatch):
    service, private, character, allowed, client, base, headers = mixed_api(research, monkeypatch)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'visual_embeddings')
    assert client.get(base + '/indexes').status_code == 403
    original = service.indexes
    def revoke(*args):
        value = original(*args); allowed[0] = False; return value
    monkeypatch.setattr(service, 'indexes', revoke)
    response = client.get(base + '/indexes', headers=headers)
    assert response.status_code == 403 and character['title'] not in response.text


@pytest.mark.parametrize('mode', ['default_off', 'v1_acceptance'])
def test_global_disabled_and_v1_modes_still_reject_all_embedding_reads(research, monkeypatch, mode):
    service, private, character, allowed, client, base, headers = mixed_api(research, monkeypatch)
    if mode == 'default_off': monkeypatch.delenv('EXPERIMENTAL_FEATURES')
    else: monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    for path in ['/status', '/providers', '/sources', '/indexes', f"/indexes/{character['id']}/records"]:
        response = client.get(base + path, headers=headers)
        assert response.status_code == 404 and response.json()['detail']['feature'] == 'visual_embeddings'
