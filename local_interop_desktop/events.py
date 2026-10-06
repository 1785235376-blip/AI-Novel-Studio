"""Bounded metadata event projection. Grant checks happen at enqueue AND delivery.

No background thread, polling timer, business read or event subscription starts
on import. The product lifecycle drives poll_due()/drain() at its own cadence.
Provenance lives outside the frozen V1 envelope and is never elevated to authority.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Iterable, Protocol
from uuid import uuid4

from local_interop_protocol import (
    AppContextCapsule,
    InteropEvent,
    ProtocolViolation,
    parse_wire,
    validate_capsule,
)
from local_interop_protocol.models import EventType

from .identity import opaque, utcnow


class EventProvenance(str, Enum):
    DIRECT_EVENT = "DIRECT_EVENT"
    POLLING = "POLLING"
    SYNTHETIC = "SYNTHETIC"


class InteropEventSource(Protocol):
    def subscribe(
        self, callback: Callable[[str, AppContextCapsule], None]
    ) -> Callable[[], None]: ...


@dataclass(frozen=True)
class EventDelivery:
    event: InteropEvent
    provenance: EventProvenance
    module: str


@dataclass
class _Registration:
    provenance: EventProvenance
    poll: Callable[[], Iterable[tuple[str, AppContextCapsule]]] | None
    close: Callable[[], None] | None
    next_poll: float = 0
    interval: float = 1
    failures: int = 0


@dataclass
class _Subscription:
    session_id: str
    peer_id: str
    expires_at: datetime
    authorize: Callable[[AppContextCapsule], bool]
    callback: Callable[[EventDelivery], None] | None
    modules: frozenset[str]
    paused: bool = False
    sequence: int = 0
    dropped: int = 0
    queue: OrderedDict = field(default_factory=OrderedDict)


class InteropEventSourceRegistry:
    MODULES = frozenset({"PROJECT", "CHAPTER", "TASK", "MODEL", "RUNTIME", "EXPORT", "WORKFLOW"})

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] = utcnow,
        monotonic: Callable[[], float] = time.monotonic,
        queue_limit: int = 32,
        subscriber_limit: int = 32,
        poll_interval: float = 1,
        max_idle_interval: float = 30,
        poll_batch_limit: int = 32,
        mock_only: bool = False,
    ):
        if (
            not 1 <= queue_limit <= 256
            or not 1 <= subscriber_limit <= 256
            or not 1 <= poll_batch_limit <= 256
        ):
            raise ValueError("Invalid event capacity")
        if not 0.05 <= poll_interval <= max_idle_interval <= 300:
            raise ValueError("Invalid bounded polling interval")
        self.clock, self.monotonic = clock, monotonic
        self.queue_limit, self.subscriber_limit = queue_limit, subscriber_limit
        self.poll_interval, self.max_idle_interval = poll_interval, max_idle_interval
        self.poll_batch_limit, self.mock_only = poll_batch_limit, mock_only
        self._sources: dict[str, _Registration] = {}
        self._subscribers: dict[str, _Subscription] = {}

    def register(
        self,
        module: str,
        *,
        source: InteropEventSource | None = None,
        poll: Callable[[], Iterable[tuple[str, AppContextCapsule]]] | None = None,
        provenance: EventProvenance | None = None,
    ) -> None:
        if (
            module not in self.MODULES
            or module in self._sources
            or (source is not None and poll is not None)
        ):
            raise ValueError("Invalid or duplicate module registration")
        provenance = provenance or (
            EventProvenance.POLLING if poll is not None else EventProvenance.DIRECT_EVENT
        )
        if not isinstance(provenance, EventProvenance) or (
            provenance == EventProvenance.SYNTHETIC and not self.mock_only
        ):
            raise ValueError("Synthetic event sources require an explicit mock registry")
        if poll is not None and provenance != EventProvenance.POLLING:
            raise ValueError("Polling cannot be represented as a direct event")
        registration = _Registration(provenance, poll, None, interval=self.poll_interval)
        self._sources[module] = registration
        try:
            if source is not None:

                def accept(kind, capsule):
                    try:
                        self.publish(module, kind, capsule)
                        registration.failures = 0
                    except Exception:
                        # Projection failures must not break the product's business event.
                        registration.failures += 1

                registration.close = source.subscribe(accept)
                if not callable(registration.close):
                    raise ValueError("Event source must return an unsubscribe callback")
        except Exception:
            self._sources.pop(module, None)
            raise

    def describe(self) -> tuple[dict, ...]:
        return tuple(
            {
                "module": module,
                "provenance": source.provenance.value,
                "poll_interval_seconds": source.interval if source.poll else None,
                "status": "DEGRADED" if source.failures else "READY",
            }
            for module, source in sorted(self._sources.items())
        )

    def subscribe(
        self,
        *,
        session_id: str,
        peer_id: str,
        expires_at: datetime,
        authorize: Callable[[AppContextCapsule], bool],
        callback: Callable[[EventDelivery], None] | None = None,
        modules: Iterable[str] | None = None,
    ) -> str:
        self.expire()
        opaque(session_id)
        opaque(peer_id)
        if expires_at.tzinfo is None or expires_at <= self.clock() or not callable(authorize):
            raise ProtocolViolation(
                "PERMISSION_DENIED", "A live explicit event authorization is required"
            )
        selected = frozenset(self.MODULES if modules is None else modules)
        if not selected.issubset(self.MODULES):
            raise ValueError("Unknown event module")
        if len(self._subscribers) >= self.subscriber_limit:
            raise ProtocolViolation("TRANSPORT_ERROR", "Subscription capacity reached")
        sid = "subscription-" + uuid4().hex
        self._subscribers[sid] = _Subscription(
            session_id, peer_id, expires_at, authorize, callback, selected
        )
        return sid

    def _authorized(self, subscription: _Subscription, capsule: AppContextCapsule) -> bool:
        if subscription.expires_at <= self.clock() or subscription.paused:
            return False
        try:
            validate_capsule(capsule, now=self.clock())
            return subscription.authorize(capsule) is True
        except Exception:
            return False

    def publish(
        self,
        module: str,
        event_type: str,
        capsule: AppContextCapsule,
        *,
        subscription_id: str | None = None,
    ) -> int:
        source = self._sources.get(module)
        if source is None or event_type not in EventType.__args__:
            raise ProtocolViolation(
                "INVALID_MESSAGE", "An enrolled source and existing V1 event type are required"
            )
        capsule = parse_wire(AppContextCapsule, capsule.model_dump_json())
        if capsule.content.level != "NONE":
            raise ProtocolViolation("CONTEXT_NOT_AUTHORIZED", "Events may contain metadata only")
        self.expire()
        count = 0
        for sid, subscription in tuple(self._subscribers.items()):
            if subscription_id is not None and sid != subscription_id:
                continue
            if module not in subscription.modules or not self._authorized(subscription, capsule):
                continue
            key = (module, event_type, capsule.project_id, capsule.chapter_id, capsule.task_id)
            if key in subscription.queue:
                subscription.queue.pop(key)
            elif len(subscription.queue) >= self.queue_limit:
                subscription.queue.popitem(last=False)
                subscription.dropped += 1
            subscription.queue[key] = (event_type, capsule, source.provenance, module)
            count += 1
        return count

    def drain(self, subscription_id: str, *, limit: int | None = None) -> tuple[EventDelivery, ...]:
        self.expire()
        subscription = self._subscribers.get(subscription_id)
        if subscription is None or subscription.paused:
            return ()
        limit = self.queue_limit if limit is None else limit
        if type(limit) is not int or not 1 <= limit <= self.queue_limit:
            raise ValueError("Invalid delivery batch")
        result = []
        for _ in range(min(limit, len(subscription.queue))):
            if self._subscribers.get(subscription_id) is not subscription:
                break
            _, (kind, capsule, provenance, module) = subscription.queue.popitem(last=False)
            if not self._authorized(subscription, capsule):
                continue
            subscription.sequence += 1
            event = InteropEvent(
                event_id="event-" + uuid4().hex,
                session_id=subscription.session_id,
                sequence=subscription.sequence,
                event_type=kind,
                created_at=self.clock(),
                context=capsule,
            )
            delivery = EventDelivery(event, provenance, module)
            if subscription.callback is not None:
                try:
                    subscription.callback(delivery)
                except Exception:
                    # One unhealthy subscriber never disables a different peer.
                    self.revoke(subscription_id)
                    break
            result.append(delivery)
        return tuple(result)

    def is_active(self, subscription_id: str) -> bool:
        self.expire()
        return subscription_id in self._subscribers

    def revoke(self, subscription_id: str) -> None:
        subscription = self._subscribers.pop(subscription_id, None)
        if subscription is not None:
            subscription.queue.clear()

    unsubscribe = revoke

    def pause(self, subscription_id: str) -> None:
        subscription = self._subscribers.get(subscription_id)
        if subscription is not None:
            subscription.paused = True
            subscription.queue.clear()

    def resume(self, subscription_id: str) -> None:
        self.expire()
        subscription = self._subscribers.get(subscription_id)
        if subscription is not None:
            subscription.paused = False

    def disconnect(self, peer_id: str) -> None:
        for sid, subscription in tuple(self._subscribers.items()):
            if subscription.peer_id == peer_id:
                self.revoke(sid)

    def expire(self) -> None:
        for sid, subscription in tuple(self._subscribers.items()):
            if subscription.expires_at <= self.clock():
                self.revoke(sid)

    def poll_due(self) -> int:
        self.expire()
        # No subscribers means no business reads. Direct producers remain independent.
        if not any(not subscription.paused for subscription in self._subscribers.values()):
            return 0
        count = 0
        for module, source in self._sources.items():
            now = self.monotonic()
            if source.poll is None or now < source.next_poll:
                continue
            changed = 0
            try:
                for index, (kind, capsule) in enumerate(source.poll()):
                    if index >= self.poll_batch_limit:
                        break
                    changed += self.publish(module, kind, capsule)
                source.failures = 0
            except Exception:
                source.failures += 1
            source.interval = (
                self.poll_interval if changed else min(self.max_idle_interval, source.interval * 2)
            )
            source.next_poll = now + source.interval
            count += changed
        return count

    def clear_subscriptions(self) -> None:
        for sid in tuple(self._subscribers):
            self.revoke(sid)

    def shutdown(self) -> None:
        self.clear_subscriptions()
        for source in tuple(self._sources.values()):
            if source.close is not None:
                try:
                    source.close()
                except Exception:
                    pass
        self._sources.clear()
