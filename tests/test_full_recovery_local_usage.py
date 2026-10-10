"""Use measured local runtime accounting; never invent token counts."""
from types import SimpleNamespace
import json

import pytest

from app.model_center.discovery_bridge import LocalTextAdapter
from app.model_runtime import ModelRuntimeError, RuntimeErrorCode, TextGenerationRequest


@pytest.mark.parametrize('measured, expected', [
    ({'prompt_tokens': 9, 'completion_tokens': 3, 'total_tokens': 12}, (9, 3, 12)),
    ({'prompt_tokens': -1, 'completion_tokens': True}, None),
    (None, None),
])
def test_local_llama_response_retains_only_reported_usage(measured, expected):
    candidate = {'id': 'candidate', 'provider_id': 'local-test', 'model_name': 'local-model',
                 'runtime_config': {'type': 'LLAMA_CPP', 'management': 'EXTERNAL', 'endpoint': 'http://127.0.0.1:8091'}}
    bridge = SimpleNamespace(guard=lambda identity: candidate,
        service=SimpleNamespace(check_model_dispatch=lambda record: None))
    adapter = LocalTextAdapter(bridge, candidate)
    adapter.client = SimpleNamespace(json=lambda *args, **kwargs:
        {'choices': [{'message': {'content': 'contract text'}}], 'usage': measured})
    response = adapter.generate_text(TextGenerationRequest('local-test', 'candidate', 'contract prompt'))
    if expected is None:
        assert response.usage is None
    else:
        assert (response.usage.input_tokens, response.usage.output_tokens, response.usage.total_tokens) == expected


def test_local_llama_forwards_structured_schema_and_rejects_incomplete_output():
    candidate = {'id': 'candidate', 'provider_id': 'local-test', 'model_name': 'local-model',
                 'runtime_config': {'type': 'LLAMA_CPP', 'management': 'EXTERNAL', 'endpoint': 'http://127.0.0.1:8091'}}
    bridge = SimpleNamespace(guard=lambda identity: candidate,
        service=SimpleNamespace(check_model_dispatch=lambda record: None))
    adapter = LocalTextAdapter(bridge, candidate)
    schema = {'type': 'object', 'required': ['summary'], 'properties': {'summary': {'type': 'string', 'maxLength': 12000}}}
    finish = ['stop']
    def transport(_endpoint, _path, *, body):
        assert body['response_format'] == {'type': 'json_object', 'schema': {'type': 'object', 'required': ['summary'], 'properties': {'summary': {'type': 'string'}}}}
        return {'choices': [{'message': {'content': '{"summary":"contract"}'}, 'finish_reason': finish[0]}]}
    adapter.client = SimpleNamespace(json=transport)
    request = TextGenerationRequest('local-test', 'candidate', 'contract prompt', structured_output_schema=schema)
    assert adapter.generate_text(request).text == '{"summary":"contract"}'
    for reason in ('length', 'content_filter'):
        finish[0] = reason
        with pytest.raises(ModelRuntimeError) as error:
            adapter.generate_text(request)
        assert error.value.code == RuntimeErrorCode.GENERATION_FAILED
    finish[0] = 'stop'
    adapter.client = SimpleNamespace(json=lambda *_a, **_k: {'choices':[{'message':{'content':json.dumps({'summary':'x'*12001})},'finish_reason':'stop'}]})
    with pytest.raises(ModelRuntimeError) as error:
        adapter.generate_text(request)
    assert error.value.code == RuntimeErrorCode.GENERATION_FAILED


def test_unsupported_local_structured_schema_is_rejected_before_transport():
    candidate = {'id': 'candidate', 'provider_id': 'local-test', 'model_name': 'local-model',
                 'runtime_config': {'type': 'OLLAMA', 'management': 'EXTERNAL', 'endpoint': 'http://127.0.0.1:11434'}}
    bridge = SimpleNamespace(guard=lambda identity: candidate)
    adapter = LocalTextAdapter(bridge, candidate)
    adapter.client = SimpleNamespace(json=lambda *_a, **_k: pytest.fail('unsupported schema must not dispatch'))
    with pytest.raises(ModelRuntimeError) as error:
        adapter.generate_text(TextGenerationRequest('local-test', 'candidate', 'contract prompt', structured_output_schema={'type':'object'}))
    assert error.value.code == RuntimeErrorCode.CAPABILITY_NOT_SUPPORTED
