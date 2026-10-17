"""Offline, read-only verification of the original R2 restore output."""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

import app.backup_restore as recovery
from test_r2_backup_restore import fixture_tree


@pytest.fixture
def restored(tmp_path):
    source, values = fixture_tree(tmp_path)
    backup, target = tmp_path / "backup", tmp_path / "target"
    recovery.backup_directory(source, backup, app_version="0.7.0", offline_confirmed=True)
    recovery.restore_directory(backup, target)
    return source, backup, target, values


def verify(backup, target):
    return recovery.verify_restored_directory(backup, target, offline_confirmed=True)


def snapshot(*roots):
    return [{p.relative_to(root).as_posix(): ("link", os.readlink(p)) if p.is_symlink()
             else ("directory",) if p.is_dir() else ("file", p.read_bytes())
             for p in root.rglob("*")} for root in roots]


def test_actual_cli_roundtrip_read_only_and_no_application_startup(restored, tmp_path):
    source, backup, target, values = restored
    before = snapshot(source, backup, target)
    # sitecustomize observes the actual -m command at interpreter shutdown;
    # the test process's normal app fixtures are separate from this interpreter.
    probe = tmp_path / "probe"
    probe.mkdir()
    (probe / "sitecustomize.py").write_text(
        "import atexit, sys\n"
        "def check():\n"
        "    assert not {'app.main', 'app.api', 'app.runtime', 'psycopg'} & set(sys.modules)\n"
        "    print('CLI_NO_APP_STARTUP', file=sys.stderr)\n"
        "atexit.register(check)\n")
    environment = {**os.environ, "PYTHONPATH": str(probe) + os.pathsep + str(Path.cwd()),
                   "PYTHONDONTWRITEBYTECODE": "1"}
    command = [sys.executable, "-m", "app.backup_restore", "verify-restored",
               "--backup", str(backup), "--destination", str(target), "--offline-confirmed"]
    result = subprocess.run(command, capture_output=True, text=True, env=environment)
    assert result.returncode == 0, result.stderr
    assert result.stderr.strip() == "CLI_NO_APP_STARTUP"
    assert json.loads(result.stdout) == {
        "status": "file_bytes_verified", "verified_file_count": len(values),
        "verified_byte_count": sum(map(len, values.values())),
        "application_compatibility": "not_verified", "database_validation": "not_applicable",
        "switch_performed": False}
    assert snapshot(source, backup, target) == before
    (target / "novel_data/assets/shot.bin").write_bytes(b"changed")
    before = snapshot(source, backup, target)
    result = subprocess.run(command, capture_output=True, text=True, env=environment)
    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "RESTORED_CONTENT_MISMATCH\nCLI_NO_APP_STARTUP\n"
    assert snapshot(source, backup, target) == before


@pytest.mark.parametrize("mutation,code", [
    ("missing", "RESTORED_MEMBERSHIP_MISMATCH"),
    ("changed", "RESTORED_CONTENT_MISMATCH"),
    ("extra", "RESTORED_MEMBERSHIP_MISMATCH"),
    ("empty-directory", "RESTORED_MEMBERSHIP_MISMATCH"),
    ("incomplete", "RESTORED_INCOMPLETE"),
    ("backup-incomplete", "RESTORED_INCOMPLETE"),
    ("receipt-missing", "RESTORED_MEMBERSHIP_MISMATCH"),
    ("receipt-json", "RESTORED_INPUT_INVALID_OR_UNREADABLE"),
    ("receipt-extra-key", "RESTORED_RECEIPT_INVALID"),
    ("receipt-count", "RESTORED_RECEIPT_INVALID"),
    ("receipt-version", "RESTORED_RECEIPT_INVALID"),
    ("receipt-app", "RESTORED_RECEIPT_INVALID"),
    ("receipt-database", "RESTORED_RECEIPT_INVALID"),
    ("receipt-time", "RESTORED_RECEIPT_INVALID"),
    ("receipt-naive-time", "RESTORED_RECEIPT_INVALID"),
])
def test_failures_are_read_only_and_redacted(restored, mutation, code):
    source, backup, target, _ = restored
    member = target / "novel_data/assets/shot.bin"
    receipt = target / "restore-receipt.json"
    sentinel = "SENTINEL_PRIVATE_CONTENT_OR_FILENAME"
    if mutation == "missing": member.unlink()
    elif mutation == "changed": member.write_text(sentinel)
    elif mutation == "extra": (target / sentinel).write_text(sentinel)
    elif mutation == "empty-directory": (target / sentinel).mkdir()
    elif mutation == "incomplete": (target / ".restore-incomplete").write_text(sentinel)
    elif mutation == "backup-incomplete": (backup / ".incomplete").write_text(sentinel)
    elif mutation == "receipt-missing": receipt.unlink()
    elif mutation == "receipt-json": receipt.write_text(sentinel)
    else:
        value = json.loads(receipt.read_text())
        field, replacement = {
            "receipt-extra-key": (sentinel, sentinel), "receipt-count": ("file_count", True),
            "receipt-version": ("backup_version", sentinel), "receipt-app": ("app_version", sentinel),
            "receipt-database": ("database_restored", True),
            "receipt-time": ("restored_at", sentinel),
            "receipt-naive-time": ("restored_at", "2026-10-17T10:00:00"),
        }[mutation]
        value[field] = replacement
        receipt.write_text(json.dumps(value))
    before = snapshot(source, backup, target)
    with pytest.raises(recovery.BackupError) as error:
        verify(backup, target)
    assert str(error.value) == code
    assert snapshot(source, backup, target) == before


@pytest.mark.parametrize("location", ["target-file", "target-directory", "receipt", "backup-manifest", "backup-file", "root", "ancestor", "dangling"])
def test_links_are_rejected_without_opening_targets(restored, tmp_path, monkeypatch, location):
    _, backup, target, _ = restored
    outside = tmp_path / "private"
    outside.write_text("SENTINEL_CREDENTIAL")
    if location == "root":
        link = tmp_path / "linked-target"; link.symlink_to(target, target_is_directory=True); target = link
    elif location == "ancestor":
        link = tmp_path / "linked-parent"; link.symlink_to(tmp_path, target_is_directory=True); target = link / "target"
    else:
        path = {"target-file": target / "novel_data/assets/shot.bin",
                "target-directory": target / "novel_data/linked",
                "receipt": target / "restore-receipt.json", "backup-manifest": backup / "manifest.json",
                "backup-file": backup / "novel_data/assets/shot.bin", "dangling": target / "dangling"}[location]
        if path.exists(): path.unlink()
        linked = tmp_path / "absent" if location == "dangling" else tmp_path if location == "target-directory" else outside
        path.symlink_to(linked, target_is_directory=location == "target-directory")
    def forbidden(*args, **kwargs):
        pytest.fail("No content may be opened before symlink preflight succeeds")
    monkeypatch.setattr(Path, "open", forbidden)
    with pytest.raises(recovery.BackupError, match="^RESTORED_UNSAFE_(ROOT|ENTRY)$"):
        verify(backup, target)


@pytest.mark.parametrize("root_name", ["backup", "target"])
def test_unexpected_credentials_never_opened(restored, monkeypatch, root_name):
    _, backup, target, _ = restored
    private = (backup if root_name == "backup" else target) / "config/.env"
    private.write_text("SENTINEL_CREDENTIAL")
    original = Path.open
    def guarded(path, *args, **kwargs):
        assert path != private
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", guarded)
    with pytest.raises(recovery.BackupError, match="^RESTORED_(BACKUP_INVALID|MEMBERSHIP_MISMATCH)$"):
        verify(backup, target)


@pytest.mark.parametrize("bad", ["../SENTINEL", "/SENTINEL", "config/.env", "novel_data\\SENTINEL", "novel_data/SENTINEL\x00"])
def test_malformed_manifest_is_redacted(restored, bad):
    _, backup, target, _ = restored
    path = backup / "manifest.json"
    value = json.loads(path.read_text()); value["checksum"][0]["path"] = bad
    path.write_text(json.dumps(value))
    with pytest.raises(recovery.BackupError, match="^RESTORED_BACKUP_INVALID$"):
        verify(backup, target)


def test_offline_and_overlap_required(restored):
    _, backup, target, _ = restored
    with pytest.raises(recovery.BackupError, match="^RESTORED_OFFLINE_REQUIRED$"):
        recovery.verify_restored_directory(backup, target)
    with pytest.raises(recovery.BackupError, match="^RESTORED_OVERLAPPING_ROOTS$"):
        verify(backup, backup)


@pytest.mark.parametrize("constant,limit", [("RESTORED_MAX_ENTRIES", 2), ("RESTORED_MAX_DEPTH", 1),
                                           ("RESTORED_MANIFEST_BYTES", 8), ("RESTORED_RECEIPT_BYTES", 8)])
def test_bounds_fail_closed(restored, monkeypatch, constant, limit):
    _, backup, target, _ = restored
    monkeypatch.setattr(recovery, constant, limit)
    with pytest.raises(recovery.BackupError, match="^RESTORED_LIMIT_EXCEEDED$"):
        verify(backup, target)


def test_mutation_during_hash_is_detected(restored, monkeypatch):
    _, backup, target, _ = restored
    original = recovery._hash
    changed = False
    def mutate(path):
        nonlocal changed
        digest = original(path)
        if path.is_relative_to(target) and not changed:
            changed = True
            (target / "late-file").write_text("SENTINEL")
        return digest
    monkeypatch.setattr(recovery, "_hash", mutate)
    with pytest.raises(recovery.BackupError, match="^RESTORED_TREE_CHANGED$"):
        verify(backup, target)


def test_postgres_sidecars_never_claim_database_validation(restored):
    _, backup, target, _ = restored
    # Synthetic opaque dump; no PostgreSQL connection, restore or execution.
    dump = b"synthetic-not-a-real-pg-dump"
    (backup / "database.dump").write_bytes(dump)
    path = backup / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["checksum"].append({"path": "database.dump", "size": len(dump), "sha256": hashlib.sha256(dump).hexdigest()})
    manifest["file_count"] += 1; manifest["database_included"] = True
    path.write_text(json.dumps(manifest))
    path = target / "restore-receipt.json"
    receipt = json.loads(path.read_text()); receipt["file_count"] += 1; receipt["database_restored"] = True
    path.write_text(json.dumps(receipt))
    result = verify(backup, target)
    assert result["database_validation"] == "unsupported"
    assert result["application_compatibility"] == "not_verified"
    assert not result["switch_performed"]
    assert result["verified_file_count"] == manifest["file_count"] - 1


def test_original_asset_library_reopens_verified_restore(tmp_path):
    from app.services.asset_library_service import AssetLibraryService
    source = tmp_path / "source"; source.mkdir()
    assets = AssetLibraryService(source / "novel_data")
    data = b"original-asset-bytes"
    asset = assets.create("book", "reference.png", base64.b64encode(data).decode(), "image/png")
    history = source / "novel_data/novels/book/history/chapter-0001/v1.json"
    history.parent.mkdir(parents=True); history.write_text('{"version":1,"text":"Original"}')
    backup, target = tmp_path / "backup", tmp_path / "target"
    recovery.backup_directory(source, backup, app_version="0.7.0", offline_confirmed=True)
    recovery.restore_directory(backup, target)
    assert verify(backup, target)["status"] == "file_bytes_verified"
    reopened = AssetLibraryService(target / "novel_data")
    assert reopened.content(asset["id"]) == data
    assert (target / history.relative_to(source)).read_bytes() == history.read_bytes()


def test_manifest_depth_bounded_before_parent_expansion(restored, monkeypatch):
    _, backup, target, _ = restored
    path = backup / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["checksum"][0]["path"] = "novel_data/" + "a/" * 64 + "leaf"
    path.write_text(json.dumps(manifest))
    monkeypatch.setattr(recovery, "_member", lambda _: pytest.fail("Path parsing must be bounded first"))
    with pytest.raises(recovery.BackupError, match="^RESTORED_LIMIT_EXCEEDED$"):
        verify(backup, target)


def test_manifest_entry_count_bounded(restored, monkeypatch):
    _, backup, target, _ = restored
    path = backup / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["checksum"] = manifest["checksum"] * 20
    manifest["file_count"] = len(manifest["checksum"])
    path.write_text(json.dumps(manifest))
    monkeypatch.setattr(recovery, "RESTORED_MAX_ENTRIES", 100)
    with pytest.raises(recovery.BackupError, match="^RESTORED_LIMIT_EXCEEDED$"):
        verify(backup, target)


@pytest.mark.parametrize("kind", ["fifo", "hardlink"])
def test_special_files_and_hardlinks_rejected_before_content_reads(restored, tmp_path, monkeypatch, kind):
    _, backup, target, _ = restored
    path = target / "unsafe"
    if kind == "fifo":
        if not hasattr(os, "mkfifo"): pytest.skip("FIFO creation unavailable")
        os.mkfifo(path)
    else:
        outside = tmp_path / "private"; outside.write_text("SENTINEL")
        os.link(outside, path)
    monkeypatch.setattr(Path, "open", lambda *a, **k: pytest.fail("Unsafe tree must not open content"))
    with pytest.raises(recovery.BackupError, match="^RESTORED_UNSAFE_ENTRY$"):
        verify(backup, target)


def test_original_backup_credential_guard_is_redacted(restored):
    _, backup, target, _ = restored
    relative = "config/model_manifest.json"
    data = b'{"api_key":"SENTINEL_PRIVATE_CREDENTIAL"}'
    (backup / relative).write_bytes(data); (target / relative).write_bytes(data)
    path = backup / "manifest.json"; manifest = json.loads(path.read_text())
    entry = next(item for item in manifest["checksum"] if item["path"] == relative)
    entry.update(size=len(data), sha256=hashlib.sha256(data).hexdigest())
    path.write_text(json.dumps(manifest))
    with pytest.raises(recovery.BackupError, match="^RESTORED_BACKUP_INVALID$"):
        verify(backup, target)


@pytest.mark.parametrize("root_name,code", [("target", "RESTORED_CONTENT_MISMATCH"),
                                           ("backup", "RESTORED_BACKUP_INVALID")])
def test_same_size_corruption_checks_hash(restored, root_name, code):
    source, backup, target, _ = restored
    path = (target if root_name == "target" else backup) / "novel_data/assets/shot.bin"
    original = path.read_bytes()
    path.write_bytes(bytes([original[0] ^ 1]) + original[1:])
    before = snapshot(source, backup, target)
    with pytest.raises(recovery.BackupError) as error:
        verify(backup, target)
    assert str(error.value) == code
    assert snapshot(source, backup, target) == before


@pytest.mark.parametrize("alias", ["novel_data//assets/shot.bin", "novel_data/./assets/shot.bin",
                                  "novel_data/assets/shot.bin"])
def test_manifest_alias_and_duplicate_rejected(restored, alias):
    _, backup, target, _ = restored
    path = backup / "manifest.json"; manifest = json.loads(path.read_text())
    entry = next(item for item in manifest["checksum"] if item["path"] == "novel_data/assets/shot.bin")
    manifest["checksum"].append({**entry, "path": alias}); manifest["file_count"] += 1
    path.write_text(json.dumps(manifest))
    with pytest.raises(recovery.BackupError, match="^RESTORED_BACKUP_INVALID$"):
        verify(backup, target)


def test_manifest_path_length_bounded_before_parsing(restored, monkeypatch):
    _, backup, target, _ = restored
    path = backup / "manifest.json"; manifest = json.loads(path.read_text())
    manifest["checksum"][0]["path"] = "novel_data/" + "x" * 4096
    path.write_text(json.dumps(manifest))
    monkeypatch.setattr(recovery, "_member", lambda _: pytest.fail("Length must be bounded first"))
    with pytest.raises(recovery.BackupError, match="^RESTORED_LIMIT_EXCEEDED$"):
        verify(backup, target)


def test_manifest_is_read_only_once_with_a_bound(restored, monkeypatch):
    _, backup, target, _ = restored
    original = recovery._restored_json
    reads = []
    def observed(path, limit):
        reads.append((path.name, limit))
        return original(path, limit)
    monkeypatch.setattr(recovery, "_restored_json", observed)
    original_read_text = Path.read_text
    def disallow_manifest_reread(path, *args, **kwargs):
        assert path != backup / "manifest.json"
        return original_read_text(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", disallow_manifest_reread)
    verify(backup, target)
    assert [item for item in reads if item[0] in {"manifest.json", "restore-receipt.json"}] == [
        ("manifest.json", recovery.RESTORED_MANIFEST_BYTES),
        ("restore-receipt.json", recovery.RESTORED_RECEIPT_BYTES)]


def test_expected_json_credential_read_is_bounded_and_old_default_unchanged(restored, monkeypatch):
    _, backup, target, _ = restored
    monkeypatch.setattr(recovery, "RESTORED_JSON_BYTES", 8)
    original = recovery._restored_json
    observed = []
    def checked(path, limit):
        if path.suffix == ".json" and path.name not in {"manifest.json", "restore-receipt.json"}:
            observed.append(limit)
        return original(path, limit)
    monkeypatch.setattr(recovery, "_restored_json", checked)
    with pytest.raises(recovery.BackupError, match="^RESTORED_LIMIT_EXCEEDED$"):
        verify(backup, target)
    assert observed == [8]
    assert recovery.verify_backup(backup)["backup_version"] == recovery.FORMAT_VERSION


def test_aggregate_manifest_members_stop_before_over_limit_expansion(monkeypatch):
    monkeypatch.setattr(recovery, "RESTORED_MAX_ENTRIES", 3)
    def members():
        yield "a/b/c"
        pytest.fail("Expansion must stop in the first path before consuming more members")
    with pytest.raises(recovery.BackupError, match="^RESTORED_LIMIT_EXCEEDED$"):
        recovery._restored_members(members())


def test_aggregate_manifest_members_count_shared_parents_once(monkeypatch):
    monkeypatch.setattr(recovery, "RESTORED_MAX_ENTRIES", 4)
    assert recovery._restored_members({"novel_data/a", "novel_data/b"}) == {
        "", "novel_data", "novel_data/a", "novel_data/b"}
