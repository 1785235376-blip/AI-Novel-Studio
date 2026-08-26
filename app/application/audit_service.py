from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping
from uuid import uuid4

from ..actor_context import ActorContext
from ..authorization import AuditEvent, AuthorizationScope


_SENSITIVE_KEYS = frozenset({
    "content", "document", "prompt", "secret", "secrets", "local_only",
    "context", "context_pack", "text", "markdown",
})


def safe_audit_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return the small, identifier-only metadata vocabulary allowed in audit rows."""
    if not metadata:
        return {}
    result: dict[str, Any] = {}
    for key, value in metadata.items():
        normalized = key.casefold()
        if normalized in _SENSITIVE_KEYS or any(token in normalized for token in ("prompt", "secret", "content")):
            continue
        if key not in {
            "expected_version", "actual_version", "result_version", "reason",
            "session_id", "client_id", "correlation_id", "conflict_type",
            "result_count", "novel_id", "agent_id", "status", "created_after", "created_before", "branch_id", "target",
        }:
            continue
        if value is None or isinstance(value, (str, int, float, bool)):
            result[key] = value
    return result


class AuditService:
    """Builds and persists events in the existing authorization audit stream."""

    def __init__(self, authorization_repository):
        self.repository = authorization_repository

    def build(
        self,
        actor: ActorContext,
        action: str,
        target_type: str,
        target_id: str,
        scope: AuthorizationScope,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = AuditEvent(
            id=str(uuid4()), actor_id=actor.actor_id, action=action,
            target_type=target_type, target_id=target_id, scope=scope,
            metadata=safe_audit_metadata({
                **(metadata or {}),
                "session_id": actor.session_id,
                "client_id": actor.client_id,
                "correlation_id": actor.effective_correlation_id,
            }),
        )
        value = asdict(event)
        value["scope"]["kind"] = event.scope.kind.value
        return value

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        return self.repository.append_audit_event(event)
