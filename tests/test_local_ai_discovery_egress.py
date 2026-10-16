"""Real request-serialization paths with synthetic local-only transports; no model server."""
from __future__ import annotations

import copy
import json
import time
from io import BytesIO
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.asset_providers import AssetProviderRegistry
from app.model_center.discovery_api import create_local_discovery_router
from app.model_center.discovery_bridge import LocalDiscoveryBridge
from app.model_center.discovery_probes import LocalProbeClient
from app.model_center.discovery_types import RegistrationInput
from app.model_runtime import ProviderRegistry,ModelRegistry,ModelRuntimeError,TextGenerationRequest
from app.providers import OllamaProvider,ProviderError
from test_local_ai_discovery import service,scan,ollama,approve_license


class WireResponse(BytesIO):
    status=200
    def __enter__(self):return self
    def __exit__(self,*_args):self.close()


class OllamaWire:
    """Captures urllib Request bytes after the production LocalProbeClient serializes them."""
    def __init__(self,name='ordinary-local-name'):
        self.tag={'name':name,'size':1234,'modified_at':'synthetic','digest':'a'*64,'details':{'format':'gguf','family':'qwen'}}
        self.show={'capabilities':['completion'],'details':{'format':'gguf','family':'qwen'},'model_info':{'general.architecture':'qwen3'}}
        self.calls=[];self.on_show=None;self.complete=True;self.response_text='synthetic local draft'
    def open(self,request,**_kwargs):
        path=urlsplit(request.full_url).path
        body=json.loads(request.data) if request.data else None
        self.calls.append((request.full_url,path,body))
        if path=='/api/tags':data={'models':[copy.deepcopy(self.tag)]}
        elif path=='/api/show':
            if self.on_show:self.on_show()
            data=copy.deepcopy(self.show)
        elif path=='/api/version':data={'version':'synthetic'}
        elif path=='/api/generate':
            if body.get('stream'):
                rows=[{'response':self.response_text,'done':False}]
                if self.complete:rows.append({'done':True,'prompt_eval_count':8,'eval_count':3})
                return WireResponse(('\n'.join(json.dumps(row) for row in rows)+'\n').encode())
            data={'response':self.response_text,'done':True,'prompt_eval_count':8,'eval_count':3}
        else:raise AssertionError('unexpected synthetic path '+path)
        return WireResponse(json.dumps(data).encode())
    def client(self):
        client=LocalProbeClient();client.open=self.open;return client
    @property
    def generations(self):return [call for call in self.calls if call[1]=='/api/generate']


def enabled(tmp_path):
    svc=service(tmp_path);wire=OllamaWire();svc.client=wire.client()
    runtime=SimpleNamespace(provider_registry=ProviderRegistry(),model_registry=ModelRegistry())
    svc.route_bridge=LocalDiscoveryBridge(svc,runtime,AssetProviderRegistry())
    candidate=scan(svc)['candidates'][0];svc.validate(candidate['id']);svc.register(candidate['id']);approve_license(svc,candidate['id']);svc.enable(candidate['id'])
    adapter=runtime.provider_registry.resolve(candidate['provider_id']);adapter.client=wire.client()
    wire.calls.clear()
    return svc,runtime,candidate,adapter,wire


@pytest.mark.parametrize('where',['tags','show'])
@pytest.mark.parametrize('field,value',[('remote_host','https://ollama.com'),('remote_model','remote-private-model')])
def test_hosted_metadata_with_innocent_name_never_gains_local_route(tmp_path,where,field,value):
    svc=service(tmp_path);wire=OllamaWire();svc.client=wire.client()
    (wire.tag if where=='tags' else wire.show)[field]=value
    candidate=scan(svc)['candidates'][0];record=svc.validate(candidate['id'])
    assert record['source_locality']=='REMOTE' and not record['local']
    assert not record['verified_capabilities'] and 'OLLAMA_REMOTE_MODEL_BLOCKED' in record['enable_blockers']
    svc.register(candidate['id']);approve_license(svc,candidate['id'])
    with pytest.raises(ValueError):svc.enable(candidate['id'])
    assert not wire.generations


@pytest.mark.parametrize('where,field',[('tags','digest'),('tags','size'),('tags','details'),('show','capabilities'),('show','details'),('show','model_info')])
def test_missing_positive_local_evidence_fails_closed(tmp_path,where,field):
    svc=service(tmp_path);wire=OllamaWire();svc.client=wire.client()
    (wire.tag if where=='tags' else wire.show).pop(field)
    record=svc.validate(scan(svc)['candidates'][0]['id'])
    assert record['source_locality']=='NOT_VERIFIED' and not record['verified_capabilities']
    assert not record['enable_eligible'] and not wire.generations


@pytest.mark.parametrize('where',['tags','show'])
def test_same_tag_becoming_hosted_after_enable_has_zero_prompt_requests(tmp_path,where):
    svc,runtime,candidate,adapter,wire=enabled(tmp_path)
    (wire.tag if where=='tags' else wire.show)['remote_host']='https://ollama.com'
    with pytest.raises(ModelRuntimeError):adapter.generate_text(TextGenerationRequest(candidate['provider_id'],candidate['id'],'SYNTHETIC_PRIVATE_MANUSCRIPT'))
    assert not wire.generations
    assert 'SYNTHETIC_PRIVATE_MANUSCRIPT' not in json.dumps(wire.calls)
    assert not svc.registrations[candidate['id']]['enabled']


def test_dispatch_rechecks_digest_even_without_scan(tmp_path):
    svc,runtime,candidate,adapter,wire=enabled(tmp_path);wire.tag['digest']='b'*64
    with pytest.raises(ModelRuntimeError):adapter.generate_text(TextGenerationRequest(candidate['provider_id'],candidate['id'],'SYNTHETIC_PRIVATE_MANUSCRIPT'))
    assert not wire.generations and not svc.registrations[candidate['id']]['enabled']


def test_cancel_during_metadata_wait_cannot_send_prompt(tmp_path):
    from threading import Event
    svc,runtime,candidate,adapter,wire=enabled(tmp_path);cancel=Event();wire.on_show=cancel.set
    with pytest.raises(ModelRuntimeError):adapter.generate_text(TextGenerationRequest(candidate['provider_id'],candidate['id'],'SYNTHETIC_PRIVATE_MANUSCRIPT',cancellation=cancel))
    assert not wire.generations


def test_disable_callback_after_metadata_prevents_prompt(tmp_path):
    svc,runtime,candidate,adapter,wire=enabled(tmp_path)
    with pytest.raises(ModelRuntimeError):adapter.generate_text(TextGenerationRequest(candidate['provider_id'],candidate['id'],'SYNTHETIC_PRIVATE_MANUSCRIPT',dispatch_guard=lambda:svc.disable(candidate['id'])))
    assert not wire.generations


@pytest.mark.parametrize('operation',['disable','remove','configure'])
def test_stale_enable_validation_cannot_overwrite_newer_control(tmp_path,operation):
    svc,runtime,candidate,adapter,wire=enabled(tmp_path)
    def newer_control():
        wire.on_show=None
        if operation=='disable':svc.disable(candidate['id'])
        elif operation=='remove':svc.remove(candidate['id'])
        else:svc.configure_registration(candidate['id'],RegistrationInput(license_confirmed=False))
    wire.on_show=newer_control
    with pytest.raises((ValueError,KeyError)):svc.enable(candidate['id'])
    assert not svc.registrations.get(candidate['id'],{}).get('enabled')


@pytest.mark.parametrize('operation',['generate','stream'])
@pytest.mark.parametrize('where',['tags','show'])
def test_legacy_ollama_leaf_blocks_hosted_models_before_prompt(operation,where):
    wire=OllamaWire();(wire.tag if where=='tags' else wire.show)['remote_model']='hosted'
    provider=OllamaProvider('http://localhost:11434');provider._metadata_client=wire.client()
    with pytest.raises(ProviderError):
        result=getattr(provider,operation)('SYNTHETIC_LOCAL_ONLY_TEXT',wire.tag['name'])
        if operation=='stream':list(result)
    assert not wire.generations and 'SYNTHETIC_LOCAL_ONLY_TEXT' not in json.dumps(wire.calls)


def test_legacy_ollama_leaf_pins_digest_and_has_no_unverified_fallback():
    wire=OllamaWire();provider=OllamaProvider('http://localhost:11434');provider._metadata_client=wire.client()
    assert provider.generate('synthetic first',wire.tag['name']).text=='synthetic local draft'
    wire.calls.clear();wire.tag['digest']='b'*64
    with pytest.raises(ProviderError):provider.generate('SYNTHETIC_CHANGED_SOURCE',wire.tag['name'])
    assert not wire.generations
    wire.show.pop('capabilities');provider=OllamaProvider('http://localhost:11434');provider._metadata_client=wire.client()
    with pytest.raises(ProviderError):list(provider.stream('SYNTHETIC_NO_METADATA',wire.tag['name']))
    assert not wire.generations


def test_complete_http_discovery_picker_diagnostics_and_author_job_draft(tmp_path,monkeypatch):
    from app import api as api_module,jobs as jobs_module
    from app.jobs import JobManager
    from app.runtime import Runtime
    from app.stable_identity import StableIdentityStore
    from test_application_model_selection_v070 import MemoryGenerations,Chapters,Contexts
    runtime=Runtime(StableIdentityStore(tmp_path/'identities.json'))
    svc=service(tmp_path);wire=OllamaWire();svc.client=wire.client();runtime.providers['ollama']._metadata_client=wire.client();svc.route_bridge=LocalDiscoveryBridge(svc,runtime,AssetProviderRegistry())
    chapter=Chapters();persistence=MemoryGenerations();contexts=Contexts()
    manager=JobManager(generations=persistence,chapters=chapter,contexts=contexts,canon=object(),memory_extractor=object(),snapshot_required=False,collaboration_updates=object())
    monkeypatch.setattr(api_module,'runtime',runtime);monkeypatch.setattr(jobs_module,'runtime',runtime)
    monkeypatch.setattr(api_module,'jobs',manager);monkeypatch.setattr(api_module,'chapter_service',chapter)
    monkeypatch.setattr(api_module,'novel_service',SimpleNamespace(get=lambda _: {'id':'n'}))
    monkeypatch.setattr(jobs_module.agent_runner,'build_prompt',lambda *_args:'SYNTHETIC_LOCAL_ONLY_AUTHOR_PROMPT')
    monkeypatch.setattr(jobs_module,'deterministic_review',lambda *_args:[])
    app=FastAPI();app.include_router(api_module.router,prefix="/api");app.include_router(create_local_discovery_router(svc,mutation_authorization=lambda token:{'can_mutate':token=='synthetic-session'}))
    client=TestClient(app);headers={'X-Session-Token':'synthetic-session'};prefix='/api/model-center/local-ai'
    started=client.post(prefix+'/scan',headers=headers).json();deadline=time.monotonic()+3
    while time.monotonic()<deadline:
        detected=client.get(prefix+'/scan/'+started['id'],headers=headers).json()
        if detected['status']!='RUNNING':break
        time.sleep(.005)
    candidate=next(item for item in detected['candidates'] if item['model_name']==wire.tag['name']);identifier=candidate['id']
    assert client.post(prefix+f'/candidates/{identifier}/validate',headers=headers).status_code==200
    assert client.post(prefix+f'/candidates/{identifier}/register',headers=headers).status_code==200
    assert client.put(prefix+f'/registrations/{identifier}',headers=headers,json={'license_confirmed':True,'workflow_adapter_id':''}).status_code==200
    assert client.post(prefix+f'/registrations/{identifier}/enable',headers=headers,json={'confirmed':True}).status_code==200
    adapter=runtime.provider_registry.resolve(candidate['provider_id']);adapter.client=wire.client()
    picker=client.get('/api/text-models').json()['items'];assert any(item['model_id']==identifier and item['available'] for item in picker)
    diagnostics=client.get('/api/novels/n/text-runtime-diagnostics',params={'provider_id':candidate['provider_id'],'model_id':identifier})
    assert diagnostics.status_code==200 and diagnostics.json()['state']=='READY'
    response=client.post('/api/generate/continue',json={'novel_id':'n','chapter_id':'c','profile':'LOCAL_ONLY','provider_id':candidate['provider_id'],'model_id':identifier})
    assert response.status_code==202
    job_id=response.json()['job_id'];deadline=time.monotonic()+3
    while time.monotonic()<deadline:
        result=client.get('/api/generation/'+job_id).json()
        if result['status'] in {'COMPLETED','FAILED'}:break
        time.sleep(.005)
    assert result['status']=='COMPLETED',result
    assert result['output']=='synthetic local draft' and result['requested_model']==identifier
    assert persistence.values[job_id]['status']=='COMPLETED'
    assert chapter.get('c')['content']=='chapter'  # Draft is not auto-accepted into正文.
    assert len(wire.generations)==1 and wire.generations[0][2]['prompt']=='SYNTHETIC_LOCAL_ONLY_AUTHOR_PROMPT'


@pytest.mark.parametrize('operation',['generate','stream'])
def test_legacy_leaf_rechecks_cancellation_after_metadata_wait(operation):
    from threading import Event
    wire=OllamaWire();cancel=Event();wire.on_show=cancel.set
    provider=OllamaProvider('http://localhost:11434');provider._metadata_client=wire.client()
    with pytest.raises(ProviderError):
        result=getattr(provider,operation)('SYNTHETIC_CANCELLED_PRIVATE',wire.tag['name'],cancellation=cancel)
        if operation=='stream':list(result)
    assert not wire.generations


@pytest.mark.parametrize('operation',['generate','stream'])
def test_legacy_leaf_authority_guard_runs_after_safe_metadata(operation):
    wire=OllamaWire();provider=OllamaProvider('http://localhost:11434');provider._metadata_client=wire.client()
    def revoked():raise ModelRuntimeError(__import__('app.model_runtime',fromlist=['RuntimeErrorCode']).RuntimeErrorCode.INVALID_REQUEST,'synthetic revoked')
    with pytest.raises(ModelRuntimeError):
        result=getattr(provider,operation)('SYNTHETIC_REVOKED_PRIVATE',wire.tag['name'],dispatch_guard=revoked)
        if operation=='stream':list(result)
    assert not wire.generations and any(call[1]=='/api/show' for call in wire.calls)
