"""Independent fixed-snapshot discovery invariants; synthetic metadata only."""
from pathlib import Path
import sys
from types import SimpleNamespace as S
import pytest
sys.path.insert(0,str(Path.cwd()/'tests'))
from test_local_ai_discovery import service, scan, ollama, approve_license, FixtureClient, gguf
from app.asset_providers import AssetProviderRegistry
from app.model_center.discovery_bridge import LocalDiscoveryBridge
from app.model_center.discovery_types import LocalRuntimeInput
from app.model_runtime import ProviderRegistry,ModelRegistry,TextModelNode,TextModelNodeInput,TextGenerationRequest,ModelRuntimeError


def enabled(tmp_path, tags=None, show=None):
    svc=service(tmp_path);ollama(svc.client,'ordinary-local-name')
    endpoint='http://127.0.0.1:11434'
    if tags is not None:svc.client.payloads[(endpoint,'/api/tags')]={'models':[tags]}
    if show is not None:svc.client.payloads[(endpoint,'/api/show')]=show
    runtime=S(provider_registry=ProviderRegistry(),model_registry=ModelRegistry())
    bridge=LocalDiscoveryBridge(svc,runtime,AssetProviderRegistry());svc.route_bridge=bridge
    candidate=scan(svc)['candidates'][0]
    svc.validate(candidate['id']);svc.register(candidate['id']);approve_license(svc,candidate['id'])
    svc.enable(candidate['id'])
    adapter=runtime.provider_registry.resolve(candidate['provider_id'])
    adapter.client=FixtureClient();adapter.client.payloads[(endpoint,'/api/generate')]={'response':'Synthetic response','done':True}
    return svc,runtime,bridge,candidate,adapter


@pytest.mark.parametrize('source',['tags','show'])
def test_remote_ollama_metadata_must_not_gain_local_route(tmp_path,source):
    tags={'name':'ordinary-local-name','digest':'synthetic','remote_host':'https://ollama.com:443','remote_model':'hosted-private-test'}
    show={'capabilities':['completion'],'remote_host':'https://ollama.com:443','remote_model':'hosted-private-test'}
    try: svc,runtime,bridge,candidate,adapter=enabled(tmp_path,tags=tags if source=='tags' else None,show=show if source=='show' else None)
    except (ValueError,ModelRuntimeError):return
    descriptor=next(x for x in runtime.provider_registry.descriptors() if x.provider_id==candidate['provider_id'])
    assert descriptor.provider_type!='local', 'Explicit remote_host was discarded and remote model granted local-source routing'


def test_enabled_text_model_works_at_author_stream_node_boundary(tmp_path):
    svc,runtime,bridge,candidate,adapter=enabled(tmp_path)
    node=TextModelNode(runtime.provider_registry,runtime.model_registry)
    request=TextGenerationRequest(candidate['provider_id'],candidate['id'],'SYNTHETIC_LOCAL_AUTHOR_TEXT')
    events=list(node.stream(TextModelNodeInput(request)))
    assert any(event.event_type=='generation.completed' for event in events)
    assert len(adapter.client.calls)==1


def test_rescan_changed_ollama_identity_invalidates_registered_route(tmp_path):
    svc,runtime,bridge,candidate,adapter=enabled(tmp_path)
    svc.client.payloads[('http://127.0.0.1:11434','/api/tags')]={'models':[{'name':'ordinary-local-name','digest':'REPLACED_MODEL_DIGEST','size':9999}]}
    scan(svc)
    try: adapter.generate_text(TextGenerationRequest(candidate['provider_id'],candidate['id'],'SYNTHETIC_PRIVATE_SOURCE'))
    except (ValueError,ModelRuntimeError):pass
    assert adapter.client.calls==[], 'Rescan observed replaced model identity but stale enabled registration still dispatched'


def test_disable_during_final_dispatch_guard_cannot_dispatch(tmp_path):
    svc,runtime,bridge,candidate,adapter=enabled(tmp_path)
    request=TextGenerationRequest(candidate['provider_id'],candidate['id'],'SYNTHETIC_PRIVATE_SOURCE',dispatch_guard=lambda:svc.disable(candidate['id']))
    try:adapter.generate_text(request)
    except (ValueError,ModelRuntimeError):pass
    assert not adapter.client.calls, 'Disable succeeded during authority callback, but adapter sent afterward'


def test_external_llama_uses_the_verified_runtime_model_id(tmp_path):
    svc=service(tmp_path);path=tmp_path/'qwen.gguf';gguf(path)
    endpoint='http://127.0.0.1:9991'
    svc.client.payloads[(endpoint,'/v1/models')]={'data':[{'id':'configured-model-alias'}]}
    svc.configure_runtime(LocalRuntimeInput(name='External llama',type='LLAMA_CPP',endpoint=endpoint,model_path=str(path),model_id='configured-model-alias'))
    runtime=S(provider_registry=ProviderRegistry(),model_registry=ModelRegistry())
    svc.route_bridge=LocalDiscoveryBridge(svc,runtime,AssetProviderRegistry())
    candidate=next(c for c in scan(svc)['candidates'] if c['local_path']==str(path))
    svc.validate(candidate['id']);svc.register(candidate['id']);approve_license(svc,candidate['id']);svc.enable(candidate['id'])
    adapter=runtime.provider_registry.resolve(candidate['provider_id']);adapter.client=FixtureClient()
    adapter.client.payloads[(endpoint,'/v1/chat/completions')]={'choices':[{'message':{'content':'Synthetic'}}]}
    adapter.generate_text(TextGenerationRequest(candidate['provider_id'],candidate['id'],'Synthetic'))
    assert adapter.client.calls[0][2]['model']=='configured-model-alias'


def test_late_enable_cannot_overwrite_a_newer_disable(tmp_path):
    svc,runtime,bridge,candidate,adapter=enabled(tmp_path)
    def revoke_while_validating(_):
        svc.disable(candidate['id'])
        return {'capabilities':['completion']}
    svc.client.payloads[('http://127.0.0.1:11434','/api/show')]=revoke_while_validating
    try:svc.enable(candidate['id'])
    except (ValueError,ModelRuntimeError):pass
    assert not svc.registrations[candidate['id']]['enabled'], 'Slow prior Enable resurrected the registration after newer Disable completed'


def test_comfy_capability_requires_selected_checkpoint_in_adapter_loader(tmp_path):
    svc=service(tmp_path);endpoint='http://127.0.0.1:8188'
    svc.client.payloads[(endpoint,'/system_stats')]={'system':{}}
    svc.client.payloads[(endpoint,'/object_info')]={
       'UNETLoader':{'input':{'required':{'unet_name':[['sdxl-only-unet.safetensors']]}}},
       'CheckpointLoaderSimple':{'input':{'required':{'ckpt_name':[['a-different-checkpoint.safetensors']]}}},
       **{name:{} for name in ('KSampler','EmptyLatentImage','CLIPTextEncode','VAEDecode','SaveImage')}}
    candidate=next(c for c in scan(svc)['candidates'] if c['model_name']=='sdxl-only-unet.safetensors')
    svc.validate(candidate['id']);svc.register(candidate['id']);approve_license(svc,candidate['id'])
    try: svc.enable(candidate['id'])
    except (ValueError,ModelRuntimeError):return
    assert not svc.registrations[candidate['id']]['enable_eligible'], 'Workflow loader cannot load this advertised UNET, but structural IMAGE validation passed'


@pytest.mark.parametrize('change',['cancel','permission'])
def test_managed_startup_rechecks_cancellation_and_authority_before_prompt(tmp_path,change):
    from threading import Event
    from unittest.mock import Mock
    svc=service(tmp_path);path=tmp_path/'qwen.gguf';gguf(path)
    exe=tmp_path/'llama-server';exe.write_bytes(b'SYNTHETIC_NOT_EXECUTABLE')
    endpoint='http://127.0.0.1:9991'
    svc.configure_runtime(LocalRuntimeInput(name='Managed fixture',type='LLAMA_CPP',endpoint=endpoint,model_path=str(path),executable=str(exe),management='MANAGED'))
    runtime=S(provider_registry=ProviderRegistry(),model_registry=ModelRegistry())
    bridge=LocalDiscoveryBridge(svc,runtime,AssetProviderRegistry());svc.route_bridge=bridge
    candidate=next(c for c in scan(svc)['candidates'] if c['local_path']==str(path))
    svc.validate(candidate['id']);svc.register(candidate['id']);approve_license(svc,candidate['id']);svc.enable(candidate['id'])
    cancelled=Event();permitted=[True]
    def startup(_):
        if change=='cancel':cancelled.set()
        else:permitted[0]=False
        return 'synthetic-owned-process'
    bridge.launch_on_demand=startup;svc.center.lifecycle.stop=Mock()
    adapter=runtime.provider_registry.resolve(candidate['provider_id']);adapter.client=FixtureClient()
    def guard():
        if not permitted[0]:raise ValueError('Permission revoked during startup')
    request=TextGenerationRequest(candidate['provider_id'],candidate['id'],'SYNTHETIC_PRIVATE_SOURCE',cancellation=cancelled,dispatch_guard=guard)
    with pytest.raises((ValueError,ModelRuntimeError)):adapter.generate_text(request)
    assert not adapter.client.calls
    svc.center.lifecycle.stop.assert_called_once_with('synthetic-owned-process')


@pytest.mark.parametrize('action',['validate','diagnostics'])
def test_legacy_validate_of_discovery_managed_runtime_does_not_execute_program(tmp_path,monkeypatch,action):
    from unittest.mock import Mock
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.model_center.api import create_model_center_router
    svc=service(tmp_path);path=tmp_path/'qwen.gguf';gguf(path)
    exe=tmp_path/'llama-server';exe.write_bytes(b'SYNTHETIC_NOT_EXECUTABLE')
    endpoint='http://127.0.0.1:9991'
    svc.configure_runtime(LocalRuntimeInput(name='Managed fixture',type='LLAMA_CPP',endpoint=endpoint,model_path=str(path),executable=str(exe),management='MANAGED'))
    runtime=S(provider_registry=ProviderRegistry(),model_registry=ModelRegistry())
    bridge=LocalDiscoveryBridge(svc,runtime,AssetProviderRegistry());svc.route_bridge=bridge
    candidate=next(c for c in scan(svc)['candidates'] if c['local_path']==str(path))
    svc.validate(candidate['id']);svc.register(candidate['id']);approve_license(svc,candidate['id']);svc.enable(candidate['id'])
    # Reproduce the definition inserted by a previous authorized on-demand task.
    # All lifecycle calls remain test doubles; nothing is actually launched.
    svc.center.lifecycle.start=Mock()
    svc.center.lifecycle.health=Mock(return_value=S(http_reachable=True,state='RUNNING'))
    rid=bridge.launch_on_demand(svc.registrations[candidate['id']])
    calls=[]
    def run(argv,**kwargs):
        calls.append(argv)
        return S(stdout=b'Synthetic version',stderr=b'')
    monkeypatch.setattr('app.model_center.service.subprocess.run',run)
    monkeypatch.setattr(svc.center,'capability_snapshot',lambda _:S(runtime_id=rid))
    # Retain real validation and route handlers, stub only HTTP health/status.
    svc.center.lifecycle.health=Mock(return_value=S(http_reachable=True,state='RUNNING',process_alive=False,latency_ms=None,last_success=None,last_failure=None,safe_error_code=None))
    app=FastAPI();app.include_router(create_model_center_router(svc.center,mutation_authorization=lambda token:{'can_mutate':token=='synthetic'}))
    client=TestClient(app,raise_server_exceptions=False)
    response=getattr(client,'post' if action=='validate' else 'get')('/api/model-center/runtimes/'+rid+'/'+action,headers={'X-Session-Token':'synthetic'})
    assert response.status_code==200,response.text
    assert calls==[], {'unintended_process_invocations':calls,'runtime_id':rid}
