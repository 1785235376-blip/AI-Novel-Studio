"""Original worker completion handoff only; no claim of Research publication."""
import pytest
from test_v2_independent_workspace import rig
from test_research_ocr_job_execution_additive import setup, wait


def test_handoff_observes_settled_persisted_result_once_and_detached(rig,monkeypatch):
    holder={}; received=[]
    def result(value):
        e=holder['value'];saved=e.manager.persistence.get(e.job.id)
        assert saved['status']=='COMPLETED' and saved['terminal_hook_status']=='COMPLETED'
        assert saved['output']==value.text
        received.append(value.text)
        value.receipt['review_required']=False
    e=setup(rig,monkeypatch,on_result=result);holder['value']=e
    e.manager._start_research_ocr_job(e.job);wait(e)
    assert received==[e.job.output]
    assert e.job.research_ocr_execution_authority.result().receipt['review_required'] is True
    assert e.calls==['dispatch','terminal']
    with pytest.raises(ValueError):e.manager._run(e.job)
    assert len(received)==1


def test_failed_handoff_does_not_leave_live_completion_or_replay(rig,monkeypatch):
    calls=[]
    def result(_):calls.append(True);raise OSError('synthetic review write failure')
    e=setup(rig,monkeypatch,on_result=result);e.manager._start_research_ocr_job(e.job)
    wait(e)
    assert e.job.status=='FAILED' and e.job.output=='' and calls==[True]
    assert e.job.error_code=='RESEARCH_OCR_TERMINAL_UNCONFIRMED'
    assert e.manager.persistence.get(e.job.id)['status']=='FAILED'
    with pytest.raises(ValueError):e.job.research_ocr_execution_authority.result()
    assert e.calls==['dispatch','terminal'] and e.provider.calls==1


def test_cancelled_inference_never_calls_result_handoff(rig,monkeypatch):
    calls=[];e=setup(rig,monkeypatch,on_result=lambda value:calls.append(value))
    e.provider.mutate=lambda _:e.job.cancelled.set()
    e.manager._start_research_ocr_job(e.job);wait(e)
    assert e.job.status=='CANCELLED' and calls==[]


def test_source_revoked_by_handoff_retires_live_result(rig,monkeypatch):
    holder={}
    def result(_):
        e=holder['value']
        e.service.transition_source(rig.nid,rig.scope,rig.actor,e.row['id'],1,'revoke',guard=lambda:None)
    e=setup(rig,monkeypatch,on_result=result);holder['value']=e;e.manager._start_research_ocr_job(e.job)
    wait(e)
    assert e.job.status=='FAILED' and e.job.output==''
    assert e.manager.persistence.get(e.job.id)['status']=='FAILED'


def test_pending_publication_is_not_available_to_another_thread(rig,monkeypatch):
    from threading import Event
    entered, release=Event(),Event()
    def result(_):
        entered.set()
        assert release.wait(10)
    e=setup(rig,monkeypatch,on_result=result);e.manager._start_research_ocr_job(e.job)
    try:
        assert entered.wait(10)
        assert not e.job.research_ocr_execution_authority.finished
        with pytest.raises(ValueError,match='PUBLICATION_PENDING'):
            e.job.research_ocr_execution_authority.result()
    finally:release.set()
    wait(e)
    assert e.job.status=='COMPLETED'
    assert e.job.research_ocr_execution_authority.result().text==e.job.output
