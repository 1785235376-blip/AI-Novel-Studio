"""Fail-closed privacy policy shared by storage and outbound context builders."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

PRIVACY_LEVELS = frozenset({"CLOUD_ALLOWED", "REDACT_BEFORE_CLOUD", "LOCAL_ONLY"})
_PRIVACY_ORDER = {"CLOUD_ALLOWED": 0, "REDACT_BEFORE_CLOUD": 1, "LOCAL_ONLY": 2}
_REDACTED_CONSTRAINT = "存在未到揭露时机的受保护事实；禁止猜测或揭露原文"


def normalize_privacy(value: object) -> str:
    """Unknown, malformed and missing policies never grant cloud permission."""
    return value if isinstance(value, str) and value in PRIVACY_LEVELS else "LOCAL_ONLY"


def merge_privacy(*values: object) -> str:
    """All supplied sources restrict access; a permissive copy cannot override one."""
    return max((normalize_privacy(value) for value in values), key=_PRIVACY_ORDER.get, default="LOCAL_ONLY")


def privacy_for_update(payload: Mapping, previous: Mapping | None = None) -> str:
    # Only an explicitly provided policy is a policy change. Legacy omissions are
    # not evidence of consent and updates must not reset an existing restriction.
    if "privacy_level" in payload:
        return normalize_privacy(payload["privacy_level"])
    return normalize_privacy((previous or {}).get("privacy_level"))


def privacy_record(item: Mapping) -> dict:
    """Expose unknown historical policy for review without editing its source."""
    policy = item.get("privacy_level")
    output = {**item, "privacy_level": normalize_privacy(policy)}
    if not isinstance(policy, str) or policy not in PRIVACY_LEVELS:
        output["privacy_status"] = "UNKNOWN"
    return output


def _redacted_fact() -> dict:
    return {"type": "protected_fact", "constraint": _REDACTED_CONSTRAINT,
            "privacy_level": "REDACT_BEFORE_CLOUD"}


def _cloud_children(value):
    if isinstance(value, Mapping):
        # Child records may impose a stricter rule than an admitted parent.
        policies = [value[key] for key in ("privacy_level", "privacy", "locality") if key in value]
        level = merge_privacy(*policies) if policies else "CLOUD_ALLOWED"
        if level == "LOCAL_ONLY":
            return None
        if level == "REDACT_BEFORE_CLOUD":
            return _redacted_fact()
        return {key: cleaned for key, child in value.items()
                if (cleaned := _cloud_children(child)) is not None}
    if isinstance(value, list):
        return [cleaned for child in value if (cleaned := _cloud_children(child)) is not None]
    return value


def cloud_safe_context(entries: list[dict]) -> tuple[list[dict], list[str]]:
    safe: list[dict] = []
    omitted: list[str] = []
    for item in entries:
        if not isinstance(item, Mapping):
            raise ValueError("Context records must be objects")
        policies = [item.get("privacy_level")]
        policies.extend(item[key] for key in ("privacy", "locality") if key in item)
        level = merge_privacy(*policies)
        if level == "LOCAL_ONLY":
            omitted.append(str(item.get("id", "unknown")))
            continue
        if level == "REDACT_BEFORE_CLOUD":
            # Never echo arbitrary titles, identifiers, types or extensions.
            safe.append(_redacted_fact())
        else:
            safe.append(_cloud_children(item))
    return safe, omitted


def prompt_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
