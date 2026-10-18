"""Mounted original Research routes with real native OCR and live fences."""
from types import SimpleNamespace
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.experimental.research_library_api import create_research_library_router
from test_v2_independent_workspace import rig
from test_research_native_ocr_coordinator_additive import setup
from test_research_ocr_job_execution_additive import wait


def mounted(e,c):
    state={'review':False,'token':'valid','enabled':True}
    def authorize(nid,token,branch,permission):
        if nid!=e.nid or token!=state['token'] or branch!='current':raise HTTPException(403,'denied')
        if permission=='domain.review' and not state['review']:raise HTTPException(403,'review denied')
        return e.actor,e.scope
    def flag(name):
        if not state['enabled']:raise HTTPException(404,'disabled')
    app=FastAPI();app.include_router(create_research_library_router(c.research,authorize,flag))
    return TestClient(app),state,{'X-Session-Token':'valid','X-Branch-ID':'current'},f'/novels/{e.nid}/experimental/research-library/analysis/jobs/{c.analysis["id"]}'


def test_mounted_native_preview_dispatch_review_and_poll(rig,monkeypatch):
    c=setup(rig,monkeypatch);client,state,headers,path=mounted(rig,c)
    with client:
        response=client.post(path+'/native-preview',headers=headers,json={'expected_version':1,'provider_id':'native-ocr','model_id':'eng','language':'eng'})
        assert response.status_code==200,response.text
        ready=response.json();assert response.headers['cache-control']=='no-store'
        response=client.post(path+'/native-dispatch',headers=headers,json={'expected_version':ready['version'],
            'reviewed_preview_digest':ready['native_ocr_preview']['reviewed_preview_digest'],'idempotency_key':'http'})
        assert response.status_code==200,response.text
        job=c.manager.get(response.json()['native_ocr_execution']['generation_id']);wait(SimpleNamespace(job=job))
        result=client.get(path,headers=headers);assert result.status_code==200,result.text
        row=result.json();assert row['status']=='REVIEW_REQUIRED'
        assert client.post(path+'/review',headers=headers,json={'expected_version':row['version']}).status_code==403
        state['review']=True
        reviewed=client.post(path+'/review',headers=headers,json={'expected_version':row['version']})
        assert reviewed.status_code==200,reviewed.text
        assert reviewed.json()['status']=='REVIEWED'
        row=reviewed.json()
        exported=client.get(path+'/native-export',headers=headers,params={'expected_version':row['version'],'result_digest':row['result_digest']})
        assert exported.status_code==200,exported.text
        assert exported.content==b'STUDIO OCR 123\n'
        assert exported.headers['cache-control']=='no-store'
        assert exported.headers['content-disposition']=='attachment; filename="research-ocr.txt"'
        assert exported.headers['x-content-type-options']=='nosniff'
        assert client.get(path,headers={'X-Session-Token':'invalid','X-Branch-ID':'current'}).status_code==403


def test_native_route_unconfigured_and_disabled_fail_without_jobs(rig,monkeypatch):
    c=setup(rig,monkeypatch);client,state,headers,path=mounted(rig,c)
    c.research.native_ocr=None
    with client:
        body={'expected_version':1,'provider_id':'native-ocr','model_id':'eng','language':'eng'}
        response=client.post(path+'/native-preview',headers=headers,json=body)
        assert response.status_code==409,response.text
        state['enabled']=False
        assert client.post(path+'/native-dispatch',headers=headers,content='invalid-json').status_code==404
    assert c.manager.jobs=={} and c.broker.ledger(rig.nid,rig.scope,rig.actor)==[]
