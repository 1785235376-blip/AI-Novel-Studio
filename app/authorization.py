from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class DomainRole(StrEnum):
    ADMIN = "ADMIN"
    DOMAIN_LEAD = "DOMAIN_LEAD"


class ModalityDomain(StrEnum):
    NOVEL = "NOVEL"
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    AUDIO = "AUDIO"


class ScopeKind(StrEnum):
    WORKSPACE = "WORKSPACE"
    PROJECT = "PROJECT"
    STORYLINE = "STORYLINE"
    BRANCH = "BRANCH"


@dataclass(frozen=True)
class AuthorizationScope:
    kind: ScopeKind
    workspace_id: str
    project_id: str | None = None
    storyline_id: str | None = None
    branch_id: str | None = None

    def __post_init__(self) -> None:
        required = {
            ScopeKind.WORKSPACE: (), ScopeKind.PROJECT: ("project_id",),
            ScopeKind.STORYLINE: ("project_id", "storyline_id"),
            ScopeKind.BRANCH: ("project_id", "storyline_id", "branch_id"),
        }[self.kind]
        if any(not getattr(self, name) for name in required):
            raise ValueError(f"{self.kind} scope is incomplete")
        allowed = set(required)
        if any(getattr(self, name) is not None for name in ("project_id", "storyline_id", "branch_id") if name not in allowed):
            raise ValueError(f"{self.kind} scope has fields below its declared level")

    def contains(self, other: AuthorizationScope) -> bool:
        fields = ("workspace_id", "project_id", "storyline_id", "branch_id")
        return all(getattr(self, name) is None or getattr(self, name) == getattr(other, name) for name in fields)


@dataclass(frozen=True)
class DomainRoleAssignment:
    id: str
    principal_id: str
    role: DomainRole
    domain: ModalityDomain
    scope: AuthorizationScope
    created_by: str
    created_at: str = field(default_factory=utcnow)


@dataclass(frozen=True)
class PermissionAssignment:
    id: str
    principal_id: str
    permission: str
    domain: ModalityDomain
    scope: AuthorizationScope
    created_by: str
    created_at: str = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        if not self.permission.strip():
            raise ValueError("permission must not be empty")


@dataclass(frozen=True)
class AuditEvent:
    id: str
    actor_id: str
    action: str
    target_type: str
    target_id: str
    scope: AuthorizationScope
    timestamp: str = field(default_factory=utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)
