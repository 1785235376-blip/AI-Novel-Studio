from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app

def setup(client):
    n=client.post('/api/novels',json={'title':f'镜头源-{uuid4()}'}).json();client.post(f"/api/novels/{n['id']}/chapters",json={'title':'第一场','content':'人物进入房间。'});s=client.post(f"/api/novels/{n['id']}/screenplays",json={}).json();client.post(f"/api/novels/{n['id']}/screenplays/{s['id']}/approve");return n,s

def test_shot_plan_has_required_fields_and_freezes():
    c=TestClient(app);n,s=setup(c);url=f"/api/novels/{n['id']}/screenplays/{s['id']}";planned=c.post(url+'/shots').json();shot=planned['shots'][0]
    assert shot['number']==11 and shot['shot_size']=='MEDIUM' and shot['duration_seconds']==5
    updated=c.put(url+f"/shots/{shot['id']}",json={**shot,'shot_size':'CLOSE_UP','duration_seconds':8}).json();assert updated['shots'][0]['shot_size']=='CLOSE_UP'
    assert c.post(url+'/shots/approve').json()['shot_status']=='APPROVED'
    assert c.put(url+f"/shots/{shot['id']}",json={**shot,'shot_size':'WIDE'}).status_code==400
