"""Transport-neutral application status and task contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping


class TaskStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"

    @property
    def terminal(self) -> bool:
        return self in {
            self.COMPLETED,
            self.FAILED,
            self.CANCELLED,
            self.ACCEPTED,
            self.REJECTED,
        }


@dataclass(frozen=True, slots=True)
class Failure:
    code: str
    message: str
    retryable: bool = False
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Progress:
    current: int
    total: int | None = None
    message: str | None = None

    def __post_init__(self) -> None:
        if self.current < 0 or (self.total is not None and self.total < self.current):
            raise ValueError("progress must satisfy 0 <= current <= total")


@dataclass(frozen=True, slots=True)
class TaskRef:
    id: str
    operation: str


@dataclass(frozen=True, slots=True)
class TaskResult:
    output: str = ""
    provider: str | None = None
    model: str | None = None
    issues: tuple[Any, ...] = ()


@dataclass(frozen=True, slots=True)
class TaskSnapshot:
    id: str
    operation: str
    status: TaskStatus
    created_at: str | datetime | None = None
    updated_at: str | datetime | None = None
    progress: Progress | None = None
    result: TaskResult | None = None
    failure: Failure | None = None
    cancellation_requested: bool = False


@dataclass(frozen=True, slots=True)
class RuntimeProviderStatus:
    name: str
    configured: bool
    available: bool
    kind: str
    status: str | None = None
    models: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class RuntimeStatus:
    healthy: bool
    providers: tuple[RuntimeProviderStatus, ...]


@dataclass(frozen=True, slots=True)
class HealthStatus:
    status: str
    runtime: RuntimeStatus | None = None
