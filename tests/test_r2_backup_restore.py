from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from app.backup_restore import BackupError, backup_directory, restore_directory, verify_backup


def fixture_tree(tmp_path):
    source = tmp_path / "source"
    values = {"novel_data/novels/book/novel.json":b'{"id":"book","privacy_level":"LOCAL_ONLY"}',
              "novel_data/novels/book/chapters/chapter-0001.md":"# 合成正文\n\nOriginal text".encode(),
              "novel_data/novels/book/history/chapter-0001/v1.json":b'{"version":1}',
              "novel_data/assets/shot.bin":b"synthetic-asset\x00\x01",
              "novel_data/export_jobs/job.json":b'{"id":"job","snapshot_id":"snapshot","project_id":"book"}',
              "novel_data/workspaces/membership.json":b'{"user_id":"synthetic-user","role":"owner"}',
              "config/model_manifest.json":b'{"model":"local","configured":false}',
              "database/migrations/001.sql":b'SELECT 1;', "prompts/writer.txt":b'Write', "workflows/writing.json":b'{}'}
    for name, value in values.items():
        path = source / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(value)
    return source, values


def backup(source, destination, **kwargs):
    return backup_directory(source, destination, app_version="0.7.0", offline_confirmed=True, **kwargs)


def test_roundtrip_all_assets_history_permissions_and_task_refs(tmp_path):
    source, values = fixture_tree(tmp_path)
    saved = tmp_path / "backup"; target = tmp_path / "new-instance"
    manifest = backup(source,saved)
    assert manifest["file_count"] == len(values)
    result = restore_directory(saved,target)
    assert result["file_count"] == len(values)
    for relative, contents in values.items(): assert (target/relative).read_bytes() == contents
    assert not (target/".restore-incomplete").exists()
    # Re-open and independently hash-verify using a fresh interpreter.
    result = subprocess.run([sys.executable,"-m","app.backup_restore","verify","--backup",str(saved)], capture_output=True,text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["file_count"] == len(values)


def test_existing_target_even_empty_is_never_overwritten(tmp_path):
    source, _ = fixture_tree(tmp_path); saved=tmp_path/"backup"; backup(source,saved)
    target=tmp_path/"existing"; target.mkdir()
    with pytest.raises(BackupError,match="already exist"): restore_directory(saved,target)
    with pytest.raises(BackupError,match="already exist"): backup(source,saved)
    assert not list(target.iterdir())


def test_corruption_fails_before_creating_target(tmp_path):
    source,_=fixture_tree(tmp_path); saved=tmp_path/"backup"; backup(source,saved)
    (saved/"novel_data/assets/shot.bin").write_bytes(b"corrupt")
    target=tmp_path/"new"
    with pytest.raises(BackupError,match="integrity"):restore_directory(saved,target)
    assert not target.exists()


@pytest.mark.parametrize("path", ["../escape", "/tmp/escape", "C:/escape", "novel_data/../../escape", "novel_data\\escape", "config/.env"])
def test_manifest_traversal_or_credential_member_rejected(tmp_path,path):
    source,_=fixture_tree(tmp_path); saved=tmp_path/"backup"; backup(source,saved)
    manifest=json.loads((saved/"manifest.json").read_text()); manifest["checksum"][0]["path"]=path
    (saved/"manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(BackupError):verify_backup(saved)


def test_symlink_and_unlisted_members_rejected(tmp_path):
    source,_=fixture_tree(tmp_path); saved=tmp_path/"backup"; backup(source,saved)
    (saved/"novel_data/link").symlink_to(source/"novel_data",target_is_directory=True)
    with pytest.raises(BackupError,match="Symlink"):verify_backup(saved)
    (saved/"novel_data/link").unlink();(saved/"extra").write_text("injected")
    with pytest.raises(BackupError,match="unlisted"):verify_backup(saved)


def test_credentials_excluded_and_embedded_plaintext_rejected(tmp_path):
    source,_=fixture_tree(tmp_path)
    (source/"config/.env").write_text("API_KEY=SYNTHETIC_DO_NOT_BACKUP")
    (source/"config/key.pem").write_text("SYNTHETIC_DO_NOT_BACKUP")
    backup(source,tmp_path/"safe")
    assert not (tmp_path/"safe/config/.env").exists()
    assert not (tmp_path/"safe/config/key.pem").exists()
    (source/"config/plain.json").write_text('{"provider":{"api_key":"SYNTHETIC_DO_NOT_BACKUP"}}')
    with pytest.raises(BackupError,match="Plaintext credential"):backup(source,tmp_path/"unsafe")
    assert not (tmp_path/"unsafe").exists()


def test_interrupted_backup_or_restore_never_reports_success(tmp_path,monkeypatch):
    import app.backup_restore as module
    source,_=fixture_tree(tmp_path); saved=tmp_path/"backup"; backup(source,saved)
    def fail(*_args): raise OSError("synthetic disk failure")
    monkeypatch.setattr(module.shutil,"copyfile",fail)
    with pytest.raises(OSError):backup(source,tmp_path/"interrupted")
    with pytest.raises(BackupError,match="incomplete"):verify_backup(tmp_path/"interrupted")
    with pytest.raises(OSError):restore_directory(saved,tmp_path/"restore-interrupted")
    assert (tmp_path/"restore-interrupted/.restore-incomplete").exists()
    with pytest.raises(BackupError,match="already exist"):restore_directory(saved,tmp_path/"restore-interrupted")


def test_requires_offline_and_separate_backup_destination(tmp_path):
    source,_=fixture_tree(tmp_path)
    with pytest.raises(BackupError,match="Stop all"):backup_directory(source,tmp_path/"backup",app_version="0.7.0",offline_confirmed=False)
    with pytest.raises(BackupError,match="outside"):backup(source,source/"backup")


def test_actual_external_runtime_data_root_includes_sidecars(tmp_path):
    source,_=fixture_tree(tmp_path); runtime=tmp_path/"UserData/NovelData"; runtime.mkdir(parents=True)
    (runtime/"runtime-sidecar.json").write_text('{"id":"new"}')
    backup(source,tmp_path/"backup",data_directory=runtime)
    assert (tmp_path/"backup/novel_data/runtime-sidecar.json").exists()
    assert not (tmp_path/"backup/novel_data/novels/book").exists()
