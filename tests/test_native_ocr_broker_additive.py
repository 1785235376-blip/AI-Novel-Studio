"""Private original broker inventory/admission, not public Research availability."""
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4
import base64
import pytest

from app.experimental.model_broker import ModelBrokerService
from app.experimental.research_library import ResearchLibraryService
from app.experimental.research_vision import PreparedResearchOCRSource
from app.local_tesseract_ocr import LocalTesseractOCRProvider
from app.model_runtime import ProviderDescriptor,ModelDescriptor,Modality
from app.runtime import Runtime
from app.stable_identity import StableIdentityStore
from test_v2_independent_workspace import rig
from test_r4_research_library import payload
from test_research_ocr_job_persistence_additive import reopen
from test_research_ocr_job_execution_additive import wait
from test_local_tesseract_ocr_additive import image_bytes
from types import SimpleNamespace


def configured(e,monkeypatch):
    from app.experimental.flags import runtime_dependencies
    from app.experimental.research_ocr_execution import FLAGS
    required=set(FLAGS);dependencies=runtime_dependencies()
    while True:
        expanded=required|{f for flag in required for f in dependencies[flag]}
        if expanded==required:break
        required=expanded
    monkeypatch.setenv('EXPERIMENTAL_FEATURES',','.join(sorted(required)));monkeypatch.setenv('V1_ACCEPTANCE_MODE','false')
    tool=Path('/usr/bin/tesseract');model=Path('/usr/share/tesseract-ocr/5/tessdata/eng.traineddata')
    if not tool.is_file() or not model.is_file():pytest.skip('Installed native English OCR fixture unavailable')
    runtime=Runtime(StableIdentityStore(e.root/'native-broker-identities.json'))
    provider=LocalTesseractOCRProvider(provider_id='native-ocr',model_id='eng',executable=tool,
        executable_sha256=sha256(tool.read_bytes()).hexdigest(),traineddata=model,
        model_sha256=sha256(model.read_bytes()).hexdigest(),language='eng')
    runtime.provider_registry.register(ProviderDescriptor('native-ocr','Native fixture','local',frozenset({Modality.VISION}),True,True),provider)
    runtime.model_registry.register(ModelDescriptor('eng','native-ocr','English fixture',Modality.VISION,frozenset({'OCR'})))
    research=ResearchLibraryService(e.raw_store,e.novels,e.chapters,historical_inspection=True)
    row=research.import_file(e.nid,e.scope,e.actor,payload(filename='fixture.png',content_base64=base64.b64encode(image_bytes()).decode()),guard=lambda:None)
    source=PreparedResearchOCRSource(research,e.nid,e.scope,e.actor,row['id'],1,lambda:None)
    identity=source.binding['project_incarnation']
    @contextmanager
    def lease():
        with e.store.existing_owner_only(),e.store.owner_lease(e.nid) as current:
            if current!=identity:raise ValueError('ORIGINAL_OWNER_CHANGED')
            yield current
    broker=ModelBrokerService(e.raw_store,e.novels,e.chapters,runtime=runtime)
    route=broker.candidates(local_ocr_only=True)[0]
    decision=broker.preview(e.nid,e.scope,e.actor,{'capability':'VISION','policy':'CUSTOM',
        'preferred_route':route['route_id'],'max_cost_microusd':0},guard=source.validate_current,
        route_guard=lambda _:source.validate_current(),local_ocr_only=True,owner_lease=lease)
    return SimpleNamespace(runtime=runtime,provider=provider,source=source,research=research,row=row,
        broker=broker,route=route,decision=decision,lease=lease)


def reserve(e,c,job_id=None,key='one'):
    return c.broker.reserve(e.nid,e.scope,e.actor,c.decision['id'],c.decision['version'],key,
        job_id or str(uuid4()),guard=c.source.validate_current,owner_lease=c.lease)


def test_private_inventory_and_zero_fee_are_not_synthetic_or_public(rig,monkeypatch):
    c=configured(rig,monkeypatch)
    assert c.decision['chosen']['synthetic'] is False
    assert c.decision['chosen']['cost_state']=='KNOWN_LOCAL_PROVIDER_ZERO'
    assert c.decision['chosen']['price']['applicability']=='native_provider_fee_only_excludes_host_compute'
    assert c.decision['execution_authorized'] is False
    assert not any(r['route_id']==c.route['route_id'] for r in c.broker.candidates())
    assert c.decision['candidate_profile']=='LOCAL_NATIVE_OCR_ONLY_V1'
    with pytest.raises(ValueError,match='LOCAL_OCR_PROFILE'):
        c.broker.preview(rig.nid,rig.scope,rig.actor,{'capability':'VISION','allow_cloud_fallback':True},
            local_ocr_only=True,owner_lease=c.lease,guard=c.source.validate_current)


def test_original_reserve_dispatch_finalize_records_local_zero(rig,monkeypatch):
    c=configured(rig,monkeypatch);jid=str(uuid4());entry=reserve(rig,c,jid)
    c.broker.guard_dispatch(rig.nid,rig.scope,rig.actor,entry['id'],jid,c.source.validate_current,owner_lease=c.lease)
    settled=c.broker.finalize(rig.nid,rig.scope,rig.actor,entry['id'],jid,'COMPLETED',owner_lease=c.lease)
    assert settled['status']=='SETTLED' and settled['actual_microusd']==0
    assert settled['cost_state']=='KNOWN_LOCAL_PROVIDER_ZERO'
    assert c.broker.budget(rig.nid,rig.scope)['inflight']==0


def test_disabled_or_replaced_provider_invalidates_original_preview(rig,monkeypatch):
    c=configured(rig,monkeypatch)
    model=next(m for m in c.runtime.model_registry.descriptors() if m.provider_id=='native-ocr')
    c.runtime.model_registry.register(replace(model,enabled=False),replace=True)
    with pytest.raises(ValueError):reserve(rig,c)
    assert c.broker.ledger(rig.nid,rig.scope,rig.actor)==[]


def test_original_owner_recreation_refuses_late_native_reservation(rig,monkeypatch):
    c=configured(rig,monkeypatch);rig.novels.delete(rig.nid);rig.create_project(nid=rig.nid)
    with pytest.raises((ValueError,FileNotFoundError)):reserve(rig,c)


def test_actual_ocr_job_uses_real_original_broker_hooks(rig,monkeypatch):
    c=configured(rig,monkeypatch);manager=reopen(rig);holder={}
    def dispatch():
        c.broker.guard_dispatch(rig.nid,rig.scope,rig.actor,holder['reservation']['id'],holder['job'].id,
            guard=c.source.validate_current,owner_lease=c.lease)
    def terminal():
        job=holder['job']
        c.broker.finalize(rig.nid,rig.scope,rig.actor,holder['reservation']['id'],job.id,
            job.execution_outcome or 'UNKNOWN',owner_lease=c.lease)
    binding={k:v for k,v in c.source.binding.items() if k not in {'contract','access','page'}}
    binding.update(contract='RESEARCH_OCR_JOB_V1',source_kind='IMAGE',language='eng',
        route_digest=c.route['identity']['native_ocr_binding']['route_digest'],reviewed_preview_digest='c'*64)
    job=manager._prepare_research_ocr_job(source=c.source,node=c.runtime.generation_runtime.vision_ocr_node,
        binding=binding,provider_id='native-ocr',model_id='eng',deadline=(datetime.now(timezone.utc)+timedelta(seconds=60)).isoformat(),
        before_dispatch=dispatch,on_terminal=terminal)
    holder['job']=job;holder['reservation']=reserve(rig,c,job.id)
    manager._start_research_ocr_job(job);wait(SimpleNamespace(job=job))
    assert job.status=='COMPLETED' and job.research_ocr_execution_authority.result().text=='STUDIO OCR 123'
    ledger=c.broker.ledger(rig.nid,rig.scope,rig.actor)
    assert len(ledger)==1 and ledger[0]['status']=='SETTLED' and ledger[0]['actual_microusd']==0
    assert ledger[0]['cost_state']=='KNOWN_LOCAL_PROVIDER_ZERO'
    assert c.research.analysis_status(rig.nid,rig.scope,rig.actor)['status']=='NOT_CONFIGURED'


def test_new_project_does_not_inherit_old_native_hold_or_idempotency(rig,monkeypatch):
    from copy import deepcopy
    c=configured(rig,monkeypatch);old=reserve(rig,c);before=deepcopy(old)
    assert rig.raw_store.read(rig.nid,rig.scope)['collections'][c.broker.LEDGER][old['id']]==before
    rig.novels.delete(rig.nid);rig.create_project(nid=rig.nid)
    fresh=configured(rig,monkeypatch)
    assert fresh.decision['chosen'] is not None, 'Old native reservation blocked a new project incarnation'
    new=reserve(rig,fresh,key='one')
    assert new['id']!=old['id']
    raw=rig.raw_store.read(rig.nid,rig.scope)['collections'][c.broker.LEDGER]
    assert raw[old['id']]==before
    assert [x['id'] for x in fresh.broker.ledger(rig.nid,rig.scope,rig.actor)]==[new['id']]
    assert c.decision['id'] not in {x['id'] for x in fresh.broker.decisions(rig.nid,rig.scope,rig.actor)}
    with pytest.raises((ValueError,FileNotFoundError)):
        fresh.broker.finalize(rig.nid,rig.scope,rig.actor,old['id'],old['job_id'],'FAILED')
    assert rig.raw_store.read(rig.nid,rig.scope)['collections'][c.broker.LEDGER][old['id']]==before


def test_subclassed_provider_cannot_claim_private_native_fee_admission(rig,monkeypatch):
    c=configured(rig,monkeypatch);original=c.provider
    class Unadmitted(LocalTesseractOCRProvider):pass
    replacement=Unadmitted(provider_id=original.provider_id,model_id=original.model_id,
        executable=original.executable,executable_sha256=original.executable_sha256,
        traineddata=original.traineddata,model_sha256=original.model_sha256,language=original.language)
    descriptor=next(d for d in c.runtime.provider_registry.descriptors() if d.provider_id=='native-ocr')
    c.runtime.provider_registry.register(descriptor,replacement,replace=True)
    assert c.broker.candidates(local_ocr_only=True)==[]
    with pytest.raises(ValueError):reserve(rig,c)


def test_private_profile_requires_owner_lease_and_is_not_request_data(rig,monkeypatch):
    c=configured(rig,monkeypatch)
    with pytest.raises(ValueError,match='OWNER_REQUIRED'):
        c.broker.reserve(rig.nid,rig.scope,rig.actor,c.decision['id'],1,'missing-owner',str(uuid4()))
    with pytest.raises(ValueError):
        c.broker.preview(rig.nid,rig.scope,rig.actor,{'candidate_profile':'LOCAL_NATIVE_OCR_ONLY_V1'})
    assert c.broker.ledger(rig.nid,rig.scope,rig.actor)==[]
