"""Real native OCR to original Research review; no public API wiring claim."""
from copy import deepcopy
from threading import Event
from types import SimpleNamespace
import pytest
from app.experimental.research_native_ocr import NativeResearchOCRCoordinator
from test_v2_independent_workspace import rig
from test_native_ocr_broker_additive import configured
from test_research_ocr_job_persistence_additive import reopen
from test_research_ocr_job_execution_additive import wait


def setup(e,monkeypatch):
    c=configured(e,monkeypatch);c.manager=reopen(e)
    c.controller=NativeResearchOCRCoordinator(c.research,c.broker,c.manager)
    c.analysis=c.research.create_analysis(e.nid,e.scope,e.actor,
        {'source_id':c.row['id'],'source_version':1,'operation':'OCR','pages':[1]},guard=lambda:None)
    return c


def preview(e,c):
    return c.controller.preview(e.nid,e.scope,e.actor,c.analysis['id'],
        {'expected_version':c.analysis['version'],'provider_id':'native-ocr','model_id':'eng','language':'eng'},guard=lambda:None)


def dispatch(e,c,row,key='one'):
    body={'expected_version':row['version'],'reviewed_preview_digest':row['native_ocr_preview']['reviewed_preview_digest'],
          'idempotency_key':key}
    answer=c.controller.dispatch(e.nid,e.scope,e.actor,row['id'],body,guard=lambda:None)
    job=c.manager.get(answer['native_ocr_execution']['generation_id'])
    wait(SimpleNamespace(job=job))
    return body,job,c.research.analysis_job(e.nid,e.scope,e.actor,row['id'])


def test_actual_native_result_enters_original_review_and_is_idempotent(rig,monkeypatch):
    c=setup(rig,monkeypatch);original=c.research.original(rig.nid,rig.scope,rig.actor,c.row['id'])
    ready=preview(rig,c);body,job,result=dispatch(rig,c,ready)
    assert job.status=='COMPLETED' and result['status']=='REVIEW_REQUIRED'
    assert result['result']['blocks'][0]['text']=='STUDIO OCR 123'
    assert result['result']['verification']=='CONTRACT_VERIFIED' and result['automatic_canon'] is False
    assert result['result']['blocks'][0]['citation']['source_id']==c.row['id']
    reviewed=c.research.analysis_action(rig.nid,rig.scope,rig.actor,result['id'],'review',result['version'],guard=lambda:None)
    assert reviewed['status']=='REVIEWED' and reviewed['reviewed_by']==rig.actor
    replay=c.controller.dispatch(rig.nid,rig.scope,rig.actor,ready['id'],body,guard=lambda:None)
    assert replay['status']=='REVIEWED' and len(c.manager.jobs)==1
    assert len(c.broker.ledger(rig.nid,rig.scope,rig.actor))==1
    assert c.research.original(rig.nid,rig.scope,rig.actor,c.row['id'])==original
    assert rig.chapters.list(rig.nid)==[]


def test_wrong_preview_and_other_actor_do_not_run(rig,monkeypatch):
    c=setup(rig,monkeypatch);ready=preview(rig,c)
    with pytest.raises(ValueError):c.controller.dispatch(rig.nid,rig.scope,rig.actor,ready['id'],
        {'expected_version':ready['version'],'reviewed_preview_digest':'0'*64,'idempotency_key':'bad'},guard=lambda:None)
    with pytest.raises(FileNotFoundError):c.controller.preview(rig.nid,rig.scope,'other',ready['id'],
        {'expected_version':ready['version'],'provider_id':'native-ocr','model_id':'eng','language':'eng'},guard=lambda:None)
    assert c.manager.jobs=={} and c.broker.ledger(rig.nid,rig.scope,rig.actor)==[]


def test_cancel_claimed_task_keeps_native_metadata_hidden_and_settles(rig,monkeypatch):
    c=setup(rig,monkeypatch);ready=preview(rig,c);entered,release=Event(),Event();original=c.provider.recognize_image
    def paused(request):
        entered.set();assert release.wait(10);return original(request)
    monkeypatch.setattr(c.provider,'recognize_image',paused)
    answer=c.controller.dispatch(rig.nid,rig.scope,rig.actor,ready['id'],
        {'expected_version':ready['version'],'reviewed_preview_digest':ready['native_ocr_preview']['reviewed_preview_digest'],'idempotency_key':'cancel'},guard=lambda:None)
    job=c.manager.get(answer['native_ocr_execution']['generation_id'])
    try:
        assert entered.wait(10)
        cancelled=c.research.analysis_action(rig.nid,rig.scope,rig.actor,answer['id'],'cancel',answer['version'],guard=lambda:None)
        assert cancelled['status']=='CANCELLED'
        assert 'native_ocr_preview' not in cancelled and 'native_ocr_execution' not in cancelled
    finally:release.set()
    wait(SimpleNamespace(job=job))
    assert job.status=='CANCELLED' and job.output==''
    assert c.broker.ledger(rig.nid,rig.scope,rig.actor)[0]['status']=='SETTLED'


def test_tampered_derived_citation_cannot_be_reviewed(rig,monkeypatch):
    c=setup(rig,monkeypatch);ready=preview(rig,c);_,job,result=dispatch(rig,c,ready)
    from app.experimental.planning import digest
    with rig.raw_store.transaction(rig.nid,rig.scope) as state:
        row=state['collections']['research_analysis_jobs'][result['id']]
        row['result']['blocks'][0]['citation']['source_id']='forged-source'
        row['result_digest']=digest(row['result'])
    before=deepcopy(rig.raw_store.read(rig.nid,rig.scope))
    with pytest.raises(ValueError,match='DURABLE_RESULT_MISMATCH'):
        c.research.analysis_action(rig.nid,rig.scope,rig.actor,result['id'],'review',result['version'],guard=lambda:None)
    assert rig.raw_store.read(rig.nid,rig.scope)==before


def test_completed_receipt_reopens_for_review_without_execution_authority(rig,monkeypatch):
    from app.experimental.research_library import ResearchLibraryService
    from app.experimental.model_broker import ModelBrokerService
    c=setup(rig,monkeypatch);ready=preview(rig,c);body,job,result=dispatch(rig,c,ready)
    research=ResearchLibraryService(rig.raw_store,rig.novels,rig.chapters,historical_inspection=True)
    broker=ModelBrokerService(rig.raw_store,rig.novels,rig.chapters,runtime=c.runtime)
    manager=reopen(rig);controller=NativeResearchOCRCoordinator(research,broker,manager)
    restored=research.analysis_job(rig.nid,rig.scope,rig.actor,result['id'])
    assert restored==result
    reviewed=research.analysis_action(rig.nid,rig.scope,rig.actor,result['id'],'review',result['version'],guard=lambda:None)
    assert reviewed['status']=='REVIEWED'
    assert controller.dispatch(rig.nid,rig.scope,rig.actor,result['id'],body,guard=lambda:None)['status']=='REVIEWED'
    passive=manager.get(job.id)
    with pytest.raises(ValueError,match='RESEARCH_OCR_EXECUTION_UNAVAILABLE'):
        manager._start_research_ocr_job(passive)
    assert len(manager.jobs)==1 and len(broker.ledger(rig.nid,rig.scope,rig.actor))==1


def test_source_revocation_after_completion_prevents_review(rig,monkeypatch):
    c=setup(rig,monkeypatch);ready=preview(rig,c);_,job,result=dispatch(rig,c,ready)
    c.research.transition_source(rig.nid,rig.scope,rig.actor,c.row['id'],1,'revoke',guard=lambda:None)
    before=deepcopy(rig.raw_store.read(rig.nid,rig.scope))
    with pytest.raises((ValueError,FileNotFoundError)):
        c.research.analysis_action(rig.nid,rig.scope,rig.actor,result['id'],'review',result['version'],guard=lambda:None)
    assert rig.raw_store.read(rig.nid,rig.scope)==before


def test_export_requires_current_human_review_and_exact_receipt(rig,monkeypatch):
    c=setup(rig,monkeypatch);ready=preview(rig,c);_,job,result=dispatch(rig,c,ready)
    with pytest.raises(ValueError,match='REVIEWED_EXPORT_REQUIRED'):
        c.controller.export_reviewed(rig.nid,rig.scope,rig.actor,result['id'],result['version'],result['result_digest'])
    reviewed=c.research.analysis_action(rig.nid,rig.scope,rig.actor,result['id'],'review',result['version'],guard=lambda:None)
    before=deepcopy(rig.raw_store.read(rig.nid,rig.scope))
    assert c.controller.export_reviewed(rig.nid,rig.scope,rig.actor,reviewed['id'],reviewed['version'],reviewed['result_digest'])==b'STUDIO OCR 123\n'
    with pytest.raises(ValueError,match='REVIEWED_EXPORT_REQUIRED'):
        c.controller.export_reviewed(rig.nid,rig.scope,rig.actor,reviewed['id'],reviewed['version'],'0'*64)
    with pytest.raises(FileNotFoundError):
        c.controller.export_reviewed(rig.nid,rig.scope,'other',reviewed['id'],reviewed['version'],reviewed['result_digest'])
    assert rig.raw_store.read(rig.nid,rig.scope)==before


def test_restart_projection_reports_interruption_without_releasing_hold(rig,monkeypatch):
    from app.experimental.research_library import ResearchLibraryService
    c=setup(rig,monkeypatch);ready=preview(rig,c)
    def interrupted_start(job):
        job.status='QUEUED';c.manager.jobs[job.id]=job;c.manager._persist(job)
    monkeypatch.setattr(c.manager,'_start_research_ocr_job',interrupted_start)
    row=c.controller.dispatch(rig.nid,rig.scope,rig.actor,ready['id'],
        {'expected_version':ready['version'],'reviewed_preview_digest':ready['native_ocr_preview']['reviewed_preview_digest'],'idempotency_key':'restart'},guard=lambda:None)
    assert row['status']=='RUNNING'
    research=ResearchLibraryService(rig.raw_store,rig.novels,rig.chapters,historical_inspection=True)
    manager=reopen(rig);NativeResearchOCRCoordinator(research,c.broker,manager)
    before=deepcopy(rig.raw_store.read(rig.nid,rig.scope))
    projected=research.analysis_job(rig.nid,rig.scope,rig.actor,row['id'])
    assert projected['status']=='INTERRUPTED' and projected['persisted_status']=='RUNNING'
    assert projected['recovery']['automatic_resume'] is False
    assert projected['recovery']['budget_hold_retained'] is True
    assert projected['recovery']['explicit_host_recovery_required'] is True
    assert rig.raw_store.read(rig.nid,rig.scope)==before
    assert c.broker.ledger(rig.nid,rig.scope,rig.actor)[0]['status']=='RESERVED'
    assert manager.get(row['native_ocr_execution']['generation_id']).status=='FAILED'
