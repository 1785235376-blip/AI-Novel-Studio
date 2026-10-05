"""Synthetic adapters only: no installed model, process launch, cloud or private data."""
from __future__ import annotations

import copy
import json
import struct
import threading
import time
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.asset_providers import AssetProviderRegistry
from app.model_center.discovery import LocalDiscoveryService
from app.model_center.discovery_api import create_local_discovery_router
from app.model_center.discovery_bridge import LocalDiscoveryBridge
from app.model_center.discovery_probes import LocalProbeClient, ProbeFailure, gguf_metadata, infer_family, scan_gguf_roots
from app.model_center.discovery_types import DiscoverySettingsInput, LocalRuntimeInput, RegistrationInput, local_endpoint
from app.model_center.service import create_default_model_center
from app.model_runtime import ModelRegistry, ProviderRegistry, Modality, TextGenerationRequest, ModelRuntimeError


class FixtureClient:
    def __init__(self): self.calls = []; self.payloads = {}
    def json(self, endpoint, path, *, body=None):
        self.calls.append((endpoint, path, body))
        result = self.payloads.get((endpoint, path), ProbeFailure('LOCAL_AI_PROBE_UNAVAILABLE'))
        if isinstance(result, Exception): raise result
        if callable(result): return result(body)
        return copy.deepcopy(result)


def service(tmp_path, client=None):
    center = create_default_model_center()
    center.lifecycle.start = Mock(side_effect=AssertionError('discovery must never launch'))
    return LocalDiscoveryService(center, tmp_path/'discovery.json', client=client or FixtureClient(),
        hardware_probe=lambda: {'platform':'Synthetic', 'architecture':'x86_64', 'ram_bytes':16*1024**3, 'gpus':[], 'status':'DETECTED'})


def scan(svc):
    job = svc.start_scan()
    deadline = time.monotonic()+3
    while time.monotonic() < deadline:
        job = svc.get_scan(job['id'])
        if job['status'] != 'RUNNING': return job
        time.sleep(.005)
    raise AssertionError('scan did not terminate')


def approve_license(svc, identifier):
    record = svc.registrations[identifier]
    svc.configure_registration(identifier, RegistrationInput(license_confirmed=True, workflow_adapter_id=record.get('workflow_adapter_id', '')))


def ollama(client, name='qwen3.6:8b', capabilities=('completion',)):
    endpoint = 'http://127.0.0.1:11434'
    client.payloads[(endpoint, '/api/tags')] = {'models':[{'name':name, 'size':1234, 'modified_at':'synthetic', 'digest':'abc'}]}
    client.payloads[(endpoint, '/api/show')] = {'capabilities':list(capabilities)}


def gguf(path, arch='qwen3', magic=b'GGUF', version=3):
    def string(value):
        data=value.encode(); return struct.pack('<Q', len(data))+data
    path.write_bytes(magic+struct.pack('<IQQ', version, 1, 1)+string('general.architecture')+struct.pack('<I',8)+string(arch))


def test_full_state_chain_does_not_enable_or_launch_implicitly(tmp_path):
    svc=service(tmp_path); ollama(svc.client)
    job=scan(svc); candidate=job['candidates'][0]; identifier=candidate['id']
    assert job['status']=='PARTIAL'  # Missing other runtimes is ordinary partial discovery.
    assert candidate['status']=='DISCOVERED' and not candidate['verified_capabilities']
    assert not svc.registrations
    with pytest.raises(ValueError, match='VALIDATE_BEFORE_REGISTER'): svc.register(identifier)
    validated=svc.validate(identifier)
    assert validated['verified_capabilities']==['TEXT'] and not validated['verified']
    assert not validated['enable_eligible'] and validated['status']=='LICENSE_REQUIRED'
    registered=svc.register(identifier)
    assert not registered['enabled'] and not svc.center.models[identifier].metadata['enabled']
    approve_license(svc, identifier)
    enabled=svc.enable(identifier)
    assert enabled['enabled'] and enabled['status']=='DEGRADED' and not enabled['verified']
    assert svc.disable(identifier)['status']=='DISABLED'
    assert svc.remove(identifier)=={'removed':True,'model_files_deleted':False}
    svc.center.lifecycle.start.assert_not_called()
    assert all(path in {'/api/tags','/api/version','/api/show','/system_stats','/sdapi/v1/sd-models','/v1/models'} for _,path,_ in svc.client.calls)


@pytest.mark.parametrize('name', ['qwen3:8b','Qwen3.5-27B-Q4_K_M.gguf','qwen3.6:4b','QwenFuture-Next.gguf'])
def test_qwen_family_is_flexible_but_name_does_not_verify(name):
    assert infer_family(name)==('QWEN',['TEXT'])


@pytest.mark.parametrize('name,family,modality', [('qwen-image-2512.safetensors','QWEN_IMAGE','IMAGE'),('flux.2-dev','FLUX','IMAGE'),('Z-Image-Turbo','ZIMAGE','IMAGE'),('MiniMax-H3','MINIMAX_H3','VIDEO'),('Wan2.2','WAN','VIDEO'),('LTX-2.5','LTX','VIDEO'),('SeedVR2-7b','SEEDVR2','RESTORATION'),('rife49.pth','RIFE','INTERPOLATION')])
def test_family_declarations_keep_utilities_separate(name,family,modality):
    assert infer_family(name)==(family,[modality])


@pytest.mark.parametrize('value', ['http://example.com:80','http://127.0.0.1.evil:80','http://192.168.1.4:80','http://169.254.169.254:80','http://0.0.0.0:80','http://user:secret@127.0.0.1:80','http://127.0.0.1:80?path=secret','http://localhost:80/#x','file:///tmp/model','http://localhost','http://localhost:80/%2fsecret'])
def test_endpoint_validation_blocks_remote_and_ambiguous_destinations(value):
    with pytest.raises(ValueError): local_endpoint(value)


def test_localhost_is_pinned_to_numeric_loopback():
    assert local_endpoint('http://localhost:11434/')=='http://127.0.0.1:11434'


@pytest.mark.parametrize('magic,version,valid', [(b'GGUF',3,True),(b'GGUF',2,True),(b'GGUF',1,False),(b'GGUF',99,False),(b'FAIL',3,False)])
def test_gguf_header_is_validated_without_reading_tensors(tmp_path,magic,version,valid):
    path=tmp_path/'qwen.gguf'; gguf(path,magic=magic,version=version)
    result=gguf_metadata(path)
    assert result['header_valid'] is valid
    if valid: assert result['general.architecture']=='qwen3'


def test_truncated_gguf_and_unknown_architecture_remain_unverified(tmp_path):
    path=tmp_path/'x.gguf'; path.write_bytes(b'GGUF')
    assert not gguf_metadata(path)['header_valid']
    path.write_bytes(b'GGUF'+struct.pack('<IQQ',3,0,0))
    assert not gguf_metadata(path)['header_valid']


def test_scans_only_configured_roots_bounded_depth_and_no_link(tmp_path):
    root=tmp_path/'models';root.mkdir(); gguf(root/'qwen.gguf')
    private=tmp_path/'private';private.mkdir();gguf(private/'secret.gguf')
    (root/'link').symlink_to(private, target_is_directory=True)
    (root/'readme.txt').write_text('private prompt never read')
    deep=root/'a'/'b'/'c'/'d';deep.mkdir(parents=True);gguf(deep/'too-deep.gguf')
    found=list(scan_gguf_roots([str(root)],threading.Event(),time.monotonic()+5))
    assert found==[root/'qwen.gguf']
    with pytest.raises(ValueError): DiscoverySettingsInput(scan_roots=[str(root/'link')])
    with pytest.raises(ValueError): DiscoverySettingsInput(scan_roots=['/'])


def test_unknown_ollama_and_embedding_are_not_assumed_text_capable(tmp_path):
    svc=service(tmp_path);ollama(svc.client,'mystery:latest',('embedding',))
    candidate=scan(svc)['candidates'][0]
    assert candidate['family']=='UNKNOWN' and candidate['declared_capabilities']==['TEXT']
    validated=svc.validate(candidate['id'])
    assert not validated['verified_capabilities'] and not validated['enable_eligible']
    svc.register(candidate['id'])
    with pytest.raises(ValueError,match='CAPABILITY_UNVERIFIED'): svc.enable(candidate['id'])


def test_comfy_model_node_workflow_and_inference_evidence_are_distinct(tmp_path):
    svc=service(tmp_path); endpoint='http://127.0.0.1:8188'
    svc.client.payloads[(endpoint,'/system_stats')]={'system':{'comfyui_version':'synthetic'}}
    svc.client.payloads[(endpoint,'/object_info')]={
        'UNETLoader':{'input':{'required':{'unet_name':[['qwen-image.safetensors','Wan2.2.safetensors','MiniMax-H3.safetensors','LTX2.safetensors','SeedVR2.pth','rife49.pth','unknown.safetensors']]}}}}
    candidates=scan(svc)['candidates']
    assert {c['modality'] for c in candidates}=={'IMAGE','VIDEO','RESTORATION','INTERPOLATION','UNKNOWN'}
    for candidate in candidates:
        validated=svc.validate(candidate['id'])
        assert validated['evidence']['model_listed'] is True
        assert validated['evidence']['model_file_exists'] is None
        assert validated['evidence']['node_classes']==['UNETLoader']
        assert validated['evidence']['workflow_status']=='NOT_CONFIGURED'
        assert not validated['enable_eligible'] and not validated['verified']
        if candidate['family'] in {'MINIMAX_H3','LTX'}: assert validated['status']=='LICENSE_REQUIRED'


def test_a1111_checkpoint_available_without_credentials(tmp_path):
    svc=service(tmp_path)
    svc.client.payloads[('http://127.0.0.1:7860','/sdapi/v1/sd-models')]=[{'title':'SDXL.safetensors [123]','filename':'synthetic.ckpt'}]
    candidate=scan(svc)['candidates'][0]
    assert svc.validate(candidate['id'])['verified_capabilities']==['IMAGE']
    svc.register(candidate['id']);approve_license(svc,candidate['id']);assert svc.enable(candidate['id'])['enabled']


def test_unavailable_timeout_and_invalid_runtime_are_partial_not_fatal(tmp_path):
    svc=service(tmp_path)
    svc.client.payloads[('http://127.0.0.1:11434','/api/tags')]=ProbeFailure('LOCAL_AI_PROBE_TIMEOUT')
    svc.client.payloads[('http://127.0.0.1:7860','/sdapi/v1/sd-models')]={'wrong':'shape'}
    job=scan(svc)
    assert job['status']=='PARTIAL' and len(job['runtimes'])>=3
    assert any(error['code']=='LOCAL_AI_PROBE_TIMEOUT' for error in job['errors'])
    assert not job['candidates']


def test_duplicate_runtime_model_identity_and_register_are_idempotent(tmp_path):
    svc=service(tmp_path);ollama(svc.client)
    svc.configure_runtime(LocalRuntimeInput(name='Saved Ollama',type='OLLAMA',endpoint='http://localhost:11434'))
    job=scan(svc); assert len(job['candidates'])==1
    identifier=job['candidates'][0]['id'];svc.validate(identifier)
    assert svc.register(identifier)==svc.register(identifier)
    assert scan(svc)['candidates'][0]['id']==identifier


def test_cancel_partial_results_and_scan_are_idempotent(tmp_path):
    svc=service(tmp_path);ollama(svc.client)
    started=threading.Event();release=threading.Event()
    def delayed(_): started.set();release.wait(2);return {'system':{}}
    svc.client.payloads[('http://127.0.0.1:8188','/system_stats')]=delayed
    first=svc.start_scan();assert started.wait(1)
    assert svc.start_scan()['id']==first['id']
    svc.cancel_scan(first['id']);release.set()
    deadline=time.monotonic()+2
    while svc.get_scan(first['id'])['status']=='RUNNING' and time.monotonic()<deadline:time.sleep(.01)
    job=svc.get_scan(first['id']);assert job['status']=='CANCELLED'
    assert len(job['candidates'])==1


def test_restart_requires_revalidation_without_startup_probe(tmp_path):
    svc=service(tmp_path);ollama(svc.client)
    candidate=scan(svc)['candidates'][0];svc.validate(candidate['id']);svc.register(candidate['id']);approve_license(svc,candidate['id']);svc.enable(candidate['id'])
    restored=service(tmp_path)
    record=restored.registrations[candidate['id']]
    assert not record['enabled'] and record['enable_blockers']==['REVALIDATION_REQUIRED']
    assert restored.client.calls==[]


def test_persistence_failure_does_not_publish_registration(tmp_path,monkeypatch):
    svc=service(tmp_path);ollama(svc.client)
    candidate=scan(svc)['candidates'][0];svc.validate(candidate['id'])
    monkeypatch.setattr('app.model_center.discovery.os.replace',Mock(side_effect=OSError('simulated')))
    with pytest.raises(ValueError,match='WRITE_FAILED'):svc.register(candidate['id'])
    assert not svc.registrations and candidate['id'] not in svc.center.models


def test_runtime_configuration_invalidates_enabled_route(tmp_path):
    svc=service(tmp_path);ollama(svc.client)
    config=LocalRuntimeInput(name='Ollama',type='OLLAMA',endpoint='http://localhost:11434')
    runtime=svc.configure_runtime(config)
    candidate=scan(svc)['candidates'][0];svc.validate(candidate['id']);svc.register(candidate['id']);approve_license(svc,candidate['id']);svc.enable(candidate['id'])
    svc.configure_runtime(config.model_copy(update={'endpoint':'http://127.0.0.1:11435'}),runtime['id'])
    record=svc.registrations[candidate['id']]
    assert not record['enabled'] and not record['validated_at']


def test_enable_revalidates_model_disappearance(tmp_path):
    svc=service(tmp_path);ollama(svc.client)
    candidate=scan(svc)['candidates'][0];svc.validate(candidate['id']);svc.register(candidate['id'])
    svc.client.payloads[('http://127.0.0.1:11434','/api/tags')]={'models':[]}
    with pytest.raises(ValueError,match='MODEL_OR_RUNTIME_NOT_FOUND'):svc.enable(candidate['id'])
    assert not svc.registrations[candidate['id']]['enabled']


def test_registry_bridge_routes_only_explicitly_enabled_and_disables_live_adapter(tmp_path):
    svc=service(tmp_path);ollama(svc.client)
    runtime=type('Runtime',(),{'provider_registry':ProviderRegistry(),'model_registry':ModelRegistry()})()
    svc.route_bridge=LocalDiscoveryBridge(svc,runtime,AssetProviderRegistry())
    candidate=scan(svc)['candidates'][0];identifier=candidate['id'];provider=candidate['provider_id']
    svc.validate(identifier);svc.register(identifier)
    assert not runtime.model_registry.contains(provider,identifier)
    approve_license(svc, identifier)
    svc.enable(identifier)
    assert runtime.model_registry.resolve(provider,identifier,Modality.TEXT).enabled
    adapter=runtime.provider_registry.resolve(provider)
    adapter.client=FixtureClient();adapter.client.payloads[('http://127.0.0.1:11434','/api/generate')]={'response':'synthetic local text'}
    response=adapter.generate_text(TextGenerationRequest(provider,identifier,'synthetic prompt'))
    assert response.text=='synthetic local text'
    assert adapter.client.calls[0][2]['model']=='qwen3.6:8b'
    svc.disable(identifier)
    with pytest.raises(ModelRuntimeError):adapter.generate_text(TextGenerationRequest(provider,identifier,'blocked'))
    with pytest.raises(ModelRuntimeError):runtime.model_registry.resolve(provider,identifier,Modality.TEXT)


@pytest.mark.parametrize('prefix',['/api/model-center/local-ai','/api/v1/model-center/local-ai'])
def test_router_requires_session_for_every_path_and_confirmed_enable(tmp_path,prefix):
    svc=service(tmp_path);ollama(svc.client)
    app=FastAPI();app.include_router(create_local_discovery_router(svc,prefix=prefix,mutation_authorization=lambda token:{'can_mutate':token=='test-session'}))
    client=TestClient(app)
    for method,path,payload in [('GET','',None),('POST','/scan',{}),('PUT','/settings',{'scan_roots':[]}),('POST','/candidates/x/register',{}),('DELETE','/registrations/x',None)]:
        assert client.request(method,prefix+path,json=payload).status_code==401
    headers={'X-Session-Token':'test-session'}
    candidate=scan(svc)['candidates'][0];identifier=candidate['id']
    assert client.post(prefix+f'/candidates/{identifier}/validate',headers=headers).status_code==200
    assert client.post(prefix+f'/candidates/{identifier}/register',headers=headers).status_code==200
    assert client.post(prefix+f'/registrations/{identifier}/enable',headers=headers,json={}).status_code==422
    assert client.post(prefix+f'/registrations/{identifier}/enable',headers=headers,json={'confirmed':False}).status_code==422
    approve_license(svc,identifier)
    assert client.post(prefix+f'/registrations/{identifier}/enable',headers=headers,json={'confirmed':True}).status_code==200
    assert client.delete(prefix+f'/registrations/{identifier}',headers=headers).json()['model_files_deleted'] is False


def test_minimax_legacy_audio_identity_is_not_reinterpreted():
    center=create_default_model_center()
    assert center.models['minimax-h3'].status=='DISABLED'
    assert 'VIDEO' not in center.models['minimax-h3'].capabilities
    assert center.models['minimax-h3-video'].capabilities==('VIDEO',)


def test_malformed_nested_comfy_payload_does_not_abort_other_probes(tmp_path):
    svc=service(tmp_path)
    svc.client.payloads[('http://127.0.0.1:8188','/system_stats')]={'system':[]}
    svc.client.payloads[('http://127.0.0.1:8188','/object_info')]={'Bad':{'input':[]}}
    svc.client.payloads[('http://127.0.0.1:7860','/sdapi/v1/sd-models')]=[{'title':'SDXL'}]
    candidates=scan(svc)['candidates']
    assert len(candidates)==1 and candidates[0]['runtime_type']=='AUTOMATIC1111'


def test_ollama_malformed_capabilities_string_is_not_evidence(tmp_path):
    svc=service(tmp_path);ollama(svc.client)
    svc.client.payloads[('http://127.0.0.1:11434','/api/show')]={'capabilities':'completion'}
    candidate=scan(svc)['candidates'][0]
    assert not svc.validate(candidate['id'])['verified_capabilities']


def test_names_with_incidental_family_substrings_stay_unknown():
    for value in ('swan-song.ckpt','conflux.safetensors','strife.pth','notqwen.gguf'):
        assert infer_family(value)==('UNKNOWN',[])


def test_llama_external_requires_advertised_model_identity(tmp_path):
    svc=service(tmp_path);path=tmp_path/'qwen.gguf';gguf(path)
    config=LocalRuntimeInput(name='llama',type='LLAMA_CPP',endpoint='http://127.0.0.1:9991',model_path=str(path),management='EXTERNAL')
    svc.configure_runtime(config)
    svc.client.payloads[(config.endpoint,'/v1/models')]={'data':[{'id':'a-different-model.gguf'}]}
    candidate=next(c for c in scan(svc)['candidates'] if c['local_path']==str(path))
    validated=svc.validate(candidate['id'])
    assert 'RUNTIME_MODEL_UNVERIFIED' in validated['enable_blockers']


def test_managed_gguf_validation_never_executes_and_keeps_low_memory_warning(tmp_path):
    svc=service(tmp_path);path=tmp_path/'qwen.gguf';gguf(path)
    exe=tmp_path/'llama-server.exe';exe.write_bytes(b'synthetic-not-an-executable')
    config=LocalRuntimeInput(name='llama',type='LLAMA_CPP',endpoint='http://127.0.0.1:9991',model_path=str(path),executable=str(exe),management='MANAGED',gpu_layers=4)
    svc.configure_runtime(config)
    candidate=next(c for c in scan(svc)['candidates'] if c['local_path']==str(path))
    validated=svc.validate(candidate['id'])
    assert validated['verified_capabilities']==['TEXT']
    assert 'CPU_OFFLOAD_MAY_BE_REQUIRED' in validated['validation_notes']
    svc.register(candidate['id']);approve_license(svc,candidate['id']);svc.enable(candidate['id'])
    svc.center.lifecycle.start.assert_not_called()


def test_discovery_paths_are_not_leaked_through_public_catalog(tmp_path):
    svc=service(tmp_path);path=tmp_path/'qwen.gguf';gguf(path)
    svc.configure_roots(DiscoverySettingsInput(scan_roots=[str(tmp_path)]))
    candidate=next(c for c in scan(svc)['candidates'] if c['local_path']==str(path))
    svc.validate(candidate['id']);svc.register(candidate['id'])
    assert svc.center.model(candidate['id'])['local_paths']==[]
    assert svc.snapshot()['registrations'][0]['local_path']==str(path)


def test_unknown_license_requires_user_acknowledgment(tmp_path):
    svc=service(tmp_path);ollama(svc.client)
    candidate=scan(svc)['candidates'][0];svc.validate(candidate['id']);svc.register(candidate['id'])
    with pytest.raises(ValueError,match='LICENSE_VALIDATION_REQUIRED'):svc.enable(candidate['id'])
    assert not svc.registrations[candidate['id']]['license_confirmed']


class ByteResponse:
    status=200
    def __init__(self,data):self.data=data
    def __enter__(self):return self
    def __exit__(self,*_args):return False
    def read(self,count=-1):
        if count < 0: count=len(self.data)
        result,self.data=self.data[:count],self.data[count:]
        return result


def test_probe_response_limit_and_redirect_fail_closed():
    client=LocalProbeClient()
    client.open=lambda *_args,**_kwargs:ByteResponse(b'x'*(4*1024*1024+1))
    with pytest.raises(ProbeFailure,match='TOO_LARGE'):client.json('http://127.0.0.1:1234','/models')
    from app.model_center.service import RuntimeProbeRedirectRejected
    client.open=Mock(side_effect=RuntimeProbeRedirectRejected('redirect'))
    with pytest.raises(ProbeFailure):client.json('http://127.0.0.1:1234','/models')
    assert client.open.call_count==1


def test_remove_registration_preserves_gguf_file(tmp_path):
    svc=service(tmp_path);path=tmp_path/'qwen.gguf';gguf(path);original=path.read_bytes()
    svc.configure_roots(DiscoverySettingsInput(scan_roots=[str(tmp_path)]))
    candidate=scan(svc)['candidates'][0];svc.validate(candidate['id']);svc.register(candidate['id']);svc.remove(candidate['id'])
    assert path.read_bytes()==original


def test_real_loopback_http_probe_ignores_proxy_and_rejects_redirect(monkeypatch):
    from http.server import BaseHTTPRequestHandler, HTTPServer
    class Handler(BaseHTTPRequestHandler):
        hits=[]
        def do_GET(self):
            self.hits.append(self.path)
            if self.path=='/redirect':
                self.send_response(307);self.send_header('Location','http://example.invalid:80/private');self.end_headers()
            else:
                self.send_response(200);self.end_headers();self.wfile.write(b'{"models":[]}')
        def log_message(self,*_args):pass
    server=HTTPServer(('127.0.0.1',0),Handler)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    monkeypatch.setenv('HTTP_PROXY','http://127.0.0.1:1')
    try:
        client=LocalProbeClient();url=f'http://127.0.0.1:{server.server_port}'
        assert client.json(url,'/api/tags')=={'models':[]}
        with pytest.raises(ProbeFailure):client.json(url,'/redirect')
        assert Handler.hits==['/api/tags','/redirect']
    finally:server.shutdown();server.server_close();worker.join(2)


def test_standard_comfy_workflow_structure_can_enable_without_claiming_inference(tmp_path):
    svc=service(tmp_path);endpoint='http://127.0.0.1:8188'
    info={node:{'input':{'required':{}}} for node in svc.workflow_adapters[0]['required_nodes']}
    info['CheckpointLoaderSimple']['input']['required']['ckpt_name']=[['SDXL.safetensors']]
    svc.client.payloads[(endpoint,'/system_stats')]={'system':{}}
    svc.client.payloads[(endpoint,'/object_info')]=info
    candidate=scan(svc)['candidates'][0];validated=svc.validate(candidate['id'])
    assert validated['evidence']['workflow_status']=='STRUCTURE_VALIDATED_NOT_GENERATED'
    assert validated['verified_capabilities']==['IMAGE'] and not validated['verified']
    svc.register(candidate['id']);approve_license(svc,candidate['id'])
    assert svc.enable(candidate['id'])['enabled']
    del info['SaveImage']
    svc.client.payloads[(endpoint,'/object_info')]=info
    with pytest.raises(ValueError,match='WORKFLOW_ADAPTER_REQUIRED'):svc.enable(candidate['id'])
    assert not svc.registrations[candidate['id']]['enabled']


def test_changed_model_digest_invalidates_prior_license_review(tmp_path):
    svc=service(tmp_path);ollama(svc.client)
    candidate=scan(svc)['candidates'][0];svc.validate(candidate['id']);svc.register(candidate['id']);approve_license(svc,candidate['id'])
    svc.enable(candidate['id'])
    svc.client.payloads[('http://127.0.0.1:11434','/api/tags')]['models'][0]['digest']='replacement-digest'
    with pytest.raises(ValueError,match='LICENSE_VALIDATION_REQUIRED'):svc.enable(candidate['id'])
    assert not svc.registrations[candidate['id']]['enabled']
    assert not svc.registrations[candidate['id']]['license_confirmed']


def test_enable_confirmation_is_strict_boolean():
    from app.model_center.discovery_types import EnableInput
    for value in (1,'true','yes',False,None):
        with pytest.raises(ValueError):EnableInput(confirmed=value)
    assert EnableInput(confirmed=True).confirmed


def test_managed_launch_occurs_only_at_task_dispatch_and_releases_after_task(tmp_path):
    from types import SimpleNamespace
    svc=service(tmp_path);path=tmp_path/'qwen.gguf';gguf(path)
    exe=tmp_path/'llama-server.exe';exe.write_bytes(b'synthetic')
    runtime=SimpleNamespace(provider_registry=ProviderRegistry(),model_registry=ModelRegistry())
    svc.route_bridge=LocalDiscoveryBridge(svc,runtime,AssetProviderRegistry())
    config=LocalRuntimeInput(name='llama',type='LLAMA_CPP',endpoint='http://127.0.0.1:9991',model_path=str(path),executable=str(exe),management='MANAGED')
    svc.configure_runtime(config)
    candidate=next(c for c in scan(svc)['candidates'] if c['local_path']==str(path))
    svc.validate(candidate['id']);svc.register(candidate['id']);approve_license(svc,candidate['id']);svc.enable(candidate['id'])
    svc.center.lifecycle.start.assert_not_called()
    svc.center.lifecycle.start=Mock(return_value=SimpleNamespace(state='STARTING'))
    svc.center.lifecycle.health=Mock(return_value=SimpleNamespace(http_reachable=True))
    svc.center.lifecycle.stop=Mock()
    adapter=runtime.provider_registry.resolve(candidate['provider_id']);adapter.client=FixtureClient()
    adapter.client.payloads[(config.endpoint,'/v1/chat/completions')]={'choices':[{'message':{'content':'Synthetic generated result'}}]}
    result=adapter.generate_text(TextGenerationRequest(candidate['provider_id'],candidate['id'],'synthetic prompt'))
    assert result.text=='Synthetic generated result'
    assert svc.center.lifecycle.start.call_count==1 and svc.center.lifecycle.stop.call_count==1
    definition=svc.center.lifecycle.start.call_args.args[0]
    assert definition.model_path==str(path)
    assert '--model' in definition.launch_arguments
    assert '--host' in definition.launch_arguments and '127.0.0.1' in definition.launch_arguments


def test_image_registry_enable_disable_and_media_selection(tmp_path):
    from types import SimpleNamespace
    from app.asset_providers import AssetGenerationRequest, AssetGenerationResult
    svc=service(tmp_path)
    svc.client.payloads[('http://127.0.0.1:7860','/sdapi/v1/sd-models')]=[{'title':'SDXL.safetensors'}]
    registry=AssetProviderRegistry();runtime=SimpleNamespace(provider_registry=ProviderRegistry(),model_registry=ModelRegistry())
    svc.route_bridge=LocalDiscoveryBridge(svc,runtime,registry)
    candidate=scan(svc)['candidates'][0];svc.validate(candidate['id']);svc.register(candidate['id']);approve_license(svc,candidate['id']);svc.enable(candidate['id'])
    row=svc.media_routes()[0]
    assert row['reachable'] and row['registered'] and row['default_model']==candidate['id']
    adapter=registry.get(candidate['provider_id'])
    adapter.delegate.generate=Mock(side_effect=lambda request:AssetGenerationResult(request.provider_id,request.model_id,'data:image/png;base64,c3ludGhldGlj'))
    output=adapter.generate(AssetGenerationRequest(candidate['provider_id'],candidate['id'],'synthetic','task'))
    assert adapter.delegate.generate.call_args.args[0].model_id=='SDXL.safetensors'
    assert output.model_id==candidate['id']
    svc.disable(candidate['id'])
    assert svc.media_routes()==[]
    with pytest.raises(ValueError):registry.get(candidate['provider_id'])
    with pytest.raises(ModelRuntimeError):adapter.generate(AssetGenerationRequest(candidate['provider_id'],candidate['id'],'blocked','task'))


def test_non_finite_runtime_json_is_rejected_before_snapshot_serialization():
    client=LocalProbeClient();client.open=lambda *_args,**_kwargs:ByteResponse(b'{"models":[{"name":"qwen","size":NaN}]}')
    with pytest.raises(ProbeFailure):client.json('http://127.0.0.1:1234','/api/tags')


def test_saved_legacy_local_endpoints_are_reused_without_bootstrap_network(tmp_path):
    from types import SimpleNamespace
    from app.providers import OllamaProvider
    from app.asset_providers import ComfyUIImageProvider
    svc=service(tmp_path)
    registry=AssetProviderRegistry();registry.register('saved-comfy',ComfyUIImageProvider(None,'http://127.0.0.1:8888'))
    runtime=SimpleNamespace(providers={'ollama':OllamaProvider('http://localhost:11435')},provider_registry=ProviderRegistry(),model_registry=ModelRegistry())
    LocalDiscoveryBridge(svc,runtime,registry)
    assert svc.client.calls==[]
    configs=svc._runtimes()
    assert any(r['endpoint']=='http://127.0.0.1:11435' for r in configs)
    assert any(r['endpoint']=='http://127.0.0.1:8888' for r in configs)


def test_public_catalog_hides_discovered_filenames_without_host_session(tmp_path):
    from app.model_center.api import create_model_center_router
    svc=service(tmp_path);ollama(svc.client,'private-model-filename')
    candidate=scan(svc)['candidates'][0];svc.validate(candidate['id']);svc.register(candidate['id'])
    app=FastAPI();app.include_router(create_model_center_router(svc.center,mutation_authorization=lambda token:{'can_mutate':token=='local'}))
    client=TestClient(app)
    assert 'private-model-filename' not in client.get('/api/model-center/models').text
    assert client.get('/api/model-center/models/'+candidate['id']).status_code==401
    assert 'private-model-filename' in client.get('/api/model-center/models',headers={'X-Session-Token':'local'}).text


def test_ollama_discovery_reuses_existing_enumerator_with_safe_reader(tmp_path,monkeypatch):
    from app.providers import OllamaProvider
    original=OllamaProvider.list_models;calls=[]
    def wrapper(self,**kwargs):
        calls.append(kwargs)
        return original(self,**kwargs)
    monkeypatch.setattr(OllamaProvider,'list_models',wrapper)
    monkeypatch.setattr('app.providers.urlopen',Mock(side_effect=AssertionError('unsafe legacy network path used')))
    svc=service(tmp_path);ollama(svc.client)
    candidate=scan(svc)['candidates'][0]
    assert candidate['model_name']=='qwen3.6:8b'
    assert candidate['evidence']['digest']=='abc'
    assert calls and callable(calls[0]['read_json']) and calls[0]['strict'] and calls[0]['include_details']


def test_ollama_enumeration_legacy_shape_and_strict_error_contract(monkeypatch):
    from app.providers import OllamaProvider
    payload={'models':[{'name':'qwen','size':123,'modified_at':'synthetic','digest':'digest','details':{'family':'qwen'}}]}
    monkeypatch.setattr('app.providers.urlopen',lambda *_args,**_kwargs:ByteResponse(json.dumps(payload).encode()))
    assert OllamaProvider('http://127.0.0.1:1').list_models()==[{'name':'qwen','size':123,'modified_at':'synthetic'}]
    provider=OllamaProvider('http://127.0.0.1:1')
    reader=Mock(side_effect=ProbeFailure('LOCAL_AI_PROBE_TIMEOUT'))
    assert provider.list_models(read_json=reader)==[]
    with pytest.raises(ProbeFailure,match='TIMEOUT'):provider.list_models(read_json=reader,strict=True)


def test_display_gpu_name_preserved_without_inventing_vram(monkeypatch):
    from app.model_center.discovery_probes import host_hardware
    from app.provider_runtime_v2_host_hardware_inventory import WindowsHostHardwareProbe,HostHardwareFacts
    fact=WindowsHostHardwareProbe._fact_from_dxgi_description(0x10DE,0,0,'Synthetic GPU')
    assert fact.name=='Synthetic GPU' and fact.dedicated_vram_bytes==0
    assert WindowsHostHardwareProbe._fact_from_dxgi_description(0x1414,123,2,'Software GPU') is None
    monkeypatch.setattr('app.model_center.discovery_probes.platform.system',lambda:'Windows')
    monkeypatch.setattr(WindowsHostHardwareProbe,'collect',lambda _self:HostHardwareFacts('AMD64',16*1024**3,(fact,)))
    result=host_hardware()
    assert result['gpus']==[{'vendor':'NVIDIA','name':'Synthetic GPU','dedicated_vram_bytes':0}]
