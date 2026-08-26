import pytest
from app.authorization import *
from app.repositories.file.scope import FileScopeRepository,FileAuthorizationRepository
from app.services.collaboration_scope_service import CollaborationScopeService
from app.services.authorization_service import AuthorizationService
from app.collaboration import Workspace,Storyline,Branch

class Novels:
 def get(self,item):return {"id":item}

def setup(tmp_path):
 scope_service=CollaborationScopeService(FileScopeRepository(tmp_path),Novels());scope_service.create_workspace(Workspace("w","W"));scope_service.link_project("w","p");scope_service.create_storyline(Storyline("s","w","p","S"));scope_service.create_branch(Branch("b1","w","p","s","B1"));scope_service.create_branch(Branch("b2","w","p","s","B2"));return AuthorizationService(FileAuthorizationRepository(tmp_path),scope_service)

def test_domain_lead_inherits_down_scope_and_is_domain_specific(tmp_path):
 service=setup(tmp_path);grant=AuthorizationScope(ScopeKind.PROJECT,"w","p");target=AuthorizationScope(ScopeKind.BRANCH,"w","p","s","b1")
 service.assign_role(DomainRoleAssignment("r","alice",DomainRole.DOMAIN_LEAD,ModalityDomain.NOVEL,grant,"owner"))
 assert service.is_allowed("alice","domain.write",ModalityDomain.NOVEL,target)
 assert not service.is_allowed("alice","domain.write",ModalityDomain.IMAGE,target)
 assert not service.is_allowed("alice","unknown",ModalityDomain.NOVEL,target)

def test_admin_is_not_a_single_global_user_role(tmp_path):
 service=setup(tmp_path);branch=AuthorizationScope(ScopeKind.BRANCH,"w","p","s","b1");other=AuthorizationScope(ScopeKind.BRANCH,"w","p","s","b2")
 service.assign_role(DomainRoleAssignment("r","admin",DomainRole.ADMIN,ModalityDomain.VIDEO,branch,"owner"))
 assert service.is_allowed("admin","anything",ModalityDomain.VIDEO,branch)
 assert service.is_allowed("admin","anything",ModalityDomain.NOVEL,branch)
 assert not service.is_allowed("admin","anything",ModalityDomain.VIDEO,other)

def test_direct_permission_audit_reload_and_immutable_ids(tmp_path):
 service=setup(tmp_path);scope=AuthorizationScope(ScopeKind.WORKSPACE,"w");item=PermissionAssignment("p1","bob","asset.read",ModalityDomain.IMAGE,scope,"owner")
 service.assign_permission(item);assert service.is_allowed("bob","asset.read",ModalityDomain.IMAGE,AuthorizationScope(ScopeKind.BRANCH,"w","p","s","b1"))
 reloaded=setup(tmp_path);assert reloaded.is_allowed("bob","asset.read",ModalityDomain.IMAGE,AuthorizationScope(ScopeKind.PROJECT,"w","p"));assert len(reloaded.repository.list_audit_events())==1
 with pytest.raises(ValueError):reloaded.assign_permission(PermissionAssignment("p1","eve","asset.read",ModalityDomain.IMAGE,scope,"owner"))

def test_invalid_scope_rejected(tmp_path):
 service=setup(tmp_path)
 with pytest.raises(ValueError):service.assign_role(DomainRoleAssignment("x","a",DomainRole.ADMIN,ModalityDomain.NOVEL,AuthorizationScope(ScopeKind.PROJECT,"w","missing"),"owner"))
 with pytest.raises(ValueError):AuthorizationScope(ScopeKind.WORKSPACE,"w","p")

def test_assignment_and_audit_are_one_file_commit(tmp_path,monkeypatch):
 service=setup(tmp_path);repository=service.repository
 monkeypatch.setattr(repository,"_write",lambda *_: (_ for _ in ()).throw(OSError("disk full")))
 with pytest.raises(OSError):service.assign_role(DomainRoleAssignment("atomic","a",DomainRole.ADMIN,ModalityDomain.NOVEL,AuthorizationScope(ScopeKind.WORKSPACE,"w"),"owner"))
 assert repository.list_role_assignments("a")==[] and repository.list_audit_events()==[]
