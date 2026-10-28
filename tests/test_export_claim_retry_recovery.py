from concurrent.futures import Future, ThreadPoolExecutor
from threading import Barrier, Event
import time

import pytest

from app.services import export_job_service as module
from app.services.export_execution_claim import ExportExecutionUnavailable


def test_idempotent_retry_resubmits_persisted_queue_after_claim_error(tmp_path, monkeypatch):
    calls = []
    service = module.ExportJobService(tmp_path, lambda *args: calls.append('run') or {'content': 'ok', 'filename': 'ok.txt'})
    original = module.try_execution_claim
    try:
        def unavailable(*args):
            raise ExportExecutionUnavailable('lock unavailable')
        monkeypatch.setattr(module, 'try_execution_claim', unavailable)
        with pytest.raises(ExportExecutionUnavailable):
            service.create('book', 'txt', 'same-key')
        with pytest.raises(ExportExecutionUnavailable):
            service.create('book', 'txt', 'same-key')
        assert len(service._read()) == 1 and not calls
        monkeypatch.setattr(module, 'try_execution_claim', original)
        retry = service.create('book', 'txt', 'same-key')
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and service.get(retry['id'])['status'] == 'queued':
            time.sleep(.01)
        service._pool.shutdown(wait=True)
        assert service.get(retry['id'])['status'] == 'succeeded'
        assert len(service._read()) == 1 and calls == ['run']
    finally:
        service._pool.shutdown(wait=True)


def test_idempotent_retry_does_not_duplicate_a_live_queued_claim(tmp_path, monkeypatch):
    class DeferredPool:
        def __init__(self, **kwargs): self.pending = []
        def submit(self, *args):
            future = Future()
            self.pending.append(future)
            return future
        def shutdown(self, wait=True):
            for future in self.pending: future.cancel()

    monkeypatch.setattr(module, 'ThreadPoolExecutor', DeferredPool)
    owner = module.ExportJobService(tmp_path, lambda *args: pytest.fail('must remain queued'))
    other = module.ExportJobService(tmp_path, lambda *args: pytest.fail('must not steal live claim'))
    try:
        first = owner.create('book', 'txt', 'same-key')
        duplicate = other.create('book', 'txt', 'same-key')
        assert first['id'] == duplicate['id'] and duplicate['status'] == 'queued'
        assert len(owner._pool.pending) == 1 and not other._pool.pending
    finally:
        owner._pool.shutdown()
        other._pool.shutdown()


def test_simultaneous_idempotent_retries_obtain_only_one_claim(tmp_path, monkeypatch):
    class DeferredPool:
        def __init__(self, **kwargs): self.pending = []
        def submit(self, *args):
            future = Future()
            self.pending.append(future)
            return future
        def shutdown(self, wait=True):
            for future in self.pending: future.cancel()

    monkeypatch.setattr(module, 'ThreadPoolExecutor', DeferredPool)
    services = [module.ExportJobService(tmp_path, lambda *args: pytest.fail('must remain queued')) for _ in range(4)]
    original = module.try_execution_claim
    try:
        def unavailable(*args):
            raise ExportExecutionUnavailable('lock unavailable')
        monkeypatch.setattr(module, 'try_execution_claim', unavailable)
        with pytest.raises(ExportExecutionUnavailable):
            services[0].create('book', 'txt', 'same-key')
        monkeypatch.setattr(module, 'try_execution_claim', original)
        barrier = Barrier(len(services))
        def retry(service):
            barrier.wait(timeout=5)
            return service.create('book', 'txt', 'same-key')
        with ThreadPoolExecutor(max_workers=len(services)) as pool:
            rows = list(pool.map(retry, services))
        assert len({row['id'] for row in rows}) == 1
        assert sum(len(service._pool.pending) for service in services) == 1
    finally:
        for service in services: service._pool.shutdown()


def test_closed_retry_pool_does_not_fail_original_queued_job(tmp_path, monkeypatch):
    calls, entered, release = [], Event(), Event()
    owner = module.ExportJobService(tmp_path, lambda *args: calls.append('run') or {'content': 'ok', 'filename': 'ok.txt'})
    retry_service = module.ExportJobService(tmp_path, lambda *args: pytest.fail('closed pool must not execute'))
    original_submit = owner._submit
    def delayed_submit(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original_submit(*args, **kwargs)
    monkeypatch.setattr(owner, '_submit', delayed_submit)
    retry_service._pool.shutdown(wait=True)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            original = pool.submit(owner.create, 'book', 'txt', 'same-key')
            assert entered.wait(5)
            with pytest.raises(RuntimeError, match='EXPORT_QUEUE_UNAVAILABLE'):
                retry_service.create('book', 'txt', 'same-key')
            assert next(iter(owner._read().values()))['status'] == 'queued'
            release.set()
            row = original.result(timeout=5)
        owner._pool.shutdown(wait=True)
        assert owner.get(row['id'])['status'] == 'succeeded' and calls == ['run']
    finally:
        release.set()
        owner._pool.shutdown(wait=True)


@pytest.mark.parametrize('terminal', ['succeeded', 'cancelled'])
def test_retry_rereads_after_original_completes_or_cancels(tmp_path, monkeypatch, terminal):
    calls, release_workers, retry_entered, release_retry = [], Event(), Event(), Event()
    owner = module.ExportJobService(tmp_path, lambda *args: calls.append('run') or {'content': 'ok', 'filename': 'ok.txt'})
    retry_service = module.ExportJobService(tmp_path, lambda *args: pytest.fail('terminal job must not run again'))
    blockers_started = Barrier(3)
    def block_worker():
        blockers_started.wait(timeout=5)
        assert release_workers.wait(5)
    for _ in range(2): owner._pool.submit(block_worker)
    blockers_started.wait(timeout=5)
    original_submit = retry_service._submit
    def delayed_submit(*args, **kwargs):
        retry_entered.set()
        assert release_retry.wait(5)
        return original_submit(*args, **kwargs)
    monkeypatch.setattr(retry_service, '_submit', delayed_submit)
    try:
        row = owner.create('book', 'txt', 'same-key')
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(retry_service.create, 'book', 'txt', 'same-key')
            assert retry_entered.wait(5)
            if terminal == 'cancelled': owner.cancel(row['id'])
            release_workers.set()
            owner._pool.shutdown(wait=True)
            assert owner.get(row['id'])['status'] == terminal
            release_retry.set()
            result = future.result(timeout=5)
        retry_service._pool.shutdown(wait=True)
        assert result['status'] == terminal
        assert owner.get(row['id'])['status'] == terminal
        assert calls == (['run'] if terminal == 'succeeded' else [])
    finally:
        release_workers.set(); release_retry.set()
        owner._pool.shutdown(wait=True); retry_service._pool.shutdown(wait=True)
