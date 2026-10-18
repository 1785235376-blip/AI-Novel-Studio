"""The existing packaged Windows marker must not admit development stand-ins."""
from dataclasses import replace
from unittest.mock import patch
import pytest


def host(tmp_path, monkeypatch, mock=True):
    import app.runtime as module
    from app.stable_identity import StableIdentityStore
    from app.credential_vault import credential_vault
    from app.providers import OllamaProvider
    monkeypatch.setattr(module, 'settings', replace(module.settings, enable_packaged_runtime=False, mock_provider=mock, enable_cloud=False))
    monkeypatch.setenv('PACKAGED_WINDOWS_MODE', 'true')
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'synthetic-test-key')
    monkeypatch.setattr(credential_vault, 'has', lambda _: False)
    monkeypatch.setattr(OllamaProvider, 'health_check', lambda _: False)
    monkeypatch.setattr(OllamaProvider, 'list_models', lambda *a, **k: [])
    with patch('httpx.Client.send', side_effect=AssertionError('No external request')):
        return module.Runtime(StableIdentityStore(tmp_path / 'identity.json'))


@pytest.mark.parametrize('boundary', ['standin', 'author', 'router', 'status'])
def test_packaged_marker_fences_original_runtime_without_settings_alias(tmp_path, monkeypatch, boundary):
    value = host(tmp_path, monkeypatch, mock=boundary != 'status')
    if boundary == 'standin':
        assert value._deepseek_execution_mode == 'real'
    elif boundary == 'author':
        assert value.packaged_author_route_ready('mock') is False
        assert value.packaged_author_route_ready('deepseek') is False
    elif boundary == 'router':
        assert [route.provider for route in value.router('LOCAL_ONLY', 'writer').routes['writer']] == ['ollama']
    else:
        status = value.provider_status()['deepseek']
        assert status['configured'] is False and status['available'] is False
        assert status['execution_mode'] == 'real'
