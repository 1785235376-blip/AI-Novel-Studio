from fastapi.testclient import TestClient
from app.main import app
from uuid import uuid4

def test_timeline_create_and_update_round_trip():
    client=TestClient(app);novel=client.post('/api/novels',json={'title':f'Phase4 Timeline {uuid4()}'}).json();client.put(f"/api/novels/{novel['id']}/locations/mist-port",json={'name':'雾港'});url=f"/api/novels/{novel['id']}/timeline/port-lockdown"
    created=client.put(url,json={'title':'雾港封锁','sequence':2,'time':'冬至夜','description':'港口突然封锁','location':'mist-port','characters':['lin-hai'],'chapter_id':f"{novel['id']}:1"}).json();assert created['title']=='雾港封锁'
    updated=client.put(url,json={**created,'title':'雾港解除封锁','sequence':3,'status':'CONFIRMED'}).json();rows=client.get(f"/api/novels/{novel['id']}/timeline").json();assert updated['sequence']==3 and rows[0]['characters']==['lin-hai']
