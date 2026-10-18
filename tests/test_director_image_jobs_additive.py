"""Original File/PG owners, injected vision transport only; no live model proof."""
from copy import deepcopy
import json
import time
from types import SimpleNamespace
import pytest
import httpx
from test_v2_independent_workspace import rig, import_asset
from test_local_vision_runtime_additive import setup, Chunks, response
from app.creative.director_image_generation import DirectorImageCoordinator
from app.creative.director_image_terminal import FIELD
from app.local_ollama_vision import GuardedOllamaVisionHTTP

@pytest.fixture
def lane(rig, setup):
    from app.jobs import JobManager
    from app.services.generation_service import GenerationService
    from app.experimental.model_broker import ModelBrokerService
    from app.model_center.discovery_authority import resolve_discovery_authority
    from app.trusted_sessions import TrustedSessionResolver
    from app.actor_context import SessionContext
    from starlette.requests import Request
    from creative_director_execution_fixture import ForbiddenOwner
    r,s = rig,setup
    forbidden = ForbiddenOwner()
    persistence = GenerationService(r.bundle.generations)
    manager = JobManager(persistence,forbidden,forbidden,forbidden,memory_extractor=forbidden,
        snapshot_required=True,collaboration_updates=forbidden)
    broker = ModelBrokerService(r.raw_store,r.novels,forbidden,runtime=s.runtime)
    sessions = TrustedSessionResolver(); token = 'image-test-token'
    sessions.register(token,SessionContext('image-session','image-client',r.actor,'image-workspace'))
    host = resolve_discovery_authority(Request({'type':'http','method':'POST','scheme':'http','path':'/private',
        'headers':[],'client':('127.0.0.1',41000),'server':('127.0.0.1',8000),'query_string':b''}),token,
        settings_getter=lambda:SimpleNamespace(enable_packaged_runtime=False,enable_collaboration_runtime=False,frontend_origin=''),
        resolver_getter=lambda:sessions,bootstrap_getter=lambda:None)
    draft = r.service.creative.create(r.nid,r.scope,r.actor,{'mode':'DIRECTOR','title':'Human draft',
        'source_independent':True,'scenes':[{'id':'scene-1','sequence':1,'heading':'Human selected scene','action':'Author context'}]})
    asset = import_asset(r)
    active = {'yes':True}
    def guard():
        if not active['yes']: raise PermissionError('revoked')
    coordinator = DirectorImageCoordinator(r.service,manager,broker,s.runtime)
    advice = {'contract':'DIRECTOR_IMAGE_ADVICE_V3','observations':['Possible blue area.'],
        'suggestions':['Consider a wider framing.'],'uncertainty':'Image interpretation is unverified.'}
    def handler(request):
        s.events['post'] += 1
        return httpx.Response(200,stream=Chunks([response(message={'role':'assistant','content':json.dumps(advice)})]))
    s.provider.transport = GuardedOllamaVisionHTTP(transport=httpx.MockTransport(handler))
    value = coordinator.preview(r.nid,r.scope,r.actor,asset={'asset_id':asset['id'],'version':asset['version'],'sha256':asset['sha256']},
        target={'document_id':draft['id'],'version':draft['version'],'digest':r.service.creative.document_digest(draft),'scene_id':'scene-1'},
        provider_id=s.provider_id,model_id=s.candidate['id'],instruction='Suggest direction.',host=host,guard=guard)
    return SimpleNamespace(r=r,s=s,manager=manager,broker=broker,coordinator=coordinator,host=host,guard=guard,
        active=active,row=value,draft=draft,asset=asset,persistence=persistence)


def dispatch(e):
    return e.coordinator.dispatch(e.r.nid,e.r.scope,e.r.actor,e.row['id'],expected_version=e.row['version'],
        reviewed_preview_digest=e.row['binding']['preview_digest'],host=e.host,guard=e.guard)


def allow_unpriced(e):
    e.broker.configure_budget(e.r.nid,e.r.scope,e.r.actor,{'expected_version':0,'require_known_estimate':False})


def wait(e,job):
    until = time.monotonic()+5
    while time.monotonic()<until:
        if job.director_image_authority.publication_state in {'CONFIRMED','UNKNOWN'} or job.status in {'FAILED','CANCELLED'} and job.terminal_hook_status:
            return
        time.sleep(.005)
    pytest.fail(repr(job.public()))


def test_preview_exact_target_and_default_unknown_price_block(lane):
    e=lane
    assert e.s.events['post']==0 and e.persistence.load_all()==[]
    with pytest.raises(ValueError,match='BROKER_ADMISSION_BLOCKED'): dispatch(e)
    assert e.s.events['post']==0 and e.manager.jobs=={}
    assert e.r.service.creative.get(e.r.nid,e.r.scope,e.draft['id'])==e.draft


def test_original_job_persists_pending_with_unknown_accounting_and_no_adoption(lane):
    e=lane; allow_unpriced(e); job=dispatch(e); wait(e,job)
    assert job.status=='COMPLETED', job.public()
    saved=e.persistence.get(job.id)
    assert saved[FIELD]['accounting']['status']=='UNKNOWN_UPSTREAM'
    assert saved[FIELD]['accounting']['actual_microusd'] is None
    assert e.s.events['post']==1
    row=e.coordinator.prepare_pending(e.r.nid,e.r.scope,e.r.actor,e.row['id'],expected_version=2,host=e.host,guard=e.guard)
    assert row['pending']['adoption_available'] is False
    assert row['pending']['source']['asset']['sha256']==e.asset['sha256']
    assert row['pending']['target']['document_id']==e.draft['id']
    with pytest.raises(ValueError,match='ADOPTION_NOT_INTEGRATED'): e.coordinator.adopt()
    assert e.r.service.creative.get(e.r.nid,e.r.scope,e.draft['id'])==e.draft
    with pytest.raises(Exception): dispatch(e)
    assert len(e.manager.jobs)==1 and e.s.events['post']==1
    from app.jobs import generation_content_available
    assert not generation_content_available(job)
    with pytest.raises(FileNotFoundError): e.r.service.creative.proposals.get(e.r.nid,e.r.scope,e.r.actor,e.row['id'])


@pytest.mark.parametrize('change',['target','asset','authority','preview'])
def test_stale_or_unreviewed_preparation_never_dispatches(lane,change):
    e=lane; allow_unpriced(e)
    if change=='authority': e.active['yes']=False
    elif change=='preview': e.row['binding']['preview_digest']='a'*64
    elif change=='target':
        value={k:e.draft[k] for k in ('mode','title','source_independent','scenes')}; value['title']='Changed by human'
        e.r.service.creative.update(e.r.nid,e.r.scope,e.r.actor,e.draft['id'],e.draft['version'],value)
    else:
        with e.r.service._asset_scope(e.r.nid,e.r.scope):
            e.r.assets.delete(e.asset['id'])
    with pytest.raises(Exception): dispatch(e)
    assert e.s.events['post']==0 and e.manager.jobs=={}


def test_generic_job_routes_cannot_execute_image_or_mint_terminal(lane):
    e=lane
    with pytest.raises(ValueError): e.manager.prepare_job('creative_director_image_v3',{})
    allow_unpriced(e); job=dispatch(e); wait(e,job)
    saved=e.persistence.get(job.id)
    forged=deepcopy(saved); forged['id']='f9559522-1342-446d-acdc-b0cfebd1e13f'; forged[FIELD]['job_id']=forged['id']
    with pytest.raises(ValueError): e.persistence.save(forged)
    changed=deepcopy(saved); changed['output']='changed'
    with pytest.raises(ValueError): e.persistence.save(changed)


def test_completed_pending_can_reopen_from_original_repository_after_restart(lane):
    e=lane; allow_unpriced(e); job=dispatch(e); wait(e,job)
    from app.jobs import JobManager
    old=e.manager
    restarted=JobManager(e.persistence,old.chapters,old.contexts,old.canon,memory_extractor=old.memory_extractor,
        snapshot_required=True,collaboration_updates=old.collaboration_updates)
    e.coordinator.manager=restarted
    assert restarted.get(job.id).director_image_authority is None
    with pytest.raises(ValueError): restarted._start_director_image_job(restarted.get(job.id))
    pending=e.coordinator.prepare_pending(e.r.nid,e.r.scope,e.r.actor,e.row['id'],expected_version=2,host=e.host,guard=e.guard)
    assert pending['pending']['accounting_status']=='UNKNOWN_UPSTREAM' and e.s.events['post']==1


def test_cancel_queued_job_releases_original_reservation_without_post(lane,monkeypatch):
    e=lane; allow_unpriced(e)
    original=e.manager._run
    queued=[]
    monkeypatch.setattr(e.manager,'_run',lambda job:queued.append(job))
    job=dispatch(e)
    until=time.monotonic()+2
    while not queued and time.monotonic()<until: time.sleep(.005)
    e.coordinator.cancel(e.r.nid,e.r.scope,e.r.actor,e.row['id'],host=e.host,guard=e.guard)
    original(job)
    assert job.status=='CANCELLED' and e.s.events['post']==0
    ledger=e.broker.get(e.r.nid,e.r.scope,e.broker.LEDGER,job.director_image_authority.reservation['id'])
    assert ledger['status']=='RELEASED' and ledger['actual_microusd']==0


@pytest.mark.parametrize('change',['cancel','revoke','invalid_output'])
def test_possible_dispatch_failure_keeps_unknown_and_no_terminal(lane,change):
    e=lane; allow_unpriced(e)
    def handler(request):
        e.s.events['post']+=1
        if change=='cancel': next(iter(e.manager.jobs.values())).cancelled.set()
        elif change=='revoke': e.active['yes']=False
        return httpx.Response(200,stream=Chunks([response()]))
    e.s.provider.transport=GuardedOllamaVisionHTTP(transport=httpx.MockTransport(handler))
    job=dispatch(e); wait(e,job)
    assert job.status in {'FAILED','CANCELLED'} and e.s.events['post']==1
    saved=e.persistence.get(job.id); assert FIELD not in saved and not saved['output']
    ledger=e.broker.get(e.r.nid,e.r.scope,e.broker.LEDGER,job.director_image_authority.reservation['id'])
    assert ledger['status']=='UNKNOWN_UPSTREAM' and ledger['actual_microusd'] is None


def test_lost_terminal_acknowledgement_does_not_replay_or_overwrite_history(lane,monkeypatch):
    e=lane; allow_unpriced(e); original=e.persistence.save
    def lost(item):
        result=original(item)
        if FIELD in item: raise OSError('simulated acknowledgement loss')
        return result
    monkeypatch.setattr(e.persistence,'save',lost)
    job=dispatch(e); wait(e,job)
    assert job.director_image_authority.publication_state=='UNKNOWN' and job.status=='FAILED'
    saved=e.persistence.get(job.id)
    assert FIELD in saved and saved['status']=='COMPLETED' and e.s.events['post']==1
    # Durable exact history may be inspected with fresh authority; never re-executed.
    pending=e.coordinator.prepare_pending(e.r.nid,e.r.scope,e.r.actor,e.row['id'],expected_version=2,host=e.host,guard=e.guard)
    assert not pending['pending']['adoption_available']
    with pytest.raises(Exception): dispatch(e)
    assert len(e.manager.jobs)==1 and e.s.events['post']==1


def test_changed_target_after_terminal_blocks_pending(lane):
    e=lane; allow_unpriced(e); job=dispatch(e); wait(e,job)
    value={k:e.draft[k] for k in ('mode','title','source_independent','scenes')}; value['title']='Later human edit'
    e.r.service.creative.update(e.r.nid,e.r.scope,e.r.actor,e.draft['id'],e.draft['version'],value)
    with pytest.raises(ValueError,match='TARGET_CHANGED'):
        e.coordinator.prepare_pending(e.r.nid,e.r.scope,e.r.actor,e.row['id'],expected_version=2,host=e.host,guard=e.guard)
    assert e.s.events['post']==1


@pytest.mark.parametrize('kind',['asset','target'])
def test_source_or_target_change_after_post_blocks_terminal(lane,kind):
    e=lane; allow_unpriced(e)
    def handler(request):
        e.s.events['post']+=1
        if kind=='asset':
            with e.r.service._asset_scope(e.r.nid,e.r.scope): e.r.assets.delete(e.asset['id'])
        else:
            value={k:e.draft[k] for k in ('mode','title','source_independent','scenes')}; value['title']='Changed during inference'
            e.r.service.creative.update(e.r.nid,e.r.scope,e.r.actor,e.draft['id'],e.draft['version'],value)
        text=json.dumps({'contract':'DIRECTOR_IMAGE_ADVICE_V3','observations':['Visible object.'],
            'suggestions':['Try another angle.'],'uncertainty':'Unverified.'})
        return httpx.Response(200,stream=Chunks([response(message={'role':'assistant','content':text})]))
    e.s.provider.transport=GuardedOllamaVisionHTTP(transport=httpx.MockTransport(handler))
    job=dispatch(e); wait(e,job)
    assert job.status=='FAILED' and FIELD not in e.persistence.get(job.id) and e.s.events['post']==1
    ledger=e.broker.get(e.r.nid,e.r.scope,e.broker.LEDGER,job.director_image_authority.reservation['id'])
    assert ledger['status']=='UNKNOWN_UPSTREAM'


def test_restarted_queued_job_is_passive_and_retains_reservation(lane,monkeypatch):
    e=lane; allow_unpriced(e)
    monkeypatch.setattr(e.manager,'_run',lambda job:None)
    job=dispatch(e)
    from app.jobs import JobManager, require_whole_generation_acceptance, require_generation_content
    old=e.manager
    restored=JobManager(e.persistence,old.chapters,old.contexts,old.canon,memory_extractor=old.memory_extractor,
        snapshot_required=True,collaboration_updates=old.collaboration_updates).get(job.id)
    assert restored.status=='FAILED' and restored.error_code=='DIRECTOR_IMAGE_RESTART_UNKNOWN'
    assert restored.director_image_authority is None and not restored.output
    with pytest.raises(Exception): require_generation_content(restored)
    with pytest.raises(ValueError): require_whole_generation_acceptance(restored)
    with pytest.raises(ValueError): e.manager.start_prepared(restored)
    assert e.s.events['post']==0
    ledger=e.broker.get(e.r.nid,e.r.scope,e.broker.LEDGER,job.director_image_authority.reservation['id'])
    assert ledger['status']=='RESERVED'


def test_private_broker_authority_not_reconstructible_from_receipt(lane):
    e=lane; allow_unpriced(e); job=dispatch(e); wait(e,job)
    authority=job.director_image_authority.broker_authority
    from copy import copy
    from dataclasses import replace
    with pytest.raises(TypeError): copy(authority)
    with pytest.raises(ValueError): e.broker.candidates(local_vision_only=True,vision_authority=replace(authority))
    assert e.broker.candidates(local_vision_only=True)[0]['available'] is False
    with pytest.raises(ValueError): e.manager.cancel(job.id)
    saved=e.persistence.get(job.id)
    forged=deepcopy(saved); forged['generation_deadline']='2099-01-01T00:00:00+00:00'
    with pytest.raises(ValueError): e.persistence.save(forged)


def test_original_asset_and_project_leases_survive_scope_commit_boundary(lane,monkeypatch):
    from contextlib import contextmanager
    from app.creative.director_image_binding import ImageBinding
    e=lane; binding=ImageBinding.model_validate(e.row['binding'])
    original=e.r.raw_store.transaction; seen=[]
    @contextmanager
    def commit_boundary(nid,scope):
        with original(nid,scope) as state:
            yield state
            # This is after the coordinator's final body guard but before the
            # original raw owner's actual commit. Both leases must still live.
            owner=getattr(e.r.assets._scope,'binding',None)
            assert owner is not None and owner['novel_id']==nid
            assert nid in getattr(e.r.store._local,'owners',{})
            seen.append(True)
    monkeypatch.setattr(e.r.raw_store,'transaction',commit_boundary)
    with e.coordinator.transaction(binding,e.guard,e.host): pass
    assert seen==[True]
    assert getattr(e.r.assets._scope,'binding',None) is None


@pytest.mark.parametrize('field,value',[('provider','forged'),('model','forged'),('execution_outcome','FAILED')])
def test_generic_save_cannot_rewrite_terminal_actual_route_or_outcome(lane,field,value):
    e=lane; allow_unpriced(e); job=dispatch(e); wait(e,job)
    saved=e.persistence.get(job.id); changed=deepcopy(saved); changed[field]=value
    with pytest.raises(ValueError): e.persistence.save(changed)
    assert e.persistence.get(job.id)==saved
