"""Final-guard error combination contracts for the shared experimental store."""
from copy import deepcopy
from contextlib import contextmanager
import pytest
from app.experimental.store import ExperimentalStore

NID = 'independent-guard-exceptions'
SCOPE = {'mode': 'local', 'novel_id': NID}

class BodyError(RuntimeError):
    pass

class GuardError(RuntimeError):
    pass

def _pg_store(tmp_path, monkeypatch, events):
    store = ExperimentalStore(tmp_path, backend='postgres', database_url='synthetic-no-connection')
    durable = deepcopy(store.empty(NID, SCOPE))
    class Connection:
        def __enter__(self):
            self.pending = None
            events.append('connection_enter')
            return self
        def __exit__(self, typ, exc, tb):
            events.append('rollback' if typ else 'commit')
            if typ is None and self.pending is not None:
                durable.update(self.pending)
            return False
        def execute(self, sql, params):
            if sql.startswith('UPDATE '):
                self.pending = deepcopy(params[0].obj)
                events.append('UPDATE')
            return self
        def fetchone(self):
            return [deepcopy(durable)]
    monkeypatch.setattr(store, '_connect', Connection)
    return store, durable

def test_body_error_stays_primary_when_guard_entry_also_fails(tmp_path, monkeypatch):
    events = []
    store, durable = _pg_store(tmp_path, monkeypatch, events)
    body = BodyError('original body failure')
    guard_failure = GuardError('later guard entry failure')
    @contextmanager
    def guard():
        events.append('guard_enter')
        raise guard_failure
    with pytest.raises(BodyError) as caught:
        with store.transaction(NID, SCOPE, final_guard=guard) as doc:
            doc['collections']['reviewer'] = {'candidate': {'v': 99}}
            raise body
    assert caught.value is body
    assert caught.value.__notes__ and 'GuardError' in caught.value.__notes__[-1]
    assert caught.value.__guard_entry_error__ is guard_failure
    assert durable == store.empty(NID, SCOPE)
    assert store.key(NID, SCOPE) not in store._local.active
    assert events[-1] == 'rollback'

def test_guard_entry_error_is_primary_when_body_succeeds(tmp_path, monkeypatch):
    events = []
    store, durable = _pg_store(tmp_path, monkeypatch, events)
    guard_failure = GuardError('guard refusal')
    @contextmanager
    def guard():
        events.append('guard_enter')
        raise guard_failure
    with pytest.raises(GuardError) as caught:
        with store.transaction(NID, SCOPE, final_guard=guard) as doc:
            doc['collections']['reviewer'] = {'candidate': {'v': 99}}
    assert caught.value is guard_failure
    assert 'UPDATE' not in events
    assert durable == store.empty(NID, SCOPE)
    assert store.key(NID, SCOPE) not in store._local.active
