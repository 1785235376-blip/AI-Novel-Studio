"""Synthetic wire/metadata contracts; no model download, launch or inference."""
from __future__ import annotations

import base64
import copy

import pytest

from app.asset_providers import AssetGenerationRequest, Automatic1111ImageProvider, ComfyUIImageProvider
from app.services.studio_image_provider_recipes import (build_workflow, project_comfy_image_recipe,
    project_automatic1111_image_recipe, validate_workflow)


def object_info():
    def node(inputs, outputs): return {'input': {'required': inputs}, 'output': outputs}
    integer = lambda low=0, high=2147483647: ['INT', {'min': low, 'max': high}]
    number = lambda low=0, high=100: ['FLOAT', {'min': low, 'max': high}]
    return {
        'CheckpointLoaderSimple': node({'ckpt_name': [['sdxl-fixture.safetensors']]}, ['MODEL','CLIP','VAE']),
        'UNETLoader': node({'unet_name': [['flux1-dev.safetensors','flux1-schnell.safetensors','qwen_image_fp8_e4m3fn.safetensors']], 'weight_dtype': [['default','fp8_e4m3fn']]}, ['MODEL']),
        'DualCLIPLoader': node({'clip_name1': [['clip_l.safetensors']], 'clip_name2': [['t5xxl_fp16.safetensors']], 'type': [['flux','sdxl']]}, ['CLIP']),
        'CLIPLoader': node({'clip_name': [['qwen_2.5_vl_7b_fp8_scaled.safetensors']], 'type': [['qwen_image','stable_diffusion']]}, ['CLIP']),
        'VAELoader': node({'vae_name': [['ae.safetensors','qwen_image_vae.safetensors']]}, ['VAE']),
        'CLIPTextEncode': node({'text': ['STRING'], 'clip': ['CLIP']}, ['CONDITIONING']),
        'FluxGuidance': node({'conditioning': ['CONDITIONING'], 'guidance': number()}, ['CONDITIONING']),
        'ModelSamplingAuraFlow': node({'model': ['MODEL'], 'shift': number()}, ['MODEL']),
        'EmptyLatentImage': node({'width': integer(64,2048), 'height': integer(64,2048), 'batch_size': integer(1,1)}, ['LATENT']),
        'EmptySD3LatentImage': node({'width': integer(64,2048), 'height': integer(64,2048), 'batch_size': integer(1,1)}, ['LATENT']),
        'KSampler': node({'seed': integer(), 'steps': integer(1,150), 'cfg': number(), 'sampler_name': [['euler']], 'scheduler': [['normal']],
            'denoise': number(0,1), 'model': ['MODEL'], 'positive': ['CONDITIONING'], 'negative': ['CONDITIONING'], 'latent_image': ['LATENT']}, ['LATENT']),
        'VAEDecode': node({'samples': ['LATENT'], 'vae': ['VAE']}, ['IMAGE']),
        'SaveImage': node({'filename_prefix': ['STRING'], 'images': ['IMAGE']}, []),
        'LoadImage': node({'image': [['existing.png']]}, ['IMAGE','MASK']),
        'VAEEncode': node({'pixels': ['IMAGE'], 'vae': ['VAE']}, ['LATENT']),
        'ImageBlend': node({'image1': ['IMAGE'], 'image2': ['IMAGE'], 'blend_factor': number(0,1), 'blend_mode': [['normal','multiply']]}, ['IMAGE']),
        'ImageToMask': node({'image': ['IMAGE'], 'channel': [['red','green','blue','alpha']]}, ['MASK']),
        'InvertMask': node({'mask': ['MASK']}, ['MASK']),
        'VAEEncodeForInpaint': node({'pixels': ['IMAGE'], 'vae': ['VAE'], 'mask': ['MASK'], 'grow_mask_by': integer(0,64)}, ['LATENT']),
        'ImageCompositeMasked': node({'destination': ['IMAGE'], 'source': ['IMAGE'], 'x': integer(), 'y': integer(),
            'resize_source': ['BOOLEAN'], 'mask': ['MASK']}, ['IMAGE']),
    }


def image_api():
    properties = {key: {'type': kind} for key,kind in {
        'init_images':'array','mask':'string','denoising_strength':'number','inpainting_mask_invert':'integer',
        'inpaint_full_res':'boolean','inpaint_full_res_padding':'integer','inpainting_fill':'integer','mask_blur':'integer','resize_mode':'integer',
        'width':'integer','height':'integer','steps':'integer','seed':'integer','prompt':'string','negative_prompt':'string','override_settings':'object'}.items()}
    properties['init_images']['items'] = {'type':'string'}
    return {'paths': {'/sdapi/v1/img2img': {'post': {'requestBody': {'content': {'application/json': {'schema': {'$ref':'#/components/schemas/ImageInput'}}}}}}},
        'components': {'schemas': {'ImageInput': {'type':'object','properties':properties}}}}


def png():
    from app.services.studio_image_mask_authoring import encode_mask
    data,_ = encode_mask(64,64,base64.b64encode(b'\xff'*256+b'\x00'*256).decode())
    return data


def inline(): return 'data:image/png;base64,'+base64.b64encode(png()).decode()


@pytest.mark.parametrize('model,family,rid', [('sdxl-fixture.safetensors','STABLE_DIFFUSION','comfy-sd-checkpoint-v1'),
    ('flux1-dev.safetensors','FLUX','comfy-flux1-v1'),('flux1-schnell.safetensors','FLUX','comfy-flux1-v1'),
    ('qwen_image_fp8_e4m3fn.safetensors','QWEN_IMAGE','comfy-qwen-image-v1')])
def test_fixed_recipe_components_and_structural_only_evidence(model,family,rid):
    recipe=project_comfy_image_recipe(object_info(),model,family)
    assert recipe['recipe_id']==rid and recipe['components']['model']==model
    assert recipe['operations']==['t2i','i2i','reference','inpaint']
    assert recipe['structural_only'] is True and recipe['inference_verified'] is False
    assert recipe['reference_semantics']=='WEIGHTED_PIXEL_INITIALIZATION'
    graph=build_workflow(recipe,'中文场景',{'seed':17,'steps':12})
    validate_workflow(object_info(),graph)
    assert graph['3']['inputs']['seed']==17 and graph['3']['inputs']['steps']==12
    if family=='FLUX':
        assert graph['11']['inputs']['type']=='flux' and graph['12']['inputs']['vae_name']=='ae.safetensors'
        assert graph['14']['inputs']['guidance']==3.5 and graph['3']['inputs']['cfg']==1
    if family=='QWEN_IMAGE':
        assert graph['11']['inputs']['type']=='qwen_image' and graph['13']['inputs']['shift']==3.1


@pytest.mark.parametrize('mutation', ['missing_vae','wrong_type','bad_enum','extra_required','wrong_output','ambiguous_component'])
def test_family_name_cannot_authorize_missing_or_wrong_loader_components(mutation):
    info=object_info()
    if mutation=='missing_vae':del info['VAELoader']
    if mutation=='wrong_type':info['DualCLIPLoader']['input']['required']['type']=[['sdxl']]
    if mutation=='bad_enum':info['KSampler']['input']['required']['sampler_name']=[['dpmpp_2m']]
    if mutation=='extra_required':info['UNETLoader']['input']['required']['arbitrary_command']=['STRING']
    if mutation=='wrong_output':info['DualCLIPLoader']['output']=['IMAGE']
    if mutation=='ambiguous_component':info['DualCLIPLoader']['input']['required']['clip_name2'][0].append('t5xxl_fp8_e4m3fn.safetensors')
    assert project_comfy_image_recipe(info,'flux1-dev.safetensors','FLUX') is None


def test_weights_affect_normalized_pixel_initialization_and_mask_keeps_original():
    recipe=project_comfy_image_recipe(object_info(),'sdxl-fixture.safetensors','STABLE_DIFFUSION')
    graph=build_workflow(recipe,'detail',{'denoising_strength':0.4},operation='reference',uploads=['a.png','b.png','c.png'],weights=[1,.25,.75])
    assert graph['31']['inputs']['blend_factor']==.2
    assert graph['32']['inputs']['blend_factor']==.375
    assert graph['5']['inputs']['pixels']==['32',0] and graph['3']['inputs']['denoise']==.4
    paint=build_workflow(recipe,'detail',{},operation='inpaint',uploads=['base.png'],weights=[1],mask='keep.png')
    assert paint['27']=={'class_type':'InvertMask','inputs':{'mask':['26',0]}}
    assert paint['5']['inputs']['grow_mask_by']==0 and paint['5']['inputs']['mask']==['27',0]
    assert paint['28']['inputs']['destination']==['20',0] and paint['28']['inputs']['mask']==['27',0]
    assert paint['9']['inputs']['images']==['28',0]


@pytest.mark.parametrize('bad', [0,-1,2,True,float('nan'),float('inf')])
def test_bad_weight_rejected(bad):
    recipe=project_comfy_image_recipe(object_info(),'sdxl-fixture.safetensors','STABLE_DIFFUSION')
    with pytest.raises(ValueError,match='REFERENCES_INVALID'):
        build_workflow(recipe,'detail',{},operation='reference',uploads=['a.png'],weights=[bad])


def test_optional_nodes_do_not_advertise_unsupported_operation():
    info=object_info();del info['ImageBlend'];del info['InvertMask']
    recipe=project_comfy_image_recipe(info,'sdxl-fixture.safetensors','STABLE_DIFFUSION')
    assert recipe['operations']==['t2i','i2i'] and recipe['reference_limit']==1 and recipe['mask_semantics'] is None


@pytest.mark.parametrize('operation',['i2i','reference','inpaint'])
def test_non_t2i_dimensions_are_rejected_instead_of_ignored(operation):
    recipe=project_comfy_image_recipe(object_info(),'sdxl-fixture.safetensors','STABLE_DIFFUSION')
    with pytest.raises(ValueError,match='IMAGE_PARAMETER_UNSUPPORTED'):
        build_workflow(recipe,'p',{'width':128,'height':128},operation=operation,uploads=['base.png'],weights=[1],
            mask='mask.png' if operation=='inpaint' else None)


def test_fixed_flux_cfg_one_rejects_negative_prompt_instead_of_ignoring_it():
    recipe=project_comfy_image_recipe(object_info(),'flux1-dev.safetensors','FLUX')
    with pytest.raises(ValueError,match='IMAGE_PARAMETER_UNSUPPORTED'):
        build_workflow(recipe,'p',{'negative_prompt':'ignored negative is forbidden'})


class Response:
    status_code=200
    def __init__(self,body=None,content=b''):self.body=body;self.content=content
    def json(self):return copy.deepcopy(self.body)
    def raise_for_status(self):pass


class Transport:
    def __init__(self):self.calls=[];self.info=object_info();self.revoked=False;self.after_upload=None
    def get(self,url,**kwargs):
        self.calls.append((url,kwargs))
        if url.endswith('/object_info'):return Response(self.info)
        if '/history/' in url:return Response({'prompt-1':{'outputs':{'9':{'images':[{'filename':'result.png','type':'output'}]}}}})
        if url.endswith('/view'):return Response(content=png())
        raise AssertionError(url)
    def post(self,url,**kwargs):
        self.calls.append((url,kwargs))
        if url.endswith('/upload/image'):
            if self.after_upload:self.after_upload()
            return Response({'name':kwargs['files']['image'][0],'type':'input'})
        if url.endswith('/prompt'):return Response({'prompt_id':'prompt-1'})
        if url.endswith('/sdapi/v1/img2img'):return Response({'images':[base64.b64encode(png()).decode()]})
        raise AssertionError(url)


def provider(transport):
    adapter=ComfyUIImageProvider(transport,'http://127.0.0.1:8188')
    adapter.image_recipe_descriptor=project_comfy_image_recipe(transport.info,'sdxl-fixture.safetensors','STABLE_DIFFUSION')
    return adapter


def test_weighted_reference_uploads_exact_fixed_graph_and_validated_output():
    transport=Transport();adapter=provider(transport);checks=[]
    request=AssetGenerationRequest('comfyui','sdxl-fixture.safetensors','雨夜','synthetic',{'seed':17},dispatch_guard=lambda:checks.append('checked'))
    result=adapter.generate_image(request,operation='reference',images=[inline(),inline()],reference_weights=[1,.25])
    submitted=next(kwargs['json']['prompt'] for url,kwargs in transport.calls if url.endswith('/prompt'))
    assert submitted['31']['inputs']['blend_factor']==.2
    assert len([url for url,_ in transport.calls if url.endswith('/upload/image')])==2
    assert result.asset_uri==inline() and len(checks)>=12


def test_revocation_after_first_upload_preserves_exception_and_never_submits():
    transport=Transport();adapter=provider(transport)
    class Revoked(RuntimeError):pass
    error=Revoked('synthetic authority revoked')
    def guard():
        if transport.revoked:raise error
    transport.after_upload=lambda:setattr(transport,'revoked',True)
    with pytest.raises(Revoked) as caught:
        adapter.generate_image(AssetGenerationRequest('comfyui','sdxl-fixture.safetensors','p','task',dispatch_guard=guard),
            operation='reference',images=[inline(),inline()],reference_weights=[1,.5])
    assert caught.value is error
    assert len([url for url,_ in transport.calls if url.endswith('/upload/image')])==1
    assert not any(url.endswith('/prompt') for url,_ in transport.calls)


def test_recipe_drift_after_upload_prevents_prompt_dispatch():
    transport=Transport();adapter=provider(transport)
    transport.after_upload=lambda:transport.info.pop('ImageBlend',None)
    with pytest.raises(ValueError,match='CONFIGURATION_CHANGED'):
        adapter.generate_image(AssetGenerationRequest('comfyui','sdxl-fixture.safetensors','p','task'),
            operation='reference',images=[inline(),inline()],reference_weights=[1,.5])
    assert not any(url.endswith('/prompt') for url,_ in transport.calls)


def test_bad_weight_never_uploads_or_submits():
    transport=Transport();adapter=provider(transport)
    with pytest.raises(ValueError,match='REFERENCES_INVALID'):
        adapter.generate_image(AssetGenerationRequest('comfyui','sdxl-fixture.safetensors','p','task'),operation='reference',images=[inline()],reference_weights=[0])
    assert not transport.calls


def test_a1111_inpaint_requires_explicit_api_schema_and_sends_inverted_keep_mask():
    recipe=project_automatic1111_image_recipe(image_api(),'fixture-model')
    assert recipe['operations']==['t2i','i2i','inpaint'] and recipe['reference_limit']==1
    transport=Transport();adapter=Automatic1111ImageProvider(transport,'http://127.0.0.1:7860');adapter.image_recipe_descriptor=recipe
    adapter.generate_image(AssetGenerationRequest('automatic1111','fixture-model','detail','task',{'denoising_strength':.4}),
        operation='inpaint',images=[inline()],reference_weights=[1],mask=inline())
    body=transport.calls[0][1]['json']
    assert body['inpainting_mask_invert']==1 and body['mask_blur']==0 and body['denoising_strength']==.4 and body['mask']==inline()
    broken=image_api();broken['components']['schemas']['ImageInput']['properties']['mask']['type']='integer'
    assert project_automatic1111_image_recipe(broken,'fixture-model') is None


def test_unconfigured_legacy_adapter_never_advertises_new_operations():
    adapter=ComfyUIImageProvider(Transport(),'http://127.0.0.1:8188')
    assert adapter.image_configuration() is None
    with pytest.raises(ValueError,match='NOT_CONFIGURED'):
        adapter.generate_image(AssetGenerationRequest('comfyui','model','prompt','task'),operation='inpaint',images=[inline()],reference_weights=[1],mask=inline())


def test_guarded_download_stream_propagates_cancel_and_closes_wire(monkeypatch):
    from app.model_center.discovery_bridge import _LocalImageTransport
    from test_rebuild_image_transport import mock_wire
    wire,calls,clients=mock_wire(monkeypatch,[b'first',b'second'])
    class Revoked(RuntimeError):pass
    error=Revoked('synthetic cancelled download')
    def guard():
        if wire.count:raise error
    with pytest.raises(Revoked) as caught:
        _LocalImageTransport('http://127.0.0.1:8188').get('http://127.0.0.1:8188/view',dispatch_guard=guard)
    assert caught.value is error and wire.closed and wire.count==5


def test_rich_t2i_uses_flux_loader_not_legacy_checkpoint():
    transport=Transport();adapter=ComfyUIImageProvider(transport,'http://127.0.0.1:8188')
    adapter.image_recipe_descriptor=project_comfy_image_recipe(transport.info,'flux1-dev.safetensors','FLUX')
    adapter.generate(AssetGenerationRequest('comfyui','flux1-dev.safetensors','p','task'))
    graph=next(kwargs['json']['prompt'] for url,kwargs in transport.calls if url.endswith('/prompt'))
    assert graph['4']['class_type']=='UNETLoader' and graph['4']['inputs']['unet_name']=='flux1-dev.safetensors'
    assert not any(url.endswith('/upload/image') for url,_ in transport.calls)
