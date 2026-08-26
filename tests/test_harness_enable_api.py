from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import user_preference_service

def test_harness_enable_round_trip(monkeypatch, tmp_path):
    original=user_preference_service.path
    user_preference_service.path=tmp_path/"prefs.json"
    client=TestClient(app)
    assert client.get('/api/user-preferences').json()['harness_enabled'] is False
    result=client.put('/api/harness-enabled?enabled=true')
    assert result.status_code==200 and result.json()=={'harness_enabled':True}
    assert client.get('/api/user-preferences').json()['harness_enabled'] is True
    user_preference_service.path=original
