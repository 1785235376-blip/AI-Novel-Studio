from __future__ import annotations

import hashlib
import hmac
import secrets
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from threading import RLock
from typing import Callable
from urllib.parse import urlsplit

from ..actor_context import SessionContext
from ..trusted_sessions import TrustedSessionResolver
from .runtime_identity import RuntimeIdentity


class BootstrapState(StrEnum):
    ACTIVE = "ACTIVE"
    USED = "USED"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"


class BootstrapDenied(PermissionError):
    def __init__(self, code: str, safe_message: str):
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message


@dataclass(frozen=True)
class TrustedLocalIdentity:
    actor_id: str
    workspace_id: str

    def __post_init__(self) -> None:
        if not self.actor_id.strip() or not self.workspace_id.strip():
            raise ValueError("trusted local actor and workspace are required")


@dataclass(frozen=True)
class BootstrapReceipt:
    session_token: str = field(repr=False)


class LocalSessionBootstrap:
    """One-shot in-memory bridge into the existing trusted session resolver."""

    def __init__(
        self, *, runtime: RuntimeIdentity, sessions: TrustedSessionResolver,
        trusted_identity: TrustedLocalIdentity, expected_origin: str,
        ttl_seconds: float = 60.0, clock: Callable[[], float] = time.monotonic,
        event_sink: Callable[[str], None] | None = None,
        bootstrap_secret: str | None = None,
    ):
        if ttl_seconds <= 0 or ttl_seconds > 300:
            raise ValueError("bootstrap TTL must be greater than zero and at most five minutes")
        parsed_origin = urlsplit(expected_origin)
        if (
            parsed_origin.scheme != "http"
            or parsed_origin.hostname != "127.0.0.1"
            or parsed_origin.port is None
            or parsed_origin.username is not None
            or parsed_origin.password is not None
            or parsed_origin.path not in {"", "/"}
            or parsed_origin.query
            or parsed_origin.fragment
        ):
            raise ValueError("packaged frontend origin must be an explicit 127.0.0.1 origin")
        self.runtime = runtime
        self.sessions = sessions
        self.trusted_identity = trusted_identity
        self.expected_origin = expected_origin.rstrip("/")
        self.ttl_seconds = ttl_seconds
        self.clock = clock
        self.event_sink = event_sink if event_sink is not None else (lambda _event: None)
        self._lock = RLock()
        self._secret: str | None = bootstrap_secret or secrets.token_urlsafe(48)
        self._secret_hash = _digest(self._secret)
        self._created_at = self.clock()
        self._state = BootstrapState.ACTIVE
        self._launcher_secret_delivered = False
        self._issued_tokens: set[str] = set()
        self._event("bootstrap.created")

    @property
    def state(self) -> BootstrapState:
        with self._lock:
            if self._state is BootstrapState.ACTIVE and self.clock() >= self._created_at + self.ttl_seconds:
                self._state = BootstrapState.EXPIRED
            return self._state

    @property
    def safe_metadata(self) -> dict[str, str | float]:
        return {
            "runtime_instance_id": self.runtime.runtime_instance_id,
            "bootstrap_state": self.state.value,
            "expires_after_seconds": self.ttl_seconds,
        }

    def take_launcher_secret(self) -> str:
        """Transfer the raw secret once to the future launcher/frontend adapter."""
        with self._lock:
            if self._launcher_secret_delivered or self._secret is None:
                raise RuntimeError("bootstrap secret has already been transferred")
            secret = self._secret
            self._secret = None
            self._launcher_secret_delivered = True
            return secret

    def resolve_issued_session(self, token: str | None):
        """Resolve only a session token issued by this current bootstrap instance."""
        if not token:
            raise BootstrapDenied("PACKAGED_SESSION_REQUIRED", "本地安全会话无效或已过期。")
        with self._lock:
            if self._state is not BootstrapState.USED or token not in self._issued_tokens:
                raise BootstrapDenied("PACKAGED_SESSION_REQUIRED", "本地安全会话无效或已过期。")
        try:
            return self.sessions.resolve(token)
        except KeyError as exc:
            raise BootstrapDenied("PACKAGED_SESSION_REQUIRED", "本地安全会话无效或已过期。") from exc

    def exchange(
        self, *, bootstrap_secret: str | None, runtime_instance_id: str | None,
        origin: str | None, remote_host: str | None,
    ) -> BootstrapReceipt:
        if remote_host != "127.0.0.1":
            self._reject("bootstrap.rejected", "BOOTSTRAP_LOOPBACK_REQUIRED", "仅允许本机应用完成安全连接。")
        if origin != self.expected_origin:
            self._reject("bootstrap.rejected", "BOOTSTRAP_ORIGIN_DENIED", "应用来源验证失败。")
        if runtime_instance_id != self.runtime.runtime_instance_id:
            self._reject("bootstrap.rejected", "BOOTSTRAP_DENIED", "安全连接凭证无效或已过期。")
        if not bootstrap_secret:
            self._reject("bootstrap.rejected", "BOOTSTRAP_DENIED", "安全连接凭证无效或已过期。")

        with self._lock:
            if self.state is BootstrapState.EXPIRED:
                self._event("bootstrap.expired")
                raise BootstrapDenied("BOOTSTRAP_DENIED", "安全连接凭证无效或已过期。")
            if self._state is not BootstrapState.ACTIVE:
                self._reject("bootstrap.rejected", "BOOTSTRAP_DENIED", "安全连接凭证无效或已过期。")
            if not hmac.compare_digest(_digest(bootstrap_secret), self._secret_hash):
                self._reject("bootstrap.rejected", "BOOTSTRAP_DENIED", "安全连接凭证无效或已过期。")

            # Consume before session registration: any internal failure remains fail-closed.
            self._state = BootstrapState.USED
            token = secrets.token_urlsafe(48)
            session = SessionContext(
                session_id=f"packaged:{uuid.uuid4()}",
                client_id=f"windows-runtime:{self.runtime.runtime_instance_id}",
                actor_id=self.trusted_identity.actor_id,
                workspace_id=self.trusted_identity.workspace_id,
            )
            self.sessions.register(token, session)
            self._issued_tokens.add(token)
            self._event("bootstrap.accepted")
            self._event("session.issued")
            return BootstrapReceipt(session_token=token)

    def invalidate(self) -> None:
        with self._lock:
            self._state = BootstrapState.INVALIDATED
            self._secret = None
            tokens = tuple(self._issued_tokens)
            self._issued_tokens.clear()
        for token in tokens:
            self.sessions.revoke(token)
        self._event("bootstrap.invalidated")

    def _reject(self, event: str, code: str, message: str) -> None:
        self._event(event)
        raise BootstrapDenied(code, message)

    def _event(self, category: str) -> None:
        # Only fixed categories cross this boundary; request bodies and secrets never do.
        self.event_sink(category)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
