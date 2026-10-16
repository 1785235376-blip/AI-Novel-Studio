"""Verify the hosted journey's synthetic boundaries without launching a browser."""
from pathlib import Path
import json
import os
import subprocess
import sys

import pytest
from v2_discovery_browser_server import SyntheticDiscoveryFixture, LABEL, model_mutation_forbidden
from test_local_ai_discovery import service


def test_fixture_probe_is_closed_metadata_only_and_never_falls_back_to_http(tmp_path, monkeypatch):
    fixture = SyntheticDiscoveryFixture(tmp_path / 'adapter', delay_seconds=0)
    def network_forbidden(*_args, **_kwargs):
        raise AssertionError('No network transport belongs in the synthetic adapter')
    monkeypatch.setattr('urllib.request.urlopen', network_forbidden)
    monkeypatch.setattr('socket.create_connection', network_forbidden)
    assert fixture.json('http://127.0.0.1:11434', '/api/tags') == {'models': []}
    for endpoint, path, body in [('http://127.0.0.1:1', '/api/tags', None), ('http://127.0.0.1:11434', '/api/show', {}), ('http://127.0.0.1:11434', '/api/tags', {})]:
        with pytest.raises(AssertionError, match='UNAPPROVED_PROBE'):
            fixture.json(endpoint, path, body=body)
    assert len(fixture.calls) == 1
    assert fixture.hardware()['platform'] == 'SYNTHETIC_BROWSER_FIXTURE'


def test_fixture_reuses_original_service_and_only_its_owned_empty_directory(tmp_path):
    fixture = SyntheticDiscoveryFixture(tmp_path / 'adapter', delay_seconds=0)
    original = service(tmp_path)
    center = original.center
    fixture.install(original)
    assert original.center is center and original.client is fixture
    assert original.settings == {'scan_roots': [], 'runtimes': [], 'include_common_model_dirs': False}
    assert not center.runtimes and not center.models and not center.pipelines
    assert fixture.require_path(fixture.common) == fixture.common
    for value in (tmp_path, tmp_path / 'not-owned', fixture.common / 'unexpected-model.gguf'):
        with pytest.raises(AssertionError, match='UNAPPROVED_FILESYSTEM_TARGET'):
            fixture.require_path(value)
    with pytest.raises(AssertionError, match='PROGRAM_LAUNCH_FORBIDDEN'):
        center.lifecycle.start('anything')
    assert fixture.launch_attempts == 1


@pytest.mark.parametrize('mode', ['enabled', 'default-off', 'acceptance'])
def test_original_mounted_file_http_fixture_preview_confirmation_and_report_without_browser(tmp_path, mode):
    root = tmp_path / 'owned-process'
    for directory in ('home', 'data', 'cache', 'config', 'local', 'tmp'):
        (root / directory).mkdir(parents=True)
    env = {**os.environ, 'V2_DISCOVERY_FIXTURE_ROOT': str(root), 'NOVEL_DATA_PATH': str(root / 'novel-data'),
           'HOME': str(root / 'home'), 'USERPROFILE': str(root / 'home'), 'APPDATA': str(root / 'local'), 'XDG_DATA_HOME': str(root / 'data'), 'XDG_CACHE_HOME': str(root / 'cache'),
           'XDG_CONFIG_HOME': str(root / 'config'), 'LOCALAPPDATA': str(root / 'local'), 'TMPDIR': str(root / 'tmp'),
           'STORAGE_BACKEND': 'file', 'ENABLE_COLLABORATION_RUNTIME': 'false', 'ENABLE_PACKAGED_RUNTIME': 'false',
           'MOCK_PROVIDER': 'true', 'ENABLE_CLOUD': 'false', 'ENABLE_PROVIDER_FALLBACK': 'false',
           'EXPERIMENTAL_FEATURES': '' if mode == 'default-off' else 'narrative_production_v2', 'V1_ACCEPTANCE_MODE': str(mode == 'acceptance').lower(),
           'COLLABORATION_DEV_SESSIONS_JSON': '', 'FRONTEND_ORIGIN': 'http://127.0.0.1:5187',
           'CREDENTIAL_VAULT_BACKEND': 'memory', 'CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK': 'true'}
    command = [sys.executable, str(Path(__file__).with_name('v2_discovery_browser_server.py')), '--self-check']
    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    receipt = json.loads(result.stdout.strip().splitlines()[-1])
    assert receipt['fixture'] == LABEL and receipt['synthetic'] is True
    assert receipt['hardware_calls'] == (1 if mode == 'enabled' else 0)
    assert len(receipt['probe_calls']) == (7 if mode == 'enabled' else 0)
    assert receipt['scan_status'] == ('COMPLETED' if mode == 'enabled' else None)
    assert receipt['inference_status'] == receipt['windows_acceptance'] == 'NOT_RUN'
    assert receipt['registrations'] == receipt['enabled_registrations'] == receipt['launch_attempts'] == 0
    assert receipt['model_weights_loaded'] is False and receipt['blocked_attempts'] == []

@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_fixture_model_mutations_fail_closed_in_both_mounted_aliases(prefix):
    for suffix in ('/runtimes/new', '/registrations/model/enable', '/candidates/model/validate'):
        assert model_mutation_forbidden(prefix + '/model-center/local-ai' + suffix, 'POST')
    assert model_mutation_forbidden(prefix + '/model-center/runtimes/example/start', 'POST')
    assert not model_mutation_forbidden(prefix + '/model-center/local-ai/onboarding/scan', 'POST')
    assert not model_mutation_forbidden(prefix + '/model-center/local-ai/scan/example/cancel', 'POST')
    assert not model_mutation_forbidden(prefix + '/model-center/local-ai/environment', 'GET')
