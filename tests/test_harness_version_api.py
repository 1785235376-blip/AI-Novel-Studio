from fastapi.testclient import TestClient
from app.main import app

def test_harness_status_reports_incompatible_version(monkeypatch):
    class Response:
        status_code=200; headers={"content-type":"application/json"}
        def json(self): return {"version":"0.1.0"}
    monkeypatch.setenv('DEEPSEEK_HARNESS_URL','http://localhost:3080')
    monkeypatch.setenv('DEEPSEEK_HARNESS_MIN_VERSION','0.2.0')
    monkeypatch.setattr('httpx.get',lambda *a,**k: Response())
    result=TestClient(app).get('/api/harness/status').json()
    assert result['reachable'] is True and result['compatible'] is False
