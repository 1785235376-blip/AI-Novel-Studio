"""Real File index durability checks in fresh Python processes.

The parent fixture owns temporary source data. Every index query below executes
in a distinct process and reacquires the real CreativeProjectStore project-owner
lease and AssetLibraryService mutation lease. This is index lifecycle coverage;
the mounted-route authority and response checks live in the Studio query tests.
"""
import hashlib
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import time
from uuid import uuid4

import pytest

from test_studio_asset_query import rig  # noqa: F401 -- shared real File fixture


pytestmark = pytest.mark.file_backend_only


WORKER = r'''
import json
import os
from pathlib import Path
import sys
import threading
import sqlite3

from app.experimental.store import ExperimentalStore
from app.creative.project_store import CreativeProjectStore
from app.services.asset_library_service import AssetLibraryService
from app.services.asset_query_index import (
    AssetQueryBudgetExceeded, AssetQueryChanged, AssetQueryUnavailable,
    FileAssetQueryIndex,
)

root, nid, options = Path(sys.argv[1]), sys.argv[2], json.loads(sys.argv[3])
assets = AssetLibraryService(root)
store = CreativeProjectStore(ExperimentalStore(root, "file", ""))
scope = {"mode": "local", "novel_id": nid}
for key, value in options.get("limits", {}).items():
    setattr(FileAssetQueryIndex, key, value)

class ControlledIndex(FileAssetQueryIndex):
    def _rebuild_checkpoint(self, phase):
        if phase != options.get("phase"):
            return
        if options.get("change_source"):
            path = assets.root / (options["change_source"] + ".json")
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["filename"] = "changed-during-build.png"
            path.write_text(json.dumps(payload), encoding="utf-8")
        elif options.get("marker"):
            Path(options["marker"]).write_text(phase, encoding="ascii")
            # The parent sends SIGKILL only after the checkpoint is on disk.
            threading.Event().wait(30)
            raise RuntimeError("parent did not kill the paused worker")

reads = 0
def load(asset_id):
    global reads
    reads += 1
    return assets._load(asset_id)

try:
    with assets.project_scope(nid, None, lambda: store.owner_lease(nid),
                              scope_key=store.key(nid, scope)):
        index = ControlledIndex(assets.root)
        snapshot = index.snapshot(load)
        if options.get("fill_after_snapshot"):
            for number in range(options["fill_after_snapshot"]):
                (index.directory / ("retained-" + str(number))).write_bytes(b"retained evidence")
            snapshot = index.snapshot(load)
        if options.get("live_sidecar"):
            mode = options["live_sidecar"]
            if mode == "wal":
                connection = sqlite3.connect(index.path)
                connection.execute("PRAGMA journal_mode=WAL")
                connection.close()
                # Cache the completed WAL-mode main file before another
                # connection creates a real WAL without changing that identity.
                snapshot = index.snapshot(load)
            previous = index.path.stat()
            writer = sqlite3.connect(index.path)
            try:
                writer.execute("PRAGMA wal_autocheckpoint=0")
                writer.execute("BEGIN IMMEDIATE")
                writer.execute("UPDATE sources SET filename_folded='hidden-in-live-sidecar'")
                if mode == "wal":
                    writer.commit()
                    assert Path(str(index.path) + "-wal").stat().st_size > 0
                    assert Path(str(index.path) + "-shm").exists()
                else:
                    assert Path(str(index.path) + "-journal").stat().st_size > 0
                current = index.path.stat()
                for field in ("st_ino", "st_size", "st_mtime_ns", "st_ctime_ns"):
                    assert getattr(previous, field) == getattr(current, field), field
                # A warm instance must reject sidecars before consuming cached
                # columns, even when the canonical file identity is unchanged.
                snapshot = index.snapshot(load)
                raise AssertionError("live sidecar incorrectly accepted")
            finally:
                if mode == "wal":
                    writer.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                else:
                    writer.rollback()
                writer.close()
        rows = []
        for candidate in index.iter_candidates(
                snapshot, nid, assets._scope.binding,
                keyword=options.get("keyword", ""), kind=options.get("kind")):
            try:
                # The index is only a candidate source; the real owner remains
                # responsible for existence, project binding and visibility.
                row = assets.get(candidate["id"])
            except (ValueError, FileNotFoundError):
                continue
            rows.append({key: row[key] for key in ("id", "filename", "kind")})
        if options.get("change_after_read"):
            path = assets.root / (options["change_after_read"] + ".json")
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["filename"] = "changed-after-read.png"
            path.write_text(json.dumps(payload), encoding="utf-8")
        index.verify(snapshot)
        result = {"pid": os.getpid(), "rows": rows, "revision": snapshot.revision,
                  "build_metadata_reads": reads}
except (AssetQueryBudgetExceeded, AssetQueryChanged, AssetQueryUnavailable) as error:
    # Publish no partial rows, counts or source identifiers on failure.
    result = {"pid": os.getpid(), "error": str(error)}
print("INDEX_RESULT=" + json.dumps(result, sort_keys=True), flush=True)
'''


def worker_args(rig, options=None):
    environment = os.environ.copy()
    environment.update(NOVEL_DATA_PATH=str(rig.root), STORAGE_BACKEND="file",
                       MOCK_PROVIDER="true", ENABLE_CLOUD="false",
                       CREDENTIAL_VAULT_BACKEND="memory",
                       EXPERIMENTAL_FEATURES="narrative_production_v2,asset_lineage_v2",
                       LOCALAPPDATA=str(rig.root / "process-appdata"))
    environment.pop("V1_ACCEPTANCE_MODE", None)
    return {"args": [sys.executable, "-c", WORKER, str(rig.root), rig.nid,
                     json.dumps(options or {})],
            "cwd": str(Path(__file__).resolve().parents[1]), "env": environment,
            "text": True, "stdout": subprocess.PIPE, "stderr": subprocess.PIPE}


def query_process(rig, **options):
    completed = subprocess.run(**worker_args(rig, options), timeout=30)
    assert completed.returncode == 0, completed.stderr
    lines = [line.removeprefix("INDEX_RESULT=") for line in completed.stdout.splitlines()
             if line.startswith("INDEX_RESULT=")]
    assert len(lines) == 1, completed.stdout
    result = json.loads(lines[0])
    assert result["pid"] != os.getpid()
    return result


def index_path(rig):
    return rig.assets.root / ".asset-query-index" / "index.sqlite3"


def file_digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_snapshot(rig):
    result = {}
    for path in rig.assets.root.iterdir():
        if path.suffix not in {".json", ".bin"}:
            continue
        info = path.stat()
        result[path.name] = (info.st_ino, info.st_size, info.st_mtime_ns, file_digest(path))
    return result


def atomic_metadata(rig, row, **updates):
    # Filename/kind currently have no general public update method. Exercise
    # the existing owner's atomic metadata primitive under its original lease.
    with rig.workspace._asset_scope(rig.nid, rig.scope):
        current = rig.assets.get(row["id"])
        current.update(updates)
        rig.assets._write_meta(current)


def test_fresh_process_reopens_persistent_index_without_source_rebuild(rig):
    expected = [rig.seed("second.png", stamp="2026-02-01"),
                rig.seed("first.png", stamp="2026-01-01")]
    before = source_snapshot(rig)
    cold = query_process(rig)
    reopened = query_process(rig)
    assert cold["pid"] != reopened["pid"]
    assert cold["build_metadata_reads"] == 2
    assert reopened["build_metadata_reads"] == 0
    assert reopened["revision"] == cold["revision"]
    assert [row["id"] for row in reopened["rows"]] == [row["id"] for row in reversed(expected)]
    assert reopened["rows"] == cold["rows"]
    assert source_snapshot(rig) == before
    if os.name != "nt":
        assert index_path(rig).stat().st_mode & 0o777 == 0o600
        assert index_path(rig).parent.stat().st_mode & 0o777 == 0o700


def test_atomic_insert_rename_type_change_delete_reconciles_in_new_process(rig):
    kept = rig.seed("before.png", stamp="2026-01-01")
    removed = rig.seed("remove.png", stamp="2026-02-01")
    original = query_process(rig)
    atomic_metadata(rig, kept, filename="after.wav", kind="audio")
    with rig.workspace._asset_scope(rig.nid, rig.scope):
        rig.assets.delete(removed["id"])
    added = rig.seed("insert.wav", "audio", stamp="2026-03-01")
    changed = query_process(rig, kind="audio")
    assert changed["revision"] != original["revision"]
    assert changed["build_metadata_reads"] == 3
    assert changed["rows"] == [{"id": kept["id"], "filename": "after.wav", "kind": "audio"},
                               {"id": added["id"], "filename": "insert.wav", "kind": "audio"}]
    assert query_process(rig, keyword="before")["rows"] == []
    assert [row["id"] for row in query_process(rig)["rows"]] == [kept["id"], added["id"]]


def test_in_place_source_edit_is_detected_without_directory_mtime_change(rig):
    saved = rig.seed("before.png")
    original = query_process(rig)
    path = rig.assets.root / (saved["id"] + ".json")
    directory_time = rig.assets.root.stat().st_mtime_ns
    previous_stat = path.stat()
    text = path.read_text(encoding="utf-8")
    assert '"before.png"' in text
    path.write_text(text.replace('"before.png"', '"afters.png"'), encoding="utf-8")
    # Even a writer preserving mtime and file length changes ctime.
    os.utime(path, ns=(previous_stat.st_atime_ns, previous_stat.st_mtime_ns))
    assert path.stat().st_size == previous_stat.st_size
    assert rig.assets.root.stat().st_mtime_ns == directory_time
    reopened = query_process(rig, keyword="afters")
    assert reopened["revision"] != original["revision"]
    assert reopened["build_metadata_reads"] == 1
    assert [row["id"] for row in reopened["rows"]] == [saved["id"]]
    assert query_process(rig, keyword="before")["rows"] == []


@pytest.mark.parametrize("damage", ["missing", "invalid_sqlite", "old_format", "wrong_root", "filter_column", "oversized_cell"])
def test_missing_corrupt_or_incompatible_index_rebuilds_from_real_sources(rig, damage):
    saved = rig.seed("needle.png")
    original = query_process(rig)
    path = index_path(rig)
    cursor_key = path.parent / "cursor.key"
    cursor_key.write_bytes(b"synthetic cursor key preserved by index recovery")
    before = source_snapshot(rig)
    if damage == "missing":
        path.unlink()
    elif damage == "invalid_sqlite":
        path.write_bytes(b"this is not a SQLite database")
    else:
        with sqlite3.connect(path) as connection:
            if damage == "filter_column":
                connection.execute("UPDATE sources SET filename_folded='hidden-by-corruption'")
            elif damage == "oversized_cell":
                connection.execute("UPDATE sources SET payload=?", ("x" * (9 * 1024 * 1024),))
            else:
                key = "format" if damage == "old_format" else "source_root"
                connection.execute("UPDATE metadata SET value=? WHERE key=?", ("incompatible", key))
    recovered = query_process(rig, keyword="needle")
    assert recovered["pid"] != original["pid"]
    assert recovered["build_metadata_reads"] == 1
    assert recovered["revision"] == original["revision"]
    assert [row["id"] for row in recovered["rows"]] == [saved["id"]]
    assert source_snapshot(rig) == before
    assert cursor_key.read_bytes() == b"synthetic cursor key preserved by index recovery"


def kill_at_checkpoint(rig, phase):
    marker = rig.root / ("checkpoint-" + phase + "-" + uuid4().hex)
    process = subprocess.Popen(**worker_args(rig, {"phase": phase, "marker": str(marker)}))
    try:
        deadline = time.monotonic() + 15
        while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert marker.exists(), "worker did not reach the requested real rebuild checkpoint"
        assert marker.read_text(encoding="ascii") == phase
        process.kill()
        stdout, stderr = process.communicate(timeout=5)
        assert process.returncode == -signal.SIGKILL
        assert "INDEX_RESULT=" not in stdout, (stdout, stderr)
        return process.pid
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=5)


@pytest.mark.skipif(os.name == "nt", reason="SIGKILL recovery contract runs on POSIX")
@pytest.mark.parametrize("phase", ["row", "staged", "committed", "published"])
def test_sigkill_rebuild_keeps_a_complete_committed_database_and_recovers(rig, phase):
    saved = rig.seed("old.png")
    original = query_process(rig)
    old_digest = file_digest(index_path(rig))
    atomic_metadata(rig, saved, filename="new.png")
    added = rig.seed("added.png")
    before = source_snapshot(rig)
    killed_pid = kill_at_checkpoint(rig, phase)
    if phase != "published":
        assert file_digest(index_path(rig)) == old_digest
        abandoned = list(index_path(rig).parent.glob("building-*.sqlite3"))
        assert abandoned
    else:
        assert file_digest(index_path(rig)) != old_digest
        abandoned = []
    recovered = query_process(rig)
    assert recovered["pid"] not in {killed_pid, original["pid"]}
    assert recovered["revision"] != original["revision"]
    assert {(row["id"], row["filename"]) for row in recovered["rows"]} == {
        (saved["id"], "new.png"), (added["id"], "added.png")}
    assert recovered["build_metadata_reads"] == (0 if phase == "published" else 2)
    assert all(path.exists() for path in abandoned), "recovery must not erase interrupted evidence"
    assert source_snapshot(rig) == before


@pytest.mark.skipif(os.name == "nt", reason="SIGKILL recovery contract runs on POSIX")
def test_first_build_sigkill_recovers_without_a_prior_index(rig):
    saved = rig.seed("first-build.png")
    killed_pid = kill_at_checkpoint(rig, "committed")
    assert not index_path(rig).exists()
    recovered = query_process(rig)
    assert recovered["pid"] != killed_pid
    assert recovered["build_metadata_reads"] == 1
    assert [row["id"] for row in recovered["rows"]] == [saved["id"]]


@pytest.mark.parametrize("stage", ["during_build", "after_read"])
def test_source_changes_are_conflicts_without_partial_results(rig, stage):
    saved = rig.seed("before.png")
    query_process(rig)
    old_digest = file_digest(index_path(rig))
    if stage == "during_build":
        atomic_metadata(rig, saved, filename="trigger-rebuild.png")
        result = query_process(rig, phase="staged", change_source=saved["id"])
    else:
        result = query_process(rig, change_after_read=saved["id"])
    assert set(result) == {"pid", "error"}
    assert result["error"] == "ASSET_QUERY_RESTART_REQUIRED"
    assert file_digest(index_path(rig)) == old_digest
    recovered = query_process(rig)
    expected = "changed-during-build.png" if stage == "during_build" else "changed-after-read.png"
    assert recovered["rows"] == [{"id": saved["id"], "filename": expected, "kind": "image"}]


@pytest.mark.parametrize("limits", [
    {"MAX_METADATA_FILES": 0}, {"MAX_DIRECTORY_ENTRIES": 0},
    {"MAX_METADATA_BYTES": 16}, {"MAX_SOURCE_BYTES": 16},
    {"MAX_INDEX_BYTES": 16}, {"MAX_OPERATION_SECONDS": -1},
])
def test_budget_exhaustion_is_explicit_and_never_returns_partial_success(rig, limits):
    rig.seed("budget.png")
    query_process(rig)
    old_digest = file_digest(index_path(rig))
    before = source_snapshot(rig)
    result = query_process(rig, limits=limits)
    assert set(result) == {"pid", "error"}
    assert result["error"] == "ASSET_QUERY_BUDGET_EXCEEDED"
    assert file_digest(index_path(rig)) == old_digest
    assert source_snapshot(rig) == before


@pytest.mark.parametrize("mode", ["wal", "journal"])
def test_live_sqlite_sidecar_is_rejected_by_an_unchanged_warm_identity(rig, mode):
    saved = rig.seed("needle.png")
    query_process(rig)
    before = source_snapshot(rig)
    denied = query_process(rig, live_sidecar=mode, keyword="needle")
    assert set(denied) == {"pid", "error"}
    assert denied["error"] == "ASSET_QUERY_INDEX_UNAVAILABLE"
    assert not any(Path(str(index_path(rig)) + suffix).exists()
                   for suffix in ("-wal", "-shm", "-journal"))
    recovered = query_process(rig, keyword="needle")
    assert [row["id"] for row in recovered["rows"]] == [saved["id"]]
    # WAL committed damage is detected and rebuilt after its writer closes;
    # a rolled-back DELETE journal leaves the original valid index reusable.
    assert recovered["build_metadata_reads"] == (1 if mode == "wal" else 0)
    assert source_snapshot(rig) == before


@pytest.mark.parametrize("boundary", ["hot_entries", "directory_bytes", "cursor_reservation",
                                      "rebuild_entries", "rebuild_bytes", "within_room"])
def test_derived_directory_budgets_preserve_sources_and_retained_files(rig, boundary):
    saved = rig.seed("before.png")
    query_process(rig)
    path = index_path(rig)
    old_digest = file_digest(path)
    retained = path.parent / "retained-build-evidence"
    retained.write_bytes(b"evidence" * 8)
    retained_digest = file_digest(retained)
    usage = sum(entry.stat().st_size for entry in path.parent.iterdir())
    # Missing cursor.key and cursor.identity reserve 32 + 128 bytes, two names.
    index_cap = max(path.stat().st_size, 64 * 1024)
    options = {}
    if boundary == "hot_entries":
        limits = {"MAX_INDEX_DIRECTORY_ENTRIES": 5}
        options["fill_after_snapshot"] = 2
    elif boundary == "directory_bytes":
        limits = {"MAX_INDEX_DIRECTORY_BYTES": usage + 159}
    elif boundary == "cursor_reservation":
        limits = {"MAX_INDEX_DIRECTORY_ENTRIES": 3}
    else:
        atomic_metadata(rig, saved, filename="after.png")
        limits = {"MAX_INDEX_BYTES": index_cap, "MAX_INDEX_JOURNAL_HEADROOM_BYTES": 4096}
        if boundary == "rebuild_entries":
            limits["MAX_INDEX_DIRECTORY_ENTRIES"] = 5
        else:
            limits["MAX_INDEX_DIRECTORY_BYTES"] = usage + 160 + index_cap * 2 + 4096
            limits["MAX_INDEX_DIRECTORY_ENTRIES"] = 6
            if boundary == "rebuild_bytes":
                limits["MAX_INDEX_DIRECTORY_BYTES"] -= 1
    before = source_snapshot(rig)
    result = query_process(rig, limits=limits, **options)
    if boundary == "within_room":
        assert result["rows"] == [{"id": saved["id"], "filename": "after.png", "kind": "image"}]
        assert result["build_metadata_reads"] == 1
    else:
        assert set(result) == {"pid", "error"}
        assert result["error"] == "ASSET_QUERY_BUDGET_EXCEEDED"
        assert file_digest(path) == old_digest
    assert retained.exists() and file_digest(retained) == retained_digest
    assert source_snapshot(rig) == before


@pytest.mark.skipif(os.name == "nt", reason="SIGKILL recovery contract runs on POSIX")
def test_repeated_sigkill_evidence_consumes_budget_without_deleting_key_or_old_index(rig):
    saved = rig.seed("before.png")
    query_process(rig)
    path = index_path(rig)
    old_digest = file_digest(path)
    key = path.parent / "cursor.key"
    identity = path.parent / "cursor.identity"
    key.write_bytes(b"synthetic-secret" * 2)
    identity.write_bytes(b"synthetic identity evidence")
    atomic_metadata(rig, saved, filename="after.png")
    pids = {kill_at_checkpoint(rig, "committed") for _ in range(2)}
    assert len(pids) == 2
    abandoned = list(path.parent.glob("building-*.sqlite3"))
    assert len(abandoned) == 2
    evidence = {entry.name: file_digest(entry) for entry in path.parent.iterdir()}
    before = source_snapshot(rig)
    # Five existing artifacts fit; two new staging/journal slots do not fit.
    denied = query_process(rig, limits={"MAX_INDEX_DIRECTORY_ENTRIES": 6})
    assert set(denied) == {"pid", "error"}
    assert denied["error"] == "ASSET_QUERY_BUDGET_EXCEEDED"
    assert {entry.name: file_digest(entry) for entry in path.parent.iterdir()} == evidence
    assert file_digest(path) == old_digest
    recovered = query_process(rig, limits={"MAX_INDEX_DIRECTORY_ENTRIES": 7})
    assert recovered["rows"] == [{"id": saved["id"], "filename": "after.png", "kind": "image"}]
    for entry in [key, identity, *abandoned]:
        assert file_digest(entry) == evidence[entry.name]
    assert source_snapshot(rig) == before


def test_sqlite_page_growth_cap_is_a_budget_failure_with_old_artifact_preserved(rig):
    saved = rig.seed("page-cap.png")
    query_process(rig)
    path = index_path(rig)
    assert path.stat().st_size < 64 * 1024
    old_digest = file_digest(path)
    with rig.workspace._asset_scope(rig.nid, rig.scope):
        rig.assets.update_metadata(saved["id"], {"parameters": {"synthetic": "x" * (48 * 1024)}})
    before = source_snapshot(rig)
    denied = query_process(rig, limits={"MAX_INDEX_BYTES": 64 * 1024})
    assert set(denied) == {"pid", "error"}
    assert denied["error"] == "ASSET_QUERY_BUDGET_EXCEEDED"
    assert file_digest(path) == old_digest
    assert not list(path.parent.glob("building-*.sqlite3"))
    recovered = query_process(rig)
    assert [row["id"] for row in recovered["rows"]] == [saved["id"]]
    assert source_snapshot(rig) == before
