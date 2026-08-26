from fastapi.testclient import TestClient
from app.main import app
from uuid import uuid4

def test_character_create_and_update_round_trip():
    client=TestClient(app);novel=client.post('/api/novels',json={'title':f'Phase4 Characters {uuid4()}'}).json();url=f"/api/novels/{novel['id']}/characters/lin-hai"
    created=client.put(url,json={'name':'林海','age':31,'role':'船医','personality':'谨慎','goal':'寻找船员','current_location':'雾港','status':'ALIVE'}).json()
    assert created['name']=='林海' and created['role']=='船医'
    updated=client.put(url,json={**created,'name':'林海','role':'远航船医','status':'MISSING'}).json()
    rows=client.get(f"/api/novels/{novel['id']}/characters").json()
    assert updated['status']=='MISSING' and rows[0]['role']=='远航船医'
