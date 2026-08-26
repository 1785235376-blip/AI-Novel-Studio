from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import adaptation_service
from app.model_runtime import TextGenerationResponse,TextModelNodeOutput

def setup_novel(client):
    novel=client.post('/api/novels',json={'title':f'原作-{uuid4()}'}).json()
    client.post(f"/api/novels/{novel['id']}/chapters",json={'title':'第一章','content':'原始正文'})
    return novel

def test_adaptation_proposal_snapshots_source_without_mutating_chapters():
    client=TestClient(app);novel=setup_novel(client);before=client.get(f"/api/novels/{novel['id']}/chapters").json()
    created=client.post(f"/api/novels/{novel['id']}/adaptations",json={'target':'SCREEN','instruction':'压缩为六集'}).json()
    after=client.get(f"/api/novels/{novel['id']}/chapters").json()
    assert created['status']=='DRAFT' and created['source_chapter_count']==1
    assert created['blueprint']['format']=='影视改编蓝图'
    assert created['blueprint']['chapter_map'][0]['unit']=='第1集'
    detail=client.get(f"/api/chapters/{before[0]['id']}").json()
    assert created['source_versions']==[{'chapter_id':before[0]['id'],'version':detail['version']}]
    assert after==before

def test_adaptation_proposal_requires_supported_target_and_single_approval():
    client=TestClient(app);novel=setup_novel(client);url=f"/api/novels/{novel['id']}/adaptations"
    assert client.post(url,json={'target':'UNKNOWN'}).status_code==400
    created=client.post(url,json={'target':'COMMERCIAL','title':'商业版'}).json()
    approved=client.post(f"{url}/{created['id']}/approve").json()
    assert approved['status']=='APPROVED'
    assert client.post(f"{url}/{created['id']}/approve").status_code==400
    assert client.get(url).json()[0]['title']=='商业版'

def test_approved_adaptation_materializes_independent_version_once():
    client=TestClient(app);novel=setup_novel(client);url=f"/api/novels/{novel['id']}/adaptations"
    created=client.post(url,json={'target':'LITERARY','title':'文学改编版'}).json()
    assert client.post(f"{url}/{created['id']}/materialize").status_code==400
    client.post(f"{url}/{created['id']}/approve")
    first=client.post(f"{url}/{created['id']}/materialize").json();second=client.post(f"{url}/{created['id']}/materialize").json()
    assert first['id']==second['id'] and first['id']!=novel['id']
    copied=client.get(f"/api/novels/{first['id']}/chapters").json();original=client.get(f"/api/novels/{novel['id']}/chapters").json()
    assert len(copied)==1 and copied[0]['content'].endswith('原始正文') and original[0]['content'].endswith('原始正文')
    assert copied[0]['content'].count('# 第一章')==1
    stored=client.get(url).json()[0]
    assert stored['execution_status']=='PENDING_REWRITE' and stored['execution_manifest'][0]['status']=='PENDING_REWRITE'
    task=stored['execution_manifest'][0];draft=client.post(f"{url}/{created['id']}/tasks/{task['id']}/generate",json={'mode':'deterministic'}).json()
    assert draft['status']=='AWAITING_REVIEW' and draft['draft']['schema']=='adaptation_chapter_draft'
    assert client.post(f"{url}/{created['id']}/tasks/{task['id']}/review",json={'decision':'ACCEPTED'}).json()['status']=='ACCEPTED'
    applied=client.post(f"{url}/{created['id']}/tasks/{task['id']}/apply")
    assert applied.status_code==200 and applied.json()['status']=='APPLIED'
    assert client.post(f"{url}/{created['id']}/tasks/{task['id']}/apply").status_code==400

def test_blueprint_revision_preserves_source_identity_and_freezes_after_approval():
    client=TestClient(app);novel=setup_novel(client);url=f"/api/novels/{novel['id']}/adaptations";created=client.post(url,json={'target':'SCREEN'}).json();mapping=created['blueprint']['chapter_map'][0]
    body={**created['blueprint'],'focus':'新的改编重点','chapter_map':[{**mapping,'source_chapter_id':'forged','unit':'第2集','action':'重排冲突'}]}
    updated=client.put(f"{url}/{created['id']}/blueprint",json=body).json()
    assert updated['blueprint_revision']==2 and len(updated['blueprint_history'])==1
    assert updated['blueprint']['chapter_map'][0]['source_chapter_id']==mapping['source_chapter_id']
    client.post(f"{url}/{created['id']}/approve")
    assert client.put(f"{url}/{created['id']}/blueprint",json=body).status_code==400

def test_model_adaptation_draft_validates_contract_and_fails_closed(monkeypatch):
    client=TestClient(app);novel=setup_novel(client);url=f"/api/novels/{novel['id']}/adaptations";created=client.post(url,json={'target':'SCREEN','title':f'模型改编-{uuid4()}'}).json();client.post(f"{url}/{created['id']}/approve");materialized=client.post(f"{url}/{created['id']}/materialize");assert materialized.status_code==201,materialized.text;stored=next(item for item in client.get(url).json() if item['id']==created['id']);task=stored['execution_manifest'][0]
    class ValidNode:
        def execute(self,_):
            text='{"schema":"adaptation_chapter_draft","summary":"影视化重写","content":"改编后的可拍摄正文","source_chapter_id":"'+task['source_chapter_id']+'","source_version":'+str(task['source_version'])+'}'
            response=TextGenerationResponse(text,'completed','deepseek','deepseek-chat');return TextModelNodeOutput(text,response,task['id'])
    monkeypatch.setattr(adaptation_service.runtime,'prepare_text_route',lambda *_:ValidNode())
    generated=client.post(f"{url}/{created['id']}/tasks/{task['id']}/generate",json={'mode':'model','provider_id':'deepseek','model_id':'deepseek-chat'}).json()
    assert generated['status']=='AWAITING_REVIEW' and generated['draft']['content']=='改编后的可拍摄正文'

    second=setup_novel(client);second_url=f"/api/novels/{second['id']}/adaptations";proposal=client.post(second_url,json={'target':'SCREEN','title':f'失败关闭-{uuid4()}'}).json();client.post(f"{second_url}/{proposal['id']}/approve");second_materialized=client.post(f"{second_url}/{proposal['id']}/materialize");assert second_materialized.status_code==201,second_materialized.text;second_stored=next(item for item in client.get(second_url).json() if item['id']==proposal['id']);second_task=second_stored['execution_manifest'][0];before=client.get(f"/api/chapters/{second_task['target_chapter_id']}").json()['content']
    class InvalidNode:
        def execute(self,_):
            response=TextGenerationResponse('{"content":"missing contract"}','completed','deepseek','deepseek-chat');return TextModelNodeOutput(response.text,response,second_task['id'])
    monkeypatch.setattr(adaptation_service.runtime,'prepare_text_route',lambda *_:InvalidNode())
    failed=client.post(f"{second_url}/{proposal['id']}/tasks/{second_task['id']}/generate",json={'mode':'model','provider_id':'deepseek','model_id':'deepseek-chat'}).json()
    assert failed['status']=='FAILED' and failed['error_code']=='INVALID_ADAPTATION_DRAFT'
    assert client.get(f"/api/chapters/{second_task['target_chapter_id']}").json()['content']==before
