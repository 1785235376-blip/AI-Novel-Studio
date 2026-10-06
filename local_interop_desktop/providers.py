"""Product-role ports: existing product owners retain all content and mutation authority."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Protocol

from local_interop_protocol import (
    AppContextCapsule,
    CaseCandidate,
    HandoffTarget,
    ModelRegistry,
    ProtocolViolation,
    TutorGuidance,
    TutorRequest,
    VerificationCondition,
    VerifierResult,
    canonical_hash,
    parse_wire,
)

from .identity import opaque, utcnow


class InteropContextProvider(Protocol):
    def current_product_context(self): ...
    def current_project_context(self): ...
    def current_surface(self): ...
    def current_task(self): ...
    def current_model_state(self): ...
    def current_runtime_state(self): ...
    def selected_content_metadata(self): ...
    def build_capsule(self, scope) -> AppContextCapsule: ...


class InteropTutorAdapter(Protocol):
    async def request(self, request: TutorRequest) -> TutorGuidance: ...


class InteropVerifierAdapter(Protocol):
    def verify(
        self, condition: VerificationCondition, fresh_context: AppContextCapsule, trusted_evidence
    ) -> VerifierResult: ...


class InteropCaseGateAdapter(Protocol):
    def preview(self, candidate: CaseCandidate): ...
    def submit(self, candidate: CaseCandidate, *, approval): ...


class InteropMemoryCandidateAdapter(Protocol):
    """Creates candidates only. Policy, approval and the existing Memory Gate own writes."""

    def preview(self, context: AppContextCapsule): ...
    def submit(self, candidate, *, approval): ...


class InteropModelRegistryProvider(Protocol):
    def snapshot(self) -> ModelRegistry: ...


@dataclass(frozen=True)
class ModelRegistryCacheSnapshot:
    registry: ModelRegistry | None
    state: str
    fetched_at: datetime | None


class InteropModelRegistryCache:
    """Volatile read-only V1 metadata only; no endpoints, credentials or prompts."""

    def __init__(
        self,
        provider: InteropModelRegistryProvider,
        *,
        ttl_seconds: float = 30,
        clock: Callable[[], datetime] = utcnow,
    ):
        if not 0 < ttl_seconds <= 3600:
            raise ValueError("Invalid cache TTL")
        self.provider, self.clock = provider, clock
        self.ttl = timedelta(seconds=ttl_seconds)
        self._registry: ModelRegistry | None = None
        self._fetched_at: datetime | None = None
        self._failed = False

    def refresh(self) -> ModelRegistry:
        try:
            registry = self.provider.snapshot()
            # Reparse rather than trusting construct()/copy() or arbitrary dictionaries.
            raw = registry.model_dump_json() if isinstance(registry, ModelRegistry) else registry
            registry = parse_wire(ModelRegistry, raw)
            now = self.clock()
            if registry.created_at > now or now - registry.created_at >= self.ttl:
                raise ProtocolViolation("CONTEXT_STALE", "Model metadata is stale")
            self._registry, self._fetched_at, self._failed = registry, now, False
            return registry
        except Exception:
            self._failed = True
            raise

    def snapshot(self) -> ModelRegistryCacheSnapshot:
        state = "UNAVAILABLE"
        if self._registry is not None:
            stale = (
                self._failed
                or self.clock() < self._registry.created_at
                or self.clock() - self._registry.created_at >= self.ttl
            )
            state = "STALE" if stale else "READY"
        return ModelRegistryCacheSnapshot(self._registry, state, self._fetched_at)

    def clear(self) -> None:
        self._registry, self._fetched_at, self._failed = None, None, False


@dataclass(frozen=True)
class _Presence:
    action: str
    target_id: str
    source: str
    expires_at: datetime


class UserPresenceGate:
    """Use only from a trusted local UI click/dialog handler, never from peer JSON."""

    def __init__(self, *, clock: Callable[[], datetime] = utcnow, limit: int = 32):
        if not 1 <= limit <= 256:
            raise ValueError("Invalid gesture capacity")
        self.clock, self.limit = clock, limit
        self._tokens: dict[str, _Presence] = {}

    def issue(
        self, action: str, target_id: str, *, source: str = "USER_CLICK", ttl_seconds: float = 30
    ) -> str:
        if action not in {
            "OPEN_FEATURE",
            "OPEN_PROJECT",
            "OPEN_TASK",
            "OPEN_CHAPTER",
            "OPEN_SESSION",
        }:
            raise ProtocolViolation("PERMISSION_DENIED", "Unsupported handoff action")
        if source not in {"USER_CLICK", "CONFIRMED_DIALOG"} or not 0 < ttl_seconds <= 60:
            raise ProtocolViolation("PERMISSION_DENIED", "Fresh local user presence required")
        opaque(target_id)
        self._tokens = {
            key: value for key, value in self._tokens.items() if value.expires_at > self.clock()
        }
        if len(self._tokens) >= self.limit:
            raise ProtocolViolation("PERMISSION_DENIED", "User presence capacity reached")
        token = "gesture-" + secrets.token_hex(32)
        self._tokens[token] = _Presence(
            action, target_id, source, self.clock() + timedelta(seconds=ttl_seconds)
        )
        return token

    def consume(self, token: str, action: str, target_id: str) -> None:
        presence = self._tokens.pop(token, None)
        if (
            presence is None
            or presence.expires_at <= self.clock()
            or (presence.action, presence.target_id) != (action, target_id)
        ):
            raise ProtocolViolation("PERMISSION_DENIED", "Fresh matching user presence required")

    def issue_target(
        self,
        target: HandoffTarget,
        *,
        session_id: str | None = None,
        source: str = "USER_CLICK",
        ttl_seconds: float = 30,
    ) -> str:
        target = HandoffTarget.model_validate_json(target.model_dump_json())
        if session_id is not None:
            opaque(session_id)
        binding = canonical_hash(
            {"target": target.model_dump(mode="json"), "session_id": session_id}
        )
        return self.issue(target.action, binding, source=source, ttl_seconds=ttl_seconds)

    def consume_target(
        self, token: str, target: HandoffTarget, *, session_id: str | None = None
    ) -> None:
        target = HandoffTarget.model_validate_json(target.model_dump_json())
        binding = canonical_hash(
            {"target": target.model_dump(mode="json"), "session_id": session_id}
        )
        self.consume(token, target.action, binding)

    def clear(self) -> None:
        self._tokens.clear()


class InteropHandoffHandler:
    """Semantic targets only; the injected host resolves ownership/version before UI open."""

    def __init__(
        self,
        presence: UserPresenceGate,
        *,
        resolve: Callable[[HandoffTarget], bool],
        open_target: Callable[[HandoffTarget], None],
    ):
        self.presence, self.resolve, self.open_target = presence, resolve, open_target

    def open(
        self, target: HandoffTarget, *, user_presence_token: str, session_id: str | None = None
    ) -> None:
        self.presence.consume_target(user_presence_token, target, session_id=session_id)
        if self.resolve(target) is not True:
            raise ProtocolViolation("HANDOFF_TARGET_NOT_FOUND", "Handoff target is not current")
        self.open_target(target)


class InteropNotificationAdapter(Protocol):
    """Desktop mapping remains LOCAL_REQUIRED; no timers or unsolicited popup loop."""

    def notify(self, level: str, message_code: str) -> None: ...
