"""Owner-only erased-vector recovery receipts survive source invalidation."""
import pytest

from app.experimental.common import StaleSourceError
from app.experimental.embeddings import EmbeddingService, MockEmbeddingProvider
from app.experimental.store import ExperimentalStore
from test_r3_planning import planning_env
from test_r4_research_library import research, imported


def prepared(e, source, actor='author'):
    service = EmbeddingService(e.store, e.novels, e.chapter_service,
                               provider=MockEmbeddingProvider(), research=e.research)
    index = service.create_index(e.nid, e.scope, actor, {'title': 'Synthetic receipt',
        'entities': [{'entity_type': 'RESEARCH', 'entity_id': source['id']}]})
    service.rebuild(e.nid, e.scope, actor, index['id'], index['version'])
    return service, index


@pytest.mark.parametrize('action', ['delete', 'revoke'])
def test_source_owner_can_read_erased_receipt_after_restart_but_cannot_query(research, action):
    e = research; source = imported(e); service, index = prepared(e, source)
    e.research.transition_source(e.nid, e.scope, 'author', source['id'], source['version'], action, guard=lambda: None)
    reopened = EmbeddingService(ExperimentalStore(e.root, e.backend, e.url), e.novels,
        e.chapter_service, provider=MockEmbeddingProvider(), research=e.research)
    receipts = reopened.records(e.nid, e.scope, index['id'], 'author')
    assert len(receipts) == 1 and receipts[0]['status'] == 'INVALIDATED'
    assert 'vector' not in receipts[0] and 'paragraphs' not in receipts[0]
    assert not any(row['vector'] for row in reopened.list(e.nid, e.scope, reopened.VECTORS))
    with pytest.raises(StaleSourceError):
        reopened.query(e.nid, e.scope, {'index_id': index['id'], 'text': 'synthetic'}, actor='author')
    with pytest.raises(FileNotFoundError): reopened.records(e.nid, e.scope, index['id'], 'other')


def test_former_shared_reader_cannot_inspect_source_owner_tombstone(research):
    e = research; source = imported(e, access='PROJECT'); service, index = prepared(e, source, 'other')
    assert service.records(e.nid, e.scope, index['id'], 'other')
    e.research.transition_source(e.nid, e.scope, 'author', source['id'], source['version'], 'revoke', guard=lambda: None)
    with pytest.raises(FileNotFoundError): service.records(e.nid, e.scope, index['id'], 'other')
    with pytest.raises(FileNotFoundError): service.records(e.nid, e.scope, index['id'], 'author')


def test_receipt_requires_complete_vector_erasure_and_current_feature_authority(research):
    e = research; source = imported(e); service, index = prepared(e, source)
    e.research.transition_source(e.nid, e.scope, 'author', source['id'], source['version'], 'delete', guard=lambda: None)
    with e.store.transaction(e.nid, e.scope) as state:
        next(iter(state['collections'][service.VECTORS].values()))['vector'] = [1.0]
    with pytest.raises(StaleSourceError, match='RECEIPT_UNSAFE'):
        service.records(e.nid, e.scope, index['id'], 'author')
    def disabled(): raise FileNotFoundError('research feature disabled')
    service.research_guard = disabled
    with pytest.raises(FileNotFoundError, match='feature disabled'):
        service.records(e.nid, e.scope, index['id'], 'author')
