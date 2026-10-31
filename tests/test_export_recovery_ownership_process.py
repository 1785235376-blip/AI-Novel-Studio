"""Original create/worker/startup recovery, real isolated child processes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

WORKER = r'''
import json, sys, time
from pathlib import Path
from app.services.export_job_service import ExportJobService
root, control, role = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
def exporter(novel_id, fmt):
    (control / (role + '-entered')).write_text(json.dumps({'novel_id':novel_id,'format':fmt}))
    end = time.monotonic() + 30
    while not (control / (role + '-release')).exists():
        if time.monotonic() > end: raise RuntimeError('synthetic control timeout')
        time.sleep(.01)
    return {'content': role, 'filename':'synthetic.txt','format':fmt}
s = ExportJobService(root, exporter)
(control / (role + '-constructed')).touch()
if role == 'a':
    row = s.create('synthetic-book','txt','synthetic-key')
    (control / 'job.json').write_text(json.dumps(row))
s._pool.shutdown(wait=True)
(control / (role + '-rows.json')).write_text(json.dumps(s._read()))
'''

def wait(path, timeout=15):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if path.exists(): return True
        time.sleep(.01)
    return False


def launch(root, control, role):
    source=Path(__file__).resolve().parents[1]
    return subprocess.Popen([sys.executable,'-c',WORKER,str(root),str(control),role],cwd=source,
        env={**os.environ,'PYTHONPATH':str(source)},stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)


def finish(child):
    out,err=child.communicate(timeout=20)
    assert child.returncode==0,(out,err)


def clean(children,control):
    for role in ('a','b'): (control/(role+'-release')).touch()
    for child in children:
        if child.poll() is None: child.kill()
        child.communicate(timeout=10)


def test_second_process_must_not_recover_live_exporter(tmp_path):
    root=tmp_path/'data'; root.mkdir(); control=tmp_path/'control';control.mkdir();children=[]
    try:
        a=launch(root,control,'a');children.append(a)
        assert wait(control/'a-entered') and wait(control/'job.json')
        job_id=json.loads((control/'job.json').read_text())['id']
        before=json.loads((root/'export_jobs.json').read_text())[job_id]
        assert before['status']=='running' and before['recovery_count']==0 and a.poll() is None
        b=launch(root,control,'b');children.append(b)
        assert wait(control/'b-constructed')
        duplicated=wait(control/'b-entered',1)
        during=json.loads((root/'export_jobs.json').read_text())[job_id]
        (control/'b-release').touch(); finish(b)
        after_b=json.loads((root/'export_jobs.json').read_text())[job_id]
        assert a.poll() is None
        (control/'a-release').touch();finish(a)
        final=json.loads((root/'export_jobs.json').read_text())[job_id]
        print(json.dumps({'live_duplicate':duplicated,'before_recovery':before['recovery_count'],
            'during_recovery':during['recovery_count'],'after_b_content':(after_b.get('result') or {}).get('content'),
            'final_content':(final.get('result') or {}).get('content')},sort_keys=True))
        assert not duplicated, 'startup B invoked the same exporter while A remained alive and paused'
        assert during['recovery_count']==0
        assert final['result']['content']=='a'
    finally: clean(children,control)


@pytest.mark.skipif(os.name=='nt',reason='This contrast uses POSIX SIGKILL, not Windows evidence')
def test_dead_process_original_job_is_recovered(tmp_path):
    root=tmp_path/'data';root.mkdir();control=tmp_path/'control';control.mkdir();children=[]
    try:
        a=launch(root,control,'a');children.append(a)
        assert wait(control/'a-entered') and wait(control/'job.json')
        job_id=json.loads((control/'job.json').read_text())['id']
        a.kill();a.communicate(timeout=10);assert a.returncode<0
        b=launch(root,control,'b');children.append(b)
        assert wait(control/'b-entered')
        (control/'b-release').touch();finish(b)
        final=json.loads((root/'export_jobs.json').read_text())[job_id]
        assert final['status']=='succeeded' and final['recovery_count']==1
        assert final['result']['content']=='b'
    finally:clean(children,control)


def test_two_recovery_processes_do_not_replay_same_dead_job(tmp_path):
    root=tmp_path/'data';root.mkdir();control=tmp_path/'control';control.mkdir();children=[]
    try:
        a=launch(root,control,'a');children.append(a)
        assert wait(control/'a-entered') and wait(control/'job.json')
        job_id=json.loads((control/'job.json').read_text())['id']
        a.kill();a.communicate(timeout=10)
        for role in ('b','c'): children.append(launch(root,control,role))
        assert wait(control/'b-constructed') and wait(control/'c-constructed')
        assert wait(control/'b-entered',1) or wait(control/'c-entered',1)
        entered=[role for role in ('b','c') if (control/(role+'-entered')).exists()]
        for role in ('b','c'): (control/(role+'-release')).touch()
        for child in children[1:]:finish(child)
        assert len(entered)==1
        final=json.loads((root/'export_jobs.json').read_text())[job_id]
        assert final['recovery_count']==1 and final['result']['content']==entered[0]
    finally:
        (control/'c-release').touch();clean(children,control)


def test_other_job_and_cancellation_do_not_wait_for_exporter(tmp_path):
    root=tmp_path/'data';root.mkdir();control=tmp_path/'control';control.mkdir();children=[]
    try:
        a=launch(root,control,'a');children.append(a)
        assert wait(control/'a-entered') and wait(control/'job.json')
        job_id=json.loads((control/'job.json').read_text())['id']
        source=Path(__file__).resolve().parents[1]
        script=r'''
import sys,json,time
from pathlib import Path
from app.services.export_job_service import ExportJobService
root,control,jid=Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3]
calls=[]
def exporter(book,fmt):
 calls.append(book)
 return {'content':'independent','filename':'independent.txt'}
s=ExportJobService(root,exporter)
row=s.create('other-book','txt')
s._pool.shutdown(wait=True)
assert calls==['other-book'],calls
assert s.get(row['id'])['status']=='succeeded'
s.cancel(jid)
(control/'independent-finished').touch()
'''
        child=subprocess.Popen([sys.executable,'-c',script,str(root),str(control),job_id],cwd=source,env={**os.environ,'PYTHONPATH':str(source)},stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);children.append(child)
        finish(child)
        assert (control/'independent-finished').exists() and a.poll() is None
        (control/'a-release').touch();finish(a)
        final=json.loads((root/'export_jobs.json').read_text())[job_id]
        assert final['status']=='cancelled' and final['result'] is None
    finally:clean(children,control)
