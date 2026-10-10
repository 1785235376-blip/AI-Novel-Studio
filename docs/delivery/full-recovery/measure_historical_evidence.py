"""Measure downloaded historical CI evidence without copying raw logs into Git."""
from __future__ import annotations

import collections
import json
import pathlib
import xml.etree.ElementTree as ET
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent
items = json.loads((ROOT / "pr45-artifact-verification.json").read_text(encoding="utf-8"))
measured = []
for item in items:
    if item["status"] != "VERIFIED":
        continue
    entry = {"artifact_id": item["id"], "artifact_name": item["name"], "run_id": item["run_id"],
             "archive_sha256": item["sha256"], "xml_results": [], "summaries": {}}
    with zipfile.ZipFile(item["archive_path"]) as archive:
        for member in archive.namelist():
            if member.endswith(".xml") and not item["name"].startswith("windows-acceptance"):
                try:
                    tree = ET.fromstring(archive.read(member))
                except ET.ParseError:
                    continue
                cases = list(tree.iter("testcase"))
                if not cases:
                    continue
                outcomes = collections.Counter()
                seconds = 0.0
                for case in cases:
                    outcome = "passed"
                    for status in ("skipped", "failure", "error"):
                        if case.find(status) is not None:
                            outcome = status
                    outcomes[outcome] += 1
                    seconds += float(case.get("time", "0"))
                entry["xml_results"].append({"member": member, "tests": len(cases), "outcomes": dict(outcomes),
                                            "summed_test_seconds": round(seconds, 3)})
            if member in {"backend-coverage.json", "summary.json"}:
                entry["summaries"][member] = json.loads(archive.read(member))
            if member == "native-smoke/native-base-smoke.json":
                native = json.loads(archive.read(member))
                entry["native_summary"] = {key: val for key, val in native.items()
                                           if key in {"status", "source_revision", "schema_version"}}
                for key in ("commands", "steps"):
                    if isinstance(native.get(key), list):
                        entry["native_summary"][key + "_count"] = len(native[key])
                if isinstance(native.get("commands"), list):
                    entry["native_summary"]["commands_exit_zero"] = sum(
                        cmd.get("exit_code") == 0 for cmd in native["commands"]
                    )
    measured.append(entry)
(ROOT / "pr45-historical-ci-measurements.json").write_text(
    json.dumps(measured, ensure_ascii=False, indent=2), encoding="utf-8"
)
for item in measured:
    if item["xml_results"] or item["summaries"]:
        print(json.dumps({key: val for key, val in item.items() if key not in {"native_summary"}}, ensure_ascii=False))
