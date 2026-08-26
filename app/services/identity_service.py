from __future__ import annotations

from dataclasses import asdict
from ..identity import utcnow

from ..identity import IdentityStatus, User, WorkspaceMembership


def serialize(item) -> dict:
    value = asdict(item)
    value["status"] = item.status.value
    return value


def deserialize_user(value: dict) -> User:
    return User(**{**value, "status": IdentityStatus(value["status"])})


def deserialize_membership(value: dict) -> WorkspaceMembership:
    return WorkspaceMembership(**{**value, "status": IdentityStatus(value["status"])})


class IdentityService:
    def __init__(self, repository, scope_service):
        self.repository = repository
        self.scope_service = scope_service

    def create_user(self, user: User) -> User:
        return deserialize_user(self.repository.save_user(serialize(user)))

    def get_user(self, user_id: str) -> User:
        return deserialize_user(self.repository.get_user(user_id))

    def add_membership(self, membership: WorkspaceMembership) -> WorkspaceMembership:
        self.get_user(membership.user_id)
        self.scope_service.get_workspace(membership.workspace_id)
        return deserialize_membership(self.repository.save_membership(serialize(membership)))

    def add_membership_with_audit(self, membership: WorkspaceMembership, audit: dict) -> WorkspaceMembership:
        self.get_user(membership.user_id)
        self.scope_service.get_workspace(membership.workspace_id)
        method = getattr(self.repository, "save_membership_with_audit", None)
        if method is None:
            raise RuntimeError("atomic membership administration port unavailable")
        return deserialize_membership(method(serialize(membership), audit))

    def get_membership(self, user_id: str, workspace_id: str) -> WorkspaceMembership:
        return deserialize_membership(self.repository.get_membership(user_id, workspace_id))

    def remove_membership_with_audit(self, user_id: str, workspace_id: str, audit: dict) -> WorkspaceMembership:
        self.get_user(user_id)
        self.scope_service.get_workspace(workspace_id)
        method = getattr(self.repository, "remove_membership_with_audit", None)
        if method is None:
            raise RuntimeError("atomic membership administration port unavailable")
        return deserialize_membership(method(user_id, workspace_id, audit))

    def require_active_membership(self, user_id: str, workspace_id: str) -> WorkspaceMembership:
        user = self.get_user(user_id)
        membership = self.get_membership(user_id, workspace_id)
        if user.status is not IdentityStatus.ACTIVE or membership.status is not IdentityStatus.ACTIVE:
            raise PermissionError(f"{user_id} is not an active member of {workspace_id}")
        return membership

    def set_membership_status(self, user_id: str, workspace_id: str, status: IdentityStatus) -> WorkspaceMembership:
        self.get_user(user_id)
        self.scope_service.get_workspace(workspace_id)
        return deserialize_membership(self.repository.update_membership_status(user_id, workspace_id, status.value, utcnow()))

    def set_membership_status_with_audit(self, user_id: str, workspace_id: str, status: IdentityStatus, audit: dict) -> WorkspaceMembership:
        self.get_user(user_id)
        self.scope_service.get_workspace(workspace_id)
        method = getattr(self.repository, "update_membership_status_with_audit", None)
        if method is None:
            raise RuntimeError("atomic membership administration port unavailable")
        return deserialize_membership(method(user_id, workspace_id, status.value, utcnow(), audit))
