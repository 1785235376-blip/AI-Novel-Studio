import json
from threading import Event
from unittest.mock import patch

import httpx
import pytest

from app.native_text_providers import AnthropicTextProvider, GeminiTextProvider
from app.openai_compatible import CompatibleProviderConfig
from app.model_runtime import ModelRuntimeError, TextGenerationRequest, TextGenerationParameters


@pytest.mark.parametrize("cls,provider,path,body", [
    (AnthropicTextProvider,"claude","/v1/messages",{"id":"synthetic","content":[{"type":"text","text":"Synthetic result"}],"stop_reason":"end_turn","usage":{"input_tokens":4,"output_tokens":2}}),
    (GeminiTextProvider,"gemini","/v1/models/user-selected:generateContent",{"responseId":"synthetic","candidates":[{"content":{"parts":[{"text":"Synthetic result"}]},"finishReason":"STOP"}],"usageMetadata":{"promptTokenCount":4,"candidatesTokenCount":2,"totalTokenCount":6}}),
])
def test_native_request_shape_usage_and_header_only_credentials(cls,provider,path,body):
    seen=[]
    def transport(request):seen.append(request);return httpx.Response(200,json=body)
    adapter=cls(CompatibleProviderConfig(provider,"https://example.invalid/v1","SYNTHETIC_KEY"),transport=httpx.MockTransport(transport))
    request=TextGenerationRequest(provider,"user-selected","Synthetic prompt",system_instruction="Synthetic role",parameters=TextGenerationParameters(max_output_tokens=64))
    with patch.object(adapter,"_key",return_value="synthetic-key"):
        response=adapter.generate_text(request)
    assert response.text=="Synthetic result" and response.usage.input_tokens==4
    assert seen[0].url.path==path and "synthetic-key" not in str(seen[0].url)
    sent=json.loads(seen[0].content)
    assert "synthetic-key" not in seen[0].content.decode()
    if provider=="claude":assert sent["max_tokens"]==64 and seen[0].headers["anthropic-version"]=="2023-06-01"
    else:assert sent["generationConfig"]["maxOutputTokens"]==64 and seen[0].headers["x-goog-api-key"]=="synthetic-key"


@pytest.mark.parametrize("cls,provider,events", [
    (AnthropicTextProvider,"claude",[
        {"type":"message_start","message":{"id":"synthetic","usage":{"input_tokens":3,"output_tokens":1}}},
        {"type":"content_block_delta","delta":{"type":"text_delta","text":"Hello"}},
        {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":2}},
        {"type":"message_stop"},
    ]),
    (GeminiTextProvider,"gemini",[
        {"candidates":[{"content":{"parts":[{"text":"Hello"}]}}]},
        {"candidates":[{"finishReason":"STOP"}],"usageMetadata":{"promptTokenCount":3,"candidatesTokenCount":2,"totalTokenCount":5}},
    ]),
])
def test_native_sse_records_real_usage_without_replay(cls,provider,events):
    wire=''.join('data: '+json.dumps(event)+'\n\n' for event in events)
    adapter=cls(CompatibleProviderConfig(provider,"https://example.invalid/v1","SYNTHETIC_KEY"),transport=httpx.MockTransport(lambda _:httpx.Response(200,text=wire)))
    with patch.object(adapter,"_key",return_value="synthetic-key"):
        result=list(adapter.stream_text(TextGenerationRequest(provider,"user-selected","Synthetic")))
    assert result[-1].event_type=="generation.completed"
    assert result[-1].response.text=="Hello" and result[-1].response.usage.output_tokens==2


@pytest.mark.parametrize("status",[401,429,503])
@pytest.mark.parametrize("cls",[AnthropicTextProvider,GeminiTextProvider])
def test_native_http_faults_do_not_retry_or_expose_provider_body(cls,status):
    sent=[]
    def transport(request):sent.append(request);return httpx.Response(status,json={"error":"synthetic-secret-marker"})
    adapter=cls(CompatibleProviderConfig("claude","https://example.invalid/v1","SYNTHETIC_KEY"),transport=httpx.MockTransport(transport))
    with patch.object(adapter,"_key",return_value="synthetic-key"),pytest.raises(ModelRuntimeError) as failure:
        adapter.generate_text(TextGenerationRequest("claude","user-selected","Synthetic"))
    assert len(sent)==1 and "synthetic-secret-marker" not in str(failure.value)


def test_native_tool_output_is_never_executed_or_silently_accepted():
    adapter=AnthropicTextProvider(CompatibleProviderConfig("claude","https://example.invalid","SYNTHETIC_KEY"),transport=httpx.MockTransport(lambda _:httpx.Response(200,json={"content":[{"type":"tool_use","name":"shell","input":{"command":"untrusted"}}],"stop_reason":"tool_use"})))
    with patch.object(adapter,"_key",return_value="synthetic-key"),pytest.raises(ModelRuntimeError):
        adapter.generate_text(TextGenerationRequest("claude","user-selected","Synthetic"))
