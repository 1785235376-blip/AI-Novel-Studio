from __future__ import annotations

import os
import urllib.request

import httpx
import pytest

from app.config import settings
from app.model_runtime import TextGenerationRequest, TextModelNodeInput
from app.runtime import Runtime
from app.runtime_diagnostics import TextRuntimeDiagnosticsAdapter, TextRuntimeState


PROVIDER_KEYS = (
    "DEEPSEEK_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY",
    "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
)


@pytest.fixture(autouse=True)
def isolated_runtime(monkeypatch):
    previous = (settings.mock_provider, settings.enable_packaged_runtime, settings.mock_failure)
    monkeypatch.setenv("CREDENTIAL_VAULT_BACKEND", "memory")
    for key in PROVIDER_KEYS:
        monkeypatch.delenv(key, raising=False)
    yield
    object.__setattr__(settings, "mock_provider", previous[0])
    object.__setattr__(settings, "enable_packaged_runtime", previous[1])
    object.__setattr__(settings, "mock_failure", previous[2])


def configure(*, mock: bool, packaged: bool, failure: str = "") -> None:
    object.__setattr__(settings, "mock_provider", mock)
    object.__setattr__(settings, "enable_packaged_runtime", packaged)
    object.__setattr__(settings, "mock_failure", failure)


def deepseek_descriptor(value: Runtime):
    return next(item for item in value.provider_registry.descriptors() if item.provider_id == "deepseek")


def diagnostics(value: Runtime):
    return TextRuntimeDiagnosticsAdapter(value.provider_registry, value.model_registry).diagnose("deepseek", "deepseek-chat")


def test_mock_standin_remains_ready_across_repeated_status_reads(monkeypatch):
    configure(mock=True, packaged=False)
    from app.credential_vault import credential_vault
    monkeypatch.setattr(credential_vault, "has", lambda *_a: pytest.fail("credential vault touched"))
    monkeypatch.setattr(credential_vault, "resolve", lambda *_a: pytest.fail("credential vault touched"))
    value = Runtime()
    adapter = value.provider_registry.resolve("deepseek")
    assert all(item["available"] for item in value.text_models() if item["provider_id"] == "deepseek")
    for _ in range(3):
        status = value.provider_status()["deepseek"]
        assert status == {"available": True, "configured": True, "kind": "cloud", "execution_mode": "mock_standin"}
        assert value.provider_registry.resolve("deepseek") is adapter
        assert deepseek_descriptor(value).health_status == "mock_standin"
        assert diagnostics(value).state is TextRuntimeState.READY


def test_mock_standin_generates_with_mock_and_never_real_transport(monkeypatch):
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


def test_mock_standin_never_uses_credentials_or_network(monkeypatch):
    configure(mock=True, packaged=False)
    from app.credential_vault import credential_vault
    from app.providers import OpenAICompatibleProvider

    blocked = lambda *_a, **_k: pytest.fail("real credential or network access attempted")
    monkeypatch.setattr(credential_vault, "has", blocked)
    monkeypatch.setattr(credential_vault, "resolve", blocked)
    monkeypatch.setattr(urllib.request, "urlopen", blocked)
    monkeypatch.setattr(httpx, "request", blocked)
    monkeypatch.setattr(OpenAICompatibleProvider, "health_check", blocked)
    monkeypatch.setattr(OpenAICompatibleProvider, "generate", blocked)
    monkeypatch.setattr(OpenAICompatibleProvider, "stream", blocked)

    value = Runtime()
    assert value.provider_status()["deepseek"]["available"] is True
    result = value.generation_runtime.text_node.execute(TextModelNodeInput(TextGenerationRequest(
        provider_id="deepseek", model_id="deepseek-chat", prompt="test",
    )))
    assert result.response.text


def test_mock_failure_is_configured_but_unavailable(monkeypatch):
    configure(mock=True, packaged=False, failure="health")
    value = Runtime()
    status = value.provider_status()["deepseek"]
    descriptor = deepseek_descriptor(value)
    assert status["configured"] is True and status["available"] is False
    assert status["execution_mode"] == "mock_standin"
    assert descriptor.configured is True and descriptor.available is False
    assert descriptor.health_status == "mock_standin_unavailable"
    assert diagnostics(value).state is TextRuntimeState.UNAVAILABLE


def test_non_mock_without_credential_stays_not_configured(monkeypatch):
    configure(mock=False, packaged=False)
    value = Runtime()
    status = value.provider_status()["deepseek"]
    assert status["configured"] is False and status["available"] is False
    assert status["execution_mode"] == "real"
    assert diagnostics(value).state is TextRuntimeState.NOT_CONFIGURED


def test_packaged_mock_without_credential_stays_fail_closed(monkeypatch):
    configure(mock=True, packaged=True)
    value = Runtime()
    assert value.provider_status()["deepseek"] == {
        "available": False, "configured": False, "kind": "cloud", "execution_mode": "real",
    }
    assert diagnostics(value).state is TextRuntimeState.NOT_CONFIGURED
    assert value.packaged_author_route_ready("deepseek") is False
    assert value.packaged_author_route_ready("mock") is False


def test_real_credential_mode_preserves_real_adapter_without_network(monkeypatch):
    configure(mock=False, packaged=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "TEST_ONLY_KEY")
    from app.providers import OpenAICompatibleProvider
    monkeypatch.setattr(OpenAICompatibleProvider, "health_check", lambda _self: True)
    value = Runtime()
    adapter = value.provider_registry.resolve("deepseek")
    assert value.provider_status()["deepseek"] == {
        "available": True, "configured": True, "kind": "cloud", "execution_mode": "real",
    }
    assert value.provider_registry.resolve("deepseek") is adapter
    assert diagnostics(value).state is TextRuntimeState.READY
