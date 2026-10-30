"""Read-only project storage measurement primitives for the capacity owner.

This module measures *logical file length* (``st_size``) of objects already
attributed to a project by the caller. It never scans unrelated directories,
never follows reparse points/symlinks out of a root, never deletes, claims or
repairs anything, and never reports allocated/compressed/sparse storage as if it
were measured.

Rules encoded (see ``PROJECT_CAPACITY_CLOSURE_LEDGER_20261030.md``):
- same physical object (same ``st_dev``/``st_ino`` observed on the same root
  walk) is counted once;
- two physical files with identical bytes/digest are still two objects and are
  counted separately (this module never hashes to deduplicate);
- reparse points, non-regular files, missing roots and read errors are reported
  as UNKNOWN and excluded from the measured byte total;
- the result is diagnostics, never quota admission by itself.
"""
from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

MEASUREMENT = "LOGICAL_FILE_LENGTH_NOT_ALLOCATED"
MAX_OBJECTS = 200_000
MAX_UNKNOWN_ENTRIES = 256
_FILE_ATTRIBUTE_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


class CapacityMeasurementError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class MeasuredRoot:
    label: str
    path: Path


def _normalized_roots(roots: Iterable[tuple[str, Path | str] | MeasuredRoot]) -> list[MeasuredRoot]:
    normalized: list[MeasuredRoot] = []
    seen: set[str] = set()
    for item in roots:
        root = item if isinstance(item, MeasuredRoot) else MeasuredRoot(str(item[0]), Path(item[1]))
        if not root.label or root.label in seen:
            raise CapacityMeasurementError("CAPACITY_ROOT_LABEL_INVALID")
        seen.add(root.label)
        normalized.append(root)
    if not normalized:
        raise CapacityMeasurementError("CAPACITY_ROOTS_EMPTY")
    return normalized


def _is_reparse(entry: os.stat_result) -> bool:
    return bool(getattr(entry, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT) or stat.S_ISLNK(entry.st_mode)


def measure_roots(roots: Iterable[tuple[str, Path | str] | MeasuredRoot],
                  *, max_objects: int = MAX_OBJECTS) -> dict:
    """Measure project-attributed roots and return bounded diagnostics.

    ``logical_bytes`` counts each distinct physical regular file once.
    ``unknown`` lists objects/reasons that prevent an authoritative measurement;
    callers must treat a non-empty ``unknown`` set as "measurement incomplete"
    and must not use this result to admit new writes.
    """
    if type(max_objects) is not int or max_objects < 1:
        raise CapacityMeasurementError("CAPACITY_OBJECT_LIMIT_INVALID")
    measured_roots = _normalized_roots(roots)
    objects = 0
    logical_bytes = 0
    physical: set[tuple[int, int]] = set()
    unknown: list[dict] = []
    root_views: list[dict] = []
    truncated = False

    def record_unknown(path: str, reason: str) -> None:
        nonlocal truncated
        if len(unknown) >= MAX_UNKNOWN_ENTRIES:
            truncated = True
            return
        unknown.append({"path": path, "reason": reason})

    for root in measured_roots:
        view = {"label": root.label, "path": str(root.path), "state": "MISSING",
                "objects": 0, "logical_bytes": 0}
        try:
            info = root.path.lstat()
        except FileNotFoundError:
            root_views.append(view)
            continue
        except OSError:
            view["state"] = "UNREADABLE"
            record_unknown(str(root.path), "ROOT_UNREADABLE")
            root_views.append(view)
            continue
        if _is_reparse(info) or not stat.S_ISDIR(info.st_mode):
            view["state"] = "NOT_A_REGULAR_DIRECTORY"
            record_unknown(str(root.path), "ROOT_NOT_REGULAR_DIRECTORY")
            root_views.append(view)
            continue
        view["state"] = "MEASURED"
        pending = [root.path]
        while pending:
            if objects >= max_objects:
                truncated = True
                record_unknown(str(pending[0]) if pending else str(root.path), "OBJECT_LIMIT")
                break
            current = pending.pop()
            try:
                with os.scandir(current) as entries:
                    children = sorted(entries, key=lambda entry: entry.name)
            except OSError:
                record_unknown(str(current), "DIRECTORY_UNREADABLE")
                continue
            for child in children:
                try:
                    # Windows DirEntry.stat(follow_symlinks=False) can report
                    # zero device/inode; lstat is the authoritative identity.
                    child_info = Path(child.path).lstat()
                except OSError:
                    record_unknown(child.path, "ENTRY_UNREADABLE")
                    continue
                if _is_reparse(child_info):
                    record_unknown(child.path, "REPARSE_POINT")
                    continue
                if stat.S_ISDIR(child_info.st_mode):
                    pending.append(Path(child.path))
                    continue
                if not stat.S_ISREG(child_info.st_mode):
                    record_unknown(child.path, "NOT_A_REGULAR_FILE")
                    continue
                identity = (child_info.st_dev, child_info.st_ino)
                objects += 1
                if identity in physical:
                    view["duplicate_entries"] = view.get("duplicate_entries", 0) + 1
                    continue
                physical.add(identity)
                logical_bytes += int(child_info.st_size)
                view["objects"] += 1
                view["logical_bytes"] += int(child_info.st_size)
        root_views.append(view)

    return {"measurement": MEASUREMENT,
            "logical_bytes": logical_bytes,
            "objects": len(physical),
            "walked_objects": objects,
            "roots": root_views,
            "unknown": unknown,
            "unknown_count": len(unknown),
            "unknown_truncated": truncated,
            "complete": not unknown and not truncated,
            "allocated_storage_bytes": "UNKNOWN",
            "physical_dedupe": "SAME_DEV_INO_COUNTED_ONCE",
            "digest_dedupe": "NOT_PERFORMED",
            "deleted": False,
            "claimed": False}


def attribute_roots(project_root: Path | str, *, extra: Mapping[str, Path | str] | None = None) -> list[tuple[str, Path]]:
    """Return the project-owned roots a caller may explicitly attribute.

    Only the project's own directory and caller-declared extra roots are used;
    shared directories (other projects, cache, model center) are never guessed.
    """
    root = Path(project_root)
    roots: list[tuple[str, Path]] = [("project", root)]
    for label, path in sorted((extra or {}).items()):
        roots.append((str(label), Path(path)))
    return roots

