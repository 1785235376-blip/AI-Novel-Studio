from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import user_preference_service
from app.services import harness_access_audit_service as audit_module


def test_harness_access_audit_records_metadata_only(tmp_path):
    original_pref = user_preference_service.path
    original_audit = audit_module.harness_access_audit_service.path
    user_preference_service.path = tmp_path / "prefs.json"
    audit_module.harness_access_audit_service.path = tmp_path / "audit.json"
    audit_module.harness_access_audit_service.append(novel_id="n1", chapter=2, agent_id="writer", scopes=["novel.chapter"])
    body = TestClient(app).get("/api/harness/access-audit").json()
    user_preference_service.path = original_pref
    audit_module.harness_access_audit_service.path = original_audit
    assert body["items"][0]["novel_id"] == "n1"
    assert "prompt" not in body["items"][0]
    filtered = TestClient(app).get("/api/harness/access-audit", params={"novel_id": "other"}).json()
    assert filtered["items"] == []
    assert TestClient(app).delete("/api/harness/access-audit").status_code == 400
    assert TestClient(app).delete("/api/harness/access-audit", params={"confirm": "true"}).json() == {"cleared": True}
