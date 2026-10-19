#!/usr/bin/env python3
"""Check that local-CI evidence receipts only reference files that exist.

Every committed @verification-summary.json@ (and @LOCAL_CI_RESULTS.json@ where it
declares evidence paths) must point at real archived files; otherwise a report can
look reviewable while its evidence path is dangling. XML evidence is also parsed.

Usage:
    python scripts/check_local_ci_evidence_index.py
    python scripts/check_local_ci_evidence_index.py --evidence-root docs/v2/engineering/evidence/local-ci --json-out report.json
"""
from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = ROOT / "docs" / "v2" / "engineering" / "evidence" / "local-ci"


def check_evidence_root(root: Path = DEFAULT_ROOT) -> dict:
    report = {"root": root.as_posix(), "checked_paths": 0, "missing": [], "xml_invalid": [],
              "receipts": 0, "notes": []}
    for summary_path in sorted(root.glob("*/verification-summary.json")):
        report["receipts"] += 1
        try:
            rows = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            report["missing"].append([summary_path.name, "unreadable: " + type(exc).__name__])
            continue
        if not isinstance(rows, list):
            rows = [rows]
        for row in rows:
            if not isinstance(row, dict):
                continue
            for key in ("junit", "console", "log", "receipt"):
                name = row.get(key)
                if not name:
                    continue
                report["checked_paths"] += 1
                candidate = (summary_path.parent / name).resolve()
                try:
                    candidate.relative_to(summary_path.parent.resolve())
                except ValueError:
                    report["missing"].append([summary_path.parent.name, key, name, "outside evidence dir"])
                    continue
                if not candidate.is_file():
                    report["missing"].append([summary_path.parent.name, key, name])
    for xml_path in sorted(root.rglob("*.xml")):
        try:
            ET.parse(xml_path)
        except ET.ParseError as exc:
            report["xml_invalid"].append([xml_path.relative_to(root).as_posix(), str(exc)])
    report["status"] = "PASS" if not report["missing"] and not report["xml_invalid"] else "FAIL"
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
