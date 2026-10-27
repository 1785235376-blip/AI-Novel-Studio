"""Independent same-host ownership, release, and path boundary counterexamples."""
from concurrent.futures import ThreadPoolExecutor
import errno
import hashlib
import os
from pathlib import Path
from threading import Event, Thread
import time

import pytest
from app.services import export_execution_claim as claims
from app.services.export_job_service import ExportJobService


def wait_status(s, jid, wanted, timeout=5):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        row=s.get(jid)
        if row['status'] in wanted:return row
        time.sleep(.005)
    raise AssertionError((row,wanted))


def result(text='ok'):
    return {'content':text,'filename':'synthetic.txt','format':'txt'}


def acquire_release(root,jid):
    claim=claims.try_execution_claim(root,jid)
    assert claim is not None
    claim.release()


def test_claim_idempotent_release_alias_and_other_job(tmp_path):
    alias=tmp_path/'alias'; data=tmp_path/'data';data.mkdir();alias.symlink_to(data,target_is_directory=True)
    first=claims.try_execution_claim(data,'job')
    try:
        assert claims.try_execution_claim(alias,'job') is None
        acquire_release(data,'other')
    finally:first.release();first.release()
    acquire_release(alias,'job')


@pytest.mark.parametrize('kind',['directory-symlink','file-symlink','hardlink'])
def test_unsafe_lock_facilities_fail_closed(tmp_path,kind):
    data=tmp_path/'data';data.mkdir(); outside=tmp_path/'outside';outside.mkdir()
    directory=data/'.export-execution-locks';name=hashlib.sha256(b'j').hexdigest()+'.lock'
    target=outside/'target';target.write_bytes(b'unchanged')
    if kind=='directory-symlink':directory.symlink_to(outside,target_is_directory=True)
    else:
        directory.mkdir()
        if kind=='file-symlink':(directory/name).symlink_to(target)
        else:os.link(target,directory/name)
    with pytest.raises(claims.ExportExecutionUnavailable):claims.try_execution_claim(data,'j')
    assert target.read_bytes()==b'unchanged'
    assert set(p.name for p in outside.iterdir())=={'target'}


@pytest.mark.parametrize('failure',['open','locking'])
def test_failed_acquisition_does_not_leave_registry_claim(tmp_path,monkeypatch,failure):
    if failure=='open':
        original=claims.os.open
        monkeypatch.setattr(claims.os,'open',lambda *a,**k: (_ for _ in ()).throw(PermissionError(errno.EACCES,'synthetic')))
    else:
        original=claims._try_lock
        monkeypatch.setattr(claims,'_try_lock',lambda *a: (_ for _ in ()).throw(OSError(errno.EIO,'synthetic')))
    with pytest.raises(claims.ExportExecutionUnavailable):claims.try_execution_claim(tmp_path,'j')
    if failure=='open':monkeypatch.setattr(claims.os,'open',original)
    else:monkeypatch.setattr(claims,'_try_lock',original)
    acquire_release(tmp_path,'j')


def test_replacement_during_lock_acquisition_fails_closed(tmp_path,monkeypatch):
    original=claims._try_lock
    def replace(handle):
        locked=original(handle)
        p=tmp_path/'.export-execution-locks'/(hashlib.sha256(b'j').hexdigest()+'.lock')
        p.rename(p.with_suffix('.old'));p.write_bytes(b'0')
        return locked
    monkeypatch.setattr(claims,'_try_lock',replace)
    with pytest.raises(claims.ExportExecutionUnavailable):claims.try_execution_claim(tmp_path,'j')
    monkeypatch.setattr(claims,'_try_lock',original)
    acquire_release(tmp_path,'j')


def test_idle_get_list_do_not_create_execution_facilities(tmp_path):
    s=ExportJobService(tmp_path,lambda *a:result())
    try:
        assert not (tmp_path/'.export-execution-locks').exists()
        with pytest.raises(FileNotFoundError):s.get('missing')
        assert s.list('book',permission_context={'mode':'local','novel_id':'book'})['items']==[]
        assert not (tmp_path/'.export-execution-locks').exists()
    finally:s._pool.shutdown(wait=True)


def test_two_owners_live_cancel_and_independent_job(tmp_path):
    entered=Event();release=Event();calls=[]
    def exporter(n,f):
        calls.append(n)
        if n=='slow':entered.set();assert release.wait(5)
        return result(n)
    a=ExportJobService(tmp_path,exporter); b=None
    try:
        row=a.create('slow','txt');assert entered.wait(3)
        before=a.path.read_bytes()
        b=ExportJobService(tmp_path,lambda *args:pytest.fail('duplicate renderer'))
        assert a.path.read_bytes()==before
        a._submit(row['id']);assert calls==['slow']
        other=a.create('fast','txt');assert wait_status(a,other['id'],{'succeeded'})['result']['content']=='fast'
        b.cancel(row['id']);release.set()
        a._pool.shutdown(wait=True)
        assert a.get(row['id'])['status']=='cancelled'
        acquire_release(tmp_path,row['id'])
    finally:
        release.set();a._pool.shutdown(wait=True)
        if b:b._pool.shutdown(wait=True)


def test_queued_claim_survives_other_startup_and_cancelled_future_releases(tmp_path):
    release=Event();entered=[Event(),Event()];calls=[]
    def exporter(n,f):
        calls.append(n)
        if n in {'block0','block1'}:entered[int(n[-1])].set();assert release.wait(5)
        return result(n)
    a=ExportJobService(tmp_path,exporter);b=None
    try:
        for i in range(2):a.create('block'+str(i),'txt')
        assert all(e.wait(3) for e in entered)
        queued=a.create('queued','txt');assert a.get(queued['id'])['status']=='queued'
        before=a.path.read_bytes()
        b=ExportJobService(tmp_path,lambda *args:pytest.fail('queued work was stolen'))
        assert a.path.read_bytes()==before
        assert claims.try_execution_claim(tmp_path,queued['id']) is None
        a.cancel(queued['id'])
        acquire_release(tmp_path,queued['id'])
        assert 'queued' not in calls
    finally:
        release.set();a._pool.shutdown(wait=True)
        if b:b._pool.shutdown(wait=True)


def test_shutdown_pool_does_not_poison_other_live_job(tmp_path):
    release=Event();entered=Event()
    def exporter(*args):entered.set();assert release.wait(5);return result()
    a=ExportJobService(tmp_path,exporter);b=None
    try:
        row=a.create('book','txt');assert entered.wait(3)
        b=ExportJobService(tmp_path,lambda *args:pytest.fail('duplicate'))
        b._pool.shutdown(wait=True);before=a.path.read_bytes()
        b._submit(row['id'])
        assert a.path.read_bytes()==before
    finally:
        release.set();a._pool.shutdown(wait=True)
        if b:b._pool.shutdown(wait=True)


def test_submission_failure_releases_own_claim(tmp_path):
    s=ExportJobService(tmp_path,lambda *args:result());s._pool.shutdown(wait=True)
    row=s.create('book','txt')
    assert s.get(row['id'])['error']['code']=='EXPORT_QUEUE_UNAVAILABLE'
    acquire_release(tmp_path,row['id'])


@pytest.mark.parametrize('failure',['exporter','artifact','final-write'])
def test_failure_paths_release_claim(tmp_path,monkeypatch,failure):
    def exporter(*args):
        if failure=='exporter':raise ValueError('synthetic')
        return result()
    s=ExportJobService(tmp_path,exporter)
    if failure=='artifact':monkeypatch.setattr(s,'_persist_artifact',lambda *args: (_ for _ in ()).throw(OSError('synthetic')))
    if failure=='final-write':
        original=s._write
        def write(rows):
            if any(row.get('status')=='succeeded' for row in rows.values()):raise OSError('synthetic final write')
            return original(rows)
        monkeypatch.setattr(s,'_write',write)
    try:
        row=s.create('book','txt');s._pool.shutdown(wait=True)
        assert s.get(row['id'])['status']==('running' if failure=='final-write' else 'failed')
        acquire_release(tmp_path,row['id'])
    finally:s._pool.shutdown(wait=True)


def test_create_submit_gap_allows_one_winner_without_duplicate(tmp_path,monkeypatch):
    gate=Event();release=Event();calls=[]
    a=ExportJobService(tmp_path,lambda *args:(calls.append('a') or result('a')));b=None
    original=a._submit
    def delayed(jid):gate.set();assert release.wait(5);original(jid)
    monkeypatch.setattr(a,'_submit',delayed)
    rows=[]
    t=Thread(target=lambda:rows.append(a.create('book','txt')))
    try:
        t.start();assert gate.wait(3)
        b=ExportJobService(tmp_path,lambda *args:(calls.append('b') or result('b')))
        b._pool.shutdown(wait=True);release.set();t.join(5);assert not t.is_alive()
        a._pool.shutdown(wait=True)
        assert calls==['b'] and a.get(rows[0]['id'])['status']=='succeeded'
    finally:
        release.set();t.join(5);a._pool.shutdown(wait=True)
        if b:b._pool.shutdown(wait=True)


def test_unsupported_platform_fails_closed_and_cleans_registry(tmp_path,monkeypatch):
    real_os=claims.os
    class Unsupported:
        name='unsupported-test-platform'
        def __getattr__(self,name):return getattr(real_os,name)
    monkeypatch.setattr(claims,'os',Unsupported())
    with pytest.raises(claims.ExportExecutionUnavailable,match='unsupported'):
        claims.try_execution_claim(tmp_path,'j')
    monkeypatch.setattr(claims,'os',real_os)
    acquire_release(tmp_path,'j')


def test_readers_of_terminal_job_never_attempt_execution_claim(tmp_path,monkeypatch):
    s=ExportJobService(tmp_path,lambda *args:result())
    row=s.create('book','txt',permission_context={'mode':'local','novel_id':'book'})
    s._pool.shutdown(wait=True)
    from app.services import export_job_service as service_module
    monkeypatch.setattr(service_module,'try_execution_claim',lambda *a:pytest.fail('GET acquired execution claim'))
    before={str(p.relative_to(tmp_path)):(p.read_bytes(),p.stat().st_mtime_ns) for p in tmp_path.rglob('*') if p.is_file()}
    reader=ExportJobService(tmp_path,lambda *args:pytest.fail('read-only renderer'))
    try:
        assert reader.get(row['id'])['status']=='succeeded'
        assert reader.list('book',permission_context={'mode':'local','novel_id':'book'})['items'][0]['id']==row['id']
        after={str(p.relative_to(tmp_path)):(p.read_bytes(),p.stat().st_mtime_ns) for p in tmp_path.rglob('*') if p.is_file()}
        assert before==after
    finally:reader._pool.shutdown(wait=True)
