"""Explicit stopped-executor recovery over original File/PostgreSQL owners."""
from contextlib import contextmanager
from copy import deepcopy
from threading import Event
from types import SimpleNamespace
import pytest
from app.experimental.research_library import ResearchLibraryService
from app.experimental.research_native_ocr import NativeResearchOCRCoordinator
from test_v2_independent_workspace import rig
from test_research_native_ocr_coordinator_additive import setup,preview,dispatch
from test_research_ocr_job_persistence_additive import reopen
from test_research_ocr_job_execution_additive import wait


def stopped(e,monkeypatch):
    c=setup(e,monkeypatch);ready=preview(e,c)
    def queued(job):
        job.status='QUEUED';c.manager.jobs[job.id]=job;c.manager._persist(job)
    monkeypatch.setattr(c.manager,'_start_research_ocr_job',queued)
    claimed=c.controller.dispatch(e.nid,e.scope,e.actor,ready['id'],
        {'expected_version':ready['version'],'reviewed_preview_digest':ready['native_ocr_preview']['reviewed_preview_digest'],'idempotency_key':'interrupted'},guard=lambda:None)
    c.research=ResearchLibraryService(e.raw_store,e.novels,e.chapters,historical_inspection=True)
    c.manager=reopen(e);c.controller=NativeResearchOCRCoordinator(c.research,c.broker,c.manager)
    c.claimed=claimed
    ledger=c.broker.ledger(e.nid,e.scope,e.actor)[0]
    body={'expected_version':claimed['version'],'reservation_version':ledger['version'],
        'original_executor_stopped_confirmed':True,'evidence_note':'Original executor was explicitly stopped; do not replay.'}
    return c,body


def test_explicit_recovery_releases_only_zero_fee_hold_and_is_idempotent(rig,monkeypatch):
    c,body=stopped(rig,monkeypatch)
    monkeypatch.setattr(c.provider,'recognize_image',lambda request:pytest.fail('Recovery must not infer'))
    original=c.research.original(rig.nid,rig.scope,rig.actor,c.row['id'])
    assert c.broker.budget(rig.nid,rig.scope)['inflight']==1
    result=c.controller.recover(rig.nid,rig.scope,rig.actor,c.claimed['id'],body,guard=lambda:None)
    assert result['status']=='FAILED' and result['automatic_replay'] is False
    assert set(result)=={'id','version','status','recovery_recorded','automatic_resume','automatic_replay'}
    ledger=c.broker.ledger(rig.nid,rig.scope,rig.actor)[0]
    assert ledger['status']=='RECONCILED' and ledger['actual_microusd']==0
    assert ledger['cost_state']=='KNOWN_LOCAL_PROVIDER_ZERO' and c.broker.budget(rig.nid,rig.scope)['inflight']==0
    after=deepcopy(rig.raw_store.read(rig.nid,rig.scope))
    assert c.controller.recover(rig.nid,rig.scope,rig.actor,c.claimed['id'],body,guard=lambda:None)==result
    assert rig.raw_store.read(rig.nid,rig.scope)==after
    assert c.research.original(rig.nid,rig.scope,rig.actor,c.row['id'])==original
    assert len(c.manager.jobs)==1 and next(iter(c.manager.jobs.values())).status=='FAILED'


@pytest.mark.parametrize('confirmation',[False,1])
def test_recovery_requires_literal_true_without_mutation(rig,monkeypatch,confirmation):
    c,body=stopped(rig,monkeypatch);before=deepcopy(rig.raw_store.read(rig.nid,rig.scope))
    with pytest.raises(ValueError):
        c.controller.recover(rig.nid,rig.scope,rig.actor,c.claimed['id'],dict(body,original_executor_stopped_confirmed=confirmation),guard=lambda:None)
    assert rig.raw_store.read(rig.nid,rig.scope)==before


def test_live_executor_cannot_be_reconciled_even_with_confirmation(rig,monkeypatch):
    c=setup(rig,monkeypatch);ready=preview(rig,c);entered,release=Event(),Event();original=c.provider.recognize_image
    def paused(request):
        entered.set();assert release.wait(10);return original(request)
    monkeypatch.setattr(c.provider,'recognize_image',paused)
    row=c.controller.dispatch(rig.nid,rig.scope,rig.actor,ready['id'],
        {'expected_version':ready['version'],'reviewed_preview_digest':ready['native_ocr_preview']['reviewed_preview_digest'],'idempotency_key':'live'},guard=lambda:None)
    job=c.manager.get(row['native_ocr_execution']['generation_id'])
    try:
        assert entered.wait(10);ledger=c.broker.ledger(rig.nid,rig.scope,rig.actor)[0]
        before=deepcopy(rig.raw_store.read(rig.nid,rig.scope))
        with pytest.raises(ValueError,match='EXECUTOR_STILL_ACTIVE'):
            c.controller.recover(rig.nid,rig.scope,rig.actor,row['id'],{'expected_version':row['version'],
                'reservation_version':ledger['version'],'original_executor_stopped_confirmed':True,'evidence_note':'Not sufficient while live'},guard=lambda:None)
        assert rig.raw_store.read(rig.nid,rig.scope)==before
    finally:release.set()
    wait(SimpleNamespace(job=job));assert job.status=='COMPLETED'


def test_retry_after_research_commit_failure_does_not_reconcile_twice(rig,monkeypatch):
    c,body=stopped(rig,monkeypatch);original=rig.raw_store.transaction
    @contextmanager
    def failed(nid,scope):
        with original(nid,scope) as state:
            before=deepcopy(state['collections']['research_analysis_jobs'][c.claimed['id']])
            yield state
            after=state['collections']['research_analysis_jobs'][c.claimed['id']]
            if not before['native_ocr_execution'].get('recovery_id') and after['native_ocr_execution'].get('recovery_id'):
                raise OSError('Injected original Research commit failure')
    monkeypatch.setattr(rig.raw_store,'transaction',failed)
    with pytest.raises(OSError,match='Injected'):
        c.controller.recover(rig.nid,rig.scope,rig.actor,c.claimed['id'],body,guard=lambda:None)
    ledger=c.broker.ledger(rig.nid,rig.scope,rig.actor)[0];assert ledger['status']=='RECONCILED'
    assert c.research.get(rig.nid,rig.scope,'research_analysis_jobs',c.claimed['id'])['status']=='RUNNING'
    monkeypatch.setattr(rig.raw_store,'transaction',original)
    result=c.controller.recover(rig.nid,rig.scope,rig.actor,c.claimed['id'],dict(body,reservation_version=ledger['version']),guard=lambda:None)
    assert result['status']=='FAILED'
    assert c.broker.ledger(rig.nid,rig.scope,rig.actor)[0]==ledger


def test_old_actor_or_recreated_project_cannot_reconcile_old_hold(rig,monkeypatch):
    c,body=stopped(rig,monkeypatch);old=c.broker.ledger(rig.nid,rig.scope,rig.actor)[0]
    before=deepcopy(rig.raw_store.read(rig.nid,rig.scope))
    with pytest.raises(FileNotFoundError):c.controller.recover(rig.nid,rig.scope,'other',c.claimed['id'],body,guard=lambda:None)
    assert rig.raw_store.read(rig.nid,rig.scope)==before
    rig.novels.delete(rig.nid);rig.create_project(nid=rig.nid)
    fresh=setup(rig,monkeypatch);ready=preview(rig,fresh)
    with pytest.raises((FileNotFoundError,ValueError)):
        c.controller.recover(rig.nid,rig.scope,rig.actor,c.claimed['id'],body,guard=lambda:None)
    _,job,result=dispatch(rig,fresh,ready,'fresh')
    assert job.status=='COMPLETED' and result['status']=='REVIEW_REQUIRED'
    assert rig.raw_store.read(rig.nid,rig.scope)['collections'][c.broker.LEDGER][old['id']]==old


def test_mounted_recovery_requires_original_host_authority_before_body(rig,monkeypatch):
    from fastapi import FastAPI,HTTPException
    from fastapi.testclient import TestClient
    from app.experimental.research_library_api import create_research_library_router
    c,body=stopped(rig,monkeypatch)
    def authorize(nid,token,branch,permission):
        if nid!=rig.nid or token not in {'writer','host'} or branch!='current':raise HTTPException(403,'denied')
        return rig.actor,rig.scope
    def host(token):
        if token!='host':raise HTTPException(403,'host required')
    app=FastAPI();app.include_router(create_research_library_router(c.research,authorize,lambda _:None,host))
    path=f'/novels/{rig.nid}/experimental/research-library/analysis/jobs/{c.claimed["id"]}/native-recover'
    before=deepcopy(rig.raw_store.read(rig.nid,rig.scope))
    with TestClient(app) as client:
        rejected=client.post(path,headers={'X-Session-Token':'writer','X-Branch-ID':'current'},content='malformed-json')
        assert rejected.status_code==403 and rig.raw_store.read(rig.nid,rig.scope)==before
        result=client.post(path,headers={'X-Session-Token':'host','X-Branch-ID':'current'},json=body)
        assert result.status_code==200,result.text
        assert result.json()['recovery_recorded'] is True and result.headers['cache-control']=='no-store'
        assert 'request' not in result.json() and 'result' not in result.json()
    assert c.broker.budget(rig.nid,rig.scope)['inflight']==0


def test_revoked_source_recovery_does_not_redisclose_or_reactivate_it(rig,monkeypatch):
    c,body=stopped(rig,monkeypatch)
    c.research.transition_source(rig.nid,rig.scope,rig.actor,c.row['id'],1,'revoke',guard=lambda:None)
    raw=c.research.get(rig.nid,rig.scope,'research_analysis_jobs',c.claimed['id'])
    assert raw['status']=='INVALIDATED'
    result=c.controller.recover(rig.nid,rig.scope,rig.actor,raw['id'],dict(body,expected_version=raw['version']),guard=lambda:None)
    assert result['status']=='INVALIDATED' and 'request' not in result and 'result' not in result
    assert c.broker.budget(rig.nid,rig.scope)['inflight']==0
    with pytest.raises((ValueError,FileNotFoundError)):
        c.research.original(rig.nid,rig.scope,rig.actor,c.row['id'])


def test_cached_job_identity_change_cannot_release_the_original_hold(rig,monkeypatch):
    c,body=stopped(rig,monkeypatch);before=deepcopy(rig.raw_store.read(rig.nid,rig.scope))
    job=c.manager.get(c.claimed['native_ocr_execution']['generation_id']);job.actor_id='other'
    with pytest.raises(ValueError,match='RECOVERY_JOB_MISMATCH'):
        c.controller.recover(rig.nid,rig.scope,rig.actor,c.claimed['id'],body,guard=lambda:None)
    assert rig.raw_store.read(rig.nid,rig.scope)==before
