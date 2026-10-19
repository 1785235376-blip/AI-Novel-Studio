#!/usr/bin/env python3
"""Audit a local-CI JUnit receipt for silently skipped contracts.

LOCAL-02 runs a focused File-backend slice. Some node ids are expected to skip:
PostgreSQL implementation contracts (covered by the real PostgreSQL suite) and
the Windows symlink-privilege case (covered by hosted Linux CI). Everything else
must execute. This script makes the taxonomy explicit and fails when an unknown
skip reason appears or when a test function would be skipped on every backend.

Usage:
    python scripts/audit_local_ci_skips.py --junit docs/v2/engineering/evidence/local-ci/<run>/LOCAL-02-junit.xml
    python scripts/audit_local_ci_skips.py --junit <file> --fail-on-pg-only --json-out report.json
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ALLOWED_SKIP_MARKERS = (
    "PostgreSQL implementation contract",
    "WINDOWS_SYMLINK_PRIVILEGE_UNAVAILABLE",
)
BEHAVIOUR_PATTERNS = {
    "project_create_read": [r"create", r"read", r"lifecycle", r"list"],
    "save_reread_persistence": [r"persist", r"reload", r"reopen", r"read_back", r"reread", r"save"],
    "cas_conflict": [r"cas", r"conflict", r"revision", r"version"],
    "cross_project_denied": [r"authority", r"scope", r"denied", r"forbidden", r"cross"],
    "review_candidate_not_promoted": [r"review", r"promot", r"approve", r"pending", r"canon"],
    "failure_revocation": [r"revok", r"rollback", r"fail", r"retire", r"orphan"],
}


def base_name(name: str) -> str:
    return re.sub(r"\[[^\]]*\]$", "", name)


def inspect(junit: Path) -> dict:
    root = ET.parse(junit).getroot()
    passed, failed, skipped = [], [], []
    for case in root.iter("testcase"):
        name = case.get("name") or ""
        classname = case.get("classname") or ""
        node = (classname + "::" if classname else "") + name
        if case.find("failure") is not None or case.find("error") is not None:
            failed.append(node)
        elif case.find("skipped") is not None:
            message = (case.find("skipped").get("message") or "").strip()
            skipped.append({"node": node, "name": name, "message": message, "classname": classname})
        else:
            passed.append(node)

    passed_base = {base_name(node.split("::")[-1]) for node in passed}
    unknown = [row for row in skipped
               if not any(marker in row["message"] for marker in ALLOWED_SKIP_MARKERS)]
    pg_rows = [row for row in skipped if "PostgreSQL implementation contract" in row["message"]]
    pg_only = [row for row in pg_rows if base_name(row["name"]) not in passed_base]
    symlink = [row for row in skipped if "WINDOWS_SYMLINK_PRIVILEGE_UNAVAILABLE" in row["message"]]

    behaviours = {key: [] for key in BEHAVIOUR_PATTERNS}
    for node in passed:
        short = node.split("::")[-1].lower()
        for key, patterns in BEHAVIOUR_PATTERNS.items():
            if any(re.search(pattern, short) for pattern in patterns):
                behaviours[key].append(node)

    return {
        "junit": junit.as_posix(),
        "counts": {"total": len(passed) + len(failed) + len(skipped),
                   "passed": len(passed), "failed": len(failed), "skipped": len(skipped)},
        "failed_nodes": failed,
        "skip_messages": dict(collections.Counter(row["message"] for row in skipped)),
        "skip_by_file": dict(collections.Counter(row["classname"] or "?" for row in skipped)),
        "unknown_skips": [row["node"] for row in unknown],
        "postgres_contracts": len(pg_rows),
        "postgres_only_functions": [row["node"] for row in pg_only],
        "symlink_privilege_skips": [row["node"] for row in symlink],
        "behaviour_executed_counts": {key: len(value) for key, value in behaviours.items()},
        "behaviour_examples": {key: value[:4] for key, value in behaviours.items()},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--fail-on-pg-only", action="store_true",
                        help="fail when a PostgreSQL variant is the only realization of its function")
    args = parser.parse_args(argv)
    report = inspect(args.junit)
    if args.json_out:
        args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8", newline="\n")
    print(json.dumps({key: report[key] for key in
                      ("counts", "skip_messages", "unknown_skips", "symlink_privilege_skips",
                       "behaviour_executed_counts")}, ensure_ascii=False, indent=2))
    if report["counts"]["failed"]:
        return 1
    if report["unknown_skips"]:
        print("UNKNOWN SKIP REASONS: " + ", ".join(report["unknown_skips"]), file=sys.stderr)
        return 1
    if args.fail_on_pg_only and report["postgres_only_functions"]:
        print("POSTGRES-ONLY FUNCTIONS: " + ", ".join(report["postgres_only_functions"]), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())