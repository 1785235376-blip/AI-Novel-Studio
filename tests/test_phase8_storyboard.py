from fastapi.testclient import TestClient
from app.main import app

def test_storyboard_lifecycle():
    client=TestClient(app)
    novel=client.post('/api/novels',json={'title':'分镜测试'}).json(); nid=novel['id']
    client.post(f'/api/novels/{nid}/chapters',json={'title':'第一章','content':'内容'})
    sp=client.post(f'/api/novels/{nid}/screenplays',json={'title':'剧本'}).json(); sid=sp['id']
    client.post(f'/api/novels/{nid}/screenplays/{sid}/approve')
    client.post(f'/api/novels/{nid}/screenplays/{sid}/shots')
    client.post(f'/api/novels/{nid}/screenplays/{sid}/shots/approve')
    board=client.post(f'/api/novels/{nid}/screenplays/{sid}/storyboard').json()
    assert board['storyboard'][0]['shot_id']==board['shots'][0]['id']
    card=board['storyboard'][0]
    updated=client.put(f'/api/novels/{nid}/screenplays/{sid}/storyboard/{card["id"]}',json={'frame_prompt':'近景','composition':'中心','color':'冷色'}).json()
    assert updated['storyboard'][0]['frame_prompt']=='近景'
    approved=client.post(f'/api/novels/{nid}/screenplays/{sid}/storyboard/approve')
    assert approved.status_code==200
    frozen=client.put(f'/api/novels/{nid}/screenplays/{sid}/storyboard/{card["id"]}',json={'frame_prompt':'改'} )
    assert frozen.status_code==400
