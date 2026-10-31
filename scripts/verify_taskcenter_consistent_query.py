"""Isolated synthetic File verification for the TaskCenter query slice.

Run only on an explicitly authorized CI executor. This script never imports the
application in its own process, never supplies credentials, and never starts a
database, model, service, worker, or user desktop session.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import xml.etree.ElementTree as ET


BASE = "ffe1937911cff32d4ebd4770b350674627501d3a"
BASE_TREE = "447bfefcee8393b9b0907fe7daff2d5b044709da"
FOCUSED = [
    "tests/test_taskcenter_query_backend.py",
    "tests/test_taskcenter_consistent_query.py",
    "tests/test_taskcenter_cursor_independent.py",
    "tests/test_taskcenter_query_measurements.py",
]
REGRESSION = [
    "tests/test_collaboration_http_boundary_v056.py",
    "tests/test_packaged_local_session_bootstrap_v070.py",
    "tests/test_p0_security_regressions.py",
    "tests/test_phase1_media_project_authorization.py",
    "tests/test_phase6_agent_jobs.py",
    "tests/test_phase6_agent_authorization.py",
    "tests/test_export_jobs.py",
    "tests/test_api_v1_alias.py",
    "tests/test_studio_production_query.py",
]
PLUGIN = r"""
import hashlib
import json
import os
from pathlib import Path
import sys

_reports = []
_collected = []
_collection_errors = []

def pytest_collection_finish(session):
    global _collected
    _collected = [item.nodeid for item in session.items]

def pytest_collectreport(report):
    if report.failed:
        _collection_errors.append({"nodeid": report.nodeid, "message": str(report.longrepr)})

def pytest_runtest_logreport(report):
    if report.failed:
        crash = getattr(report.longrepr, "reprcrash", None)
        _reports.append({
            "nodeid": report.nodeid,
            "when": report.when,
            "failure_message": getattr(crash, "message", str(report.longrepr)),
        })

def pytest_sessionfinish(session, exitstatus):
    modules = {}
    root = Path(os.environ["TASKCENTER_SOURCE_ROOT"]).resolve()
    violations = []
    for name, module in list(sys.modules.items()):
        if not (name == "app" or name.startswith("app.") or name.startswith("test_")):
            continue
        filename = getattr(module, "__file__", None)
        if not filename:
            continue
        path = Path(filename).resolve()
        if path.is_file():
            modules[name] = {
                "path": str(path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            if (name == "app" or name.startswith("app.")) and not path.is_relative_to(root):
                violations.append(name)
    Path(os.environ["TASKCENTER_EVIDENCE_PATH"]).write_text(json.dumps({
        "source_root": str(root), "exitstatus": int(exitstatus),
        "failed_reports": _reports, "collected_nodeids": _collected,
        "collection_errors": _collection_errors, "modules": modules,
        "outside_source_modules": violations,
    }, indent=2, sort_keys=True), encoding="utf-8")
"""


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(root, *arguments):
    return subprocess.check_output(["git", "-C", str(root), *arguments], text=True).strip()


def hash_sources(root, output):
    files = [*root.glob("app/**/*.py"), *root.glob("tests/test_taskcenter*.py")]
    files += [root / "pyproject.toml", root / "AGENTS.md", root / "tests/conftest.py",
              root / "scripts/verify_taskcenter_consistent_query.py",
              root / ".github/workflows/taskcenter-consistent-query.yml"]
    result = {
        str(path.relative_to(root)): sha256(path)
        for path in sorted(files) if path.is_file()
    }
    write_json(output, result)
    return result


def junit_summary(path):
    if not path.is_file():
        return {"present": False, "tests": 0, "failures": [], "errors": []}
    document = ET.parse(path)
    cases = document.findall(".//testcase")
    failures, errors = [], []
    for case in cases:
        for kind, destination in (("failure", failures), ("error", errors)):
            for item in case.findall(kind):
                destination.append({
                    "classname": case.get("classname"),
                    "name": case.get("name"),
                    "message": item.get("message"),
                    "type": item.get("type"),
                })
    return {"present": True, "tests": len(cases), "failures": failures, "errors": errors}


def run_group(name, source, arguments, output, scratch, support):
    run = scratch / name
    run.mkdir()
    env = os.environ.copy()
    for key in (
        "DEEPSEEK_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY",
        "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "XAI_API_KEY",
        "DASHSCOPE_API_KEY", "GROQ_API_KEY", "MISTRAL_API_KEY", "DATABASE_URL",
        "TEST_POSTGRES_DATABASE_URL", "E2E_DATABASE_URL",
    ):
        env.pop(key, None)
    for key, folder in (
        ("HOME", "home"), ("LOCALAPPDATA", "localappdata"), ("NOVEL_DATA_PATH", "data"),
        ("TMPDIR", "tmp"), ("XDG_DATA_HOME", "xdg-data"),
        ("XDG_CONFIG_HOME", "xdg-config"), ("XDG_CACHE_HOME", "xdg-cache"),
    ):
        directory = run / folder
        directory.mkdir()
        env[key] = str(directory)
    loaded = output / (name + "-loaded-modules.json")
    env.update(
        PROJECT_ROOT=str(source),
        PYTHONPATH=os.pathsep.join((str(source), str(source / "tests"), str(support))),
        STORAGE_BACKEND="file", CREDENTIAL_VAULT_BACKEND="memory",
        CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK="true", MOCK_PROVIDER="true",
        ENABLE_CLOUD="false", TASKCENTER_SOURCE_ROOT=str(source),
        TASKCENTER_EVIDENCE_PATH=str(loaded),
    )
    xml = output / (name + ".xml")
    command = [
        sys.executable, "-m", "pytest", *arguments, "-q",
        "-p", "taskcenter_evidence", "--junitxml=" + str(xml),
        "--basetemp=" + str(run / "pytest-tmp"), "-o", "cache_dir=" + str(run / "pytest-cache"),
    ]
    timed_out = False
    with (output / (name + ".log")).open("w", encoding="utf-8") as log:
        log.write("cwd=" + str(source) + "\ncommand=" + json.dumps(command) + "\n")
        log.flush()
        try:
            result = subprocess.run(command, cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=240)
            returncode = result.returncode
        except subprocess.TimeoutExpired:
            returncode, timed_out = 124, True
            log.write("\nVERIFICATION_SUBPROCESS_TIMEOUT\n")
    evidence = json.loads(loaded.read_text(encoding="utf-8")) if loaded.is_file() else {}
    summary = {
        "command": command, "cwd": str(source), "returncode": returncode,
        "timed_out": timed_out, "junit": junit_summary(xml),
        "loaded_module_evidence_present": loaded.is_file(),
        "outside_source_modules": evidence.get("outside_source_modules", ["EVIDENCE_MISSING"]),
        "failed_reports": evidence.get("failed_reports", []),
        "collected_nodeids": evidence.get("collected_nodeids", []),
        "collection_errors": evidence.get("collection_errors", []),
    }
    write_json(output / (name + "-summary.json"), summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    candidate = Path(__file__).resolve().parents[1]
    head = git(candidate, "rev-parse", "HEAD")
    metadata = {
        "baseline_sha": BASE, "baseline_expected_tree": BASE_TREE,
        "candidate_sha": head, "candidate_tree": git(candidate, "rev-parse", "HEAD^{tree}"),
        "python": sys.version, "focused_files": FOCUSED, "regression_files": REGRESSION,
        "provider": "MOCK_PROVIDER_SYNTHETIC_ONLY",
        "not_run": ["real PostgreSQL", "Windows", "real frontend", "real model"],
    }
    write_json(output / "metadata.json", metadata)
    if os.getenv("GITHUB_ACTIONS") == "true":
        if os.getenv("GITHUB_REPOSITORY") != "1785235376-blip/AI-Novel-Studio":
            raise RuntimeError("UNEXPECTED_REPOSITORY")
        if os.getenv("GITHUB_REF") != "refs/heads/work/taskcenter-consistent-query-20261025":
            raise RuntimeError("UNEXPECTED_TASK_BRANCH")
    with tempfile.TemporaryDirectory(prefix="taskcenter-verification-") as temporary:
        scratch = Path(temporary)
        baseline = scratch / "baseline"
        baseline.mkdir()
        subprocess.run(["git", "-C", str(candidate), "fetch", "--no-tags", "--depth=1", "origin", BASE], check=True)
        if git(candidate, "rev-parse", BASE + "^{tree}") != BASE_TREE:
            raise RuntimeError("FIXED_BASELINE_TREE_MISMATCH")
        archive = scratch / "baseline.tar"
        subprocess.run(["git", "-C", str(candidate), "archive", "--format=tar", "--output=" + str(archive), BASE], check=True)
        with tarfile.open(archive) as source:
            source.extractall(baseline, filter="data")
        support = scratch / "support"
        support.mkdir()
        plugin = support / "taskcenter_evidence.py"
        plugin.write_text(PLUGIN, encoding="utf-8")
        write_json(output / "evidence-plugin.json", {"sha256": sha256(plugin), "content": PLUGIN})
        baseline_before = hash_sources(baseline, output / "baseline-source-hashes.json")
        candidate_before = hash_sources(candidate, output / "candidate-source-hashes.json")
        results = {}
        results["baseline_original"] = run_group(
            "baseline-original", baseline, FOCUSED[:1], output, scratch, support)
        results["baseline_regression"] = run_group(
            "baseline-regression", baseline, REGRESSION, output, scratch, support)
        probe_source = candidate / FOCUSED[1]
        probe_target = baseline / FOCUSED[1]
        if probe_target.exists():
            raise RuntimeError("FIXED_BASELINE_ALREADY_HAS_NEW_PROBE")
        probe_target.write_bytes(probe_source.read_bytes())
        write_json(output / "baseline-red-overlay.json", {
            "path": FOCUSED[1], "source_sha256": sha256(probe_source),
            "target_sha256": sha256(probe_target),
            "scope": "ONLY_NEW_TEST_FILE_ADDED_AFTER_UNMODIFIED_BASELINE_RUNS",
        })
        results["baseline_red"] = run_group(
            "baseline-red", baseline, [FOCUSED[1], "-k", "test_m0_"], output, scratch, support)
        results["candidate_focused"] = run_group(
            "candidate-focused", candidate, [*FOCUSED, "-s"], output, scratch, support)
        results["candidate_regression"] = run_group(
            "candidate-regression", candidate, REGRESSION, output, scratch, support)
        baseline_after = hash_sources(baseline, output / "baseline-source-hashes-after.json")
        candidate_after = hash_sources(candidate, output / "candidate-source-hashes-after.json")
        baseline_expected = {**baseline_before, FOCUSED[1]: sha256(probe_source)}
        sources_unchanged = (
            baseline_after == baseline_expected and candidate_after == candidate_before
        )
        write_json(output / "source-integrity.json", {
            "baseline_unchanged_except_recorded_red_test": baseline_after == baseline_expected,
            "candidate_unchanged": candidate_after == candidate_before,
            "allowed_baseline_overlay": {FOCUSED[1]: sha256(probe_source)},
        })
        before = results["baseline_regression"]
        after = results["candidate_regression"]
        same_regression = (
            before["returncode"] in (0, 1) and after["returncode"] in (0, 1)
            and before["junit"]["present"] and after["junit"]["present"]
            and before["junit"]["tests"] > 0
            and before["collected_nodeids"] == after["collected_nodeids"]
            and bool(before["collected_nodeids"])
            and not before["collection_errors"] and not after["collection_errors"]
            and before["junit"]["failures"] == after["junit"]["failures"]
            and before["junit"]["errors"] == after["junit"]["errors"]
            and before["failed_reports"] == after["failed_reports"]
        )
        red = results["baseline_red"]
        effective_red = (
            red["returncode"] == 1 and red["junit"]["tests"] > 0
            and bool(red["junit"]["failures"]) and not red["junit"]["errors"]
        )
        evidence_ok = all(
            item["loaded_module_evidence_present"] and not item["outside_source_modules"]
            and not item["collection_errors"]
            for item in results.values()
        )
        accepted = (
            results["baseline_original"]["returncode"] == 0
            and results["candidate_focused"]["returncode"] == 0
            and same_regression and effective_red and evidence_ok and sources_unchanged
        )
        report = {
            "accepted": accepted, "effective_baseline_red": effective_red,
            "regression_nodeids_and_messages_match": same_regression,
            "source_isolation_verified": evidence_ok, "source_integrity_verified": sources_unchanged,
            "results": results,
            "interpretation": (
                "Focused tests and unchanged regression evidence only; existing baseline failures remain reported. "
                "Cursor HTTP support and complete product readiness are not claimed."
            ),
        }
        write_json(output / "verification-summary.json", report)
        print(json.dumps(report, indent=2, sort_keys=True), flush=True)
    manifest = {
        path.name: {"sha256": sha256(path), "bytes": path.stat().st_size}
        for path in sorted(output.iterdir()) if path.is_file() and path.name != "artifact-hashes.json"
    }
    write_json(output / "artifact-hashes.json", manifest)
    if sum(item["bytes"] for item in manifest.values()) > 20_000_000:
        raise RuntimeError("VERIFICATION_ARTIFACT_SIZE_LIMIT")
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
