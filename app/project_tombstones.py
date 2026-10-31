"""Bounded project-deletion tombstones for client cold-start purge.

A project delete physically retires the project and its authority, so a client
that was closed while the project was deleted has no way to learn the id from the
project list. These tombstones are an auxiliary UI signal for that purge: they
carry only the deleted project id, its workspace, the project incarnation seen
before deletion and the deletion time. They are never authority, content,
audit evidence or a quota ledger.

Properties:
- The completed deletion stays authoritative; a journal write failure never
  rolls back a project retirement (the caller logs and continues).
- The journal is bounded (oldest entries are trimmed) and strictly validated;
  a corrupt journal is reported unavailable and is never silently overwritten.
- Appends are serialized with the existing workspace mutation lock and the file
  is replaced atomically. Reads only filter by the caller's workspace.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .repositories.file.mutation_coordinator import workspace_mutation
from .storage import atomic_write


SCHEMA = "project-tombstones/1"
JOURNAL_RELATIVE = "runtime/project-tombstones.json"
MAX_ENTRIES = 2048
MAX_FILE_BYTES = 1024 * 1024
MAX_PAGE = 200
FIELDS = ("seq", "project_id", "workspace_id", "incarnation", "deleted_at")
LOCK_NAME = "project-tombstones"


class TombstoneUnavailable(RuntimeError):
    """The journal is unreadable or does not match the declared schema."""


def journal_root(repository=None) -> Path:
    """Resolve the File data root owned by the active repository when possible."""
    backend = getattr(repository, "backend", None)
    data = getattr(backend, "data", None)
    if data is not None:
        return Path(data)
    from .config import settings
    return settings.data_path()


def _journal_path(root: Path) -> Path:
    return Path(root) / JOURNAL_RELATIVE


def _empty() -> dict[str, Any]:
    return {"schema": SCHEMA, "items": []}


def _valid_identifier(value: object) -> bool:
    return isinstance(value, str) and 0 < len(value) <= 240 and not any(ord(char) < 32 for char in value)


def _load(root: Path) -> dict[str, Any]:
    path = _journal_path(root)
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return _empty()
    except OSError as exc:
        raise TombstoneUnavailable("PROJECT_DELETIONS_UNAVAILABLE") from exc
    if len(raw) > MAX_FILE_BYTES:
        raise TombstoneUnavailable("PROJECT_DELETIONS_UNAVAILABLE")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise TombstoneUnavailable("PROJECT_DELETIONS_UNAVAILABLE") from exc
    if (not isinstance(value, dict) or set(value) != {"schema", "items"}
            or value.get("schema") != SCHEMA or not isinstance(value.get("items"), list)):
        raise TombstoneUnavailable("PROJECT_DELETIONS_UNAVAILABLE")
    items: list[dict[str, Any]] = []
    previous = 0
    for row in value["items"]:
        if not isinstance(row, dict) or set(row) != set(FIELDS):
            raise TombstoneUnavailable("PROJECT_DELETIONS_UNAVAILABLE")
        seq = row.get("seq")
        if type(seq) is not int or seq <= previous:
            raise TombstoneUnavailable("PROJECT_DELETIONS_UNAVAILABLE")
        if not _valid_identifier(row.get("project_id")):
            raise TombstoneUnavailable("PROJECT_DELETIONS_UNAVAILABLE")
        if row.get("workspace_id") is not None and not _valid_identifier(row["workspace_id"]):
            raise TombstoneUnavailable("PROJECT_DELETIONS_UNAVAILABLE")
        if row.get("incarnation") is not None and not _valid_identifier(row["incarnation"]):
            raise TombstoneUnavailable("PROJECT_DELETIONS_UNAVAILABLE")
        if not _valid_identifier(row.get("deleted_at")):
            raise TombstoneUnavailable("PROJECT_DELETIONS_UNAVAILABLE")
        previous = seq
        items.append(dict(row))
    return {"schema": SCHEMA, "items": items}


def _write(root: Path, items: list[dict[str, Any]]) -> None:
    payload = json.dumps({"schema": SCHEMA, "items": items}, ensure_ascii=False,
                         indent=2, sort_keys=True)
    if len(payload.encode("utf-8")) > MAX_FILE_BYTES:
        raise TombstoneUnavailable("PROJECT_DELETIONS_UNAVAILABLE")
    atomic_write(_journal_path(root), payload)


def record(root: Path, project_id: str, *, workspace_id: str | None = None,
           incarnation: str | None = None, deleted_at: str | None = None) -> dict[str, Any]:
    """Append one deletion tombstone; the caller decides how to handle failure."""
    if not _valid_identifier(project_id):
        raise ValueError("invalid project id for tombstone")
    if workspace_id is not None and not _valid_identifier(workspace_id):
        raise ValueError("invalid workspace id for tombstone")
    if incarnation is not None and not _valid_identifier(incarnation):
        incarnation = None
    root = Path(root)
    _journal_path(root).parent.mkdir(parents=True, exist_ok=True)
    with workspace_mutation(root, LOCK_NAME):
        data = _load(root)
        sequence = (data["items"][-1]["seq"] if data["items"] else 0) + 1
        entry = {"seq": sequence, "project_id": project_id, "workspace_id": workspace_id,
                 "incarnation": incarnation,
                 "deleted_at": deleted_at or datetime.now(timezone.utc).isoformat()}
        _write(root, (data["items"] + [entry])[-MAX_ENTRIES:])
    return entry


def read_page(root: Path, *, workspace_id: str | None, after: int = 0,
              limit: int = 100) -> tuple[list[dict[str, Any]], int | None, bool]:
    """Return one bounded page of tombstones visible to the given workspace."""
    if type(after) is not int or after < 0:
        raise ValueError("invalid deletion cursor")
    if type(limit) is not int or not 1 <= limit <= MAX_PAGE:
        raise ValueError("invalid deletion page limit")
    rows = [row for row in _load(Path(root))["items"]
            if row["seq"] > after and row["workspace_id"] == workspace_id]
    page = rows[:limit]
    has_more = len(rows) > limit
    next_cursor = page[-1]["seq"] if has_more and page else None
    return page, next_cursor, has_more
