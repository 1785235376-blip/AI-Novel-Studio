from types import SimpleNamespace
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.services.import_review_service import ImportReviewService


def test_import_excerpt_confirmation_does_not_waive_stored_secrets(tmp_path,monkeypatch):
    import app.api as api
    service=ImportReviewService(tmp_path)
    review=service.ensure_pending('n',{})
    monkeypatch.setattr(api,'import_review_service',service)
    chapter={'id':'n:1','novel_id':'n','version':1,'number':1,'title':'Synthetic','content':'STORED_SECRET_CANARY'}
    novels=SimpleNamespace(get=lambda nid:{'id':nid,'title':'Synthetic'},chapters=SimpleNamespace(list=lambda nid:[chapter]),public_secrets=lambda nid:[{'id':'s','visibility':'LOCAL_ONLY'}],data_set=lambda *args:[],outline=lambda nid:{})
    monkeypatch.setattr(api,'novel_service',novels)
    monkeypatch.setattr(api,'settings',SimpleNamespace(enable_collaboration_runtime=False))
    called=[]
    monkeypatch.setattr(api.runtime,'is_remote_text_provider',lambda pid:True)
    monkeypatch.setattr(api.runtime.generation_runtime.text_node,'execute',lambda value:called.append(value))
    app=FastAPI();app.include_router(api.router,prefix='/api');client=TestClient(app)
    route=f'/api/novels/n/import/knowledge-base/review/{review["id"]}/ai-analyze'
    assert client.post(route,json={}).status_code==403
    response=client.post(route,json={'allow_cloud_excerpt':True})
    assert response.status_code==403 and response.json()['detail']['code']=='IMPORT_SOURCE_RESTRICTED'
    assert called==[]


def test_review_requires_revision_and_empty_selection_does_not_apply_all(tmp_path,monkeypatch):
    import app.api as api
    service=ImportReviewService(tmp_path)
    review=service.ensure_pending('n',{'characters':[{'name':'Should not be accepted'}]})
    monkeypatch.setattr(api,'import_review_service',service)
    called=[]
    monkeypatch.setattr(api,'novel_service',SimpleNamespace(get=lambda nid:{'id':nid},review_import_knowledge=lambda nid,decision,selected:called.append(selected) or {'decision':decision,'applied':selected}))
    monkeypatch.setattr(api,'settings',SimpleNamespace(enable_collaboration_runtime=False))
    app=FastAPI();app.include_router(api.router,prefix='/api');client=TestClient(app)
    route='/api/novels/n/import/knowledge-base/review'
    assert client.post(route,json={'review_id':review['id'],'decision':'ACCEPTED'}).status_code==428
    result=client.post(route,json={'review_id':review['id'],'decision':'ACCEPTED','expected_version':1,'candidates':{},'selected':{'characters':[False]}})
    assert result.status_code==200 and called==[]
    repeated=client.post(route,json={'review_id':review['id'],'decision':'ACCEPTED','expected_version':1})
    assert repeated.status_code==200 and called==[]
