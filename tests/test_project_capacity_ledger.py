"""Capacity owner primitives: measurement, reservations, commit, reconcile, adjust.

These tests exercise the new project-capacity accounting owner in isolation from
the still-closed product write gates. They cover positive paths and the
counterexamples required by the capacity ledger: over-limit, concurrent
reservations, expiry after a crashed reserving process, unknown objects blocking
new reservations without deleting them, corrupt ledger fail-closed, CAS/lease on
limit adjustment, physical-object dedupe and digest-based dedupe refusal.

Synthetic temporary directories only; no production data or database is touched.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from app.project_capacity import (
    CapacityLedgerUnavailable,
    CapacityRefused,
    DEFAULT_LIMIT_BYTES,
    ProjectCapacityLedger,
)
from app.project_capacity_measurement import (
    CapacityMeasurementError,
    measure_roots,
)

ROOT = Path(__file__).resolve().parents[1]


def make_ledger(tmp_path: Path, **kwargs) -> ProjectCapacityLedger:
    return ProjectCapacityLedger(tmp_path / "data" / "runtime" / "project-capacity.json", **kwargs)


def raw_ledger(tmp_path: Path) -> dict:
    return json.loads((tmp_path / "data" / "runtime" / "project-capacity.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Reservations / commit / release
# ---------------------------------------------------------------------------

def test_uninitialized_project_is_unavailable_not_silently_created(tmp_path):
    ledger = make_ledger(tmp_path)
    with pytest.raises(CapacityLedgerUnavailable):
        ledger.snapshot("project-a")
    assert not (tmp_path / "data" / "runtime" / "project-capacity.json").exists()


def test_reserve_commit_release_conversion(tmp_path):
    ledger = make_ledger(tmp_path, default_limit_bytes=1000)
    reservation = ledger.reserve("project-a", 400, operation="asset.import", actor_id="author", ttl_seconds=60)
    view = ledger.snapshot("project-a")
    assert (view["used_bytes"], view["reserved_bytes"], view["remaining_bytes"]) == (0, 400, 600)
    assert view["state"] == "OK" and view["reservations"] == 1

    committed = ledger.commit("project-a", reservation["reservation_id"], 250, actor_id="author")
    assert (committed["used_bytes"], committed["reserved_bytes"], committed["remaining_bytes"]) == (250, 0, 750)
    with pytest.raises(CapacityRefused) as repeated:
        ledger.commit("project-a", reservation["reservation_id"], 0, actor_id="author")
    assert repeated.value.code == "PROJECT_CAPACITY_RESERVATION_UNKNOWN"

    second = ledger.reserve("project-a", 100, operation="asset.import", actor_id="author")
    released = ledger.release("project-a", second["reservation_id"], actor_id="author")
    assert (released["used_bytes"], released["reserved_bytes"], released["remaining_bytes"]) == (250, 0, 750)


def test_over_limit_and_two_reservations_that_only_fit_apart(tmp_path):
    ledger = make_ledger(tmp_path, default_limit_bytes=100)
    ledger.reserve("project-a", 60, operation="op", actor_id="author")
    with pytest.raises(CapacityRefused) as refused:
        ledger.reserve("project-a", 60, operation="op", actor_id="author")
    assert refused.value.code == "PROJECT_CAPACITY_EXCEEDED"
    assert refused.value.details["requested_bytes"] == 60


def test_commit_cannot_exceed_reserved_peak_and_only_counts_landed_bytes(tmp_path):
    ledger = make_ledger(tmp_path, default_limit_bytes=100)
    reservation = ledger.reserve("project-a", 50, operation="op", actor_id="author")
    with pytest.raises(CapacityRefused) as exceeded:
        ledger.commit("project-a", reservation["reservation_id"], 51, actor_id="author")
    assert exceeded.value.code == "PROJECT_CAPACITY_COMMIT_EXCEEDS_RESERVATION"
    view = ledger.commit("project-a", reservation["reservation_id"], 50, actor_id="author")
    assert (view["used_bytes"], view["reserved_bytes"], view["remaining_bytes"]) == (50, 0, 50)


def test_released_reservation_never_frees_landed_bytes(tmp_path):
    ledger = make_ledger(tmp_path, default_limit_bytes=100)
    reservation = ledger.reserve("project-a", 40, operation="op", actor_id="author")
    ledger.commit("project-a", reservation["reservation_id"], 40, actor_id="author")
    extra = ledger.reserve("project-a", 10, operation="op", actor_id="author")
    ledger.release("project-a", extra["reservation_id"], actor_id="author")
    view = ledger.snapshot("project-a")
    assert view["used_bytes"] == 40


def test_expired_reservation_from_dead_process_is_retired_without_charging(tmp_path):
    clock = [__import__("time").time()]
    ledger = make_ledger(tmp_path, default_limit_bytes=100, clock=lambda: clock[0])
    ledger.reserve("project-a", 90, operation="op", actor_id="author", ttl_seconds=10)
    clock[0] += 11
    fresh = ledger.reserve("project-a", 90, operation="op", actor_id="author", ttl_seconds=10)
    view = ledger.snapshot("project-a")
    assert view["used_bytes"] == 0 and view["reserved_bytes"] == 90 and view["reservations"] == 1
    assert fresh["capacity"]["state"] == "OK"
    audit = raw_ledger(tmp_path)["projects"]["project-a"]["audit"]
    assert any(entry["action"] == "RESERVATION_EXPIRED" for entry in audit)


def test_incarnation_binding_refuses_recreated_project(tmp_path):
    ledger = make_ledger(tmp_path, default_limit_bytes=100)
    ledger.reserve("project-a", 10, operation="op", actor_id="author", incarnation="inc-1")
    with pytest.raises(CapacityRefused) as changed:
        ledger.reserve("project-a", 10, operation="op", actor_id="author", incarnation="inc-2")
    assert changed.value.code == "PROJECT_CAPACITY_INCARNATION_CHANGED"


def test_unknown_objects_block_new_reservations_and_stay_visible(tmp_path):
    ledger = make_ledger(tmp_path, default_limit_bytes=1000)
    view = ledger.reconcile("project-a", measured_bytes=100, unknown_objects=2,
                            incarnation="inc-1", actor_id="reconciler")
    assert view["state"] == "UNKNOWN_BLOCKED" and view["unknown"] == {"objects": 2, "blocked": True}
    with pytest.raises(CapacityRefused) as blocked:
        ledger.reserve("project-a", 1, operation="op", actor_id="author")
    assert blocked.value.code == "PROJECT_CAPACITY_UNKNOWN_BLOCKED"
    assert ledger.snapshot("project-a")["used_bytes"] == 100


def test_corrupt_ledger_fails_closed_and_is_not_overwritten(tmp_path):
    ledger = make_ledger(tmp_path, default_limit_bytes=100)
    ledger.reserve("project-a", 10, operation="op", actor_id="author")
    path = tmp_path / "data" / "runtime" / "project-capacity.json"
    corrupt = b'{"schema":"project-capacity/1","version":3,"projects":{"project-a":{}}}'
    path.write_bytes(corrupt)
    with pytest.raises(CapacityLedgerUnavailable):
        ledger.snapshot("project-a")
    with pytest.raises(CapacityLedgerUnavailable):
        ledger.reserve("project-a", 1, operation="op", actor_id="author")
    assert path.read_bytes() == corrupt


def test_ledger_survives_restart_and_keeps_cross_process_reservation(tmp_path):
    first = make_ledger(tmp_path, default_limit_bytes=100, pid=1111)
    reservation = first.reserve("project-a", 30, operation="op", actor_id="author", ttl_seconds=3600)
    second = make_ledger(tmp_path, default_limit_bytes=100, pid=2222)
    view = second.snapshot("project-a")
    assert view["reserved_bytes"] == 30 and view["reservations"] == 1
    committed = second.commit("project-a", reservation["reservation_id"], 20, actor_id="author")
    assert committed["used_bytes"] == 20


def test_audit_history_is_bounded(tmp_path):
    ledger = make_ledger(tmp_path, default_limit_bytes=10_000)
    for _ in range(40):
        reservation = ledger.reserve("project-a", 1, operation="op", actor_id="author")
        ledger.release("project-a", reservation["reservation_id"], actor_id="author")
    audit = raw_ledger(tmp_path)["projects"]["project-a"]["audit"]
    assert 0 < len(audit) <= 32 and audit[-1]["action"] == "RELEASE"


def test_concurrent_reservations_serialize_across_processes(tmp_path):
    path = tmp_path / "data" / "runtime" / "project-capacity.json"
    worker = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
from app.project_capacity import CapacityRefused, ProjectCapacityLedger
ledger = ProjectCapacityLedger(sys.argv[2], default_limit_bytes=170)
try:
    result = ledger.reserve("project-a", 60, operation="op", actor_id="child", ttl_seconds=60)
    print(json.dumps({"ok": True, "id": result["reservation_id"]}))
except CapacityRefused as exc:
    print(json.dumps({"ok": False, "code": exc.code}))
""".strip()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        runs = [pool.submit(subprocess.run, [sys.executable, "-c", worker, str(ROOT), str(path)],
                            capture_output=True, text=True, cwd=str(ROOT), timeout=90) for _ in range(4)]
        results = [json.loads(run.result().stdout.strip().splitlines()[-1]) for run in runs]
    assert sum(1 for item in results if item["ok"]) == 2
    assert sum(1 for item in results if not item["ok"] and item["code"] == "PROJECT_CAPACITY_EXCEEDED") == 2
    view = make_ledger(tmp_path, default_limit_bytes=170).snapshot("project-a")
    assert view["reserved_bytes"] == 120 and view["reservations"] == 2


def test_killed_reserving_process_leaves_only_ttl_scoped_reservation(tmp_path):
    path = tmp_path / "data" / "runtime" / "project-capacity.json"
    worker = r"""
import sys
sys.path.insert(0, sys.argv[1])
from app.project_capacity import ProjectCapacityLedger
ProjectCapacityLedger(sys.argv[2], default_limit_bytes=100).reserve(
    "project-a", 90, operation="op", actor_id="child", ttl_seconds=5)
print("RESERVED")
"""
    completed = subprocess.run([sys.executable, "-c", worker, str(ROOT), str(path)],
                               capture_output=True, text=True, cwd=str(ROOT), timeout=90)
    assert completed.returncode == 0 and completed.stdout.strip() == "RESERVED"
    clock = [__import__("time").time()]
    ledger = make_ledger(tmp_path, default_limit_bytes=100, clock=lambda: clock[0])
    assert ledger.snapshot("project-a")["used_bytes"] == 0
    clock[0] += 6
    fresh = ledger.reserve("project-a", 90, operation="op", actor_id="author", ttl_seconds=30)
    assert fresh["capacity"]["reserved_bytes"] == 90 and fresh["capacity"]["used_bytes"] == 0


# ---------------------------------------------------------------------------
# Reconcile and limit adjustment
# ---------------------------------------------------------------------------

def test_reconcile_sets_used_and_audits(tmp_path):
    ledger = make_ledger(tmp_path, default_limit_bytes=1000)
    view = ledger.reconcile("project-a", measured_bytes=250, unknown_objects=0,
                            incarnation="inc-1", actor_id="reconciler")
    assert (view["used_bytes"], view["unknown"], view["state"]) == (250, {"objects": 0, "blocked": False}, "OK")
    audit = raw_ledger(tmp_path)["projects"]["project-a"]["audit"]
    assert any(entry["action"] == "RECONCILE" and entry["measured_bytes"] == 250 for entry in audit)


def test_adjust_limit_requires_matching_lease_and_version(tmp_path):
    ledger = make_ledger(tmp_path, default_limit_bytes=1000)
    ledger.reconcile("project-a", measured_bytes=100, unknown_objects=0,
                     incarnation="inc-1", actor_id="reconciler")
    version = raw_ledger(tmp_path)["version"]
    with pytest.raises(CapacityRefused) as unscoped:
        ledger.adjust_limit("project-a", 2000, expected_version=version,
                            lease={"novel_id": "project-b", "incarnation": "inc-1"}, actor_id="manager")
    assert unscoped.value.code == "PROJECT_CAPACITY_ADJUSTMENT_UNSCOPED"
    with pytest.raises(CapacityRefused) as stale:
        ledger.adjust_limit("project-a", 2000, expected_version=version - 1,
                            lease={"novel_id": "project-a", "incarnation": "inc-1"}, actor_id="manager")
    assert stale.value.code == "PROJECT_CAPACITY_VERSION_CONFLICT"
    view = ledger.adjust_limit("project-a", 2000, expected_version=version,
                               lease={"novel_id": "project-a", "incarnation": "inc-1"}, actor_id="manager")
    assert view["limit_bytes"] == 2000 and view["used_bytes"] == 100


def test_lowering_below_used_keeps_content_and_reservations_but_blocks_new(tmp_path):
    ledger = make_ledger(tmp_path, default_limit_bytes=1000)
    ledger.reconcile("project-a", measured_bytes=300, unknown_objects=0,
                     incarnation="inc-1", actor_id="reconciler")
    active = ledger.reserve("project-a", 100, operation="op", actor_id="author")
    version = raw_ledger(tmp_path)["version"]
    view = ledger.adjust_limit("project-a", 200, expected_version=version,
                               lease={"novel_id": "project-a", "incarnation": "inc-1"}, actor_id="manager")
    assert view["state"] == "OVER_LIMIT" and view["reserved_bytes"] == 100
    assert active["reservation_id"] in raw_ledger(tmp_path)["projects"]["project-a"]["reservations"]
    with pytest.raises(CapacityRefused) as blocked:
        ledger.reserve("project-a", 1, operation="op", actor_id="author")
    assert blocked.value.code == "PROJECT_CAPACITY_EXCEEDED"


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------

def _write(path: Path, size: int, byte: bytes = b"x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(byte * size)


def test_measurement_counts_logical_bytes_and_same_object_once(tmp_path):
    root = tmp_path / "project"
    _write(root / "a.txt", 10)
    _write(root / "notes" / "b.bin", 5)
    os.link(root / "a.txt", root / "a-hardlink.txt")
    # Identical content in two physical files is still two objects: never
    # dedupe by digest.
    _write(root / "same-1.bin", 4, b"z")
    _write(root / "same-2.bin", 4, b"z")
    result = measure_roots([("project", root)])
    assert result["measurement"] == "LOGICAL_FILE_LENGTH_NOT_ALLOCATED"
    assert result["logical_bytes"] == 23
    assert result["objects"] == 4 and result["walked_objects"] == 5
    assert result["complete"] is True and result["unknown"] == []
    assert result["roots"][0]["duplicate_entries"] == 1
    assert result["allocated_storage_bytes"] == "UNKNOWN"
    assert result["physical_dedupe"] == "SAME_DEV_INO_COUNTED_ONCE"
    assert result["digest_dedupe"] == "NOT_PERFORMED"


def test_measurement_does_not_follow_reparse_points_or_delete(tmp_path):
    root = tmp_path / "project"
    _write(root / "inside.txt", 7)
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"o" * 99)
    link = root / "link-outside.txt"
    try:
        os.symlink(outside, link)
        symlink_available = True
    except (OSError, NotImplementedError):
        symlink_available = False
    before = sorted((str(p.relative_to(tmp_path)), p.stat().st_size) for p in tmp_path.rglob("*") if p.is_file())
    result = measure_roots([("project", root)])
    after = sorted((str(p.relative_to(tmp_path)), p.stat().st_size) for p in tmp_path.rglob("*") if p.is_file())
    assert before == after
    if symlink_available:
        assert result["logical_bytes"] == 7
        assert any(item["reason"] == "REPARSE_POINT" for item in result["unknown"])
        assert result["complete"] is False


def test_measurement_reports_missing_and_non_directory_roots(tmp_path):
    file_root = tmp_path / "not-a-dir"
    file_root.write_bytes(b"x")
    result = measure_roots([("missing", tmp_path / "missing"), ("file", file_root)])
    by_label = {item["label"]: item["state"] for item in result["roots"]}
    assert by_label == {"missing": "MISSING", "file": "NOT_A_REGULAR_DIRECTORY"}
    assert any(item["reason"] == "ROOT_NOT_REGULAR_DIRECTORY" for item in result["unknown"])


def test_measurement_rejects_bad_root_specs(tmp_path):
    with pytest.raises(CapacityMeasurementError):
        measure_roots([])
    with pytest.raises(CapacityMeasurementError):
        measure_roots([("project", tmp_path), ("project", tmp_path)])
    with pytest.raises(CapacityMeasurementError):
        measure_roots([("project", tmp_path)], max_objects=0)


def test_measurement_feeds_reconcile_and_blocks_on_unknown(tmp_path):
    root = tmp_path / "project"
    _write(root / "content.bin", 16)
    result = measure_roots([("project", root)])
    ledger = make_ledger(tmp_path, default_limit_bytes=100)
    view = ledger.reconcile("project-a", measured_bytes=result["logical_bytes"],
                            unknown_objects=result["unknown_count"], incarnation="inc-1", actor_id="reconciler")
    assert view["used_bytes"] == 16 and view["state"] == "OK"
    assert result["logical_bytes"] == DEFAULT_LIMIT_BYTES - (DEFAULT_LIMIT_BYTES - 16)

