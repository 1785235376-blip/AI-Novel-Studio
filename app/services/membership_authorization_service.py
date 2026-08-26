from __future__ import annotations

from ..actor_context import ActorContext


class MembershipAuthorizationService:
    """Membership gate composed with, not replacing, AuthorizationService."""

    def __init__(self, identity_service, authorization_service):
        self.identity_service = identity_service
        self.authorization_service = authorization_service

    def is_allowed(self, actor: ActorContext, permission, domain, scope) -> bool:
        if actor.workspace_id != scope.workspace_id:
            return False
        try:
            self.identity_service.require_active_membership(actor.actor_id, scope.workspace_id)
        except (KeyError, PermissionError):
            return False
        return self.authorization_service.is_allowed(actor.actor_id, permission, domain, scope)

    def require(self, actor: ActorContext, permission, domain, scope) -> None:
        if actor.workspace_id != scope.workspace_id:
            raise PermissionError("actor workspace does not match scope")
        self.identity_service.require_active_membership(actor.actor_id, scope.workspace_id)
        self.authorization_service.require(actor.actor_id, permission, domain, scope)
