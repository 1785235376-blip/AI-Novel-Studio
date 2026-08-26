from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_relationship_create_and_update_round_trip():
    client=TestClient(app);novel=client.post('/api/novels',json={'title':f'Phase4 Relationships {uuid4()}'}).json();nid=novel['id']
    client.put(f'/api/novels/{nid}/characters/lin-hai',json={'name':'林海'});client.put(f'/api/novels/{nid}/characters/su-ye',json={'name':'苏夜'})
    url=f'/api/novels/{nid}/relationships/lin-hai-su-ye'
    created=client.put(url,json={'source_character_id':'lin-hai','target_character_id':'su-ye','relationship_type':'FRIEND','description':'共同调查雾港','valid_from_event_id':'port-lockdown'}).json()
    updated=client.put(url,json={**created,'relationship_type':'INTEREST','status':'ACTIVE','certainty':'CONFIRMED'}).json();rows=client.get(f'/api/novels/{nid}/relationships').json()
    assert updated['relationship_type']=='INTEREST' and rows[0]['id']=='lin-hai-su-ye'
    assert rows[0]['source_character_id']=='lin-hai' and rows[0]['target_character_id']=='su-ye'
    assert rows[0]['valid_from_event_id']=='port-lockdown'
