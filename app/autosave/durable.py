from __future__ import annotations

from threading import RLock
from typing import Any, Callable
from inspect import signature

from ..document import markdown_to_document


class DurableVersionAutosaveAdapter:
    """Adapts editor generations to repository durable-version CAS.

    Editor generations identify in-memory snapshots only.  They must never be
    sent as durable expected versions because edits can outnumber saves.
    """

    def __init__(self, save: Callable[..., dict], *, load: Callable[[str], dict] | None = None):
        self._save = save
        self._load = load
        self._versions: dict[str, int] = {}
        self._supports_revision_flag = "create_revision" in signature(save).parameters
        self._lock = RLock()

    def track(self, document_id: str, durable_version: int) -> None:
        with self._lock:
            self._versions[document_id] = durable_version

    def durable_version(self, document_id: str) -> int | None:
        with self._lock:
            return self._versions.get(document_id)

    def __call__(self, document_id: str, content: Any, generation: int) -> None:
        del generation  # deliberately independent from the durable version
        with self._lock:
            expected = self._versions.get(document_id)
            if expected is None:
                if self._load is None:
                    raise RuntimeError(f"durable version is not tracked for {document_id}")
                expected = self._load(document_id)["version"]
                self._versions[document_id] = expected
            document = content if isinstance(content, dict) else markdown_to_document(content)
            if self._supports_revision_flag:
                saved = self._save(document_id, document, expected, create_revision=False)
            else:
                saved = self._save(document_id, document, expected)
            self._versions[document_id] = saved["version"]
