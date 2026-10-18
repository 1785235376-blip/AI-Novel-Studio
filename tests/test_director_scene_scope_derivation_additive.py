"""Selected-scene sub-Director drafts reuse the original derivation transaction."""
from copy import deepcopy
import pytest
from app.creative.service import CreativeService, document_digest
from test_v2_creative_foundation import rig, client, public


def director(e):
    return e.service.create(e.nid,e.scope,e.actor,{'mode':'DIRECTOR','title':'Original Director','source_independent':True,
        'scenes':[{'id':'scene-a','sequence':1,'heading':'A','action':'Selected original text'},
                  {'id':'scene-b','sequence':2,'heading':'B','action':'Outside selected scope'}],
        'director_notes':[{'id':'note-a','number':1,'scene_id':'scene-a','note':'Preserved direction'},
                          {'id':'note-b','number':2,'scene_id':'scene-b','note':'Excluded direction'}]})


def body(source,**patch):
    value={'expected_version':source['version'],'mode':'DIRECTOR','director_scope':{
        'source_digest':document_digest(source),'responsibility':'Opening scene direction','scene_ids':['scene-a']}}
    value.update(patch);return value


def test_selected_scene_scope_is_a_separate_reopenable_source_bound_draft(rig):
    e=rig;source=director(e);result=e.service.derive(e.nid,e.scope,e.actor,source['id'],body(source))
    assert result['id']!=source['id'] and result['mode']=='DIRECTOR' and result['status']=='DRAFT'
    assert result['scenes']==source['scenes'][:1] and result['director_notes']==source['director_notes'][:1]
    assert result['source_documents']=={source['id']:{'version':1,'digest':document_digest(source)}}
    assert result['provenance']['parameters']['responsibility']=='Opening scene direction'
    assert result['provenance']['parameters']['scene_ids']==['scene-a']
    assert result['provenance']['model_called'] is False and result['provenance']['parameters']['copied_approval'] is False
    reopened=CreativeService(e.store,e.novels,e.chapters)
    assert reopened.get(e.nid,e.scope,result['id'])==result and reopened.get(e.nid,e.scope,source['id'])==source
    board=reopened.derive(e.nid,e.scope,e.actor,result['id'],{'expected_version':1,'mode':'STORYBOARD','shot_policy':'DIRECTOR_NOTES'})
    assert len(board['shots'])==1 and board['shots'][0]['scene_id']=='scene-a'


@pytest.mark.parametrize('patch',[{'scene_ids':[]},{'scene_ids':['missing']},{'scene_ids':['scene-a','scene-a']},
    {'source_digest':'b'*64},{'responsibility':'   '},{'responsibility':'bad\nlabel'}])
def test_invalid_or_stale_selection_never_creates_a_document(rig,patch):
    e=rig;source=director(e);request=body(source);request['director_scope'].update(patch);before=deepcopy(e.store.read(e.nid,e.scope))
    with pytest.raises(ValueError):e.service.derive(e.nid,e.scope,e.actor,source['id'],request)
    assert e.store.read(e.nid,e.scope)==before


def test_final_authority_revoke_rolls_back_and_parent_change_invalidates_child(rig):
    e=rig;source=director(e);before=deepcopy(e.store.read(e.nid,e.scope));calls=0
    def revoke():
        nonlocal calls
        calls+=1
        if calls==2:raise PermissionError('synthetic revoked')
    with pytest.raises(PermissionError):e.service.derive(e.nid,e.scope,e.actor,source['id'],body(source),reauthorize=revoke)
    assert e.store.read(e.nid,e.scope)==before
    child=e.service.derive(e.nid,e.scope,e.actor,source['id'],body(source));updated=public(source);updated['scenes'][0]['action']='Changed original'
    e.service.update(e.nid,e.scope,e.actor,source['id'],1,updated)
    with pytest.raises(ValueError):e.service.get(e.nid,e.scope,child['id'])


def test_existing_derive_route_requires_mutation_permission_and_returns_new_draft(rig,client):
    e=rig;source=director(e);url=f'/api/novels/{e.nid}/experimental/creative/documents/{source["id"]}/derive';before=deepcopy(e.store.read(e.nid,e.scope))
    assert client.post(url,json=body(source),headers={'X-Session-Token':'reader'}).status_code==403
    assert e.store.read(e.nid,e.scope)==before
    response=client.post(url,json=body(source),headers={'X-Session-Token':'owner'})
    assert response.status_code==201,response.text
    assert response.json()['scenes'][0]['id']=='scene-a' and len(response.json()['scenes'])==1
