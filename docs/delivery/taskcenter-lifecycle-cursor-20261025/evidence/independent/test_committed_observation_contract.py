"""Original-owner contract tests, no monkeypatched lifecycle evidence."""
import pytest
from app.experimental.store import ExperimentalStore, canonical
from app.creative.project_store import CreativeProjectStore
from app.experimental.imports import JOBS
SCOPE = {'mode': 'local', 'novel_id': 'book'}

def seeded(tmp_path):
    (tmp_path / 'novels' / 'book').mkdir(parents=True)
    store = ExperimentalStore(tmp_path)
    identity = CreativeProjectStore(store).incarnation('book')
    with store.transaction('book', SCOPE) as doc:
        doc['collections'][JOBS] = {'one': {'id': 'one', 'novel_id': 'book', 'scope': SCOPE, 'version': 1, 'status': 'QUEUED'}}
    return store, identity

def capture(store):
    return store.capture_committed_collection('book', SCOPE, collection=JOBS)

def test_original_committed_observation_binding_and_aba(tmp_path):
    store, identity = seeded(tmp_path)
    a = capture(store)
    assert a['project_identity'] == identity
    assert a['document_incarnation'] and a['row_lifecycles']['one']
    for version in (2, 1):
        with store.transaction('book', SCOPE) as doc:
            doc['collections'][JOBS]['one']['version'] = version
    c = capture(store)
    assert a['rows'] == c['rows']
    assert a['row_lifecycles']['one'] != c['row_lifecycles']['one']

def test_unselected_collection_activity_does_not_change_selected_observation(tmp_path):
    store, _ = seeded(tmp_path)
    a = capture(store)
    for rows in ({'h': {'v': 1}}, {}, {'h': {'v': 1}}):
        with store.transaction('book', SCOPE) as doc:
            doc['collections']['private_unselected'] = rows
        assert capture(store) == a

def test_legacy_doc_cannot_bind_merely_because_current_marker_exists(tmp_path):
    (tmp_path / 'novels' / 'book').mkdir(parents=True)
    store = ExperimentalStore(tmp_path)
    CreativeProjectStore(store).incarnation('book')
    path = store.path('book', SCOPE)
    path.parent.mkdir(parents=True)
    path.write_text(canonical(store.empty('book', SCOPE)))
    before = path.read_bytes()
    with pytest.raises(ValueError, match='EXPERIMENTAL_OBSERVATION_UNSUPPORTED'):
        capture(store)
    assert path.read_bytes() == before
    with store.transaction('book', SCOPE) as doc:
        doc['collections'][JOBS] = {'old': {'id': 'old', 'version': 1}}
    after = path.read_bytes()
    with pytest.raises(ValueError, match='EXPERIMENTAL_OBSERVATION_UNSUPPORTED'):
        capture(store)
    assert path.read_bytes() == after

def test_active_transaction_never_exports_uncommitted_rows(tmp_path):
    store, _ = seeded(tmp_path)
    committed = capture(store)
    other = ExperimentalStore(tmp_path)
    with pytest.raises(RuntimeError, match='rollback'):
        with store.transaction('book', SCOPE) as doc:
            doc['collections'][JOBS]['one']['version'] = 999
            for target in (store, other):
                try:
                    observed = capture(target)
                except ValueError as exc:
                    assert str(exc) == 'EXPERIMENTAL_OBSERVATION_UNSUPPORTED'
                else:
                    assert observed == committed
            raise RuntimeError('rollback')
    assert capture(store) == committed

def test_committed_observation_and_noop_do_not_write(tmp_path):
    store, _ = seeded(tmp_path)
    path = store.path('book', SCOPE)
    a, before = capture(store), path.read_bytes()
    with store.transaction('book', SCOPE):
        pass
    creative = CreativeProjectStore(store)
    with creative.existing_owner_only(), creative.source_lease('book', SCOPE):
        pass
    assert capture(store) == a and path.read_bytes() == before
