from __future__ import annotations

"""Durable knowledge-base import review state.

Import parsing deliberately produces candidates without mutating a project.
This small local-first store keeps the review window resumable after a
DesktopHost restart and records every decision without retaining source files
or provider credentials.  The service is storage-backend agnostic so the
existing file runtime can use it today while a PostgreSQL repository can be
introduced later without changing the HTTP contract.
"""

import hashlib
import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..storage import atomic_write


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class ImportReviewService:
    """Persist pending and completed import-review decisions.

    Records are intentionally bounded to candidate metadata supplied by the
    parser.  Raw imported document bytes are never copied into this store.
    """

    SCHEMA_VERSION = 1
    VALID_DECISIONS = frozenset({"ACCEPTED", "REJECTED", "SKIPPED"})

    def __init__(self, data_path: Path):
        self.path = data_path / "import_reviews.json"
        self._lock = threading.RLock()

    def _read(self) -> dict[str, dict]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
        if not isinstance(payload, dict):
            return {}
        return {str(key): value for key, value in payload.items() if isinstance(value, dict)}

    def _write(self, records: dict[str, dict]) -> None:
        atomic_write(self.path, json.dumps(records, ensure_ascii=False, indent=2))

    @staticmethod
    def _normalise_candidates(candidates: Any) -> dict[str, list[dict]]:
        if not isinstance(candidates, dict):
            return {}
        output: dict[str, list[dict]] = {}
        for kind, items in candidates.items():
            if not isinstance(items, list):
                continue
            safe_items: list[dict] = []
            for item in items:
                if isinstance(item, dict):
                    # Keep parser evidence useful for editing, while ensuring
                    # an accidental non-JSON value cannot poison persistence.
                    try:
                        safe_items.append(json.loads(_canonical(item)))
                    except (TypeError, ValueError):
                        continue
            if safe_items:
                output[str(kind)[:80]] = safe_items
        return output

    @classmethod
    def _fingerprint(cls, novel_id: str, candidates: dict[str, list[dict]]) -> str:
        raw = f"{novel_id}:{_canonical(candidates)}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _normalise(record: dict) -> dict:
        item = dict(record)
        item.setdefault("schema_version", ImportReviewService.SCHEMA_VERSION)
        item.setdefault("status", "PENDING")
        item.setdefault("history", [])
        item.setdefault("selected", {})
        item.setdefault("updated_at", item.get("created_at") or _now())
        return item

    def ensure_pending(
        self,
        novel_id: str,
        candidates: dict[str, list[dict]],
        *,
        source_format: str | None = None,
        import_id: str | None = None,
    ) -> dict:
        """Create or reuse a pending review for the same candidate set."""

        normalized = self._normalise_candidates(candidates)
        fingerprint = self._fingerprint(novel_id, normalized)
        with self._lock:
            records = self._read()
            for raw in records.values():
                if (
                    raw.get("novel_id") == novel_id
                    and raw.get("fingerprint") == fingerprint
                    and raw.get("status") == "PENDING"
                ):
                    return self._normalise(raw)
            review = {
                "id": str(uuid.uuid4()),
                "schema_version": self.SCHEMA_VERSION,
                "novel_id": novel_id,
                "status": "PENDING",
                "source_format": str(source_format or "")[:40],
                "import_id": str(import_id or "")[:120] or None,
                "fingerprint": fingerprint,
                "candidates": normalized,
                "selected": {kind: [False] * len(items) for kind, items in normalized.items()},
                "history": [],
                "created_at": _now(),
                "updated_at": _now(),
            }
            records[review["id"]] = review
            self._write(records)
            return self._normalise(review)

    def get(self, review_id: str) -> dict:
        with self._lock:
            item = self._read().get(str(review_id))
            if not isinstance(item, dict):
                raise FileNotFoundError(review_id)
            return self._normalise(item)

    def list_for_novel(self, novel_id: str, *, status: str | None = None) -> list[dict]:
        wanted = str(status or "").upper() or None
        with self._lock:
            rows = [self._normalise(item) for item in self._read().values() if item.get("novel_id") == novel_id]
        rows.sort(key=lambda item: str(item.get("updated_at", "")), reverse=True)
        if wanted:
            rows = [item for item in rows if str(item.get("status", "")).upper() == wanted]
        return rows

    def update_candidates(
        self,
        review_id: str,
        candidates: dict[str, list[dict]],
        *,
        selected: dict[str, list[bool]] | None = None,
        analysis: dict[str, Any] | None = None,
    ) -> dict:
        normalized = self._normalise_candidates(candidates)
        with self._lock:
            records = self._read()
            item = records.get(str(review_id))
            if not isinstance(item, dict):
                raise FileNotFoundError(review_id)
            if str(item.get("status", "PENDING")).upper() != "PENDING":
                raise ValueError("completed knowledge review cannot be edited")
            item["candidates"] = normalized
            if selected is None:
                item["selected"] = {kind: [False] * len(values) for kind, values in normalized.items()}
            else:
                item["selected"] = {
                    kind: [bool(flag) for flag in (selected.get(kind) or [])][: len(values)]
                    + [False] * max(0, len(values) - len(selected.get(kind) or []))
                    for kind, values in normalized.items()
                }
            item["fingerprint"] = self._fingerprint(str(item.get("novel_id", "")), normalized)
            if analysis is not None:
                item["analysis"] = json.loads(_canonical(analysis))
            item["updated_at"] = _now()
            records[str(review_id)] = item
            self._write(records)
            return self._normalise(item)

    def decide(
        self,
        review_id: str,
        decision: str,
        *,
        selected: dict[str, list[dict]] | None = None,
        applied: dict[str, list[dict]] | None = None,
        note: str = "",
    ) -> dict:
        decision = str(decision or "").upper().strip()
        if decision not in self.VALID_DECISIONS:
            raise ValueError("invalid knowledge review decision")
        with self._lock:
            records = self._read()
            item = records.get(str(review_id))
            if not isinstance(item, dict):
                raise FileNotFoundError(review_id)
            status = str(item.get("status", "PENDING")).upper()
            if status != "PENDING":
                # Idempotent replay returns the prior decision rather than
                # duplicating history or writing entities twice.
                return self._normalise(item)
            event = {
                "decision": decision,
                "selected": self._normalise_candidates(selected or {}),
                "applied": self._normalise_candidates(applied or {}),
                "note": str(note or "")[:500],
                "at": _now(),
            }
            item["status"] = decision
            item["decision"] = decision
            item["applied"] = event["applied"]
            item["history"] = [*(item.get("history") or []), event]
            item["updated_at"] = event["at"]
            records[str(review_id)] = item
            self._write(records)
            return self._normalise(item)
