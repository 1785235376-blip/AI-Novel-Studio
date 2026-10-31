"""Flag-gated capacity admission protocol for one bounded File asset write.

This module is the bridge between the capacity ledger and a real content writer.
It is deliberately inactive unless ``ENABLE_PROJECT_CAPACITY_ADMISSION`` is
enabled; even when enabled it only admits the caller-provided write after:

1. measuring the original owners (project root + metadata-attributed assets);
2. persisting that measurement through ``ledger.reconcile`` so the baseline is
   never stale client input;
3. refusing when any unproven object exists (UNKNOWN, unreadable metadata,
   missing content, or root-level crash residue);
4. reserving the incoming content bytes plus a bounded metadata/staging peak;
5. converting the landed bytes (content + metadata) from the reservation and
   never exceeding the reserved peak.

A failed write reconciles first so any landed residue stays charged instead of
being released as free space. All limits/errors are fail-closed.
"""
from __future__ import annotations

from pathlib import Path
import stat
from typing import Any

from .project_capacity import (
    CapacityLedgerUnavailable,
    CapacityRefused,
    ProjectCapacityLedger,
)
from .project_capacity_attribution import measure_assets
from .project_capacity_measurement import measure_roots

METADATA_PEAK_BYTES = 1024 * 1024
DEFAULT_TTL_SECONDS = 900
_FILE_ATTRIBUTE_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


class CapacityAdmissionRefused(ValueError):
    def __init__(self, code: str, details: dict | None = None):
        self.code = code
        self.details = details or {}
        super().__init__(code)


def _is_reparse(info: Any) -> bool:
    return bool(getattr(info, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT) or stat.S_ISLNK(info.st_mode)


def unproven_objects(measurement: dict, assets: dict) -> int:
    counters = assets["counters"]
    return (measurement["unknown_count"] + assets["unknown_count"]
            + counters["unreadable_entries"] + counters["missing_content"]
            + counters["unattributed_files"])


class CapacityAdmission:
    """One admission session bound to a project and its original owners."""

    def __init__(self, ledger: ProjectCapacityLedger, *, project_id: str, project_root: Path | str,
                 assets_root: Path | str, actor_id: str, incarnation: str | None = None,
                 operation: str = "asset.write", metadata_peak_bytes: int = METADATA_PEAK_BYTES,
                 ttl_seconds: int = DEFAULT_TTL_SECONDS):
        if (type(metadata_peak_bytes) is not int or metadata_peak_bytes < 1
                or metadata_peak_bytes > 64 * 1024 * 1024):
            raise CapacityAdmissionRefused("PROJECT_CAPACITY_RESERVATION_INVALID")
        self.ledger = ledger
        self.project_id = project_id
        self.project_root = Path(project_root)
        self.assets_root = Path(assets_root)
        self.actor_id = actor_id
        self.incarnation = incarnation
        self.operation = operation
        self.metadata_peak_bytes = metadata_peak_bytes
        self.ttl_seconds = ttl_seconds

    def measure(self) -> dict:
        measurement = measure_roots([("project", self.project_root)])
        assets = measure_assets(self.assets_root, self.project_id)
        unknown = unproven_objects(measurement, assets)
        return {"measurement": measurement, "assets": assets, "unknown_objects": unknown,
                "logical_bytes": measurement["logical_bytes"] + assets["logical_bytes"]}

    def _reconcile(self) -> dict:
        measured = self.measure()
        try:
            view = self.ledger.reconcile(
                self.project_id, measured_bytes=measured["logical_bytes"],
                unknown_objects=measured["unknown_objects"],
                incarnation=self.incarnation, actor_id=self.actor_id)
        except CapacityLedgerUnavailable as exc:
            raise CapacityAdmissionRefused(exc.code) from None
        except CapacityRefused as exc:
            raise CapacityAdmissionRefused(exc.code, exc.details) from None
        return {"view": view, "measurement": measured}

    def begin(self, incoming_bytes: int, *, incarnation: str | None = None) -> dict:
        """Reconcile the baseline, refuse unknown objects, reserve the peak."""
        if type(incoming_bytes) is not int or incoming_bytes < 1 or incoming_bytes > 512 * 1024 * 1024:
            raise CapacityAdmissionRefused("PROJECT_CAPACITY_RESERVATION_INVALID")
        if incarnation is not None:
            self.incarnation = incarnation
        reconciled = self._reconcile()
        view = reconciled["view"]
        if view["unknown"]["blocked"]:
            raise CapacityAdmissionRefused("PROJECT_CAPACITY_UNKNOWN_BLOCKED",
                                           {"unknown_objects": view["unknown"]["objects"]})
        reserved = incoming_bytes + self.metadata_peak_bytes
        try:
            reservation = self.ledger.reserve(
                self.project_id, reserved, operation=self.operation,
                actor_id=self.actor_id, ttl_seconds=self.ttl_seconds,
                incarnation=self.incarnation)
        except CapacityRefused as exc:
            raise CapacityAdmissionRefused(exc.code, exc.details) from None
        except CapacityLedgerUnavailable as exc:
            raise CapacityAdmissionRefused(exc.code) from None
        return {"reservation_id": reservation["reservation_id"],
                "reserved_bytes": reserved,
                "incoming_bytes": incoming_bytes,
                "expires_at": reservation["expires_at"],
                "capacity": reservation["capacity"]}

    def commit(self, reservation_id: str, actual_bytes: int) -> dict:
        if type(actual_bytes) is not int or actual_bytes < 0:
            raise CapacityAdmissionRefused("PROJECT_CAPACITY_COMMIT_INVALID")
        try:
            return self.ledger.commit(self.project_id, reservation_id, actual_bytes,
                                      actor_id=self.actor_id)
        except CapacityRefused as exc:
            if exc.code == "PROJECT_CAPACITY_COMMIT_EXCEEDS_RESERVATION":
                # Content landed outside the reserved peak: charge it from a
                # fresh authoritative measurement instead of hiding it.
                self._reconcile()
                raise CapacityAdmissionRefused("PROJECT_CAPACITY_ACCOUNTING_EXCEEDED") from None
            raise CapacityAdmissionRefused(exc.code, exc.details) from None
        except CapacityLedgerUnavailable as exc:
            raise CapacityAdmissionRefused(exc.code) from None

    def abort(self, reservation_id: str, *, reason: str = "ABORTED") -> dict:
        try:
            return self.ledger.release(self.project_id, reservation_id,
                                       actor_id=self.actor_id, reason=reason)
        except (CapacityRefused, CapacityLedgerUnavailable):
            return {}

    def reconcile(self) -> dict:
        return self._reconcile()

    def reconcile_and_release(self, reservation_id: str, *, reason: str = "FAILED_WRITE") -> dict:
        """Account any landed residue first, then retire the reservation."""
        reconciled = self._reconcile()
        self.abort(reservation_id, reason=reason)
        return reconciled

    def landed_bytes(self, asset_id: str, *, content_suffix: str = "bin",
                     metadata_suffix: str = "json") -> int:
        """Actual bytes written by the original asset owner for one asset."""
        total = 0
        for suffix in (content_suffix, metadata_suffix):
            path = self.assets_root / f"{asset_id}.{suffix}"
            try:
                info = path.lstat()
            except OSError:
                raise CapacityAdmissionRefused("PROJECT_CAPACITY_ADMISSION_LANDED_UNKNOWN") from None
            if _is_reparse(info) or not stat.S_ISREG(info.st_mode):
                raise CapacityAdmissionRefused("PROJECT_CAPACITY_ADMISSION_LANDED_UNKNOWN")
            total += int(info.st_size)
        return total
