from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import user_preference_service

def test_launch_readiness_requires_authorization(tmp_path):
    original=user_preference_service.path; user_preference_service.path=tmp_path/"prefs.json"
    result=TestClient(app).get('/api/harness/launch-readiness')
    assert result.json()['ready'] is False and result.json()['authorized'] is False
    user_preference_service.path=original
