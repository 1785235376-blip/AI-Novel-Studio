from __future__ import annotations
import json, os
from threading import Event
import httpx, pytest
from app.model_runtime import ModelRuntimeError,RuntimeErrorCode,TextGenerationParameters,TextGenerationRequest
from app.openai_compatible import CompatibleProviderConfig,OpenAICompatibleTextProvider

SECRET="sk-phase2b-secret"
def request(**changes):
    values=dict(provider_id="deepseek",model_id="deepseek-chat",prompt="Reply with one word.",system_instruction="Be concise",parameters=TextGenerationParameters(temperature=.2,max_output_tokens=8),job_id="job")
    values.update(changes);return TextGenerationRequest(**values)
def provider(handler):
    return OpenAICompatibleTextProvider(CompatibleProviderConfig("deepseek","https://unit.invalid/v1","DEEPSEEK_API_KEY"),transport=httpx.MockTransport(handler))

def test_non_stream_request_response_usage_and_secret_header(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY",SECRET)
    def handler(r):
        body=json.loads(r.content);assert r.headers["Authorization"]=="Bearer "+SECRET;assert body["messages"][0]["role"]=="system";assert body["max_tokens"]==8
        return httpx.Response(200,json={"id":"ref","choices":[{"message":{"content":"OK"},"finish_reason":"stop"}],"usage":{"prompt_tokens":3,"completion_tokens":1,"total_tokens":4}})
    result=provider(handler).generate_text(request())
    assert (result.text,result.finish_reason,result.usage.total_tokens)==("OK","stop",4)

def test_sse_fragment_safe_stream_finish_usage(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY",SECRET)
    body='data: '+json.dumps({"id":"ref","choices":[{"delta":{"content":"O"},"finish_reason":None}]})+'\n\n'+'data: '+json.dumps({"choices":[{"delta":{"content":"K"},"finish_reason":"stop"}],"usage":{"prompt_tokens":2,"completion_tokens":1,"total_tokens":3}})+'\n\ndata: [DONE]\n\n'
    events=list(provider(lambda r:httpx.Response(200,content=body.encode())).stream_text(request()))
    assert [e.event_type for e in events]==["generation.started","generation.delta","generation.delta","generation.completed"]
    assert events[-1].response.text=="OK" and events[-1].response.usage.total_tokens==3

@pytest.mark.parametrize("status,code",[(401,RuntimeErrorCode.AUTHENTICATION_FAILED),(429,RuntimeErrorCode.RATE_LIMITED),(404,RuntimeErrorCode.MODEL_NOT_FOUND),(400,RuntimeErrorCode.INVALID_REQUEST),(503,RuntimeErrorCode.PROVIDER_UNAVAILABLE)])
def test_http_error_mapping_and_secret_redaction(monkeypatch,status,code):
    monkeypatch.setenv("DEEPSEEK_API_KEY",SECRET)
    with pytest.raises(ModelRuntimeError) as caught:provider(lambda r:httpx.Response(status,text=SECRET,headers={"retry-after":"2"})).generate_text(request())
    assert caught.value.code is code and SECRET not in caught.value.safe_message and SECRET not in repr(caught.value.metadata)

def test_missing_credential_is_invalid_configuration(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY",raising=False)
    with pytest.raises(ModelRuntimeError) as caught:provider(lambda r:httpx.Response(200)).generate_text(request())
    assert caught.value.code is RuntimeErrorCode.INVALID_CONFIGURATION

def test_explicit_probe_verifies_remote_reachability(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", SECRET)
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): return False
    calls = []
    def fake_open(request, timeout):
        calls.append((request.full_url, request.get_header("Authorization"), timeout))
        return Response()
    monkeypatch.setattr("app.providers.urlopen", fake_open)
    from app.providers import OpenAICompatibleProvider
    result = OpenAICompatibleProvider("deepseek", "https://api.deepseek.com/v1", "DEEPSEEK_API_KEY").probe()
    assert result == {"configured": True, "reachable": True, "status_code": 200}
    assert calls == [("https://api.deepseek.com/v1/models", "Bearer " + SECRET, 8.0)]

def test_timeout_and_connection_mapping(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY",SECRET)
    for exc,code in ((httpx.ReadTimeout("late"),RuntimeErrorCode.TIMEOUT),(httpx.ConnectError("down"),RuntimeErrorCode.PROVIDER_UNAVAILABLE)):
        with pytest.raises(ModelRuntimeError) as caught:provider(lambda r,e=exc:(_ for _ in ()).throw(e)).generate_text(request())
        assert caught.value.code is code

def test_cancel_before_stream_opens_no_request(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY",SECRET);signal=Event();signal.set();called=False
    def handler(r):
        nonlocal called;called=True;return httpx.Response(200)
    with pytest.raises(ModelRuntimeError) as caught:list(provider(handler).stream_text(request(cancellation=signal)))
    assert caught.value.code is RuntimeErrorCode.CANCELLED and not called

def test_cancel_during_stream_closes_owned_response(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY",SECRET);signal=Event()
    class Stream(httpx.SyncByteStream):
        closed=False
        def __iter__(self):
            yield ('data: '+json.dumps({"choices":[{"delta":{"content":"A"},"finish_reason":None}]})+'\n\n').encode()
            signal.set()
            yield ('data: '+json.dumps({"choices":[{"delta":{"content":"B"},"finish_reason":None}]})+'\n\n').encode()
        def close(self):self.closed=True
    stream=Stream()
    with pytest.raises(ModelRuntimeError) as caught:list(provider(lambda r:httpx.Response(200,stream=stream)).stream_text(request(cancellation=signal)))
    assert caught.value.code is RuntimeErrorCode.CANCELLED
    assert stream.closed is True

def test_overall_timeout_is_normalized(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY",SECRET)
    value=provider(lambda r:httpx.Response(200,content=b'data: [DONE]\n\n'))
    object.__setattr__(value.config,"overall_timeout",-1)
    with pytest.raises(ModelRuntimeError) as caught:list(value.stream_text(request()))
    assert caught.value.code is RuntimeErrorCode.TIMEOUT
    assert caught.value.metadata == {"phase":"OVERALL"}
