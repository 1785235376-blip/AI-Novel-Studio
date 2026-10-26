"""Independent mounted local-export cursor probes, original writer/auth/reader."""
from copy import deepcopy
from types import SimpleNamespace
import json
import pytest
from test_studio_asset_query import rig, shared_scope

pytestmark=pytest.mark.file_backend_only


def files(root):
    return {str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file() and not p.name.endswith('.lock')}


@pytest.fixture
def export_rig(rig,monkeypatch):
    from app import api as legacy
    from app.experimental import api
    from app.experimental.store import ExperimentalStore
    source=legacy.export_job_service
    calls=[]
    monkeypatch.setattr(source,'path',rig.root/'export_jobs.json')
    monkeypatch.setattr(source,'artifact_root',rig.root/'export_artifacts')
    monkeypatch.setattr(source,'snapshotter',None)
    monkeypatch.setattr(source,'_submit',lambda jid:calls.append(jid))
    monkeypatch.setattr(source,'exporter',lambda *a,**kw:pytest.fail('real exporter forbidden'))
    monkeypatch.setattr(legacy,'chapter_service',rig.workspace.creative.chapters)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','workspace_tools_v2')
    monkeypatch.setattr(api.workspace_tools_service,'store',ExperimentalStore(rig.root))
    monkeypatch.setattr(api.workspace_tools_service,'novels',rig.novels)
    monkeypatch.setattr(api.workspace_tools_service,'chapters',rig.workspace.creative.chapters)
    rig.workspace.creative.store.incarnation(rig.nid)
    ids=[]
    for i in range(3):
        response=rig.client.post('/api/exports',params={'novel_id':rig.nid},json={'format':'txt'},headers={'Idempotency-Key':f'fixture-{i}'})
        assert response.status_code==202,response.text
        ids.append(response.json()['id'])
    return SimpleNamespace(rig=rig,source=source,ids=ids,calls=calls,legacy=legacy,api=api,monkeypatch=monkeypatch)


def get(e,params=None,prefix='/api',headers=None):
    return e.rig.client.get(f'{prefix}/novels/{e.rig.nid}/experimental/workspace/tasks',params={'authority':'exports','page_mode':'cursor','limit':1,**(params or {})},headers=headers)


@pytest.mark.parametrize('prefix',['/api','/api/v1'])
def test_original_post_then_cursor_first_next_replay_final_readonly(export_rig,prefix):
    e=export_rig;before=files(e.rig.root);submitted=list(e.calls)
    first=get(e,prefix=prefix);assert first.status_code==200,first.text
    second=get(e,{'cursor':first.json()['next_cursor']},prefix);assert second.status_code==200,second.text
    assert get(e,{'cursor':first.json()['next_cursor']},prefix).json()==second.json()
    third=get(e,{'cursor':second.json()['next_cursor']},prefix);assert third.status_code==200,third.text
    assert third.json()['next_cursor'] is None and third.json()['has_more'] is False
    assert {x.json()['items'][0]['id'] for x in (first,second,third)}==set(e.ids)
    for response in (first,second,third):
        assert response.headers['cache-control']=='no-store'
        assert 'row_lifecycles' not in response.text and '_export_lifecycle' not in response.text
    assert files(e.rig.root)==before and e.calls==submitted
