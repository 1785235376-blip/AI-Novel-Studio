"""Legacy cloud transport must honor the normalized author request contract."""
import json
from threading import Event

import pytest

from app.providers import OpenAICompatibleProvider, ProviderError


class Response:
    def __init__(self, payload):
        self.payload = payload
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def read(self):
        return json.dumps(self.payload).encode()

    def __iter__(self):
        for item in self.payload:
            yield ('data: ' + (item if isinstance(item, str) else json.dumps(item)) + '\n').encode()


def provider(monkeypatch):
    monkeypatch.setenv('RECOVERY_TEST_KEY', 'synthetic-contract-secret')
    return OpenAICompatibleProvider('recovery-test', 'https://unit.invalid/v1', 'RECOVERY_TEST_KEY')


@pytest.mark.parametrize('stream', [False, True])
def test_author_parameters_reach_cloud_transport(monkeypatch, stream):
    sent = []
    def open_request(request, timeout):
        sent.append(json.loads(request.data))
        return Response([{'choices': [{'delta': {'content': 'ok'}, 'finish_reason': 'stop'}]}, '[DONE]'] if stream else
                        {'choices': [{'message': {'content': 'ok'}}]})
    monkeypatch.setattr('app.providers.urlopen', open_request)
    value = provider(monkeypatch)
    call = value.stream if stream else value.generate
    result = call('prompt', 'model', temperature=0.3, max_tokens=128, stop=['END'])
    if stream:
        assert ''.join(result) == 'ok'
    assert sent[0]['temperature'] == 0.3
    assert sent[0]['max_tokens'] == 128
    assert sent[0]['stop'] == ['END']


@pytest.mark.parametrize('stream', [False, True])
def test_cancelled_dispatch_never_opens_cloud_request(monkeypatch, stream):
    cancellation = Event()
    cancellation.set()
    opened = []
    monkeypatch.setattr('app.providers.urlopen', lambda *args, **kwargs: opened.append(True))
    value = provider(monkeypatch)
    with pytest.raises(ProviderError, match='cancel'):
        result = (value.stream if stream else value.generate)('prompt', 'model', cancellation=cancellation)
        if stream:
            list(result)
    assert opened == []


def test_stream_usage_and_dispatch_reauthorization(monkeypatch):
    calls = []
    response = Response([
        {'choices': [{'delta': {'content': 'ok'}, 'finish_reason': 'stop'}]},
        {'choices': [], 'usage': {'prompt_tokens': 7, 'completion_tokens': 2}}, '[DONE]'])
    monkeypatch.setattr('app.providers.urlopen', lambda *args, **kwargs: response)
    usage = {}
    assert ''.join(provider(monkeypatch).stream('prompt', 'model',
        dispatch_guard=lambda: calls.append('authorized'), usage_callback=usage.update)) == 'ok'
    assert calls == ['authorized']
    assert usage == {'input_tokens': 7, 'output_tokens': 2}
    assert response.closed
