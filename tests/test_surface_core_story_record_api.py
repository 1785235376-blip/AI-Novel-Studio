"""Mounted five-kind API against unchanged aliases and real project grants."""
from uuid import uuid4
import pytest
from app.authorization import AuthorizationScope, DomainRole, DomainRoleAssignment, ModalityDomain, ScopeKind
from test_r3_mounted_contracts import mounted,prefix,scoped,checked
from test_surface_story_record_api import story
from test_surface_core_story_records import payload

KINDS=['characters','locations','relationships']


def setup(e,kind):
    if kind=='relationships':
        for rid in ['a','b']:e.novels.upsert_character(e.nid,rid,{'name':rid,'privacy_level':'LOCAL_ONLY'})
    return e.story+'/'+kind+'/exact-original'


def grant(e):
    role=DomainRoleAssignment('project-'+uuid4().hex,e.lead,DomainRole.DOMAIN_LEAD,ModalityDomain.NOVEL,AuthorizationScope(ScopeKind.PROJECT,e.workspace,e.nid),e.lead)
    e.authorization.assign_role(role)
    return role


@pytest.mark.parametrize('kind',KINDS)
def test_alias_owner_cas_required_conflict_restore_flag_off_and_legacy_compatibility(story,monkeypatch,kind):
    e=story;path=setup(e,kind)
    catalog=checked(e.client.get(e.story+'/catalog'))
    assert catalog['kinds']==['timeline','foreshadowing','characters','locations','relationships']
    assert catalog['scope']=='PROJECT' and catalog['branch_id'] is None
    data={'record':payload(kind),'expected_digest':None,'expected_version':0}
    for field in ['expected_digest','expected_version']:
        assert e.client.put(path,json={k:v for k,v in data.items() if k!=field}).status_code==422
    first=checked(e.client.put(path,json=data))
    assert first['version']==1
    public=checked(e.client.get(e.prefix+f'/novels/{e.nid}/{kind}'))
    assert next(row for row in public if row['id']=='exact-original')==first['record']
    request={'record':payload(kind,'Changed'),'expected_digest':first['digest'],'expected_version':1}
    second=checked(e.client.put(path,json=request));assert second['version']==2
    conflict=e.client.put(path,json=request)
    assert conflict.status_code==409 and 'Changed' not in conflict.text and 'history' not in conflict.text
    restore={'expected_digest':second['digest'],'expected_version':2,'restore_version':1,'confirmed':True}
    assert e.client.post(path+'/restore',json={**restore,'confirmed':False}).status_code==422
    assert checked(e.client.get(path))['version']==2
    restored=checked(e.client.post(path+'/restore',json=restore))
    assert restored['record']==first['record'] and restored['version']==3
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','')
    assert e.client.get(path).status_code==404 and e.client.put(path,json=request).status_code==404
    legacy=checked(e.client.put(e.prefix+f'/novels/{e.nid}/{kind}/exact-original',json=payload(kind,'Legacy')))
    assert legacy['id']=='exact-original'
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','story_record_versions_v1')
    assert checked(e.client.get(path))['version']==4
    monkeypatch.setenv('V1_ACCEPTANCE_MODE','true')
    assert e.client.get(path).status_code==404


@pytest.mark.parametrize('kind',KINDS)
def test_project_only_permissions_terminal_review_revocation_and_denial_are_private(story,monkeypatch,kind):
    e=story;path=setup(e,kind);e=scoped(e,monkeypatch);token={'X-Session-Token':e.lead}
    assert e.client.get(e.story+'/catalog').status_code==401
    assert e.client.get(e.story+'/catalog',headers=token).status_code==403
    role=grant(e)
    assert e.client.get(e.story+'/catalog',headers=e.headers).status_code==409
    data={'record':payload(kind),'expected_digest':None,'expected_version':0}
    first=checked(e.client.put(path,headers=token,json=data))
    data.update(expected_digest=first['digest'],expected_version=1)
    assert e.client.put(path,headers=e.viewer_headers,json=data).status_code==403
    assert e.client.post(path+'/restore',headers=e.viewer_headers,json={'expected_digest':first['digest'],'expected_version':1,'restore_version':0,'confirmed':True}).status_code==403
    feedback={'expected_digest':first['digest'],'expected_version':1,'decision':'INTENTIONAL','note':'Human reviewed','evidence':'Original source'}
    reviewed=checked(e.client.post(path+'/feedback',headers=token,json=feedback))
    assert reviewed['version']==2 and reviewed['record']==first['record']
    assert e.client.post(path+'/feedback',headers=token,json={**feedback,'expected_version':2}).status_code==409
    e.authorization.revoke_role(role.id,e.lead)
    for response in [e.client.get(path,headers=token),e.client.put(path,headers=token,json=data),e.client.post(path+'/feedback',headers=token,json=feedback)]:
        assert response.status_code==403 and 'Human reviewed' not in response.text and 'history' not in response.text
    assert e.novels.story_record(e.nid,kind,'exact-original')['version']==2


@pytest.mark.parametrize('kind',KINDS)
@pytest.mark.parametrize('revoke',['permission','flag'])
def test_authority_is_rechecked_under_original_commit_lock(story,monkeypatch,kind,revoke):
    e=story;path=setup(e,kind);e=scoped(e,monkeypatch);token={'X-Session-Token':e.lead};role=grant(e)
    first=checked(e.client.put(path,headers=token,json={'record':payload(kind),'expected_digest':None,'expected_version':0}))
    writer=e.bundle.novels.compare_and_swap_record
    def revoke_before_write(*args,**kwargs):
        if revoke=='permission':e.authorization.revoke_role(role.id,e.lead)
        else:monkeypatch.setenv('EXPERIMENTAL_FEATURES','')
        return writer(*args,**kwargs)
    monkeypatch.setattr(e.bundle.novels,'compare_and_swap_record',revoke_before_write)
    response=e.client.put(path,headers=token,json={'record':payload(kind,'Must not commit'),'expected_digest':first['digest'],'expected_version':1})
    assert response.status_code==(403 if revoke=='permission' else 404)
    assert e.novels.story_record(e.nid,kind,'exact-original')==first


@pytest.mark.parametrize('kind',KINDS)
def test_input_boundaries_opaque_client_fields_and_no_blind_recreate(story,kind):
    e=story;path=setup(e,kind)
    data={'record':payload(kind),'expected_digest':None,'expected_version':0}
    for key in ['_story_record','import_extension','id','privacy_status']:
        assert e.client.put(path,json={**data,'record':{**payload(kind),key:'forbidden'}}).status_code==422
    required='source_character_id' if kind=='relationships' else 'name'
    assert e.client.put(path,json={**data,'record':{**payload(kind),required:'   '}}).status_code==422
    assert e.client.put(path,json={**data,'record':{**payload(kind),required:'x'*128001}}).status_code==413
    assert e.client.get(path).status_code==404
    if kind=='relationships':
        for field in ['source_character_id','target_character_id','valid_from_event_id','valid_to_event_id']:
            assert e.client.put(path,json={**data,'record':{**payload(kind),field:'foreign-or-missing'}}).status_code==404
        assert e.client.put(path,json={**data,'record':{**payload(kind),'target_character_id':'a'}}).status_code==422
    first=checked(e.client.put(path,json=data))
    assert e.client.put(path,json=data).status_code==409
    assert checked(e.client.get(path))['digest']==first['digest']
