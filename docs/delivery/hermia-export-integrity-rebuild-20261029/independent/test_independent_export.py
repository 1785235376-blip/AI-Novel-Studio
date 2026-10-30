import base64
import json
import multiprocessing
import os
from pathlib import Path
import time
from types import SimpleNamespace
import pytest
from app.services.export_job_service import ExportJobService, ExportJobResultInvalid

@pytest.fixture
def ready(tmp_path):
    svc=ExportJobService(tmp_path,lambda *_:{'content':'独立原文','format':'txt'})
    row=svc.create('independent-synthetic','txt',permission_context={'mode':'local','novel_id':'independent-synthetic'})
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        row=svc.get(row['id'])
        if row['status'] in ('succeeded','failed'): break
        time.sleep(.01)
    assert row['status']=='succeeded'
    svc._pool.shutdown(wait=True)
    yield svc,row

def edit(svc,row,kind):
    doc=json.loads(svc.path.read_text())
    item=doc[row['id']]
    if kind=='inline': item['result']['content']='different'
    elif kind=='size': item['artifact']['size']+=1
    elif kind=='legacy': item.pop('artifact')
    svc.path.write_text(json.dumps(doc,ensure_ascii=False))

@pytest.mark.parametrize('kind',['inline','size'])
def test_receipt_on_missing_file(ready,kind):
    svc,row=ready
    (svc.artifact_root/row['artifact']['path']).unlink()
    edit(svc,row,kind)
    with pytest.raises(ExportJobResultInvalid): svc.download(row['id'])

@pytest.mark.parametrize('kind',['valid','legacy'])
def test_compatibility_read_no_write(ready,kind):
    svc,row=ready
    (svc.artifact_root/row['artifact']['path']).unlink()
    if kind=='legacy':edit(svc,row,kind)
    before=svc.path.read_bytes()
    assert svc.download(row['id'])['content']=='独立原文'.encode()
    assert svc.path.read_bytes()==before

@pytest.mark.parametrize('prefix',['/api','/api/v1'])
def test_http_rejects_corrupt_fallback(ready,monkeypatch,prefix):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import app.api as api
    svc,row=ready
    (svc.artifact_root/row['artifact']['path']).unlink()
    edit(svc,row,'inline')
    monkeypatch.setattr(api,'settings',SimpleNamespace(enable_collaboration_runtime=False))
    monkeypatch.setattr(api,'export_job_service',svc)
    app=FastAPI();app.include_router(api.router,prefix=prefix)
    with TestClient(app) as client: response=client.get(f'{prefix}/exports/{row["id"]}/download')
    assert response.status_code==500
    assert response.json()['detail']['code']=='EXPORT_RESULT_INVALID'
    assert 'different' not in response.text

@pytest.mark.parametrize('named',[True,False])
def test_predecode_admission(monkeypatch,named):
    monkeypatch.setattr(ExportJobService,'MAX_RESULT_BYTES',4)
    calls=[]
    original=base64.b64decode
    def traced(*a,**kw):calls.append(1);return original(*a,**kw)
    monkeypatch.setattr(base64,'b64decode',traced)
    payload={('content_base64' if named else 'content'):'YWJjYWJjYWJj','content_encoding':'base64'}
    with pytest.raises(ExportJobResultInvalid):ExportJobService._result_bytes(payload)
    assert calls==[]

@pytest.mark.parametrize('payload',[b'',b'a',b'abc',b'abcd'])
def test_legacy_valid_boundary(monkeypatch,payload):
    monkeypatch.setattr(ExportJobService,'MAX_RESULT_BYTES',4)
    assert ExportJobService._result_bytes({'content':base64.b64encode(payload).decode(),'content_encoding':'base64'})==payload

def child(root,job,target,mode,out):
    target=Path(target)
    if mode.startswith('swap'):
        orig=Path.stat
        swapped=False
        def changing(p,*a,**kw):
            nonlocal swapped
            result=orig(p,*a,**kw)
            if p==target and not swapped:
                swapped=True;p.unlink()
                if mode=='swapfifo':os.mkfifo(p)
                else:p.mkdir()
            return result
        Path.stat=changing
    svc=ExportJobService(Path(root),lambda *_:{})
    try:
        try:svc.download(job)
        except ExportJobResultInvalid:out.put('invalid')
        except Exception as e:out.put(type(e).__name__)
        else:out.put('returned')
    finally:svc._pool.shutdown(wait=True)

@pytest.mark.skipif(os.name!='posix',reason='synthetic POSIX special files')
@pytest.mark.parametrize('mode',['fifo','directory','swapfifo','swapdirectory'])
def test_special_file_and_open_window(ready,mode):
    svc,row=ready
    target=svc.artifact_root/row['artifact']['path']
    if mode in ('fifo','directory'):
        target.unlink()
        if mode=='fifo':os.mkfifo(target)
        else:target.mkdir()
    ctx=multiprocessing.get_context('fork');out=ctx.Queue()
    proc=ctx.Process(target=child,args=(str(svc.path.parent),row['id'],str(target),mode,out))
    proc.start();proc.join(3)
    try:
        assert not proc.is_alive(),'special-file open exceeded watchdog'
        assert proc.exitcode==0
        assert out.get(timeout=1)=='invalid'
    finally:
        if proc.is_alive():proc.kill();proc.join(3)
        out.close()
