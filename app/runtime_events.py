"""Content-free notifications from committed product owners.

Owners know nothing about Tutor or transports. Observers are weak, bounded and
failure-isolated; no event history or secondary business state is persisted.
"""
from __future__ import annotations

import re
import threading
import weakref
from dataclasses import dataclass
from functools import wraps

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


@dataclass(frozen=True)
class RuntimeChange:
    module: str
    project_id: str
    entity_id: str | None = None
    version: int | None = None


class RuntimeEventSource:
    def __init__(self):
        self._observers = set()
        self._lock = threading.Lock()

    def subscribe(self, callback):
        reference = weakref.WeakMethod(callback) if getattr(callback, "__self__", None) else weakref.ref(callback)
        with self._lock:
            self._observers = {item for item in self._observers if item() is not None}
            if len(self._observers) >= 128:
                raise RuntimeError("runtime observer limit")
            self._observers.add(reference)
        def unsubscribe():
            with self._lock:
                self._observers.discard(reference)
        return unsubscribe

    def publish(self, change: RuntimeChange):
        with self._lock:
            observers = tuple(self._observers)
        for reference in observers:
            observer = reference()
            if observer is not None:
                try:
                    observer(change)
                except Exception:  # noqa: BLE001,S110 - never fail owner writes or log payload-bearing exceptions
                    # A passive observer may never turn a committed write into
                    # an apparent failure, or block the owner's normal lifecycle.
                    pass


runtime_events = RuntimeEventSource()


def committed_change(module: str):
    """Notify after the decorated owner method/transaction has returned.

    Only explicit IDs/version are extracted. Neither payloads nor returned
    documents, prompts, model configuration or exception text enter this bus.
    """
    if module not in {"PROJECT", "CHAPTER", "TASK"}:
        raise ValueError("unsupported owner module")
    def decorate(method):
        @wraps(method)
        def call(*args, **kwargs):
            result = method(*args, **kwargs)
            try:
                row = result if isinstance(result, dict) else {}
                if module == "TASK":
                    row = args[1] if len(args) > 1 and isinstance(args[1], dict) else kwargs.get("item", {})
                entity = row.get("id")
                first = args[1] if len(args) > 1 else next(iter(kwargs.values()), None)
                if not entity and isinstance(first, str):
                    entity = first
                project = row.get("novel_id") or (entity if module == "PROJECT" else None)
                if not project and module == "CHAPTER" and isinstance(entity, str) and ":" in entity:
                    project = entity.rsplit(":", 1)[0]
                if isinstance(project, str) and _ID.fullmatch(project):
                    entity = entity if isinstance(entity, str) and _ID.fullmatch(entity) else None
                    version = row.get("version")
                    version = version if type(version) is int and version >= 0 else None
                    runtime_events.publish(RuntimeChange(module, project, entity, version))
            except Exception:  # noqa: BLE001,S110 - observer projection is best effort and non-authoritative
                pass
            return result
        return call
    return decorate
