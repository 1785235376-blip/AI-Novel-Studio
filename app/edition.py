"""Edition boundary declarations for build verification and release gates.

This module deliberately contains no authorization, routing or data-access logic: the
existing project/scope/session/CAS owners remain the single authority. It only makes the
public-vs-internal-research edition boundary explicit so build verification and tests can
fail closed before a public artifact is assembled.

SPEC-2026.10.19-r1 requires a public distribution and an internal research edition to be
separated (product, data, models and backend policy). The runtime separation for the
internal research deployment is NOT implemented in this repository yet; the edition
manifest records that honestly as BLOCKED instead of pretending it exists.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

PUBLIC = "PUBLIC"
INTERNAL_RESEARCH = "INTERNAL_RESEARCH"
VALID_EDITIONS = frozenset({PUBLIC, INTERNAL_RESEARCH})
EDITION_ENV = "POEMSEED_STUDIO_EDITION"
MANIFEST = Path(__file__).resolve().parents[1] / "docs" / "v2" / "engineering" / "edition_manifest.json"


def current_edition() -> str:
    """Fail closed to PUBLIC for unknown values; never silently open internal scope."""
    value = os.getenv(EDITION_ENV, PUBLIC).strip().upper()
    return value if value in VALID_EDITIONS else PUBLIC


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))
