"""Archive-member path safety for the delivered-bundle and portable-project readers.

Both readers are in-memory: they never hand member names to a filesystem path.
These regressions lock that untrusted ZIP names cannot become traversal,
absolute, reserved, duplicate or file/directory-conflicting entries, and that the
reader keeps returning only the validated relative paths.
"""
from __future__ import annotations

import io
import os
import stat
import zipfile

import pytest

from app.experimental.interactive_export_contract import (
    check_path_set, read_zip_safely, safe_bundle_path,
)
from app.experimental.portable_projects import read_archive

PREFIX = "interactive-probe/"


def _zip(members: list[tuple[str, bytes]], *, symlink: str | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, data in members:
            archive.writestr(name, data)
        if symlink is not None:
            info = zipfile.ZipInfo(symlink)
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, b"target")
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Delivered-bundle reader (interactive export contract)
# ---------------------------------------------------------------------------

def test_bundle_reader_returns_only_validated_relative_paths():
    raw = _zip([(PREFIX + "manifest.json", b"{}"), (PREFIX + "notes/a.txt", b"synthetic")])
    assert read_zip_safely(raw, PREFIX) == {"manifest.json": b"{}", "notes/a.txt": b"synthetic"}


@pytest.mark.parametrize("relative", [
    "../escape", "a/../../escape", "/absolute", "a:b", "CON", "a.", "a ",
    "nested/./x", "nested//x",
])
def test_bundle_reader_rejects_unsafe_member_paths(relative):
    with pytest.raises(ValueError):
        read_zip_safely(_zip([(PREFIX + relative, b"x")]), PREFIX)


def test_bundle_reader_backslash_member_is_normalized_or_rejected():
    """Windows ``zipfile`` normalizes backslashes in member names on write *and*
    read (``os.sep`` replacement), while POSIX keeps them. Either way an untrusted
    member must never resolve outside the declared bundle root: Windows sees a
    nested relative path, POSIX rejects the backslash outright."""
    raw = _zip([(PREFIX + "a/b", b"x")])
    raw = raw.replace((PREFIX + "a/b").encode("ascii"), (PREFIX + "a\\b").encode("ascii"))
    assert b"a\\b" in raw
    if os.name == "nt":
        assert read_zip_safely(raw, PREFIX) == {"a/b": b"x"}
    else:
        with pytest.raises(ValueError):
            read_zip_safely(raw, PREFIX)


@pytest.mark.parametrize("name", [
    "other/manifest.json", "interactive-probe2/x", "interactive-probe",
])
def test_bundle_reader_requires_the_declared_root_prefix(name):
    with pytest.raises(ValueError):
        read_zip_safely(_zip([(name, b"x")]), PREFIX)


def test_bundle_reader_rejects_case_collisions_and_prefix_conflicts():
    with pytest.raises(ValueError):
        read_zip_safely(_zip([(PREFIX + "A.txt", b"1"), (PREFIX + "a.txt", b"2")]), PREFIX)
    with pytest.raises(ValueError):
        read_zip_safely(_zip([(PREFIX + "a", b"1"), (PREFIX + "a/b.txt", b"2")]), PREFIX)


def test_bundle_path_validator_contract():
    assert safe_bundle_path("notes/a.txt") == "notes/a.txt"
    for value in ("", "/x", "a\\b", "a:b", "../x", "a/./b", "CON", "x.", "x ", " " + "x"):
        with pytest.raises(ValueError):
            safe_bundle_path(value)
    with pytest.raises(ValueError):
        safe_bundle_path("a/b/c/d/e/f/g/h/i/j/k/l/m")
    with pytest.raises(ValueError):
        check_path_set(["a.txt", "A.TXT"])


# ---------------------------------------------------------------------------
# Portable-project archive reader
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", [
    "../escape", "/absolute", "a\\b", "media/../x", ".", "..", "media//x",
    "media/a0001.png/../x", "manifest.json/../x", "CON", "media/a0001.png ",
])
def test_portable_reader_rejects_unsafe_member_names(name):
    with pytest.raises(ValueError) as raised:
        read_archive(_zip([(name, b"x")]))
    assert "PORTABLE_UNSAFE_MEMBER" in str(raised.value)


def test_portable_reader_rejects_symlink_and_duplicate_members():
    raw = _zip([("media/a0001.png", b"x")], symlink="media/a0002.png")
    with pytest.raises(ValueError) as raised:
        read_archive(raw)
    assert "PORTABLE_UNSAFE_MEMBER" in str(raised.value)
    duplicate = _zip([("media/a0001.png", b"1"), ("media/a0001.png", b"2")])
    with pytest.raises(ValueError) as raised:
        read_archive(duplicate)
    assert "PORTABLE_UNSAFE_MEMBER" in str(raised.value)


def test_portable_reader_requires_manifest_after_member_allowlist():
    # Names pass the strict allowlist; the reader still refuses an undeclared
    # payload-only archive before it reads any manifest or member content.
    with pytest.raises(ValueError) as raised:
        read_archive(_zip([("media/a0001.png", b"x")]))
    assert "PORTABLE_MANIFEST_MISSING" in str(raised.value)
