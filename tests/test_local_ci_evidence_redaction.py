"""Evidence redaction must stay XML-safe and remove absolute host paths (D-22)."""
from __future__ import annotations

import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_redactor():
    spec = importlib.util.spec_from_file_location(
        "redact_local_ci_evidence", ROOT / "scripts" / "redact_local_ci_evidence.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_redaction_uses_xml_safe_placeholders_and_keeps_junit_parseable(tmp_path):
    redactor = _load_redactor()
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    repo_path = str(ROOT.resolve())
    junit = evidence / "junit.xml"
    junit.write_text(
        '<?xml version="1.0" encoding="utf-8"?>'
        '<testsuites><testsuite name="case"><testcase classname="' + repo_path + '/tests/test_x.py" '
        'name="test_case" time="0.1"><skipped message="cwd ' + repo_path + '"/></testcase></testsuite></testsuites>',
        encoding="utf-8")
    log = evidence / "run.log"
    log.write_text("$ python " + repo_path + "/scripts/run_local_ci.py\n", encoding="utf-8")

    report = redactor.redact_directory(evidence, ROOT)

    assert report["xml_valid"] is True
    assert report["errors"] == []
    assert all("[repo]" in (evidence / name).read_text(encoding="utf-8")
               for name in ("junit.xml", "run.log"))
    assert all(repo_path not in (evidence / name).read_text(encoding="utf-8")
               for name in ("junit.xml", "run.log"))
    assert "<repo>" not in junit.read_text(encoding="utf-8")
    ET.parse(junit)


def test_redaction_is_idempotent(tmp_path):
    redactor = _load_redactor()
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    log = evidence / "run.log"
    log.write_text("path=" + str(ROOT.resolve()) + "/x\n", encoding="utf-8")
    first = redactor.redact_directory(evidence, ROOT)
    second = redactor.redact_directory(evidence, ROOT)
    assert first["xml_valid"] is True and second["xml_valid"] is True
    assert sum(1 for row in second["files"] if row.get("redacted")) == 0
    assert log.read_text(encoding="utf-8").count("[repo]") == 1
