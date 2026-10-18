"""Exact original File/PG owners; human declarations, injected vision only."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import pytest
from test_director_image_jobs_additive import lane, rig, setup, allow_unpriced, dispatch, wait
from app.creative.director_terminal_evidence import digest
from app.creative.director_image_terminal import FIELD


def completed(e):
    allow_unpriced(e); job=dispatch(e); wait(e,job)
    assert job.status=='COMPLETED'
    saved=e.persistence.get(job.id)
    ledger=e.broker.get(e.r.nid,e.r.scope,e.broker.LEDGER,saved[FIELD]['accounting']['id'])
    body={'contract':'DIRECTOR_IMAGE_COST_DECLARATION_V3','request_id':'human-declaration-1',
        'expected_version':ledger['version'],'reviewed_terminal_digest':digest(saved[FIELD]),
        'declared_microusd':0,'evidence_note':'Human declares local provider fee zero; unmeasured.',
        'confirmed_declaration':True}
    return job,saved,body


def declare(e,body):
    return e.coordinator.declare_cost(e.r.nid,e.r.scope,e.r.actor,e.row['id'],body,host=e.host,guard=e.guard)


def review(e):
    return e.coordinator.review(e.r.nid,e.r.scope,e.r.actor,e.row['id'],host=e.host,guard=e.guard)


def adoption(r):
    return {'contract':'DIRECTOR_IMAGE_ADOPTION_INPUT_V1','request_id':'human-adoption-1',
        'expected_version':r['proposal_version'],'target':r['target'],
        'reviewed_terminal_digest':r['terminal_digest'],'reviewed_accounting_digest':r['accounting_digest'],
        'selected_suggestions':[0],'note':'Human reviewed suggestion: consider a wider framing.',
        'human_review_confirmed':True}


def adopt(e,body):
    return e.coordinator.adopt(e.r.nid,e.r.scope,e.r.actor,e.row['id'],body,host=e.host,guard=e.guard)


def test_unknown_blocks_review_and_explicit_zero_preserves_historical_terminal(lane):
    e=lane; job,saved,body=completed(e)
    with pytest.raises(ValueError): review(e)
    result=declare(e,body)
    assert result['cost_state']=='HUMAN_DECLARED_LOCAL_COST' and result['measurement_verified'] is False
    assert result['actual_microusd']==0
    assert declare(e,body)==result
    assert e.persistence.get(job.id)==saved
    r=review(e)
    assert r['measurement_verified'] is False and r['observations_verified'] is False
    assert r['accounting']['measurement_verified'] is False
    assert e.r.service.creative.get(e.r.nid,e.r.scope,e.draft['id'])==e.draft


def test_explicit_scene_note_adoption_and_restart_replay(lane):
    e=lane; job,saved,body=completed(e); declare(e,body)
    request=adoption(review(e)); result=adopt(e,request)
    document=e.r.service.creative.get(e.r.nid,e.r.scope,e.draft['id'])
    assert document['version']==e.draft['version']+1
    assert document['scenes']==e.draft['scenes']
    assert len(document['director_notes'])==1
    assert document['director_notes'][0]['scene_id']=='scene-1'
    assert document['prompt_adoptions'][-1]==result['proof']
    assert result['proof']['source']['asset']['sha256']==e.asset['sha256']
    assert result['proof']['observations_verified'] is False
    from app.creative.director_image_generation import DirectorImageCoordinator
    e.coordinator=DirectorImageCoordinator(e.r.service,e.manager,e.broker,e.s.runtime)
    again=adopt(e,request)
    assert again['replayed'] and again['historical']
    assert e.r.service.creative.get(e.r.nid,e.r.scope,e.draft['id'])==document
    changed=deepcopy(request); changed['note']='Different text'
    with pytest.raises(ValueError,match='REQUEST_REUSED'): adopt(e,changed)
    assert e.persistence.get(job.id)==saved and e.s.events['post']==1


@pytest.mark.parametrize('change',['unconfirmed','negative','terminal','request_reuse'])
def test_declaration_rejects_invalid_or_changed_input(lane,change):
    e=lane; _,_,body=completed(e)
    if change=='unconfirmed':body['confirmed_declaration']=False
    elif change=='negative':body['declared_microusd']=-1
    elif change=='terminal':body['reviewed_terminal_digest']='a'*64
    else:
        declare(e,body);body['declared_microusd']=1
    with pytest.raises(ValueError):declare(e,body)


@pytest.mark.parametrize('change',['authority','target','source','accounting','selection','proof'])
def test_adoption_fresh_guards_and_strict_human_input(lane,change):
    e=lane;_,_,body=completed(e);declare(e,body);request=adoption(review(e))
    if change=='authority':e.active['yes']=False
    elif change=='target':request['target']['version']+=1
    elif change=='source':
        with e.r.service._asset_scope(e.r.nid,e.r.scope):e.r.assets.delete(e.asset['id'])
    elif change=='accounting':request['reviewed_accounting_digest']='a'*64
    elif change=='selection':request['selected_suggestions']=[False]
    else:request['server_proof']={'forged':True}
    with pytest.raises(Exception):adopt(e,request)
    assert e.r.service.creative.get(e.r.nid,e.r.scope,e.draft['id'])==e.draft


def test_concurrent_identical_adoptions_commit_one_revision(lane):
    e=lane;_,_,body=completed(e);declare(e,body);request=adoption(review(e))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:adopt(e,request),range(2)))
    assert sorted(r['replayed'] for r in results)==[False,True]
    document=e.r.service.creative.get(e.r.nid,e.r.scope,e.draft['id'])
    assert document['version']==e.draft['version']+1 and len(document['director_notes'])==1


def test_lost_adoption_commit_ack_replays_without_second_revision(lane,monkeypatch):
    from contextlib import contextmanager
    e=lane;_,_,body=completed(e);declare(e,body);request=adoption(review(e))
    original=e.coordinator.store.store.transaction
    @contextmanager
    def lost(*args,**kwargs):
        with original(*args,**kwargs) as state:yield state
        raise RuntimeError('lost acknowledgement')
    with monkeypatch.context() as m:
        m.setattr(e.coordinator.store.store,'transaction',lost)
        with pytest.raises(RuntimeError,match='lost acknowledgement'):adopt(e,request)
    result=adopt(e,request)
    assert result['replayed']
    assert e.r.service.creative.get(e.r.nid,e.r.scope,e.draft['id'])['version']==e.draft['version']+1


def test_positive_declared_cost_is_unmeasured_and_generic_reconcile_stays_blocked(lane):
    e=lane;_,saved,body=completed(e)
    ledger=saved[FIELD]['accounting']
    with pytest.raises(ValueError,match='IMAGE_RECONCILIATION_OWNER_REQUIRED'):
        e.broker.reconcile(e.r.nid,e.r.scope,e.r.actor,ledger['id'],{
            'expected_version':ledger['version'],'actual_microusd':0,
            'upstream_terminal_confirmed':True,'evidence_note':'Cannot bypass IMAGE owner.'})
    body['declared_microusd']=123
    row=declare(e,body)
    assert row['actual_microusd']==123 and row['accounted_microusd']==123
    assert row['measurement_verified'] is False
    assert review(e)['accounting']['declared_microusd']==123


def test_revocation_after_review_never_changes_draft(lane):
    e=lane;_,_,body=completed(e);declare(e,body);request=adoption(review(e))
    calls={'n':0}
    def guard():
        calls['n']+=1
        if calls['n']>=5:raise PermissionError('revoked')
    with pytest.raises(PermissionError):
        e.coordinator.adopt(e.r.nid,e.r.scope,e.r.actor,e.row['id'],request,host=e.host,guard=guard)
    assert e.r.service.creative.get(e.r.nid,e.r.scope,e.draft['id'])==e.draft


def test_existing_broker_recovery_projection_labels_human_declaration(lane):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.experimental.model_broker_api import create_model_broker_router
    e=lane;_,saved,body=completed(e);declare(e,body)
    app=FastAPI()
    app.include_router(create_model_broker_router(e.broker,
        lambda *_args:(e.r.actor,e.r.scope),lambda *_args:None,
        lambda *_args:e.host.guard(),manager=e.manager))
    response=TestClient(app).get('/novels/'+e.r.nid+'/experimental/model-broker/jobs/'+saved[FIELD]['accounting']['id'])
    assert response.status_code==200,response.text
    result=response.json()
    assert result['ledger']['measurement_verified'] is False
    assert result['ledger']['evidence_kind']=='HUMAN_DECLARED_LOCAL_COST'
    assert result['job']['content_available'] is False


@pytest.mark.parametrize('change',['history','route','measurement','amount'])
def test_changed_ledger_evidence_blocks_review_and_adoption(lane,change):
    e=lane;_,saved,body=completed(e);declare(e,body);request=adoption(review(e))
    with e.r.raw_store.transaction(e.r.nid,e.r.scope) as state:
        row=state['collections'][e.broker.LEDGER][saved[FIELD]['accounting']['id']]
        if change=='history':row['history']=[]
        elif change=='route':row['provider_id']='other'
        elif change=='measurement':row['measurement_verified']=True
        else:row['actual_microusd']=17
    with pytest.raises(ValueError):review(e)
    with pytest.raises(ValueError):adopt(e,request)
    assert e.r.service.creative.get(e.r.nid,e.r.scope,e.draft['id'])==e.draft


@pytest.mark.parametrize('confirmation',[False,1,'true'])
def test_human_adoption_requires_explicit_boolean_true(lane,confirmation):
    e=lane;_,_,body=completed(e);declare(e,body);request=adoption(review(e))
    request['human_review_confirmed']=confirmation
    with pytest.raises(ValueError):adopt(e,request)
    assert e.r.service.creative.get(e.r.nid,e.r.scope,e.draft['id'])==e.draft
