from app.actor_context import ActorContext,SessionContext
from app.authorization import AuthorizationScope,DomainRole,DomainRoleAssignment,ModalityDomain,ScopeKind
from app.collaboration import Branch,Storyline,Workspace
from app.identity import User,WorkspaceMembership
from app.repositories.file.identity import FileIdentityRepository
from app.repositories.file.scope import FileAuthorizationRepository,FileScopeRepository
from app.services.authorization_service import AuthorizationService
from app.services.collaboration_scope_service import CollaborationScopeService
from app.services.identity_service import IdentityService
from app.services.membership_authorization_service import MembershipAuthorizationService


class Novels:
    def get(self,novel_id):return {"id":novel_id}


def authorization_stack(tmp_path):
    scopes=CollaborationScopeService(FileScopeRepository(tmp_path),Novels())
    scopes.create_workspace(Workspace("w","Workspace"));scopes.link_project("w","p")
    scopes.create_storyline(Storyline("s","w","p","Story"));scopes.create_branch(Branch("b","w","p","s","Main"))
    identity=IdentityService(FileIdentityRepository(tmp_path),scopes)
    authorization=AuthorizationService(FileAuthorizationRepository(tmp_path),scopes)
    for user in ("member","lead","admin"):
        identity.create_user(User(user,user.title()));identity.add_membership(WorkspaceMembership(f"m:{user}",user,"w"))
    scope=AuthorizationScope(ScopeKind.BRANCH,"w","p","s","b")
    authorization.assign_role(DomainRoleAssignment("lead-role","lead",DomainRole.DOMAIN_LEAD,ModalityDomain.NOVEL,scope,"admin"))
    authorization.assign_role(DomainRoleAssignment("admin-role","admin",DomainRole.ADMIN,ModalityDomain.NOVEL,AuthorizationScope(ScopeKind.WORKSPACE,"w"),"admin"))
    return MembershipAuthorizationService(identity,authorization),scope


def actor(user):return ActorContext(user,"w",SessionContext(f"session:{user}",f"client:{user}",user,"w"))


def test_agent_job_capability_matrix_uses_real_membership_and_roles(tmp_path):
    service,scope=authorization_stack(tmp_path)
    for permission in ("domain.read","domain.write","domain.review"):
        assert not service.is_allowed(actor("member"),permission,ModalityDomain.NOVEL,scope)
        assert service.is_allowed(actor("lead"),permission,ModalityDomain.NOVEL,scope)
        assert service.is_allowed(actor("admin"),permission,ModalityDomain.NOVEL,scope)


def test_agent_job_capabilities_reject_cross_workspace_actor(tmp_path):
    service,scope=authorization_stack(tmp_path)
    outsider=ActorContext("lead","other",SessionContext("session","client","lead","other"))
    assert not service.is_allowed(outsider,"domain.read",ModalityDomain.NOVEL,scope)
