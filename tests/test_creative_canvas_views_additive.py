"""Original File/PG/Asset owners; independent display data, never execution."""
import base64
from copy import deepcopy
from uuid import uuid4
import pytest
from app.creative.graph import CreativeGraphService, execution_definition
from app.creative.graph_models import parse_graph, MAX_NODES, MAX_MEDIA_NODES
from app.creative.canvas_view_models import CANVAS_VIEWS, CanvasViewDefinition
from test_v2_independent_workspace import rig, import_asset, png_bytes


def owner(e):return CreativeGraphService(e.store,e.service)
def reference(row):return {key:row[source] for key,source in [('asset_id','id'),('version','version'),('digest','sha256'),('kind','kind')]}
def definition(assets,count=1):return {'title':'Media display','cards':[{'id':f'card-{i}','position':{'x':float(i%40*240),'y':float(i//40*180)},'asset':reference(assets[i%len(assets)])} for i in range(count)]}
def create(e,graph,value,request_id=None,guard=lambda:None):return graph.canvas_views.create(e.nid,e.scope,e.actor,{'request_id':request_id or 'view-'+uuid4().hex,'definition':value},guard)


def test_thousand_real_reference_cards_save_reopen_without_binary_or_execution(rig,monkeypatch):
    e=rig;assets=[import_asset(e,data=png_bytes(bytes([i,20,30])),filename=f'synthetic-{i}.png') for i in range(4)]
    graph=owner(e);value=definition(assets,1000)
    with monkeypatch.context() as m:
        m.setattr(e.assets,'content',lambda *a,**k:(_ for _ in ()).throw(AssertionError('No binary load for display metadata')))
        first=create(e,graph,value,'large-view');repeated=create(e,graph,value,'large-view')
        assert repeated==first and len(first['definition']['cards'])==1000
        assert first['execution_authority'] is False and first['binary_content_verified'] is False
        assert all(row['state']=='CURRENT_METADATA' for row in first['reference_states'])
        replacement=deepcopy(first['definition']);replacement['cards'][0]['position']['x']=450.0
        saved=graph.canvas_views.save(e.nid,e.scope,e.actor,first['id'],{'expected_version':1,'definition':replacement})
        assert owner(e).canvas_views.get(e.nid,e.scope,e.actor,first['id'])==saved
    raw=e.raw_store.read(e.nid,e.scope)
    assert raw['collections'][CANVAS_VIEWS][first['id']]['history'][0]['definition']==first['definition']
    assert not raw['collections'].get(graph.RUNS) and not raw['collections'].get(graph.GRAPHS)
    assert MAX_NODES==16 and MAX_MEDIA_NODES==24
    with pytest.raises(ValueError):parse_graph(value)


def test_current_asset_metadata_stale_deleted_masking_and_explicit_removal(rig):
    e=rig;asset=import_asset(e);graph=owner(e);created=create(e,graph,definition([asset]))
    with e.service._asset_scope(e.nid,e.scope):
        e.assets.update_metadata(asset['id'],{'provider_id':'synthetic-update'},expected_version=asset['version'])
    stale=graph.canvas_views.get(e.nid,e.scope,e.actor,created['id'])
    assert stale['reference_states']==[{'card_id':'card-0','state':'STALE'}]
    before=deepcopy(e.raw_store.read(e.nid,e.scope))
    with pytest.raises(ValueError):graph.canvas_views.save(e.nid,e.scope,e.actor,created['id'],{'expected_version':1,'definition':stale['definition']})
    assert e.raw_store.read(e.nid,e.scope)==before
    with e.service._asset_scope(e.nid,e.scope):e.assets.delete(asset['id'])
    masked=graph.canvas_views.get(e.nid,e.scope,e.actor,created['id'])
    assert masked['reference_states']==[{'card_id':'card-0','state':'UNAVAILABLE'}]
    assert 'asset' not in masked['definition']['cards'][0]
    assert e.raw_store.read(e.nid,e.scope)==before
    repaired=graph.canvas_views.save(e.nid,e.scope,e.actor,created['id'],{'expected_version':1,'definition':{'title':'Empty repaired view','cards':[]}})
    assert repaired['version']==2 and repaired['definition']['cards']==[]


def test_actor_and_reused_project_do_not_inherit_old_display_views(rig):
    e=rig;graph=owner(e);created=create(e,graph,{'title':'Old owner','cards':[]},'same-request')
    with pytest.raises(FileNotFoundError):graph.canvas_views.get(e.nid,e.scope,'another-actor',created['id'])
    assert graph.canvas_views.list(e.nid,e.scope,'another-actor')['items']==[]
    old_raw=deepcopy(e.raw_store.read(e.nid,e.scope)['collections'][CANVAS_VIEWS][created['id']])
    e.novels.delete(e.nid);e.create_project('New owner',e.nid)
    with pytest.raises(FileNotFoundError):graph.canvas_views.get(e.nid,e.scope,e.actor,created['id'])
    assert graph.canvas_views.list(e.nid,e.scope,e.actor)['items']==[]
    fresh=create(e,graph,{'title':'New owner','cards':[]},'same-request')
    assert fresh['id']!=created['id'] and graph.canvas_views.get(e.nid,e.scope,e.actor,fresh['id'])==fresh
    raw=e.raw_store.read(e.nid,e.scope)['collections'][CANVAS_VIEWS]
    if created['id'] in raw:assert raw[created['id']]==old_raw


def test_private_asset_references_and_invalid_or_reused_request_fail_without_writes(rig):
    e=rig;graph=owner(e)
    with e.service._asset_scope(e.nid,e.scope):
        private=e.assets.create(e.nid,'private.png',base64.b64encode(png_bytes()).decode(),media_type='image/png',kind='image',required_features=('narrative_production_v2',),owner_actor_id=e.actor)
    before=deepcopy(e.raw_store.read(e.nid,e.scope))
    with pytest.raises(ValueError):create(e,graph,definition([private]))
    assert e.raw_store.read(e.nid,e.scope)==before
    created=create(e,graph,{'title':'Original','cards':[]},'fixed');before=deepcopy(e.raw_store.read(e.nid,e.scope))
    with pytest.raises(ValueError):create(e,graph,{'title':'Changed','cards':[]},'fixed')
    with pytest.raises(ValueError):graph.canvas_views.save(e.nid,e.scope,e.actor,created['id'],{'expected_version':2,'definition':created['definition']})
    assert e.raw_store.read(e.nid,e.scope)==before
    for invalid in [{'schema_version':True,'title':'Invalid','cards':[]},{'title':'Too many','cards':[{'id':f'c{i}','position':{'x':0,'y':0},'asset':reference(private)} for i in range(1001)]}]:
        with pytest.raises(ValueError):CanvasViewDefinition.model_validate(invalid)


def test_collection_capacity_and_final_guard_roll_back_original_transaction(rig):
    e=rig;graph=owner(e);before=deepcopy(e.raw_store.read(e.nid,e.scope))
    def guard():
        if graph.store.read(e.nid,e.scope)['collections'].get(CANVAS_VIEWS):raise PermissionError('Synthetic final authority retirement')
    with pytest.raises(PermissionError):create(e,graph,{'title':'Denied','cards':[]},guard=guard)
    assert e.raw_store.read(e.nid,e.scope)==before
    for i in range(8):create(e,graph,{'title':f'View {i}','cards':[]})
    before=deepcopy(e.raw_store.read(e.nid,e.scope))
    with pytest.raises(ValueError,match='CAPACITY'):create(e,graph,{'title':'Over limit','cards':[]})
    assert e.raw_store.read(e.nid,e.scope)==before
