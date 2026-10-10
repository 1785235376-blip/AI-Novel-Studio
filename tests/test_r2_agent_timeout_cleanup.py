from types import SimpleNamespace
from threading import Event
import pytest
from app.services.agent_job_service import AgentJobService


def test_deleted_job_timer_does_not_raise_or_recreate_any_record():
    writes=[]
    def missing(_): raise KeyError('synthetic-deleted-job')
    service=AgentJobService(SimpleNamespace(get=missing,save=writes.append),None,None)
    service.cancellations['synthetic-deleted-job']=Event()
    assert service._timeout('synthetic-deleted-job') is None
    assert writes==[] and 'synthetic-deleted-job' not in service.cancellations


def test_timeout_does_not_swallow_database_errors():
    def unavailable(_): raise RuntimeError('synthetic database unavailable')
    service=AgentJobService(SimpleNamespace(get=unavailable),None,None)
    with pytest.raises(RuntimeError,match='database unavailable'):
        service._timeout('synthetic-job')


def test_completed_async_job_disposes_scheduled_timer(monkeypatch):
    # The lifecycle itself can be checked without a repository or provider.
    row={'id':'synthetic','status':'QUEUED','operation':'AGENT_TASK','timeout_seconds':120}
    class Store:
        def get(self,_):return dict(row)
    service=AgentJobService(Store(),None,None)
    completed=Event();scheduled=[]
    class Timer:
        def __init__(self,*_args,**_kwargs):self.cancelled=False;scheduled.append(self)
        def start(self):pass
        def cancel(self):self.cancelled=True
    monkeypatch.setattr('app.services.agent_job_service.threading.Timer',Timer)
    def execute(*_):row['status']='COMPLETED';completed.set();return dict(row)
    monkeypatch.setattr(service,'execute',execute)
    service.start('synthetic')
    assert completed.wait(2)
    # Wait for the async wrapper finally without a timing-sensitive sleep.
    import time
    deadline=time.monotonic()+2
    while service._timers and time.monotonic()<deadline:time.sleep(.001)
    assert scheduled and scheduled[0].cancelled and not service._timers


def test_cancel_disposes_timer_and_does_not_recreate_terminal_state():
    row={'id':'synthetic','status':'WORKING','operation':'AGENT_TASK'}
    class Store:
        def get(self,_):return dict(row)
        def save(self,value):row.update(value)
    service=AgentJobService(Store(),None,None)
    calls=[];service._timers['synthetic']=SimpleNamespace(cancel=lambda:calls.append('cancel'))
    result=service.cancel('synthetic')
    assert result['status']=='CANCELLED' and calls==['cancel'] and not service._timers
