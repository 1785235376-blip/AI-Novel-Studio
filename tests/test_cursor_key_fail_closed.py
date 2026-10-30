"""Fail-closed contract for the asset-query cursor signing key.

The Windows runtime this project supports lacks ``dir_fd``, ``O_NOFOLLOW`` and
``O_DIRECTORY`` primitives. Production must refuse the cursor feature (HTTP 503
``ASSET_QUERY_CURSOR_UNAVAILABLE``) instead of falling back to an unchecked path
open. These tests lock that fail-closed behavior only; they do not claim a
Windows signing-key backend, and they are not an acceptance of the still-OPEN
"Windows cursor signing key" work item.
"""
from __future__ import annotations

import os
import sys

import pytest

from app.creative import asset_query_cursor as cursor


def _expected_primitives_available() -> bool:
    return (os.open in os.supports_dir_fd and os.stat in os.supports_dir_fd
            and hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY"))


def test_primitive_report_matches_interpreter_facts():
    # The refusal is driven by interpreter capabilities, not by a platform list
    # that could silently claim a safe primitive it does not have.
    assert cursor.signing_key_primitives_available() is _expected_primitives_available()


def test_missing_safe_primitives_refuse_instead_of_falling_back(monkeypatch, tmp_path):
    monkeypatch.setattr(cursor, "signing_key_primitives_available", lambda: False)
    directory = tmp_path / "cursor-store"
    with pytest.raises(cursor.AssetQueryCursorUnavailable):
        cursor.load_signing_key(directory)
    # No unchecked fallback file is created before or after the refusal.
    assert not directory.exists()


@pytest.mark.skipif(_expected_primitives_available(),
                    reason="safe POSIX primitives are present; the refusal path is not reached")
def test_platform_without_primitives_refuses_and_creates_nothing(tmp_path):
    directory = tmp_path / "cursor-store"
    with pytest.raises(cursor.AssetQueryCursorUnavailable):
        cursor.load_signing_key(directory)
    assert not directory.exists()


def test_codec_rejects_key_material_of_wrong_type_or_size():
    for key in ("x" * 32, b"", b"short", b"x" * 31, b"x" * 33, bytearray(b"x" * 32)):
        with pytest.raises(cursor.AssetQueryCursorUnavailable):
            cursor.AssetQueryCursorCodec(key)


def test_cursor_token_carries_no_authority_and_rejects_tampering():
    key = b"k" * 32
    clock = lambda: 1_000_000.0  # noqa: E731 - deterministic test clock
    codec = cursor.AssetQueryCursorCodec(key, clock=clock)
    binding, revision = "a" * 64, "b" * 64
    token = codec.encode(binding, revision, ("2026-10-30T00:00:00+00:00", "asset-1"))
    position = codec.decode(token, binding, revision)
    assert position.after == ("2026-10-30T00:00:00+00:00", "asset-1")
    # Cross-binding replay and tampering are fixed refusals, never access.
    with pytest.raises(cursor.AssetQueryCursorInvalid):
        codec.decode(token, "c" * 64, revision)
    body, signature = token.split(".")[1:]
    tampered = "aq1." + body[:-2] + ("AA" if body[-2:] != "AA" else "BB") + "." + signature
    with pytest.raises((cursor.AssetQueryCursorInvalid, cursor.AssetQueryCursorRestart)):
        codec.decode(tampered, binding, revision)


def test_expired_cursor_requires_restart_without_renewing_ttl():
    now = [1_000_000.0]
    codec = cursor.AssetQueryCursorCodec(b"k" * 32, clock=lambda: now[0])
    binding, revision = "a" * 64, "b" * 64
    token = codec.encode(binding, revision, ("2026-10-30T00:00:00+00:00", "asset-1"))
    first = codec.decode(token, binding, revision)
    now[0] += cursor.CURSOR_TTL_SECONDS
    with pytest.raises(cursor.AssetQueryCursorRestart):
        codec.decode(token, binding, revision)
    # A continuation cannot slide the original expiry forward.
    with pytest.raises(cursor.AssetQueryCursorRestart):
        codec.encode(binding, revision, first.after, prior=first)
