"""Independent regression coverage for the durable-identity lock-file boundary.

The stable identity registry serializes read/validate/mutate/persist with a
lock file in the server-owned state directory. Opening that file by ordinary
path follows a replaced entry; this suite binds the fail-closed contract: a
link/reparse-point lock entry, an unreadable lock file, or a file replaced
between inspection and open is an integrity error and no identity data is
written.

Only synthetic temporary directories are used.
"""
from __future__ import annotations

import os
import stat
from types import SimpleNamespace

import pytest

from app import stable_identity
from app.stable_identity import IdentityIntegrityError, StableIdentityStore


def _entry(mode: int, attributes: int = 0) -> SimpleNamespace:
    return SimpleNamespace(st_mode=mode, st_file_attributes=attributes)


def test_unsafe_lock_entry_rejects_links_and_reparse_points():
    assert stable_identity._unsafe_lock_entry(_entry(stat.S_IFLNK)) is True
    assert stable_identity._unsafe_lock_entry(_entry(stat.S_IFREG, 0x400)) is True
    assert stable_identity._unsafe_lock_entry(_entry(stat.S_IFREG)) is False
    assert stable_identity._unsafe_lock_entry(_entry(stat.S_IFREG, 0x20)) is False


def test_open_lock_file_opens_an_ordinary_file(tmp_path):
    lock_path = tmp_path / "identity.json.lock"
    lock_path.write_bytes(b"0")
    with stable_identity._open_lock_file(lock_path) as handle:
        handle.seek(0)
        assert handle.read() == b"0"


def test_open_lock_file_rejects_a_replaced_entry(tmp_path, monkeypatch):
    lock_path = tmp_path / "identity.json.lock"
    lock_path.write_bytes(b"0")
    real_fstat = os.fstat

    def mismatched_fstat(descriptor):
        opened = real_fstat(descriptor)
        return SimpleNamespace(
            st_mode=opened.st_mode,
            st_file_attributes=0,
            st_dev=opened.st_dev,
            st_ino=opened.st_ino + 1,
        )

    monkeypatch.setattr(stable_identity.os, "fstat", mismatched_fstat)
    with pytest.raises(IdentityIntegrityError):
        stable_identity._open_lock_file(lock_path)


def test_open_lock_file_reports_unreadable_lock_as_integrity_error(tmp_path, monkeypatch):
    lock_path = tmp_path / "identity.json.lock"
    lock_path.write_bytes(b"0")

    def failing_open(path, flags, *args, **kwargs):
        raise PermissionError("synthetic denied lock")

    monkeypatch.setattr(stable_identity.os, "open", failing_open)
    with pytest.raises(IdentityIntegrityError) as caught:
        stable_identity._open_lock_file(lock_path)
    assert "IDENTITY_STORE_LOCK_UNREADABLE" in str(caught.value)


@pytest.mark.skipif(os.name == "nt" or not hasattr(os, "symlink"), reason="POSIX symlink fixture")
def test_open_lock_file_rejects_a_symlink_without_touching_its_target(tmp_path):
    victim = tmp_path / "victim.txt"
    victim.write_bytes(b"unchanged")
    lock_path = tmp_path / "identity.json.lock"
    os.symlink(victim, lock_path)
    with pytest.raises(IdentityIntegrityError) as caught:
        stable_identity._open_lock_file(lock_path)
    assert "IDENTITY_STORE_LOCK_UNSAFE" in str(caught.value)
    assert victim.read_bytes() == b"unchanged"


def test_mutation_fails_closed_before_writing_identity_data(tmp_path, monkeypatch):
    store = StableIdentityStore(tmp_path / "identity.json")

    def unsafe_open(_path):
        raise IdentityIntegrityError("IDENTITY_STORE_LOCK_UNSAFE")

    monkeypatch.setattr(stable_identity, "_open_lock_file", unsafe_open)
    with pytest.raises(IdentityIntegrityError):
        store.create("provider", "synthetic-provider")
    assert not (tmp_path / "identity.json").exists()
    assert StableIdentityStore(tmp_path / "identity.json").list("provider") == ()
