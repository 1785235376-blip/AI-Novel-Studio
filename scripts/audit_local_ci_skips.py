#!/usr/bin/env python3
"""Audit a local-CI JUnit receipt for silently skipped contracts.

LOCAL-02 runs a focused File-backend slice. Some node ids are expected to skip:
PostgreSQL implementation contracts (covered by the real PostgreSQL suite) and
the Windows symlink-privilege case (covered by hosted Linux CI). Everything else
must execute. This script makes the taxonomy explicit and fails when an unknown
skip reason appears or when a test function would be skipped on every backend.

Pairing is strict (D-24 round-3 audit fix). A skipped PostgreSQL node counts as
covered only when ALL of the following hold:

* it shares the exact module/class and function identity with its control;
* the PostgreSQL variant is the leading parameter token ("postgres" or
  "postgres-...");
* the only differing parameter token is that backend token, so every other
  parameter value is identical;
* the control node exists in the executed (passed) set and its backend token is
  explicitly "file".

Bare function names are therefore never sufficient: cross-module same-name
functions, different parameter combinations, skipped controls and other backends
are all reported as PostgreSQL-only instead of silently matching.

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
BACKEND_TOKENS = {"file", "postgres", "postgresql"}


def split_node(node: str) -> tuple[str, str, str | None]:
    """Return (owner, function name, parameter string or None) for a JUnit node id.

    owner keeps the full module/class identity (for example
    "tests.test_x.TestY"), so functions with the same name in different modules
    or classes can never be paired with each other.
    """
    owner, separator, name = node.rpartition("::")
    if not separator:
        owner, name = "", node
    params = None
    if name.endswith("]") and "[" in name:
        name, _, params = name[:-1].partition("[")
    return owner, name, params


def backend_and_rest(params: str | None) -> tuple[str | None, str | None]:
    """Split a parameter string into its leading backend token and the rest."""
    if not params:
        return None, None
    token, separator, rest = params.partition("-")
    if token not in BACKEND_TOKENS:
        return None, params
    return ("postgres" if token == "postgresql" else token), (rest if separator else "")


def file_control(owner: str, name: str, params: str | None) -> str | None:
    """Return the exact File-control node id for a PostgreSQL node, if any."""
    backend, rest = backend_and_rest(params)
    if backend != "postgres":
        return None
    control_params = "file" + (("-" + rest) if rest else "")
    control_name = name + "[" + control_params + "]"
    return (owner + "::" if owner else "") + control_name


def base_name(name: str) -> str:
    return name[:-1].partition("[")[0] if name.endswith("]") and "[" in name else name


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

    passed_set = set(passed)
    passed_names = {split_node(node)[1] for node in passed}
    unknown = [row for row in skipped
               if not any(marker in row["message"] for marker in ALLOWED_SKIP_MARKERS)]
    pg_rows = [row for row in skipped if "PostgreSQL implementation contract" in row["message"]]
    matched, pg_only, controls = [], [], []
    for row in pg_rows:
        owner, name, params = split_node(row["node"])
        control = file_control(owner, name, params)
        if control is not None and control in passed_set:
            matched.append(row["node"])
            controls.append({"skipped": row["node"], "control": control})
        else:
            pg_only.append(row["node"])
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
        "postgres_contracts_matched": len(matched),
        "postgres_only_functions": pg_only,
        "postgres_pairing_examples": controls[:4],
        "symlink_privilege_skips": [row["node"] for row in symlink],
        "executed_function_names_with_pg_contracts": len(passed_names & {split_node(row["node"])[1] for row in pg_rows}),
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
                       "postgres_contracts", "postgres_contracts_matched",
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
