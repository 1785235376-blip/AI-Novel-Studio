"""Original explicit discovery owner: metadata is never inference acceptance."""
from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest

from app.asset_providers import AssetGenerationRequest,AssetProviderRegistry
from app.model_center.discovery_bridge import LocalDiscoveryBridge
from app.model_center.discovery_types import RegistrationInput
from app.model_runtime import ProviderRegistry,ModelRegistry
from test_local_ai_discovery import service,scan,approve_license
from test_v2_discovered_image_production import discovery as legacy_discovery
from test_v2_image_provider_recipes import object_info,image_api,Transport,inline


def enabled(tmp_path,model='flux1-dev.safetensors',kind='COMFYUI',info=None):
    original=service(tmp_path)
    endpoint='http://127.0.0.1:8188' if kind=='COMFYUI' else 'http://127.0.0.1:7860'
    if kind=='COMFYUI':
        original.client.payloads[(endpoint,'/system_stats')]={'system':{}}
        original.client.payloads[(endpoint,'/object_info')]=info or object_info()
    else:
        original.client.payloads[(endpoint,'/sdapi/v1/sd-models')]=[{'title':model}]
        original.client.payloads[(endpoint,'/openapi.json')]=info or image_api()
    registry=AssetProviderRegistry()
    original.route_bridge=LocalDiscoveryBridge(original,SimpleNamespace(provider_registry=ProviderRegistry(),model_registry=ModelRegistry()),registry)
    candidate=next(c for c in scan(original)['candidates'] if c['model_name']==model)
    validated=original.validate(candidate['id'])
    original.register(candidate['id']);approve_license(original,candidate['id']);original.enable(candidate['id'])
    return original,registry,registry.get(candidate['provider_id']),validated


@pytest.mark.parametrize('model,rid', [('flux1-dev.safetensors','comfy-flux1-v1'),('qwen_image_fp8_e4m3fn.safetensors','comfy-qwen-image-v1')])
def test_actual_loader_schema_can_enable_fixed_recipe_but_never_claim_inference(tmp_path,model,rid):
    original,registry,adapter,validated=enabled(tmp_path,model)
    assert validated['verified_capabilities']==['IMAGE']
    config=adapter.studio_configuration()
    assert config['image_recipe']['recipe_id']==rid
    assert config['image_operations']==['t2i','i2i','reference','inpaint']
    assert config['image_capabilities']['inference_verified'] is False
    before=list(original.client.calls)
    expected=('steps','seed','denoising_strength') if model.startswith('flux') else ('steps','seed','negative_prompt','denoising_strength')
    assert adapter.image_configuration()['supported_parameters']['inpaint']==expected
    assert original.client.calls==before
    projection=adapter.image_recipe(AssetGenerationRequest(config['default_model'],config['default_model'],'prompt','task'),
        operation='reference',reference_weights=[1,.5])
    assert projection['4']['inputs']['unet_name']==model and projection['31']['inputs']['blend_factor']==pytest.approx(1/3)
    assert adapter.studio_configuration()['registration_digest']==config['registration_digest']


def test_only_model_name_and_node_names_do_not_enable_flux(tmp_path):
    original=service(tmp_path);info=object_info();del info['VAELoader']
    original.client.payloads[('http://127.0.0.1:8188','/system_stats')]={'system':{}}
    original.client.payloads[('http://127.0.0.1:8188','/object_info')]=info
    candidate=next(c for c in scan(original)['candidates'] if c['model_name']=='flux1-dev.safetensors')
    validated=original.validate(candidate['id'])
    assert validated['verified_capabilities']==[] and 'WORKFLOW_ADAPTER_REQUIRED' in validated['enable_blockers']


@pytest.mark.parametrize('kind',['COMFYUI','AUTOMATIC1111'])
def test_original_minimal_registration_stays_t2i_only_public_shape(tmp_path,kind):
    original,registry,adapter=legacy_discovery(tmp_path,kind)
    assert 'image_recipe' not in adapter.studio_configuration()
    assert adapter.image_configuration() is None
    with pytest.raises(ValueError,match='NOT_CONFIGURED'):
        adapter.generate_image(AssetGenerationRequest(adapter.candidate['provider_id'],adapter.candidate['id'],'p','task'),
            operation='inpaint',images=[inline()],reference_weights=[1],mask=inline())


def test_runtime_model_mapping_and_original_enable_guard_cover_every_upload(tmp_path):
    original,registry,adapter,_=enabled(tmp_path,'sdxl-fixture.safetensors')
    transport=Transport();adapter.delegate.transport=transport
    identifier=adapter.candidate['id']
    transport.after_upload=lambda:original.disable(identifier)
    with pytest.raises(ValueError,match='STUDIO_DISCOVERED_IMAGE_REGISTRATION_CHANGED'):
        adapter.generate_image(AssetGenerationRequest(adapter.candidate['provider_id'],identifier,'p','task'),
            operation='reference',images=[inline(),inline()],reference_weights=[1,.5])
    assert len([url for url,_ in transport.calls if url.endswith('/upload/image')])==1
    assert not any(url.endswith('/prompt') for url,_ in transport.calls)


def test_reenable_never_reuses_prior_recipe_identity(tmp_path):
    original,registry,adapter,_=enabled(tmp_path,'sdxl-fixture.safetensors')
    identifier=adapter.candidate['id'];original.disable(identifier);original.enable(identifier)
    with pytest.raises(ValueError,match='STUDIO_DISCOVERED_IMAGE_REGISTRATION_CHANGED'):adapter.studio_configuration()
    assert registry.get(adapter.candidate['provider_id']) is not adapter


def test_a1111_openapi_evidence_is_required_and_frozen_in_registration(tmp_path):
    original,registry,adapter,_=enabled(tmp_path,'SDXL.safetensors','AUTOMATIC1111')
    config=adapter.studio_configuration()
    assert config['image_operations']==['t2i','i2i','inpaint']
    assert config['image_capabilities']['reference_semantics']=='SINGLE_IMAGE_INITIALIZATION'
    broken=copy.deepcopy(image_api());broken['components']['schemas']['ImageInput']['properties'].pop('mask')
    original.client.payloads[('http://127.0.0.1:7860','/openapi.json')]=broken
    with pytest.raises(ValueError,match='LOCAL_AI_LOCAL_MODEL_EVIDENCE_CHANGED'):
        adapter.generate_image(AssetGenerationRequest(adapter.candidate['provider_id'],adapter.candidate['id'],'p','task'),
            operation='inpaint',images=[inline()],reference_weights=[1],mask=inline())
    assert not original.registrations[adapter.candidate['id']]['enabled']


def test_new_recipe_definition_changes_stale_original_consent(tmp_path,monkeypatch):
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','narrative_production_v2')
    original=service(tmp_path)
    receipt=original.preview_scan_scope(False,'synthetic-principal',lambda:True)
    original.image_workflow_adapters[0]['required_nodes'].append('SyntheticArbitraryNode')
    with pytest.raises(ValueError,match='LOCAL_AI_SCOPE_STALE'):
        original.start_consented_scan(receipt['scope_digest'],'synthetic-principal',lambda:True)
    assert original.client.calls==[]


def test_a1111_openapi_is_declared_in_original_consent_but_empty_models_need_no_read(tmp_path,monkeypatch):
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','narrative_production_v2')
    original=service(tmp_path)
    receipt=original.preview_scan_scope(False,'synthetic-principal',lambda:True)
    runtime=next(row for row in receipt['services'] if row['type']=='AUTOMATIC1111')
    assert runtime['probe_paths']==['/sdapi/v1/sd-models','/openapi.json']
    original.client.payloads[('http://127.0.0.1:7860','/sdapi/v1/sd-models')]=[]
    scan(original)
    assert not any(path=='/openapi.json' for _,path,_ in original.client.calls)


def test_empty_a1111_api_schema_keeps_original_t2i_only(tmp_path):
    original=service(tmp_path)
    original.client.payloads[('http://127.0.0.1:7860','/sdapi/v1/sd-models')]=[{'title':'SDXL.safetensors'}]
    original.client.payloads[('http://127.0.0.1:7860','/openapi.json')]={}
    candidate=next(c for c in scan(original)['candidates'] if c['runtime_type']=='AUTOMATIC1111')
    validated=original.validate(candidate['id'])
    assert validated['verified_capabilities']==['IMAGE']
    assert 'image_recipe' not in validated['evidence']


def test_a1111_scan_is_passive_and_only_explicit_validation_reads_new_api(tmp_path):
    original=service(tmp_path)
    endpoint='http://127.0.0.1:7860'
    original.client.payloads[(endpoint,'/sdapi/v1/sd-models')]=[{'title':'SDXL.safetensors'}]
    original.client.payloads[(endpoint,'/openapi.json')]=image_api()
    candidate=next(c for c in scan(original)['candidates'] if c['runtime_type']=='AUTOMATIC1111')
    assert 'image_recipe' not in candidate['evidence']
    assert not any(path=='/openapi.json' for _,path,_ in original.client.calls)
    validated=original.validate(candidate['id'])
    assert validated['evidence']['image_recipe']['operations']==['t2i','i2i','inpaint']
    assert len([path for _,path,_ in original.client.calls if path=='/openapi.json'])==1


def test_a1111_rich_enabled_scan_rechecks_pins_and_revokes_changed_api(tmp_path):
    original,registry,adapter,_=enabled(tmp_path,'SDXL.safetensors','AUTOMATIC1111')
    endpoint='http://127.0.0.1:7860';before=len(original.client.calls)
    original.client.payloads[(endpoint,'/openapi.json')]={}
    scan(original)
    assert any(path=='/openapi.json' for _,path,_ in original.client.calls[before:])
    assert not original.registrations[adapter.candidate['id']]['enabled']
    with pytest.raises(ValueError,match='STUDIO_DISCOVERED_IMAGE_REGISTRATION_CHANGED'):adapter.studio_configuration()
