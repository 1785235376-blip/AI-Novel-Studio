from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.runtime import runtime


def test_text_models_is_reachable_in_collaboration_mode(monkeypatch):
    object.__setattr__(settings, "enable_collaboration_runtime", True)
    monkeypatch.setattr(runtime, "text_models", lambda: [
        {"provider_id": "mock", "model_id": "mock-writer", "display_name": "内置测试写作模型", "available": True},
        {"provider_id": "deepseek", "model_id": "deepseek-chat", "display_name": "DeepSeek Chat", "available": False},
    ])
    response = TestClient(app).get("/api/text-models")
    assert response.status_code == 200
    assert response.json() == {"items": [
        {"provider_id": "mock", "model_id": "mock-writer", "display_name": "内置测试写作模型", "available": True},
        {"provider_id": "deepseek", "model_id": "deepseek-chat", "display_name": "DeepSeek Chat", "available": False},
    ]}
    assert "COLLABORATION_ROUTE_NOT_ENABLED" not in response.text
    assert "api_key" not in response.text.casefold()
    assert "authorization" not in response.text.casefold()


def test_collaboration_admin_routes_remain_protected(monkeypatch):
    object.__setattr__(settings, "enable_collaboration_runtime", True)
    response = TestClient(app).get("/api/collaboration/admin/workspaces")
    assert response.status_code != 501
    assert response.status_code in {401, 403}


def test_collaboration_catalog_uses_mock_backed_deepseek_only_in_mock_mode(monkeypatch):
    from app.runtime import Runtime
    object.__setattr__(settings, "enable_collaboration_runtime", True)
    object.__setattr__(settings, "mock_provider", True)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    value = Runtime()
    monkeypatch.setattr(runtime, "text_models", value.text_models)
    response = TestClient(app).get("/api/text-models")
    assert response.status_code == 200
    deepseek = [item for item in response.json()["items"] if item["provider_id"] == "deepseek"]
    assert deepseek and all(item["available"] for item in deepseek)
    assert all(set(item) == {"provider_id", "model_id", "display_name", "available"} for item in deepseek)
    assert "api_key" not in response.text.casefold() and "authorization" not in response.text.casefold()
