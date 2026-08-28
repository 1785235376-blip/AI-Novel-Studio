from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.credential_vault import CredentialVault, MemoryBackend
from app.main import app
from app.runtime import runtime
from app.runtime_diagnostics import TextRuntimeDiagnosticsAdapter, TextRuntimeState


class SpyMemoryBackend(MemoryBackend):
    def __init__(self):
        super().__init__()
        self.calls = {"set": 0, "resolve": 0, "clear": 0}

    def set(self, provider, secret):
        self.calls["set"] += 1
        super().set(provider, secret)

    def resolve(self, provider):
        self.calls["resolve"] += 1
        return super().resolve(provider)

    def clear(self, provider):
        self.calls["clear"] += 1
        super().clear(provider)


@pytest.fixture(autouse=True)
def isolated_vault(monkeypatch):
    import app.credential_vault as vault_module
    import app.openai_compatible as compatible_module
    import app.providers as providers_module

    previous = (
        settings.enable_collaboration_runtime,
        settings.mock_provider,
        settings.enable_packaged_runtime,
        settings.mock_failure,
    )
    backend = SpyMemoryBackend()
    vault = CredentialVault(
        backend_impl=backend,
        supports_provider=lambda provider: provider == "deepseek",
    )
    calls = {"windows": 0, "keyring": 0, "urlopen": 0, "httpx_client": 0}

    def blocked(name):
        def fail(*_args, **_kwargs):
            calls[name] += 1
            pytest.fail(f"forbidden {name} access")
        return fail

    monkeypatch.setattr(vault_module, "credential_vault", vault)
    monkeypatch.setattr(vault_module.WindowsBackend, "__init__", blocked("windows"))
    monkeypatch.setattr(vault_module.WindowsBackend, "set", blocked("windows"))
    monkeypatch.setattr(vault_module.WindowsBackend, "resolve", blocked("windows"))
    monkeypatch.setattr(vault_module.WindowsBackend, "clear", blocked("windows"))
    monkeypatch.setattr(vault_module.KeyringBackend, "__init__", blocked("keyring"))
    monkeypatch.setattr(vault_module.KeyringBackend, "probe", blocked("keyring"))
    monkeypatch.setattr(vault_module.KeyringBackend, "set", blocked("keyring"))
    monkeypatch.setattr(vault_module.KeyringBackend, "resolve", blocked("keyring"))
    monkeypatch.setattr(vault_module.KeyringBackend, "clear", blocked("keyring"))
    monkeypatch.setattr(providers_module, "urlopen", blocked("urlopen"))
    monkeypatch.setattr(providers_module.OllamaProvider, "health_check", lambda _self: False)
    monkeypatch.setattr(providers_module.OllamaProvider, "list_models", lambda _self: [])
    monkeypatch.setattr(compatible_module.OpenAICompatibleTextProvider, "_client", blocked("httpx_client"))
    try:
        yield backend, calls
    finally:
        object.__setattr__(settings, "enable_collaboration_runtime", previous[0])
        object.__setattr__(settings, "mock_provider", previous[1])
        object.__setattr__(settings, "enable_packaged_runtime", previous[2])
        object.__setattr__(settings, "mock_failure", previous[3])
    assert calls == {"windows": 0, "keyring": 0, "urlopen": 0, "httpx_client": 0}


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


def test_collaboration_catalog_uses_mock_backed_deepseek_only_in_mock_mode(monkeypatch, isolated_vault):
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
    assert isolated_vault[0].calls == {"set": 0, "resolve": 0, "clear": 0}


def test_health_then_text_models_preserves_mock_standin_runtime(monkeypatch, isolated_vault):
    import app.providers as providers_module
    from app.runtime import Runtime

    previous = (settings.mock_provider, settings.enable_packaged_runtime, settings.mock_failure)
    object.__setattr__(settings, "mock_provider", True)
    object.__setattr__(settings, "enable_packaged_runtime", False)
    object.__setattr__(settings, "mock_failure", "")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    ollama_calls = {"health": 0, "models": 0}
    monkeypatch.setattr(providers_module.OllamaProvider, "health_check", lambda _self: ollama_calls.__setitem__("health", ollama_calls["health"] + 1) or False)
    monkeypatch.setattr(providers_module.OllamaProvider, "list_models", lambda _self: ollama_calls.__setitem__("models", ollama_calls["models"] + 1) or [])
    value = Runtime()
    adapter = value.provider_registry.resolve("deepseek")
    monkeypatch.setattr(runtime, "provider_status", value.provider_status)
    monkeypatch.setattr(runtime, "text_models", value.text_models)

    try:
        client = TestClient(app)
        health = client.get("/api/health")
        models = client.get("/api/text-models")
        diagnostics = TextRuntimeDiagnosticsAdapter(
            value.provider_registry, value.model_registry,
        ).diagnose("deepseek", "deepseek-chat")
    finally:
        object.__setattr__(settings, "mock_provider", previous[0])
        object.__setattr__(settings, "enable_packaged_runtime", previous[1])
        object.__setattr__(settings, "mock_failure", previous[2])

    assert health.status_code == 200
    deepseek_health = health.json()["providers"]["deepseek"]
    assert deepseek_health["available"] is True
    assert deepseek_health["execution_mode"] == "mock_standin"
    assert models.status_code == 200
    deepseek_models = [item for item in models.json()["items"] if item["provider_id"] == "deepseek"]
    assert deepseek_models and all(item["available"] for item in deepseek_models)
    assert all(set(item) == {"provider_id", "model_id", "display_name", "available"} for item in deepseek_models)
    assert diagnostics.state is TextRuntimeState.READY
    assert value.provider_registry.resolve("deepseek") is adapter
    assert isolated_vault[0].calls == {"set": 0, "resolve": 0, "clear": 0}
    assert isolated_vault[1]["urlopen"] == 0
    assert isolated_vault[1]["httpx_client"] == 0
    assert ollama_calls == {"health": 1, "models": 1}
