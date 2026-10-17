"""Actual versioned HTTP actions over original File lifecycle owners.

Provider wire is mocked; no browser, live model or PostgreSQL claim.
"""
import json
from copy import deepcopy
import pytest
from creative_director_execution_fixture import lifecycle, wait
from test_v2_independent_director_adoption import board, output, review_body, raw_bytes
from test_director_durable_pending_review import restart, fresh_host
from test_director_observation_transport_additive import mounted

pytestmark=pytest.mark.file_backend_only


def preview_request(e):
    return {'expected_version':e.row['version'],'route_id':e.route['route_id'],
            'allow_synthetic':False,'max_output_tokens':512,'temperature':0.0}


def completed(e,m):
    e.wire_text=json.dumps(output(e))
    response=m.client.post(m.url+'/preview',headers=m.headers,json=preview_request(e))
    assert response.status_code==200,response.text
    preview=response.json()['receipt']
    assert preview['model_called'] is False and e.requests==[] and e.persistence.load_all()==[]
    assert 'host_principal' not in response.text and 'broker_decision' not in response.text
    before=raw_bytes(e)
    reopened=m.client.get(m.url+'/preview',headers=m.headers)
    assert reopened.status_code==200 and reopened.json()==response.json()
    assert raw_bytes(e)==before and e.requests==[]
    body={'expected_version':preview['version'],'reviewed_preview_digest':preview['reviewed_preview_digest']}
    dispatched=m.client.post(m.url+'/dispatch',headers=m.headers,json=body)
    assert dispatched.status_code in (200,409),dispatched.text
    # A response guard can lose a race after admission. Prove admission itself
    # occurred exactly once before accepting an uncertain HTTP receipt.
    assert len(e.manager.jobs)==1
    job=next(iter(e.manager.jobs.values()));wait(e,job)
    assert job.status=='COMPLETED' and job.terminal_hook_status=='COMPLETED'
    state=m.client.get(m.url+'/status',headers=m.headers)
    assert state.status_code==200 and state.json()['receipt']['phase']=='COMPLETED',state.text
    duplicate=m.client.post(m.url+'/dispatch',headers=m.headers,json=body)
    assert duplicate.status_code==409 and 'host_principal' not in duplicate.text and 'current' not in duplicate.json()['detail']
    assert len(e.manager.jobs)==len(e.persistence.load_all())==len(e.requests)==1
    return preview,state.json()['receipt']


def pending(e,m):
    preview,state=completed(e,m)
    body={'expected_version':state['version'],'terminal_evidence_digest':state['terminal_evidence_digest']}
    result=m.client.post(m.url+'/prepare-review',headers=m.headers,json=body)
    assert result.status_code==200,result.text
    assert 'reservation_id' not in result.text and 'host_principal' not in result.text
    before=raw_bytes(e)
    read=m.client.get(m.url+'/pending-review',headers=m.headers)
    assert read.status_code==200 and read.json()==result.json()
    assert raw_bytes(e)==before and len(e.requests)==1
    return result.json()['receipt']


def test_explicit_http_flow_adopts_once_and_reopens_from_original_owners(lifecycle):
    e=board(lifecycle);m=mounted(e,actions=True);candidate=pending(e,m)
    assert candidate['provenance']['quality_verification']=='HUMAN_REVIEW_REQUIRED'
    body=review_body(candidate);body['director_notes'][0]['note']='Human-reviewed direction.'
    response=m.client.post(m.url+'/review',headers=m.headers,json=body)
    assert response.status_code==200,response.text
    receipt=response.json()['receipt'];assert receipt['document']['status']=='DRAFT'
    assert 'director_notes' not in response.text and 'host_principal' not in response.text
    before=raw_bytes(e)
    duplicate=m.client.post(m.url+'/review',headers=m.headers,json=body)
    assert duplicate.status_code==409 and raw_bytes(e)==before
    restart(e);fresh_host(e);m=mounted(e,actions=True)
    result=m.client.post(m.url+'/reconcile-review',headers=m.headers,json=body)
    assert result.status_code==200 and result.json()['receipt']==receipt
    assert m.client.get(m.url+'/adopted-draft',headers=m.headers).json()['receipt']==receipt
    assert raw_bytes(e)==before and len(e.requests)==1 and len(e.persistence.load_all())==1
    draft=e.documents.get(e.nid,e.scope,receipt['document']['document_id'])
    assert draft['director_notes'][0]['note']=='Human-reviewed direction.'


@pytest.mark.parametrize('after_commit',[False,True])
def test_uncertain_review_response_requires_read_only_exact_reconciliation(lifecycle,monkeypatch,after_commit):
    e=board(lifecycle);m=mounted(e,actions=True);candidate=pending(e,m);body=review_body(candidate)
    original=e.coordinator._review_independent_pending
    def uncertain(*args,**kwargs):
        if after_commit: original(*args,**kwargs)
        raise ValueError('private-review-error-must-not-echo')
    monkeypatch.setattr(e.coordinator,'_review_independent_pending',uncertain)
    response=m.client.post(m.url+'/review',headers=m.headers,json=body)
    assert response.status_code==409 and 'private-review-error' not in response.text
    before=raw_bytes(e)
    result=m.client.post(m.url+'/reconcile-review',headers=m.headers,json=body)
    assert result.status_code==(200 if after_commit else 409)
    assert raw_bytes(e)==before and len(e.requests)==len(e.persistence.load_all())==1


@pytest.mark.parametrize('change',['host','token','origin','forwarded','writer','scope','synthetic','synthetic-int','extra','boolean-version'])
def test_preview_denials_never_call_model_or_write_proposal(lifecycle,change):
    e=board(lifecycle);m=mounted(e,actions=True,host=change!='host',writer=change!='writer')
    body=preview_request(e);headers=dict(m.headers)
    if change=='token':headers={}
    if change=='origin':headers['Origin']='https://untrusted.example'
    if change=='forwarded':headers['X-Forwarded-Host']='untrusted.example'
    if change=='scope':headers['X-Branch-ID']='different'
    if change=='synthetic':body['allow_synthetic']=True
    if change=='synthetic-int':body['allow_synthetic']=0
    if change=='extra':body['terminal_evidence']=True
    if change=='boolean-version':body['expected_version']=True
    before=raw_bytes(e)
    result=m.client.post(m.url+'/preview',headers=headers,json=body)
    assert result.status_code in (401,403,422),result.text
    assert raw_bytes(e)==before and e.requests==[] and e.persistence.load_all()==[]
    assert result.headers['cache-control']=='no-store'


def test_reads_and_actions_are_not_implicitly_mounted(lifecycle):
    e=board(lifecycle);m=mounted(e,actions=False);before=raw_bytes(e)
    for suffix in ('preview','dispatch','prepare-review','review','cancel'):
        assert m.client.post(m.url+'/'+suffix,headers=m.headers,json={}).status_code==404
    assert raw_bytes(e)==before and e.requests==[]


@pytest.mark.parametrize('dispatched',[False,True])
def test_http_cancel_only_signals_owned_worker_and_retains_true_settlement(lifecycle,monkeypatch,dispatched):
    from threading import Event
    e=board(lifecycle);m=mounted(e,actions=True);e.wire_text=json.dumps(output(e))
    entered,release=Event(),Event()
    if dispatched:
        def hold():
            entered.set();assert release.wait(15)
        e.wire_hook=hold
    else:
        original=e.manager._run
        def queued(job):
            entered.set();assert release.wait(15);original(job)
        monkeypatch.setattr(e.manager,'_run',queued)
    p=m.client.post(m.url+'/preview',headers=m.headers,json=preview_request(e)).json()['receipt']
    job=None
    try:
        result=m.client.post(m.url+'/dispatch',headers=m.headers,json={
            'expected_version':p['version'],'reviewed_preview_digest':p['reviewed_preview_digest']})
        assert result.status_code==200,result.text
        assert entered.wait(5) and len(e.manager.jobs)==1
        job=next(iter(e.manager.jobs.values()))
        state=m.client.get(m.url+'/status',headers=m.headers).json()['receipt']
        body={key:state[key] for key in ['job_id','request_digest','reviewed_preview_digest']}
        body['expected_version']=state['version']
        before=raw_bytes(e)
        denied=m.client.post(m.url+'/cancel',headers=m.headers,json={**body,'job_id':'foreign-job'})
        assert denied.status_code==409 and not job.cancelled.is_set()
        reader=mounted(e,actions=True,writer=False)
        assert reader.client.post(reader.url+'/cancel',headers=reader.headers,json=body).status_code==403
        assert not job.cancelled.is_set()
        e.active=False
        assert m.client.post(m.url+'/cancel',headers=m.headers,json=body).status_code==403
        assert not job.cancelled.is_set();e.active=True
        result=m.client.post(m.url+'/cancel',headers=m.headers,json=body)
        assert result.status_code==200,result.text
        assert result.json()['receipt']['cancellation_requested'] is True
        assert result.json()['receipt']['cancellation_confirmed'] is False
        assert job.cancelled.is_set() and raw_bytes(e)==before
    finally:
        e.active=True;release.set()
    assert job is not None and wait(e,job).status=='CANCELLED'
    state=m.client.get(m.url+'/status',headers=m.headers).json()['receipt']
    assert state['cancellation_confirmed'] is (not dispatched)
    assert state['settlement_state']==('UNKNOWN_UPSTREAM' if dispatched else 'RELEASED')
    assert state['upstream_cancellation_guaranteed'] is False
    assert len(e.requests)==int(dispatched) and len(e.persistence.load_all())==1


@pytest.mark.parametrize('change',['source','flag','host-session'])
def test_preview_does_not_grant_future_execution_authority(lifecycle,monkeypatch,change):
    e=board(lifecycle);m=mounted(e,actions=True)
    p=m.client.post(m.url+'/preview',headers=m.headers,json=preview_request(e)).json()['receipt']
    if change=='source':
        source=deepcopy(e.source)
        source['shots'][0]['action']='Changed after preview'
        e.documents.update(e.nid,e.scope,e.actor,source['id'],source['version'],{
            key:source[key] for key in ['mode','source_independent','title','scenes','shots']},reauthorize=e.guard)
    if change=='flag':monkeypatch.setenv('EXPERIMENTAL_FEATURES','')
    if change=='host-session':e.sessions.revoke(e.token)
    before=raw_bytes(e)
    result=m.client.post(m.url+'/dispatch',headers=m.headers,json={
        'expected_version':p['version'],'reviewed_preview_digest':p['reviewed_preview_digest']})
    assert result.status_code in (401,403,404,409),result.text
    assert raw_bytes(e)==before and e.requests==[] and e.persistence.load_all()==[]


def test_pending_http_read_rechecks_generation_after_final_callback(lifecycle,monkeypatch):
    e=board(lifecycle);m=mounted(e,actions=True);pending(e,m)
    job=next(iter(e.manager.jobs.values()))
    original=e.coordinator._pending_current;calls=0
    def changed(*args,**kwargs):
        nonlocal calls
        result=original(*args,**kwargs)
        if args[1]['status']=='INTERNAL_MODEL_PENDING_REVIEW':
            calls+=1
            if calls==2:
                saved=e.persistence.get(job.id);saved.update(status='FAILED',output='');e.persistence.save(saved)
        return result
    monkeypatch.setattr(e.coordinator,'_pending_current',changed)
    before=raw_bytes(e)
    response=m.client.get(m.url+'/pending-review',headers=m.headers)
    assert calls>=2
    assert response.status_code==409,response.text
    assert 'Candidate interpretation' not in response.text
    assert raw_bytes(e)==before and len(e.requests)==1


def test_unsupported_persistence_is_rejected_before_preview_side_effects(lifecycle,monkeypatch):
    e=board(lifecycle);m=mounted(e,actions=True);before=raw_bytes(e)
    monkeypatch.setattr(e.manager,'persistence',object())
    response=m.client.post(m.url+'/preview',headers=m.headers,json=preview_request(e))
    assert response.status_code==409
    assert raw_bytes(e)==before and e.requests==[] and e.manager.jobs=={}


def test_read_pending_does_not_publish_candidates_or_retry_a_job(lifecycle):
    e=board(lifecycle);m=mounted(e,actions=True);completed(e,m);before=raw_bytes(e)
    result=m.client.get(m.url+'/pending-review',headers=m.headers)
    assert result.status_code==409 and raw_bytes(e)==before
    assert len(e.requests)==len(e.persistence.load_all())==1
