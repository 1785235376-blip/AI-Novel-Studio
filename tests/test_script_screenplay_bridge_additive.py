"""Exact generic-text staging through the original Creative derive owner."""
import copy
import pytest
from test_v2_creative_foundation import rig, client, public
from app.creative.service import CreativeService, document_digest


def script(e, text='  口播稿\n\nSecond line.  '):
    return e.service.create(e.nid, e.scope, e.actor, {'mode':'SCRIPT','title':'Synthetic script',
        'source_independent':True,'script':{'purpose':'PODCAST','body':text}})


def derive(e, row, **changes):
    return e.service.derive(e.nid,e.scope,e.actor,row['id'],{'mode':'SCREENPLAY','expected_version':row['version'],'script_policy':'TEXT_CHUNKS',**changes})


@pytest.mark.parametrize('text',['  口播稿\n\nSecond line.  ','甲'*31999+'🙂'+'尾'*32000],ids=['short','unicode-64000'])
def test_exact_text_and_source_survive_original_save_reopen_and_downstream_stage(rig,text):
    e=rig; source=script(e,text); result=derive(e,source)
    assert result['mode']=='SCREENPLAY' and result['status']=='DRAFT' and not result['source_independent']
    assert ''.join(scene['action'] for scene in result['scenes'])==text
    assert all(len(scene['action'])<=16000 and not scene['dialogue'] and not scene['characters'] for scene in result['scenes'])
    assert result['source_documents']=={source['id']:{'version':source['version'],'digest':document_digest(source)}}
    assert result['provenance']['parameters']['source_purpose']=='PODCAST'
    assert result['provenance']['parameters']['semantic_scene_analysis'] is False
    service=CreativeService(e.store,e.novels,e.chapters)
    assert service.get(e.nid,e.scope,result['id'])==result
    assert service.get(e.nid,e.scope,source['id'])==source
    board=service.derive(e.nid,e.scope,e.actor,result['id'],{'mode':'STORYBOARD','expected_version':1})
    assert board['scenes']==result['scenes'] and len(board['shots'])==len(result['scenes'])
    assert board['provenance']['parameters']=={'rule_version':'creative-stage-copy-v1'}


def test_missing_policy_wrong_source_and_stale_version_never_write(rig):
    e=rig; source=script(e); before=copy.deepcopy(e.store.read(e.nid,e.scope))
    for changes in [{'script_policy':None},{'expected_version':2},{'shot_policy':'DIRECTOR_NOTES'}]:
        with pytest.raises(ValueError):derive(e,source,**changes)
        assert e.store.read(e.nid,e.scope)==before
    result=derive(e,source);before=copy.deepcopy(e.store.read(e.nid,e.scope))
    with pytest.raises(ValueError):derive(e,result)
    assert e.store.read(e.nid,e.scope)==before


def test_source_change_and_final_guard_keep_original_derived_authority(rig):
    e=rig;source=script(e);before=copy.deepcopy(e.store.read(e.nid,e.scope));calls=0
    def reject_final():
        nonlocal calls
        calls+=1
        if calls==2:raise PermissionError('synthetic permission retirement')
    with pytest.raises(PermissionError):
        e.service.derive(e.nid,e.scope,e.actor,source['id'],{'mode':'SCREENPLAY','expected_version':1,'script_policy':'TEXT_CHUNKS'},reauthorize=reject_final)
    assert e.store.read(e.nid,e.scope)==before
    result=derive(e,source);body=public(source);body['script']['body']='Changed'
    e.service.update(e.nid,e.scope,e.actor,source['id'],1,body)
    with pytest.raises(ValueError):e.service.get(e.nid,e.scope,result['id'])


def test_original_mounted_derive_permission_and_explicit_policy(rig,client):
    e=rig;source=script(e);url=f'/api/novels/{e.nid}/experimental/creative/documents/{source["id"]}/derive'
    body={'mode':'SCREENPLAY','expected_version':1,'script_policy':'TEXT_CHUNKS'}
    before=copy.deepcopy(e.store.read(e.nid,e.scope))
    assert client.post(url,json=body,headers={'X-Session-Token':'reader'}).status_code==403
    assert e.store.read(e.nid,e.scope)==before
    response=client.post(url,json=body,headers={'X-Session-Token':'owner'})
    assert response.status_code==201,response.text
    assert ''.join(scene['action'] for scene in response.json()['scenes'])==source['script']['body']


def test_staged_text_reaches_original_human_director_review_without_admitting_script_directly(rig):
    e=rig;source=script(e)
    before=copy.deepcopy(e.store.read(e.nid,e.scope))
    with pytest.raises(ValueError):
        e.service.proposals.create(e.nid,e.scope,e.actor,{'source_document_id':source['id'],'expected_source_version':1})
    assert e.store.read(e.nid,e.scope)==before
    staged=derive(e,source)
    proposal=e.service.proposals.create(e.nid,e.scope,e.actor,{'source_document_id':staged['id'],'expected_source_version':1})
    assert proposal['status']=='NEEDS_REVIEW' and proposal['provenance']['model_called'] is False
    reviewed=e.service.proposals.review(e.nid,e.scope,e.actor,proposal['id'],{
        'expected_version':proposal['version'],'reviewed_output_digest':proposal['output_digest'],
        'title':proposal['title'],'director_notes':proposal['director_notes']})['document']
    assert reviewed['mode']=='DIRECTOR' and reviewed['scenes']==staged['scenes']
    service=CreativeService(e.store,e.novels,e.chapters)
    assert service.get(e.nid,e.scope,reviewed['id'])==reviewed
    assert service.get(e.nid,e.scope,source['id'])==source
