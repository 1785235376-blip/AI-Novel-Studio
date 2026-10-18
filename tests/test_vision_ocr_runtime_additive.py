"""Synthetic typed-runtime checks only; no OCR/provider/network quality claim."""
from dataclasses import replace
from hashlib import sha256
from threading import Event
from copy import deepcopy
import pytest
from app.model_runtime import GenerationRuntime,ProviderRegistry,ModelRegistry,ProviderDescriptor,ModelDescriptor,Modality,ModelRuntimeError,RuntimeErrorCode
from app.stable_identity import StableIdentityStore
from app.vision_ocr_runtime import VisionOCRRequest,VisionOCRResponse

class Provider:
    supports_dispatch_guard=True
    def __init__(self):
        self.calls=0;self.mutate=lambda request: None;self.result=lambda response: response
        self.route={'schema':'local-vision-ocr-admission/1','provider_id':'vision','model_id':'ocr',
            'endpoint':'http://127.0.0.1:8999','model_sha256':'a'*64,'admission_digest':'b'*64,
            'languages':['eng'],'adapter_version':'test-only/1'}
    def route_snapshot(self):return deepcopy(self.route)
    def recognize_image(self,request):
        request.dispatch_guard();self.calls+=1;self.mutate(request)
        text='SYNTHETIC protocol text; no source pixels were recognized.'
        return self.result(VisionOCRResponse('vision','ocr',text,{'model_called':True,
            'source_digest':request.source_digest,'input_sha256':sha256(request.content).hexdigest(),
            'route_digest':request.route_digest,'language':request.language,'text_sha256':sha256(text.encode()).hexdigest()}))

@pytest.fixture
def rig(tmp_path,monkeypatch):
    from app.experimental.flags import runtime_dependencies
    flags={'ai_execution_v2','narrative_production_v2','model_broker_v2','author_context_inspector_v2'}
    dependencies=runtime_dependencies()
    while True:
        expanded=flags|{dependency for flag in flags for dependency in dependencies[flag]}
        if expanded==flags:break
        flags=expanded
    monkeypatch.setenv('EXPERIMENTAL_FEATURES',','.join(sorted(flags)));monkeypatch.setenv('V1_ACCEPTANCE_MODE','false')
    identities=StableIdentityStore(tmp_path/'identities.json');identities.get_or_create('execution_node','local')
    providers=ProviderRegistry(identities);models=ModelRegistry(identities);provider=Provider()
    providers.register(ProviderDescriptor('vision','Test only','local',frozenset({Modality.VISION}),True,True),provider)
    models.register(ModelDescriptor('ocr','vision','Test only',Modality.VISION,frozenset({'OCR'})))
    runtime=GenerationRuntime(providers,models)
    return runtime,provider

def request(runtime,**changes):
    content=b'synthetic byte envelope; provider owns image decoding'
    values=dict(provider_id='vision',model_id='ocr',content=content,media_type='image/png',language='eng',
        source_digest=sha256(content).hexdigest(),route_digest=runtime.vision_ocr_node.binding('vision','ocr')['route_digest'],
        request_id='fixture-request',dispatch_guard=lambda:None)
    values.update(changes);return VisionOCRRequest(**values)

def test_construction_has_no_call_and_uses_original_registries(rig):
    runtime,provider=rig;assert provider.calls==0
    assert runtime.vision_ocr_node.providers is runtime.providers
    output=runtime.vision_ocr_node.execute(request(runtime))
    assert provider.calls==1 and output.receipt['review_required'] is True
    assert output.receipt['automatic_canon'] is False and output.receipt['model_quality']=='NOT_RUN'
    assert output.receipt['provider_uuid'] and output.receipt['execution_node_uuid']

@pytest.mark.parametrize('change',[{'content':b''},{'content':b'other'},{'content':b'a'*(4*1024*1024+1)},
 {'media_type':'application/pdf'},{'media_type':[]},{'language':'auto'},{'language':'eng+chi_sim'},
 {'source_digest':'bad'},{'route_digest':'bad'},{'dispatch_guard':None},{'cancellation':object()}])
def test_invalid_request_refuses_before_dispatch(rig,change):
    runtime,provider=rig
    with pytest.raises(ModelRuntimeError):request(runtime,**change)
    assert provider.calls==0

def test_language_must_be_admitted_not_inferred_from_installed_tool(rig):
    runtime,provider=rig
    with pytest.raises(ModelRuntimeError):runtime.vision_ocr_node.execute(request(runtime,language='zh'))
    assert provider.calls==0

def test_cancel_and_revoked_owner_prevent_dispatch(rig):
    runtime,provider=rig;cancel=Event();cancel.set()
    with pytest.raises(ModelRuntimeError) as error:runtime.vision_ocr_node.execute(request(runtime,cancellation=cancel))
    assert error.value.code==RuntimeErrorCode.CANCELLED
    def revoked():raise PermissionError('revoked')
    with pytest.raises(PermissionError):runtime.vision_ocr_node.execute(request(runtime,dispatch_guard=revoked))
    assert provider.calls==0

def test_changes_during_inference_discard_output(rig):
    runtime,provider=rig
    provider.mutate=lambda _:provider.route.update(admission_digest='c'*64)
    with pytest.raises(ModelRuntimeError):runtime.vision_ocr_node.execute(request(runtime))
    assert provider.calls==1

def test_provider_object_replacement_cannot_reuse_old_authority(rig):
    runtime,provider=rig
    def replace_provider(_):
        runtime.providers.register(runtime.providers.descriptors()[0],Provider(),replace=True)
    provider.mutate=replace_provider
    with pytest.raises(ModelRuntimeError):runtime.vision_ocr_node.execute(request(runtime))

@pytest.mark.parametrize('change',[{'text':''},{'text':'x'*262145},{'text':'bad\x00text'},{'text':b'not text'},
 {'text':'bad\ud800'},{'provider_id':'other'},{'model_id':'other'}])
def test_invalid_output_is_not_published(rig,change):
    runtime,provider=rig;provider.result=lambda output:replace(output,**change)
    with pytest.raises(ModelRuntimeError):runtime.vision_ocr_node.execute(request(runtime))

@pytest.mark.parametrize('change',[{'model_called':False},{'source_digest':'c'*64},{'input_sha256':'c'*64},
 {'route_digest':'c'*64},{'language':'zh'},{'text_sha256':'c'*64},{'private_data':'not allowed'}])
def test_wrong_or_extra_receipt_fields_fail_closed(rig,change):
    runtime,provider=rig;provider.result=lambda output:replace(output,receipt={**output.receipt,**change})
    with pytest.raises(ModelRuntimeError):runtime.vision_ocr_node.execute(request(runtime))

def test_flags_disabled_block_before_provider(rig,monkeypatch):
    runtime,provider=rig;value=request(runtime);monkeypatch.setenv('EXPERIMENTAL_FEATURES','')
    from fastapi import HTTPException
    with pytest.raises(HTTPException):runtime.vision_ocr_node.execute(value)
    assert provider.calls==0

def test_missing_stable_identity_refuses(rig):
    runtime,provider=rig;runtime.models.identity_store=None
    with pytest.raises(ModelRuntimeError):runtime.vision_ocr_node.binding('vision','ocr')
    assert provider.calls==0

@pytest.mark.parametrize('change',[{'endpoint':'https://example.com/ocr'},{'endpoint':['bad']},{'languages':['eng','eng']},
 {'languages':['eng+zh']},{'languages':[]},{'model_sha256':'bad'},{'extra':'unexpected'}])
def test_unadmitted_route_shapes_refuse_before_provider(rig,change):
    runtime,provider=rig;provider.route.update(change)
    with pytest.raises(ModelRuntimeError):runtime.vision_ocr_node.binding('vision','ocr')
    assert provider.calls==0

def test_public_manifest_includes_only_standard_typed_seam():
    import json
    from pathlib import Path
    manifest=json.loads((Path(__file__).resolve().parents[1]/'packaging/public-build.json').read_text())
    assert 'app/vision_ocr_runtime.py' in manifest['files']
    assert manifest['excluded_namespace']=='studio_private_extensions'
