"""Append candidate tests to the original strict manifest without loosening gates.

Two fresh, unfiltered pytest collections must agree in exact order. Original
nodes and skip dictionaries stay intact; original source changes fail closed
except the reviewed Windows path-only catalog correction. The original gzip
bytes remain permanently archived beside the recovery evidence.
"""
from __future__ import annotations

import argparse
import ast
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/delivery/full-recovery"
BASELINE_SHA = "665817243cad59eef0d4140f17c2ea644f46971e"
BASELINE_NAME = "PR45_BASELINE_COVERAGE_MANIFEST.json.gz"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(value) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8").strip()


class CollectionRecorder:
    def __init__(self):
        self.inventory = []
        self.errors = []

    def pytest_collection_finish(self, session):
        self.inventory = [
            {"nodeid": item.nodeid,
             "backend": "postgres" if item.get_closest_marker("postgres_backend_only") else
             "file" if item.get_closest_marker("file_backend_only") else "both"}
            for item in session.items
        ]
        for item in session.items:
            if item.get_closest_marker("postgres_backend_only") and item.get_closest_marker("file_backend_only"):
                self.errors.append("contradictory backend-only markers: " + item.nodeid)

    def pytest_collectreport(self, report):
        if report.failed or report.skipped:
            self.errors.append(str(report.nodeid) + ": " + report.outcome)


def collect(path: Path) -> int:
    import pytest
    recorder = CollectionRecorder()
    # No -k/-m/deselect/ignore. Normal repository collection hooks remain active.
    code = int(pytest.main(["--collect-only", "-q", "-p", "no:cacheprovider"], plugins=[recorder]))
    path.write_bytes(encoded({"exit_code": code, "inventory": recorder.inventory, "collection_errors": recorder.errors}) + b"\n")
    return code


def assertions(source: str) -> list[str]:
    return [ast.dump(node, include_attributes=False) for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Assert)]


def baseline_manifest() -> tuple[dict, bytes]:
    original = EVIDENCE / BASELINE_NAME
    if not original.exists():
        raw = subprocess.check_output(["git", "show", BASELINE_SHA + ":.github/ci/coverage_manifest.json.gz"], cwd=ROOT)
        original.write_bytes(raw)
    raw = original.read_bytes()
    expected = subprocess.check_output(["git", "show", BASELINE_SHA + ":.github/ci/coverage_manifest.json.gz"], cwd=ROOT)
    if raw != expected:
        raise ValueError("archived PR45 manifest bytes differ from original Git blob")
    return json.loads(gzip.decompress(raw)), raw


def build(output: Path) -> dict:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    original, raw = baseline_manifest()
    for guard in ("suite_coverage.py", "coverage_reconcile.py", "postgres_gate.py"):
        name = ".github/ci/" + guard
        original_guard = subprocess.check_output(["git", "show", BASELINE_SHA + ":" + name], cwd=ROOT)
        if (ROOT / name).read_bytes() != original_guard:
            raise ValueError("original strict guard changed: " + name)
    fixture_name = ".github/ci/test_coverage_reconcile.py"
    fixture_before_bytes = subprocess.check_output(["git", "show", BASELINE_SHA + ":" + fixture_name], cwd=ROOT)
    fixture_before = fixture_before_bytes.decode("utf-8")
    fixture_after_bytes = (ROOT / fixture_name).read_bytes()
    fixture_after = fixture_after_bytes.decode("utf-8")
    fixture_required = fixture_before.replace("str(path.relative_to(tmp_path))", "path.relative_to(tmp_path).as_posix()")
    if fixture_after != fixture_required or assertions(fixture_before) != assertions(fixture_after):
        raise ValueError("coverage selftest fixture exception exceeds reviewed path-only correction")
    fixture_receipt = {"path":fixture_name, "before_sha256":sha(fixture_before_bytes),
                       "after_sha256":sha(fixture_after_bytes), "all_original_assertion_ast_unchanged":True,
                       "assertion_count":len(assertions(fixture_before)),
                       "assertion_ast_sha256":sha(encoded(assertions(fixture_before))),
                       "scope":"Synthetic selftest source-path serialization only: relative_to(tmp_path).as_posix(); all strict assertions unchanged",
                       "receipt":"docs/delivery/full-recovery/coverage-harness-portability-green.xml"}
    env = dict(os.environ)
    env.update(STORAGE_BACKEND="file", MOCK_PROVIDER="true", MOCK_STREAM_DELAY_MS="0", ENABLE_CLOUD="false",
               CREDENTIAL_VAULT_BACKEND="memory", CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK="true",
               NOVEL_DATA_PATH=str(ROOT / ".runtime/full-recovery/manifest-collection-data"))
    snapshots = []
    for attempt in (1, 2):
        target = EVIDENCE / f"candidate-collection-{attempt}.json"
        with (EVIDENCE / f"candidate-collection-{attempt}.log").open("wb") as log:
            result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--collect-output", str(target)],
                                    cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, check=False)
        snapshot = json.loads(target.read_text(encoding="utf-8"))
        if result.returncode or snapshot["exit_code"] or snapshot["collection_errors"]:
            raise ValueError(f"complete collection {attempt} failed; original output retained")
        snapshots.append(snapshot["inventory"])
    if snapshots[0] != snapshots[1]:
        raise ValueError("independent complete collections differ in exact node order or backend classification")
    current_nodes = [row["nodeid"] for row in snapshots[0]]
    if len(current_nodes) != len(set(current_nodes)):
        raise ValueError("duplicate candidate product nodes")
    original_nodes = original["product_nodes"]
    original_node_set = set(original_nodes)
    if not original_node_set <= set(current_nodes):
        raise ValueError("one or more original 9,116 product nodes disappeared")
    original_subset_in_order = [node for node in current_nodes if node in original_node_set]
    if original_subset_in_order != original_nodes:
        raise ValueError("original product node relative order changed")
    candidate = copy.deepcopy(original)
    exceptions = [fixture_receipt]
    implementation_updates = []
    for name, expected in original["source_files"].items():
        actual = sha((ROOT / name).read_bytes())
        if actual == expected:
            continue
        if name == "pyproject.toml":
            before = subprocess.check_output(["git", "show", BASELINE_SHA + ":" + name], cwd=ROOT).decode("utf-8")
            after = (ROOT / name).read_text(encoding="utf-8")
            required = before.replace('"pypdf==6.19.0"]', '"pypdf==6.19.0", "jsonschema>=4.18,<5"]')
            if after != required:
                raise ValueError("pyproject update exceeds the reviewed production jsonschema dependency addition")
            implementation_updates.append({"path":name,"before_sha256":expected,"after_sha256":actual,
                                           "scope":"Add jsonschema to production dependencies; every original dependency pin, optional dependency and pytest configuration unchanged"})
            candidate["source_files"][name] = actual
            continue
        reviewed_replacements = {
            "tests/test_surface_api_catalog.py": (
                "str(path.relative_to(ROOT))", "path.relative_to(ROOT).as_posix()",
                "Exactly str(relative_to(ROOT)) -> relative_to(ROOT).as_posix(); full map/fingerprint assertions unchanged"),
            "tests/test_r2_windows_base_inputs.py": (
                '    with zipfile.ZipFile(stream, "w") as value:\n        for name in names:\n            value.writestr(name, b"synthetic")',
                '    with zipfile.ZipFile(stream, "w") as value:\n        for name in names:\n            info = zipfile.ZipInfo(name)\n            info.filename = name\n            value.writestr(info, b"synthetic")',
                "Archive fixture serializes the actual raw malicious ZIP entry before Windows ZipInfo normalization; all assertions/parameters unchanged"),
        }
        if name not in reviewed_replacements:
            raise ValueError("unreviewed original frozen source changed: " + name)
        before = subprocess.check_output(["git", "show", BASELINE_SHA + ":" + name], cwd=ROOT).decode("utf-8")
        after = (ROOT / name).read_text(encoding="utf-8")
        old, new, scope = reviewed_replacements[name]
        if name == "tests/test_r2_windows_base_inputs.py" and before.count(old) != 1:
            raise ValueError("reviewed malicious archive fixture context is not unique")
        required = before.replace(old, new)
        if after != required or assertions(before) != assertions(after):
            raise ValueError("source fixture exception exceeds the exact reviewed correction: " + name)
        receipt = {"path": name, "before_sha256": expected, "after_sha256": actual,
                   "all_original_assertion_ast_unchanged": True, "assertion_count":len(assertions(before)),
                   "assertion_ast_sha256": sha(encoded(assertions(before))),
                   "scope":scope,
                   "receipt":"docs/delivery/full-recovery/original-test-preservation.json"}
        exceptions.append(receipt)
        candidate["source_files"][name] = actual
    added = [node for node in current_nodes if node not in original_node_set]
    candidate["product_nodes"] = current_nodes
    candidate["added_nodes"] = [*original["added_nodes"], *added]
    candidate["reviewed_fixture_changes"] = [*original.get("reviewed_fixture_changes", []), *exceptions]
    for path in sorted({node.split("::", 1)[0] for node in current_nodes}):
        candidate["source_files"][path] = sha((ROOT / path).read_bytes())
    # Add the guard code and application sources as stricter candidate inputs.
    # This protects the frozen local working tree as well as hosted Git identity.
    additional_inputs = [*sorted((ROOT / ".github/ci").glob("*.py")),
                         *sorted((ROOT / "app").rglob("*.py")),
                         *sorted((ROOT / "local_interop_protocol").rglob("*.py")),
                         *sorted(path for path in (ROOT / "contracts/local-interop/v1").rglob("*") if path.is_file()),
                         *sorted((ROOT / "scripts").glob("*.py")),
                         *sorted((ROOT / "scripts").glob("*.cjs")),
                         *sorted((ROOT / "packaging").glob("*.json")),
                         *sorted((ROOT / "packaging").glob("*.txt")),
                         *sorted(path for path in (ROOT / "frontend/src").rglob("*") if path.is_file()),
                         *sorted(path for path in (ROOT / "frontend/tests").rglob("*") if path.is_file()),
                         *sorted(path for path in (ROOT / "frontend").glob("*config*")
                                 if path.is_file() and path.suffix in {".json", ".ts", ".js", ".mjs", ".cjs"}),
                         ROOT / "frontend/package.json",
                         *[path for path in (ROOT / "frontend/package-lock.json", ROOT / "frontend/pnpm-lock.yaml") if path.exists()],
                         *sorted((ROOT).glob("API_CATALOG*")), ROOT / "API_OPENAPI.json.gz",
                         *sorted(path for path in (ROOT / "prompts").rglob("*") if path.is_file()),
                         ROOT / "pyproject.toml",
                         Path(__file__).resolve()]
    for path in additional_inputs:
        candidate["source_files"][path.relative_to(ROOT).as_posix()] = sha(path.read_bytes())
    if candidate["skips"] != original["skips"] or encoded(candidate["skips"]) != encoded(original["skips"]):
        raise ValueError("original skip allowlists changed")
    if candidate["external_gates"] != original["external_gates"]:
        raise ValueError("original TCP/external gates changed")
    metadata = {"baseline_pr45_sha": BASELINE_SHA, "baseline_manifest_sha256":sha(raw),
                "baseline_manifest_archive":"docs/delivery/full-recovery/" + BASELINE_NAME,
                "baseline_product_nodes":len(original_nodes), "candidate_product_nodes":len(current_nodes),
                "added_nodes":added, "collections_identical_in_order_and_backend":True,
                "collection_inventory_sha256":sha(encoded(snapshots[0])),
                "original_node_subset_and_relative_order_preserved":True,
                "original_skip_dictionary_sha256":sha(encoded(original["skips"])),
                "candidate_skip_dictionary_sha256":sha(encoded(candidate["skips"])),
                "reviewed_original_source_exceptions":exceptions,
                "reviewed_implementation_source_updates":implementation_updates,
                "source_files_count":len(candidate["source_files"]),
                "source_files_fingerprint_sha256":sha(encoded(candidate["source_files"])),
                "git_head_when_generated":git("rev-parse", "HEAD"),
                "working_tree_provenance":"Frozen current file hashes, not an assertion that uncommitted changes belong to the old Git SHA",
                "platform":"Local Windows/Python supplemental inventory; not hosted Linux execution evidence",
                "suite_coverage_reconciler_postgres_gate_changed":False}
    candidate["full_recovery_inventory"] = metadata
    data = gzip.compress(encoded(candidate) + b"\n", mtime=0)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    metadata["candidate_manifest_sha256"] = sha(data)
    (EVIDENCE / "candidate-coverage-manifest-provenance.json").write_bytes(encoded(metadata) + b"\n")
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--collect-output", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--output", type=Path, default=ROOT / ".github/ci/coverage_manifest.json.gz")
    args = parser.parse_args()
    if args.collect_output:
        raise SystemExit(collect(args.collect_output))
    print(json.dumps(build(args.output), ensure_ascii=False, indent=2))
