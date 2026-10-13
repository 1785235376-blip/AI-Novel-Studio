"""Original discovered-image owner contracts; synthetic HTTP, never real inference."""
from copy import deepcopy
from types import SimpleNamespace
import base64
import hashlib
import json

import httpx
import pytest

from app.asset_providers import AssetGenerationRequest, AssetGenerationResult, AssetProviderRegistry
from app.creative.production_execution import ProductionExecutionService, digest
from app.creative.production_execution_models import MediaCommand, MediaJobAction, MediaReview, ProviderSelection
from app.model_center.discovery_bridge import LocalDiscoveryBridge
from app.model_runtime import ModelRegistry, ProviderRegistry
from app.services.image_job_service import ImageJobService
from test_local_ai_discovery import service, scan, approve_license
from test_v2_independent_workspace import rig, reopened, png_bytes


def discovery(tmp_path, kind='COMFYUI'):
    original = service(tmp_path)
    endpoint = 'http://127.0.0.1:8188' if kind == 'COMFYUI' else 'http://127.0.0.1:7860'
    if kind == 'COMFYUI':
        info = {node: {'input': {'required': {}}} for node in original.workflow_adapters[0]['required_nodes']}
        info['CheckpointLoaderSimple']['input']['required']['ckpt_name'] = [['SDXL.safetensors']]
        original.client.payloads[(endpoint, '/system_stats')] = {'system': {}}
        original.client.payloads[(endpoint, '/object_info')] = info
    else:
        original.client.payloads[(endpoint, '/sdapi/v1/sd-models')] = [{'title': 'SDXL.safetensors'}]
    registry = AssetProviderRegistry()
    original.route_bridge = LocalDiscoveryBridge(original, SimpleNamespace(provider_registry=ProviderRegistry(),
        model_registry=ModelRegistry()), registry)
    candidate = scan(original)['candidates'][0]
    original.validate(candidate['id']); original.register(candidate['id']); approve_license(original, candidate['id'])
    original.enable(candidate['id'])
    return original, registry, registry.get(candidate['provider_id'])


def owner(registry, monkeypatch, environment=None):
    from app import asset_provider_config, audio_providers
    monkeypatch.setattr(asset_provider_config, 'load', lambda: {})
    monkeypatch.setattr(audio_providers, 'provider_catalog', lambda: [])
    if environment is None:
        result = ProductionExecutionService.__new__(ProductionExecutionService)
        result.image_registry, result.video_configs = registry, {}
        result._base = lambda *args: {}
        return result
    monkeypatch.setenv('EXPERIMENTAL_FEATURES',
        'narrative_production_v2,asset_lineage_v2,ai_execution_v2,model_broker_v2,author_context_inspector_v2')
    environment.service.activate(environment.nid, environment.scope, environment.actor)
    return ProductionExecutionService(environment.service, ImageJobService(environment.root), registry,
        SimpleNamespace(), {}, {}, SimpleNamespace(), SimpleNamespace(), SimpleNamespace())


def command(adapter, request_id='synthetic-discovered-image'):
    return {'operation_id': 'm5.image.t2i', 'request_id': request_id,
        'provider_id': adapter.candidate['provider_id'], 'model_id': adapter.candidate['id'],
        'prompt': 'SYNTHETIC PRIVATE PIXELS', 'parameters': {'seed': 3, 'width': 64, 'height': 64}}


@pytest.mark.parametrize('kind', ['COMFYUI', 'AUTOMATIC1111'])
def test_enabled_original_image_routes_are_passive_and_t2i_only(tmp_path, monkeypatch, kind):
    original, registry, adapter = discovery(tmp_path, kind)
    production = owner(registry, monkeypatch)
    original.client.calls.clear()
    def forbidden(*args, **kwargs): raise AssertionError('passive listing attempted runtime, model, credential or HTTP work')
    monkeypatch.setattr(original.client, 'json', forbidden)
    monkeypatch.setattr(original, 'media_routes', forbidden)
    monkeypatch.setattr(adapter.delegate, 'health_check', forbidden)
    result = production.providers('project', {}, 'actor', lambda: None)
    assert result == {'items': [{'operation_id': 'm5.image.t2i', 'provider_id': adapter.candidate['provider_id'],
        'model_id': adapter.candidate['id'], 'local': True,
        'route_digest': production._binding(ProviderSelection(**{key: command(adapter)[key]
            for key in ('operation_id', 'provider_id', 'model_id')}))['route_digest'],
        'capability': 'TEXT_TO_IMAGE', 'supported_parameters': ['width', 'height', 'steps', 'seed', 'negative_prompt'],
        'readiness': 'CONFIGURED_NOT_VERIFIED', 'product_acceptance': 'LOCAL_REQUIRED'}],
        'automatic_runtime_start': False, 'health_probed': False, 'credentials_read': False}
    assert not original.client.calls and original.center.lifecycle.start.call_count == 0
    assert 'endpoint' not in result['items'][0] and 'registration_digest' not in result['items'][0]
    with pytest.raises(ValueError, match='STUDIO_IMAGE_EDIT_PROVIDER_UNSUPPORTED'):
        production._binding(ProviderSelection(operation_id='m5.image.i2i', provider_id=adapter.candidate['provider_id'],
            model_id=adapter.candidate['id']))


@pytest.mark.parametrize('kind', ['COMFYUI', 'AUTOMATIC1111'])
def test_recipe_uses_exact_original_runtime_model_and_candidate_binding(tmp_path, monkeypatch, kind):
    original, registry, adapter = discovery(tmp_path, kind)
    production = owner(registry, monkeypatch)
    value = MediaCommand.model_validate(command(adapter))
    recipe = production._recipe(value)
    assert recipe['adapter'] == ('COMFYUI_BUILTIN_IMAGE' if kind == 'COMFYUI' else 'AUTOMATIC1111_IMAGE')
    assert len(production._binding(value)['registration_digest']) == 64
    assert 'registration_digest' not in recipe
    assert recipe['automatic_fallback'] is False
    if kind == 'COMFYUI':
        assert recipe['workflow']['4']['inputs']['ckpt_name'] == 'SDXL.safetensors'
        assert recipe['workflow']['5']['inputs']['batch_size'] == 1
    assert value.model_id == adapter.candidate['id']
    assert recipe['recipe_digest'] == digest({key: val for key, val in recipe.items() if key != 'recipe_digest'})


@pytest.mark.parametrize('field,value', [('enabled_at', 'new-enable'), ('model_name', 'OTHER.safetensors'),
    ('runtime_fingerprint', 'changed'), ('model_evidence_fingerprint', 'changed'), ('license_confirmed', False)])
def test_existing_wrapper_cannot_adopt_registration_drift(tmp_path, monkeypatch, field, value):
    original, registry, adapter = discovery(tmp_path)
    production = owner(registry, monkeypatch)
    original.registrations[adapter.candidate['id']][field] = value
    assert production.providers('project', {}, 'actor', lambda: None)['items'] == []
    with pytest.raises(ValueError, match='STUDIO_DISCOVERED_IMAGE_REGISTRATION_CHANGED'):
        production._binding(MediaCommand.model_validate(command(adapter)))


def test_reenable_requires_new_preview_and_never_reuses_original_route(tmp_path, monkeypatch):
    original, registry, adapter = discovery(tmp_path)
    production = owner(registry, monkeypatch)
    before = production._binding(MediaCommand.model_validate(command(adapter)))
    original.disable(adapter.candidate['id']); original.enable(adapter.candidate['id'])
    after = production._binding(MediaCommand.model_validate(command(adapter)))
    assert before['route_digest'] != after['route_digest']
    assert registry.get(adapter.candidate['provider_id']) is not adapter
    with pytest.raises(ValueError, match='STUDIO_DISCOVERED_IMAGE_REGISTRATION_CHANGED'):
        adapter.studio_configuration()


def test_saved_same_candidate_reference_does_not_duplicate_discovery_route(tmp_path, monkeypatch):
    from app import asset_provider_config
    original, registry, adapter = discovery(tmp_path)
    production = owner(registry, monkeypatch)
    monkeypatch.setattr(asset_provider_config, 'load', lambda: {adapter.candidate['provider_id']:
        {'default_model': adapter.candidate['id'], 'endpoint': adapter.endpoint,
         'api_style': 'comfyui', 'local': True, 'enabled': True}})
    original.client.calls.clear()
    result = production.providers('project', {}, 'actor', lambda: None)
    assert len(result['items']) == 1
    assert result['items'][0]['operation_id'] == 'm5.image.t2i'
    assert result['items'][0]['model_id'] == adapter.candidate['id']
    assert original.client.calls == [] and result['health_probed'] is False


@pytest.mark.parametrize('kind', ['COMFYUI', 'AUTOMATIC1111'])
def test_last_mile_rechecks_registration_after_caller_guard(tmp_path, monkeypatch, kind):
    original, registry, adapter = discovery(tmp_path, kind)
    posts = []
    monkeypatch.setattr(adapter.delegate.transport, 'post', lambda *args, **kwargs: posts.append(args))
    def revoke(): original.disable(adapter.candidate['id'])
    with pytest.raises((ValueError, RuntimeError)):
        adapter.generate(AssetGenerationRequest(adapter.candidate['provider_id'], adapter.candidate['id'],
            'SYNTHETIC', 'job', dispatch_guard=revoke))
    assert posts == []


def test_comfy_revoke_after_send_prevents_poll_and_download(tmp_path, monkeypatch):
    original, registry, adapter = discovery(tmp_path)
    production = owner(registry, monkeypatch)
    value = MediaCommand.model_validate(command(adapter))
    captured = production._binding(value)
    hits = []
    def post(url, **kwargs):
        hits.append(url); original.disable(adapter.candidate['id'])
        return httpx.Response(200, json={'prompt_id': 'synthetic-prompt'}, request=httpx.Request('POST', url))
    monkeypatch.setattr(adapter.delegate.transport, 'post', post)
    monkeypatch.setattr(adapter.delegate.transport, 'get', lambda *a, **k: hits.append('FORBIDDEN_POLL'))
    def current():
        if production._binding(value) != captured:
            raise ValueError('STUDIO_PROVIDER_ROUTE_CHANGED')
    with pytest.raises((ValueError, RuntimeError)):
        adapter.generate(AssetGenerationRequest(adapter.candidate['provider_id'], adapter.candidate['id'],
            'SYNTHETIC', 'job', {'seed': 3}, dispatch_guard=current))
    assert hits == [adapter.endpoint + '/prompt']


def test_registration_change_after_ready_history_prevents_image_download(tmp_path, monkeypatch):
    original, registry, adapter = discovery(tmp_path)
    production = owner(registry, monkeypatch)
    value = MediaCommand.model_validate(command(adapter))
    captured = production._binding(value)
    hits = []
    def current():
        if production._binding(value) != captured:
            raise ValueError('STUDIO_PROVIDER_ROUTE_CHANGED')
    def history(url, **kwargs):
        hits.append('history')
        original.registrations[adapter.candidate['id']]['model_evidence_fingerprint'] = 'changed-after-ready-history'
        return httpx.Response(200, json={'ready': {'outputs': {'9': {'images': [{'filename': 'synthetic.png'}]}}}},
            request=httpx.Request('GET', url))
    def forbidden_fetch(*args, **kwargs):
        hits.append('FORBIDDEN_DOWNLOAD')
        raise AssertionError('stale registration must be rejected before downloading result bytes')
    monkeypatch.setattr(adapter.delegate.transport, 'get', history)
    monkeypatch.setattr('app.media_files.fetch_media_bytes', forbidden_fetch)
    request = AssetGenerationRequest(adapter.candidate['provider_id'], adapter.candidate['id'],
        'SYNTHETIC', 'job', dispatch_guard=current)
    with pytest.raises(ValueError, match='STUDIO_DISCOVERED_IMAGE_REGISTRATION_CHANGED'):
        adapter.delegate._result(request, 'ready')
    assert hits == ['history']


@pytest.mark.parametrize('revocation', ['registration', 'caller-authority'])
def test_revocation_during_download_prevents_result_adoption(tmp_path, monkeypatch, revocation):
    original, registry, adapter = discovery(tmp_path)
    production = owner(registry, monkeypatch)
    value = MediaCommand.model_validate(command(adapter))
    captured = production._binding(value)
    hits = []
    caller_active = True
    denied = PermissionError('SYNTHETIC_HOST_AUTHORITY_REVOKED')
    def current():
        if not caller_active:
            raise denied
        if production._binding(value) != captured:
            raise ValueError('STUDIO_PROVIDER_ROUTE_CHANGED')
    def history(url, **kwargs):
        hits.append('history')
        return httpx.Response(200, json={'ready': {'outputs': {'9': {'images': [{'filename': 'synthetic.png'}]}}}},
            request=httpx.Request('GET', url))
    def download(*args, **kwargs):
        nonlocal caller_active
        hits.append('download')
        if revocation == 'registration':
            original.registrations[adapter.candidate['id']]['model_name'] = 'changed-during-download.safetensors'
        else:
            caller_active = False
        return png_bytes()
    def forbidden_decode(*args, **kwargs):
        hits.append('FORBIDDEN_RESULT_DECODE')
        raise AssertionError('revoked downloaded bytes cannot become a generation result')
    monkeypatch.setattr(adapter.delegate.transport, 'get', history)
    monkeypatch.setattr('app.media_files.fetch_media_bytes', download)
    monkeypatch.setattr('app.media_files.inspect_image', forbidden_decode)
    request = AssetGenerationRequest(adapter.candidate['provider_id'], adapter.candidate['id'],
        'SYNTHETIC', 'job', dispatch_guard=current)
    with pytest.raises(PermissionError if revocation == 'caller-authority' else ValueError) as raised:
        adapter.delegate._result(request, 'ready')
    if revocation == 'caller-authority':
        assert raised.value is denied
    else:
        assert str(raised.value) == 'STUDIO_DISCOVERED_IMAGE_REGISTRATION_CHANGED'
    assert hits == ['history', 'download']


def test_configured_provider_default_binding_and_recipe_identity_are_unchanged(tmp_path, monkeypatch):
    from app import asset_provider_config
    from app.asset_providers import Automatic1111ImageProvider
    registry = AssetProviderRegistry()
    adapter = Automatic1111ImageProvider(SimpleNamespace(), 'http://127.0.0.1:7860')
    adapter.default_model = 'configured-checkpoint'
    registry.register('configured', adapter)
    production = owner(registry, monkeypatch)
    config = {'enabled': True, 'local': True, 'requires_credential': False, 'default_model': adapter.default_model,
        'api_style': 'automatic1111', 'endpoint': adapter.endpoint}
    monkeypatch.setattr(asset_provider_config, 'load', lambda: {'configured': config})
    value = MediaCommand.model_validate({'operation_id': 'm5.image.t2i', 'request_id': 'legacy',
        'provider_id': 'configured', 'model_id': adapter.default_model, 'prompt': 'SYNTHETIC'})
    binding = {'provider_id': 'configured', 'model_id': adapter.default_model, 'endpoint': adapter.endpoint,
        'local': True, 'capability': 'TEXT_TO_IMAGE'}
    binding['route_digest'] = digest({**binding, 'config': {key: config.get(key) for key in
        ('enabled', 'local', 'requires_credential', 'default_model', 'model_id', 'api_style', 'capabilities', 'video_to_video')}})
    assert production._binding(value) == binding
    recipe = {'contract': 'studio-execution-recipe/1', 'operation_id': 'm5.image.t2i',
        'adapter': 'AUTOMATIC1111_IMAGE', 'parameters': {}, 'automatic_fallback': False,
        'defaults': {'width': 1024, 'height': 1024, 'steps': 28}}
    recipe['recipe_digest'] = digest(recipe)
    assert production._recipe(value) == recipe


@pytest.mark.parametrize('kind', ['COMFYUI', 'AUTOMATIC1111'])
def test_original_queue_bytes_review_and_reopen(rig, monkeypatch, kind):
    original, registry, adapter = discovery(rig.root, kind)
    production = owner(registry, monkeypatch, rig)
    data = png_bytes(); calls = []
    def post(url, **kwargs):
        calls.append((url, deepcopy(kwargs)))
        payload = {'prompt_id': 'synthetic-prompt'} if kind == 'COMFYUI' else {'images': [base64.b64encode(data).decode()]}
        return httpx.Response(200, json=payload, request=httpx.Request('POST', url))
    def get(url, **kwargs):
        calls.append((url, deepcopy(kwargs)))
        return httpx.Response(200, json={'synthetic-prompt': {'outputs': {'9': {'images': [{'filename': 'synthetic.png'}]}}}},
            request=httpx.Request('GET', url))
    monkeypatch.setattr(adapter.delegate.transport, 'post', post)
    monkeypatch.setattr(adapter.delegate.transport, 'get', get)
    monkeypatch.setattr('app.media_files.fetch_media_bytes', lambda *args, **kwargs: data)
    body = command(adapter)
    preview = production.preview(rig.nid, rig.scope, rig.actor, body, lambda: None)[0]
    assert calls == []
    row = production.create(rig.nid, rig.scope, rig.actor,
        {'command': body, 'reviewed_preview_digest': preview['preview_digest']}, lambda: None)
    assert row['status'] == 'QUEUED' and calls == []
    completed = production.execute(rig.nid, rig.scope, rig.actor, 'image', row['id'],
        MediaJobAction(expected_version=row['version'], expected_request_digest=row['request_digest']), lambda: None)
    assert completed['status'] == 'AWAITING_REVIEW' and completed['attempt'] == 1
    assert completed['product_acceptance'] == 'LOCAL_REQUIRED' and completed['automatic_replay'] is False
    assert calls[0][0].endswith('/prompt' if kind == 'COMFYUI' else '/sdapi/v1/txt2img')
    sent = calls[0][1]['json']
    assert (sent['prompt']['4']['inputs']['ckpt_name'] if kind == 'COMFYUI' else
        sent['override_settings']['sd_model_checkpoint']) == 'SDXL.safetensors'
    candidate = completed['output_candidate']
    assert candidate['digest'] == hashlib.sha256(data).hexdigest()
    assert rig.service.list_assets(rig.nid, rig.scope)['items'] == []
    with pytest.raises(FileNotFoundError): rig.service.asset(rig.nid, rig.scope, candidate['id'])
    meta, actual = production.candidate(rig.nid, rig.scope, rig.actor, 'image', row['id'], lambda: None)
    assert actual == data and meta['sha256'] == candidate['digest']
    approved = production.review(rig.nid, rig.scope, rig.actor, 'image', row['id'],
        MediaReview(expected_version=completed['version'], expected_request_digest=completed['request_digest'],
            reviewed_output_digest=candidate['digest']), lambda: None)
    assert approved['status'] == 'APPROVED' and approved['approved_asset_version'] == 2
    assert rig.service.asset(rig.nid, rig.scope, candidate['id'])['sha256'] == candidate['digest']
    restarted = ProductionExecutionService(reopened(rig), ImageJobService(rig.root), registry,
        SimpleNamespace(), {}, {}, SimpleNamespace(), SimpleNamespace(), SimpleNamespace())
    assert restarted.get(rig.nid, rig.scope, rig.actor, 'image', row['id'], lambda: None) == approved
    assert len([call for call in calls if call[0].endswith('/prompt') or call[0].endswith('/txt2img')]) == 1
