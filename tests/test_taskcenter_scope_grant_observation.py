"""Original-owner lifecycle evidence; these probes never dispatch work."""
import json
from copy import deepcopy
from dataclasses import asdict
from uuid import uuid4

import pytest

from app.authorization import AuthorizationScope, ScopeKind, ModalityDomain
from app.collaboration import CollaborationScope
from app.repositories.file.scope import FileScopeRepository, FileAuthorizationRepository
from app.services.authorization_service import AuthorizationService
from app.services.collaboration_scope_service import CollaborationScopeService

SCOPE = CollaborationScope('w', 'p', 's', 'b')
AUTH_SCOPE = AuthorizationScope(ScopeKind.BRANCH, 'w', 'p', 's', 'b')

class Novels:
    def get(self, project):
        if project != 'p':
            raise FileNotFoundError(project)
        return {'id': project}

@pytest.fixture
def owners(tmp_path):
    scopes = FileScopeRepository(tmp_path)
    for kind, row in (
        ('workspaces', {'id': 'w', 'name': 'workspace'}),
        ('project_workspaces', {'id': 'p', 'workspace_id': 'w'}),
        ('storylines', {'id': 's', 'workspace_id': 'w', 'project_id': 'p'}),
        ('branches', {'id': 'b', 'workspace_id': 'w', 'project_id': 'p', 'storyline_id': 's'}),
    ):
        scopes.create(kind, row)
    grants = FileAuthorizationRepository(tmp_path)
    row = {'id': 'g', 'principal_id': 'u', 'permission': 'domain.read', 'domain': 'NOVEL',
           'scope': {'kind': 'WORKSPACE', 'workspace_id': 'w', 'project_id': None, 'storyline_id': None, 'branch_id': None}}
    grants.save_permission_assignment(row)
    service = AuthorizationService(grants, CollaborationScopeService(scopes, Novels()))
    return scopes, grants, service, row

def observe(grants, service):
    return grants.binding_observation(service, 'u', 'domain.read', ModalityDomain.NOVEL, AUTH_SCOPE)

def test_capture_is_read_only_and_reload_stable(owners):
    scopes, grants, service, _ = owners
    before = [p.read_bytes() for p in (scopes.path, grants.path)]
    a, b = scopes.binding_observation(SCOPE), observe(grants, service)
    assert scopes.revalidate_binding(SCOPE, a)
    assert grants.revalidate_binding(service, 'u', 'domain.read', ModalityDomain.NOVEL, AUTH_SCOPE, b)
    assert FileScopeRepository(scopes.path.parent).binding_observation(SCOPE) == a
    assert [p.read_bytes() for p in (scopes.path, grants.path)] == before

@pytest.mark.parametrize('kind', ['workspaces', 'project_workspaces', 'storylines', 'branches'])
def test_scope_delete_recreate_identical_row_changes_lifecycle(owners, kind):
    scopes, _, _, _ = owners
    before = scopes.binding_observation(SCOPE)
    data = scopes._read(); row = deepcopy(data[kind][0]); data[kind] = []; scopes._write(data)
    scopes.create(kind, row)
    assert not scopes.revalidate_binding(SCOPE, before)

@pytest.mark.parametrize('kind,field,value', [('project_workspaces','workspace_id','other'), ('storylines','project_id','other'), ('branches','parent_branch_id','ancestor')])
def test_scope_topology_aba_detected(owners, kind, field, value):
    scopes, _, _, _ = owners
    before = scopes.binding_observation(SCOPE)
    data = scopes._read(); original = deepcopy(data[kind][0]); data[kind][0][field] = value; scopes._write(data)
    data = scopes._read(); data[kind][0] = original; scopes._write(data)
    assert not scopes.revalidate_binding(SCOPE, before)

def test_revision_presentation_unrelated_scope_changes_do_not_invalidate(owners):
    scopes, _, _, _ = owners
    before = scopes.binding_observation(SCOPE)
    scopes.compare_and_increment(SCOPE, 0)
    data = scopes._read(); data['workspaces'][0].update(name='renamed',updated_at='later'); data['branches'][0]['name']='renamed'; scopes._write(data)
    scopes.create('branches', {'id':'unrelated','workspace_id':'w','project_id':'p','storyline_id':'s'})
    assert scopes.binding_observation(SCOPE) == before

@pytest.mark.parametrize('kind', ['role', 'permission'])
def test_selected_grant_revoke_restore_aba_detected(owners, kind):
    _, grants, service, row = owners
    if kind == 'role':
        row = {k:v for k,v in row.items() if k != 'permission'}; row.update(id='role', role='DOMAIN_LEAD')
        grants.save_role_assignment(row)
    before = observe(grants, service)
    method = getattr(grants, 'revoke_' + kind + '_assignment_with_audit')
    method(row['id'], {'id':'audit','scope':row['scope']})
    getattr(grants, 'save_' + kind + '_assignment')(row)
    assert observe(grants, service) != before

def test_admin_override_uses_original_cross_domain_policy(owners):
    _, grants, service, row = owners
    grants.revoke_permission_assignment_with_audit('g', {'id':'revoke'})
    role = {k:v for k,v in row.items() if k != 'permission'}; role.update(role='ADMIN',domain='IMAGE')
    grants.save_role_assignment(role)
    assert service.explain('u','domain.read',ModalityDomain.NOVEL,AUTH_SCOPE)['sources'][0]['source_type']=='ADMIN_OVERRIDE'
    assert observe(grants,service)['rows'][0]['kind']=='role_assignments'

def test_unrelated_grants_audit_and_actor_do_not_invalidate(owners):
    _, grants, service, row = owners
    before = observe(grants, service)
    grants.save_permission_assignment({**row,'id':'other-actor','principal_id':'v'})
    grants.save_permission_assignment({**row,'id':'other-permission','permission':'domain.write','domain':'IMAGE'})
    grants.append_audit_event({'id':'unrelated-audit'})
    assert observe(grants, service) == before

def test_revoked_authorization_is_not_empty_success(owners):
    _, grants, service, _ = owners
    grants.revoke_permission_assignment_with_audit('g', {'id':'revoke'})
    with pytest.raises(PermissionError): observe(grants, service)

def test_original_project_retirement_changes_scope_and_grants(owners):
    scopes, grants, service, row = owners
    project_row = {**row, 'id':'project-grant','scope':{**row['scope'],'kind':'PROJECT','project_id':'p'}}
    grants.save_permission_assignment(project_row)
    before = observe(grants, service)
    grants.retire_project('p')
    assert observe(grants, service) != before
    scopes.retire_project('p')
    with pytest.raises(ValueError): scopes.binding_observation(SCOPE)

@pytest.mark.parametrize('owner,key', [('scope','_scope_lifecycle_v1'),('grant','_grant_lifecycle_v1')])
@pytest.mark.parametrize('legacy', [False, True])
def test_reserved_null_injection_is_rejected_without_write(tmp_path, owner, key, legacy):
    repo = FileScopeRepository(tmp_path) if owner=='scope' else FileAuthorizationRepository(tmp_path)
    data=repo._read()
    if legacy: repo.path.write_text(json.dumps(data))
    before=repo.path.read_bytes() if repo.path.exists() else None
    data[key]=None
    with pytest.raises(ValueError, match='owner-managed'): repo._write(data)
    assert (repo.path.read_bytes() if repo.path.exists() else None)==before

@pytest.mark.parametrize('owner,key', [('scope','_scope_lifecycle_v1'),('grant','_grant_lifecycle_v1')])
def test_legacy_business_write_does_not_bind(owners, owner, key):
    scopes, grants, service, row = owners
    repo=scopes if owner=='scope' else grants
    data=repo._read();data.pop(key);repo.path.write_text(json.dumps(data))
    if owner=='scope':
        scopes.create('workspaces',{'id':'extra'})
        with pytest.raises(ValueError): scopes.binding_observation(SCOPE)
    else:
        grants.append_audit_event({'id':'extra'})
        with pytest.raises(ValueError): observe(grants,service)
    assert key not in json.loads(repo.path.read_text())

@pytest.mark.parametrize('owner,key', [('scope','_scope_lifecycle_v1'),('grant','_grant_lifecycle_v1')])
@pytest.mark.parametrize('change', ['remove','null','nonce','rows'])
def test_owned_metadata_cannot_be_mutated(owners, owner, key, change):
    scopes,grants,_,_=owners;repo=scopes if owner=='scope' else grants
    before=repo.path.read_bytes();data=repo._read()
    if change=='remove':data.pop(key)
    elif change=='null':data[key]=None
    elif change=='nonce':data[key]['incarnation']=str(uuid4())
    else:data[key]['rows']={}
    with pytest.raises(ValueError,match='owner-managed'):repo._write(data)
    assert repo.path.read_bytes()==before

@pytest.mark.parametrize('owner,key', [('scope','_scope_lifecycle_v1'),('grant','_grant_lifecycle_v1')])
def test_invalid_persisted_metadata_fails_closed_without_repair(owners,owner,key):
    scopes,grants,service,_=owners;repo=scopes if owner=='scope' else grants
    data=repo._read();data[key]['schema_version']=True;repo.path.write_text(json.dumps(data));before=repo.path.read_bytes()
    with pytest.raises(ValueError):repo._read()
    assert repo.path.read_bytes()==before

@pytest.mark.parametrize('owner', ['scope','grant'])
def test_atomic_write_failure_preserves_business_and_evidence(owners,monkeypatch,owner):
    scopes,grants,_,row=owners;repo=scopes if owner=='scope' else grants;before=repo.path.read_bytes()
    import app.repositories.file.scope as module
    def fail(*args,**kwargs):raise OSError('injected')
    monkeypatch.setattr(module,'atomic_write',fail)
    with pytest.raises(OSError):
        if owner=='scope':scopes.compare_and_increment(SCOPE,0)
        else:grants.save_permission_assignment({**row,'id':'new'})
    assert repo.path.read_bytes()==before

def test_workspace_compensation_restores_same_file_metadata(owners,monkeypatch):
    scopes,grants,_,_=owners
    paths=[scopes.path,grants.path,scopes.path.with_name('identity.json')]
    before={p:p.read_bytes() if p.exists() else None for p in paths}
    def fail(*args,**kwargs):raise OSError('audit failed')
    monkeypatch.setattr(FileAuthorizationRepository,'save_role_assignment_with_audit',fail)
    with pytest.raises(OSError):scopes.create_workspace('new','new','u')
    assert {p:p.read_bytes() if p.exists() else None for p in paths}==before
