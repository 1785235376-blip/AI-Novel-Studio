"""Additional cross-runtime controls; metadata doubles only, no native process."""
import sys
from pathlib import Path
from types import SimpleNamespace as S
import pytest
sys.path.insert(0,str(Path.cwd()/'tests'))
from test_local_ai_discovery import service,scan,approve_license,FixtureClient,gguf
from test_local_ai_discovery_egress import enabled
from app.asset_providers import AssetProviderRegistry
from app.model_center.discovery_bridge import LocalDiscoveryBridge
from app.model_center.discovery_types import LocalRuntimeInput
from app.model_runtime import ProviderRegistry,ModelRegistry,TextGenerationRequest,ModelRuntimeError


def enable_one(svc,candidate):
    runtime=S(provider_registry=ProviderRegistry(),model_registry=ModelRegistry())
    svc.route_bridge=LocalDiscoveryBridge(svc,runtime,AssetProviderRegistry())
    identifier=candidate['id'];svc.validate(identifier);svc.register(identifier);approve_license(svc,identifier);svc.enable(identifier)
    return runtime


def test_rescan_replaced_a1111_checkpoint_revokes_enable(tmp_path):
    svc=service(tmp_path);key=('http://127.0.0.1:7860','/sdapi/v1/sd-models')
    svc.client.payloads[key]=[{'title':'SDXL.safetensors','sha256':'a'*64}]
    candidate=scan(svc)['candidates'][0];enable_one(svc,candidate)
    svc.client.payloads[key]=[{'title':'SDXL.safetensors','sha256':'b'*64}]
    scan(svc)
    assert not svc.registrations[candidate['id']]['enabled'], 'A1111 rescan observed new checksum but retained old route approval'


def test_rescan_removed_comfy_loader_revokes_enable(tmp_path):
    svc=service(tmp_path);endpoint='http://127.0.0.1:8188'
    svc.client.payloads[(endpoint,'/system_stats')]={'system':{}}
    info={'CheckpointLoaderSimple':{'input':{'required':{'ckpt_name':[['sdxl.safetensors']]}}},**{name:{} for name in ('KSampler','EmptyLatentImage','CLIPTextEncode','VAEDecode','SaveImage')}}
    svc.client.payloads[(endpoint,'/object_info')]=info
    candidate=scan(svc)['candidates'][0];enable_one(svc,candidate)
    svc.client.payloads[(endpoint,'/object_info')]={}
    scan(svc)
    assert not svc.registrations[candidate['id']]['enabled'], 'Required Comfy loader disappeared on rescan, but old enabled workflow remained'


def test_rescan_replaced_gguf_revokes_enable(tmp_path):
    svc=service(tmp_path);path=tmp_path/'qwen.gguf';gguf(path)
    exe=tmp_path/'llama-server';exe.write_bytes(b'SYNTHETIC_NOT_EXECUTABLE')
    svc.configure_runtime(LocalRuntimeInput(name='Managed fixture',type='LLAMA_CPP',endpoint='http://127.0.0.1:9991',model_path=str(path),executable=str(exe),management='MANAGED'))
    candidate=next(c for c in scan(svc)['candidates'] if c['local_path']==str(path));enable_one(svc,candidate)
    path.write_bytes(b'REPLACED_INVALID_MODEL')
    scan(svc)
    assert not svc.registrations[candidate['id']]['enabled'], 'GGUF became invalid on rescan, but old enabled local route survived'


def test_buffered_ollama_incomplete_response_is_not_completed(tmp_path):
    svc,runtime,candidate,adapter,wire=enabled(tmp_path)
    adapter.client=FixtureClient();adapter.client.payloads[('http://127.0.0.1:11434','/api/generate')]={'response':'UNFINISHED_TEXT','done':False}
    with pytest.raises((ValueError,ModelRuntimeError)):
        adapter.generate_text(TextGenerationRequest(candidate['provider_id'],candidate['id'],'SYNTHETIC'))


def test_absent_provider_counters_are_unknown_not_reported_usage(tmp_path):
    svc,runtime,candidate,adapter,wire=enabled(tmp_path)
    adapter.client=FixtureClient();adapter.client.payloads[('http://127.0.0.1:11434','/api/generate')]={'response':'Synthetic completed','done':True}
    result=adapter.generate_text(TextGenerationRequest(candidate['provider_id'],candidate['id'],'SYNTHETIC'))
    assert result.usage is None, 'Both provider counters absent, but adapter fabricated a reportable usage object'


def ready_runtime(tmp_path,kind):
    svc=service(tmp_path)
    if kind=='AUTOMATIC1111':
        svc.client.payloads[('http://127.0.0.1:7860','/sdapi/v1/sd-models')]=[{'title':'SDXL.safetensors','sha256':'a'*64}]
    elif kind=='COMFYUI':
        svc.client.payloads[('http://127.0.0.1:8188','/system_stats')]={'system':{}}
        svc.client.payloads[('http://127.0.0.1:8188','/object_info')]={
            'CheckpointLoaderSimple':{'input':{'required':{'ckpt_name':[['sdxl.safetensors']]}}},
            **{name:{} for name in ('KSampler','EmptyLatentImage','CLIPTextEncode','VAEDecode','SaveImage')}}
    else:
        path=tmp_path/'qwen.gguf';gguf(path);exe=tmp_path/'llama-server';exe.write_bytes(b'SYNTHETIC_NOT_EXECUTABLE')
        svc.configure_runtime(LocalRuntimeInput(name='Managed fixture',type='LLAMA_CPP',endpoint='http://127.0.0.1:9991',model_path=str(path),executable=str(exe),management='MANAGED'))
    candidate=next(c for c in scan(svc)['candidates'] if c['runtime_type']==kind)
    runtime=enable_one(svc,candidate)
    return svc,runtime,candidate


def drift(svc,candidate):
    if candidate['runtime_type']=='AUTOMATIC1111':
        svc.client.payloads[('http://127.0.0.1:7860','/sdapi/v1/sd-models')][0]['sha256']='b'*64
    elif candidate['runtime_type']=='COMFYUI':
        svc.client.payloads[('http://127.0.0.1:8188','/object_info')].pop('SaveImage')
    else:Path(candidate['local_path']).write_bytes(b'INVALID_REPLACEMENT')


@pytest.mark.parametrize('kind',['AUTOMATIC1111','COMFYUI','LLAMA_CPP'])
def test_unchanged_rescan_preserves_explicit_enable(tmp_path,kind):
    svc,runtime,candidate=ready_runtime(tmp_path,kind)
    previous=svc.registrations[candidate['id']]['enabled_at']
    scan(svc)
    record=svc.registrations[candidate['id']]
    assert record['enabled'] and record['enabled_at']==previous


@pytest.mark.parametrize('kind',['AUTOMATIC1111','COMFYUI','LLAMA_CPP'])
def test_queued_adapter_rechecks_identity_before_dispatch_without_rescan(tmp_path,kind):
    from unittest.mock import Mock
    from app.asset_providers import AssetGenerationRequest
    svc,runtime,candidate=ready_runtime(tmp_path,kind)
    if kind=='LLAMA_CPP':
        adapter=runtime.provider_registry.resolve(candidate['provider_id']);adapter.client=FixtureClient()
    else:
        adapter=svc.route_bridge.asset_registry.get(candidate['provider_id'])
        adapter.delegate.generate=Mock(side_effect=AssertionError('stale media dispatch'))
    drift(svc,candidate)
    with pytest.raises((ValueError,ModelRuntimeError)):
        if kind=='LLAMA_CPP':adapter.generate_text(TextGenerationRequest(candidate['provider_id'],candidate['id'],'SYNTHETIC_PRIVATE_QUEUED'))
        else:adapter.generate(AssetGenerationRequest(candidate['provider_id'],candidate['id'],'SYNTHETIC_PRIVATE_QUEUED','queued-task'))
    if kind=='LLAMA_CPP':
        assert adapter.client.calls==[];svc.center.lifecycle.start.assert_not_called()
    else:adapter.delegate.generate.assert_not_called()
    assert not svc.registrations[candidate['id']]['enabled']


@pytest.mark.parametrize('done',[False,None,1,'true'])
def test_buffered_ollama_requires_strict_terminal_completion(tmp_path,done):
    svc,runtime,candidate,adapter,wire=enabled(tmp_path)
    adapter.client=FixtureClient();adapter.client.payloads[('http://127.0.0.1:11434','/api/generate')]={'response':'UNFINISHED','done':done}
    with pytest.raises(ModelRuntimeError):adapter.generate_text(TextGenerationRequest(candidate['provider_id'],candidate['id'],'Synthetic'))


@pytest.mark.parametrize('counts,expected',[
    ({},None),({'prompt_eval_count':None,'eval_count':None},None),
    ({'prompt_eval_count':True,'eval_count':-1},None),
    ({'prompt_eval_count':0,'eval_count':0},(0,0,0)),
    ({'prompt_eval_count':7,'eval_count':3},(7,3,10)),
    ({'prompt_eval_count':7},(7,None,None)),
])
def test_buffered_usage_preserves_only_actual_provider_counters(tmp_path,counts,expected):
    svc,runtime,candidate,adapter,wire=enabled(tmp_path)
    adapter.client=FixtureClient();adapter.client.payloads[('http://127.0.0.1:11434','/api/generate')]={'response':'Synthetic completed','done':True,**counts}
    result=adapter.generate_text(TextGenerationRequest(candidate['provider_id'],candidate['id'],'Synthetic'))
    if expected is None:assert result.usage is None
    else:assert (result.usage.input_tokens,result.usage.output_tokens,result.usage.total_tokens)==expected


@pytest.mark.parametrize('stream',[False,True])
def test_legacy_ollama_missing_usage_is_unknown(stream):
    import json
    from urllib.parse import urlsplit
    from app.providers import OllamaProvider
    from app.model_runtime import LegacyTextProviderAdapter
    from test_local_ai_discovery_egress import OllamaWire,WireResponse
    wire=OllamaWire();original=wire.open
    def no_counters(request,**kwargs):
        if urlsplit(request.full_url).path=='/api/generate':
            return WireResponse(json.dumps({'response':'Synthetic','done':True}).encode()+b'\n')
        return original(request,**kwargs)
    wire.open=no_counters
    provider=OllamaProvider('http://localhost:11434');provider._metadata_client=wire.client()
    adapter=LegacyTextProviderAdapter('ollama',provider);request=TextGenerationRequest('ollama',wire.tag['name'],'Synthetic')
    result=list(adapter.stream_text(request))[-1].response if stream else adapter.generate_text(request)
    assert result.usage is None


def test_legacy_buffered_incomplete_response_cannot_complete():
    import json
    from urllib.parse import urlsplit
    from app.providers import OllamaProvider,ProviderError
    from test_local_ai_discovery_egress import OllamaWire,WireResponse
    wire=OllamaWire();original=wire.open
    def unfinished(request,**kwargs):
        if urlsplit(request.full_url).path=='/api/generate':return WireResponse(json.dumps({'response':'UNFINISHED','done':False}).encode())
        return original(request,**kwargs)
    wire.open=unfinished;provider=OllamaProvider('http://localhost:11434');provider._metadata_client=wire.client()
    with pytest.raises(ProviderError):provider.generate('Synthetic',wire.tag['name'])
