from fastapi.testclient import TestClient
from app.main import app
from uuid import uuid4


def test_location_create_and_update_round_trip():
    client = TestClient(app)
    novel = client.post('/api/novels', json={'title': f'Phase4 Locations {uuid4()}'}).json()
    url = f"/api/novels/{novel['id']}/locations/mist-port"
    response = client.put(url, json={
        'name': '雾港', 'location_type': '港口城市', 'description': '终年被雾覆盖',
        'rules': '午夜后禁止鸣笛', 'atmosphere': '潮湿压抑', 'status': 'ACTIVE',
        'privacy_level': 'LOCAL_ONLY',
    })
    assert response.status_code == 200
    created = response.json()
    assert created['name'] == '雾港' and created['status'] == 'ACTIVE'
    response = client.put(url, json={**created, 'status': 'INACCESSIBLE'})
    assert response.status_code == 200
    updated = response.json()
    rows = client.get(f"/api/novels/{novel['id']}/locations").json()
    assert updated['status'] == 'INACCESSIBLE'
    assert rows == [updated]
    assert rows[0]['rules'] == '午夜后禁止鸣笛'
    assert rows[0]['privacy_level'] == 'LOCAL_ONLY'
