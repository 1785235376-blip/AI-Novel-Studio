"""Windows cursor signing-key backend: current-user DPAPI sealed key.

The Windows product runtime has no ``dir_fd``/``O_NOFOLLOW``/``O_DIRECTORY``, so
the POSIX signing-key contract cannot be used. This backend stores only a
DPAPI-sealed 32-byte key plus the same independent identity marker; missing,
replaced, mismatched, interrupted or reparse-point state fails closed instead of
silently rotating or degrading to a plaintext path. These tests use synthetic
temporary directories and the real local DPAPI binding of this user; they are
not the desktop end-to-end acceptance (still ``NOT_VERIFIED``).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from app.creative import asset_query_cursor as cursor
from app.windows_dpapi import DpapiUnavailable, protect, unprotect


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows DPAPI backend")


def _directory(tmp_path: Path) -> Path:
    return tmp_path / "cursor-state"


def test_dpapi_roundtrip_is_user_scoped_and_rejects_tamper():
    secret = os.urandom(32)
    sealed = protect(secret)
    assert len(sealed) > 32
    assert secret not in sealed
    assert unprotect(sealed) == secret
    with pytest.raises(DpapiUnavailable):
        unprotect(sealed[:-1] + bytes([sealed[-1] ^ 1]))
    for bad in (b"", b"x" * 65, "text"):
        with pytest.raises(DpapiUnavailable):
            protect(bad)
    with pytest.raises(DpapiUnavailable):
        unprotect(b"")


def test_signing_key_is_stable_and_only_sealed_material_is_stored(tmp_path):
    directory = _directory(tmp_path)
    key = cursor.load_signing_key(directory)
    assert type(key) is bytes and len(key) == 32
    assert cursor.load_signing_key(directory) == key
    assert sorted(path.name for path in directory.iterdir()) == ["cursor.identity", "cursor.key.dpapi"]
    sealed = (directory / "cursor.key.dpapi").read_bytes()
    marker = (directory / "cursor.identity").read_bytes()
    assert len(sealed) > 32 and key not in sealed
    assert marker == cursor._IDENTITY_PREFIX + hashlib.sha256(key).hexdigest().encode("ascii") + b"\n"


def test_independent_process_reopens_the_persisted_key(tmp_path):
    directory = _directory(tmp_path)
    key = cursor.load_signing_key(directory)
    token = cursor.AssetQueryCursorCodec(key, clock=lambda: 1000).encode(
        "a" * 64, "b" * 64, ("2026-10-30T00:00:00+00:00", "asset-1"))
    code = """import json,sys
from pathlib import Path
from app.creative.asset_query_cursor import AssetQueryCursorCodec, load_signing_key
request = json.loads(sys.stdin.read())
position = AssetQueryCursorCodec(load_signing_key(Path(request['directory'])),
    clock=lambda: 1100).decode(request['token'], request['binding'], request['revision'])
print(json.dumps({'after': position.after, 'expires_at': position.expires_at}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        input=json.dumps({"directory": str(directory), "token": token,
                          "binding": "a" * 64, "revision": "b" * 64}),
        text=True, capture_output=True, check=True, timeout=30,
        cwd=Path(__file__).resolve().parents[1])
    assert json.loads(completed.stdout) == {
        "after": ["2026-10-30T00:00:00+00:00", "asset-1"], "expires_at": 1900}


def test_missing_key_after_initialization_is_refused_without_rotation(tmp_path):
    directory = _directory(tmp_path)
    key = cursor.load_signing_key(directory)
    (directory / "cursor.key.dpapi").unlink()
    marker_before = (directory / "cursor.identity").read_bytes()
    with pytest.raises(cursor.AssetQueryCursorUnavailable):
        cursor.load_signing_key(directory)
    assert not (directory / "cursor.key.dpapi").exists()
    assert (directory / "cursor.identity").read_bytes() == marker_before
    assert key


def test_changed_marker_is_refused_and_key_bytes_are_untouched(tmp_path):
    directory = _directory(tmp_path)
    cursor.load_signing_key(directory)
    sealed_before = (directory / "cursor.key.dpapi").read_bytes()
    marker = directory / "cursor.identity"
    marker.write_bytes(b"x" * marker.stat().st_size)
    with pytest.raises(cursor.AssetQueryCursorUnavailable):
        cursor.load_signing_key(directory)
    assert (directory / "cursor.key.dpapi").read_bytes() == sealed_before
    assert marker.read_bytes() == b"x" * marker.stat().st_size


def test_corrupt_sealed_key_is_refused_and_not_overwritten(tmp_path):
    directory = _directory(tmp_path)
    cursor.load_signing_key(directory)
    key_path = directory / "cursor.key.dpapi"
    corrupt = b"not-a-dpapi-blob"
    key_path.write_bytes(corrupt)
    with pytest.raises(cursor.AssetQueryCursorUnavailable):
        cursor.load_signing_key(directory)
    assert key_path.read_bytes() == corrupt


def test_interrupted_empty_key_creation_is_refused(tmp_path):
    directory = _directory(tmp_path)
    directory.mkdir(mode=0o700)
    key_path = directory / "cursor.key.dpapi"
    key_path.write_bytes(b"")
    with pytest.raises(cursor.AssetQueryCursorUnavailable):
        cursor.load_signing_key(directory)
    assert key_path.read_bytes() == b""
    assert not (directory / "cursor.identity").exists()


def test_sealed_key_written_before_marker_is_recovered(tmp_path):
    directory = _directory(tmp_path)
    directory.mkdir(mode=0o700)
    raw = os.urandom(32)
    (directory / "cursor.key.dpapi").write_bytes(protect(raw))
    assert cursor.load_signing_key(directory) == raw
    marker = (directory / "cursor.identity").read_bytes()
    assert marker == cursor._IDENTITY_PREFIX + hashlib.sha256(raw).hexdigest().encode("ascii") + b"\n"


def test_hardlinked_key_entry_is_refused(tmp_path):
    directory = _directory(tmp_path)
    cursor.load_signing_key(directory)
    key_path = directory / "cursor.key.dpapi"
    os.link(key_path, tmp_path / "hardlinked-copy")
    with pytest.raises(cursor.AssetQueryCursorUnavailable):
        cursor.load_signing_key(directory)


def test_directory_reparse_point_is_refused(tmp_path):
    target = tmp_path / "real-state"
    target.mkdir()
    link = tmp_path / "linked-state"
    try:
        os.symlink(target, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        completed = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                                   capture_output=True, text=True)
        if completed.returncode != 0:
            pytest.skip("directory symlink/junction creation is not permitted")
    try:
        with pytest.raises(cursor.AssetQueryCursorUnavailable):
            cursor.load_signing_key(link)
        assert not list(target.iterdir())
    finally:
        try:
            os.rmdir(link)
        except OSError:
            os.unlink(link)
