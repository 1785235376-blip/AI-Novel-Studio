from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_story_route_parent_child_round_trip():
    client=TestClient(app);novel=client.post('/api/novels',json={'title':f'Phase5 Routes {uuid4()}'}).json();base=f"/api/novels/{novel['id']}/story-routes"
    root=client.put(f'{base}/original',json={'title':'原剧情','route_type':'ORIGINAL','summary':'公开雾港真相','status':'ACTIVE'}).json()
    ending=client.put(f'{base}/ending-a',json={'title':'结局 A','route_type':'ENDING_A','parent_route_id':'original','divergence_chapter':12,'shared_until_chapter':11,'divergence_summary':'选择保护证人','summary':'证人出庭','status':'DRAFT'}).json()
    updated=client.put(f'{base}/ending-a',json={**ending,'status':'ACTIVE','summary':'证人出庭并公开密道'}).json();rows=client.get(base).json()
    assert root['parent_route_id']=='' and updated['parent_route_id']=='original'
    assert rows[1]['divergence_chapter']==12 and rows[1]['shared_until_chapter']==11


def test_story_route_rejects_missing_parent():
    client=TestClient(app);novel=client.post('/api/novels',json={'title':f'Phase5 Route Parent {uuid4()}'}).json()
    response=client.put(f"/api/novels/{novel['id']}/story-routes/hidden",json={'title':'隐藏路线','route_type':'HIDDEN','parent_route_id':'missing'})
    assert response.status_code==400
