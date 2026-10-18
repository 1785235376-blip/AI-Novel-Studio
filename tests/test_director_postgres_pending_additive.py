"""Real PostgreSQL original-owner Director pending lifecycle; mocked wire only."""
import pytest
from creative_director_postgres_fixture_additive import pg_lifecycle
from test_v2_independent_director_adoption import board,review_body
from test_director_durable_pending_review import publish,prepare,read,review,fresh_host
from app.creative.director_terminal_evidence import FIELD
pytestmark=pytest.mark.postgres_backend_only


def restart(e):
    from app.jobs import JobManager
    from app.creative.service import CreativeService
    from app.creative.generation import DirectorModelCoordinator
    from app.experimental.store import ExperimentalStore
    from app.repositories.postgres.generation import PostgresGenerationRepository
    from app.services.generation_service import GenerationService
    e.raw=ExperimentalStore(e.root,'postgres',e.url)
    e.documents=CreativeService(e.raw,e.novels,e.forbidden)
    from app.experimental.model_broker import ModelBrokerService
    e.broker=ModelBrokerService(e.raw,e.novels,e.forbidden,runtime=e.runtime)
    e.persistence=GenerationService(PostgresGenerationRepository(e.database))
    e.manager=JobManager(e.persistence,e.forbidden,e.forbidden,e.forbidden,memory_extractor=e.forbidden,snapshot_required=True,collaboration_updates=e.forbidden)
    e.coordinator=DirectorModelCoordinator(e.documents.proposals,e.broker,e.forbidden,e.manager)
    e.documents.proposals.generation=e.coordinator


def test_real_postgres_terminal_pending_review_and_reopen(pg_lifecycle):
    e=board(pg_lifecycle)
    job,body=publish(e)
    saved=e.persistence.get(job.id)
    assert FIELD in saved and saved[FIELD]['consumer_authority'] is False
    assert not (e.root/'runtime/jobs'/f'{job.id}.json').exists()
    restart(e);fresh_host(e)
    candidate=prepare(e,body)
    restart(e);fresh_host(e)
    assert read(e)==candidate
    adopted=review(e,review_body(candidate));draft=adopted['document']
    restart(e)
    assert e.documents.get(e.nid,e.scope,draft['id'])==draft
    assert len(e.requests)==len(e.broker.ledger(e.nid,e.scope,e.actor))==1


def test_expired_result_and_cleared_output_keep_pending_review(pg_lifecycle,monkeypatch):
    from datetime import datetime,timedelta
    import app.jobs as jobs
    import app.creative.generation as generation
    e=board(pg_lifecycle);job,body=publish(e)
    class Expired(datetime):
        @classmethod
        def now(cls,tz=None):return datetime.fromisoformat(job.generation_deadline)+timedelta(seconds=1)
    monkeypatch.setattr(jobs,'datetime',Expired);monkeypatch.setattr(generation,'datetime',Expired)
    restart(e);fresh_host(e);candidate=prepare(e,body)
    saved=e.persistence.get(job.id);evidence=saved.pop(FIELD);saved.update(output='',status='FAILED')
    e.persistence.save(saved)
    assert e.persistence.get(job.id)[FIELD]==evidence
    restart(e);fresh_host(e);assert read(e)==candidate
    adopted=review(e,review_body(candidate));assert adopted['document']['status']=='DRAFT'
    assert len(e.requests)==1


@pytest.mark.parametrize('fault',['host','scope','actor','source','incarnation','route','license','digest'])
def test_postgres_prepare_requires_fresh_authority_and_exact_source(pg_lifecycle,monkeypatch,fault):
    from copy import deepcopy
    from fastapi import HTTPException
    e=board(pg_lifecycle);job,body=publish(e)
    if fault=='host':e.sessions.revoke(e.token)
    elif fault=='scope':e.active=False
    elif fault=='actor':e.ctx.actor='other-author'
    elif fault=='route':e.candidate['model_evidence_fingerprint']='changed'
    elif fault=='license':e.candidate['license_confirmed']=False
    elif fault=='digest':body['terminal_evidence_digest']='0'*64
    elif fault=='incarnation':
        e.novels.delete(e.nid);e.novels.create({'id':e.nid,'title':'Replacement same public id'})
    else:
        with e.raw.transaction(e.nid,e.scope) as state:state['collections'][e.documents.COLLECTION][e.source['id']]['title']='changed'
    before=deepcopy(e.raw.read(e.nid,e.scope))
    with pytest.raises((ValueError,HTTPException,PermissionError,FileNotFoundError,KeyError)):prepare(e,body)
    assert e.raw.read(e.nid,e.scope)==before


def test_generic_saves_cannot_mint_or_replace_evidence(pg_lifecycle):
    from copy import deepcopy
    e=board(pg_lifecycle);job,body=publish(e);before=e.persistence.get(job.id)
    with pytest.raises(ValueError):e.persistence.save(deepcopy(before))
    forged=deepcopy(before);forged['id']='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
    with pytest.raises(ValueError):e.persistence.save(forged)
    with pytest.raises(ValueError):e.persistence.repository._publish_director_terminal(job,object(),before[FIELD])
    assert e.persistence.get(job.id)==before
    with pytest.raises(KeyError):e.persistence.get(forged['id'])


def test_different_original_database_denied_before_admission(pg_lifecycle):
    from app.repositories.postgres.session import Database
    from app.repositories.postgres.generation import PostgresGenerationRepository
    from app.services.generation_service import GenerationService
    from test_v2_independent_director_adoption import preview
    e=board(pg_lifecycle);prepared=preview(e)
    other=Database(e.url.rsplit('/',1)[0]+'/v2_wrong_director_database')
    try:
        e.manager.persistence=GenerationService(PostgresGenerationRepository(other))
        with pytest.raises(ValueError,match='BACKEND_UNSUPPORTED'):
            e.coordinator._dispatch_independent(e.ctx,e.row['id'],{'expected_version':prepared['version'],'reviewed_preview_digest':prepared['model_preview']['preview_digest']},e.guard,host_authority=e.authority,terminal_evidence=True)
        assert not e.manager.jobs and not e.requests
    finally:other.engine.dispose()


def test_independent_coordinators_concurrent_prepare_and_review(pg_lifecycle):
    from copy import deepcopy
    from types import SimpleNamespace
    from concurrent.futures import ThreadPoolExecutor
    from test_director_durable_pending_review import DENIALS
    e=board(pg_lifecycle);job,body=publish(e);other=SimpleNamespace(**vars(e));restart(other)
    before=e.raw.read(e.nid,e.scope)['collections'][e.documents.proposals.COLLECTION][e.row['id']]['version']
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda owner:prepare(owner,deepcopy(body)),[e,other]))
    assert results[0]==results[1]
    assert e.raw.read(e.nid,e.scope)['collections'][e.documents.proposals.COLLECTION][e.row['id']]['version']==before+1
    def adopt(owner):
        try:return review(owner,review_body(results[0]))
        except DENIALS:return None
    with ThreadPoolExecutor(max_workers=2) as pool:adopted=list(pool.map(adopt,[e,other]))
    assert sum(row is not None for row in adopted)==1
    assert len(e.raw.read(e.nid,e.scope)['collections'][e.documents.COLLECTION])==3
    assert len(e.requests)==1


def test_clear_before_last_row_leaf_rolls_back_pending(pg_lifecycle,monkeypatch):
    from contextlib import contextmanager
    from copy import deepcopy
    e=board(pg_lifecycle);job,body=publish(e);repository=e.persistence.repository;original=repository._director_snapshot_leaf
    @contextmanager
    def clear_then_lock(jid):
        saved=repository.get(jid);evidence=saved.pop(FIELD);saved.update(output='',status='FAILED');repository.save(saved)
        assert repository.get(jid)[FIELD]==evidence
        with original(jid) as locked:yield locked
    monkeypatch.setattr(repository,'_director_snapshot_leaf',clear_then_lock)
    before=deepcopy(e.raw.read(e.nid,e.scope))
    with pytest.raises(ValueError,match='OUTPUT_CHANGED'):prepare(e,body)
    assert e.raw.read(e.nid,e.scope)==before and repository.get(job.id)['output']==''


def test_original_http_actions_restore_and_reconcile_on_postgres(pg_lifecycle):
    import json
    from copy import deepcopy
    from creative_director_execution_fixture import wait
    from test_v2_independent_director_adoption import output
    from test_director_observation_transport_additive import mounted
    from test_director_model_transport_additive import preview_request
    e=board(pg_lifecycle);e.wire_text=json.dumps(output(e));m=mounted(e,actions=True)
    response=m.client.post(m.url+'/preview',headers=m.headers,json=preview_request(e));assert response.status_code==200,response.text
    preview=response.json()['receipt'];assert not e.requests
    response=m.client.post(m.url+'/dispatch',headers=m.headers,json={'expected_version':preview['version'],'reviewed_preview_digest':preview['reviewed_preview_digest']})
    assert response.status_code in {200,409},response.text
    assert len(e.manager.jobs)==1;job=wait(e,next(iter(e.manager.jobs.values())));assert job.status=='COMPLETED'
    response=m.client.get(m.url+'/status',headers=m.headers);assert response.status_code==200,response.text
    status=response.json()['receipt'];assert status['phase']=='COMPLETED'
    response=m.client.post(m.url+'/prepare-review',headers=m.headers,json={'expected_version':status['version'],'terminal_evidence_digest':status['terminal_evidence_digest']});assert response.status_code==200,response.text
    candidate=response.json()['receipt'];human=review_body(candidate);human['director_notes'][0]['note']='Human PostgreSQL HTTP review'
    response=m.client.post(m.url+'/review',headers=m.headers,json=human);assert response.status_code==200,response.text
    receipt=response.json()['receipt'];before=deepcopy(e.raw.read(e.nid,e.scope))
    assert m.client.post(m.url+'/review',headers=m.headers,json=human).status_code==409
    restart(e);fresh_host(e);m=mounted(e,actions=True)
    response=m.client.post(m.url+'/reconcile-review',headers=m.headers,json=human);assert response.status_code==200,response.text
    assert response.json()['receipt']==receipt
    assert m.client.get(m.url+'/adopted-draft',headers=m.headers).json()['receipt']==receipt
    assert e.raw.read(e.nid,e.scope)==before and len(e.requests)==1
    assert e.documents.get(e.nid,e.scope,receipt['document']['document_id'])['director_notes'][0]['note']=='Human PostgreSQL HTTP review'
    assert 'host_principal' not in response.text and 'reservation_id' not in response.text
    e.sessions.revoke(e.token)
    denied=m.client.get(m.url+'/adopted-draft',headers=m.headers)
    assert denied.status_code in {401,403,404} and 'Human PostgreSQL HTTP review' not in denied.text


@pytest.mark.parametrize('after_commit',[False,True])
def test_terminal_transaction_fault_has_truthful_durable_outcome(pg_lifecycle,monkeypatch,after_commit):
    from sqlalchemy.orm import Session
    from app.repositories.postgres.models import GenerationJobModel
    e=board(pg_lifecycle);repository=e.persistence.repository;attempts=[]
    if after_commit:
        original=repository._publish_director_terminal
        def uncertain(*args):
            attempts.append('after')
            original(*args)
            raise OSError('Synthetic acknowledgment loss after PostgreSQL commit')
        monkeypatch.setattr(repository,'_publish_director_terminal',uncertain)
    else:
        original_flush=Session.flush
        def failing_flush(session,*args,**kwargs):
            if any(isinstance(row,GenerationJobModel) and FIELD in (row.request or {}).get('_repository_payload',{}) for row in session.dirty):
                attempts.append('before')
                raise OSError('Synthetic failure before PostgreSQL terminal commit')
            return original_flush(session,*args,**kwargs)
        monkeypatch.setattr(Session,'flush',failing_flush)
    import json
    from creative_director_execution_fixture import wait,raw_proposal
    from test_v2_independent_director_adoption import output,preview
    from app.creative.director_terminal_evidence import digest
    e.wire_text=json.dumps(output(e));prepared=preview(e)
    receipt=e.coordinator._dispatch_independent(e.ctx,e.row['id'],{'expected_version':prepared['version'],'reviewed_preview_digest':prepared['model_preview']['preview_digest']},e.guard,host_authority=e.authority,terminal_evidence=True)
    job=wait(e,e.manager.get(receipt['model_execution']['job_id']));saved=e.persistence.get(job.id)
    assert len(attempts)==1
    assert job.status=='FAILED' and job.output=='' and job.creative_execution_authority.publication_state=='UNKNOWN'
    body={'expected_version':raw_proposal(e)['version'],'terminal_evidence_digest':digest(saved.get(FIELD))}
    assert (FIELD in saved)==after_commit
    if after_commit:
        candidate=prepare(e,body);assert candidate['director_notes']
        assert prepare(e,body)==candidate
    else:
        with pytest.raises(ValueError):prepare(e,body)
    assert len(e.requests)==1
