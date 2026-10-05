import json
from threading import Event
from urllib.error import URLError
from unittest.mock import patch

import httpx
import pytest

from app.model_runtime import (GenerationEvent, ModelDescriptor, Modality, ModelRegistry,
    ModelRuntimeError, ProviderDescriptor, ProviderRegistry, TextGenerationRequest,
    TextModelNode, TextModelNodeInput)
from app.openai_compatible import CompatibleProviderConfig, OpenAICompatibleTextProvider
from app.providers import OpenAICompatibleProvider, ProviderError


def test_partial_legacy_stream_is_not_replayed():
    class Partial:
        def __enter__(self):return self
        def __exit__(self,*_):pass
        def __iter__(self):
            yield b'data: {"choices":[{"delta":{"content":"partial"}}]}\n'
            raise URLError("interrupted")
    provider=OpenAICompatibleProvider("test","https://example.invalid","TEST_KEY")
    with patch.object(provider,"_key",return_value="synthetic"),patch("app.providers.urlopen",return_value=Partial()) as send:
        stream=provider.stream("synthetic","model",retries=3)
        assert next(stream)=="partial"
        with pytest.raises(ProviderError):next(stream)
        assert send.call_count==1


def test_incomplete_sse_is_failure_and_has_no_completed_event():
    transport=httpx.MockTransport(lambda request:httpx.Response(200,text='data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'))
    provider=OpenAICompatibleTextProvider(CompatibleProviderConfig("test","https://example.invalid","TEST_KEY"),transport=transport)
    request=TextGenerationRequest("test","model","synthetic")
    events=[]
    with patch.object(provider,"_key",return_value="synthetic"):
        with pytest.raises(ModelRuntimeError):
            for event in provider.stream_text(request):events.append(event)
    assert not any(e.event_type=="generation.completed" for e in events)


def test_cancelled_nonstream_request_never_dispatches():
    sent=[]
    provider=OpenAICompatibleTextProvider(CompatibleProviderConfig("test","https://example.invalid","TEST_KEY"),transport=httpx.MockTransport(lambda req:sent.append(req)))
    cancelled=Event();cancelled.set()
    with pytest.raises(ModelRuntimeError):provider.generate_text(TextGenerationRequest("test","model","synthetic",cancellation=cancelled))
    assert sent==[]


def test_runtime_does_not_invent_completion_for_adapter_eof():
    class Broken:
        def stream_text(self,request):yield GenerationEvent("generation.started",request.job_id)
    providers=ProviderRegistry();models=ModelRegistry()
    providers.register(ProviderDescriptor("test","Test","local",frozenset({Modality.TEXT}),True,True),Broken())
    models.register(ModelDescriptor("model","test","Test",Modality.TEXT,frozenset({"stream"}),streaming=True))
    events=list(TextModelNode(providers,models).stream(TextModelNodeInput(TextGenerationRequest("test","model","synthetic"))))
    assert events[-1].event_type=="generation.failed"


def test_mock_standin_is_labeled_in_picker_and_response():
    from app.runtime import runtime
    if runtime._deepseek_execution_mode != "mock_standin":pytest.skip("development mock profile only")
    models=[row for row in runtime.text_models() if row["provider_id"]=="deepseek"]
    assert models and all(row["execution_mode"]=="mock_standin" and "模拟测试" in row["display_name"] for row in models)
    result=runtime.generation_runtime.text_node.execute(TextModelNodeInput(TextGenerationRequest("deepseek","deepseek-chat","synthetic")))
    assert result.response.execution_mode=="mock_standin"


def test_agent_context_cloud_filters_all_domain_sections():
    from types import SimpleNamespace
    from app.services.agent_context_service import AgentContextService
    novels=SimpleNamespace(get_outline=lambda _: {"theme":"SYNTHETIC_PRIVATE_OUTLINE","privacy_level":"LOCAL_ONLY"},get_data_set=lambda *_:[{"id":"private","text":"SYNTHETIC_PRIVATE_DATASET","privacy_level":"LOCAL_ONLY"},{"id":"public","text":"synthetic allowed","privacy_level":"CLOUD_ALLOWED"}])
    chapters=SimpleNamespace(get=lambda _: {"id":"n:1","version":1})
    context=AgentContextService(novels,chapters,None).build("planner","n",1,cloud=True)
    encoded=json.dumps(context)
    assert "SYNTHETIC_PRIVATE" not in encoded and "synthetic allowed" in encoded


def test_interrupted_agent_job_requires_explicit_retry():
    from types import SimpleNamespace
    from app.services.agent_job_service import AgentJobService
    rows=[{"id":"synthetic","operation":"AGENT_TASK","status":"WORKING"}]
    generations=SimpleNamespace(load_all=lambda:rows,save=lambda value:rows.__setitem__(0,value))
    service=AgentJobService(generations,None,None)
    assert service.recover_interrupted()==["synthetic"]
    assert rows[0]["status"]=="FAILED" and rows[0]["replay_safe"] is False


def test_ollama_stream_requires_terminal_record_and_preserves_usage():
    from app.providers import OllamaProvider
    from app.model_runtime import LegacyTextProviderAdapter
    from test_local_ai_discovery_egress import OllamaWire
    wire=OllamaWire('synthetic')
    provider=OllamaProvider("http://localhost:11434");provider._metadata_client=wire.client()
    adapter=LegacyTextProviderAdapter("ollama",provider)
    request=TextGenerationRequest("ollama","synthetic","Synthetic input")
    events=list(adapter.stream_text(request))
    assert events[-1].response.usage.input_tokens==8 and events[-1].response.usage.total_tokens==11
    wire.complete=False
    with pytest.raises(ModelRuntimeError):list(adapter.stream_text(request))
