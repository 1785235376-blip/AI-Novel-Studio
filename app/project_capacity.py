"""Persistent project capacity ledger: limits, reservations, commit, reconcile.

The ledger is the project-wide accounting owner for the File data directory. It
owns only numbers and reservation identities; it never stores project content,
never deletes files and never grants read/write authority. Callers must still
enforce the original project/session/incarnation authority around any mutation
(``project_management_lease`` for limit changes; the asset owner for writes).

Contract (see ``PROJECT_CAPACITY_CLOSURE_LEDGER_20261030.md``):
- reserve before writing; the landed bytes are converted from that reservation to
  used bytes by ``commit``; the same bytes are never counted as both used and a
  full reservation;
- a failed write that still occupies space keeps its used bytes; a released
  reservation must not free bytes that were actually landed;
- unproven/unknown objects block *new reservations* for that project, stay
  readable and diagnostic-only, and are never deleted or claimed here;
- lowering a limit below used+active-reservations only shows over-limit and
  refuses new reservations; it never cancels an existing valid reservation;
- adjustment requires the caller-supplied original management lease, a CAS on
  the ledger version and a persistent audit entry;
- a corrupt or unreadable ledger fails closed and is never overwritten.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import socket
import threading
import uuid
from typing import Any, Callable

from .repositories.file.mutation_coordinator import workspace_mutation
from .storage import atomic_write

SCHEMA = "project-capacity/1"
DEFAULT_LIMIT_BYTES = 512 * 1024 * 1024
MAX_LIMIT_BYTES = 64 * 1024 * 1024 * 1024
MAX_RESERVATION_BYTES = 4 * 1024 * 1024 * 1024
MAX_AUDIT_ENTRIES = 32
MAX_FILE_BYTES = 1024 * 1024
_LOCK_NAME = "project-capacity"


class CapacityLedgerUnavailable(RuntimeError):
    def __init__(self, code: str = "PROJECT_CAPACITY_LEDGER_UNAVAILABLE"):
        self.code = code
        super().__init__(code)


class CapacityRefused(ValueError):
    def __init__(self, code: str, details: dict | None = None):
        self.code = code
        self.details = details or {}
        super().__init__(code)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: object) -> float:
    if not isinstance(value, str) or not value:
        raise CapacityLedgerUnavailable()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        raise CapacityLedgerUnavailable() from None


def _positive_int(value: object, *, maximum: int, code: str) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise CapacityRefused(code)
    return value


def _nonnegative_int(value: object, *, code: str) -> int:
    if type(value) is not int or value < 0:
        raise CapacityRefused(code)
    return value


class ProjectCapacityLedger:
    """One JSON ledger with cross-process serialization and strict validation."""

    def __init__(self, path: Path | str, *, pid: int | None = None,
                 hostname: str | None = None, clock: Callable[[], float] | None = None,
                 default_limit_bytes: int = DEFAULT_LIMIT_BYTES):
        self.path = Path(path)
        self.root = self.path.parent.parent
        self._pid = os.getpid() if pid is None else pid
        self._hostname = socket.gethostname() if hostname is None else hostname
        self._clock = clock or (lambda: datetime.now(timezone.utc).timestamp())
        self._default_limit = _positive_int(default_limit_bytes, maximum=MAX_LIMIT_BYTES,
                                            code="PROJECT_CAPACITY_LIMIT_INVALID")
        self._thread_lock = threading.RLock()

    # -- persistence -------------------------------------------------------
    def _empty(self) -> dict:
        return {"schema": SCHEMA, "version": 0, "projects": {}}

    def _load(self) -> dict:
        try:
            raw = self.path.read_bytes()
        except FileNotFoundError:
            return self._empty()
        except OSError as exc:
            raise CapacityLedgerUnavailable() from exc
        if len(raw) > MAX_FILE_BYTES:
            raise CapacityLedgerUnavailable()
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeError, ValueError) as exc:
            raise CapacityLedgerUnavailable() from exc
        if (not isinstance(value, dict) or set(value) != {"schema", "version", "projects"}
                or value.get("schema") != SCHEMA or type(value.get("version")) is not int
                or value["version"] < 0 or not isinstance(value.get("projects"), dict)):
            raise CapacityLedgerUnavailable()
        projects: dict[str, dict] = {}
        for project_id, record in value["projects"].items():
            projects[project_id] = self._validate_record(project_id, record)
        return {"schema": SCHEMA, "version": value["version"], "projects": projects}

    def _validate_record(self, project_id: object, record: object) -> dict:
        if not isinstance(project_id, str) or not project_id or len(project_id) > 240:
            raise CapacityLedgerUnavailable()
        if not isinstance(record, dict) or set(record) != {
                "incarnation", "limit_bytes", "used_bytes", "reservations", "unknown",
                "audit", "updated_at", "reconciled_at"}:
            raise CapacityLedgerUnavailable()
        if record["incarnation"] is not None and not isinstance(record["incarnation"], str):
            raise CapacityLedgerUnavailable()
        limit = _positive_int(record["limit_bytes"], maximum=MAX_LIMIT_BYTES,
                              code="PROJECT_CAPACITY_LEDGER_INVALID")
        try:
            used = _nonnegative_int(record["used_bytes"], code="PROJECT_CAPACITY_LEDGER_INVALID")
        except CapacityRefused as exc:
            raise CapacityLedgerUnavailable() from exc
        if used > MAX_RESERVATION_BYTES:
            raise CapacityLedgerUnavailable()
        if not isinstance(record["reservations"], dict):
            raise CapacityLedgerUnavailable()
        reservations = {}
        for reservation_id, item in record["reservations"].items():
            if not isinstance(reservation_id, str) or not isinstance(item, dict) or set(item) != {
                    "bytes", "created_at", "expires_at", "operation", "owner_pid",
                    "owner_host", "actor_id"}:
                raise CapacityLedgerUnavailable()
            _positive_int(item["bytes"], maximum=MAX_RESERVATION_BYTES,
                          code="PROJECT_CAPACITY_LEDGER_INVALID")
            _parse_iso(item["created_at"]); _parse_iso(item["expires_at"])
            for key in ("operation", "owner_host", "actor_id"):
                if not isinstance(item[key], str):
                    raise CapacityLedgerUnavailable()
            if type(item["owner_pid"]) is not int or item["owner_pid"] < 0:
                raise CapacityLedgerUnavailable()
            reservations[reservation_id] = dict(item)
        unknown = record["unknown"]
        if (not isinstance(unknown, dict) or set(unknown) != {"objects", "blocked"}
                or type(unknown["objects"]) is not int or unknown["objects"] < 0
                or not isinstance(unknown["blocked"], bool)):
            raise CapacityLedgerUnavailable()
        if not isinstance(record["audit"], list) or len(record["audit"]) > MAX_AUDIT_ENTRIES:
            raise CapacityLedgerUnavailable()
        for entry in record["audit"]:
            if (not isinstance(entry, dict) or not isinstance(entry.get("action"), str)
                    or not isinstance(entry.get("at"), str) or not isinstance(entry.get("actor_id"), str)):
                raise CapacityLedgerUnavailable()
        _parse_iso(record["updated_at"])
        if record["reconciled_at"] is not None:
            _parse_iso(record["reconciled_at"])
        return {"incarnation": record["incarnation"], "limit_bytes": limit,
                "used_bytes": used, "reservations": reservations, "unknown": dict(unknown),
                "audit": [dict(entry) for entry in record["audit"]],
                "updated_at": record["updated_at"], "reconciled_at": record["reconciled_at"]}

    def _write(self, data: dict) -> None:
        payload = json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        if len(payload.encode("utf-8")) > MAX_FILE_BYTES:
            raise CapacityLedgerUnavailable()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(self.path, payload)
        # Never report success for state this owner cannot read back.
        self._load()

    @contextmanager
    def _locked(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._thread_lock:
            with workspace_mutation(self.root, _LOCK_NAME):
                yield

    def _record(self, data: dict, project_id: str) -> dict:
        record = data["projects"].get(project_id)
        if record is None:
            record = {"incarnation": None, "limit_bytes": self._default_limit,
                      "used_bytes": 0, "reservations": {}, "unknown": {"objects": 0, "blocked": False},
                      "audit": [], "updated_at": _now_iso(), "reconciled_at": None}
            data["projects"][project_id] = record
        return record

    def _audit(self, record: dict, action: str, actor_id: str, **details: Any) -> None:
        entry = {"action": action, "at": _now_iso(), "actor_id": str(actor_id or "")[:240]}
        entry.update({key: value for key, value in details.items() if value is not None})
        record["audit"] = (record["audit"] + [entry])[-MAX_AUDIT_ENTRIES:]

    def _active_reserved(self, record: dict) -> int:
        return sum(item["bytes"] for item in record["reservations"].values())

    def _expire_stale(self, record: dict, now: float) -> None:
        for reservation_id, item in list(record["reservations"].items()):
            if _parse_iso(item["expires_at"]) <= now:
                self._audit(record, "RESERVATION_EXPIRED", "capacity-owner",
                            reservation_id=reservation_id, bytes=item["bytes"],
                            operation=item["operation"])
                record["reservations"].pop(reservation_id, None)


    def _view(self, project_id: str, record: dict, ledger_version: int) -> dict:
        reserved = self._active_reserved(record)
        limit = record["limit_bytes"]
        remaining = max(0, limit - record["used_bytes"] - reserved)
        if record["unknown"]["blocked"]:
            state = "UNKNOWN_BLOCKED"
        elif record["used_bytes"] + reserved > limit:
            state = "OVER_LIMIT"
        else:
            state = "OK"
        return {"project_id": project_id, "incarnation": record["incarnation"],
                "ledger_version": ledger_version,
                "limit_bytes": limit, "used_bytes": record["used_bytes"],
                "reserved_bytes": reserved, "remaining_bytes": remaining, "state": state,
                "reservations": len(record["reservations"]),
                "unknown": dict(record["unknown"]),
                "reconciled_at": record["reconciled_at"], "updated_at": record["updated_at"]}

    # -- public operations -------------------------------------------------
    def snapshot(self, project_id: str) -> dict:
        with self._locked():
            data = self._load()
            record = data["projects"].get(project_id)
            if record is None:
                raise CapacityLedgerUnavailable("PROJECT_CAPACITY_NOT_INITIALIZED")
            return self._view(project_id, record, data["version"])

    def peek(self, project_id: str) -> dict | None:
        """Read-only snapshot that never creates, locks or initializes files."""
        data = self._load()
        record = data["projects"].get(project_id)
        return None if record is None else self._view(project_id, record, data["version"])
    def reserve(self, project_id: str, incoming_bytes: int, *, operation: str,
                actor_id: str, ttl_seconds: int = 900, incarnation: str | None = None) -> dict:
        size = _positive_int(incoming_bytes, maximum=MAX_RESERVATION_BYTES,
                             code="PROJECT_CAPACITY_RESERVATION_INVALID")
        ttl = _positive_int(ttl_seconds, maximum=24 * 3600, code="PROJECT_CAPACITY_RESERVATION_INVALID")
        if not isinstance(operation, str) or not operation or len(operation) > 120:
            raise CapacityRefused("PROJECT_CAPACITY_RESERVATION_INVALID")
        with self._locked():
            data = self._load()
            record = self._record(data, project_id)
            now = self._clock()
            self._expire_stale(record, now)
            if record["unknown"]["blocked"]:
                raise CapacityRefused("PROJECT_CAPACITY_UNKNOWN_BLOCKED",
                                      {"unknown_objects": record["unknown"]["objects"]})
            if incarnation is not None and record["incarnation"] not in (None, incarnation):
                raise CapacityRefused("PROJECT_CAPACITY_INCARNATION_CHANGED")
            if record["incarnation"] is None and incarnation is not None:
                record["incarnation"] = incarnation
            reserved = self._active_reserved(record)
            if record["used_bytes"] + reserved + size > record["limit_bytes"]:
                raise CapacityRefused("PROJECT_CAPACITY_EXCEEDED",
                                      {"limit_bytes": record["limit_bytes"], "used_bytes": record["used_bytes"],
                                       "reserved_bytes": reserved, "requested_bytes": size})
            expires_at = datetime.fromtimestamp(now + ttl, timezone.utc).isoformat()
            reservation_id = str(uuid.uuid4())
            record["reservations"][reservation_id] = {
                "bytes": size, "created_at": _now_iso(), "expires_at": expires_at,
                "operation": operation, "owner_pid": self._pid, "owner_host": self._hostname,
                "actor_id": str(actor_id or "")[:240]}
            record["updated_at"] = _now_iso()
            self._audit(record, "RESERVE", actor_id, reservation_id=reservation_id,
                        bytes=size, operation=operation)
            data["version"] += 1
            self._write(data)
            return {"reservation_id": reservation_id, "expires_at": expires_at,
                    "bytes": size, "capacity": self._view(project_id, record, data["version"])}

    def commit(self, project_id: str, reservation_id: str, actual_bytes: int, *,
               actor_id: str) -> dict:
        actual = _nonnegative_int(actual_bytes, code="PROJECT_CAPACITY_COMMIT_INVALID")
        with self._locked():
            data = self._load()
            record = data["projects"].get(project_id)
            if record is None:
                raise CapacityLedgerUnavailable("PROJECT_CAPACITY_NOT_INITIALIZED")
            reservation = record["reservations"].get(reservation_id)
            if reservation is None:
                raise CapacityRefused("PROJECT_CAPACITY_RESERVATION_UNKNOWN")
            if actual > reservation["bytes"]:
                raise CapacityRefused("PROJECT_CAPACITY_COMMIT_EXCEEDS_RESERVATION")
            if actual > 2 * 1024 * 1024 * 1024:
                raise CapacityRefused("PROJECT_CAPACITY_COMMIT_INVALID")
            record["used_bytes"] += actual
            record["reservations"].pop(reservation_id, None)
            record["updated_at"] = _now_iso()
            self._audit(record, "COMMIT", actor_id, reservation_id=reservation_id,
                        reserved_bytes=reservation["bytes"], actual_bytes=actual)
            data["version"] += 1
            self._write(data)
            return self._view(project_id, record, data["version"])

    def release(self, project_id: str, reservation_id: str, *, actor_id: str,
                reason: str = "RELEASED") -> dict:
        if not isinstance(reason, str) or not reason:
            raise CapacityRefused("PROJECT_CAPACITY_RELEASE_INVALID")
        with self._locked():
            data = self._load()
            record = data["projects"].get(project_id)
            if record is None:
                raise CapacityLedgerUnavailable("PROJECT_CAPACITY_NOT_INITIALIZED")
            reservation = record["reservations"].get(reservation_id)
            if reservation is None:
                raise CapacityRefused("PROJECT_CAPACITY_RESERVATION_UNKNOWN")
            record["reservations"].pop(reservation_id, None)
            record["updated_at"] = _now_iso()
            self._audit(record, "RELEASE", actor_id, reservation_id=reservation_id,
                        bytes=reservation["bytes"], operation=reservation["operation"], reason=reason)
            data["version"] += 1
            self._write(data)
            return self._view(project_id, record, data["version"])

    def reconcile(self, project_id: str, *, measured_bytes: int, unknown_objects: int,
                  incarnation: str | None, actor_id: str) -> dict:
        measured = _nonnegative_int(measured_bytes, code="PROJECT_CAPACITY_RECONCILE_INVALID")
        if type(unknown_objects) is not int or unknown_objects < 0:
            raise CapacityRefused("PROJECT_CAPACITY_RECONCILE_INVALID")
        with self._locked():
            data = self._load()
            record = self._record(data, project_id)
            now = self._clock()
            self._expire_stale(record, now)
            if incarnation is not None and record["incarnation"] not in (None, incarnation):
                raise CapacityRefused("PROJECT_CAPACITY_INCARNATION_CHANGED")
            record["incarnation"] = incarnation if incarnation is not None else record["incarnation"]
            record["used_bytes"] = measured
            record["unknown"] = {"objects": unknown_objects, "blocked": unknown_objects > 0}
            record["reconciled_at"] = _now_iso()
            record["updated_at"] = _now_iso()
            self._audit(record, "RECONCILE", actor_id, measured_bytes=measured,
                        unknown_objects=unknown_objects,
                        active_reservations=len(record["reservations"]))
            data["version"] += 1
            self._write(data)
            return self._view(project_id, record, data["version"])

    def adjust_limit(self, project_id: str, limit_bytes: int, *, expected_version: int,
                     lease: dict, actor_id: str) -> dict:
        limit = _positive_int(limit_bytes, maximum=MAX_LIMIT_BYTES,
                              code="PROJECT_CAPACITY_LIMIT_INVALID")
        if (not isinstance(lease, dict) or lease.get("novel_id") != project_id
                or not isinstance(lease.get("incarnation"), str) or not lease["incarnation"]):
            raise CapacityRefused("PROJECT_CAPACITY_ADJUSTMENT_UNSCOPED")
        with self._locked():
            data = self._load()
            record = self._record(data, project_id)
            if record["incarnation"] not in (None, lease["incarnation"]):
                raise CapacityRefused("PROJECT_CAPACITY_INCARNATION_CHANGED")
            if record["incarnation"] is None:
                record["incarnation"] = lease["incarnation"]
            if type(expected_version) is not int or expected_version != data["version"]:
                raise CapacityRefused("PROJECT_CAPACITY_VERSION_CONFLICT",
                                      {"expected_version": expected_version, "current_version": data["version"]})
            previous = record["limit_bytes"]
            record["limit_bytes"] = limit
            record["updated_at"] = _now_iso()
            self._audit(record, "LIMIT_CHANGE", actor_id, previous_limit_bytes=previous,
                        limit_bytes=limit, incarnation=lease["incarnation"])
            data["version"] += 1
            self._write(data)
            return self._view(project_id, record, data["version"])



