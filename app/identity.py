from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class IdentityStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


@dataclass(frozen=True)
class User:
    id: str
    display_name: str
    status: IdentityStatus = IdentityStatus.ACTIVE
    created_at: str = field(default_factory=utcnow)
    updated_at: str = field(default_factory=utcnow)
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("user id must not be empty")
        if not self.display_name.strip():
            raise ValueError("display name must not be empty")


@dataclass(frozen=True)
class WorkspaceMembership:
    id: str
    user_id: str
    workspace_id: str
    status: IdentityStatus = IdentityStatus.ACTIVE
    created_at: str = field(default_factory=utcnow)
    updated_at: str = field(default_factory=utcnow)
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.user_id.strip() or not self.workspace_id.strip():
            raise ValueError("membership id, user id, and workspace id are required")
