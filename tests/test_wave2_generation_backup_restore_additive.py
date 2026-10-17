"""Generic File save lock housekeeping coexists with original offline recovery.

This proves exact bytes and a fresh repository read, not application readiness,
Director publication authority, model execution, or PostgreSQL recovery.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from app.backup_restore import backup_directory, restore_directory, verify_restored_directory
from app.repositories.generation_repository import GenerationRepository


def test_generic_generation_save_backup_restore_verify_and_fresh_read(tmp_path):
    source = tmp_path / "source"
    data = source / "novel_data"
    repository = GenerationRepository(data)
    record = {"id": "legacy-job-wave2", "status": "COMPLETED", "output": "原始记录 🌱"}
    repository.save(record)
    assert repository.get(record["id"]) == record

    job = data / "runtime/jobs" / f"{record['id']}.json"
    key = "generation-write:" + os.path.normcase(str(job.resolve()))
    lock = job.parent / ".workspace-mutation-locks" / (hashlib.sha256(key.encode("utf-8")).hexdigest() + ".lock")
    assert lock.is_file()
    # The original backup retains actual lock housekeeping; do not strip or
    # manufacture files to make the strict restored-tree verifier succeed.
    backup, target = tmp_path / "backup", tmp_path / "restored"
    manifest = backup_directory(source, backup, app_version="0.7.0", offline_confirmed=True)
    members = {item["path"]: item for item in manifest["checksum"]}
    assert job.relative_to(source).as_posix() in members
    assert lock.relative_to(source).as_posix() in members
    restore_directory(backup, target)

    def snapshot(root: Path):
        return {p.relative_to(root).as_posix(): ("directory",) if p.is_dir() else ("file", p.read_bytes())
                for p in root.rglob("*")}

    roots = (source, backup, target)
    before = [snapshot(root) for root in roots]
    result = verify_restored_directory(backup, target, offline_confirmed=True)
    assert result == {
        "status": "file_bytes_verified",
        "verified_file_count": len(members),
        "verified_byte_count": sum(item["size"] for item in members.values()),
        "application_compatibility": "not_verified",
        "database_validation": "not_applicable",
        "switch_performed": False,
    }
    assert [snapshot(root) for root in roots] == before
    reopened = GenerationRepository(target / "novel_data")
    assert reopened.get(record["id"]) == record
    assert (target / job.relative_to(source)).read_bytes() == job.read_bytes()
    assert (target / lock.relative_to(source)).read_bytes() == lock.read_bytes()
    assert [snapshot(root) for root in roots] == before
