"""Prepared job identity, final-hop accounting and callback failure boundaries."""
import copy
import json
import threading
from types import SimpleNamespace as S

import pytest

from app.jobs import Job, JobManager
from app.router import Route
from test_r4_author_context import rig


def prepared(e):
    return e.manager.prepare_job('continue', {**e.body, 'source': '', 'selected_text': '', 'creation_records': []})


def test_preflight_never_invokes_dispatch_or_terminal_hooks(rig):
    e = rig; value = prepared(e); calls = []
    value.before_dispatch = lambda: calls.append('dispatch')
    value.on_terminal = lambda: calls.append('terminal')
    e.manager.prepare_author_request(value, Route('fixture', 'model'))
    e.manager._guard_author_request(value, Route('fixture', 'model'))
    assert calls == []
    e.manager._run(value)
    assert value.status == 'COMPLETED'
    assert calls == ['dispatch', 'terminal']
    e.manager._finish_terminal_hook(value)
    assert calls == ['dispatch', 'terminal']


@pytest.mark.parametrize('case', ['cancel', 'route_failure', 'dispatch_failure'])
def test_terminal_callback_runs_for_every_early_worker_exit(rig, case):
    e = rig; value = prepared(e); calls = []
    def before():
        calls.append('dispatch')
        if case == 'dispatch_failure': raise ValueError('Synthetic budget revocation')
    value.before_dispatch = before
    value.on_terminal = lambda: calls.append(value.status)
    if case == 'cancel': value.cancelled.set()
    if case == 'route_failure':
        e.manager.contexts.for_chapter = lambda *_: (_ for _ in ()).throw(ValueError('synthetic preflight failure'))
    e.manager._run(value)
    assert calls[-1] in {'CANCELLED', 'FAILED'}
    assert not e.state.sent
    assert calls.count('dispatch') == (1 if case == 'dispatch_failure' else 0)


def test_terminal_failure_is_conservative_preserves_output_and_never_replays(rig):
    e = rig; value = prepared(e); attempts = []
    value.before_dispatch = lambda: None
    def settle():
        attempts.append(value.status)
        raise OSError('SYNTHETIC_PRIVATE_DATABASE_ERROR')
    value.on_terminal = settle
    e.manager._run(value)
    assert value.status == 'FAILED' and value.output == 'synthetic draft'
    assert value.terminal_hook_status == 'FAILED_RECONCILIATION_REQUIRED'
    assert value.error_code == 'TERMINAL_RECONCILIATION_REQUIRED'
    assert 'PRIVATE_DATABASE' not in json.dumps(value.public())
    e.manager._finish_terminal_hook(value)
    assert attempts == ['COMPLETED'] and len(e.state.sent) == 1


def test_start_prepared_preserves_same_object_and_never_persists_callbacks(rig, monkeypatch):
    e = rig; manager = e.manager; value = prepared(e); captures = []
    manager.jobs = {}; manager.lock = threading.Lock()
    manager._persist = lambda item: captures.append(('persist', item, copy.deepcopy(item.public())))
    class Thread:
        def __init__(self, *, target, args, daemon): captures.append(('thread', target, args[0]))
        def start(self): captures.append(('started',))
    monkeypatch.setattr('app.jobs.threading.Thread', Thread)
    value.before_dispatch = lambda: None; value.on_terminal = lambda: None
    result = JobManager.start_prepared(manager, value)
    assert result is value and manager.jobs[value.id] is value
    assert captures[0][0] == 'persist' and captures[0][1] is value
    assert captures[1][2] is value and captures[0][2]['dispatch_hooks_required'] is True
    assert not set(captures[0][2]) & {'before_dispatch', 'on_terminal', 'request_authorization', 'character_context_resolver'}
    with pytest.raises(ValueError): JobManager.start_prepared(manager, value)
    assert len([entry for entry in captures if entry[0] == 'started']) == 1


def test_reloaded_job_missing_dispatch_session_cannot_send(rig):
    e = rig; original = prepared(e); original.dispatch_hooks_required = True
    restored = Job(**original.public())
    e.manager._run(restored)
    assert restored.status == 'FAILED' and not e.state.sent
    assert restored.terminal_hook_status == 'MISSING_RECONCILIATION_REQUIRED'


def test_start_persistence_failure_does_not_start_or_release_any_callback(rig, monkeypatch):
    e = rig; value = prepared(e); e.manager.jobs = {}; e.manager.lock = threading.Lock()
    def fail(_): raise OSError('Synthetic persistence failure')
    e.manager._persist = fail
    monkeypatch.setattr('app.jobs.threading.Thread', lambda **_: pytest.fail('Must not launch after failed persist'))
    with pytest.raises(OSError): JobManager.start_prepared(e.manager, value)
    assert value.status == 'PREPARED' and value.id not in e.manager.jobs
