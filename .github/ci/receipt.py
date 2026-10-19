"""Summarize machine-produced JUnit counts; never infer a pass from missing output."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


def summarize(directory: Path) -> dict:
    reports = {}
    for path in sorted(directory.glob("*.xml")):
        root = ET.parse(path).getroot()
        cases = list(root.iter("testcase"))
        reports[path.name] = {
            "tests": len(cases),
            "failures": sum(case.find("failure") is not None for case in cases),
            "errors": sum(case.find("error") is not None for case in cases),
            "skipped": sum(case.find("skipped") is not None for case in cases),
        }
    return {
        "revision": (directory / "revision.txt").read_text(encoding="utf-8"),
        "test_reports": reports,
        "report_status": "RECORDED" if reports else "NOT RUN / NO TEST REPORT",
        "native_windows_host_appcontainer_installer": "NOT RUN",
        "real_model_and_paid_provider_execution": "NOT RUN",
    }


if __name__ == "__main__":
    directory = Path(sys.argv[1])
    result = summarize(directory)
    rendered = json.dumps(result, indent=2) + "\n"
    (directory / "summary.json").write_text(rendered, encoding="utf-8")
    print(rendered)
    if destination := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(destination, "a", encoding="utf-8") as stream:
            stream.write("## Cloud CI receipt\n\n```json\n" + rendered + "```\n")
