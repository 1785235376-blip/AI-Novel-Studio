#!/usr/bin/env python3
"""Check that local-CI evidence receipts only reference files that exist.

Committed evidence receipts promise reviewable files. This checker covers the two
receipt formats used by this repository:

* @verification-summary.json@ (one per evidence run/closeout directory): a JSON list
  (or one object) of rows whose evidence path fields are @junit@, @console@, @log@
  and @receipt@. These paths are resolved relative to the receipt's own directory.
* @LOCAL_CI_RESULTS.json@ (schema @poemseed-local-ci/1@): a run receipt whose
  @steps[*].log@ and @steps[*].checks.junit@ (including
  @steps[*].checks.commands.*.log@) are repository-relative paths. They are
  resolved relative to the repository root.

For every non-empty declared path the checker verifies: it is relative, it resolves
inside the evidence root (so @../@, absolute paths and symlinks cannot escape), and
the file exists. Declared XML files and all archived XML under the evidence root are
parsed; broken XML fails the check. @null@ / empty optional paths are ignored.

Usage:
    python scripts/check_local_ci_evidence_index.py
    python scripts/check_local_ci_evidence_index.py --evidence-root docs/v2/engineering/evidence/local-ci --json-out report.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = ROOT / "docs" / "v2" / "engineering" / "evidence" / "local-ci"

SUMMARY_NAME = "verification-summary.json"
RUN_RECEIPT_NAME = "LOCAL_CI_RESULTS.json"
SUMMARY_PATH_KEYS = ("junit", "console", "log", "receipt")
ABSOLUTE_PATH_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\|/)")
IGNORED_NON_STRING = object()


def _display_root(root: Path) -> str:
    try:
        return root.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return root.resolve().as_posix()


def _run_receipt_path_fields(data: dict):
    """Yield (field_name, raw_value) for the path fields of a run receipt.

    The @poemseed-local-ci/1@ format stores repo-relative evidence paths in
    @steps[*].log@ and @steps[*].checks.junit@ (a string when it names a JUnit
    file - @checks.junit@ is a counts dict on the LOCAL-04 step, so it must not be
    treated as a path), and in @steps[*].checks.commands.*.log@. Unknown nested
    keys are not guessed at.
    """
    if not isinstance(data, dict):
        return
    for step in data.get("steps") or []:
        if not isinstance(step, dict):
            continue
        if "log" in step:
            yield "steps[].log", step["log"]
        checks = step.get("checks") or {}
        if isinstance(checks, dict):
            if isinstance(checks.get("junit"), str):
                yield "checks.junit", checks["junit"]
            commands = checks.get("commands") or {}
            if isinstance(commands, dict):
                for name, command in commands.items():
                    if isinstance(command, dict) and "log" in command:
                        yield "checks.commands." + str(name) + ".log", command["log"]


def _check_path(report: dict, root: Path, receipt_kind: str, receipt_rel: str,
                field: str, raw_value, base: Path, base_name: str) -> None:
    if raw_value is None:
        return
    if not isinstance(raw_value, str):
        report["notes"].append([receipt_rel, field, "ignored non-string value"])
        return
    value = raw_value.strip()
    if not value:
        return
    report["checked_paths"] += 1
    entry = [receipt_kind, receipt_rel, field, value]
    if ABSOLUTE_PATH_RE.match(value):
        report["out_of_root"].append(entry + ["absolute path is not allowed"])
        return
    candidate = (base / value).resolve()
    root_resolved = root.resolve()
    try:
        relative = candidate.relative_to(root_resolved)
    except ValueError:
        report["out_of_root"].append(entry + ["resolves outside the evidence root"])
        return
    if not candidate.is_file():
        report["missing"].append(entry + ["base=" + base_name])
        return
    if candidate.suffix.lower() == ".xml":
        report["xml_checked"] += 1
        try:
            ET.parse(candidate)
        except ET.ParseError as exc:
            report["xml_invalid"].append([receipt_rel, relative.as_posix(), str(exc)])


def _check_verification_summary(report: dict, path: Path, root: Path) -> None:
    receipt_rel = path.relative_to(root).as_posix()
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        report["missing"].append(["verification-summary.json", receipt_rel, "unreadable",
                                  type(exc).__name__])
        return
    if not isinstance(rows, list):
        rows = [rows]
    for row in rows:
        if not isinstance(row, dict):
            continue
        for key in SUMMARY_PATH_KEYS:
            if key in row:
                _check_path(report, root, "verification-summary.json", receipt_rel, key,
                            row[key], path.parent, "receipt directory")


def _check_run_receipt(report: dict, path: Path, root: Path, repo_root: Path) -> None:
    receipt_rel = path.relative_to(root).as_posix()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        report["missing"].append(["LOCAL_CI_RESULTS.json", receipt_rel, "unreadable",
                                  type(exc).__name__])
        return
    for field, raw_value in _run_receipt_path_fields(data):
        _check_path(report, root, "LOCAL_CI_RESULTS.json", receipt_rel, field,
                    raw_value, repo_root, "repository root")


def check_evidence_root(root: Path = DEFAULT_ROOT, *, repo_root: Path | None = None) -> dict:
    root = Path(root)
    repo_root = Path(repo_root) if repo_root is not None else ROOT
    report = {
        "root": _display_root(root),
        "resolution_bases": {
            SUMMARY_NAME: "receipt directory",
            RUN_RECEIPT_NAME: "repository root",
        },
        "receipt_files_scanned": 0,
        "receipts": 0,
        "receipt_types": {SUMMARY_NAME: 0, RUN_RECEIPT_NAME: 0},
        "checked_paths": 0,
        "missing": [],
        "out_of_root": [],
        "xml_invalid": [],
        "xml_checked": 0,
        "notes": [],
    }
    for path in sorted(root.rglob(SUMMARY_NAME)):
        report["receipt_files_scanned"] += 1
        report["receipts"] += 1
        report["receipt_types"][SUMMARY_NAME] += 1
        _check_verification_summary(report, path, root)
    for path in sorted(root.rglob(RUN_RECEIPT_NAME)):
        report["receipt_files_scanned"] += 1
        report["receipts"] += 1
        report["receipt_types"][RUN_RECEIPT_NAME] += 1
        _check_run_receipt(report, path, root, repo_root)

    # Whole-archive XML well-formedness, including files not declared by a receipt.
    for xml_path in sorted(root.rglob("*.xml")):
        try:
            ET.parse(xml_path)
        except ET.ParseError as exc:
            report["xml_invalid"].append([xml_path.relative_to(root).as_posix(), str(exc)])

    report["status"] = ("PASS" if not report["missing"] and not report["out_of_root"]
                        and not report["xml_invalid"] else "FAIL")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args(argv)
    report = check_evidence_root(args.evidence_root)
    if args.json_out:
        args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8", newline="\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())