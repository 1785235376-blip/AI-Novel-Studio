"""Original owner saves scene order without retargeting author bindings."""
import copy
import pytest
from test_v2_creative_foundation import rig, public
from app.creative.service import CreativeService

@pytest.mark.parametrize('mode',['SCREENPLAY','DIRECTOR'])
def test_scene_order_preserves_original_identity_history_and_linked_notes(rig,mode):
    e=rig
    value={'mode':mode,'title':'Synthetic order','source_independent':True,'scenes':[
        {'id':'a','sequence':3,'heading':'First','action':'A'},
        {'id':'b','sequence':7,'heading':'Second','action':'B'}]}
    if mode=='DIRECTOR':value['director_notes']=[{'id':'note','number':1,'scene_id':'a','note':'Original direction'}]
    original=e.service.create(e.nid,e.scope,e.actor,value);body=public(original)
    body['scenes'][0]['sequence']=7;body['scenes'][1]['sequence']=3
    saved=e.service.update(e.nid,e.scope,e.actor,original['id'],1,body)
    service=CreativeService(e.store,e.novels,e.chapters)
    assert service.get(e.nid,e.scope,original['id'])==saved
    assert [(s['id'],s['sequence'],s['action']) for s in saved['scenes']]==[('b',3,'B'),('a',7,'A')]
    assert saved['director_notes']==original['director_notes'] and saved['source_evidence']==original['source_evidence']
    assert service.history(e.nid,e.scope,original['id'])['items'][0]['scenes']==original['scenes']
    before=copy.deepcopy(e.store.read(e.nid,e.scope))
    with pytest.raises(ValueError):service.update(e.nid,e.scope,e.actor,original['id'],1,body)
    assert e.store.read(e.nid,e.scope)==before
