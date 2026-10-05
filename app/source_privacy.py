"""Hash/version-bound manuscript egress policy, separate from provider credentials.

A review permits future sends of exactly one chapter revision in one branch.
Editing, revoking or changing branches invalidates that permission. Already
transmitted content cannot be recalled by changing this record.
"""
from __future__ import annotations
import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from .config import settings
from .privacy import normalize_privacy, merge_privacy
from .storage import atomic_write

_LOCK = threading.RLock()


def content_digest(chapter):
    return hashlib.sha256(str(chapter.get("content") or "").encode("utf-8")).hexdigest()


def _key(chapter, branch_id):
    return hashlib.sha256(json.dumps([chapter["novel_id"], chapter["id"], branch_id], ensure_ascii=False).encode()).hexdigest()


def _path(root=None):
    return Path(root or settings.data_path()) / "v1_capabilities" / "source_privacy.json"


def _read(root=None):
    path = _path(root)
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != 1 or not isinstance(raw.get("records"), dict):
        raise ValueError("source privacy store is invalid")
    return raw["records"]


def source_privacy_status(chapter, branch_id=None, root=None):
    with _LOCK:
        try:
            record = _read(root).get(_key(chapter, branch_id))
        except (ValueError, OSError):
            record = None
    digest = content_digest(chapter)
    valid = bool(record and record.get("chapter_version") == chapter.get("version") and record.get("content_sha256") == digest)
    effective = normalize_privacy(record.get("privacy_level")) if valid else "LOCAL_ONLY"
    # A lower-level persisted restriction is independent and cannot be waived
    # by a newer review of the excerpt at a different layer.
    if "privacy_level" in chapter:
        effective = merge_privacy(effective, chapter["privacy_level"])
    return {"novel_id": chapter["novel_id"], "chapter_id": chapter["id"], "branch_id": branch_id,
            "chapter_version": chapter.get("version"), "content_sha256": digest,
            "privacy_level": effective, "reviewed": valid, "stale": bool(record and not valid),
            "reviewed_by": record.get("actor_id") if record else None,
            "reviewed_at": record.get("reviewed_at") if record else None}


def effective_source_privacy(chapter, branch_id=None, root=None):
    return source_privacy_status(chapter, branch_id, root)["privacy_level"]


def review_source_privacy(chapter, branch_id, actor_id, privacy_level, expected_version, expected_digest, root=None):
    if privacy_level not in {"LOCAL_ONLY", "REDACT_BEFORE_CLOUD", "CLOUD_ALLOWED"}:
        raise ValueError("invalid source privacy policy")
    if expected_version != chapter.get("version") or expected_digest != content_digest(chapter):
        raise ValueError("chapter changed; review its current text before changing privacy")
    with _LOCK:
        records = _read(root)
        records[_key(chapter, branch_id)] = {"novel_id": chapter["novel_id"], "chapter_id": chapter["id"],
            "branch_id": branch_id, "chapter_version": expected_version, "content_sha256": expected_digest,
            "privacy_level": privacy_level, "actor_id": actor_id,
            "reviewed_at": datetime.now(timezone.utc).isoformat()}
        atomic_write(_path(root), json.dumps({"schema_version": 1, "records": records}, ensure_ascii=False, indent=2))
    return source_privacy_status(chapter, branch_id, root)
