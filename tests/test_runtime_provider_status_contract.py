from __future__ import annotations

import pytest

from app.config import settings
from app.credential_vault import CredentialVault, MemoryBackend
from app.model_runtime import TextGenerationRequest, TextModelNodeInput
from app.runtime import Runtime
from app.runtime_diagnostics import TextRuntimeDiagnosticsAdapter, TextRuntimeState


PROVIDER_KEYS = (
    "DEEPSEEK_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY",
    "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
)


class SpyMemoryBackend(MemoryBackend):
    def __init__(self):
        super().__init__()
        self.calls = {"set": 0, "resolve": 0, "clear": 0}

    def set(self, provider: str, secret: str) -> None:
        self.calls["set"] += 1
        super().set(provider, secret)

    def resolve(self, provider: str) -> str | None:
        self.calls["resolve"] += 1
        return super().resolve(provider)

    def clear(self, provider: str) -> None:
        self.calls["clear"] += 1
        super().clear(provider)


@pytest.fixture(autouse=True)
def isolated_runtime(monkeypatch):
    import app.credential_vault as vault_module
    import app.openai_compatible as compatible_module
    import app.providers as providers_module

    previous = (settings.mock_provider, settings.enable_packaged_runtime, settings.mock_failure)
    for key in PROVIDER_KEYS:
        monkeypatch.delenv(key, raising=False)
    backend = SpyMemoryBackend()
    vault = CredentialVault(
        backend_impl=backend,
        supports_provider=lambda provider: provider == "deepseek",
    )
    guard_calls = {"windows": 0, "keyring": 0, "urlopen": 0, "httpx_client": 0}

    def blocked(name):
        def fail(*_args, **_kwargs):
            guard_calls[name] += 1
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
        yield backend, vault, guard_calls
    finally:
        object.__setattr__(settings, "mock_provider", previous[0])
        object.__setattr__(settings, "enable_packaged_runtime", previous[1])
        object.__setattr__(settings, "mock_failure", previous[2])
    assert guard_calls == {"windows": 0, "keyring": 0, "urlopen": 0, "httpx_client": 0}


def configure(*, mock: bool, packaged: bool, failure: str = "") -> None:
    object.__setattr__(settings, "mock_provider", mock)
    object.__setattr__(settings, "enable_packaged_runtime", packaged)
    object.__setattr__(settings, "mock_failure", failure)


def deepseek_descriptor(value: Runtime):
    return next(item for item in value.provider_registry.descriptors() if item.provider_id == "deepseek")


def diagnostics(value: Runtime):
    return TextRuntimeDiagnosticsAdapter(value.provider_registry, value.model_registry).diagnose("deepseek", "deepseek-chat")


def test_mock_standin_remains_ready_across_repeated_status_reads(isolated_runtime):
    configure(mock=True, packaged=False)
    backend, _vault, _guards = isolated_runtime
    value = Runtime()
    adapter = value.provider_registry.resolve("deepseek")
    assert all(item["available"] for item in value.text_models() if item["provider_id"] == "deepseek")
    for _ in range(3):
        status = value.provider_status()["deepseek"]
        assert status == {"available": True, "configured": True, "kind": "cloud", "execution_mode": "mock_standin"}
        assert value.provider_registry.resolve("deepseek") is adapter
        assert deepseek_descriptor(value).health_status == "mock_standin"
        assert diagnostics(value).state is TextRuntimeState.READY
    assert backend.calls == {"set": 0, "resolve": 0, "clear": 0}


def test_mock_standin_generates_with_mock_and_never_real_transport(monkeypatch, isolated_runtime):
    configure(mock=True, packaged=False)
    value = Runtime()
    real = value.providers["deepseek"]
    monkeypatch.setattr(real, "health_check", lambda: pytest.fail("real DeepSeek health called"))
    monkeypatch.setattr(real, "generate", lambda *_a, **_k: pytest.fail("real DeepSeek generate called"))
    result = value.generation_runtime.text_node.execute(TextModelNodeInput(TextGenerationRequest(
        provider_id="deepseek", model_id="deepseek-chat", prompt="test",
    )))
    assert result.response.provider_id == "deepseek"
    assert result.response.text
    assert value.provider_status()["deepseek"]["execution_mode"] == "mock_standin"
    assert isolated_runtime[0].calls == {"set": 0, "resolve": 0, "clear": 0}


def test_mock_standin_never_uses_credentials_or_network(monkeypatch, isolated_runtime):
    configure(mock=True, packaged=False)
    from app.providers import OpenAICompatibleProvider

    blocked = lambda *_a, **_k: pytest.fail("real DeepSeek transport attempted")
    monkeypatch.setattr(OpenAICompatibleProvider, "health_check", blocked)
    monkeypatch.setattr(OpenAICompatibleProvider, "generate", blocked)
    monkeypatch.setattr(OpenAICompatibleProvider, "stream", blocked)

    value = Runtime()
    assert value.provider_status()["deepseek"]["available"] is True
    result = value.generation_runtime.text_node.execute(TextModelNodeInput(TextGenerationRequest(
        provider_id="deepseek", model_id="deepseek-chat", prompt="test",
    )))
    assert result.response.text
    assert isolated_runtime[0].calls == {"set": 0, "resolve": 0, "clear": 0}


def test_mock_failure_is_configured_but_unavailable(isolated_runtime):
    configure(mock=True, packaged=False, failure="health")
    value = Runtime()
    status = value.provider_status()["deepseek"]
    descriptor = deepseek_descriptor(value)
    assert status["configured"] is True and status["available"] is False
    assert status["execution_mode"] == "mock_standin"
    assert descriptor.configured is True and descriptor.available is False
    assert descriptor.health_status == "mock_standin_unavailable"
    assert diagnostics(value).state is TextRuntimeState.UNAVAILABLE
    assert isolated_runtime[0].calls == {"set": 0, "resolve": 0, "clear": 0}


def test_non_mock_without_credential_stays_not_configured(isolated_runtime):
    configure(mock=False, packaged=False)
    value = Runtime()
    status = value.provider_status()["deepseek"]
    assert status["configured"] is False and status["available"] is False
    assert status["execution_mode"] == "real"
    assert diagnostics(value).state is TextRuntimeState.NOT_CONFIGURED
    assert isolated_runtime[0].calls == {"set": 0, "resolve": 2, "clear": 0}


def test_packaged_mock_without_credential_stays_fail_closed(isolated_runtime):
    configure(mock=True, packaged=True)
    value = Runtime()
    assert value.provider_status()["deepseek"] == {
        "available": False, "configured": False, "kind": "cloud", "execution_mode": "real",
    }
    assert diagnostics(value).state is TextRuntimeState.NOT_CONFIGURED
    assert value.packaged_author_route_ready("deepseek") is False
    assert value.packaged_author_route_ready("mock") is False
    assert isolated_runtime[0].calls == {"set": 0, "resolve": 3, "clear": 0}


def test_real_credential_mode_preserves_real_adapter_without_network(monkeypatch, isolated_runtime):
    configure(mock=False, packaged=False)
    backend, vault, _guards = isolated_runtime
    vault.set("deepseek", "TEST_ONLY_KEY")
    from app.providers import OpenAICompatibleProvider
    monkeypatch.setattr(OpenAICompatibleProvider, "health_check", lambda _self: True)
    value = Runtime()
    adapter = value.provider_registry.resolve("deepseek")
    assert value.provider_status()["deepseek"] == {
        "available": True, "configured": True, "kind": "cloud", "execution_mode": "real",
    }
    assert value.provider_registry.resolve("deepseek") is adapter
    assert diagnostics(value).state is TextRuntimeState.READY
    assert backend.calls == {"set": 1, "resolve": 2, "clear": 0}
