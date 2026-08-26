from fastapi.testclient import TestClient
from app.main import app
from uuid import uuid4


def test_world_summary_round_trip():
    client=TestClient(app)
    novel=client.post('/api/novels',json={'title':f'Phase4 World Summary {uuid4()}','genre':'fantasy'}).json()
    updated=client.put(f"/api/novels/{novel['id']}",json={'long_term_summary':'天空城依靠潮汐晶体运行。'}).json()
    assert updated['long_term_summary']=='天空城依靠潮汐晶体运行。'
    assert client.get(f"/api/novels/{novel['id']}").json()['long_term_summary']==updated['long_term_summary']
