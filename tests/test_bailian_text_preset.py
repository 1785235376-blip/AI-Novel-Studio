"""Synthetic transport and host registration checks; no paid API or real key."""
import json
from unittest.mock import patch

import httpx
import pytest

from app.bailian_text_preset import BAILIAN_REGION_URLS, BailianTextProvider, bailian_configuration
from app.model_runtime import TextGenerationRequest, RuntimeErrorCode, ModelRuntimeError


@pytest.mark.parametrize('region', list(BAILIAN_REGION_URLS))
def test_region_fixed_endpoint_and_original_payload(region):
    seen = []
    def handle(request):
        seen.append(request)
        return httpx.Response(200, json={'id': 'synthetic', 'choices': [{'message': {'content': 'Synthetic answer'}, 'finish_reason': 'stop'}], 'usage': {'prompt_tokens': 4, 'completion_tokens': 2, 'total_tokens': 6}})
    adapter = BailianTextProvider(region, transport=httpx.MockTransport(handle))
    with patch.object(adapter, '_key', return_value='synthetic-test-key'):
        result = adapter.generate_text(TextGenerationRequest('aliyun-bailian', 'user-selected-model', 'Synthetic prompt'))
    assert result.text == 'Synthetic answer'
    assert str(seen[0].url) == BAILIAN_REGION_URLS[region] + '/chat/completions'
    assert json.loads(seen[0].content)['enable_thinking'] is False
    assert json.loads(seen[0].content)['model'] == 'user-selected-model'
    assert seen[0].headers['authorization'] == 'Bearer synthetic-test-key'
    assert 'synthetic-test-key' not in str(seen[0].url) and b'synthetic-test-key' not in seen[0].content


@pytest.mark.parametrize('region', ['', 'https://example.invalid', 'cn-beijing/extra', 'coding-plan', None])
def test_rejects_nonpreset_regions(region):
    with pytest.raises(ValueError, match='BAILIAN_PRESET_REGION_UNSUPPORTED'):
        bailian_configuration(region)


def test_original_streaming_and_usage_are_reused():
    frames = [{'choices': [{'delta': {'content': 'Hello'}}]}, {'choices': [{'delta': {}, 'finish_reason': 'stop'}], 'usage': {'prompt_tokens': 3, 'completion_tokens': 2, 'total_tokens': 5}}]
    adapter = BailianTextProvider(transport=httpx.MockTransport(lambda _: httpx.Response(200, text=''.join('data: ' + json.dumps(frame) + '\n\n' for frame in frames) + 'data: [DONE]\n\n')))
    with patch.object(adapter, '_key', return_value='synthetic-test-key'):
        events = list(adapter.stream_text(TextGenerationRequest('aliyun-bailian', 'user-selected-model', 'Synthetic')))
    assert events[-1].event_type == 'generation.completed'
    assert events[-1].response.text == 'Hello'
    assert events[-1].response.usage.total_tokens == 5


def test_registration_is_explicit_remote_unverified_and_does_not_enable_cloud(tmp_path, monkeypatch):
    from app.runtime import Runtime
    from app.stable_identity import StableIdentityStore
    from app.credential_vault import credential_vault
    from app.config import settings
    monkeypatch.delenv('ALIYUN_BAILIAN_MODEL', raising=False)
    monkeypatch.delenv('DASHSCOPE_API_KEY', raising=False)
    monkeypatch.setattr(credential_vault, 'has', lambda provider: False)
    from dataclasses import replace
    import app.runtime as runtime_module
    monkeypatch.setattr(runtime_module, 'settings', replace(settings, enable_cloud=False))
    with patch('httpx.Client.send', side_effect=AssertionError('No network during registration')):
        runtime = Runtime(StableIdentityStore(tmp_path / 'identities.json'))
        assert not runtime.provider_registry.contains('aliyun-bailian')
        runtime.register_bailian_text_route('user-selected-model', 'cn-beijing')
    descriptor = next(row for row in runtime.provider_registry.descriptors() if row.provider_id == 'aliyun-bailian')
    assert descriptor.provider_type == 'remote' and not descriptor.configured and descriptor.health_status == 'not_configured'
    assert runtime.is_remote_text_provider('aliyun-bailian') and not runtime_module.settings.enable_cloud
    with pytest.raises(ModelRuntimeError) as failure:
        runtime.prepare_text_route('aliyun-bailian', 'user-selected-model')
    assert failure.value.code == RuntimeErrorCode.INVALID_CONFIGURATION


def test_packaged_preset_does_not_use_environment_key(tmp_path, monkeypatch):
    from app.runtime import Runtime
    from app.stable_identity import StableIdentityStore
    from app.credential_vault import credential_vault
    monkeypatch.setenv('PACKAGED_WINDOWS_MODE', 'true')
    monkeypatch.setenv('DASHSCOPE_API_KEY', 'synthetic-test-key')
    monkeypatch.setenv('ALIYUN_BAILIAN_MODEL', 'user-selected-model')
    monkeypatch.setattr(credential_vault, 'has', lambda provider: False)
    runtime = Runtime(StableIdentityStore(tmp_path / 'identities.json'))
    descriptor = next(row for row in runtime.provider_registry.descriptors() if row.provider_id == 'aliyun-bailian')
    assert not descriptor.configured
