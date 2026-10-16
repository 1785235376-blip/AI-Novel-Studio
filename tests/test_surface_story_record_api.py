"""Mounted application aliases; real original project/session authority."""
from uuid import uuid4
import pytest
from app.authorization import AuthorizationScope, DomainRole, DomainRoleAssignment, ModalityDomain, ScopeKind
from test_r3_mounted_contracts import mounted,prefix,scoped,checked


@pytest.fixture
def story(mounted,monkeypatch):
    import app.dependencies as dependencies
    e=mounted
    # Production router captures the original owner, not a replacement service.
    monkeypatch.setattr(dependencies.novel_service,'novels',e.bundle.novels)
    monkeypatch.setattr(dependencies.novel_service,'chapters',e.bundle.chapters)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','story_record_versions_v1')
    e.story=e.base+'/story-records'
    return e


def save(e,title='Initial',headers=None):
    return e.client.put(e.story+'/timeline/event',headers=headers or {},json={'record':{'title':title,'chapter_id':e.chapter['id'],'location':'city'},'expected_digest':None,'expected_version':0})


def test_mounted_local_no_token_flag_v1_cas_restore_unknown_input_and_cancel(story,monkeypatch):
    e=story
    assert checked(e.client.get(e.story+'/catalog'))['scope']=='PROJECT'
    row=checked(save(e));assert row['version']==1
    assert checked(e.client.get(e.prefix+f'/novels/{e.nid}/timeline'))[0]==row['record']
    latest=checked(e.client.get(e.story+'/timeline/event'));assert latest['digest']==row['digest']
    request={'record':{'title':'Changed'},'expected_digest':row['digest'],'expected_version':1}
    updated=checked(e.client.put(e.story+'/timeline/event',json=request))
    denied=e.client.put(e.story+'/timeline/event',json=request)
    assert denied.status_code==409 and 'Changed' not in denied.text and 'history' not in denied.text
    assert e.client.put(e.story+'/timeline/event',json={**request,'expected_digest':updated['digest'],'expected_version':2,'record':{'title':'Bad','extra':True}}).status_code==422
    assert e.client.post(e.story+'/timeline/event/restore',json={'expected_digest':updated['digest'],'expected_version':2,'restore_version':1,'confirmed':False}).status_code==422
    # Cancel before dispatch is a local UI action, no server mutation.
    assert checked(e.client.get(e.story+'/timeline/event'))['version']==2
    restored=checked(e.client.post(e.story+'/timeline/event/restore',json={'expected_digest':updated['digest'],'expected_version':2,'restore_version':1,'confirmed':True}))
    assert restored['version']==3 and restored['record']==row['record']
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','')
    assert e.client.get(e.story+'/catalog').status_code==404
    assert checked(e.client.get(e.prefix+f'/novels/{e.nid}/timeline'))[0]==restored['record']
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','story_record_versions_v1');monkeypatch.setenv('V1_ACCEPTANCE_MODE','true')
    assert e.client.get(e.story+'/timeline/event').status_code==404


def test_project_grants_branch_rejected_review_terminal_and_revocation(story,monkeypatch):
    e=scoped(story,monkeypatch);token={'X-Session-Token':e.lead}
    assert e.client.get(e.story+'/catalog').status_code==401
    # A branch domain lead is not a project authority, even without a header.
    assert e.client.get(e.story+'/catalog',headers=token).status_code==403
    role=DomainRoleAssignment('project-'+uuid4().hex,e.lead,DomainRole.DOMAIN_LEAD,ModalityDomain.NOVEL,AuthorizationScope(ScopeKind.PROJECT,e.workspace,e.nid),e.lead)
    e.authorization.assign_role(role)
    assert e.client.get(e.story+'/catalog',headers=e.headers).status_code==409
    row=checked(save(e,headers=token))
    assert e.client.put(e.story+'/timeline/event',headers=e.viewer_headers,json={'record':{'title':'No'},'expected_digest':row['digest'],'expected_version':1}).status_code==403
    feedback={'expected_digest':row['digest'],'expected_version':1,'decision':'INTENTIONAL','note':'Human choice','evidence':'Scene reference'}
    reviewed=checked(e.client.post(e.story+'/timeline/event/feedback',headers=token,json=feedback));assert reviewed['version']==2
    feedback['expected_version']=2
    assert e.client.post(e.story+'/timeline/event/feedback',headers=token,json=feedback).status_code==409
    e.authorization.revoke_role(role.id,e.lead)
    assert e.client.get(e.story+'/timeline/event',headers=token).status_code==403
    assert e.client.post(e.story+'/timeline/event/feedback',headers=token,json=feedback).status_code==403
    assert e.novels.story_record(e.nid,'timeline','event')['version']==2


def test_permission_rechecked_inside_commit_preserves_original_record(story,monkeypatch):
    e=scoped(story,monkeypatch);token={'X-Session-Token':e.lead}
    role=DomainRoleAssignment('project-'+uuid4().hex,e.lead,DomainRole.DOMAIN_LEAD,ModalityDomain.NOVEL,AuthorizationScope(ScopeKind.PROJECT,e.workspace,e.nid),e.lead)
    e.authorization.assign_role(role);row=checked(save(e,headers=token))
    original=e.bundle.novels.compare_and_swap_record
    def revoking(*args,**kwargs):
        e.authorization.revoke_role(role.id,e.lead)
        return original(*args,**kwargs)
    monkeypatch.setattr(e.bundle.novels,'compare_and_swap_record',revoking)
    response=e.client.put(e.story+'/timeline/event',headers=token,json={'record':{'title':'No stale access'},'expected_digest':row['digest'],'expected_version':1})
    assert response.status_code==403 and e.novels.story_record(e.nid,'timeline','event')['record']==row['record']


def test_oversize_unknown_fields_foreign_source_and_read_revocation(story,monkeypatch):
    e=story
    assert e.client.put(e.story+'/timeline/event',json={'record':{'title':'Large','description':'x'*128001},'expected_digest':None,'expected_version':0}).status_code==413
    assert e.client.put(e.story+'/timeline/event',json={'record':{'title':'Injected','_story_record':{'version':999}},'expected_digest':None,'expected_version':0}).status_code==422
    other=e.novels.create({'title':'Other synthetic project'})
    foreign=e.bundle.chapters.create(other['id'],{'title':'Foreign','content':'Synthetic'})
    try:
        assert e.client.put(e.story+'/timeline/event',json={'record':{'title':'Foreign source','chapter_id':foreign['id']},'expected_digest':None,'expected_version':0}).status_code==404
        assert e.client.get(e.story+'/timeline/event').status_code==404
    finally:e.novels.delete(other['id'])
    row=checked(save(e))
    e=scoped(story,monkeypatch);token={'X-Session-Token':e.lead}
    role=DomainRoleAssignment('project-'+uuid4().hex,e.lead,DomainRole.DOMAIN_LEAD,ModalityDomain.NOVEL,AuthorizationScope(ScopeKind.PROJECT,e.workspace,e.nid),e.lead)
    e.authorization.assign_role(role)
    original=e.bundle.novels.story_record
    def revoke_during_read(*args,**kwargs):
        result=original(*args,**kwargs);e.authorization.revoke_role(role.id,e.lead);return result
    monkeypatch.setattr(e.bundle.novels,'story_record',revoke_during_read)
    denied=e.client.get(e.story+'/timeline/event',headers=token)
    assert denied.status_code==403 and row['record']['title'] not in denied.text and 'history' not in denied.text


def test_flag_revoked_inside_commit_rolls_back_without_changing_original(story,monkeypatch):
    e=story;row=checked(save(e));original=e.bundle.novels.compare_and_swap_record
    def disable_during_commit(*args,**kwargs):
        monkeypatch.setenv('EXPERIMENTAL_FEATURES','');return original(*args,**kwargs)
    monkeypatch.setattr(e.bundle.novels,'compare_and_swap_record',disable_during_commit)
    denied=e.client.put(e.story+'/timeline/event',json={'record':{'title':'Must not commit'},'expected_digest':row['digest'],'expected_version':1})
    assert denied.status_code==404
    assert e.novels.story_record(e.nid,'timeline','event')['record']==row['record']
    assert e.novels.story_record(e.nid,'timeline','event')['version']==1
