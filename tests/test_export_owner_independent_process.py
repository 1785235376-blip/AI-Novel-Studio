"""Original export writer races; no real export/model/background job execution."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import pytest

WORKER = r'''
import sys,time,json
from pathlib import Path
from app.services.export_job_service import ExportJobService
root,control,role,key=map(str,sys.argv[1:]);root=Path(root);control=Path(control)
def wait(name):
 deadline=time.monotonic()+30
 while not (control/name).exists():
  if time.monotonic()>deadline:raise RuntimeError('control timeout '+name)
  time.sleep(.01)
ExportJobService._submit=lambda self,jid:None
s=ExportJobService(root,lambda *a: (_ for _ in ()).throw(AssertionError('exporter must never run')))
try:
 (control/(role+'-ready')).touch();wait(role+'-go')
 if role=='a':
  original=s._read
  first=[True]
  def gated():
   value=original()
   if first[0]:
    first[0]=False;(control/'a-read').touch();wait('a-release')
   return value
  s._read=gated
 row=s.create('book','txt',key,permission_context={'mode':'collaboration','novel_id':'book','workspace_id':'w','storyline_id':'s','branch_id':'b','actor_id':'actor'})
 (control/(role+'-result')).write_text(json.dumps(row))
 (control/(role+'-done')).touch()
finally:s._pool.shutdown(wait=True)
'''


def wait_file(path,timeout=30):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if path.exists():return True
        time.sleep(.01)
    return False


@pytest.mark.parametrize('same_key',[False,True])
def test_original_export_create_serializes_independent_processes(tmp_path,same_key):
    data=tmp_path/'data';data.mkdir();control=tmp_path/'control';control.mkdir()
    source=Path(__file__).resolve().parents[1]
    children=[]
    try:
        for role in ('a','b'):
            key='same' if same_key else role
            children.append(subprocess.Popen([sys.executable,'-c',WORKER,str(data),str(control),role,key],cwd=source,env={**os.environ,'PYTHONPATH':str(source)},stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True))
        assert wait_file(control/'a-ready') and wait_file(control/'b-ready')
        (control/'a-go').touch();assert wait_file(control/'a-read')
        (control/'b-go').touch()
        # Old independent RLocks let B commit over A's retained snapshot.
        # A serialized owner instead keeps B blocked until A releases.
        wait_file(control/'b-done',3)
        (control/'a-release').touch()
        for child in children:
            stdout,stderr=child.communicate(timeout=30)
            assert child.returncode==0,(stdout,stderr)
        a=json.loads((control/'a-result').read_text());b=json.loads((control/'b-result').read_text())
        rows=json.loads((data/'export_jobs.json').read_text(encoding='utf-8'))
        if same_key:
            assert a['id']==b['id'],'same idempotency key created two logical jobs'
        else:
            assert a['id'] in rows and b['id'] in rows,'one original committed job was lost'
    finally:
        (control/'a-release').touch()
        for child in children:
            if child.poll() is None:child.kill()
            child.communicate(timeout=10)


@pytest.fixture
def owner(tmp_path,monkeypatch):
    from app.services.export_job_service import ExportJobService
    monkeypatch.setattr(ExportJobService,'_submit',lambda self,jid:None)
    service=ExportJobService(tmp_path/'owner',lambda *a:pytest.fail('real exporter forbidden'))
    try:yield service
    finally:service._pool.shutdown(wait=True)


def seed_terminal(s):
    row={'id':'terminal','novel_id':'book','status':'succeeded','created_at':'2026-01-01T00:00:00Z','permission_context':{'mode':'local','novel_id':'book','actor_id':'a'},'result':None}
    s._write({'terminal':row});return row


def test_private_metadata_never_changes_original_read_or_public_map(owner):
    row=seed_terminal(owner)
    assert owner._read()=={'terminal':row}
    observed=owner.binding_observation(['terminal'])
    assert observed
    assert owner.get('terminal')['id']=='terminal'
    assert '_export_lifecycle_v1' not in owner.get('terminal')
    assert '_export_lifecycle_v1' not in owner.public(owner.get('terminal'))
    before=owner.path.read_bytes();assert owner.binding_observation(['terminal'])==observed
    assert owner.path.read_bytes()==before


def test_legacy_file_remains_unbound_without_read_write_migration(owner):
    row=seed_terminal(owner)
    owner.path.write_text(json.dumps({'terminal':row}))
    before=owner.path.read_bytes()
    with pytest.raises(ValueError):owner.binding_observation(['terminal'])
    assert owner.path.read_bytes()==before
    owner._write({'terminal':{**row,'status':'failed'}})
    with pytest.raises(ValueError):owner.binding_observation(['terminal'])
    assert '_export_lifecycle_v1' not in json.loads(owner.path.read_text())


def test_reserved_null_injection_rejected_without_business_write(owner):
    seed_terminal(owner);before=owner.path.read_bytes()
    with pytest.raises(ValueError):owner._write({**owner._read(),'_export_lifecycle_v1':None})
    assert owner.path.read_bytes()==before


def test_selected_row_aba_invalidates_but_unrelated_write_does_not(owner):
    row=seed_terminal(owner);before=owner.binding_observation(['terminal'])
    owner._write({'terminal':row,'other':{**row,'id':'other'}})
    assert owner.binding_observation(['terminal'])==before
    owner._write({'terminal':{**row,'status':'failed'},'other':{**row,'id':'other'}})
    owner._write({'terminal':row,'other':{**row,'id':'other'}})
    assert owner.binding_observation(['terminal'])!=before


def test_before_atomic_write_failure_preserves_document_and_nonce(owner,monkeypatch):
    from app.services import export_job_service as module
    row=seed_terminal(owner);before=owner.path.read_bytes();observed=owner.binding_observation(['terminal'])
    def fail(*args,**kwargs):raise OSError('synthetic before-commit failure')
    monkeypatch.setattr(module,'atomic_write',fail)
    with pytest.raises(OSError):owner._write({'terminal':{**row,'status':'failed'}})
    assert owner.path.read_bytes()==before
    assert owner.binding_observation(['terminal'])==observed


CRASH_WORKER=r'''
import sys,time
from pathlib import Path
from app.services import export_job_service as m
root,control,point=sys.argv[1:];control=Path(control)
m.ExportJobService._submit=lambda self,jid:None
s=m.ExportJobService(Path(root),lambda *a: (_ for _ in ()).throw(AssertionError('real exporter forbidden')))
original=m.atomic_write
def gate(*a,**kw):
 if point=='after':original(*a,**kw)
 (control/'at-boundary').touch()
 while True:time.sleep(.1)
m.atomic_write=gate
rows=s._read();rows['terminal']['status']='failed';s._write(rows)
'''


@pytest.mark.skipif(os.name=='nt',reason='SIGKILL is POSIX-specific; not a Windows crash claim')
@pytest.mark.parametrize('point',['before','after'])
def test_original_commit_sigkill_matches_selected_nonce(owner,tmp_path,point):
    seed_terminal(owner);before=owner.path.read_bytes();observed=owner.binding_observation(['terminal'])
    control=tmp_path/'kill-control';control.mkdir();source=Path(__file__).resolve().parents[1]
    child=subprocess.Popen([sys.executable,'-c',CRASH_WORKER,str(owner.path.parent),str(control),point],cwd=source,env={**os.environ,'PYTHONPATH':str(source)},stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        assert wait_file(control/'at-boundary')
        child.kill();stdout,stderr=child.communicate(timeout=15);assert child.returncode<0,(stdout,stderr)
        now=owner.binding_observation(['terminal'])
        if point=='before':
            assert owner.path.read_bytes()==before and now==observed
        else:
            assert owner.get('terminal')['status']=='failed' and now!=observed
        # The OS lock must be released after abrupt death.
        rows=owner._read();rows['terminal']['status']='succeeded';owner._write(rows)
        assert owner.get('terminal')['status']=='succeeded'
    finally:
        if child.poll() is None:child.kill()
        child.communicate(timeout=10)


def test_original_startup_recovery_and_cancel_still_advance_selected_evidence(owner):
    from app.services.export_job_service import ExportJobService
    job=owner.create('book','txt','recovery',permission_context={'mode':'local','novel_id':'book','actor_id':'a'})
    first=owner.binding_observation([job['id']])
    restarted=ExportJobService(owner.path.parent,lambda *a:pytest.fail('real exporter forbidden'))
    try:
        recovered=restarted.get(job['id'])
        assert recovered['status']=='queued' and recovered['recovery_count']==1
        after=restarted.binding_observation([job['id']]);assert after!=first
        cancelled=restarted.cancel(job['id'])
        assert cancelled['status']=='cancelled'
        assert restarted.binding_observation([job['id']])!=after
    finally:restarted._pool.shutdown(wait=True)


def test_malformed_lifecycle_observation_fails_closed_without_repair(owner):
    seed_terminal(owner);document=json.loads(owner.path.read_text());document['_export_lifecycle_v1']=None
    owner.path.write_text(json.dumps(document));before=owner.path.read_bytes()
    with pytest.raises(ValueError):owner.binding_observation(['terminal'])
    assert owner.path.read_bytes()==before
