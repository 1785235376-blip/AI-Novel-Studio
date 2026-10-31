from copy import deepcopy
from types import SimpleNamespace
import pytest
from test_taskcenter_lifecycle_http import cursor_rig, rig
from app.experimental.imports import JOBS
from app.experimental.taskcenter_cursor import TaskCenterCursorEngine
from app.services.export_job_service import ExportJobService

pytestmark=pytest.mark.file_backend_only

@pytest.fixture
def mixed(cursor_rig,monkeypatch):
    from app import api as legacy
    from app.experimental import api
    e=cursor_rig
    source=ExportJobService(e.rig.root,lambda *a:pytest.fail('no exporter'))
    monkeypatch.setattr(source,'_submit',lambda *a:None)
    monkeypatch.setattr(legacy,'export_job_service',source)
    monkeypatch.setattr(api.taskcenter_cursor_adapter.export_adapter,'source',source)
    adapter=getattr(api.taskcenter_cursor_adapter,'mixed_adapter',None)
    if adapter is not None:monkeypatch.setattr(adapter,'engine',TaskCenterCursorEngine())
    ids=[source.create(e.rig.nid,'txt',permission_context=deepcopy(e.rig.scope))['id'] for _ in range(3)]
    yield SimpleNamespace(e=e,rig=e.rig,source=source,ids=ids,adapter=adapter,monkeypatch=monkeypatch)
    source._pool.shutdown(wait=True)


def get(e,params=None,prefix='/api'):
    return e.rig.client.get(f'{prefix}/novels/{e.rig.nid}/experimental/workspace/tasks',
        params={'authority':['semantic_import','exports'],'page_mode':'cursor','limit':2,**(params or {})})


def snapshot(root):
    return {str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}

@pytest.mark.parametrize('prefix',['/api','/api/v1'])
def test_actual_order_first_next_replay_final_zero_write(mixed,prefix):
    e=mixed;before=snapshot(e.rig.root);expected=get(e,{'page_mode':'offset','limit':100},prefix).json()['items']
    first=get(e,prefix=prefix);assert first.status_code==200,first.text
    second=get(e,{'cursor':first.json()['next_cursor']},prefix);assert second.status_code==200,second.text
    assert get(e,{'cursor':first.json()['next_cursor']},prefix).json()==second.json()
    third=get(e,{'cursor':second.json()['next_cursor']},prefix);assert third.status_code==200,third.text
    assert first.json()['items']+second.json()['items']+third.json()['items']==expected
    assert first.json()['observed_total']==6 and third.json()['next_cursor'] is None
    assert [r['authority'] for r in expected]==['semantic_import']*3+['exports']*3
    assert snapshot(e.rig.root)==before


def test_parameter_order_and_duplicates_are_canonical(mixed):
    e=mixed;first=get(e);assert first.status_code==200,first.text;token=first.json()['next_cursor']
    assert get(e,{'cursor':token}).json()==get(e,{'cursor':token,'authority':['exports','semantic_import','exports']}).json()

@pytest.mark.parametrize('which',['semantic_import','exports'])
def test_selected_private_aba_restart(mixed,which):
    e=mixed;first=get(e);assert first.status_code==200,first.text
    if which=='exports':
        rows=e.source._read();old=deepcopy(rows);rows[e.ids[0]]['snapshot']={'private':'changed'};e.source._write(rows);e.source._write(old)
    else:
        rows=e.e.store.read(e.rig.nid,e.rig.scope)['collections'][JOBS];old=deepcopy(rows)
        with e.e.store.transaction(e.rig.nid,e.rig.scope) as d:d['collections'][JOBS]['job-000']['prompt']='changed'
        with e.e.store.transaction(e.rig.nid,e.rig.scope) as d:d['collections'][JOBS]=old
    assert get(e,{'cursor':first.json()['next_cursor']}).status_code==409


def test_exact_pair_caps_and_empty_query(mixed):
    e=mixed;e.e.seed(205);rows={f'export-{i:03}':{'id':f'export-{i:03}','novel_id':e.rig.nid,'status':'queued','format':'txt','permission_context':deepcopy(e.rig.scope),'created_at':str(i).zfill(4)} for i in range(105)};e.source._write(rows)
    first=get(e,{'limit':100});assert first.status_code==200,first.text
    assert first.json()['observed_total']==300 and first.json()['source_truncated'] is True
    second=get(e,{'limit':100,'cursor':first.json()['next_cursor']});third=get(e,{'limit':100,'cursor':second.json()['next_cursor']})
    assert third.status_code==200 and third.json()['next_cursor'] is None
    assert all(r['authority']=='semantic_import' for r in first.json()['items']+second.json()['items'])
    assert all(r['authority']=='exports' for r in third.json()['items'])
    empty=get(e,{'q':'no-match'});assert empty.json()['items']==[] and empty.json()['source_truncated'] is True

@pytest.mark.parametrize('which',['semantic_import','exports','both'])
def test_empty_bound_sources(mixed,which):
    e=mixed
    if which in ('semantic_import','both'):e.e.seed(0)
    if which in ('exports','both'):e.source._write({})
    r=get(e);assert r.status_code==200,r.text;assert r.json()['observed_total']==(0 if which=='both' else 3)


def test_equal_ids_stay_authority_scoped(mixed):
    e=mixed;rows=e.source._read();rows['job-000']=rows.pop(e.ids[0]);rows['job-000']['id']='job-000';e.source._write(rows)
    r=get(e,{'limit':100});assert r.status_code==200,r.text
    assert [x['authority'] for x in r.json()['items'] if x['id']=='job-000']==['semantic_import','exports']


def test_registry_reorder_restarts(mixed):
    e=mixed;first=get(e);assert first.status_code==200,first.text
    e.monkeypatch.setattr(e.e.svc,'task_readers',tuple(reversed(e.e.svc.task_readers)))
    r=get(e,{'cursor':first.json()['next_cursor']});assert r.status_code==409,r.text

@pytest.mark.parametrize('which',['semantic_import','exports'])
def test_real_singleton_replacement_refuses(mixed,which):
    e=mixed;first=get(e);assert first.status_code==200,first.text
    from app import api as legacy
    from app.experimental import api
    if which=='exports':e.monkeypatch.setattr(legacy,'export_job_service',object())
    else:e.monkeypatch.setattr(api,'import_service',object())
    assert get(e,{'cursor':first.json()['next_cursor']}).status_code==409

@pytest.mark.parametrize('continuation',[False,True])
def test_registry_change_inside_final_component_capture_refuses(mixed,continuation):
    e=mixed;params={}
    if continuation:
        first=get(e);assert first.status_code==200,first.text
        params={'cursor':first.json()['next_cursor']}
    component=e.adapter.components['exports'];original=component._checked_capture;calls=0
    def changed(*args,**kwargs):
        nonlocal calls
        part=original(*args,**kwargs);calls+=1
        if calls==3:e.monkeypatch.setattr(e.e.svc,'task_readers',tuple(reversed(e.e.svc.task_readers)))
        return part
    e.monkeypatch.setattr(component,'_checked_capture',changed)
    response=get(e,params);assert response.status_code==(409 if continuation else 501),response.text


@pytest.mark.parametrize('which',['semantic_import','exports'])
@pytest.mark.parametrize('continuation',[False,True])
def test_denied_empty_source_never_contributes_cursor_binding(mixed,which,continuation):
    from fastapi import HTTPException
    e=mixed
    if which=='semantic_import':e.e.seed(0)
    else:e.source._write({})
    params={}
    if continuation:
        first=get(e);assert first.status_code==200,first.text
        params={'cursor':first.json()['next_cursor']}
    def denied(*args,**kwargs):raise HTTPException(403,{'private':'denied empty source'})
    if which=='semantic_import':e.monkeypatch.setattr(e.e.source,'jobs',denied)
    else:e.monkeypatch.setattr(e.source,'list',denied)
    response=get(e,params);assert response.status_code==(409 if continuation else 501),response.text
    assert 'items' not in response.json() and 'denied empty source' not in response.text

@pytest.mark.parametrize('which',['semantic_import','exports'])
@pytest.mark.parametrize('status',[403,404])
@pytest.mark.parametrize('empty',[False,True])
def test_exact_aggregate_only_denial_cannot_bind_source(mixed,which,status,empty):
    import inspect
    from fastapi import HTTPException
    from app.experimental.ux import WorkspaceToolsService
    e=mixed
    if empty:
        if which=='semantic_import':e.e.seed(0)
        else:e.source._write({})
    first=get(e);assert first.status_code==200,first.text;token=first.json()['next_cursor'];assert token
    source=e.e.source if which=='semantic_import' else e.source
    method='jobs' if which=='semantic_import' else 'list';original=getattr(source,method);calls=[]
    def deny_only_actual(*a,**kw):
        frame=inspect.currentframe()
        while frame is not None:
            if frame.f_code is WorkspaceToolsService.tasks.__code__:
                calls.append(True);raise HTTPException(status,{'private':'actual aggregate denial'})
            frame=frame.f_back
        return original(*a,**kw)
    e.monkeypatch.setattr(source,method,deny_only_actual)
    initial=get(e);continued=get(e,{'cursor':token})
    assert initial.status_code==501,initial.text
    assert continued.status_code==409,continued.text
    assert len(calls)==2 and 'items' not in initial.json() and 'actual aggregate denial' not in initial.text
