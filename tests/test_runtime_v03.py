import time
from pathlib import Path
from app.providers import MockProvider
from app.runtime import Runtime
from app.config import settings
from app.model_runtime import TextGenerationRequest,TextModelNodeInput

def test_mock_stream():
    provider=MockProvider(0,""); text="".join(provider.stream("x","mock-writer")); assert "林海" in text
def test_provider_status_never_exposes_keys():
    encoded=str(Runtime().provider_status()); assert "API_KEY" not in encoded and "sk-" not in encoded

def test_configured_normalized_provider_is_not_replaced_by_legacy_route(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-route-secret")
    value=Runtime(); before=value.provider_registry.resolve("deepseek")
    value.prepare_text_route("deepseek","deepseek-chat",value.providers["deepseek"])
    assert value.provider_registry.resolve("deepseek") is before

def test_mock_mode_surfaces_deepseek_identity_and_executes_without_real_adapter(monkeypatch):
    object.__setattr__(settings,"mock_provider",True)
    monkeypatch.delenv("DEEPSEEK_API_KEY",raising=False)
    value=Runtime();models=value.text_models()
    assert any(item["provider_id"]=="deepseek" and item["model_id"]=="deepseek-chat" and item["available"] for item in models)
    output=value.generation_runtime.text_node.execute(TextModelNodeInput(TextGenerationRequest(provider_id="deepseek",model_id="deepseek-chat",prompt="test")))
    assert output.response.provider_id=="deepseek" and output.response.model_id=="deepseek-chat"

def test_non_mock_mode_preserves_real_deepseek_availability(monkeypatch):
    object.__setattr__(settings,"mock_provider",False)
    monkeypatch.delenv("DEEPSEEK_API_KEY",raising=False)
    value=Runtime()
    assert all(not item["available"] for item in value.text_models() if item["provider_id"]=="deepseek")
    assert value.provider_registry.is_configured("deepseek") is False

def test_local_default_route_remains_mock_in_mock_mode():
    object.__setattr__(settings,"mock_provider",True)
    route=Runtime().router("LOCAL_ONLY","writer").routes["writer"]
    assert [(item.provider,item.model) for item in route]==[("mock","mock-writer")]

def test_packaged_runtime_does_not_stand_in_mock_as_deepseek(monkeypatch):
    previous_packaged=settings.enable_packaged_runtime
    previous_mock=settings.mock_provider
    object.__setattr__(settings,"enable_packaged_runtime",True)
    object.__setattr__(settings,"mock_provider",True)
    monkeypatch.delenv("DEEPSEEK_API_KEY",raising=False)
    try:
        value=Runtime()
        assert all(not item["available"] for item in value.text_models() if item["provider_id"]=="deepseek")
        assert value.packaged_author_route_ready("mock") is False
        assert value.packaged_author_route_ready("deepseek") is False
        assert [(item.provider,item.model) for item in value.router("LOCAL_ONLY","writer").routes["writer"]]==[("ollama",settings.local_model)]
    finally:
        object.__setattr__(settings,"enable_packaged_runtime",previous_packaged)
        object.__setattr__(settings,"mock_provider",previous_mock)
