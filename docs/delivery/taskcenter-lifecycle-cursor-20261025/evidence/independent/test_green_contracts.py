"""Implementation-neutral acceptance assertions: expected baseline 2 red, 3 green."""
import pytest
from app.experimental.store import ExperimentalStore
from app.creative.project_store import CreativeProjectStore
from app.experimental.imports import JOBS
from test_studio_asset_query import rig
from test_taskcenter_query_backend import mounted, get
SCOPE = {'mode': 'local', 'novel_id': 'book'}

def test_nested_independent_writer_cannot_be_silently_lost(tmp_path):
    a, b = ExperimentalStore(tmp_path), ExperimentalStore(tmp_path)
    inner_committed = False
    rejected = []
    try:
        with a.transaction('book', SCOPE) as outer:
            outer['collections']['outer'] = {'x': {'v': 1}}
            try:
                with b.transaction('book', SCOPE) as inner:
                    inner['collections']['inner'] = {'x': {'v': 2}}
                inner_committed = True
            except ValueError as exc:
                rejected.append(str(exc))
    except ValueError as exc:
        rejected.append(str(exc))
    final = b.read('book', SCOPE)['collections']
    assert rejected or not inner_committed or 'inner' in final, 'Committed inner write silently lost'
    if inner_committed:
        assert 'inner' in final, 'CAS rejection must preserve independently committed inner state'

def test_source_lease_never_accepts_cross_instance_mutation_silently(tmp_path):
    (tmp_path / 'novels' / 'book').mkdir(parents=True)
    a, b = ExperimentalStore(tmp_path), ExperimentalStore(tmp_path)
    creative = CreativeProjectStore(a)
    creative.incarnation('book')
    rejected = False
    try:
        with creative.source_lease('book', SCOPE):
            with b.transaction('book', SCOPE) as doc:
                doc['collections']['inner'] = {'x': {'v': 2}}
    except ValueError:
        rejected = True
    assert rejected, 'Read lease silently admitted another store instance committing'

def test_noop_source_lease_and_rollback_make_zero_scope_atomic_writes(tmp_path, monkeypatch):
    import app.experimental.store as module
    (tmp_path / 'novels' / 'book').mkdir(parents=True)
    store = ExperimentalStore(tmp_path)
    creative = CreativeProjectStore(store)
    creative.incarnation('book')
    calls = []
    original = module.atomic_write
    monkeypatch.setattr(module, 'atomic_write', lambda *args, **kw: (calls.append(str(args[0])), original(*args, **kw))[1])
    for existing in (False, True):
        if existing:
            with store.transaction('book', SCOPE) as doc:
                doc['collections']['existing'] = {'x': {'v': 1}}
            calls.clear()
        before = store.path('book', SCOPE).read_bytes() if existing else None
        with store.transaction('book', SCOPE):
            pass
        with store.transaction('book', SCOPE) as doc:
            doc['collections']['transient'] = {}
            del doc['collections']['transient']
        with creative.existing_owner_only(), creative.source_lease('book', SCOPE):
            pass
        with pytest.raises(RuntimeError):
            with store.transaction('book', SCOPE) as doc:
                doc['collections']['rollback'] = {}
                raise RuntimeError('rollback')
        assert calls == []
        assert (store.path('book', SCOPE).read_bytes() if store.path('book', SCOPE).exists() else None) == before

def test_unselected_collection_tail_aba_leaves_semantic_projection_identical(mounted):
    params = {'authority': 'semantic_import', 'limit': 100}
    original = get(mounted, params).json()
    for rows in ({'hidden': {'status': 'FAILED'}}, {}, {'hidden': {'status': 'FAILED'}}):
        with mounted.store.transaction(mounted.rig.nid, mounted.rig.scope) as doc:
            doc['collections']['unselected_private_collection'] = rows
        assert get(mounted, params).json() == original

def test_selected_tail_changes_full_projection_even_when_first_page_equal(mounted):
    selected = {'authority': 'semantic_import'}
    page = get(mounted, {**selected, 'limit': 1}).json()
    full = get(mounted, {**selected, 'limit': 100}).json()
    with mounted.store.transaction(mounted.rig.nid, mounted.rig.scope) as doc:
        doc['collections'][JOBS]['job-002']['version'] += 1
    assert get(mounted, {**selected, 'limit': 1}).json() == page
    assert get(mounted, {**selected, 'limit': 100}).json() != full
