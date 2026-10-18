"""Mounted original-owner IMAGE checks; File/real-PG fixture variants, injected transport."""
from copy import deepcopy
from types import SimpleNamespace
from threading import Event
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from test_director_image_jobs_additive import lane, rig, setup, allow_unpriced, dispatch, wait
from test_director_image_adoption_additive import completed, declare, review, adoption, adopt

@pytest.fixture
def mounted(lane):
    from app.creative.api import create_creative_router
    from app.model_center.discovery_authority import resolve_discovery_authority
    from app.trusted_sessions import TrustedSessionResolver
    from app.actor_context import SessionContext
    from app.experimental.flags import require_flag
    e=lane; sessions=TrustedSessionResolver(); token='mounted-token'
    sessions.register(token,SessionContext('mounted','mounted-client',e.r.actor,'workspace'))
    def authorize(nid,t,branch,permission):
        if t!=token or nid!=e.r.nid or not e.active['yes']:raise HTTPException(403,{'code':'DENIED'})
        return e.r.actor, e.r.scope if not branch else {'mode':'collaboration','novel_id':nid,'workspace_id':'workspace','storyline_id':'story','branch_id':branch}
    def host(request,t):
        return resolve_discovery_authority(request,t,settings_getter=lambda:SimpleNamespace(enable_packaged_runtime=False,enable_collaboration_runtime=False,frontend_origin=''),resolver_getter=lambda:sessions,bootstrap_getter=lambda:None)
    app=FastAPI();app.include_router(create_creative_router(e.r.service.creative,authorize,require_flag,
        require_host_session=lambda t:sessions.resolve(t),model_host_authority=host,director_images=e.coordinator))
    return SimpleNamespace(e=e,client=TestClient(app),headers={'x-session-token':token},base=f'/novels/{e.r.nid}/experimental/creative/director-image-v3')


def test_passive_mounted_capabilities_status_and_list(mounted):
    m=mounted;e=m.e;before=deepcopy(e.r.store.read(e.r.nid,e.r.scope));events=deepcopy(e.s.events)
    for path in ['/capabilities','/proposals','/proposals/'+e.row['id']]:
        response=m.client.get(m.base+path,headers=m.headers)
        assert response.status_code==200,response.text
        assert response.headers['cache-control']=='no-store'
        assert 'prompt' not in response.text and 'Author context' not in response.text
    assert e.r.store.read(e.r.nid,e.r.scope)==before
    assert e.s.events==events and e.persistence.load_all()==[]

@pytest.mark.parametrize('header',['forwarded','x-forwarded-for','x-real-ip','x-forwarded-host','x-forwarded-proto'])
def test_forwarded_host_denied(mounted,header):
    m=mounted;r=m.client.get(m.base+'/capabilities',headers={**m.headers,header:'127.0.0.1'})
    assert r.status_code==403 and r.headers['cache-control']=='no-store'


def test_cross_scope_and_revocation_deny_reopen(mounted):
    m=mounted;url=m.base+'/proposals/'+m.e.row['id']
    assert m.client.get(url,headers={**m.headers,'x-branch-id':'other'}).status_code in {403,404}
    m.e.active['yes']=False
    assert m.client.get(url,headers=m.headers).status_code==403


def test_strict_bounded_sanitized_input(mounted):
    m=mounted
    for body in [{'actor':'injected'},{'source_bytes':'private-secret'}, {'x':'x'*33000}]:
        response=m.client.post(m.base+'/preview',headers=m.headers,json=body)
        assert response.status_code in {413,422} and 'private-secret' not in response.text
        assert response.headers['cache-control']=='no-store'
    assert m.e.s.events['post']==0


@pytest.mark.parametrize('drift',['asset','target'])
def test_recovery_survives_target_drift_and_flags_off(mounted,monkeypatch,drift):
    m=mounted;e=m.e;allow_unpriced(e)
    # Keep the genuine original worker queued, with its original identity intact.
    # The private start launches _run_director_image directly; intercept only its thread start.
    import threading
    with monkeypatch.context() as queued:
        queued.setattr(threading.Thread,'start',lambda self:None)
        job=dispatch(e)
    if drift=='asset':
        with e.r.service._asset_scope(e.r.nid,e.r.scope):e.r.assets.delete(e.asset['id'],actor_id=e.r.actor)
    else:
        value={k:e.draft[k] for k in ('mode','title','source_independent','scenes')}
        value['title']='Later human edit'
        e.r.service.creative.update(e.r.nid,e.r.scope,e.r.actor,e.draft['id'],e.draft['version'],value)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','')
    response=m.client.post(m.base+'/proposals/'+e.row['id']+'/cancel',headers=m.headers,json={})
    assert response.status_code==200,response.text
    assert job.cancelled.is_set() and response.json()['upstream_stopped'] is False
    assert m.client.get(m.base+'/proposals/'+e.row['id'],headers=m.headers).status_code==200


def test_lost_dispatch_ack_status_never_reexecutes(mounted,monkeypatch):
    m=mounted;e=m.e;allow_unpriced(e);original=e.coordinator.dispatch
    def lost(*a,**kw):original(*a,**kw);raise RuntimeError('private-secret-lost-ack')
    monkeypatch.setattr(e.coordinator,'dispatch',lost)
    r=m.client.post(m.base+'/proposals/'+e.row['id']+'/dispatch',headers=m.headers,json={'expected_version':e.row['version'],'reviewed_preview_digest':e.row['binding']['preview_digest']})
    assert r.status_code==409 and 'private-secret' not in r.text
    response=m.client.get(m.base+'/proposals/'+e.row['id'],headers=m.headers)
    assert response.status_code==200 and response.json()['job_id']
    job=e.manager.get(response.json()['job_id']);wait(e,job)
    assert e.s.events['post']==1
    from app.creative.director_image_generation import DirectorImageCoordinator
    restarted=DirectorImageCoordinator(e.r.service,SimpleNamespace(jobs={},persistence=e.persistence,terminal=e.manager.terminal),e.broker,e.s.runtime)
    result=restarted.status(e.r.nid,e.r.scope,e.r.actor,e.row['id'],host=e.host,guard=e.guard)
    assert result['job_status']=='COMPLETED' and not result['can_cancel']
    assert e.s.events['post']==1


def test_historical_adoption_status_after_target_change(mounted):
    m=mounted;e=m.e;_,_,body=completed(e);declare(e,body);receipt=adopt(e,adoption(review(e)))
    response=m.client.get(m.base+'/proposals/'+e.row['id'],headers=m.headers)
    assert response.status_code==200,response.text
    status=response.json();assert status['adoption_receipt']['historical'] is True
    assert status['content_freshness']=='NOT_CHECKED' and 'proof' not in response.text
    assert status['adoption_receipt']['target']==receipt['target']


def test_mounted_explicit_preview_dispatch_declare_review_adopt(mounted):
    m=mounted;e=m.e
    value={'asset':{'asset_id':e.asset['id'],'version':e.asset['version'],'sha256':e.asset['sha256']},
        'target':e.row['binding']['target'],'provider_id':e.s.provider_id,'model_id':e.s.candidate['id'],
        'instruction':'Consider a human-reviewed camera treatment.'}
    result=m.client.post(m.base+'/preview',headers=m.headers,json=value)
    assert result.status_code==200,result.text
    preview=result.json();assert e.s.events['post']==0
    url=m.base+'/proposals/'+preview['id']
    # Default Broker gate stays intact and visible.
    blocked=m.client.post(url+'/dispatch',headers=m.headers,json={'expected_version':preview['version'],'reviewed_preview_digest':preview['preview_digest']})
    assert blocked.status_code==409 and blocked.json()['detail']['code']=='DIRECTOR_IMAGE_BROKER_ADMISSION_BLOCKED'
    assert e.s.events['post']==0
    allow_unpriced(e)
    response=m.client.post(url+'/dispatch',headers=m.headers,json={'expected_version':preview['version'],'reviewed_preview_digest':preview['preview_digest']})
    assert response.status_code==200,response.text
    wait(e,e.manager.get(response.json()['job_id']))
    response=m.client.post(url+'/prepare-review',headers=m.headers,json={'expected_version':2})
    assert response.status_code==200,response.text
    pending=response.json()
    value={'request_id':'mounted-declaration','expected_version':pending['accounting_version'],
        'reviewed_terminal_digest':pending['pending']['terminal_digest'],'declared_microusd':0,
        'evidence_note':'Human declares zero fee; not measured.','confirmed_declaration':True}
    assert m.client.post(url+'/review',headers=m.headers,json={}).status_code==409
    response=m.client.post(url+'/declare-cost',headers=m.headers,json=value)
    assert response.status_code==200,response.text
    response=m.client.post(url+'/review',headers=m.headers,json={})
    assert response.status_code==200,response.text
    reviewed=response.json();assert reviewed['measurement_verified'] is False
    response=m.client.post(url+'/adopt',headers=m.headers,json=adoption(reviewed))
    assert response.status_code==200,response.text
    assert response.json()['committed'] is True and e.s.events['post']==1
    document=e.r.service.creative.get(e.r.nid,e.r.scope,e.draft['id'])
    assert len(document['director_notes'])==1 and document['scenes']==e.draft['scenes']


def test_missing_persisted_job_reopens_metadata_without_replay(mounted,monkeypatch):
    m=mounted;e=m.e
    from app.creative.director_image_generation import COLLECTION
    from uuid import uuid4
    with e.r.raw_store.transaction(e.r.nid,e.r.scope) as state:
        row=state['collections'][COLLECTION][e.row['id']]
        row.update(status='DISPATCHED',job_id=str(uuid4()),request_digest='a'*64)
    for suffix in ['/proposals/'+e.row['id'],'/proposals']:
        response=m.client.get(m.base+suffix,headers=m.headers)
        assert response.status_code==200,response.text
        status=response.json() if 'items' not in response.json() else response.json()['items'][0]
        assert status['recovery_state']=='EXECUTOR_UNAVAILABLE_NO_REPLAY' and status['can_cancel'] is False
    assert e.s.events['post']==0 and e.manager.jobs=={}
