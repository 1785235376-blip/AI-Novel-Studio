import pytest

from app.actor_context import ActorContext, SessionContext
from app.authorization import AuthorizationScope, DomainRole, DomainRoleAssignment, ModalityDomain, ScopeKind
from app.collaboration import Workspace
from app.identity import IdentityStatus, User, WorkspaceMembership
from app.repositories.file.identity import FileIdentityRepository
from app.repositories.file.scope import FileAuthorizationRepository, FileScopeRepository
from app.services.authorization_service import AuthorizationService
from app.services.collaboration_scope_service import CollaborationScopeService
from app.services.identity_service import IdentityService
from app.services.membership_authorization_service import MembershipAuthorizationService


class Novels:
    def get(self, item):
        return {"id": item}


def setup_services(tmp_path):
    scopes = CollaborationScopeService(FileScopeRepository(tmp_path), Novels())
    scopes.create_workspace(Workspace("w1", "One"))
    scopes.create_workspace(Workspace("w2", "Two"))
    identity = IdentityService(FileIdentityRepository(tmp_path), scopes)
    authorization = AuthorizationService(FileAuthorizationRepository(tmp_path), scopes)
    return identity, authorization


def actor(user_id="alice", workspace_id="w1", client_id="computer-a"):
    session = SessionContext("session-a", client_id, user_id, workspace_id, "request-1")
    return ActorContext(user_id, workspace_id, session)


def test_create_read_and_membership_cardinality(tmp_path):
    identity, _ = setup_services(tmp_path)
    identity.create_user(User("alice", "Alice"))
    identity.create_user(User("bob", "Bob"))
    identity.add_membership(WorkspaceMembership("m1", "alice", "w1"))
    identity.add_membership(WorkspaceMembership("m2", "alice", "w2"))
    identity.add_membership(WorkspaceMembership("m3", "bob", "w1"))
    assert identity.get_user("alice").display_name == "Alice"
    assert len(identity.repository.list_memberships(user_id="alice")) == 2
    assert len(identity.repository.list_memberships(workspace_id="w1")) == 2


def test_actor_context_is_explicitly_session_and_scope_bound():
    assert actor().effective_correlation_id == "request-1"
    assert actor(client_id="computer-b").client_id == "computer-b"
    mismatched = SessionContext("s", "c", "alice", "w2")
    with pytest.raises(ValueError):
        ActorContext("alice", "w1", mismatched)


def test_inactive_and_non_member_are_denied_before_permission_lookup(tmp_path):
    identity, authorization = setup_services(tmp_path)
    identity.create_user(User("inactive", "Inactive"))
    identity.add_membership(WorkspaceMembership("m1", "inactive", "w1", IdentityStatus.INACTIVE))
    scope = AuthorizationScope(ScopeKind.WORKSPACE, "w1")
    authorization.assign_role(DomainRoleAssignment("r1", "inactive", DomainRole.ADMIN, ModalityDomain.NOVEL, scope, "owner"))
    service = MembershipAuthorizationService(identity, authorization)
    assert not service.is_allowed(actor("inactive"), "anything", ModalityDomain.VIDEO, scope)
    assert not service.is_allowed(actor("missing"), "anything", ModalityDomain.NOVEL, scope)


def test_membership_does_not_grant_permission_and_existing_roles_are_reused(tmp_path):
    identity, authorization = setup_services(tmp_path)
    for user_id in ("member", "admin", "lead"):
        identity.create_user(User(user_id, user_id.title()))
        identity.add_membership(WorkspaceMembership(f"m-{user_id}", user_id, "w1"))
    scope = AuthorizationScope(ScopeKind.WORKSPACE, "w1")
    authorization.assign_role(DomainRoleAssignment("r-admin", "admin", DomainRole.ADMIN, ModalityDomain.IMAGE, scope, "owner"))
    authorization.assign_role(DomainRoleAssignment("r-lead", "lead", DomainRole.DOMAIN_LEAD, ModalityDomain.NOVEL, scope, "owner"))
    service = MembershipAuthorizationService(identity, authorization)
    assert not service.is_allowed(actor("member"), "domain.read", ModalityDomain.NOVEL, scope)
    assert service.is_allowed(actor("admin"), "unlisted.action", ModalityDomain.VIDEO, scope)
    assert service.is_allowed(actor("lead"), "domain.write", ModalityDomain.NOVEL, scope)
    assert not service.is_allowed(actor("lead"), "domain.write", ModalityDomain.IMAGE, scope)
    assert not service.is_allowed(actor("admin"), "anything", ModalityDomain.VIDEO, AuthorizationScope(ScopeKind.WORKSPACE, "w2"))
