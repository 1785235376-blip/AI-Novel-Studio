from __future__ import annotations

from threading import RLock
import json

from .actor_context import ActorContext, SessionContext


class TrustedSessionResolver:
    """Server-side session registry used by the local collaboration transport.

    HTTP callers present only an opaque token. Actor and workspace identity are
    resolved from server-owned state, keeping this boundary replaceable by a
    future authentication provider without changing domain services.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, SessionContext] = {}
        self._lock = RLock()

    def register(self, token: str, session: SessionContext) -> None:
        if not token.strip():
            raise ValueError("session token is required")
        with self._lock:
            self._sessions[token] = session

    def revoke(self, token: str) -> None:
        with self._lock:
            self._sessions.pop(token, None)

    def resolve(self, token: str) -> ActorContext:
        with self._lock:
            session = self._sessions.get(token)
        if session is None:
            raise KeyError("unknown or expired session")
        return ActorContext(session.actor_id, session.workspace_id, session)

    @classmethod
    def from_json(cls, value: str) -> "TrustedSessionResolver":
        resolver = cls()
        if not value.strip():
            return resolver
        for item in json.loads(value):
            token = item.pop("token")
            resolver.register(token, SessionContext(**item))
        return resolver


def create_runtime_session_resolver(
    *, packaged_runtime: bool, dev_sessions_json: str, collaboration_runtime: bool = True
) -> TrustedSessionResolver:
    """Keep packaged authentication isolated from explicitly insecure developer sessions."""
    if packaged_runtime:
        if not collaboration_runtime:
            raise RuntimeError("packaged runtime requires the trusted collaboration authorization boundary")
        if dev_sessions_json.strip():
            raise RuntimeError("packaged runtime cannot load development sessions")
        return TrustedSessionResolver()
    return TrustedSessionResolver.from_json(dev_sessions_json)
