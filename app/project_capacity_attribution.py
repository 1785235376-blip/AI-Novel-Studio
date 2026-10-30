"""Bounded File-asset attribution for project capacity measurement.

Only assets whose original owner metadata declares the exact ``novel_id`` are
attributed to that project. The scanner:
- reads bounded, strict asset metadata files at the asset-library root;
- never follows reparse points/symlinks and never scans shared derived
  directories (query index, locks, caches) as if they were project content;
- counts the real metadata bytes plus the real content-file bytes, deduping the
  same physical object (same ``st_dev``/``st_ino``) once;
- reports other-project metadata and unreadable entries as aggregate counters
  only (no ids), so a project cannot learn about another project's assets;
- is read-only: no deletion, claim, repair or quota admission.

This is measurement, not an admission owner. ``allocated_storage_bytes`` stays
UNKNOWN because compressed/sparse allocation is not measured here.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import time

ATTRIBUTION = "ASSET_METADATA_PROJECT_BINDING"
MAX_METADATA_FILES = 50_000
MAX_METADATA_BYTES = 1024 * 1024
MAX_DURATION_SECONDS = 30.0
_FILE_ATTRIBUTE_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
MAX_HISTORY_FILES = 5000


class CapacityAttributionError(ValueError):
    pass


def _is_reparse(info: os.stat_result) -> bool:
    return bool(getattr(info, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT) or stat.S_ISLNK(info.st_mode)


def _entry_identity(info: os.stat_result) -> tuple[int, int]:
    return int(info.st_dev), int(info.st_ino)
def _measure_history_tree(history_root: Path, physical: set[tuple[int, int]]):
    """Bounded measurement of one asset's immutable history directory."""
    total = objects = files = 0
    pending = [history_root]
    while pending:
        current = pending.pop()
        try:
            with os.scandir(current) as entries:
                children = sorted(entries, key=lambda entry: entry.name)
        except OSError:
            raise CapacityAttributionError("CAPACITY_HISTORY_DIRECTORY_UNREADABLE") from None
        for child in children:
            try:
                info = Path(child.path).lstat()
            except OSError:
                raise CapacityAttributionError("CAPACITY_HISTORY_ENTRY_UNREADABLE") from None
            if _is_reparse(info):
                raise CapacityAttributionError("CAPACITY_HISTORY_REPARSE_POINT")
            if stat.S_ISDIR(info.st_mode):
                pending.append(Path(child.path))
                continue
            if not stat.S_ISREG(info.st_mode):
                raise CapacityAttributionError("CAPACITY_HISTORY_ENTRY_INVALID")
            files += 1
            if files > MAX_HISTORY_FILES:
                raise CapacityAttributionError("CAPACITY_HISTORY_FILE_LIMIT")
            identity = _entry_identity(info)
            if identity in physical:
                continue
            physical.add(identity)
            total += int(info.st_size)
            objects += 1
    return total, objects


def measure_assets(assets_root: Path | str, project_id: str, *,
                   max_metadata_files: int = MAX_METADATA_FILES,
                   deadline_seconds: float = MAX_DURATION_SECONDS) -> dict:
    if not isinstance(project_id, str) or not project_id or len(project_id) > 240:
        raise CapacityAttributionError("CAPACITY_ATTRIBUTION_PROJECT_INVALID")
    if type(max_metadata_files) is not int or max_metadata_files < 1:
        raise CapacityAttributionError("CAPACITY_ATTRIBUTION_LIMIT_INVALID")
    if type(deadline_seconds) not in (int, float) or not 0 < deadline_seconds <= 300:
        raise CapacityAttributionError("CAPACITY_ATTRIBUTION_LIMIT_INVALID")
    root = Path(assets_root)
    result = {"attribution": ATTRIBUTION, "assets_root": str(root), "state": "MISSING",
              "objects": 0, "logical_bytes": 0, "unknown": [], "unknown_count": 0,
              "unknown_truncated": False, "complete": True,
              "counters": {"metadata_files_scanned": 0, "other_project_metadata": 0,
                           "unreadable_entries": 0, "missing_content": 0,
                           "shared_derived_entries": "NOT_SCANNED"},
              "allocated_storage_bytes": "UNKNOWN", "deleted": False, "claimed": False}
    try:
        root_info = root.lstat()
    except FileNotFoundError:
        return result
    except OSError:
        result["state"] = "UNREADABLE"
        result["unknown"].append({"path": str(root), "reason": "ROOT_UNREADABLE"})
        result["unknown_count"] = 1
        result["complete"] = False
        return result
    if _is_reparse(root_info) or not stat.S_ISDIR(root_info.st_mode):
        result["state"] = "NOT_A_REGULAR_DIRECTORY"
        result["unknown"].append({"path": str(root), "reason": "ROOT_NOT_REGULAR_DIRECTORY"})
        result["unknown_count"] = 1
        result["complete"] = False
        return result
    result["state"] = "MEASURED"
    physical: set[tuple[int, int]] = set()
    deadline = time.monotonic() + deadline_seconds
    result["counters"].update({"content_files_seen": 0, "content_files_attributed": 0,
                               "unattributed_files": 0, "unattributed_bytes": 0,
                               "directories_skipped": 0, "history_bytes": 0, "history_objects": 0})

    def unknown(path: str, reason: str) -> None:
        if len(result["unknown"]) >= 64:
            result["unknown_truncated"] = True
        else:
            result["unknown"].append({"path": path, "reason": reason})

    try:
        with os.scandir(root) as entries:
            all_entries = sorted(entries, key=lambda entry: entry.name)
    except OSError:
        result["unknown"].append({"path": str(root), "reason": "ROOT_UNREADABLE"})
        result["unknown_count"] = 1
        result["complete"] = False
        return result

    candidates = [entry for entry in all_entries if entry.name.endswith(".json")]
    for entry in all_entries:
        if entry.name.endswith(".json"):
            continue
        try:
            stray = Path(entry.path).lstat()
        except OSError:
            result["counters"]["unreadable_entries"] += 1
            continue
        if stat.S_ISDIR(stray.st_mode) or _is_reparse(stray):
            result["counters"]["directories_skipped"] += 1
            continue
        if stat.S_ISREG(stray.st_mode):
            if entry.name.endswith(".bin"):
                result["counters"]["content_files_seen"] += 1
            else:
                # Crash residue or another owner's root-level file: keep it as
                # an aggregate signal only; admission treats it as UNKNOWN.
                result["counters"]["unattributed_files"] += 1
                result["counters"]["unattributed_bytes"] += int(stray.st_size)

    for entry in candidates:
        if result["counters"]["metadata_files_scanned"] >= max_metadata_files:
            unknown(str(root), "METADATA_FILE_LIMIT")
            break
        if time.monotonic() > deadline:
            unknown(str(root), "DEADLINE")
            break
        result["counters"]["metadata_files_scanned"] += 1
        metadata_path = Path(entry.path)
        try:
            info = metadata_path.lstat()
        except OSError:
            result["counters"]["unreadable_entries"] += 1
            continue
        if _is_reparse(info):
            unknown(str(metadata_path), "REPARSE_POINT")
            continue
        if not stat.S_ISREG(info.st_mode):
            unknown(str(metadata_path), "NOT_A_REGULAR_FILE")
            continue
        if info.st_size > MAX_METADATA_BYTES:
            unknown(str(metadata_path), "METADATA_SIZE_LIMIT")
            continue
        try:
            raw = metadata_path.read_bytes()
            metadata = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeError, ValueError):
            result["counters"]["unreadable_entries"] += 1
            continue
        if not isinstance(metadata, dict):
            result["counters"]["unreadable_entries"] += 1
            continue
        project = metadata.get("novel_id")
        if project != project_id:
            result["counters"]["other_project_metadata"] += 1
            continue
        asset_id = metadata.get("id")
        if not isinstance(asset_id, str) or not asset_id or "/" in asset_id or "\\" in asset_id:
            unknown(str(metadata_path), "METADATA_INVALID")
            continue
        content_path = root / f"{asset_id}.bin"
        try:
            content_info = content_path.lstat()
        except FileNotFoundError:
            result["counters"]["missing_content"] += 1
            continue
        except OSError:
            result["counters"]["unreadable_entries"] += 1
            continue
        if _is_reparse(content_info):
            unknown(str(content_path), "REPARSE_POINT")
            continue
        if not stat.S_ISREG(content_info.st_mode):
            unknown(str(content_path), "NOT_A_REGULAR_FILE")
            continue
        content_identity = _entry_identity(content_info)
        metadata_identity = _entry_identity(info)
        added = 0
        if metadata_identity not in physical:
            physical.add(metadata_identity)
            added += len(raw)
            result["objects"] += 1
        if content_identity not in physical:
            physical.add(content_identity)
            added += int(content_info.st_size)
            result["objects"] += 1
        result["logical_bytes"] += added
        result["counters"]["content_files_attributed"] += 1
        history_root = root / ".audio-history" / asset_id
        try:
            history_info = history_root.lstat()
        except FileNotFoundError:
            history_info = None
        except OSError:
            unknown(str(history_root), "HISTORY_UNREADABLE")
            history_info = None
        if history_info is not None:
            if _is_reparse(history_info) or not stat.S_ISDIR(history_info.st_mode):
                unknown(str(history_root), "HISTORY_NOT_REGULAR_DIRECTORY")
            else:
                try:
                    history_bytes, history_objects = _measure_history_tree(history_root, physical)
                except CapacityAttributionError as exc:
                    unknown(str(history_root), str(exc))
                else:
                    result["logical_bytes"] += history_bytes
                    result["objects"] += history_objects
                    result["counters"]["history_bytes"] += history_bytes
                    result["counters"]["history_objects"] += history_objects
    result["unknown_count"] = len(result["unknown"])
    result["complete"] = not result["unknown"] and not result["unknown_truncated"]
    return result


