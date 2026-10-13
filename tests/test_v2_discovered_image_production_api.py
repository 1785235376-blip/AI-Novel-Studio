"""Mounted discovered Image contracts on original File/real PostgreSQL owners.

The production app/router and existing trusted-session stack remain real.
Only disposable service dependencies and synthetic model HTTP responses are
rebound. These tests never start an installed runtime, contact a provider,
read private user data, or prove Windows/GPU/model-quality acceptance.
"""
from copy import deepcopy
import hashlib
import json
from uuid import uuid4

import httpx
import pytest

from app.actor_context import SessionContext
from app.services.image_job_service import ImageJobService
from test_r3_mounted_contracts import checked, mounted, prefix, scoped
from test_v2_independent_workspace_api import client
from test_v2_independent_workspace import png_bytes
from test_v2_cpu_cutout_owner import NoControl
from test_v2_discovered_image_production import command, discovery


EXECUTION_FLAGS = ('narrative_production_v2', 'asset_lineage_v2', 'ai_execution_v2',
                   'model_broker_v2', 'author_context_inspector_v2')
PUBLIC_RECIPE_KEYS = {'contract', 'operation_id', 'adapter', 'recipe_digest', 'automatic_fallback',
                      'parameters', 'workflow', 'defaults', 'denoising_strength', 'output_profile',
                      'timeline', 'export_profile'}


@pytest.fixture
def image_client(client, monkeypatch):
    """Reuse the existing test-owned Host registration, not an allow-all guard."""
    from app import asset_provider_config, audio_providers
    e = client
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(EXECUTION_FLAGS))
    monkeypatch.setattr(asset_provider_config, 'load', lambda: {})
    monkeypatch.setattr(audio_providers, 'provider_catalog', lambda: [])
    e.host = 'discovered-image-test-host-' + uuid4().hex
    e.session = SessionContext('session-' + e.host, 'client-' + e.host,
                               'discovered-image-test-author', 'discovered-image-test-workspace')
    e.sessions.register(e.host, e.session)
    e.headers = {'X-Session-Token': e.host}
    checked(e.client.post(e.studio_base + '/activate', headers=e.headers))
    e.discovery, registry, e.adapter = discovery(e.root)
    e.production = e.experimental.studio_production_service
    # Original router closures capture this real service. Preserve its methods
    # and permission invoker while moving dependencies to disposable storage.
    for name, value in (('workspace', e.studio), ('store', e.studio.store),
                        ('image_jobs', ImageJobService(e.root)), ('image_registry', registry),
                        ('video_configs', {}), ('vault', NoControl()), ('transport', NoControl())):
        monkeypatch.setattr(e.production, name, value)
    e.base = e.studio_base + '/production'
    e.command = command(e.adapter, request_id='mounted-discovered-image')
    e.pixels = png_bytes()
    e.calls = []

    def post(url, **kwargs):
        e.calls.append((url, deepcopy(kwargs)))
        return httpx.Response(200, json={'prompt_id': 'synthetic-prompt'},
                              request=httpx.Request('POST', url))

    def get(url, **kwargs):
        e.calls.append((url, deepcopy(kwargs)))
        return httpx.Response(200, json={'synthetic-prompt': {'outputs': {
            '9': {'images': [{'filename': 'synthetic.png'}]}}}}, request=httpx.Request('GET', url))

    monkeypatch.setattr(e.adapter.delegate.transport, 'post', post)
    monkeypatch.setattr(e.adapter.delegate.transport, 'get', get)
    # No download reaches the network: feed bounded genuine PNG bytes through
    # the original decoder/Asset owner so receipt hashes remain meaningful.
    monkeypatch.setattr('app.media_files.fetch_media_bytes', lambda *args, **kwargs: e.pixels)
    e.discovery.client.calls.clear()
    return e


def preview(e):
    return e.client.post(e.base + '/preview', headers=e.headers, json=e.command)


def action(row):
    return {'expected_version': row['version'], 'expected_request_digest': row['request_digest']}


def queue(e):
    captured = checked(preview(e))
    row = checked(e.client.post(e.base + '/jobs', headers=e.headers,
        json={'command': e.command, 'reviewed_preview_digest': captured['preview_digest']}), 201)
    return captured, row


def execute(e, row):
    return e.client.post(e.base + '/jobs/image/' + row['id'] + '/execute',
                         headers=e.headers, json=action(row))


def assert_success_private_headers(response):
    # Original PrivateProductionRoute decorates successful JSON/bytes with both.
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-content-type-options'] == 'nosniff'


def assert_http_exception_private_headers(response):
    # Its original HTTPException path adds no-store only. Pydantic validation
    # is a separate original path, without either additional header promise.
    assert response.headers['cache-control'] == 'no-store'


def test_passive_mounted_catalog_exposes_exact_enabled_ids_without_probe(image_client, monkeypatch):
    e = image_client
    def forbidden(*args, **kwargs):
        raise AssertionError('catalog attempted HTTP, Runtime, credential or inference work')
    monkeypatch.setattr(e.discovery.client, 'json', forbidden)
    monkeypatch.setattr(e.adapter.delegate, 'health_check', forbidden)
    response = e.client.get(e.base + '/providers', headers=e.headers)
    result = checked(response)
    assert_success_private_headers(response)
    assert result['health_probed'] is False and result['credentials_read'] is False
    assert result['automatic_runtime_start'] is False
    assert len(result['items']) == 1
    item = result['items'][0]
    assert item['operation_id'] == 'm5.image.t2i'
    assert item['provider_id'] == e.adapter.candidate['provider_id']
    assert item['model_id'] == e.adapter.candidate['id']
    assert item['local'] is True and item['capability'] == 'TEXT_TO_IMAGE'
    assert item['readiness'] == 'CONFIGURED_NOT_VERIFIED' and item['product_acceptance'] == 'LOCAL_REQUIRED'
    assert set(item) == {'operation_id', 'provider_id', 'model_id', 'local', 'route_digest',
                         'capability', 'supported_parameters', 'readiness', 'product_acceptance'}
    assert 'SDXL.safetensors' not in json.dumps(result)
    assert e.adapter.endpoint not in json.dumps(result)
    assert not e.calls and not e.discovery.client.calls
    assert e.discovery.center.lifecycle.start.call_count == 0


def test_mounted_original_queue_candidate_and_explicit_review_remain_separate(image_client):
    e = image_client
    captured, queued = queue(e)
    assert captured['automatic_dispatch'] is False and e.calls == []
    assert captured['command']['provider_id'] == queued['command']['provider_id'] == e.adapter.candidate['provider_id']
    assert captured['command']['model_id'] == queued['command']['model_id'] == e.adapter.candidate['id']
    assert captured['provider'] == queued['provider']
    assert captured['execution_recipe'] == queued['execution_recipe']
    assert set(captured['execution_recipe']) <= PUBLIC_RECIPE_KEYS
    assert 'registration_digest' not in captured['provider']
    assert queued['status'] == 'QUEUED'
    assert checked(e.client.get(e.studio_base + '/assets', headers=e.headers))['items'] == []
    completed = checked(execute(e, queued))
    assert completed['status'] == 'AWAITING_REVIEW'
    assert completed['product_acceptance'] == 'LOCAL_REQUIRED' and completed['automatic_replay'] is False
    assert len([hit for hit in e.calls if hit[0].endswith('/prompt')]) == 1
    assert e.calls[0][1]['json']['prompt']['4']['inputs']['ckpt_name'] == 'SDXL.safetensors'
    output = completed['output_candidate']
    assert output['digest'] == hashlib.sha256(e.pixels).hexdigest()
    assert e.client.get(e.studio_base + '/assets/' + output['id'], headers=e.headers).status_code == 404
    path = e.base + '/jobs/image/' + queued['id']
    downloaded = e.client.get(path + '/candidate', headers=e.headers)
    assert_success_private_headers(downloaded)
    assert downloaded.status_code == 200 and downloaded.content == e.pixels
    assert downloaded.headers['x-asset-sha256'] == output['digest']
    assert completed['status'] == 'AWAITING_REVIEW'
    approved = checked(e.client.post(path + '/review', headers=e.headers,
        json={**action(completed), 'reviewed_output_digest': output['digest']}))
    assert approved['status'] == 'APPROVED' and approved['approved_asset_version'] == 2
    assert checked(e.client.get(e.studio_base + '/assets/' + output['id'], headers=e.headers))['sha256'] == output['digest']
    assert checked(e.client.get(path, headers=e.headers)) == approved
    assert len([hit for hit in e.calls if hit[0].endswith('/prompt')]) == 1


@pytest.mark.parametrize('change,status', [('missing', 401), ('forged', 401), ('origin', 403), ('forwarded', 403)])
def test_catalog_and_preview_require_original_trusted_host(image_client, change, status):
    e = image_client
    if change == 'missing': headers = {}
    elif change == 'forged': headers = {'X-Session-Token': 'forged'}
    elif change == 'origin': headers = {**e.headers, 'Origin': 'https://untrusted.invalid'}
    else: headers = {**e.headers, 'Forwarded': 'for=127.0.0.1'}
    for method, path, body in [('GET', '/providers', None), ('POST', '/preview', e.command)]:
        response = e.client.request(method, e.base + path, headers=headers, json=body)
        assert response.status_code == status, response.text
        assert_http_exception_private_headers(response)
        assert e.command['prompt'] not in response.text
    assert not e.calls and e.discovery.center.lifecycle.start.call_count == 0


@pytest.mark.parametrize('change', ['extra-command', 'extra-parameter', 'wrong-owner'])
def test_closed_dto_rejects_expansion_before_discovered_dispatch(image_client, change):
    e = image_client
    body = deepcopy(e.command)
    if change == 'extra-command': body['unexpected_field'] = 'synthetic-extra-field'
    elif change == 'extra-parameter': body['parameters']['arbitrary_workflow'] = 'synthetic-extra-field'
    else: body['operation_id'] = 'm5.image.arbitrary'
    response = e.client.post(e.base + '/preview', headers=e.headers, json=body)
    assert response.status_code == 422, response.text
    errors = response.json()['detail']
    expected = ('extra_forbidden', ['body', 'unexpected_field']) if change == 'extra-command' else (
        ('extra_forbidden', ['body', 'parameters', 'arbitrary_workflow']) if change == 'extra-parameter' else
        ('literal_error', ['body', 'operation_id']))
    assert any(error['type'] == expected[0] and error['loc'] == expected[1] for error in errors)
    assert not e.calls


def test_registered_candidate_id_not_runtime_checkpoint_is_the_public_selection(image_client):
    e = image_client
    body = {**e.command, 'model_id': 'SDXL.safetensors'}
    response = e.client.post(e.base + '/preview', headers=e.headers, json=body)
    assert response.status_code == 422, response.text
    assert not e.calls


def test_disabling_the_discovered_registration_invalidates_preview_before_queue(image_client):
    e = image_client
    captured = checked(preview(e))
    e.discovery.disable(e.adapter.candidate['id'])
    assert checked(e.client.get(e.base + '/providers', headers=e.headers))['items'] == []
    response = e.client.post(e.base + '/jobs', headers=e.headers,
        json={'command': e.command, 'reviewed_preview_digest': captured['preview_digest']})
    assert response.status_code in {409, 422}, response.text
    assert not e.calls
    assert checked(e.client.get(e.base + '/jobs', headers=e.headers))['items'] == []


def test_review_requires_original_job_version_and_exact_candidate_digest(image_client):
    e = image_client
    _, queued = queue(e)
    path = e.base + '/jobs/image/' + queued['id']
    wrong_version = {**action(queued), 'expected_version': queued['version'] + 1}
    assert e.client.post(path + '/execute', headers=e.headers, json=wrong_version).status_code == 409
    assert not e.calls
    completed = checked(execute(e, queued))
    response = e.client.post(path + '/review', headers=e.headers,
        json={**action(completed), 'reviewed_output_digest': '0' * 64})
    assert response.status_code == 422, response.text
    assert checked(e.client.get(e.studio_base + '/assets', headers=e.headers))['items'] == []
    assert checked(e.client.get(path, headers=e.headers))['status'] == 'AWAITING_REVIEW'


def test_discovered_transport_rechecks_captured_host_before_poll_or_publication(image_client, monkeypatch):
    e = image_client
    _, queued = queue(e)
    original = e.adapter.delegate.transport.post
    def revoke(url, **kwargs):
        response = original(url, **kwargs)
        e.sessions.revoke(e.host)
        return response
    monkeypatch.setattr(e.adapter.delegate.transport, 'post', revoke)
    response = execute(e, queued)
    assert response.status_code == 401, response.text
    assert_http_exception_private_headers(response)
    assert len(e.calls) == 1 and e.calls[0][0].endswith('/prompt')
    assert e.pixels not in response.content and e.command['prompt'] not in response.text
    assert list(e.assets.root.glob('*.bin')) == []


def test_collaboration_session_does_not_gain_discovered_host_or_review_authority(image_client, monkeypatch):
    e = scoped(image_client, monkeypatch)
    for method, path, body in [('GET', '/providers', None), ('POST', '/preview', e.command)]:
        response = e.client.request(method, e.base + path, headers=e.headers, json=body)
        assert response.status_code == 403, response.text
        assert_http_exception_private_headers(response)
    assert not e.calls and e.discovery.center.lifecycle.start.call_count == 0
