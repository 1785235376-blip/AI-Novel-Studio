"""Synthetic original-owner integration: budgets do not replace snapshots/locks."""
from copy import deepcopy
import json

import pytest

from app.creative.asset_usage_budget import (
    UsageBudgetError, current_usage_budget, usage_read_budget,
)
from app.creative.project_store import CreativeProjectStore
from app.experimental.store import ExperimentalStore, LIFECYCLE, OBSERVED_COLLECTION
from app.repositories.file.identity import FileIdentityRepository
from app.repositories.file.scope import FileScopeRepository, FileAuthorizationRepository
from app.repositories.file import mutation_coordinator as coordinator
from app.services.export_job_service import ExportJobService
from app.storage import atomic_write

pytestmark = pytest.mark.file_backend_only
NID = 'safety-book'
SCOPE = {'mode': 'local', 'novel_id': NID}


@pytest.fixture
def store(tmp_path):
    original = ExperimentalStore(tmp_path)
    (tmp_path / 'novels' / NID).mkdir(parents=True)
    CreativeProjectStore(original).incarnation(NID)
    with original.transaction(NID, SCOPE) as document:
        document['collections'][OBSERVED_COLLECTION] = {
            'job': {'id': 'job', 'status': 'QUEUED', 'novel_id': NID, 'scope': SCOPE}}
    return original


@pytest.fixture(params=['store', 'identity', 'scope', 'grant', 'export'])
def reader(request, tmp_path):
    kind = request.param
    if kind == 'store':
        owner = ExperimentalStore(tmp_path)
        path = owner.path(NID, SCOPE)
        path.parent.mkdir(parents=True)
        read = lambda: owner._file_read(NID, SCOPE)
        document = owner.empty(NID, SCOPE)
        key = LIFECYCLE
    elif kind == 'export':
        owner = ExportJobService(tmp_path, lambda *_: pytest.fail('unexpected dispatch'))
        path, read, document, key = owner.path, owner._read_document, {}, owner._LIFECYCLE
    else:
        owner = {'identity': FileIdentityRepository, 'scope': FileScopeRepository,
                 'grant': FileAuthorizationRepository}[kind](tmp_path)
        path, read, document = owner.path, owner._read, owner._read()
        key = {'identity': '_identity_lifecycle_v1', 'scope': '_scope_lifecycle_v1',
               'grant': '_grant_lifecycle_v1'}[kind]
    yield path, read, document, key
    if kind == 'export':
        owner._pool.shutdown(wait=True)


def test_snapshot_keeps_exact_bytes_and_every_cas_reread_is_charged(store):
    path = store.path(NID, SCOPE)
    document = store.read(NID, SCOPE)
    physical = (' \n' + json.dumps(document, ensure_ascii=False, indent=3) + '\n\t').encode()
    atomic_write(path, physical.decode())
    with usage_read_budget(fresh=True) as budget:
        raw, decoded = store._file_snapshot(NID, SCOPE)
        assert raw == physical and decoded == document
        assert budget.reads == 1 and budget.read_bytes == len(physical)
        with store.transaction(NID, SCOPE):
            pass
        assert budget.reads == 3 and budget.read_bytes == 3 * len(physical)
    assert current_usage_budget() is None
    assert path.read_bytes() == physical


def test_committed_capture_never_uses_active_buffer_and_read_failure_releases_it(store):
    committed = store.capture_committed_collection(NID, SCOPE)
    with usage_read_budget(fresh=True) as budget:
        with store.transaction(NID, SCOPE) as document:
            document['collections'][OBSERVED_COLLECTION]['job']['status'] = 'RUNNING'
            assert store.capture_committed_collection(NID, SCOPE) == committed
        assert budget.reads >= 4  # snapshot, capture, project marker, physical CAS
    physical = store.path(NID, SCOPE).read_bytes()
    with usage_read_budget(fresh=True) as budget:
        budget.MAX_READ_BYTES = len(physical)
        with pytest.raises(UsageBudgetError):
            with store.transaction(NID, SCOPE) as document:
                document['collections'][OBSERVED_COLLECTION]['job']['status'] = 'FAILED'
        assert budget.reads == 2 and budget.read_bytes == len(physical)
        assert store._local.active == {}
    assert current_usage_budget() is None
    assert store.path(NID, SCOPE).read_bytes() == physical
    with store.transaction(NID, SCOPE) as document:
        document['collections'][OBSERVED_COLLECTION]['job']['status'] = 'SUCCEEDED'
    assert store.capture_committed_collection(NID, SCOPE)['rows'][0]['status'] == 'SUCCEEDED'


@pytest.mark.parametrize('budgeted', [False, True])
def test_all_original_readers_reject_duplicate_keys(reader, budgeted):
    path, read, document, _ = reader
    text = json.dumps(document)
    payload = ('{"duplicate": 1, "duplicate": 2,' + text[1:]) if document else '{"duplicate":1,"duplicate":2}'
    path.write_text(payload, encoding='utf-8')
    with usage_read_budget(budgeted, fresh=True) as budget:
        with pytest.raises(ValueError, match='duplicate'):
            read()
        if budgeted:
            assert budget.read_bytes == len(payload.encode()) and budget.reads == 1


def test_corrupt_lifecycle_never_becomes_an_empty_success(reader):
    path, read, document, key = reader
    document[key] = None
    path.write_text(json.dumps(document), encoding='utf-8')
    before = path.read_bytes()
    with usage_read_budget(fresh=True) as budget:
        with pytest.raises(ValueError):
            read()
        assert budget.read_bytes == len(before)
    assert path.read_bytes() == before


@pytest.mark.parametrize('shape,payload', [
    ('depth', b'[' * 5 + b'0' + b']' * 5),
    ('string', b'"' + b'x' * 33 + b'"'),
    ('scalar', b'1' * 17),
    ('tokens', b'[0,0,0,0,0,0,0,0,0,0]'),
    ('size', b' ' * 129),
])
def test_predecode_limits_apply_to_every_merged_reader(reader, monkeypatch, shape, payload):
    path, read, _, _ = reader
    path.write_bytes(payload)
    with usage_read_budget(fresh=True) as budget:
        budget.MAX_JSON_DEPTH = 4
        budget.MAX_JSON_STRING_BYTES = 32
        budget.MAX_JSON_NUMBER_BYTES = 16
        budget.MAX_JSON_TOKENS = 10
        budget.MAX_SCOPE_BYTES = 128
        with monkeypatch.context() as patch:
            patch.setattr(json, 'loads', lambda *_a, **_k: pytest.fail('decoder before admission'))
            with pytest.raises(UsageBudgetError):
                read()
        assert budget.read_bytes == (0 if shape == 'size' else len(payload))
        assert budget.json_documents == 0


@pytest.mark.parametrize('fault', ['grow', 'replace', 'disappear'])
def test_snapshot_read_fences_preopen_change_without_empty_fallback(store, monkeypatch, fault):
    from app.creative import asset_usage_budget as module
    path = store.path(NID, SCOPE)
    before = path.read_bytes()
    fired = []
    def change(stage, target):
        if stage != 'before_open' or target != path or fired:
            return
        fired.append(True)
        if fault == 'grow':
            with path.open('ab') as stream:
                stream.write(b' ')
        elif fault == 'disappear':
            path.unlink()
        else:
            replacement = path.with_suffix('.replacement')
            replacement.write_bytes(before)
            replacement.replace(path)
    monkeypatch.setattr(module, '_read_checkpoint', change)
    with usage_read_budget(fresh=True) as budget:
        with pytest.raises(UsageBudgetError):
            store._file_snapshot(NID, SCOPE)
        assert fired and budget.reads == 1 and budget.read_bytes == 0


def test_snapshot_short_read_is_charged_and_handle_is_released(store, monkeypatch):
    from app.creative import asset_usage_budget as module
    original = module._open_read
    handles = []
    class ShortRead:
        def __init__(self, handle):
            self.handle, self.calls = handle, 0
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return self.handle.__exit__(*args)
        def fileno(self):
            return self.handle.fileno()
        def read(self, count):
            self.calls += 1
            return self.handle.read(min(count, 7)) if self.calls == 1 else b''
    def short(path):
        handle = original(path)
        handles.append(handle)
        return ShortRead(handle)
    with monkeypatch.context() as patch:
        patch.setattr(module, '_open_read', short)
        with usage_read_budget(fresh=True) as budget:
            with pytest.raises(UsageBudgetError):
                store._file_snapshot(NID, SCOPE)
            assert budget.read_bytes == 7 and budget.json_documents == 0
    assert handles and all(handle.closed for handle in handles)
    with store.transaction(NID, SCOPE):
        pass


def test_strict_committed_reads_preserve_facilities_and_owner_aba(store):
    first = store.capture_committed_collection(NID, SCOPE)
    before = {str(p.relative_to(store.root)): (p.read_bytes() if p.is_file() else None)
              for p in store.root.rglob('*')}
    locks = dict(coordinator._locks)
    with usage_read_budget(fresh=True), coordinator.existing_coordination_only():
        assert store.capture_committed_collection(NID, SCOPE) == first
        with store.transaction(NID, SCOPE):
            pass
    after = {str(p.relative_to(store.root)): (p.read_bytes() if p.is_file() else None)
             for p in store.root.rglob('*')}
    assert before == after and coordinator._locks == locks
    assert not coordinator.strict_coordination_active() and current_usage_budget() is None
    assert not getattr(coordinator._thread_state, 'depths', {})
    for status in ['RUNNING', 'QUEUED']:
        with store.transaction(NID, SCOPE) as document:
            document['collections'][OBSERVED_COLLECTION]['job']['status'] = status
    with usage_read_budget(fresh=True), coordinator.existing_coordination_only():
        latest = store.capture_committed_collection(NID, SCOPE)
    assert latest['rows'] == first['rows']
    assert latest['row_lifecycles'] != first['row_lifecycles']


def test_missing_strict_facilities_refuse_without_budget_or_registry_leak(tmp_path):
    store = ExperimentalStore(tmp_path)
    locks = dict(coordinator._locks)
    before = list(tmp_path.iterdir())
    with pytest.raises(coordinator.ReadOnlyCoordinationUnavailable):
        with usage_read_budget(fresh=True), coordinator.existing_coordination_only():
            store.read(NID, SCOPE)
    assert list(tmp_path.iterdir()) == before and coordinator._locks == locks
    assert current_usage_budget() is None and not coordinator.strict_coordination_active()
    assert not getattr(coordinator._thread_state, 'depths', {})
    assert store.read(NID, SCOPE) == store.empty(NID, SCOPE)
    assert (tmp_path / '.workspace-mutation-locks').is_dir()


def test_export_retains_legacy_corrupt_fallback_and_hidden_metadata(tmp_path):
    owner = ExportJobService(tmp_path, lambda *_: pytest.fail('unexpected dispatch'))
    try:
        owner.path.write_text('{malformed', encoding='utf-8')
        with usage_read_budget(fresh=True) as budget:
            assert owner._read_document() == {}
            assert budget.read_bytes == len(b'{malformed')
        owner.path.unlink()
        owner._write({'job': {'id': 'job', 'status': 'succeeded'}})
        original = deepcopy(owner._read())
        with usage_read_budget(fresh=True) as budget:
            first = owner.binding_observation(['job'])
            assert owner._read() == original
            assert owner.revalidate_binding(['job'], first)
            assert budget.reads == 3
            assert budget.read_bytes == 3 * owner.path.stat().st_size
        assert owner._LIFECYCLE not in original
    finally:
        owner._pool.shutdown(wait=True)
