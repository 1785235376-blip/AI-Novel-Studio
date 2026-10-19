"""Committed local-CI evidence receipts must not reference dangling or escaping files.

The checker covers both receipt formats used in this repository: per-directory
@verification-summary.json@ rows (paths relative to the receipt directory) and
repository-relative @LOCAL_CI_RESULTS.json@ run receipts. Tests build a complete
fixture under a temporary directory so path-resolution, containment and XML rules
are actually exercised.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.check_local_ci_evidence_index import check_evidence_root

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = ROOT / "docs" / "v2" / "engineering" / "evidence" / "local-ci"


def make_evidence_root(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    root = repo / "docs" / "v2" / "engineering" / "evidence" / "local-ci"
    root.mkdir(parents=True, exist_ok=True)
    return repo, root


def touch(root: Path, run: str, name: str, content: str = "evidence\n") -> Path:
    path = root / run / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def write_summary(root: Path, run: str, rows: list[dict]) -> Path:
    path = root / run / "verification-summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def write_run_receipt(repo: Path, root: Path, run: str, repo_relative_paths: list[str]) -> Path:
    steps = []
    for index, relative in enumerate(repo_relative_paths):
        steps.append({"step": "LOCAL-0" + str(index + 1), "log": relative, "checks": {}})
    path = root / run / "LOCAL_CI_RESULTS.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema": "poemseed-local-ci/1", "steps": steps},
                               ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def repo_relative(repo: Path, root: Path, run: str, name: str) -> str:
    return (root / run / name).relative_to(repo).as_posix()


def test_valid_verification_summary_passes(tmp_path):
    repo, root = make_evidence_root(tmp_path)
    touch(root, "run-a", "junit.xml", "<testsuite tests='1'/>")
    touch(root, "run-a", "console.log")
    touch(root, "run-a", "payload.json", "{}")
    write_summary(root, "run-a", [
        {"label": "a", "junit": "junit.xml", "console": "console.log"},
        {"label": "b", "receipt": "payload.json", "junit": None, "console": None},
    ])
    report = check_evidence_root(root, repo_root=repo)
    assert report["status"] == "PASS"
    assert report["checked_paths"] == 3
    assert report["missing"] == [] and report["out_of_root"] == [] and report["xml_invalid"] == []
    assert report["xml_checked"] == 1


def test_valid_local_ci_results_receipt_passes(tmp_path):
    repo, root = make_evidence_root(tmp_path)
    names = ["LOCAL-01-backend.log", "LOCAL-02-junit.xml", "LOCAL-03-vitest.log"]
    touch(root, "run-b", names[0])
    touch(root, "run-b", names[1], "<testsuite tests='1'/>")
    touch(root, "run-b", names[2])
    relative = [repo_relative(repo, root, "run-b", name) for name in names]
    path = root / "run-b" / "LOCAL_CI_RESULTS.json"
    path.write_text(json.dumps({"schema": "poemseed-local-ci/1", "steps": [
        {"step": "LOCAL-01", "log": relative[0], "checks": {"junit": relative[0]}},
        {"step": "LOCAL-02", "log": relative[1], "checks": {"junit": relative[1]}},
        {"step": "LOCAL-03", "log": relative[2],
         "checks": {"commands": {"vitest": {"log": relative[2]}}}},
    ]}), encoding="utf-8")
    report = check_evidence_root(root, repo_root=repo)
    assert report["status"] == "PASS"
    assert report["receipt_types"]["LOCAL_CI_RESULTS.json"] == 1
    assert report["checked_paths"] == 6


@pytest.mark.parametrize("kind", ["summary", "run-receipt"])
def test_missing_declared_file_fails(tmp_path, kind):
    repo, root = make_evidence_root(tmp_path)
    if kind == "summary":
        write_summary(root, "run-c", [{"label": "c", "junit": "does-not-exist.xml"}])
    else:
        relative = repo_relative(repo, root, "run-c", "does-not-exist.log")
        write_run_receipt(repo, root, "run-c", [relative])
    report = check_evidence_root(root, repo_root=repo)
    assert report["status"] == "FAIL"
    assert report["missing"]
    assert report["missing"][0][0] == (SUMMARY_NAME := "verification-summary.json"
                                         if kind == "summary" else "LOCAL_CI_RESULTS.json")


def test_relative_path_cannot_escape_evidence_root(tmp_path):
    repo, root = make_evidence_root(tmp_path)
    outside = repo / "outside.log"
    outside.write_text("outside\n", encoding="utf-8")
    write_summary(root, "run-d", [{"label": "d", "console": "../../../../outside.log"}])
    report = check_evidence_root(root, repo_root=repo)
    assert report["status"] == "FAIL"
    assert report["out_of_root"]
    assert "outside the evidence root" in report["out_of_root"][0][-1]


def test_absolute_path_outside_evidence_root_fails(tmp_path):
    repo, root = make_evidence_root(tmp_path)
    outside = tmp_path / "absolute-outside.log"
    outside.write_text("outside\n", encoding="utf-8")
    write_summary(root, "run-e", [{"label": "e", "console": str(outside)}])
    report = check_evidence_root(root, repo_root=repo)
    assert report["status"] == "FAIL"
    assert report["out_of_root"]
    assert "absolute path" in report["out_of_root"][0][-1]


def test_corrupt_declared_xml_fails(tmp_path):
    repo, root = make_evidence_root(tmp_path)
    touch(root, "run-f", "broken.xml", "<testsuite><testcase></testsuite>")
    write_summary(root, "run-f", [{"label": "f", "junit": "broken.xml"}])
    report = check_evidence_root(root, repo_root=repo)
    assert report["status"] == "FAIL"
    assert report["xml_invalid"]


def test_corrupt_archived_xml_not_declared_fails(tmp_path):
    repo, root = make_evidence_root(tmp_path)
    touch(root, "run-g", "archived.xml", "<testsuites>")
    report = check_evidence_root(root, repo_root=repo)
    assert report["status"] == "FAIL"
    assert report["xml_invalid"]


def test_both_receipt_types_are_counted(tmp_path):
    repo, root = make_evidence_root(tmp_path)
    touch(root, "run-h", "junit.xml", "<testsuite tests='1'/>")
    touch(root, "run-h", "console.log")
    write_summary(root, "run-h", [{"label": "h", "junit": "junit.xml", "console": "console.log"}])
    name = repo_relative(repo, root, "run-h", "LOCAL-01-backend.log")
    touch(root, "run-h", "LOCAL-01-backend.log")
    write_run_receipt(repo, root, "run-h", [name])
    report = check_evidence_root(root, repo_root=repo)
    assert report["status"] == "PASS"
    assert report["receipt_files_scanned"] == 2
    assert report["receipts"] == 2
    assert report["receipt_types"] == {"verification-summary.json": 1, "LOCAL_CI_RESULTS.json": 1}
    assert report["checked_paths"] == 3
    assert report["xml_checked"] == 1


def test_empty_and_null_optional_paths_are_ignored(tmp_path):
    repo, root = make_evidence_root(tmp_path)
    write_summary(root, "run-i", [
        {"label": "i", "junit": None, "console": "", "log": None},
        {"label": "j", "receipt": "   ", "junit": None},
    ])
    report = check_evidence_root(root, repo_root=repo)
    assert report["status"] == "PASS"
    assert report["checked_paths"] == 0
    assert report["missing"] == []


def test_symlink_escape_is_rejected(tmp_path):
    repo, root = make_evidence_root(tmp_path)
    outside = repo / "outside.log"
    outside.write_text("outside\n", encoding="utf-8")
    link = root / "run-j" / "linked.log"
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlink privilege unavailable on this Windows account")
    write_summary(root, "run-j", [{"label": "j", "console": "linked.log"}])
    report = check_evidence_root(root, repo_root=repo)
    assert report["status"] == "FAIL"
    assert report["out_of_root"]


def test_committed_evidence_index_is_valid():
    report = check_evidence_root(EVIDENCE_ROOT)
    assert report["status"] == "PASS", report
    assert report["receipts"] > 0
    assert report["receipt_files_scanned"] == report["receipts"]
    assert report["receipt_types"]["verification-summary.json"] > 0
    assert report["receipt_types"]["LOCAL_CI_RESULTS.json"] > 0
    assert report["checked_paths"] > 0
    assert report["missing"] == []
    assert report["out_of_root"] == []
    assert report["xml_invalid"] == []