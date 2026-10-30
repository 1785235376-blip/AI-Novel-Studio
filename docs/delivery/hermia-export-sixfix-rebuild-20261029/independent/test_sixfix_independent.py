import base64
import json
import time
from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import pytest
from app.export_formats import novel_to_docx, novel_to_epub
from app.services.export_job_service import ExportJobService, ExportJobResultInvalid

@pytest.mark.parametrize('exporter', [novel_to_docx, novel_to_epub])
@pytest.mark.parametrize('bad', ['\ufffe','\uffff'])
def test_xml_parts_are_parseable(exporter,bad):
    safe='中文 😺 <&> \U0001fffe'
    data=exporter(safe+bad,[{'title':'章'+bad,'content':safe+bad}])
    texts=[]
    with ZipFile(BytesIO(data)) as z:
        for name in z.namelist():
            if name.endswith(('.xml','.rels','.opf','.xhtml')):
                root=ET.fromstring(z.read(name)); texts.extend(root.itertext())
    joined=''.join(texts)
    assert bad not in joined
    assert safe in joined

@pytest.mark.parametrize('size',range(1,8))
def test_actual_binary_budget_not_encoded_text(monkeypatch,tmp_path,size):
    monkeypatch.setattr(ExportJobService,'MAX_RESULT_BYTES',size)
    payload=b'z'*size
    for index,result in enumerate(({'content':payload},{'content_base64':base64.b64encode(payload).decode()},{'content':base64.b64encode(payload).decode(),'content_encoding':'base64'})):
        svc=ExportJobService(tmp_path/str(index),lambda *_args, r=result:r)
        try:
            job=svc.create('n','txt')
            for _ in range(300):
                row=svc.get(job['id'])
                if row['status'] in ('succeeded','failed'):break
                time.sleep(.005)
            assert row['status']=='succeeded',row.get('error')
            assert svc.download(job['id'])['content']==payload
        finally: svc._pool.shutdown(wait=True)

@pytest.mark.parametrize('alias,canonical',[('text','txt'),('md','markdown'),('word','docx'),('screenplay-standard','screenplay-fountain')])
def test_alias_replay_same_snapshot(tmp_path,alias,canonical):
    captures=[]
    svc=ExportJobService(tmp_path,lambda *_:{'content':'ok'},snapshotter=lambda n,f: captures.append((n,f)) or {'snapshot_id':'once'})
    try:
        a=svc.create('n',alias,'key');b=svc.create('n',canonical,'key')
        assert a['id']==b['id']; assert len(captures)==1
    finally:svc._pool.shutdown(wait=True)

def test_format_conflict_does_not_write_or_capture(tmp_path):
    captures=[]
    svc=ExportJobService(tmp_path,lambda *_:{'content':'ok'},snapshotter=lambda n,f: captures.append((n,f)) or {'snapshot_id':'once'})
    try:
        svc.create('n','txt','key');svc._pool.shutdown(wait=True)
        before=svc.path.read_bytes()
        with pytest.raises(ValueError,match='EXPORT_IDEMPOTENCY_FORMAT_CONFLICT'):svc.create('n','json','key')
        assert svc.path.read_bytes()==before;assert len(captures)==1
    finally:svc._pool.shutdown(wait=True)

def test_scope_and_expiry_still_separate(tmp_path):
    svc=ExportJobService(tmp_path,lambda *_:{'content':'ok'})
    try:
        a=svc.create('n','txt','key',permission_context={'actor':'a'})
        b=svc.create('n','json','key',permission_context={'actor':'b'})
        c=svc.create('m','json','key',permission_context={'actor':'a'})
        assert len({a['id'],b['id'],c['id']})==3
        svc._pool.shutdown(wait=True)
        with svc._mutation():
            rows=svc._read();rows[a['id']]['created_at']=(datetime.now(timezone.utc)-timedelta(hours=25)).isoformat();svc._write(rows)
        # Expired row no longer blocks another format (capture and submit disabled).
        svc._submit=lambda *_:None
        d=svc.create('n','json','key',permission_context={'actor':'a'})
        assert d['id']!=a['id']
    finally:svc._pool.shutdown(wait=True)

def test_concurrent_changed_format_one_owner(tmp_path):
    svc=ExportJobService(tmp_path,lambda *_:{'content':'ok'})
    def create(fmt):
        try:return svc.create('n',fmt,'key')
        except ValueError as e:return str(e)
    try:
        with ThreadPoolExecutor(2) as p: answers=list(p.map(create,['txt','json']))
        rows=[x for x in answers if isinstance(x,dict)]
        assert len(rows)==1
        assert 'EXPORT_IDEMPOTENCY_FORMAT_CONFLICT' in answers
        assert len(svc._read())==1
    finally:svc._pool.shutdown(wait=True)

@pytest.mark.parametrize('field',['content','content_base64'])
def test_existing_decode_admission_not_regressed(monkeypatch,field):
    monkeypatch.setattr(ExportJobService,'MAX_RESULT_BYTES',3)
    def forbidden(*a,**k): raise AssertionError('decoder called before admission')
    monkeypatch.setattr(base64,'b64decode',forbidden)
    with pytest.raises(ExportJobResultInvalid,match='limit'):
        ExportJobService._result_bytes({field:'YWJjYWJj','content_encoding':'base64'})

@pytest.mark.parametrize('field',['content','content_base64'])
def test_actual_decoded_overlimit_still_rejected(monkeypatch,field):
    monkeypatch.setattr(ExportJobService,'MAX_RESULT_BYTES',1)
    with pytest.raises(ValueError):
        ExportJobService._serialise_result({field:'YWE=','content_encoding':'base64'})

@pytest.mark.parametrize('prefix',['/api','/api/v1'])
def test_mounted_http_format_conflict(monkeypatch,tmp_path,prefix):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from types import SimpleNamespace
    import app.api as api
    svc=ExportJobService(tmp_path,lambda *_:{'content':'ok'})
    monkeypatch.setattr(api,'settings',SimpleNamespace(enable_collaboration_runtime=False))
    monkeypatch.setattr(api,'export_job_service',svc)
    monkeypatch.setattr(api,'novel_service',SimpleNamespace(get=lambda n:{'id':n}))
    app=FastAPI();app.include_router(api.router,prefix=prefix)
    try:
        with TestClient(app) as client:
            headers={'Idempotency-Key':'same'}
            a=client.post(prefix+'/exports?novel_id=n',json={'format':'text'},headers=headers)
            assert a.status_code==202,a.text
            b=client.post(prefix+'/exports?novel_id=n',json={'format':'json'},headers=headers)
            assert b.status_code==400,b.text
            assert b.json()['detail']=='EXPORT_IDEMPOTENCY_FORMAT_CONFLICT'
            c=client.post(prefix+'/exports?novel_id=n',json={'format':'txt'},headers=headers)
            assert c.status_code==202 and c.json()['id']==a.json()['id']
    finally:svc._pool.shutdown(wait=True)
