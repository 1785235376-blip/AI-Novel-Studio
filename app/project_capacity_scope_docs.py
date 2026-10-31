"""Read-only attribution of experimental scope documents to one project.

ExperimentalStore keeps one canonical JSON document per (novel id, scope) under
experimental_v1/<scope-key>.json. It is project-owned bytes but is not inside
the novels/<nid> root measured by the capacity owner. This bounded reader only
attributes files whose top-level novel_id equals the requested project; it never
writes, deletes or claims a document.
"""
from __future__ import annotations

import json
import os
import stat
import time
from pathlib import Path

MAX_FILES = 20_000
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_DURATION_SECONDS = 20.0
_ATTRIBUTE = "EXPERIMENTAL_SCOPE_DOCUMENT"


def measure_scope_documents(root, project_id: str, *, max_files: int = MAX_FILES,
                            deadline_seconds: float = MAX_DURATION_SECONDS) -> dict:
    if not isinstance(project_id, str) or not project_id or len(project_id) > 240:
        raise ValueError("CAPACITY_SCOPE_DOCUMENT_PROJECT_INVALID")
    if type(max_files) is not int or max_files < 1:
        raise ValueError("CAPACITY_SCOPE_DOCUMENT_LIMIT_INVALID")
    base = Path(root) / "experimental_v1"
    result = {"attribution": _ATTRIBUTE, "state": "MISSING", "bytes": 0, "objects": 0,
              "unknown_count": 0, "unknown": [], "truncated": False, "complete": True,
              "counters": {"files_scanned": 0, "files_attributed": 0,
                           "other_project_files": 0, "unreadable_entries": 0,
                           "oversized_files": 0}}
    try:
        info = base.lstat()
    except FileNotFoundError:
        return result
    except OSError:
        result.update(state="UNREADABLE", unknown_count=1, complete=False,
                      unknown=[{"path": str(base), "reason": "SCOPE_DOCUMENT_ROOT_UNREADABLE"}])
        return result
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        result.update(state="NOT_A_REGULAR_DIRECTORY", unknown_count=1, complete=False,
                      unknown=[{"path": str(base), "reason": "SCOPE_DOCUMENT_ROOT_INVALID"}])
        return result
    result["state"] = "MEASURED"
    deadline = time.monotonic() + deadline_seconds
    try:
        with os.scandir(base) as entries:
            items = sorted(entries, key=lambda entry: entry.name)
    except OSError:
        result.update(state="UNREADABLE", unknown_count=1, complete=False,
                      unknown=[{"path": str(base), "reason": "SCOPE_DOCUMENT_ROOT_UNREADABLE"}])
        return result
    seen = set()
    for entry in items:
        if result["counters"]["files_scanned"] >= max_files or time.monotonic() > deadline:
            result["truncated"] = True
            result["complete"] = False
            result["unknown_count"] += 1
            result["unknown"].append({"path": str(base), "reason": "SCOPE_DOCUMENT_LIMIT"})
            break
        if not entry.name.endswith(".json"):
            continue
        result["counters"]["files_scanned"] += 1
        path = Path(entry.path)
        try:
            stat_result = path.lstat()
        except OSError:
            result["counters"]["unreadable_entries"] += 1
            continue
        if stat.S_ISLNK(stat_result.st_mode) or not stat.S_ISREG(stat_result.st_mode):
            result["counters"]["unreadable_entries"] += 1
            continue
        if stat_result.st_size > MAX_FILE_BYTES:
            result["counters"]["oversized_files"] += 1
            result["unknown_count"] += 1
            result["unknown"].append({"path": str(path), "reason": "SCOPE_DOCUMENT_SIZE_LIMIT"})
            continue
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            result["counters"]["unreadable_entries"] += 1
            continue
        if not isinstance(document, dict):
            result["counters"]["unreadable_entries"] += 1
            continue
        if document.get("novel_id") != project_id:
            result["counters"]["other_project_files"] += 1
            continue
        identity = (int(stat_result.st_dev), int(stat_result.st_ino))
        if identity in seen:
            continue
        seen.add(identity)
        result["bytes"] += int(stat_result.st_size)
        result["objects"] += 1
        result["counters"]["files_attributed"] += 1
    return result
