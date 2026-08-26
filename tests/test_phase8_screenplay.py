from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app

def setup_novel(client):
    novel=client.post('/api/novels',json={'title':f'影视源-{uuid4()}'}).json();client.post(f"/api/novels/{novel['id']}/chapters",json={'title':'第一章 港口','content':'林舟进入港口。'});return novel

def test_screenplay_creation_locks_source_and_exposes_structured_fields():
    client=TestClient(app);novel=setup_novel(client);created=client.post(f"/api/novels/{novel['id']}/screenplays",json={}).json();scene=created['scenes'][0]
    assert created['status']=='DRAFT' and created['revision']==1
    assert scene['heading']=='第一章 港口' and scene['source_version']==1
    assert set(('time','location','characters','action','dialogue','emotion'))<=set(scene)

def test_screenplay_scene_edit_preserves_source_identity_and_freezes_after_approval():
    client=TestClient(app);novel=setup_novel(client);base=f"/api/novels/{novel['id']}/screenplays";created=client.post(base,json={'title':'六集剧本'}).json();scene=created['scenes'][0]
    body={'heading':'港口相遇','time':'夜','location':'雾港码头','characters':['林舟'],'action':'林舟穿过封锁线。','dialogue':[{'character':'林舟','text':'有人吗？'}],'emotion':'警惕','source_chapter_id':'forged'}
    updated=client.put(f"{base}/{created['id']}/scenes/{scene['id']}",json=body).json();changed=updated['scenes'][0]
    assert updated['revision']==2 and changed['source_chapter_id']==scene['source_chapter_id'] and changed['location']=='雾港码头'
    assert client.post(f"{base}/{created['id']}/approve").json()['status']=='APPROVED'
    assert client.put(f"{base}/{created['id']}/scenes/{scene['id']}",json=body).status_code==400
