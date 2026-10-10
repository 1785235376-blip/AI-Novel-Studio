"""Standalone CI infrastructure tests, intentionally outside product collection."""

from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "coverage_plugin_under_test", ROOT / "suite_coverage.py"
)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def report(when, outcome="passed", reason=None, xfail=False):
    return {"when": when, "outcome": outcome, "skip_reason": reason, "wasxfail": xfail}


def valid():
    return [report("setup"), report("call"), report("teardown")]


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "duplicate",
        "reordered",
        "setup-failure",
        "call-failure",
        "teardown-failure",
        "xfail",
        "xpass",
        "unknown-node",
        "missing-call",
        "unexpected-skip",
        "teardown-skip",
    ],
)
def test_incomplete_or_failed_outcome_rejected(change):
    outcomes = {"node": valid()}
    rows = outcomes["node"]
    if change == "missing":
        outcomes.clear()
    elif change == "duplicate":
        rows.extend(valid())
    elif change == "reordered":
        rows.reverse()
    elif change.endswith("-failure"):
        next(row for row in rows if row["when"] == change.split("-")[0])["outcome"] = (
            "failed"
        )
    elif change in {"xfail", "xpass"}:
        rows[1]["wasxfail"] = True
    elif change == "unknown-node":
        outcomes["extra"] = valid()
    elif change == "missing-call":
        del rows[1]
    elif change == "unexpected-skip":
        outcomes["node"] = [report("setup", "skipped", "surprise"), report("teardown")]
    elif change == "teardown-skip":
        rows[2] = report("teardown", "skipped", "surprise")
    assert gate.outcome_errors(
        [{"nodeid": "node", "backend": "both"}],
        ["node"],
        outcomes,
        "file",
        "backend",
        {"skips": {"file": {}}},
    )


@pytest.mark.parametrize(
    "backend,classification,reason",
    [
        ("file", "postgres", gate.POSTGRES_SKIP),
        ("postgres", "file", gate.FILE_SKIP),
    ],
)
def test_opposite_skip_is_exact_and_setup_only(backend, classification, reason):
    inventory = [{"nodeid": "node", "backend": classification}]
    manifest = {"skips": {backend: {}}}
    correct = {"node": [report("setup", "skipped", reason), report("teardown")]}
    assert not gate.outcome_errors(
        inventory, ["node"], correct, backend, "interop", manifest
    )
    incorrect = {
        "node": [report("setup"), report("call", "skipped", reason), report("teardown")]
    }
    assert gate.outcome_errors(
        inventory, ["node"], incorrect, backend, "interop", manifest
    )
    correct["node"][0]["skip_reason"] = "another reason"
    assert gate.outcome_errors(
        inventory, ["node"], correct, backend, "interop", manifest
    )


@pytest.mark.parametrize("phase", ["setup", "call"])
def test_exact_optional_legacy_skip_is_allowed_only_in_backend_scope(phase):
    rows = (
        [report("setup", "skipped", "manual"), report("teardown")]
        if phase == "setup"
        else [report("setup"), report("call", "skipped", "manual"), report("teardown")]
    )
    inventory = [{"nodeid": "node", "backend": "both"}]
    manifest = {"skips": {"file": {"node": "manual"}}}
    assert not gate.outcome_errors(
        inventory, ["node"], {"node": rows}, "file", "backend", manifest
    )
    assert gate.outcome_errors(
        inventory, ["node"], {"node": rows}, "file", "interop", manifest
    )
    inventory[0]["backend"] = "file"
    assert gate.outcome_errors(
        inventory, ["node"], {"node": rows}, "file", "backend", manifest
    )


def test_assignment_is_stable_disjoint_complete_and_preserves_selected_order():
    nodes = [f"tests/test_sample.py::test_value[{i}]" for i in range(101)]
    shards = [
        [node for node in nodes if gate.shard_for(node, 2) == index] for index in (0, 1)
    ]
    assert set(shards[0]).isdisjoint(shards[1])
    assert set(shards[0]) | set(shards[1]) == set(nodes)
    assert all(gate.shard_for(node, 1) == 0 for node in nodes)


def test_opposite_legacy_reason_is_exact_and_only_for_full_backend():
    inventory = [{"nodeid": "old-pg", "backend": "postgres"}]
    manifest = {"skips": {"file": {"old-pg": "dedicated database not configured"}}}
    rows = {
        "old-pg": [
            report("setup", "skipped", "dedicated database not configured"),
            report("teardown"),
        ]
    }
    assert not gate.outcome_errors(
        inventory, ["old-pg"], rows, "file", "backend", manifest
    )
    assert gate.outcome_errors(inventory, ["old-pg"], rows, "file", "interop", manifest)
    rows["old-pg"] = valid()
    assert gate.outcome_errors(inventory, ["old-pg"], rows, "file", "backend", manifest)


def test_only_exact_declared_external_gate_permits_applicable_file_skip():
    node = "tcp"
    inventory = [{"nodeid": node, "backend": "file"}]
    rows = {node: [report("setup", "skipped", "explicit TCP gate"), report("teardown")]}
    manifest = {
        "skips": {"file": {node: "explicit TCP gate"}},
        "external_gates": {
            "file": {
                node: {"reason": "explicit TCP gate", "junit_filename": "sync-tcp.xml"}
            }
        },
    }
    assert not gate.outcome_errors(inventory, [node], rows, "file", "backend", manifest)
    assert gate.outcome_errors(inventory, [node], rows, "file", "interop", manifest)
    manifest["external_gates"]["file"].clear()
    assert gate.outcome_errors(inventory, [node], rows, "file", "backend", manifest)


@pytest.fixture
def toy(tmp_path):
    root = tmp_path / "project"
    (root / "tests").mkdir(parents=True)
    (root / ".github/ci").mkdir(parents=True)
    (root / ".github/ci/python-constraints.txt").write_text("pytest>=8,<9\n")
    (root / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\ntestpaths=["tests"]\nmarkers=["file_backend_only", "postgres_backend_only"]\n'
    )
    (root / "tests/test_local_interop_toy.py").write_text("""import pytest
def test_both(): assert True
@pytest.mark.file_backend_only
def test_file(): assert True
@pytest.mark.postgres_backend_only
def test_postgres(): assert True
def test_second_both(): assert True
""")
    (root / "tests/conftest.py").write_text(
        '''import os, pytest
def pytest_collection_modifyitems(items):
    profile=os.environ["STORAGE_BACKEND"]
    for item in items:
        if profile=="postgres" and item.get_closest_marker("file_backend_only"):
            item.add_marker(pytest.mark.skip(reason="'''
        + gate.FILE_SKIP
        + '''"))
        if profile=="file" and item.get_closest_marker("postgres_backend_only"):
            item.add_marker(pytest.mark.skip(reason="'''
        + gate.POSTGRES_SKIP
        + """"))
"""
    )
    nodes = [
        "tests/test_local_interop_toy.py::" + name
        for name in ("test_both", "test_file", "test_postgres", "test_second_both")
    ]
    manifest = {
        "schema_version": 1,
        "product_nodes": nodes,
        "added_nodes": [],
        "source_files": {
            str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in [
                root / "tests/test_local_interop_toy.py",
                root / "tests/conftest.py",
            ]
        },
        "skips": {"file": {}, "postgres": {}},
    }
    manifest_path = root / ".github/ci/coverage_manifest.json.gz"
    manifest_path.write_bytes(gzip.compress(json.dumps(manifest).encode(), mtime=0))
    environment = {
        **os.environ,
        "PYTHONPATH": str(ROOT),
        "PYTHONDONTWRITEBYTECODE": "1",
        "CI_COVERAGE_SHA": "a" * 40,
        "CI_COVERAGE_TREE": "b" * 40,
        "GITHUB_SHA": "a" * 40,
        "GITHUB_RUN_ID": "1",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_REPOSITORY": "owner/repo",
        "STORAGE_BACKEND": "file",
        "TEST_POSTGRES_DATABASE_URL": "postgresql://synthetic",
    }

    def run(*extra, backend="file", index=0, count=1):
        output = tmp_path / f"receipts-{backend}-{index}"
        environment["STORAGE_BACKEND"] = backend
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "suite_coverage",
            "-p",
            "no:cacheprovider",
            "-q",
            "--ci-coverage-dir",
            str(output),
            "--ci-shard-index",
            str(index),
            "--ci-shard-count",
            str(count),
            "--junitxml",
            str(output / "backend.xml"),
            *extra,
        ]
        result = subprocess.run(
            command,
            check=False,
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result, output

    return root, manifest, manifest_path, run


def test_real_pytest_plugin_finishes_after_junit_and_records_both_profiles(toy):
    _, _, _, run = toy
    receipts = []
    for backend, index, count in (
        ("file", 0, 1),
        ("postgres", 0, 2),
        ("postgres", 1, 2),
    ):
        result, output = run(backend=backend, index=index, count=count)
        assert result.returncode == 0, result.stdout + result.stderr
        receipt = json.loads((output / "coverage.json").read_text())
        assert receipt["complete"] is True
        assert receipt["pytest_exitstatus"] == 0 and receipt["validation_errors"] == []
        assert len(receipt["inventory"]) == 4
        assert (output / "backend.xml").is_file()
        receipts.append(receipt)
    assert (
        receipts[0]["inventory"] == receipts[1]["inventory"] == receipts[2]["inventory"]
    )
    assert set(receipts[1]["assigned"]).isdisjoint(receipts[2]["assigned"])
    assert set(receipts[1]["assigned"]) | set(receipts[2]["assigned"]) == set(
        receipts[0]["assigned"]
    )


@pytest.mark.parametrize(
    "extra",
    [
        ["-k", "test_both"],
        ["-m", "file_backend_only"],
        ["--ignore", "tests/missing.py"],
        ["--deselect", "tests/test_local_interop_toy.py::test_both"],
    ],
)
def test_external_selection_flags_are_rejected_even_if_no_node_is_removed(toy, extra):
    _, _, _, run = toy
    result, _ = run(*extra)
    assert result.returncode != 0
    assert "external test filtering is forbidden" in result.stderr


def test_product_source_mutation_rejected_before_any_case(toy):
    root, _, _, run = toy
    (root / "tests/test_local_interop_toy.py").write_text("def test_weakened(): pass\n")
    result, _ = run()
    assert result.returncode != 0
    assert "frozen product test/source digest differs" in result.stderr


def test_incomplete_universe_is_rejected(toy):
    _, manifest, path, run = toy
    manifest["product_nodes"].pop()
    path.write_bytes(gzip.compress(json.dumps(manifest).encode(), mtime=0))
    result, output = run()
    assert result.returncode != 0
    assert json.loads((output / "coverage.json").read_text())["complete"] is False


def test_collect_only_never_produces_passing_execution_receipt(toy):
    _, _, _, run = toy
    result, output = run("--collect-only")
    assert result.returncode != 0
    assert json.loads((output / "coverage.json").read_text())["complete"] is False
