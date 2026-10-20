"""Original File owner history; no alternate history store or binary restore."""
from copy import deepcopy
import pytest
from app.experimental.common import CapabilityVersionConflict, StaleSourceError
from app.creative.canvas_view_models import CANVAS_VIEWS
from test_v2_independent_workspace import rig, import_asset
from test_creative_canvas_views_additive import owner, create, definition

def restore_body(history, version=1):
    target = next(row for row in history['items'] if row['version'] == version)
    return {'expected_version': history['current_version'], 'expected_definition_digest': history['current_definition_digest'],
        'expected_incarnation': history['incarnation'], 'restore_version': version, 'restore_definition_digest': target['definition_digest']}

def versions(e, first=None, second=None):
    graph = owner(e)
    one = create(e, graph, first or {'title': 'v1', 'cards': []})
    two = graph.canvas_views.save(e.nid, e.scope, e.actor, one['id'], {'expected_version': 1, 'definition': second or {**one['definition'], 'title': 'v2'}})
    return graph, one, two

def test_restore_creates_v3_reopens_and_preserves_original_history_and_retires_old_context(rig):
    e=rig;graph,one,two=versions(e);h=graph.canvas_views.history(e.nid,e.scope,e.actor,one['id']);body=restore_body(h)
    assert [v['version'] for v in h['items']]==[1,2] and h['items'][0]['can_restore'] and not h['items'][1]['can_restore']
    saved=graph.canvas_views.restore(e.nid,e.scope,e.actor,one['id'],body)
    assert saved['version']==3 and saved['definition']==one['definition'] and saved['definition_digest']==one['definition_digest']
    assert saved['version']!=one['version'] and saved['execution_authority'] is False
    assert owner(e).canvas_views.get(e.nid,e.scope,e.actor,one['id'])==saved
    latest=owner(e).canvas_views.history(e.nid,e.scope,e.actor,one['id'])
    assert [v['version'] for v in latest['items']]==[1,2,3] and latest['items'][1]['definition']==two['definition']
    before=deepcopy(e.raw_store.read(e.nid,e.scope))
    with pytest.raises(CapabilityVersionConflict):graph.canvas_views.restore(e.nid,e.scope,e.actor,one['id'],body)
    assert e.raw_store.read(e.nid,e.scope)==before

@pytest.mark.parametrize('field,value', [('expected_version',1),('expected_incarnation','wrong-incarnation'),('expected_definition_digest','a'*64),('restore_definition_digest','b'*64),('restore_version',99),('restore_version',2)])
def test_restore_rejects_stale_or_wrong_review_context_atomically(rig,field,value):
    e=rig;graph,one,_=versions(e);h=graph.canvas_views.history(e.nid,e.scope,e.actor,one['id']);body=restore_body(h);body[field]=value;before=deepcopy(e.raw_store.read(e.nid,e.scope))
    with pytest.raises((ValueError,CapabilityVersionConflict)):graph.canvas_views.restore(e.nid,e.scope,e.actor,one['id'],body)
    assert e.raw_store.read(e.nid,e.scope)==before

def test_history_and_restore_do_not_cross_actor_scope_project_or_incarnation(rig):
    e=rig;graph,one,_=versions(e);body=restore_body(graph.canvas_views.history(e.nid,e.scope,e.actor,one['id']))
    other='canvas-history-other-project';e.create_project('Other live project',other)
    for actor,scope,nid in [('another',e.scope,e.nid),(e.actor,{**e.scope,'novel_id':'other'},e.nid),(e.actor,{**e.scope,'novel_id':other},other),(e.actor,e.scope,'missing-project')]:
        with pytest.raises((FileNotFoundError,ValueError)):graph.canvas_views.history(nid,scope,actor,one['id'])
        with pytest.raises((FileNotFoundError,ValueError)):graph.canvas_views.restore(nid,scope,actor,one['id'],body)
    e.novels.delete(e.nid);e.create_project('Reused project',e.nid)
    with pytest.raises(FileNotFoundError):owner(e).canvas_views.history(e.nid,e.scope,e.actor,one['id'])
    with pytest.raises((FileNotFoundError,ValueError)):owner(e).canvas_views.restore(e.nid,e.scope,e.actor,one['id'],body)

def test_old_asset_pins_remain_stale_or_masked_and_never_rebind_to_latest(rig):
    e=rig;a=import_asset(e);graph,one,_=versions(e,definition([a]),{'title':'Current without old image','cards':[]})
    with e.service._asset_scope(e.nid,e.scope):e.assets.update_metadata(a['id'],{'provider_id':'metadata-change'},expected_version=a['version'])
    h=graph.canvas_views.history(e.nid,e.scope,e.actor,one['id']);assert h['items'][0]['reference_states'][0]['state']=='STALE' and not h['items'][0]['can_restore']
    assert h['items'][0]['definition']['cards'][0]['asset']['version']==a['version'];body=restore_body(h);before=deepcopy(e.raw_store.read(e.nid,e.scope))
    with pytest.raises(StaleSourceError,match='SOURCE_UNRESOLVED'):graph.canvas_views.restore(e.nid,e.scope,e.actor,one['id'],body)
    assert e.raw_store.read(e.nid,e.scope)==before
    with e.service._asset_scope(e.nid,e.scope):e.assets.delete(a['id'])
    h=graph.canvas_views.history(e.nid,e.scope,e.actor,one['id']);assert h['items'][0]['reference_states'][0]['state']=='UNAVAILABLE' and 'asset' not in h['items'][0]['definition']['cards'][0]
    with pytest.raises(StaleSourceError,match='SOURCE_UNRESOLVED'):graph.canvas_views.restore(e.nid,e.scope,e.actor,one['id'],restore_body(h))

def test_last_guard_denial_rolls_back_and_corrupt_snapshot_is_rejected(rig):
    e=rig;graph,one,_=versions(e);body=restore_body(graph.canvas_views.history(e.nid,e.scope,e.actor,one['id']));before=deepcopy(e.raw_store.read(e.nid,e.scope))
    def deny():
        if graph.store.read(e.nid,e.scope)['collections'][CANVAS_VIEWS][one['id']]['version']==3:raise PermissionError('retired')
    with pytest.raises(PermissionError):graph.canvas_views.restore(e.nid,e.scope,e.actor,one['id'],body,deny)
    assert e.raw_store.read(e.nid,e.scope)==before
    with graph.store.transaction(e.nid,e.scope) as state:state['collections'][CANVAS_VIEWS][one['id']]['history'][0]['scope']={'mode':'local','novel_id':'foreign'}
    with pytest.raises(ValueError,match='HISTORY_CORRUPT'):graph.canvas_views.history(e.nid,e.scope,e.actor,one['id'])

def test_history_capacity_refuses_restore_without_dropping_old_versions(rig):
    e=rig;graph,one,row=versions(e)
    for version in range(2,21):row=graph.canvas_views.save(e.nid,e.scope,e.actor,one['id'],{'expected_version':version,'definition':{**row['definition'],'title':f'v{version+1}'}})
    h=graph.canvas_views.history(e.nid,e.scope,e.actor,one['id']);assert len(h['items'])==21;before=deepcopy(e.raw_store.read(e.nid,e.scope))
    with pytest.raises(ValueError,match='CAPACITY'):graph.canvas_views.restore(e.nid,e.scope,e.actor,one['id'],restore_body(h))
    assert e.raw_store.read(e.nid,e.scope)==before
