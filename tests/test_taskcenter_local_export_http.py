from copy import deepcopy
from types import SimpleNamespace
import pytest
from test_studio_asset_query import rig
from app.services.export_job_service import ExportJobService
from app.experimental.taskcenter_cursor import TaskCenterCursorEngine

pytestmark=pytest.mark.file_backend_only

@pytest.fixture
def exports(rig,monkeypatch):
    from app import api as legacy
    from app.experimental import api
    from app.experimental.store import ExperimentalStore
    store=ExperimentalStore(rig.root,'file','')
    monkeypatch.setattr(legacy,'chapter_service',rig.workspace.creative.chapters)
    for key,val in [('store',store),('novels',rig.novels),('chapters',rig.workspace.creative.chapters)]:
        monkeypatch.setattr(api.workspace_tools_service,key,val)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','workspace_tools_v2')
    rig.seed('setup.bin',required_features=())
    source=ExportJobService(rig.root,lambda *a:pytest.fail('no exporter'))
    monkeypatch.setattr(source,'_submit',lambda *a:None)
    monkeypatch.setattr(legacy,'export_job_service',source)
    adapter=getattr(api.taskcenter_cursor_adapter,'export_adapter',None)
    if adapter is not None:
        monkeypatch.setattr(adapter,'source',source)
        monkeypatch.setattr(adapter,'engine',TaskCenterCursorEngine())
    ids=[source.create(rig.nid,'txt',permission_context=deepcopy(rig.scope))['id'] for _ in range(3)]
    yield SimpleNamespace(rig=rig,source=source,ids=ids,adapter=adapter,monkeypatch=monkeypatch)
    source._pool.shutdown(wait=True)


def get(e,params=None,prefix='/api',headers=None):
    return e.rig.client.get(f'{prefix}/novels/{e.rig.nid}/experimental/workspace/tasks',
        params={'authority':'exports','page_mode':'cursor','limit':1,**(params or {})},headers=headers)


def snapshot(root):
    return {str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}

@pytest.mark.parametrize('prefix',['/api','/api/v1'])
def test_first_next_replay_final_zero_write(exports,prefix):
    e=exports;before=snapshot(e.rig.root);first=get(e,prefix=prefix);assert first.status_code==200,first.text
    second=get(e,{'cursor':first.json()['next_cursor']},prefix);assert second.status_code==200,second.text
    assert get(e,{'cursor':first.json()['next_cursor']},prefix).json()==second.json()
    third=get(e,{'cursor':second.json()['next_cursor']},prefix);assert third.status_code==200,third.text
    assert third.json()['next_cursor'] is None and third.json()['observed_total']==3
    assert len({r.json()['items'][0]['id'] for r in [first,second,third]})==3
    assert all(r.headers['cache-control']=='no-store' for r in [first,second,third])
    assert snapshot(e.rig.root)==before

@pytest.mark.parametrize('kind',['private_aba','recreate_row','document','project'])
def test_restart_original_owner_changes(exports,kind):
    e=exports;first=get(e);assert first.status_code==200,first.text;rows=e.source._read();original=deepcopy(rows);jid=e.ids[0]
    if kind=='private_aba':
        rows[jid]['snapshot']={'private':'changed'};e.source._write(rows);e.source._write(original)
    elif kind=='recreate_row':
        del rows[jid];e.source._write(rows);e.source._write(original)
    elif kind=='document':e.source.path.unlink();e.source._write(original)
    else:
        (e.rig.root/'novels'/e.rig.nid/'creative_project_v2.json').unlink();e.rig.workspace.creative.store.incarnation(e.rig.nid)
    r=get(e,{'cursor':first.json()['next_cursor']});assert r.status_code==409,r.text


def test_empty_bound_and_legacy_refusal(exports):
    e=exports;e.source._write({});r=get(e);assert r.status_code==200,r.text;assert r.json()['items']==[] and r.json()['next_cursor'] is None
    e.source.path.write_text('{}');before=snapshot(e.rig.root);r=get(e);assert r.status_code==501,r.text;assert snapshot(e.rig.root)==before


def test_query_hidden_row_does_not_invalidate(exports):
    e=exports;keep=e.ids[:2];rows=e.source._read()
    for jid in keep:rows[jid]['status']='failed'
    rows[e.ids[2]]['status']='queued';e.source._write(rows)
    params={'failed_only':'true'};first=get(e,params);assert first.status_code==200,first.text
    assert first.json()['next_cursor'] is not None
    rows=e.source._read();rows[e.ids[2]]['snapshot']={'private':'hidden change'};e.source._write(rows)
    r=get(e,{**params,'cursor':first.json()['next_cursor']});assert r.status_code==200,r.text


def test_original_actual_owner_change_refuses(exports):
    e=exports;first=get(e);assert first.status_code==200,first.text
    from app import api as legacy
    e.monkeypatch.setattr(legacy,'export_job_service',object())
    r=get(e,{'cursor':first.json()['next_cursor']});assert r.status_code==409,r.text


def test_get_never_constructs_or_submits_exporter(exports):
    e=exports;e.monkeypatch.setattr(ExportJobService,'__init__',lambda *a,**k:pytest.fail('GET startup'))
    e.monkeypatch.setattr(e.source,'_submit',lambda *a:pytest.fail('GET submit'))
    assert get(e).status_code==200

@pytest.mark.parametrize('params',[{'authority':['exports','semantic_import']},{'authority':['exports','agent_team']}])
def test_mixed_unsupported(exports,params):
    r=get(exports,params);assert r.status_code==501,r.text
