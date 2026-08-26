from fastapi.testclient import TestClient
from app.main import app

def test_harness_status_rejects_non_local_endpoint(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_HARNESS_URL", "https://example.com")
    result=TestClient(app).get("/api/harness/status")
    assert result.status_code==200
    assert result.json()=={"configured":False,"reachable":False,"reason":"本地地址限制"}

def test_harness_status_reports_unreachable_local(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_HARNESS_URL", "http://127.0.0.1:1")
    result=TestClient(app).get("/api/harness/status")
    assert result.status_code==200
    assert result.json()["configured"] is True
    assert result.json()["reachable"] is False

def test_harness_status_parses_local_health(monkeypatch):
    class Response:
        status_code=200
        headers={"content-type":"application/json"}
        def json(self): return {"version":"0.1-test"}
    monkeypatch.setenv("DEEPSEEK_HARNESS_URL", "http://localhost:3080")
    monkeypatch.setattr("httpx.get", lambda *args, **kwargs: Response())
    result=TestClient(app).get("/api/harness/status")
    assert result.json()["configured"] is True and result.json()["reachable"] is True
    assert result.json()["version"] == "0.1-test"
