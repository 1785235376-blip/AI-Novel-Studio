"""R3 shared generation terminal protocol: mounted HTTP, real File/PG, synthetic transport.

No external model or billing service is contacted. PostgreSQL parameters opt in
through the existing marked disposable database fixture, never a File fallback.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event, Thread
from types import SimpleNamespace
import copy
import json

import pytest

from app.jobs import JobManager
from app.model_runtime import GenerationEvent, TextGenerationResponse
from app.router import Route
from test_r3_mounted_contracts import mounted, prefix, checked
from test_r4_broker_mounted import broker_app, quote, route


@pytest.fixture
def terminal_app(broker_app, monkeypatch):
    e = broker_app
    e.first = Event(); e.last = Event(); e.completed = Event()
    e.release_first = Event(); e.release_last = Event(); e.release_completed = Event()
    e.stopped = Event(); e.dispatched = []
    e.full_output = 'SYNTHETIC_FIRST_CHUNK_LATE_CHUNK'
    class Node:
        def stream(self, value):
            value.request.dispatch_guard()
            e.dispatched.append(value.request)
            yield GenerationEvent('generation.delta', None, delta='SYNTHETIC_FIRST_CHUNK')
            e.first.set(); assert e.release_first.wait(10)
            yield GenerationEvent('generation.delta', None, delta='_LATE_CHUNK')
            e.last.set(); assert e.release_last.wait(10)
            yield GenerationEvent('generation.completed', None,
                response=TextGenerationResponse(e.full_output, 'stop', 'mock', 'mock-writer'))
            e.completed.set(); assert e.release_completed.wait(10)
    runtime = SimpleNamespace(is_remote_text_provider=lambda _: False,
        router=lambda *_: SimpleNamespace(routes={'writer': [Route('mock', 'mock-writer')]}),
        packaged_author_route_ready=lambda _: True, prepare_text_route=lambda *_: Node())
    monkeypatch.setattr('app.jobs.runtime', runtime)
    monkeypatch.setattr('app.jobs.runtime_log', SimpleNamespace(write=lambda **_: None))
    monkeypatch.setattr(e.manager, 'canon', e.canon)
    monkeypatch.setattr(e.manager, 'memory_extractor', None)
    monkeypatch.setattr(e.manager, 'collaboration_updates', None)
    e.workers = []
    def prepare():
        return e.manager.prepare_job('continue', {'novel_id': e.nid, 'chapter_id': e.chapter['id'],
            'profile': 'LOCAL_ONLY', 'provider_id': 'mock', 'model_id': 'mock-writer'})
    def start(job=None):
        job = job or prepare()
        e.manager.jobs[job.id] = job; job.status = 'QUEUED'; e.manager._persist(job)
        def run():
            try: e.manager._run(job)
            finally: e.stopped.set()
        thread = Thread(target=run, daemon=True); e.workers.append(thread); thread.start()
        return job
    e.prepare = prepare; e.start = start
    def reopen():
        return JobManager(generations=e.manager.persistence, chapters=e.chapters,
            contexts=e.manager.contexts, canon=e.canon, memory_extractor=object(), snapshot_required=False)
    e.reopen = reopen
    yield e
    e.release_first.set(); e.release_last.set(); e.release_completed.set()
    for thread in e.workers:
        thread.join(10)
        assert not thread.is_alive(), 'Synthetic worker must not escape fixture cleanup'


def path(e, job, suffix=''):
    return e.prefix + '/generation/' + job.id + suffix


def sse(e, job):
    response = e.client.get(path(e, job, '/events'), headers=e.headers)
    assert response.status_code == 200, response.text
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]


@pytest.mark.parametrize('mode', ['OFF', 'ON', 'V1'])
@pytest.mark.parametrize('status', ['PREPARED', 'QUEUED', 'GENERATING', 'SETTLING', 'COMPLETED',
    'CANCELLED', 'FAILED', 'ACCEPTING', 'ACCEPTED', 'ACCEPTANCE_UNCERTAIN', 'REJECTED'])
def test_http_reject_is_only_completed_review_and_never_changes_other_states(terminal_app, monkeypatch, mode, status):
    e = terminal_app
    if mode == 'OFF': monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    if mode == 'V1': monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    job = e.prepare(); job.status = status; job.output = 'Complete synthetic draft'
    e.manager.jobs[job.id] = job; e.manager._persist(job)
    before = copy.deepcopy(e.manager.persistence.get(job.id))
    response = e.client.post(path(e, job, '/reject'), headers=e.headers)
    if status == 'COMPLETED':
        assert response.status_code == 200, response.text
        assert job.status == response.json()['status'] == e.manager.persistence.get(job.id)['status'] == 'REJECTED'
        events = sse(e, job)
        assert events[-1]['status'] == 'REJECTED'
        assert ''.join(row['chunk'] for row in events) == job.output
    else:
        assert response.status_code == 409, response.text
        assert response.json()['detail']['code'] == 'GENERATION_NOT_REJECTABLE'
        assert response.json()['detail']['status'] == status
        assert job.status == status and e.manager.persistence.get(job.id) == before
    assert not job.cancelled.is_set()
    assert e.chapters.get(e.chapter['id']) == e.chapter


@pytest.mark.parametrize('mode', ['OFF', 'ON', 'V1'])
@pytest.mark.parametrize('boundary', ['first_chunk', 'last_chunk', 'completed_event'])
def test_running_reject_at_each_stream_boundary_cannot_truncate_or_revive_draft(terminal_app, monkeypatch, mode, boundary):
    e = terminal_app
    if mode == 'OFF': monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    if mode == 'V1': monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    job = e.start()
    assert e.first.wait(5)
    if boundary != 'first_chunk': e.release_first.set(); assert e.last.wait(5)
    if boundary == 'completed_event': e.release_last.set(); assert e.completed.wait(5)
    response = e.client.post(path(e, job, '/reject'), headers=e.headers)
    assert response.status_code == 409, response.text
    assert job.status == e.manager.persistence.get(job.id)['status'] == 'GENERATING'
    assert not job.cancelled.is_set()
    e.release_first.set(); e.release_last.set(); e.release_completed.set()
    assert e.stopped.wait(5)
    assert job.status == e.manager.persistence.get(job.id)['status'] == 'COMPLETED'
    assert job.output == e.full_output == e.manager.persistence.get(job.id)['output']
    events = sse(e, job)
    assert events[-1]['status'] == 'COMPLETED'
    assert ''.join(row['chunk'] for row in events) == e.full_output
    assert checked(e.client.post(path(e, job, '/reject'), headers=e.headers))['status'] == 'REJECTED'
    assert e.reopen().get(job.id).status == 'REJECTED'
    assert len(e.dispatched) == 1


def test_settlement_is_durable_and_reject_does_not_wait_to_change_its_meaning(terminal_app):
    e = terminal_app; settling = Event(); release = Event(); calls = []
    job = e.prepare(); job.before_dispatch = lambda: None
    def finalize():
        calls.append(job.execution_outcome); settling.set(); assert release.wait(10)
    job.on_terminal = finalize
    try:
        e.start(job); e.release_first.set(); e.release_last.set(); e.release_completed.set()
        assert settling.wait(5)
        assert job.public()['status'] == 'SETTLING'
        assert e.manager.persistence.get(job.id)['status'] == 'SETTLING'
        with ThreadPoolExecutor(max_workers=1) as pool:
            rejected = pool.submit(e.client.post, path(e, job, '/reject'), headers=e.headers)
            try:
                response = rejected.result(timeout=2)
                assert response.status_code == 409, response.text
                assert response.json()['detail']['status'] == 'SETTLING'
            finally: release.set()
        assert e.stopped.wait(5)
        assert job.status == e.manager.persistence.get(job.id)['status'] == 'COMPLETED'
        assert job.terminal_hook_status == 'COMPLETED' and calls == ['COMPLETED']
    finally: release.set()


@pytest.mark.parametrize('status', ['PREPARED', 'QUEUED', 'GENERATING', 'SETTLING'])
def test_restart_recovery_is_persisted_and_never_dispatches_or_releases_unknown_use(terminal_app, status):
    e = terminal_app; job = e.prepare(); job.status = status; job.output = 'Retained synthetic partial'
    if status == 'SETTLING': job.dispatch_hooks_required = True; job.execution_outcome = 'COMPLETED'
    e.manager._persist(job)
    restarted = e.reopen(); restored = restarted.get(job.id)
    assert restored.status == e.manager.persistence.get(job.id)['status'] == 'FAILED'
    assert restored.output == job.output and not e.dispatched
    assert restored.before_dispatch is None and restored.on_terminal is None
    if status == 'SETTLING':
        assert restored.terminal_hook_status == 'MISSING_RECONCILIATION_REQUIRED'
        assert restored.execution_outcome == 'COMPLETED'
    with pytest.raises(ValueError): restarted.reject(job.id)
    with pytest.raises(ValueError): restarted.start_prepared(restored)
    assert e.reopen().get(job.id).public() == restored.public()


@pytest.mark.parametrize('late', ['completion', 'failure'])
def test_cancel_during_final_review_survives_late_worker_exit(terminal_app, monkeypatch, late):
    e = terminal_app; entered = Event(); release = Event()
    def review(*_):
        entered.set(); assert release.wait(10)
        if late == 'failure': raise RuntimeError('Synthetic late review failure')
        return []
    monkeypatch.setattr('app.jobs.deterministic_review', review)
    try:
        job = e.start(); e.release_first.set(); e.release_last.set(); e.release_completed.set()
        assert entered.wait(5)
        assert checked(e.client.post(path(e, job, '/cancel'), headers=e.headers))['status'] == 'CANCELLED'
        release.set(); assert e.stopped.wait(5)
        assert job.status == e.manager.persistence.get(job.id)['status'] == 'CANCELLED'
        assert job.execution_outcome == 'CANCELLED' and job.output == e.full_output
        events = sse(e, job)
        assert events[-1]['status'] == 'CANCELLED' and ''.join(row['chunk'] for row in events) == e.full_output
        assert e.client.post(path(e, job, '/reject'), headers=e.headers).status_code == 409
    finally: release.set()


@pytest.mark.parametrize('decision', ['REJECTED', 'ACCEPTED', 'ACCEPTANCE_UNCERTAIN'])
@pytest.mark.parametrize('late', ['success', 'failure'])
def test_late_worker_after_review_never_overwrites_durable_terminal(terminal_app, monkeypatch, decision, late):
    e = terminal_app; entered = Event(); release = Event()
    def review(*_):
        entered.set(); assert release.wait(10)
        if late == 'failure': raise RuntimeError('Synthetic late failure')
        return []
    monkeypatch.setattr('app.jobs.deterministic_review', review)
    try:
        job = e.start(); e.release_first.set(); e.release_last.set(); e.release_completed.set()
        assert entered.wait(5)
        # A durable review already decided elsewhere is authoritative even if a
        # previously dispatched worker returns afterward (including old clients).
        with job.condition:
            job.status = decision; e.manager._emit(job)
        release.set(); assert e.stopped.wait(5)
        assert job.status == e.manager.persistence.get(job.id)['status'] == decision
        assert e.reopen().get(job.id).status == decision
        events = sse(e, job)
        assert events[-1]['status'] == decision
        assert ''.join(row['chunk'] for row in events) == e.full_output
    finally: release.set()


@pytest.mark.parametrize('outcome', ['complete', 'cancel', 'failure'])
def test_terminal_accounting_runs_once_and_keeps_unknown_upstream_hold(terminal_app, monkeypatch, outcome):
    e = terminal_app
    candidate = {**route(e), 'synthetic': False}
    monkeypatch.setattr(e.broker, 'candidates', lambda: [copy.deepcopy(candidate)])
    now = datetime.now(timezone.utc)
    e.broker.configure_price(e.nid, e.scope, 'local-author', {
        'route_id': candidate['route_id'], 'route_fingerprint': candidate['fingerprint'],
        'reserve_microusd': 40, 'source': 'Synthetic billing protocol fixture',
        'as_of': now.isoformat(), 'expires_at': (now + timedelta(days=1)).isoformat(), 'expected_version': 0})
    e.broker.configure_budget(e.nid, e.scope, 'local-author',
        {'expected_version': 0, 'limit_microusd': 50, 'max_inflight': 2})
    selected = quote(e); job = e.prepare()
    entry = e.broker.reserve(e.nid, e.scope, 'local-author', selected['id'], selected['version'], 'terminal-once', job.id)
    calls = []
    job.before_dispatch = lambda: e.broker.guard_dispatch(e.nid, e.scope, 'local-author', entry['id'], job.id)
    def finish():
        calls.append(job.execution_outcome)
        e.broker.finalize(e.nid, e.scope, 'local-author', entry['id'], job.id, job.execution_outcome, job.usage)
    job.on_terminal = finish; job.dispatch_hooks_required = True
    if outcome == 'failure':
        monkeypatch.setattr('app.jobs.deterministic_review', lambda *_: (_ for _ in ()).throw(RuntimeError('Synthetic review failure')))
    e.start(job); assert e.first.wait(5)
    if outcome == 'cancel': e.manager.cancel(job.id)
    e.release_first.set(); e.release_last.set(); e.release_completed.set(); assert e.stopped.wait(5)
    expected = {'complete': 'COMPLETED', 'cancel': 'CANCELLED', 'failure': 'FAILED'}[outcome]
    assert job.status == e.manager.persistence.get(job.id)['status'] == expected
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: e.manager._finish_terminal_hook(job), range(16)))
    ledger = e.broker.get(e.nid, e.scope, e.broker.LEDGER, entry['id'])
    assert calls == [expected] and len(e.dispatched) == 1
    assert ledger['status'] == 'UNKNOWN_UPSTREAM' and ledger['actual_microusd'] is None
    assert ledger['accounted_microusd'] == 40 and e.broker.budget(e.nid, e.scope)['committed_microusd'] == 40
    assert job.usage_status == 'UNKNOWN' and job.terminal_hook_status == 'COMPLETED'
    if outcome == 'complete':
        checked(e.client.post(path(e, job, '/reject'), headers=e.headers))
    else:
        assert e.client.post(path(e, job, '/reject'), headers=e.headers).status_code == 409
    assert e.broker.get(e.nid, e.scope, e.broker.LEDGER, entry['id']) == ledger
    restored = e.reopen().get(job.id)
    assert restored.status == job.status and restored.terminal_hook_status == 'COMPLETED'
    assert e.broker.get(e.nid, e.scope, e.broker.LEDGER, entry['id']) == ledger


def test_cancelled_settlement_failure_does_not_revive_or_reclassify_cancelled_draft(terminal_app):
    e = terminal_app; job = e.prepare(); calls = []
    job.before_dispatch = lambda: None
    def fail():
        calls.append(job.execution_outcome)
        raise OSError('Synthetic unconfirmed upstream settlement')
    job.on_terminal = fail
    e.start(job); assert e.first.wait(5); e.manager.cancel(job.id)
    e.release_first.set(); e.release_last.set(); e.release_completed.set(); assert e.stopped.wait(5)
    assert job.status == e.manager.persistence.get(job.id)['status'] == 'CANCELLED'
    assert job.terminal_hook_status == 'FAILED_RECONCILIATION_REQUIRED'
    assert job.execution_outcome == 'CANCELLED' and calls == ['CANCELLED']
    assert e.client.post(path(e, job, '/reject'), headers=e.headers).status_code == 409
    assert sse(e, job)[-1]['status'] == 'CANCELLED'


def test_reject_rechecks_durable_status_from_another_manager(terminal_app):
    e = terminal_app; job = e.prepare(); job.status = 'COMPLETED'; job.output = 'Durable synthetic draft'
    e.manager.jobs[job.id] = job; e.manager._persist(job)
    stale = e.reopen()
    e.manager.reject(job.id)
    with pytest.raises(ValueError): stale.reject(job.id)
    assert e.manager.persistence.get(job.id)['status'] == 'REJECTED'
    assert e.reopen().get(job.id).status == 'REJECTED'


def test_other_manager_reject_cannot_be_overwritten_by_final_worker_publication(terminal_app, monkeypatch):
    e = terminal_app; publication = Event(); release = Event()
    original = e.manager._emit
    def pause_final(job, chunk=''):
        result = original(job, chunk)
        if job.status == 'COMPLETED':
            publication.set(); assert release.wait(10)
        return result
    monkeypatch.setattr(e.manager, '_emit', pause_final)
    try:
        job = e.start(); e.release_first.set(); e.release_last.set(); e.release_completed.set()
        assert publication.wait(5)
        second = e.reopen()
        assert second.get(job.id).status == 'COMPLETED'
        with ThreadPoolExecutor(max_workers=1) as pool:
            rejected = pool.submit(second.reject, job.id)
            release.set(); assert e.stopped.wait(5)
            assert rejected.result(timeout=5).status == 'REJECTED'
        assert e.manager.persistence.get(job.id)['status'] == 'REJECTED'
        assert e.reopen().get(job.id).status == 'REJECTED'
    finally: release.set()


def test_cancel_during_settlement_is_responsive_without_changing_completed_outcome(terminal_app):
    e = terminal_app; settling = Event(); release = Event(); job = e.prepare()
    job.before_dispatch = lambda: None
    def finalize(): settling.set(); assert release.wait(10)
    job.on_terminal = finalize
    try:
        e.start(job); e.release_first.set(); e.release_last.set(); e.release_completed.set()
        assert settling.wait(5)
        with ThreadPoolExecutor(max_workers=1) as pool:
            cancel = pool.submit(e.client.post, path(e, job, '/cancel'), headers=e.headers)
            try:
                response = cancel.result(timeout=2)
                assert response.status_code == 200 and response.json()['status'] == 'SETTLING'
            finally: release.set()
        assert e.stopped.wait(5)
        assert job.status == e.manager.persistence.get(job.id)['status'] == 'COMPLETED'
        assert job.execution_outcome == 'COMPLETED' and job.cancelled.is_set()
    finally: release.set()


def test_reloaded_accounted_terminal_is_not_reclassified_as_missing_accounting(terminal_app):
    e = terminal_app; job = e.prepare(); job.status = 'COMPLETED'
    job.dispatch_hooks_required = True; job.terminal_hook_status = 'COMPLETED'
    job.execution_outcome = 'COMPLETED'; job.output = e.full_output
    e.manager._persist(job); restarted = e.reopen(); restored = restarted.get(job.id)
    before = copy.deepcopy(restored.public())
    restarted._run(restored)
    assert restored.public() == before == e.manager.persistence.get(job.id)
    assert not e.dispatched


@pytest.mark.parametrize('terminal', ['COMPLETED', 'REJECTED', 'ACCEPTED', 'ACCEPTANCE_UNCERTAIN', 'CANCELLED'])
def test_recovery_snapshot_cannot_overwrite_newer_durable_terminal(terminal_app, monkeypatch, terminal):
    e = terminal_app; job = e.prepare(); job.status = 'GENERATING'; job.output = 'Full synthetic output'
    e.manager._persist(job)
    stale_snapshot = copy.deepcopy(e.manager.persistence.get(job.id))
    job.status = terminal; e.manager._persist(job)
    monkeypatch.setattr(e.manager.persistence, 'load_all', lambda: [stale_snapshot])
    restored = e.reopen().get(job.id)
    assert restored.status == e.manager.persistence.get(job.id)['status'] == terminal
    assert restored.output == job.output and not e.dispatched


@pytest.mark.parametrize('accounted', [False, True])
@pytest.mark.parametrize('failure', ['first_completion_write', 'persistent_outage'])
def test_unpublished_completion_fails_closed_and_never_becomes_reviewable(terminal_app, monkeypatch, accounted, failure):
    e = terminal_app; job = e.prepare(); calls = []; writes_failed = []
    if accounted:
        job.before_dispatch = lambda: None
        job.on_terminal = lambda: calls.append(job.execution_outcome)
    original = e.manager._persist
    def persist(value):
        if (not writes_failed and value.public()['status'] in {'COMPLETED', 'SETTLING'}) or (writes_failed and failure == 'persistent_outage'):
            writes_failed.append(value.public()['status'])
            raise OSError('Synthetic terminal publication outage')
        return original(value)
    monkeypatch.setattr(e.manager, '_persist', persist)
    e.start(job); e.release_first.set(); e.release_last.set(); e.release_completed.set(); assert e.stopped.wait(5)
    assert writes_failed
    assert job.status == 'FAILED'
    assert job.error_code == 'GENERATION_TERMINAL_PERSISTENCE_UNCERTAIN'
    assert job.output == e.full_output and job.execution_outcome == 'COMPLETED'
    assert calls == (['COMPLETED'] if accounted else [])
    assert e.client.post(path(e, job, '/reject'), headers=e.headers).status_code == 409
    assert e.client.post(path(e, job, '/accept'), headers=e.headers, json={'expected_version': e.chapter['version']}).status_code in {400, 409}
    assert sse(e, job)[-1]['status'] == 'FAILED'
    if failure == 'first_completion_write':
        assert e.manager.persistence.get(job.id)['status'] == 'FAILED'
    else:
        assert e.manager.persistence.get(job.id)['status'] == 'GENERATING'
    assert e.reopen().get(job.id).status == 'FAILED'
    assert e.chapters.get(e.chapter['id']) == e.chapter


def test_accounting_receipt_write_failure_is_not_published_as_completed(terminal_app, monkeypatch):
    e = terminal_app; job = e.prepare(); calls = []; failed = []
    job.before_dispatch = lambda: None
    job.on_terminal = lambda: calls.append(job.execution_outcome)
    original = e.manager._persist
    def persist(value):
        if value.status == 'COMPLETED' and value.terminal_hook_status == 'COMPLETED' and not failed:
            failed.append(True)
            raise OSError('Synthetic lost accounting confirmation write')
        return original(value)
    monkeypatch.setattr(e.manager, '_persist', persist)
    e.start(job); e.release_first.set(); e.release_last.set(); e.release_completed.set(); assert e.stopped.wait(5)
    assert failed and calls == ['COMPLETED']
    assert job.status == e.manager.persistence.get(job.id)['status'] == 'FAILED'
    assert job.terminal_hook_status == 'PERSISTENCE_UNCERTAIN_RECONCILIATION_REQUIRED'
    assert job.error_code == 'TERMINAL_RECONCILIATION_REQUIRED' and job.output == e.full_output
    e.manager._finish_terminal_hook(job)
    assert calls == ['COMPLETED']
    assert e.client.post(path(e, job, '/reject'), headers=e.headers).status_code == 409
    assert sse(e, job)[-1]['status'] == 'FAILED'
    assert e.reopen().get(job.id).status == 'FAILED'
