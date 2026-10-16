"""Capacity diagnostics cannot turn incomplete or mixed evidence into a pass."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from ci_capacity import (EvidenceError, analyze_events, analyze_run, identify,
                         junit_timings, main, progress_windows, seconds)

NODE = "tests/test_original.py::test_original"
SHA = "a" * 40


def event(when, outcome="passed", node=NODE):
    return {"nodeid": node, "when": when, "outcome": outcome,
            "wasxfail": False, "skip_reason": None}


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def archive(tmp_path):
    run = {"id": 123, "name": "Cloud CI", "event": "push", "head_sha": SHA,
           "run_attempt": 1, "repository": {"full_name": "example/project"}}
    job = {"id": 456, "run_id": 123, "run_attempt": 1, "head_sha": SHA,
           "name": "Backend execution / file / shard 0", "conclusion": "cancelled",
           "html_url": "https://github.com/example/project/actions/runs/123/job/456",
           "started_at": "2026-10-10T00:00:00Z", "completed_at": "2026-10-10T00:20:00Z",
           "steps": [{"name": "Complete backend collection / assigned shard execution",
                      "conclusion": "cancelled", "started_at": "2026-10-10T00:01:00Z",
                      "completed_at": "2026-10-10T00:20:00Z"}]}
    artifact = {"id": 789, "name": f"backend-file-shard-0-{SHA}-attempt-1",
                "workflow_run": {"id": 123, "head_sha": SHA}}
    receipt = {"assigned": [NODE], "backend": "file", "shard": {"index": 0, "count": 1},
               "complete": False, "pytest_exitstatus": None,
               "identity": {"run_id": "123", "run_attempt": "1", "repository": "example/project",
                            "checked_out_sha": SHA, "event_sha": SHA, "source_tree": "b" * 40}}
    write_json(tmp_path / "run-final.json", run)
    write_json(tmp_path / "jobs-final.json", {"jobs": [job]})
    write_json(tmp_path / "artifacts-final.json", {"artifacts": [artifact]})
    directory = tmp_path / "artifact-789"
    directory.mkdir()
    write_json(directory / "coverage.json", receipt)
    rows = [event("setup"), event("call", "failed"), event("teardown")]
    (directory / "coverage-events.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    (tmp_path / "job-456.log").write_text(
        "2026-10-10T00:01:00.1Z ... [100%]\n"
        "2026-10-10T00:01:00.2Z PYTHONPATH=fixture python -m pytest -p postgres_gate -p suite_coverage\n"
        "2026-10-10T00:01:03.1234567Z F [100%]\n")
    return tmp_path


def test_cancelled_failed_call_remains_separate_from_capacity(archive):
    report = analyze_run(archive)
    assert report["status"] == "DIAGNOSTIC_ONLY"
    assert report["coverage_verdict"] == "NOT_EVALUATED"
    job = report["jobs"][0]
    assert job["conclusion"] == "cancelled"
    assert job["events"]["failed_events"] == [{"node": identify(NODE), "phase": "call"}]
    assert job["receipt_complete"] is False and job["pytest_exitstatus"] is None
    assert job["junit_timing"] == {"status": "MISSING", "per_case_durations": "UNKNOWN"}
    assert job["events"]["nodes_with_teardown_event"] == 1
    assert job["progress_timing"]["largest_windows"][0]["seconds"] == 3.123456
    assert report["input_sha256"]


@pytest.mark.parametrize("field,value", [
    ("run_id", "999"), ("run_attempt", "2"), ("repository", "other/project"),
    ("event_sha", "c" * 40), ("checked_out_sha", "c" * 40),
])
def test_mixed_receipt_identity_rejected(archive, field, value):
    path = archive / "artifact-789/coverage.json"
    receipt = json.loads(path.read_text())
    receipt["identity"][field] = value
    write_json(path, receipt)
    with pytest.raises(EvidenceError):
        analyze_run(archive)


@pytest.mark.parametrize("mutation", ["job-run", "job-attempt", "job-source", "artifact-run",
                                       "artifact-source", "artifact-duplicate", "shard", "backend"])
def test_wrong_archive_metadata_rejected(archive, mutation):
    jobs = json.loads((archive / "jobs-final.json").read_text())
    artifacts = json.loads((archive / "artifacts-final.json").read_text())
    receipt = json.loads((archive / "artifact-789/coverage.json").read_text())
    if mutation == "job-run": jobs["jobs"][0]["run_id"] = 999
    if mutation == "job-attempt": jobs["jobs"][0]["run_attempt"] = 2
    if mutation == "job-source": jobs["jobs"][0]["head_sha"] = "c" * 40
    if mutation == "artifact-run": artifacts["artifacts"][0]["workflow_run"]["id"] = 999
    if mutation == "artifact-source": artifacts["artifacts"][0]["workflow_run"]["head_sha"] = "c" * 40
    if mutation == "artifact-duplicate": artifacts["artifacts"].append(copy.deepcopy(artifacts["artifacts"][0]))
    if mutation == "shard": receipt["shard"]["count"] = 2
    if mutation == "backend": receipt["backend"] = "postgres"
    write_json(archive / "jobs-final.json", jobs)
    write_json(archive / "artifacts-final.json", artifacts)
    write_json(archive / "artifact-789/coverage.json", receipt)
    with pytest.raises(EvidenceError):
        analyze_run(archive)


def test_missing_artifact_is_unknown_not_green(archive):
    write_json(archive / "artifacts-final.json", {"artifacts": []})
    report = analyze_run(archive)
    assert report["jobs"][0]["receipt_status"] == "MISSING"
    assert report["coverage_verdict"] == "NOT_EVALUATED"


def test_pr_merge_source_is_recorded_without_substituting_push(archive):
    run = json.loads((archive / "run-final.json").read_text())
    run["event"] = "pull_request"
    write_json(archive / "run-final.json", run)
    receipt = json.loads((archive / "artifact-789/coverage.json").read_text())
    receipt["identity"]["checked_out_sha"] = receipt["identity"]["event_sha"] = "c" * 40
    write_json(archive / "artifact-789/coverage.json", receipt)
    artifacts = json.loads((archive / "artifacts-final.json").read_text())
    artifacts["artifacts"][0]["name"] = f"backend-file-shard-0-{'c' * 40}-attempt-1"
    write_json(archive / "artifacts-final.json", artifacts)
    report = analyze_run(archive)
    assert report["event"] == "pull_request" and report["head_sha"] == SHA
    assert report["jobs"][0]["identity"]["checked_out_sha"] == "c" * 40
    assert report["coverage_verdict"] == "NOT_EVALUATED"


def test_duplicate_job_is_rejected(archive):
    path = archive / "jobs-final.json"
    jobs = json.loads(path.read_text())
    jobs["jobs"].append(copy.deepcopy(jobs["jobs"][0]))
    write_json(path, jobs)
    with pytest.raises(EvidenceError, match="duplicate backend"):
        analyze_run(archive)


@pytest.mark.parametrize("count", [0, 2])
def test_progress_requires_one_original_suite_command(archive, count):
    path = archive / "job-456.log"
    command = "2026-10-10T00:01:00.2Z PYTHONPATH=fixture python -m pytest -p postgres_gate -p suite_coverage\n"
    path.write_text(command * count + "2026-10-10T00:01:03Z F [100%]\n")
    with pytest.raises(EvidenceError, match="ambiguous original suite command"):
        analyze_run(archive)


@pytest.mark.parametrize("rows", [
    [event("call")], [event("setup"), event("setup")], [event("setup", node="other")],
    [event("setup"), event("teardown"), event("call")],
    [{**event("setup"), "wasxfail": True}],
    [event("unknown")], [event("setup", "unknown")],
])
def test_invalid_event_stream_rejected(rows):
    with pytest.raises(EvidenceError):
        analyze_events({"assigned": [NODE]}, rows)


def test_partial_tail_and_skips_are_observations_only():
    other = "tests/test_original.py::test_next"
    rows = [event("setup", "skipped"), event("teardown"), event("setup", node=other)]
    report, terminal = analyze_events({"assigned": [NODE, other, "unseen"]}, rows)
    assert report["nodes_with_teardown_event"] == 1
    assert report["observed_event_nodes"] == 2 and report["unobserved_nodes"] == 1
    assert report["observed_setup_skips"] == 1
    assert report["observed_call_outcomes"] == {}
    assert terminal == [("s", NODE)]


def test_progress_timing_requires_matching_original_status_prefix():
    with pytest.raises(EvidenceError, match="ordered event"):
        progress_windows("2026-10-10T00:00:01Z . [100%]", [("F", NODE)], "2026-10-10T00:00:00Z")


def test_progress_windows_do_not_extrapolate_untimed_tail():
    report = progress_windows("2026-10-10T00:00:02Z . [ 50%]", [(".", NODE), ("s", "tail")], "2026-10-10T00:00:00Z")
    assert report["matched_terminal_statuses"] == 1
    assert report["unmatched_tail_statuses"] == 1
    assert len(report["largest_windows"]) == 1


def test_prior_infrastructure_progress_is_not_product_execution():
    log = "2026-10-10T00:00:00Z ... [100%]\n2026-10-10T00:01:02Z . [100%]\n"
    report = progress_windows(log, [(".", NODE)], "2026-10-10T00:01:00Z")
    assert report["matched_terminal_statuses"] == 1
    assert report["largest_windows"][0]["seconds"] == 2


def write_xml(path, nodes, duration="1.25"):
    root = ET.Element("testsuites")
    suite = ET.SubElement(root, "testsuite")
    for node in nodes:
        case = ET.SubElement(suite, "testcase", name="display", time=duration)
        props = ET.SubElement(case, "properties")
        ET.SubElement(props, "property", name="ci_nodeid", value=node)
    path.write_bytes(ET.tostring(root))


def test_junit_uses_exact_ids_and_sums_observed_durations(tmp_path):
    path = tmp_path / "report.xml"
    write_xml(path, [NODE])
    report = junit_timings(path, {NODE})
    assert report["summed_testcase_seconds"] == 1.25
    assert report["slowest_modules"] == [{"module": "tests/test_original.py", "seconds": 1.25}]


@pytest.mark.parametrize("nodes,duration", [([NODE, NODE], "1"), ([], "1"), (["different"], "1"),
                                            ([NODE], "NaN"), ([NODE], "inf"), ([NODE], "-1")])
def test_invalid_junit_timing_evidence_rejected(tmp_path, nodes, duration):
    path = tmp_path / "report.xml"
    write_xml(path, nodes, duration)
    with pytest.raises(EvidenceError):
        junit_timings(path, {NODE})


def test_long_identity_is_bounded_without_normalizing_hash():
    long = NODE + "[" + "x" * (4 * 1024 * 1024) + "]"
    result = identify(long)
    assert len(result["preview"]) == 240 and result["preview_truncated"]
    assert result["utf8_sha256"] != identify(long[:-1])["utf8_sha256"]


def test_negative_time_rejected():
    with pytest.raises(EvidenceError):
        seconds("2026-10-10T00:00:01Z", "2026-10-10T00:00:00Z")


def test_cli_preserves_existing_output_and_never_rewrites_inputs(archive):
    original = {p: p.read_bytes() for p in archive.rglob("*") if p.is_file()}
    output = archive / "diagnostic.json"
    assert main(["--run-dir", str(archive), "--output", str(output)]) == 0
    report = output.read_bytes()
    assert main(["--run-dir", str(archive), "--output", str(output)]) == 1
    assert output.read_bytes() == report
    assert all(p.read_bytes() == raw for p, raw in original.items())
