"""Readiness must agree with the original vault-only packaged transport."""
from dataclasses import replace
from unittest.mock import patch
import pytest


@pytest.mark.parametrize('provider,variable', [('claude', 'ANTHROPIC_API_KEY'), ('gemini', 'GEMINI_API_KEY')])
def test_packaged_host_readiness_does_not_advertise_environment_credentials(tmp_path, monkeypatch, provider, variable):
    import app.runtime as runtime_module
    from app.stable_identity import StableIdentityStore
    from app.credential_vault import credential_vault
    monkeypatch.setattr(runtime_module, 'settings', replace(runtime_module.settings, enable_packaged_runtime=False, enable_cloud=False))
    monkeypatch.setenv('PACKAGED_WINDOWS_MODE', 'true')
    monkeypatch.setenv(variable, 'synthetic-test-key')
    monkeypatch.setattr(credential_vault, 'has', lambda _: False)
    with patch('httpx.Client.send', side_effect=AssertionError('No network during registration')):
        runtime = runtime_module.Runtime(StableIdentityStore(tmp_path / 'identity.json'))
        runtime.register_native_text_route(provider, 'explicit-test-model')
    descriptor = next(row for row in runtime.provider_registry.descriptors() if row.provider_id == provider)
    assert not descriptor.configured and not descriptor.available
    assert descriptor.health_status == 'not_configured'

@pytest.mark.parametrize('provider,variable', [('claude', 'ANTHROPIC_API_KEY'), ('gemini', 'GEMINI_API_KEY')])
@pytest.mark.parametrize('mode,vault,expected', [('development', False, True), ('settings-packaged', False, False), ('windows-packaged', True, True)])
def test_native_readiness_preserves_development_and_original_vault_positive_paths(tmp_path, monkeypatch, provider, variable, mode, vault, expected):
    import app.runtime as runtime_module
    from app.stable_identity import StableIdentityStore
    from app.credential_vault import credential_vault
    monkeypatch.setattr(runtime_module, 'settings', replace(runtime_module.settings, enable_packaged_runtime=mode == 'settings-packaged', enable_cloud=False))
    monkeypatch.setenv('PACKAGED_WINDOWS_MODE', 'true' if mode == 'windows-packaged' else 'false')
    monkeypatch.setenv(variable, 'synthetic-test-key')
    monkeypatch.setattr(credential_vault, 'has', lambda current: vault and current == provider)
    with patch('httpx.Client.send', side_effect=AssertionError('No network during registration')):
        runtime = runtime_module.Runtime(StableIdentityStore(tmp_path / 'identity.json'))
        runtime.register_native_text_route(provider, 'explicit-test-model')
    descriptor = next(row for row in runtime.provider_registry.descriptors() if row.provider_id == provider)
    assert descriptor.configured is expected and descriptor.available is expected
    assert descriptor.health_status == ('configured_unverified' if expected else 'not_configured')
    assert runtime_module.settings.enable_cloud is False
