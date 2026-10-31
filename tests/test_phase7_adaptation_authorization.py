from uuid import uuid4

import pytest

from fastapi.testclient import TestClient

from app.actor_context import SessionContext
from app.authorization import AuthorizationScope,DomainRole,DomainRoleAssignment,ModalityDomain,ScopeKind
from app.collaboration import Branch,Storyline,Workspace
from app.dependencies import (authorization_service, branch_manuscript_service, chapter_service,
                              collaboration_application_service, collaboration_scope_service,
                              identity_service, trusted_session_resolver)
from app.document import markdown_to_document
from app.identity import User,WorkspaceMembership
from app.main import app


@pytest.fixture(autouse=True)
def branch_manuscript_opt_in(monkeypatch):
    # Branch routes deliberately fail closed unless the real manuscript owner is opted in.
    # Keep adaptation_lifecycle_v1 off: this suite covers the legacy proposal API.
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "branch_manuscript_v1")
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)


def setup_scope():
    suffix=uuid4().hex;workspace=f"adapt-w-{suffix}";novel=f"adapt-n-{suffix}";story=f"adapt-s-{suffix}";branch=f"adapt-b-{suffix}"
    collaboration_scope_service.create_workspace(Workspace(workspace,"Adaptation Workspace"))
    client=TestClient(app)
    created=client.post('/api/novels',json={'id':novel,'title':'改编原作'})
    assert created.status_code==201,created.text
    # A distinct mainline decoy proves branch adaptations never fall back to it.
    mainline=client.post(f'/api/novels/{novel}/chapters',json={'title':'主线非来源','content':'主线非来源正文'})
    assert mainline.status_code==201,mainline.text
    collaboration_scope_service.link_project(workspace,novel);collaboration_scope_service.create_storyline(Storyline(story,workspace,novel,"Main"));collaboration_scope_service.create_branch(Branch(branch,workspace,novel,story,"Main"))
    scope=AuthorizationScope(ScopeKind.BRANCH,workspace,novel,story,branch)
    headers={}
    for role in ('member','lead','admin'):
        user=f"{role}-{suffix}";identity_service.create_user(User(user,role));identity_service.add_membership(WorkspaceMembership(f"m-{user}",user,workspace));token=f"t-{user}";trusted_session_resolver.register(token,SessionContext(f"s-{user}",f"c-{user}",user,workspace));headers[role]={'X-Session-Token':token}
    authorization_service.assign_role(DomainRoleAssignment(f"lead-role-{suffix}",f"lead-{suffix}",DomainRole.DOMAIN_LEAD,ModalityDomain.NOVEL,scope,f"admin-{suffix}"))
    authorization_service.assign_role(DomainRoleAssignment(f"admin-role-{suffix}",f"admin-{suffix}",DomainRole.ADMIN,ModalityDomain.NOVEL,AuthorizationScope(ScopeKind.WORKSPACE,workspace),f"admin-{suffix}"))
    path=f'/api/collaboration/workspaces/{workspace}/projects/{novel}/storylines/{story}/branches/{branch}/chapters'
    created=client.post(path,headers=headers['admin'],json={'title':'第一章'})
    assert created.status_code==201,created.text
    actor=trusted_session_resolver.resolve(headers['admin']['X-Session-Token'])
    saved=collaboration_application_service.update_chapter(
        actor=actor,scope=scope,chapter_id=created.json()['id'],
        document=markdown_to_document('# 第一章\n\n敏感原作正文'),
        expected_version=created.json()['version'])
    assert saved['branch_id']==branch and '敏感原作正文' in saved['content']
    return client,novel,branch,scope,headers


def test_team_adaptation_capability_matrix_and_cross_workspace_rejection():
    client,novel,branch,_,headers=setup_scope();params={'branch_id':branch}
    assert client.get(f'/api/novels/{novel}/adaptations',params=params,headers=headers['member']).status_code==403
    assert client.post(f'/api/novels/{novel}/adaptations',params=params,headers=headers['member'],json={'target':'SCREEN'}).status_code==403
    response=client.post(f'/api/novels/{novel}/adaptations',params=params,headers=headers['lead'],json={'target':'SCREEN','instruction':'敏感改编要求'})
    assert response.status_code==201,response.text
    created=response.json()
    assert client.get(f'/api/novels/{novel}/adaptations',params=params,headers=headers['lead']).status_code==200
    assert client.post(f"/api/novels/{novel}/adaptations/{created['id']}/approve",params=params,headers=headers['lead']).status_code==200
    assert client.post(f'/api/novels/{novel}/adaptations',params=params,headers={'X-Session-Token':'invalid'},json={'target':'SCREEN'}).status_code==401
    _,foreign_novel,foreign_branch,_,foreign_headers=setup_scope()
    # Both a valid actor from another workspace and a mismatched branch are forbidden.
    assert client.get(f'/api/novels/{novel}/adaptations',params=params,headers=foreign_headers['admin']).status_code==403
    assert client.post(f'/api/novels/{novel}/adaptations',params={'branch_id':foreign_branch},headers=headers['admin'],json={'target':'SCREEN'}).status_code==403
    assert client.get(f'/api/novels/{foreign_novel}/adaptations',params={'branch_id':foreign_branch},headers=headers['admin']).status_code==403


def test_team_adaptation_audit_is_content_free():
    client,novel,branch,scope,headers=setup_scope();params={'branch_id':branch}
    response=client.post(f'/api/novels/{novel}/adaptations',params=params,headers=headers['admin'],json={'target':'LITERARY','instruction':'不得写入审计的秘密要求'})
    assert response.status_code==201,response.text
    created=response.json()
    approved=client.post(f"/api/novels/{novel}/adaptations/{created['id']}/approve",params=params,headers=headers['admin'])
    assert approved.status_code==200,approved.text
    events=[event for event in authorization_service.repository.list_audit_events(scope) if event['target_type']=='AdaptationProposal']
    assert {event['action'] for event in events}=={'ADAPTATION_PROPOSAL_CREATED','ADAPTATION_PROPOSAL_APPROVED'}
    serialized=str([event['metadata'] for event in events])
    assert '秘密要求' not in serialized and '敏感原作正文' not in serialized and 'instruction' not in serialized.lower() and 'content' not in serialized.lower()
    assert all(event['actor_id'].startswith(('admin-','lead-')) for event in events)


def test_team_adaptation_materializes_scoped_project_and_is_idempotent():
    client,novel,branch,scope,headers=setup_scope();params={'branch_id':branch}
    response=client.post(f'/api/novels/{novel}/adaptations',params=params,headers=headers['admin'],json={'target':'SCREEN','title':'影视改编版'})
    assert response.status_code==201,response.text
    created=response.json()
    approved=client.post(f"/api/novels/{novel}/adaptations/{created['id']}/approve",params=params,headers=headers['admin'])
    assert approved.status_code==200,approved.text
    endpoint=f"/api/novels/{novel}/adaptations/{created['id']}/materialize"
    first=client.post(endpoint,params=params,headers=headers['admin']);second=client.post(endpoint,params=params,headers=headers['admin'])
    assert first.status_code==201 and second.status_code==201 and first.json()['id']==second.json()['id']
    target=first.json()['scope'];assert target['project_id']!=novel and target['branch_id']
    chapters=client.get(f"/api/collaboration/workspaces/{target['workspace_id']}/projects/{target['project_id']}/storylines/{target['storyline_id']}/branches/{target['branch_id']}/chapters",headers=headers['admin']).json()['items']
    assert len(chapters)==1 and chapters[0]['title']=='第一章'
    target_scope=AuthorizationScope(ScopeKind.BRANCH,target['workspace_id'],target['project_id'],target['storyline_id'],target['branch_id'])
    copied=branch_manuscript_service.for_scope(target_scope).get(chapters[0]['id'])
    source=branch_manuscript_service.for_scope(scope).list(novel)
    assert copied['document']==source[0]['document']
    assert copied['id']!=source[0]['id'] and '敏感原作正文' in copied['content']
    assert chapter_service.list(novel)[0]['title']=='主线非来源'
    actions={event['action'] for event in authorization_service.repository.list_audit_events(scope)}
    assert 'ADAPTATION_MATERIALIZED' in actions


def test_team_adaptation_snapshots_original_branch_owner_not_mainline():
    client,novel,branch,scope,headers=setup_scope()
    source=branch_manuscript_service.for_scope(scope).list(novel)
    mainline=chapter_service.list(novel)
    assert len(source)==len(mainline)==1 and source[0]['id']!=mainline[0]['id']
    response=client.post(f'/api/novels/{novel}/adaptations',params={'branch_id':branch},headers=headers['admin'],json={'target':'SCREEN'})
    assert response.status_code==201,response.text
    created=response.json()
    assert created['branch_authority'] is True
    assert created['source_chapter_count']==1
    assert created['source_versions']==[{'chapter_id':source[0]['id'],'version':source[0]['version']}]
    assert created['source_snapshots'][0]['document']==source[0]['document']
    assert branch_manuscript_service.for_scope(scope).list(novel)==source
    assert chapter_service.list(novel)==mainline


def test_team_adaptation_branch_flag_disabled_fails_closed(monkeypatch):
    client,novel,branch,_,headers=setup_scope()
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','')
    for method in ('get','post'):
        kwargs={'json':{'target':'SCREEN'}} if method=='post' else {}
        response=getattr(client,method)(f'/api/novels/{novel}/adaptations',params={'branch_id':branch},headers=headers['admin'],**kwargs)
        assert response.status_code==404
        assert response.json()['detail']=={'code':'EXPERIMENTAL_FEATURE_DISABLED','feature':'branch_manuscript_v1'}
