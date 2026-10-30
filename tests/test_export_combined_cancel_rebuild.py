import threading
from app.services.export_job_service import ExportJobService


def scenario(tmp_path, other):
    entered=threading.Event(); resume=threading.Event(); advanced=[]
    def exporter(novel_id, fmt, progress_callback):
        entered.set()
        assert resume.wait(5)
        progress_callback(40, 'checkpoint')
        advanced.append('past_cancel')
        return {'content':'not published','format':'txt'}
    a=ExportJobService(tmp_path,exporter)
    b=None
    try:
        job=a.create('synthetic','txt')
        assert entered.wait(5)
        if other:
            b=ExportJobService(tmp_path,lambda *a,**k: (_ for _ in ()).throw(AssertionError('duplicate')))
        (b or a).cancel(job['id'])
        resume.set()
        a._pool.shutdown(wait=True)
        row=a.get(job['id'])
        assert row['status']=='cancelled'
        assert row['result'] is None and row['artifact'] is None
        return advanced, a._futures.copy(), a._cancel_events.copy()
    finally:
        resume.set();a._pool.shutdown(wait=True)
        if b:b._pool.shutdown(wait=True)


def test_other_owner_cancel_stops_at_next_progress(tmp_path):
    advanced, futures, events=scenario(tmp_path, True)
    assert advanced==[]
    assert not futures and not events


def test_own_cancel_releases_local_bookkeeping(tmp_path):
    advanced, futures, events=scenario(tmp_path, False)
    assert advanced==[]
    assert not futures and not events


def test_other_owner_cancel_after_last_callback_before_result(tmp_path):
    from app.services.export_execution_claim import try_execution_claim
    entered=threading.Event(); resume=threading.Event()
    def exporter(novel_id, fmt, progress_callback):
        progress_callback(50, 'last checkpoint')
        entered.set(); assert resume.wait(5)
        return {'content':'late','format':'txt'}
    a=ExportJobService(tmp_path,exporter);b=None
    try:
        row=a.create('synthetic','txt'); assert entered.wait(5)
        b=ExportJobService(tmp_path,lambda *_: None)
        b.cancel(row['id']);resume.set();a._pool.shutdown(wait=True)
        final=a.get(row['id'])
        assert final['status']=='cancelled' and final['result'] is None and final['artifact'] is None
        assert not list(a.artifact_root.glob('*.artifact'))
        assert not a._futures and not a._cancel_events
        claim=try_execution_claim(tmp_path,row['id']); assert claim is not None;claim.release()
    finally:
        resume.set();a._pool.shutdown(wait=True)
        if b:b._pool.shutdown(wait=True)


def test_completion_wins_before_late_cancel(tmp_path):
    import pytest
    from app.services.export_job_service import ExportJobNotCancellable
    a=ExportJobService(tmp_path,lambda *_: {'content':'done','format':'txt'})
    row=a.create('synthetic','txt');a._pool.shutdown(wait=True)
    assert a.get(row['id'])['status']=='succeeded'
    with pytest.raises(ExportJobNotCancellable):a.cancel(row['id'])
    assert a.download(row['id'])['content']==b'done'
    assert not a._futures and not a._cancel_events


def test_repeated_cancel_preserves_first_terminal_and_failure_cleanup(tmp_path):
    import pytest
    from app.services.export_job_service import ExportJobNotCancellable
    entered=threading.Event();resume=threading.Event()
    def exporter(*_):
        entered.set();assert resume.wait(5)
        raise RuntimeError('synthetic provider failure after cancel')
    a=ExportJobService(tmp_path,exporter)
    try:
        row=a.create('synthetic','txt');assert entered.wait(5)
        first=a.cancel(row['id'])
        with pytest.raises(ExportJobNotCancellable):a.cancel(row['id'])
        resume.set();a._pool.shutdown(wait=True)
        final=a.get(row['id']);assert final['status']=='cancelled'
        assert final['error']==first['error']
        assert not a._futures and not a._cancel_events
    finally:resume.set();a._pool.shutdown(wait=True)


def test_unrelated_provider_error_remains_failure(tmp_path):
    from app.services.export_execution_claim import try_execution_claim
    def exporter(*_): raise TimeoutError('synthetic provider timeout')
    a=ExportJobService(tmp_path,exporter)
    row=a.create('synthetic','txt');a._pool.shutdown(wait=True)
    final=a.get(row['id']);assert final['status']=='failed'
    assert 'synthetic provider timeout' in final['error']['message']
    assert not a._futures and not a._cancel_events
    claim=try_execution_claim(tmp_path,row['id']);assert claim is not None;claim.release()
