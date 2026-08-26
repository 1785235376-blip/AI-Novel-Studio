from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any

from .contracts import SaveFailure, SaveStatus


@dataclass(frozen=True, slots=True)
class DocumentState:
    document_id: str
    content: Any
    generation: int
    status: SaveStatus
    failure: SaveFailure | None = None

    @property
    def dirty(self) -> bool:
        return self.status != SaveStatus.SAVED


class DirtyStateTracker:
    """Thread-safe source of truth for the latest in-memory document content."""

    def __init__(self) -> None:
        self._states: dict[str, DocumentState] = {}
        self._lock = RLock()

    def mark_dirty(self, document_id: str, content: Any) -> DocumentState:
        with self._lock:
            previous = self._states.get(document_id)
            generation = 1 if previous is None else previous.generation + 1
            state = DocumentState(document_id, content, generation, SaveStatus.UNSAVED)
            self._states[document_id] = state
            return state

    def mark_saving(self, document_id: str, generation: int) -> DocumentState | None:
        return self._transition(document_id, generation, SaveStatus.SAVING)

    def mark_saved(self, document_id: str, generation: int) -> DocumentState | None:
        return self._transition(document_id, generation, SaveStatus.SAVED)

    def mark_failed(
        self, document_id: str, generation: int, failure: SaveFailure
    ) -> DocumentState | None:
        return self._transition(document_id, generation, SaveStatus.FAILED, failure)

    def get(self, document_id: str) -> DocumentState | None:
        with self._lock:
            return self._states.get(document_id)

    def dirty_documents(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(key for key, value in self._states.items() if value.dirty)

    def _transition(
        self,
        document_id: str,
        generation: int,
        status: SaveStatus,
        failure: SaveFailure | None = None,
    ) -> DocumentState | None:
        with self._lock:
            current = self._states.get(document_id)
            if current is None or current.generation != generation:
                return None
            state = DocumentState(document_id, current.content, generation, status, failure)
            self._states[document_id] = state
            return state

