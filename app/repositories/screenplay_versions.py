"""Shared screenplay compare-and-swap/history rules for File and PostgreSQL."""
from __future__ import annotations
import copy
from .chapter_repository import VersionConflict


def screenplay_version(row: dict | None) -> int:
    return int((row or {}).get("edit_version", 0))


def check_screenplay_version(current: dict, expected_version: int | None) -> None:
    if expected_version is not None and screenplay_version(current) != expected_version:
        # Reuse the established 409 payload while keeping screenplay's distinct
        # content/shot revision counters separate from its storage CAS version.
        raise VersionConflict({**current, "version": screenplay_version(current)},
                              resource_id=current.get("id"), expected_version=expected_version)


def versioned_screenplay(current: dict | None, proposed: dict, expected_version: int | None) -> dict:
    check_screenplay_version(current or {"id": proposed["id"]}, expected_version)
    if current and current.get("branch_id") != proposed.get("branch_id"):
        raise ValueError("screenplay branch ownership is immutable")
    history = copy.deepcopy((current or {}).get("version_history", []))
    if current:
        history.append({key: copy.deepcopy(value) for key, value in current.items() if key != "version_history"})
    row = {key: copy.deepcopy(value) for key, value in proposed.items() if key not in {"version_history", "expected_version"}}
    row["edit_version"] = screenplay_version(current) + 1
    row["version_history"] = history
    return row
