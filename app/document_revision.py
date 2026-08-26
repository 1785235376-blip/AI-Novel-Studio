from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol


class RevisionReason(StrEnum):
    MANUAL_SAVE = "MANUAL_SAVE"
    AI_ACCEPT = "AI_ACCEPT"
    RESTORE = "RESTORE"
    CHAPTER_SWITCH = "CHAPTER_SWITCH"
    EXPLICIT_CHECKPOINT = "EXPLICIT_CHECKPOINT"


class SaveTrigger(StrEnum):
    DEBOUNCE_AUTOSAVE = "DEBOUNCE_AUTOSAVE"
    MANUAL_SAVE = "MANUAL_SAVE"
    AI_ACCEPT = "AI_ACCEPT"
    RESTORE = "RESTORE"
    CHAPTER_SWITCH = "CHAPTER_SWITCH"
    EXPLICIT_CHECKPOINT = "EXPLICIT_CHECKPOINT"


_PERMANENT_REASONS = {reason.value for reason in RevisionReason}


def permanent_revision_reason(trigger: SaveTrigger | str) -> RevisionReason | None:
    """Map meaningful checkpoints to immutable history; debounce saves are ephemeral."""
    value = trigger.value if isinstance(trigger, SaveTrigger) else str(trigger)
    return RevisionReason(value) if value in _PERMANENT_REASONS else None


@dataclass(frozen=True)
class RevisionContext:
    actor_id: str
    session_id: str | None = None
    scope_type: str | None = None
    scope_id: str | None = None


class ChapterHistory(Protocol):
    def get(self, chapter_id: str) -> dict[str, Any]: ...
    def restore(self, chapter_id: str, version: int, expected_version: int) -> dict[str, Any]: ...


def restore_as_new_current(
    repository: ChapterHistory, chapter_id: str, historical_version: int, expected_version: int
) -> dict[str, Any]:
    """Restore by appending a new current version; the selected history row is never mutated."""
    before = repository.get(chapter_id)
    if before["version"] != expected_version:
        # Let the repository raise its native conflict with the freshest representation.
        return repository.restore(chapter_id, historical_version, expected_version)
    restored = repository.restore(chapter_id, historical_version, expected_version)
    if restored["version"] <= before["version"]:
        raise RuntimeError("restore must create a new current chapter version")
    return restored
