from fastapi.testclient import TestClient
from app.main import app


def test_harness_context_contract_is_read_only():
    body = TestClient(app).get("/api/harness/context-contract").json()
    assert body["mode"] == "read_only"
    assert body["writes_enabled"] is False
    assert "novel.chapter" in body["read_scopes"]
    assert "novel.write" in body["denied_scopes"]
