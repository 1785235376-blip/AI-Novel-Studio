from fastapi.testclient import TestClient
from app.main import app
from uuid import uuid4

def test_location_create_and_update_round_trip():
    client=TestClient(app);novel=client.post('/api/novels',json={'title':f'Phase4 Locations {uuid4()}'}).json();url=f"/api/novels/{novel['id']}/locations/mist-port"
    created=client.put(url,json={'name':'雾港','location_type':'港口城市','description':'终年被雾覆盖','rules':'午夜后禁止鸣笛','atmosphere':'潮湿压抑','status':'ACTIVE'}).json();assert created['name']=='雾港'
    updated=client.put(url,json={**created,'name':'雾港','status':'INACCESSIBLE'}).json();rows=client.get(f"/api/novels/{novel['id']}/locations").json();assert updated['status']=='INACCESSIBLE' and rows[0]['rules']=='午夜后禁止鸣笛'
