"""Small immutable application events; delivery is deliberately unspecified."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True, kw_only=True)
class ApplicationEvent:
    occurred_at: datetime = field(default_factory=_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class DocumentSaved(ApplicationEvent):
    document_id: str
    version: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskStarted(ApplicationEvent):
    task_id: str
    operation: str


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskCompleted(ApplicationEvent):
    task_id: str
    operation: str
    result: Any = None


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskFailed(ApplicationEvent):
    task_id: str
    operation: str
    code: str
    message: str
    retryable: bool = False
