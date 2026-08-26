from uuid import uuid4

from fastapi.testclient import TestClient

from app.actor_context import SessionContext
from app.authorization import AuthorizationScope,DomainRole,DomainRoleAssignment,ModalityDomain,ScopeKind
from app.collaboration import Branch,Storyline,Workspace
from app.dependencies import authorization_service,collaboration_scope_service,identity_service,trusted_session_resolver
from app.identity import User,WorkspaceMembership
from app.main import app


def setup_scope():
    suffix=uuid4().hex;workspace=f"adapt-w-{suffix}";novel=f"adapt-n-{suffix}";story=f"adapt-s-{suffix}";branch=f"adapt-b-{suffix}"
    collaboration_scope_service.create_workspace(Workspace(workspace,"Adaptation Workspace"))
    client=TestClient(app);client.post('/api/novels',json={'id':novel,'title':'改编原作'});client.post(f'/api/novels/{novel}/chapters',json={'title':'第一章','content':'敏感原作正文'})
    collaboration_scope_service.link_project(workspace,novel);collaboration_scope_service.create_storyline(Storyline(story,workspace,novel,"Main"));collaboration_scope_service.create_branch(Branch(branch,workspace,novel,story,"Main"))
    scope=AuthorizationScope(ScopeKind.BRANCH,workspace,novel,story,branch)
    headers={}
    for role in ('member','lead','admin'):
        user=f"{role}-{suffix}";identity_service.create_user(User(user,role));identity_service.add_membership(WorkspaceMembership(f"m-{user}",user,workspace));token=f"t-{user}";trusted_session_resolver.register(token,SessionContext(f"s-{user}",f"c-{user}",user,workspace));headers[role]={'X-Session-Token':token}
    authorization_service.assign_role(DomainRoleAssignment(f"lead-role-{suffix}",f"lead-{suffix}",DomainRole.DOMAIN_LEAD,ModalityDomain.NOVEL,scope,f"admin-{suffix}"))
    authorization_service.assign_role(DomainRoleAssignment(f"admin-role-{suffix}",f"admin-{suffix}",DomainRole.ADMIN,ModalityDomain.NOVEL,AuthorizationScope(ScopeKind.WORKSPACE,workspace),f"admin-{suffix}"))
    return client,novel,branch,scope,headers


def test_team_adaptation_capability_matrix_and_cross_workspace_rejection():
    client,novel,branch,_,headers=setup_scope();params={'branch_id':branch}
    assert client.get(f'/api/novels/{novel}/adaptations',params=params,headers=headers['member']).status_code==403
    assert client.post(f'/api/novels/{novel}/adaptations',params=params,headers=headers['member'],json={'target':'SCREEN'}).status_code==403
    created=client.post(f'/api/novels/{novel}/adaptations',params=params,headers=headers['lead'],json={'target':'SCREEN','instruction':'敏感改编要求'}).json()
    assert client.get(f'/api/novels/{novel}/adaptations',params=params,headers=headers['lead']).status_code==200
    assert client.post(f"/api/novels/{novel}/adaptations/{created['id']}/approve",params=params,headers=headers['lead']).status_code==200
    assert client.post(f'/api/novels/{novel}/adaptations',params=params,headers={'X-Session-Token':'invalid'},json={'target':'SCREEN'}).status_code==401


def test_team_adaptation_audit_is_content_free():
    client,novel,branch,scope,headers=setup_scope();params={'branch_id':branch}
    created=client.post(f'/api/novels/{novel}/adaptations',params=params,headers=headers['admin'],json={'target':'LITERARY','instruction':'不得写入审计的秘密要求'}).json()
    client.post(f"/api/novels/{novel}/adaptations/{created['id']}/approve",params=params,headers=headers['admin'])
    events=[event for event in authorization_service.repository.list_audit_events(scope) if event['target_type']=='AdaptationProposal']
    assert {event['action'] for event in events}=={'ADAPTATION_PROPOSAL_CREATED','ADAPTATION_PROPOSAL_APPROVED'}
    serialized=str([event['metadata'] for event in events])
    assert '秘密要求' not in serialized and '敏感原作正文' not in serialized and 'instruction' not in serialized.lower() and 'content' not in serialized.lower()
    assert all(event['actor_id'].startswith(('admin-','lead-')) for event in events)


def test_team_adaptation_materializes_scoped_project_and_is_idempotent():
    client,novel,branch,scope,headers=setup_scope();params={'branch_id':branch}
    created=client.post(f'/api/novels/{novel}/adaptations',params=params,headers=headers['admin'],json={'target':'SCREEN','title':'影视改编版'}).json()
    client.post(f"/api/novels/{novel}/adaptations/{created['id']}/approve",params=params,headers=headers['admin'])
    endpoint=f"/api/novels/{novel}/adaptations/{created['id']}/materialize"
    first=client.post(endpoint,params=params,headers=headers['admin']);second=client.post(endpoint,params=params,headers=headers['admin'])
    assert first.status_code==201 and second.status_code==201 and first.json()['id']==second.json()['id']
    target=first.json()['scope'];assert target['project_id']!=novel and target['branch_id']
    chapters=client.get(f"/api/collaboration/workspaces/{target['workspace_id']}/projects/{target['project_id']}/storylines/{target['storyline_id']}/branches/{target['branch_id']}/chapters",headers=headers['admin']).json()['items']
    assert len(chapters)==1 and chapters[0]['title']=='第一章'
    actions={event['action'] for event in authorization_service.repository.list_audit_events(scope)}
    assert 'ADAPTATION_MATERIALIZED' in actions
