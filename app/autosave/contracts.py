from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable, Protocol


class SaveStatus(StrEnum):
    SAVING = "saving"
    SAVED = "saved"
    UNSAVED = "unsaved"
    FAILED = "failed"


class FlushReason(StrEnum):
    IDLE = "idle"
    PERIODIC = "periodic"
    FOCUS_LOSS = "focus_loss"
    DOCUMENT_SWITCH = "document_switch"
    CHAPTER_SWITCH = "chapter_switch"
    APPLICATION_CLOSE = "application_close"
    EXPLICIT = "explicit"


@dataclass(frozen=True, slots=True)
class SaveFailure:
    message: str
    retryable: bool
    cause: BaseException | None = None


class SaveError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class SaveObservation:
    document_id: str
    status: SaveStatus
    generation: int
    reason: FlushReason | None = None
    failure: SaveFailure | None = None


SaveCallable = Callable[[str, Any, int], None]
Observer = Callable[[SaveObservation], None]


class AutosaveLogger(Protocol):
    def info(self, event: str, **fields: Any) -> None: ...

    def error(self, event: str, **fields: Any) -> None: ...


class ScheduledHandle(Protocol):
    def cancel(self) -> None: ...


class Scheduler(Protocol):
    def call_later(self, delay: float, callback: Callable[[], None]) -> ScheduledHandle: ...

