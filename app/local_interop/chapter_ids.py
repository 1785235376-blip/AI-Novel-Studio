"""Lossless-at-the-owner chapter ID projection into the frozen Interop alphabet.

These labels are not capabilities and cannot be decoded into repository keys.
Resolution always enumerates the current, exact-scope manuscript owner. Keep
the canonical tuple in sync with frontend/src/interop/chapterIds.ts.
"""
from __future__ import annotations

import hashlib
import json
import re

WIRE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SCOPE_KEYS = ("workspace_id", "project_id", "storyline_id", "branch_id")


def chapter_wire_id(scope, native_id):
    if not isinstance(native_id, str) or not native_id:
        raise ValueError("CHAPTER_ID_REQUIRED")
    if WIRE_ID.fullmatch(native_id):
        return native_id
    values = ["studio-chapter-v1", *(scope[key] for key in SCOPE_KEYS), native_id]
    encoded = json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "chapter-" + hashlib.sha256(encoded).hexdigest()
