#!/usr/bin/env python3
"""Redact absolute host paths from a local-CI evidence directory.

The committed evidence must not contain personal host paths. The placeholders use
XML-safe, markdown-safe delimiters ([repo], [workspace], [userprofile]) because a
raw <repo> placeholder corrupts JUnit XML (D-22). Every XML file is re-parsed
after redaction; the script fails closed if redaction would break the document.

Usage:
    python scripts/redact_local_ci_evidence.py --evidence-dir docs/v2/engineering/evidence/local-ci/<run>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
XML_SUFFIXES = {".xml"}


def redaction_pairs(repo_root: Path) -> list[tuple[str, str]]:
    repo = str(repo_root.resolve())
    workspace = str(repo_root.resolve().parent)
    home = str(Path.home())
    pairs = [
        (repo, "[repo]"),
        (repo.replace("\\", "/"), "[repo]"),
        (workspace, "[workspace]"),
        (workspace.replace("\\", "/"), "[workspace]"),
        (home, "[userprofile]"),
        (home.replace("\\", "/"), "[userprofile]"),
    ]
    return pairs


def redact_text(text: str, pairs: list[tuple[str, str]]) -> tuple[str, bool]:
    changed = False
    for plain, replacement in pairs:
        if not plain or len(plain) < 4:
            continue
        variants = {plain, plain.replace("\\", "\\\\"), plain.replace("/", "\\")}
        for variant in variants:
            if variant in text:
                text = text.replace(variant, replacement)
                changed = True
    return text, changed


def redact_directory(evidence_dir: Path, repo_root: Path) -> dict:
    pairs = redaction_pairs(repo_root)
    report = {"evidence_dir": str(evidence_dir), "files": [], "xml_valid": True, "errors": []}
    for path in sorted(evidence_dir.rglob("*")):
        if not path.is_file():
            continue
        try:
            original = path.read_bytes()
            text = original.decode("utf-8")
        except UnicodeDecodeError:
            report["files"].append({"path": path.relative_to(evidence_dir).as_posix(),
                                    "redacted": False, "reason": "binary"})
            continue
        redacted, changed = redact_text(text, pairs)
        if changed:
            path.write_bytes(redacted.encode("utf-8"))
        after = path.read_bytes()
        entry = {"path": path.relative_to(evidence_dir).as_posix(), "redacted": changed,
                 "bytes": len(after),
                 "sha256_before": hashlib.sha256(original).hexdigest(),
                 "sha256_after": hashlib.sha256(after).hexdigest()}
        if changed:
            entry["sha256_before"] = entry["sha256_before"][:16]
            entry["sha256_after"] = entry["sha256_after"][:16]
        if path.suffix.lower() in XML_SUFFIXES:
            try:
                ET.parse(path)
                entry["xml"] = "ok"
            except ET.ParseError as exc:
                entry["xml"] = "invalid"
                report["xml_valid"] = False
                report["errors"].append(path.relative_to(evidence_dir).as_posix() + ": " + str(exc))
        report["files"].append(entry)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args(argv)
    if not args.evidence_dir.is_dir():
        parser.error("--evidence-dir must be an existing directory")
    report = redact_directory(args.evidence_dir, args.repo_root)
    if args.json_out:
        args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8", newline="\n")
    print(json.dumps({"redacted_files": sum(1 for row in report["files"] if row.get("redacted")),
                      "xml_valid": report["xml_valid"], "errors": report["errors"]},
                     ensure_ascii=False, indent=2))
    return 0 if report["xml_valid"] and not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
