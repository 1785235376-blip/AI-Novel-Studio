from __future__ import annotations

from threading import RLock
from typing import Any

from .contracts import (
    AutosaveLogger,
    FlushReason,
    Observer,
    SaveCallable,
    SaveError,
    SaveFailure,
    SaveObservation,
    SaveStatus,
    ScheduledHandle,
    Scheduler,
)
from .dirty_state import DirtyStateTracker


class SaveCoordinator:
    def __init__(
        self,
        save: SaveCallable,
        *,
        tracker: DirtyStateTracker | None = None,
        scheduler: Scheduler,
        idle_debounce: float = 1.0,
        periodic_interval: float | None = 30.0,
        observer: Observer | None = None,
        logger: AutosaveLogger | None = None,
    ) -> None:
        if idle_debounce < 0 or (periodic_interval is not None and periodic_interval <= 0):
            raise ValueError("autosave intervals must be positive")
        self.tracker = tracker or DirtyStateTracker()
        self._save = save
        self._scheduler = scheduler
        self._idle_debounce = idle_debounce
        self._periodic_interval = periodic_interval
        self._observer = observer
        self._logger = logger
        self._lock = RLock()
        self._idle: dict[str, ScheduledHandle] = {}
        self._saving: set[str] = set()
        self._pending: set[str] = set()
        self._closed = False
        self._periodic: ScheduledHandle | None = None
        if periodic_interval is not None:
            self._schedule_periodic()

    def content_changed(self, document_id: str, content: Any) -> int:
        with self._lock:
            if self._closed:
                raise RuntimeError("autosave coordinator is closed")
            state = self.tracker.mark_dirty(document_id, content)
        self._emit(document_id, SaveStatus.UNSAVED, state.generation)
        with self._lock:
            previous = self._idle.pop(document_id, None)
            if previous:
                previous.cancel()
            if not self._closed:
                self._idle[document_id] = self._scheduler.call_later(
                    self._idle_debounce,
                    lambda document_id=document_id: self.flush(document_id, FlushReason.IDLE),
                )
        return state.generation

    def flush(self, document_id: str, reason: FlushReason = FlushReason.EXPLICIT) -> bool:
        with self._lock:
            handle = self._idle.pop(document_id, None)
            if handle:
                handle.cancel()
            if document_id in self._saving:
                self._pending.add(document_id)
                return False
            state = self.tracker.get(document_id)
            if state is None or not state.dirty:
                return True
            self._saving.add(document_id)

        all_saved = True
        while True:
            state = self.tracker.get(document_id)
            if state is None or not state.dirty:
                break
            generation, content = state.generation, state.content
            marked = self.tracker.mark_saving(document_id, generation)
            if marked:
                self._emit(document_id, SaveStatus.SAVING, generation, reason)
            try:
                self._save(document_id, content, generation)
            except Exception as exc:
                retryable = exc.retryable if isinstance(exc, SaveError) else True
                failure = SaveFailure(str(exc), retryable, exc)
                failed = self.tracker.mark_failed(document_id, generation, failure)
                if failed:
                    self._emit(document_id, SaveStatus.FAILED, generation, reason, failure)
                self._log("error", "autosave_failed", document_id=document_id,
                          generation=generation, retryable=retryable)
                all_saved = False
                break
            else:
                saved = self.tracker.mark_saved(document_id, generation)
                if saved:
                    self._emit(document_id, SaveStatus.SAVED, generation, reason)
                self._log("info", "autosave_completed", document_id=document_id,
                          generation=generation, reason=reason.value)
            with self._lock:
                pending = document_id in self._pending
                self._pending.discard(document_id)
            latest = self.tracker.get(document_id)
            if not pending and (latest is None or not latest.dirty):
                break

        with self._lock:
            self._saving.discard(document_id)
        return all_saved and not bool(self.tracker.get(document_id) and self.tracker.get(document_id).dirty)

    def flush_all(self, reason: FlushReason = FlushReason.EXPLICIT) -> bool:
        all_saved = True
        for document_id in self.tracker.dirty_documents():
            if not self.flush(document_id, reason):
                all_saved = False
        return all_saved

    def on_focus_loss(self, document_id: str) -> bool:
        return self.flush(document_id, FlushReason.FOCUS_LOSS)

    def on_document_switch(self, document_id: str) -> bool:
        return self.flush(document_id, FlushReason.DOCUMENT_SWITCH)

    def on_chapter_switch(self, document_id: str) -> bool:
        return self.flush(document_id, FlushReason.CHAPTER_SWITCH)

    def on_application_close(self) -> bool:
        with self._lock:
            self._closed = True
            if self._periodic:
                self._periodic.cancel()
        return self.flush_all(FlushReason.APPLICATION_CLOSE)

    def _schedule_periodic(self) -> None:
        assert self._periodic_interval is not None
        self._periodic = self._scheduler.call_later(self._periodic_interval, self._periodic_tick)

    def _periodic_tick(self) -> None:
        self.flush_all(FlushReason.PERIODIC)
        with self._lock:
            if not self._closed:
                self._schedule_periodic()

    def _emit(self, document_id: str, status: SaveStatus, generation: int,
              reason: FlushReason | None = None, failure: SaveFailure | None = None) -> None:
        if self._observer:
            try:
                self._observer(SaveObservation(document_id, status, generation, reason, failure))
            except Exception:
                self._log("error", "autosave_observer_failed", document_id=document_id,
                          generation=generation, status=status.value)

    def _log(self, level: str, event: str, **fields: Any) -> None:
        if self._logger:
            try:
                getattr(self._logger, level)(event, **fields)
            except Exception:
                pass
