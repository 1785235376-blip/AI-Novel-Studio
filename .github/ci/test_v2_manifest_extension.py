"""Additive V2 manifest self-tests; no product test execution is claimed here."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.extend_v2_coverage_manifest import (
    ExtensionError, MIGRATION_AFTER, MIGRATION_BEFORE, MIGRATION_COMMIT, MIGRATION_PATH,
    extend_manifest, protected_source, verified_baseline_migration,
)
from scripts.run_v2_postgres_checks import validate_owned_cluster


def fixture():
    baseline = {"schema_version": 1, "product_nodes": ["tests/test_old.py::test_old"],
                "added_nodes": [], "source_files": {"tests/test_old.py": "a" * 64, "app/old.py": "b" * 64},
                "skips": {"file": {"tests/test_old.py::test_old": "historical reason"}, "postgres": {}},
                "external_gates": {"file": {}, "postgres": {}}}
    rows = [{"nodeid": "tests/test_old.py::test_old", "backend": "both"},
            {"nodeid": "tests/test_new.py::test_new", "backend": "postgres"}]
    sources = {**baseline["source_files"], "app/old.py": "c" * 64, "tests/test_new.py": "d" * 64}
    return baseline, rows, sources


def test_additive_inventory_retains_original_order_bytes_and_skips(tmp_path):
    baseline, rows, sources = fixture()
    original = copy.deepcopy(baseline)
    result, report = extend_manifest(tmp_path, baseline, rows, sources, "e" * 64)
    assert baseline == original
    assert result["product_nodes"] == [row["nodeid"] for row in rows]
    assert result["added_nodes"] == [rows[1]["nodeid"]]
    assert result["skips"] == original["skips"]
    assert result["external_gates"] == original["external_gates"]
    assert result["source_files"]["tests/test_old.py"] == original["source_files"]["tests/test_old.py"]
    assert report["status"] == "INVENTORY_ONLY" and report["tests_executed"] is False


@pytest.mark.parametrize("mutation", ["missing-node", "duplicate", "changed-test", "missing-hash", "invalid-backend"])
def test_manifest_rejects_test_erosion(tmp_path, mutation):
    baseline, rows, sources = fixture()
    if mutation == "missing-node": rows.pop(0)
    elif mutation == "duplicate": rows.append(rows[0])
    elif mutation == "changed-test": sources["tests/test_old.py"] = "f" * 64
    elif mutation == "missing-hash": sources.pop("tests/test_new.py")
    elif mutation == "invalid-backend": rows[0]["backend"] = "unknown"
    with pytest.raises(ExtensionError): extend_manifest(tmp_path, baseline, rows, sources, "e" * 64)


def test_baseline_relative_order_cannot_change(tmp_path):
    baseline, rows, sources = fixture()
    baseline["product_nodes"].append("tests/test_old.py::test_second")
    rows.insert(0, {"nodeid": "tests/test_old.py::test_second", "backend": "both"})
    with pytest.raises(ExtensionError, match="reordered"):
        extend_manifest(tmp_path, baseline, rows, sources, "e" * 64)


@pytest.mark.parametrize("path", ["tests/helpers.py", "frontend/src/App.test.tsx", "frontend/tests/example.spec.ts", ".github/ci/postgres_gate.py"])
def test_existing_tests_and_coverage_gates_are_protected(path):
    assert protected_source(path)
    assert not protected_source("app/creative/service.py")


def test_reviewed_migration_requires_exact_hashes_and_single_flag_provenance(monkeypatch):
    # Hosted checkout is shallow. Historical Git objects are checked during
    # explicit local generation; exercise that exact-byte guard with fixtures here.
    migrated = (ROOT / MIGRATION_PATH).read_bytes()
    original = migrated.replace(b'"%PYTHON%" -B -I -m', b'"%PYTHON%" -I -m')
    calls = []
    def read_git(command, cwd):
        calls.append(command[-1])
        return original if command[-1].startswith(MIGRATION_COMMIT + "^") else migrated
    monkeypatch.setattr("scripts.extend_v2_coverage_manifest.subprocess.check_output", read_git)
    result = verified_baseline_migration(ROOT, MIGRATION_BEFORE, MIGRATION_AFTER)
    assert result["path"] == MIGRATION_PATH and result["commit"] == MIGRATION_COMMIT
    assert calls == [f"{MIGRATION_COMMIT}^:{MIGRATION_PATH}", f"{MIGRATION_COMMIT}:{MIGRATION_PATH}"]
    with pytest.raises(ExtensionError): verified_baseline_migration(ROOT, MIGRATION_BEFORE, "f" * 64)


def test_postgres_wrapper_refuses_unowned_or_uninitialized_cluster(tmp_path):
    pg_bin = tmp_path / "bin"; pg_bin.mkdir()
    (pg_bin / ("pg_ctl.exe" if sys.platform == "win32" else "pg_ctl")).write_text("fixture")
    with pytest.raises(ValueError, match="owned"):
        validate_owned_cluster(tmp_path, pg_bin, tmp_path / "user-data")
    with pytest.raises(ValueError, match="existing disposable"):
        validate_owned_cluster(tmp_path, pg_bin, tmp_path / ".runtime/data")
    data = tmp_path / ".runtime/data"; data.mkdir(parents=True)
    (data / "PG_VERSION").write_text("17")
    assert validate_owned_cluster(tmp_path, pg_bin, data)[1] == data
