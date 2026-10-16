"""Mounted host-session boundary for cached V2 prerequisite observations."""
from __future__ import annotations

import json
from unittest.mock import Mock

import pytest

from test_v2_discovery_onboarding_api import HEADERS, onboard  # noqa: F401
from test_v2_discovery_file_projection import confirmed_scan
from test_v2_discovery_prerequisites import configure_comfy, object_info, workflow


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_mounted_projections_read_identical_same_scan_prerequisites_without_io(onboard, monkeypatch, prefix):
    client, svc, _ = onboard
    base = prefix + '/model-center/local-ai'
    configure_comfy(svc, object_info(svc))
    before = client.get(base + '/environment', headers=HEADERS)
    assert before.status_code == 200 and before.json()['workflow_prerequisites'] is None
    assert svc.client.calls == []
    job = confirmed_scan(client, base)
    assert workflow(job)['evidence_status'] == 'COMPLETE'
    guard = Mock(side_effect=AssertionError('GET cannot probe, read metadata, or enumerate'))
    monkeypatch.setattr(svc.client, 'json', guard)
    monkeypatch.setattr(svc, 'hardware_probe', guard)
    monkeypatch.setattr('app.model_center.discovery_environment._metadata_bytes', guard)
    monkeypatch.setattr('app.model_center.discovery_environment._scoped_scandir', guard)
    for suffix in ('', '/scan/' + job['id'], '/environment'):
        response = client.get(base + suffix, headers=HEADERS)
        assert response.status_code == 200, response.text
        assert response.headers['Cache-Control'] == 'no-store'
        data = response.json()['scan'] if suffix == '' else response.json()
        assert data['workflow_prerequisites'] == job['workflow_prerequisites']
    guard.assert_not_called()
    assert not svc.registrations
    svc.center.lifecycle.start.assert_not_called()


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
@pytest.mark.parametrize('enabled', [True, False])
def test_revocation_denies_cached_prerequisites_even_after_feature_disabled(onboard, monkeypatch, prefix, enabled):
    client, svc, sessions = onboard
    base = prefix + '/model-center/local-ai'
    configure_comfy(svc, object_info(svc, ['synthetic-private-checkpoint']))
    job = confirmed_scan(client, base)
    assert workflow(job)['loader']['candidate_ids']
    sessions.revoke(HEADERS['X-Session-Token'])
    if not enabled: monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    for suffix in ('', '/scan/' + job['id'], '/environment'):
        response = client.get(base + suffix, headers=HEADERS)
        assert response.status_code == 401
        assert 'workflow_prerequisites' not in response.text
        assert 'synthetic-private-checkpoint' not in response.text
        assert response.headers['Cache-Control'] == 'no-store'


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_untrusted_request_cannot_read_or_trigger_prerequisite_evidence(onboard, prefix):
    client, svc, _ = onboard
    base = prefix + '/model-center/local-ai'
    for suffix in ('', '/environment', '/onboarding/scan-scope'):
        response = client.get(base + suffix, headers={'X-Session-Token': 'unregistered', 'X-Actor-Id': 'host'})
        assert response.status_code == 401
        assert 'workflow_prerequisites' not in response.text
    assert client.post(base + '/onboarding/scan', json={'scope_digest': 'a' * 64, 'confirmed': True}).status_code == 401
    assert svc.scan is None and not svc.client.calls


@pytest.mark.parametrize('acceptance', [True, False])
def test_default_off_and_acceptance_original_http_scan_omit_extension(onboard, monkeypatch, acceptance):
    client, svc, _ = onboard
    if acceptance: monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    else: monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    base = '/api/model-center/local-ai'
    response = client.post(base + '/scan', headers=HEADERS)
    assert response.status_code == 202
    assert 'workflow_prerequisites' not in json.dumps(response.json())
    assert client.get(base + '/environment', headers=HEADERS).status_code == 404
