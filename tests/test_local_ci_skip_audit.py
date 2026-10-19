"""Strict pairing rules for scripts/audit_local_ci_skips.py (D-24 round-3 fix).

A skipped PostgreSQL node is only "covered" by an exact File control: same
module/class, same function, identical non-backend parameters, and the control
must actually have executed and passed.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts import audit_local_ci_skips as audit

PG_MESSAGE = "PostgreSQL implementation contract; covered by the real PostgreSQL full suite"
SYMLINK_MESSAGE = "WINDOWS_SYMLINK_PRIVILEGE_UNAVAILABLE: hosted Linux CI covers the symlink identity contract"


def write_junit(tmp_path: Path, cases) -> Path:
    suite = ET.Element("testsuite", name="pytest")
    for classname, name, outcome in cases:
        case = ET.SubElement(suite, "testcase", classname=classname, name=name)
        if outcome == "skipped_pg":
            ET.SubElement(case, "skipped", message=PG_MESSAGE)
        elif outcome == "skipped_symlink":
            ET.SubElement(case, "skipped", message=SYMLINK_MESSAGE)
        elif outcome == "skipped_unknown":
            ET.SubElement(case, "skipped", message="some unexpected reason")
        elif outcome == "failed":
            ET.SubElement(case, "failure", message="boom")
    path = tmp_path / "junit.xml"
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)
    return path


def run(tmp_path: Path, cases, *extra: str) -> int:
    path = write_junit(tmp_path, cases)
    return audit.main(["--junit", str(path), *extra])


def test_legal_module_and_parameter_pairing_is_accepted(tmp_path, capsys):
    cases = [
        ("tests.test_alpha", "test_scoped_read[postgres-arg]", "skipped_pg"),
        ("tests.test_alpha", "test_scoped_read[file-arg]", "passed"),
        ("tests.test_alpha.TestClass", "test_scope[postgres]", "skipped_pg"),
        ("tests.test_alpha.TestClass", "test_scope[file]", "passed"),
        ("tests.test_beta", "test_other[postgres-extra]", "skipped_pg"),
        ("tests.test_beta", "test_other[file-extra]", "passed"),
    ]
    assert run(tmp_path, cases, "--fail-on-pg-only") == 0
    report = audit.inspect(write_junit(tmp_path, cases))
    assert report["postgres_contracts"] == 3
    assert report["postgres_contracts_matched"] == 3
    assert report["postgres_only_functions"] == []


def test_cross_module_same_function_name_is_not_paired(tmp_path):
    cases = [
        ("tests.test_alpha", "test_scope[postgres]", "skipped_pg"),
        ("tests.test_beta", "test_scope[file]", "passed"),
    ]
    assert run(tmp_path, cases, "--fail-on-pg-only") == 1
    report = audit.inspect(write_junit(tmp_path, cases))
    assert report["postgres_contracts_matched"] == 0
    assert report["postgres_only_functions"] == ["tests.test_alpha::test_scope[postgres]"]


def test_different_non_backend_parameter_is_not_paired(tmp_path):
    cases = [
        ("tests.test_alpha", "test_scope[postgres-False]", "skipped_pg"),
        ("tests.test_alpha", "test_scope[file-True]", "passed"),
    ]
    assert run(tmp_path, cases, "--fail-on-pg-only") == 1
    report = audit.inspect(write_junit(tmp_path, cases))
    assert report["postgres_only_functions"] == ["tests.test_alpha::test_scope[postgres-False]"]


def test_missing_file_control_is_pg_only(tmp_path):
    cases = [("tests.test_alpha", "test_scope[postgres]", "skipped_pg")]
    assert run(tmp_path, cases, "--fail-on-pg-only") == 1
    report = audit.inspect(write_junit(tmp_path, cases))
    assert report["postgres_only_functions"] == ["tests.test_alpha::test_scope[postgres]"]


def test_skipped_file_control_does_not_count(tmp_path):
    cases = [
        ("tests.test_alpha", "test_scope[postgres]", "skipped_pg"),
        ("tests.test_alpha", "test_scope[file]", "skipped_symlink"),
    ]
    assert run(tmp_path, cases, "--fail-on-pg-only") == 1
    report = audit.inspect(write_junit(tmp_path, cases))
    assert report["postgres_only_functions"] == ["tests.test_alpha::test_scope[postgres]"]


def test_unknown_skip_reason_fails(tmp_path):
    cases = [("tests.test_alpha", "test_scope[file]", "skipped_unknown")]
    assert run(tmp_path, cases) == 1
    report = audit.inspect(write_junit(tmp_path, cases))
    assert report["unknown_skips"] == ["tests.test_alpha::test_scope[file]"]


def test_symlink_privilege_skip_is_allowed(tmp_path):
    cases = [("tests.test_alpha", "test_symlink[symlink]", "skipped_symlink")]
    assert run(tmp_path, cases) == 0
    report = audit.inspect(write_junit(tmp_path, cases))
    assert report["symlink_privilege_skips"] == ["tests.test_alpha::test_symlink[symlink]"]
    assert report["postgres_only_functions"] == []


def test_failed_case_still_fails_the_audit(tmp_path):
    cases = [("tests.test_alpha", "test_scope[file]", "failed")]
    assert run(tmp_path, cases) == 1


def test_empty_trailing_parameter_is_preserved_in_the_file_control(tmp_path):
    cases = [
        ("tests.test_gamma", "test_empty[postgres-]", "skipped_pg"),
        ("tests.test_gamma", "test_empty[file-]", "passed"),
    ]
    assert run(tmp_path, cases, "--fail-on-pg-only") == 0
    report = audit.inspect(write_junit(tmp_path, cases))
    assert report["postgres_contracts_matched"] == 1
    assert report["postgres_only_functions"] == []
    assert report["postgres_pairing_examples"] == [
        {"skipped": "tests.test_gamma::test_empty[postgres-]",
         "control": "tests.test_gamma::test_empty[file-]"},
    ]


def test_empty_trailing_parameter_does_not_pair_with_a_bare_file_control(tmp_path):
    cases = [
        ("tests.test_gamma", "test_empty[postgres-]", "skipped_pg"),
        ("tests.test_gamma", "test_empty[file]", "passed"),
    ]
    assert run(tmp_path, cases, "--fail-on-pg-only") == 1
    report = audit.inspect(write_junit(tmp_path, cases))
    assert report["postgres_contracts_matched"] == 0
    assert report["postgres_only_functions"] == ["tests.test_gamma::test_empty[postgres-]"]


def test_bare_postgres_parameter_still_pairs_with_bare_file_control(tmp_path):
    cases = [
        ("tests.test_gamma", "test_plain[postgres]", "skipped_pg"),
        ("tests.test_gamma", "test_plain[file]", "passed"),
    ]
    assert run(tmp_path, cases, "--fail-on-pg-only") == 0
    report = audit.inspect(write_junit(tmp_path, cases))
    assert report["postgres_pairing_examples"] == [
        {"skipped": "tests.test_gamma::test_plain[postgres]",
         "control": "tests.test_gamma::test_plain[file]"},
    ]
