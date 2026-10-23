"""Codec contracts and real persistent key I/O; no asset/permission mocks."""
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess
import sys

import pytest

from app.creative.asset_query_cursor import (
    AssetQueryCursorCodec, AssetQueryCursorInvalid, AssetQueryCursorRestart,
    AssetQueryCursorUnavailable, CursorPosition, CURSOR_TTL_SECONDS,
    MAX_TOKEN_BYTES, load_signing_key,
)


BINDING = hashlib.sha256(b"synthetic scope/query/actor binding").hexdigest()
REVISION = hashlib.sha256(b"synthetic source version").hexdigest()
AFTER = ("2026-10-23T00:00:00+00:00", "asset-a")


@pytest.fixture
def codec():
    clock = [1000]
    key = secrets.token_bytes(32)
    return AssetQueryCursorCodec(key, clock=lambda: clock[0]), clock, key


def sign_fixture(key, body):
    """Issue malformed but authentic payloads to exercise schema admission."""
    encoded = base64.urlsafe_b64encode(body).rstrip(b"=").decode("ascii")
    signature = hmac.new(key, b"PoemSeedStudio.AssetQueryCursor.v1\x00" + encoded.encode("ascii"),
                         hashlib.sha256).hexdigest()
    return "aq1." + encoded + "." + signature


def payload(**updates):
    return {"v": 1, "binding": BINDING, "revision": REVISION,
            "after": list(AFTER), "iat": 1000, "exp": 1900, **updates}


def test_round_trip_and_continuation_keep_original_expiry(codec):
    owner, clock, _ = codec
    token = owner.encode(BINDING, REVISION, AFTER)
    assert token.isascii() and len(token) <= MAX_TOKEN_BYTES
    position = owner.decode(token, BINDING, REVISION)
    assert position == CursorPosition(1000, 1000 + CURSOR_TTL_SECONDS, AFTER)
    clock[0] = 1800
    next_after = (AFTER[0], "asset-b")
    continued = owner.decode(owner.encode(BINDING, REVISION, next_after, position), BINDING, REVISION)
    assert continued == CursorPosition(1000, 1900, next_after)


def test_revision_change_expiry_and_clock_rollback_require_restart(codec):
    owner, clock, _ = codec
    token = owner.encode(BINDING, REVISION, AFTER)
    with pytest.raises(AssetQueryCursorRestart, match="^ASSET_QUERY_RESTART_REQUIRED$"):
        owner.decode(token, BINDING, hashlib.sha256(b"changed").hexdigest())
    position = owner.decode(token, BINDING, REVISION)
    for stamp in (999, 1900, 1901):
        clock[0] = stamp
        with pytest.raises(AssetQueryCursorRestart):
            owner.decode(token, BINDING, REVISION)
        with pytest.raises(AssetQueryCursorRestart):
            owner.encode(BINDING, REVISION, AFTER, position)


def test_changed_binding_or_mac_is_invalid(codec):
    owner, _, _ = codec
    token = owner.encode(BINDING, REVISION, AFTER)
    with pytest.raises(AssetQueryCursorInvalid, match="^ASSET_QUERY_INVALID$"):
        owner.decode(token, hashlib.sha256(b"other project/query/actor").hexdigest(), REVISION)
    pieces = token.split(".")
    pieces[1] = ("A" if pieces[1][0] != "A" else "B") + pieces[1][1:]
    with pytest.raises(AssetQueryCursorInvalid):
        owner.decode(".".join(pieces), BINDING, REVISION)
    with pytest.raises(AssetQueryCursorInvalid):
        AssetQueryCursorCodec(secrets.token_bytes(32), clock=lambda: 1000).decode(token, BINDING, REVISION)


@pytest.mark.parametrize("token", [None, "", "x" * 2049, "非ASCII", "aq1.abc", "aq1.a.b.c",
                                   "aq1.###." + "0" * 64, "aq1.abc=." + "0" * 64])
def test_token_grammar_and_size_are_bounded(codec, token):
    with pytest.raises(AssetQueryCursorInvalid):
        codec[0].decode(token, BINDING, REVISION)


@pytest.mark.parametrize("changes", [
    {"v": True}, {"v": 2}, {"extra": "no"}, {"iat": True}, {"iat": 1000.0},
    {"iat": -1}, {"exp": 1901}, {"exp": 1900.0}, {"exp": 2**100},
    {"binding": "not-a-digest"}, {"revision": "not-a-digest"},
    {"after": [AFTER[0]]}, {"after": {"created_at": AFTER[0], "id": AFTER[1]}},
    {"after": [1, AFTER[1]]}, {"after": ["x" * 81, AFTER[1]]},
    {"after": ["bad\ncreated", AFTER[1]]}, {"after": [AFTER[0], "x" * 241]},
    {"after": [AFTER[0], "../outside"]}, {"after": [AFTER[0], ""]},
])
def test_authenticated_payload_still_requires_exact_schema(codec, changes):
    owner, _, key = codec
    token = sign_fixture(key, json.dumps(payload(**changes)).encode())
    with pytest.raises(AssetQueryCursorInvalid):
        owner.decode(token, BINDING, REVISION)


@pytest.mark.parametrize("body", [b'{"v":1,"v":1}', b'{"v":NaN}', b'{"v":Infinity}',
                                  b"[" * 500 + b"0" + b"]" * 500,
                                  b" " * 1025, b"\xff\xfe"])
def test_authenticated_invalid_json_complexity_duplicates_constants_and_size(codec, body):
    owner, _, key = codec
    with pytest.raises(AssetQueryCursorInvalid):
        owner.decode(sign_fixture(key, body), BINDING, REVISION)


def test_unauthenticated_json_is_not_parsed(codec, monkeypatch):
    owner, _, key = codec
    token = sign_fixture(key, b'{"v":1}')
    token = token[:-1] + ("0" if token[-1] != "0" else "1")
    def forbidden(*_args, **_kwargs):
        raise AssertionError("unauthenticated JSON reached decoder")
    monkeypatch.setattr("app.creative.asset_query_cursor.json.loads", forbidden)
    with pytest.raises(AssetQueryCursorInvalid):
        owner.decode(token, BINDING, REVISION)


def test_invalid_codec_key_and_clock_are_unavailable():
    with pytest.raises(AssetQueryCursorUnavailable):
        AssetQueryCursorCodec(b"too short")
    for stamp in (float("nan"), float("inf"), -1, True, "1000"):
        codec = AssetQueryCursorCodec(secrets.token_bytes(32), clock=lambda: stamp)
        with pytest.raises(AssetQueryCursorUnavailable):
            codec.encode(BINDING, REVISION, AFTER)


@pytest.mark.skipif(os.name != "posix", reason="directory-relative key I/O requires POSIX primitives")
def test_real_key_permissions_reopen_and_independent_process_resume(tmp_path):
    directory = tmp_path / "cursor-state"
    key = load_signing_key(directory)
    assert len(key) == 32 and load_signing_key(directory) == key
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert stat.S_IMODE((directory / "cursor.key").stat().st_mode) == 0o600
    assert stat.S_IMODE((directory / "cursor.identity").stat().st_mode) == 0o600
    token = AssetQueryCursorCodec(key, clock=lambda: 1000).encode(BINDING, REVISION, AFTER)
    # A separate interpreter actually reopens the persisted secret and verifies
    # a token from the first process. No secret is printed or passed in argv.
    code = """import json,sys
from pathlib import Path
from app.creative.asset_query_cursor import AssetQueryCursorCodec,load_signing_key
request=json.loads(sys.stdin.read())
position=AssetQueryCursorCodec(load_signing_key(Path(request['directory'])),clock=lambda:1100).decode(request['token'],request['binding'],request['revision'])
print(json.dumps({'after':position.after,'expires_at':position.expires_at}))
"""
    result = subprocess.run([sys.executable, "-c", code], input=json.dumps({"directory": str(directory),
        "token": token, "binding": BINDING, "revision": REVISION}), text=True, capture_output=True,
        check=True, timeout=15, cwd=Path(__file__).resolve().parents[1])
    assert json.loads(result.stdout) == {"after": list(AFTER), "expires_at": 1900}


@pytest.mark.skipif(os.name != "posix", reason="directory-relative key I/O requires POSIX primitives")
@pytest.mark.parametrize("size", [0, 1, 31, 33, 4096])
def test_corrupt_key_is_not_overwritten(tmp_path, size):
    directory = tmp_path / "cursor-state"
    directory.mkdir(mode=0o700)
    path = directory / "cursor.key"
    path.write_bytes(b"z" * size)
    path.chmod(0o600)
    before = path.read_bytes()
    with pytest.raises(AssetQueryCursorUnavailable, match="^ASSET_QUERY_CURSOR_UNAVAILABLE$"):
        load_signing_key(directory)
    assert path.read_bytes() == before


@pytest.mark.skipif(os.name != "posix", reason="directory-relative key I/O requires POSIX primitives")
@pytest.mark.parametrize("change", ["missing-key", "changed-key", "corrupt-marker", "symlink-marker"])
def test_initialized_identity_cannot_silently_rotate(tmp_path, change):
    directory = tmp_path / "cursor-state"
    original_key = load_signing_key(directory)
    key_path, marker_path = directory / "cursor.key", directory / "cursor.identity"
    if change == "missing-key":
        key_path.unlink()
    elif change == "changed-key":
        changed = bytes([original_key[0] ^ 1]) + original_key[1:]
        key_path.write_bytes(changed)
    elif change == "corrupt-marker":
        marker_path.write_bytes(b"x" * marker_path.stat().st_size)
    else:
        target = tmp_path / "marker-target"
        marker_path.rename(target)
        marker_path.symlink_to(target)
    with pytest.raises(AssetQueryCursorUnavailable):
        load_signing_key(directory)
    if change == "missing-key":
        assert not key_path.exists()
    elif change == "changed-key":
        assert key_path.read_bytes() == changed
    else:
        assert key_path.read_bytes() == original_key


@pytest.mark.skipif(os.name != "posix", reason="directory-relative key I/O requires POSIX primitives")
@pytest.mark.parametrize("checkpoint", ["partial-key", "before-marker"])
def test_independent_process_interrupted_creation_is_recoverable_or_explicit(tmp_path, checkpoint):
    directory = tmp_path / "cursor-state"
    code = """import json,os,sys
from pathlib import Path
import app.creative.asset_query_cursor as cursor
request=json.loads(sys.stdin.read())
original=cursor._create_private_file
def interrupt(directory_fd,name,value):
    if request['checkpoint']=='partial-key' and name==cursor.KEY_NAME:
        fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=directory_fd)
        os.fsync(fd)
        os._exit(87)
    if request['checkpoint']=='before-marker' and name==cursor.IDENTITY_NAME:
        os._exit(87)
    original(directory_fd,name,value)
cursor._create_private_file=interrupt
cursor.load_signing_key(Path(request['directory']))
"""
    result = subprocess.run([sys.executable, "-c", code], input=json.dumps({"directory": str(directory),
        "checkpoint": checkpoint}), text=True, capture_output=True, timeout=15,
        cwd=Path(__file__).resolve().parents[1])
    assert result.returncode == 87
    key_path, marker_path = directory / "cursor.key", directory / "cursor.identity"
    before = key_path.read_bytes()
    assert not marker_path.exists()
    if checkpoint == "partial-key":
        with pytest.raises(AssetQueryCursorUnavailable):
            load_signing_key(directory)
        assert key_path.read_bytes() == before == b""
        assert not marker_path.exists()
    else:
        assert len(before) == 32 and load_signing_key(directory) == before
        assert marker_path.is_file()


@pytest.mark.skipif(os.name != "posix", reason="directory-relative key I/O requires POSIX primitives")
def test_symlink_directory_key_and_broad_permissions_are_refused(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    link = tmp_path / "linked-directory"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(AssetQueryCursorUnavailable):
        load_signing_key(link)
    assert not list(outside.iterdir())
    directory = tmp_path / "cursor-state"
    directory.mkdir(mode=0o700)
    target = tmp_path / "unrelated-key"
    target.write_bytes(secrets.token_bytes(32))
    target.chmod(0o600)
    (directory / "cursor.key").symlink_to(target)
    with pytest.raises(AssetQueryCursorUnavailable):
        load_signing_key(directory)
    (directory / "cursor.key").unlink()
    load_signing_key(directory)
    (directory / "cursor.key").chmod(0o644)
    with pytest.raises(AssetQueryCursorUnavailable):
        load_signing_key(directory)


def test_unsupported_key_primitives_fail_explicitly(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "supports_dir_fd", set())
    with pytest.raises(AssetQueryCursorUnavailable):
        load_signing_key(tmp_path / "cursor-state")
    assert not (tmp_path / "cursor-state").exists()
