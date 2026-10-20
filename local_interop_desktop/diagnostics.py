"""Bounded non-content diagnostics and audit. No arbitrary exception text is retained."""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Callable

from local_interop_protocol import CAPABILITIES, PROTOCOL_VERSION
from local_interop_protocol.models import ErrorCode

from .identity import opaque, utcnow


class HealthStatus(str, Enum):
    READY = "READY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class InteropHealth:
    transport: HealthStatus = HealthStatus.UNKNOWN
    peer: HealthStatus = HealthStatus.UNKNOWN
    session: HealthStatus = HealthStatus.UNKNOWN
    capabilities: HealthStatus = HealthStatus.UNKNOWN
    events: HealthStatus = HealthStatus.UNKNOWN
    tutor: HealthStatus = HealthStatus.UNKNOWN
    verifier: HealthStatus = HealthStatus.UNKNOWN


@dataclass(frozen=True)
class AuditRecord:
    timestamp: datetime
    operation: str
    peer_product_id: str | None
    capability: str | None
    decision: str
    result: str
    error_code: str | None = None

    def __post_init__(self):
        if self.timestamp.tzinfo is None:
            raise ValueError("Audit timestamp must have a timezone")
        if self.operation not in {
            "START",
            "STOP",
            "CONNECT",
            "DISCONNECT",
            "HELLO",
            "CAPABILITY_NEGOTIATION",
            "SESSION",
            "TUTOR",
            "DIAGNOSTICS",
            "VERIFY",
            "HANDOFF",
            "HEARTBEAT",
            "CANCEL",
            "SUBSCRIBE",
            "UNSUBSCRIBE",
            "REVOKE",
            "SHUTDOWN",
            "ATTEST",
        }:
            raise ValueError("Unknown audit operation")
        if self.peer_product_id is not None:
            opaque(self.peer_product_id)
        if self.capability is not None and self.capability not in CAPABILITIES:
            raise ValueError("Unknown audit capability")
        if self.decision not in {"ALLOW", "DENY", "NONE"}:
            raise ValueError("Unknown audit decision")
        if self.result not in {"SUCCESS", "FAILED", "CANCELLED", "TIMEOUT", "PENDING"}:
            raise ValueError("Unknown audit result")
        if self.error_code is not None and self.error_code not in ErrorCode.__args__:
            raise ValueError("Unknown audit error")


class InteropAudit:
    def __init__(self, *, limit: int = 256, clock: Callable[[], datetime] = utcnow):
        if not 1 <= limit <= 4096:
            raise ValueError("Invalid audit bound")
        self._records = deque(maxlen=limit)
        self.clock = clock

    def record(
        self,
        operation: str,
        *,
        peer_product_id=None,
        capability=None,
        decision="NONE",
        result="SUCCESS",
        error_code=None,
    ) -> None:
        self._records.append(
            AuditRecord(
                self.clock(), operation, peer_product_id, capability, decision, result, error_code
            )
        )

    def snapshot(self) -> tuple[AuditRecord, ...]:
        return tuple(self._records)

    def flush(self, sink: Callable[[tuple[dict, ...]], None]) -> None:
        rows = tuple(
            {**asdict(record), "timestamp": record.timestamp.isoformat()}
            for record in self._records
        )
        sink(rows)
        self._records.clear()


@dataclass(frozen=True)
class InteropDiagnosticSnapshot:
    state_machine: str
    capability_state: tuple[str, ...] = ()
    error_codes: tuple[str, ...] = ()
    timings_ms: tuple[float, ...] = ()
    trust_state: str = "UNVERIFIED"
    protocol_version: str = PROTOCOL_VERSION

    def __post_init__(self):
        if self.state_machine not in {
            "STOPPED",
            "STARTING",
            "LISTENING",
            "DISCOVERING",
            "CONNECTING",
            "HANDSHAKING",
            "AUTHENTICATING",
            "NEGOTIATING",
            "READY",
            "DEGRADED",
            "REVOKING",
            "DISCONNECTING",
            "FAILED",
        }:
            raise ValueError("Unknown transport state")
        if len(self.capability_state) > 64 or not set(self.capability_state).issubset(CAPABILITIES):
            raise ValueError("Unknown capabilities")
        if len(self.error_codes) > 32 or not set(self.error_codes).issubset(ErrorCode.__args__):
            raise ValueError("Unknown diagnostic errors")
        if len(self.timings_ms) > 32 or any(
            type(value) not in {float, int} or not 0 <= value <= 86400000
            for value in self.timings_ms
        ):
            raise ValueError("Invalid timing metadata")
        if self.trust_state not in {
            "UNVERIFIED",
            "SAME_USER",
            "KNOWN_PRODUCT",
            "SIGNED_PRODUCT",
            "TRUSTED_INSTALLATION",
            "REJECTED",
            "MOCK_ONLY",
        }:
            raise ValueError("Unknown trust state")
        if self.protocol_version != PROTOCOL_VERSION:
            raise ValueError("Diagnostic protocol mismatch")
