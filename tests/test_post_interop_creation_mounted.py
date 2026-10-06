"""Both production aliases, real original history and permission contracts."""
from test_r3_mounted_contracts import mounted,prefix,scoped,checked


def comparison(e):
    chapter=e.chapters.get(e.chapter['id']);newer=e.chapters.save(chapter['id'],{'version':chapter['version'],'content':'New original historical facts.'})
    return {'chapter_id':chapter['id'],'current_version':newer['version'],'before_version':chapter['version'],'after_version':newer['version']}


def test_mounted_comparison_original_history_review_and_restart(mounted):
    e=mounted;base=e.base+'/revisions';value=comparison(e);original=e.chapters.get(value['chapter_id'])
    assert checked(e.client.get(base+'/original-versions',params={'chapter_id':value['chapter_id']}))['authority']=='ORIGINAL_CHAPTER_HISTORY'
    receipt=checked(e.client.post(base+'/comparisons/preview',json=value))
    row=checked(e.client.post(base+'/comparisons',json={'comparison':value,'preview_digest':receipt['preview_digest'],'title':'Real persisted comparison'}),201)
    checked(e.client.post(base+f"/comparisons/{row['id']}/review",json={'expected_version':1,'action':'acknowledge'}))
    reopened=checked(e.client.get(base+f"/comparisons/{row['id']}"))
    assert reopened['status']=='ACKNOWLEDGED' and reopened['history'][0]['status']=='REVIEW'
    assert reopened['model_called'] is False and e.chapters.get(value['chapter_id'])==original


def test_mounted_new_comparison_routes_default_off_and_v1_acceptance(mounted,monkeypatch):
    e=mounted;value=comparison(e);base=e.base+'/revisions'
    for flags,acceptance in [('', 'false'),('revision_intelligence_v2','true')]:
        monkeypatch.setenv('EXPERIMENTAL_FEATURES',flags);monkeypatch.setenv('V1_ACCEPTANCE_MODE',acceptance)
        assert e.client.get(base+'/comparisons').status_code==404
        assert e.client.get(base+'/original-versions',params={'chapter_id':value['chapter_id']}).status_code==404
        assert e.client.post(base+'/comparisons/preview',json=value).status_code==404


def test_mounted_comparison_real_membership_role_and_branch_denial(mounted,monkeypatch):
    value=comparison(mounted);e=scoped(mounted,monkeypatch);base=e.base+'/revisions'
    assert e.client.get(base+'/comparisons',headers=e.viewer_headers).status_code==403
    assert e.client.post(base+'/comparisons/preview',json=value,headers=e.viewer_headers).status_code==403
    assert e.client.post(base+'/comparisons/preview',json=value,headers=e.headers).status_code==422
    e.authorization.revoke_role(e.role,e.lead)
    assert e.client.get(base+'/comparisons',headers=e.headers).status_code==403


def test_mounted_scene_context_uses_planning_authority_and_no_later_text(mounted):
    e=mounted;base=e.base;cid=e.chapter['id']
    plan=checked(e.client.post(base+'/planning/graphs',json={'title':'Scene graph'}),201)
    volume=checked(e.client.post(base+'/planning/nodes',json={'graph_id':plan['id'],'parent_id':plan['root_node_id'],'level':'VOLUME','title':'Volume'}),201)
    chapter=checked(e.client.post(base+'/planning/nodes',json={'graph_id':plan['id'],'parent_id':volume['id'],'level':'CHAPTER','title':'Chapter','links':{'chapter_ids':[cid]}}),201)
    scenes=[checked(e.client.post(base+'/planning/nodes',json={'graph_id':plan['id'],'parent_id':chapter['id'],'level':'SCENE','title':str(i),'position':i,'links':{'chapter_ids':[cid]}}),201) for i in (1,2)]
    row=checked(e.client.post(base+'/story-graph/records',json={'kind':'KNOWLEDGE_EVENT','title':'Later intent','chapter_id':cid,'data':{'character_id':'alice','scene_id':scenes[1]['id'],'operation':'SET_STATE','category':'INTENT','value':'LATER_SCENE_INTENT'}}),201)
    checked(e.client.post(base+f"/story-graph/records/{row['id']}/approve",json={'expected_version':1}))
    body={'chapter_id':cid,'character_id':'alice','scene_id':scenes[0]['id']}
    before=checked(e.client.post(base+'/story-graph/character-context',json=body))
    assert not before['intent'] and before['scene_id']==scenes[0]['id']
    assert checked(e.client.post(base+'/story-graph/character-context',json={**body,'scene_id':scenes[1]['id']}))['intent'][0]['text']=='LATER_SCENE_INTENT'
