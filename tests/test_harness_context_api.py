from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import user_preference_service, agent_context_service
from app.services import harness_access_audit_service as audit_module


def test_harness_context_requires_authorization(tmp_path):
    original = user_preference_service.path
    user_preference_service.path = tmp_path / "prefs.json"
    response = TestClient(app).get("/api/harness/context", params={"novel_id": "n1", "chapter": 1})
    user_preference_service.path = original
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "HARNESS_NOT_AUTHORIZED"


def test_harness_context_returns_contract_and_real_context(tmp_path, monkeypatch):
    original = user_preference_service.path
    user_preference_service.path = tmp_path / "prefs.json"
    user_preference_service.set_harness_enabled(True)
    monkeypatch.setattr(agent_context_service, "build", lambda *args: {"novel_id": "n1", "chapter_id": "c1", "target": "local", "instruction": "private"})
    response = TestClient(app).get("/api/harness/context", params={"novel_id": "n1", "chapter": 1, "agent_id": "writer"})
    user_preference_service.path = original
    assert response.status_code == 200
    body = response.json()
    assert body["contract"]["mode"] == "read_only"
    assert "novel.chapter" in body["accessed_scopes"]
    assert body["context"]["chapter_id"] == "c1"
    assert "instruction" not in body["context"]


def test_harness_context_failure_is_audited(tmp_path, monkeypatch):
    original_pref = user_preference_service.path
    original_audit = audit_module.harness_access_audit_service.path
    user_preference_service.path = tmp_path / "prefs.json"
    audit_module.harness_access_audit_service.path = tmp_path / "audit.json"
    user_preference_service.set_harness_enabled(True)
    monkeypatch.setattr(agent_context_service, "build", lambda *args: (_ for _ in ()).throw(KeyError("chapter")))
    response = TestClient(app).get("/api/harness/context", params={"novel_id": "n1", "chapter": 9})
    entries = audit_module.harness_access_audit_service.list()
    user_preference_service.path = original_pref
    audit_module.harness_access_audit_service.path = original_audit
    assert response.status_code == 404
    assert entries[0]["outcome"] == "not_found"
