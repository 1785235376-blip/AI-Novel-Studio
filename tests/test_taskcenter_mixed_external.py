"""Independent mounted mixed local cursor: original POSTs, auth and readers."""
from types import SimpleNamespace
import pytest
from test_studio_asset_query import rig,shared_scope
from test_taskcenter_local_export_external import export_rig,files


@pytest.fixture
def mixed_rig(export_rig,monkeypatch):
    e=export_rig;source=e.api.import_service;store=e.api.workspace_tools_service.store
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','workspace_tools_v2,semantic_import_v2')
    for name,value in [('store',store),('novels',e.rig.novels),('chapters',e.rig.workspace.creative.chapters)]:monkeypatch.setattr(source,name,value)
    chapter=source.chapters.create(e.rig.nid,{'title':'Synthetic import source','content':'Alice entered the forest.'})
    imports=[]
    for _ in range(3):
        r=e.rig.client.post(f'/api/novels/{e.rig.nid}/experimental/imports/jobs',json={'chapter_ids':[chapter['id']]})
        assert r.status_code==201,r.text;imports.append(r.json()['id'])
    return SimpleNamespace(**e.__dict__,imports=imports,importer=source,store=store)


def get(e,params=None,prefix='/api',headers=None):
    return e.rig.client.get(f'{prefix}/novels/{e.rig.nid}/experimental/workspace/tasks',params={'authority':['semantic_import','exports'],'page_mode':'cursor','limit':2,**(params or {})},headers=headers)


@pytest.mark.parametrize('prefix',['/api','/api/v1'])
def test_both_original_post_writers_then_mixed_replay_and_final(mixed_rig,prefix):
    e=mixed_rig;before=files(e.rig.root);submitted=list(e.calls)
    r=get(e,prefix=prefix);assert r.status_code==200,r.text
    allitems=list(r.json()['items']);t=r.json()['next_cursor']
    while t:
        r=get(e,{'cursor':t},prefix);assert r.status_code==200,r.text
        assert get(e,{'cursor':t},prefix).json()==r.json()
        allitems+=r.json()['items'];t=r.json()['next_cursor']
    assert [x['authority'] for x in allitems]==['semantic_import']*3+['exports']*3
    assert {x['id'] for x in allitems}==set(e.imports+e.ids)
    assert r.json()['observed_total']==6 and r.json()['coverage']['completeness']=='NOT_ASSERTED'
    assert files(e.rig.root)==before and e.calls==submitted
