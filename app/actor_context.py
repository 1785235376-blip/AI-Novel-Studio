from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SessionContext:
    session_id: str
    client_id: str
    actor_id: str
    workspace_id: str
    correlation_id: str | None = None

    def __post_init__(self) -> None:
        if not all((self.session_id.strip(), self.client_id.strip(), self.actor_id.strip(), self.workspace_id.strip())):
            raise ValueError("session, client, actor, and workspace ids are required")


@dataclass(frozen=True)
class ActorContext:
    actor_id: str
    workspace_id: str
    session: SessionContext
    correlation_id: str | None = None

    def __post_init__(self) -> None:
        if not self.actor_id.strip() or not self.workspace_id.strip():
            raise ValueError("actor and workspace ids are required")
        if self.actor_id != self.session.actor_id or self.workspace_id != self.session.workspace_id:
            raise ValueError("actor context must be bound to its session actor and workspace")

    @property
    def client_id(self) -> str:
        return self.session.client_id

    @property
    def session_id(self) -> str:
        return self.session.session_id

    @property
    def effective_correlation_id(self) -> str | None:
        return self.correlation_id or self.session.correlation_id
