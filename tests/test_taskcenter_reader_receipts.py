"""Private actual-read receipts preserve default aggregate behavior."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi import HTTPException
from app.experimental.ux import WorkspaceToolsService, TaskReader
from app.experimental.inbox import ReviewContext
from app.experimental.ux import ReadContext

CTX=ReadContext('book',{'mode':'local','novel_id':'book'},'local-author')

def row(rid):return {'id':rid,'novel_id':'book','scope':deepcopy(CTX.scope),'status':'QUEUED','permission_context':deepcopy(CTX.scope)}
def reader(name,callback):return TaskReader(name,name,'history',callback)
def run(svc,**kw):return svc.tasks(CTX,lambda f:None,authorities=('semantic_import','exports'),**kw)


def test_only_selected_actual_instances_and_default_result_identical():
    a=reader('semantic_import',lambda c:[row('a')]);b=reader('exports',lambda c:[row('b')])
    other=reader('media',lambda c:pytest.fail('unselected reader called'))
    svc=WorkspaceToolsService(None,None,None,task_readers=(a,other,b));events=[];auth=[]
    before=run(svc,reauthorize=lambda:auth.append(True));n=len(auth);auth.clear()
    observed=run(svc,reauthorize=lambda:auth.append(True),_read_observer=lambda r,ok:events.append((r,ok)))
    assert observed==before and len(auth)==n and events==[(a,True),(b,True)]
    assert '_read_observer' not in str(observed)

@pytest.mark.parametrize('status',[403,404,500])
def test_default_denial_contract_unchanged_but_receipt_false(status):
    def denied(c):raise HTTPException(status,{'private':'source denial'})
    a=reader('semantic_import',denied);b=reader('exports',lambda c:[row('b')])
    svc=WorkspaceToolsService(None,None,None,task_readers=(a,b));events=[]
    original=run(svc);observed=run(svc,_read_observer=lambda r,ok:events.append((r,ok)))
    assert observed==original and events==[(a,False),(b,True)]
    assert [r['id'] for r in original['items']]==['b']
    assert bool(original['unavailable'])==(status==500)
    assert 'source denial' not in str(original)

@pytest.mark.parametrize('fails',[False,True])
def test_observer_error_is_not_swallowed_as_source_availability(fails):
    def read(c):
        if fails:raise HTTPException(403,{'private':'denied'})
        return []
    a=reader('semantic_import',read);b=reader('exports',lambda c:[])
    def broken(*a):raise RuntimeError('receipt_callback_failed')
    with pytest.raises(RuntimeError,match='receipt_callback_failed'):
        run(WorkspaceToolsService(None,None,None,task_readers=(a,b)),_read_observer=broken)


def test_projector_failure_is_not_completed_read():
    malformed=row('bad');del malformed['id']
    a=reader('semantic_import',lambda c:[malformed]);b=reader('exports',lambda c:[]);events=[]
    value=run(WorkspaceToolsService(None,None,None,task_readers=(a,b)),_read_observer=lambda r,ok:events.append((r,ok)))
    assert events==[(a,False),(b,True)] and value['unavailable']


def test_request_receipts_remain_local_on_same_service():
    a=reader('semantic_import',lambda c:[]);b=reader('exports',lambda c:[])
    svc=WorkspaceToolsService(None,None,None,task_readers=(a,b))
    def one(_):
        events=[];run(svc,_read_observer=lambda r,ok:events.append((r,ok)))
        return events
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(one,range(4)))
    assert all(events==[(a,True),(b,True)] for events in results)
    assert len({id(events) for events in results})==4
