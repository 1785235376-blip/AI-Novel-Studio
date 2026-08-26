from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import user_preference_service, harness_process_service
import app.api as api_module

def test_start_harness_requires_explicit_authorization(tmp_path):
    original=user_preference_service.path; user_preference_service.path=tmp_path/"prefs.json"
    result=TestClient(app).post('/api/harness/process/start')
    assert result.status_code==403
    assert result.json()['detail']['code']=='HARNESS_NOT_AUTHORIZED'
    user_preference_service.path=original

def test_stop_harness_is_idempotent(monkeypatch):
    monkeypatch.setattr(harness_process_service, 'stop', lambda: {'running':False,'pid':None})
    client=TestClient(app)
    assert client.post('/api/harness/process/stop').json()=={'running':False,'pid':None}

def test_start_harness_rejects_incompatible_version(tmp_path, monkeypatch):
    original=user_preference_service.path; user_preference_service.path=tmp_path/"prefs.json"
    user_preference_service.set_harness_enabled(True)
    monkeypatch.setattr(api_module, "harness_status", lambda: {
        "configured": True, "reachable": True, "compatible": False, "version": "0.0.1"
    })
    response=TestClient(app).post('/api/harness/process/start')
    assert response.status_code==409
    assert response.json()['detail']['code']=='HARNESS_NOT_READY'
    assert '版本不兼容' in response.json()['detail']['reason']
    user_preference_service.path=original
