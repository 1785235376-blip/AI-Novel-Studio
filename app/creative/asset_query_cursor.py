"""Bounded, scope-bound asset query cursors; tokens never authorize a read.

The caller performs the original authority checks before decoding, supplies
the current source revision, and checks that revision again before returning.
This codec neither reads assets nor claims a snapshot across other owners.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re
import secrets
import stat
import time


MAX_TOKEN_BYTES = 2048
MAX_PAYLOAD_BYTES = 1024
CURSOR_TTL_SECONDS = 900
KEY_NAME = "cursor.key"
IDENTITY_NAME = "cursor.identity"
# The Windows backend stores only the DPAPI-sealed key under a distinct name so
# a plaintext POSIX-style key is never mistaken for a sealed one.
WINDOWS_KEY_NAME = "cursor.key.dpapi"
MAX_WINDOWS_BLOB_BYTES = 4096
_IDENTITY_PREFIX = b"asset-query-cursor-key/1\n"
_DOMAIN = b"PoemSeedStudio.AssetQueryCursor.v1\x00"
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,239}\Z")
_URL64 = re.compile(r"[A-Za-z0-9_-]+\Z")
_FIELDS = {"v", "binding", "revision", "after", "iat", "exp"}


class AssetQueryCursorInvalid(ValueError):
    def __init__(self):
        super().__init__("ASSET_QUERY_INVALID")


class AssetQueryCursorRestart(ValueError):
    def __init__(self):
        super().__init__("ASSET_QUERY_RESTART_REQUIRED")


class AssetQueryCursorUnavailable(RuntimeError):
    def __init__(self):
        super().__init__("ASSET_QUERY_CURSOR_UNAVAILABLE")


@dataclass(frozen=True)
class CursorPosition:
    issued_at: int
    expires_at: int
    after: tuple[str, str]


def _digest(value):
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        raise AssetQueryCursorInvalid()
    return value


def _after(value):
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise AssetQueryCursorInvalid()
    created, aid = value
    if (not isinstance(created, str) or len(created) > 80
            or any(ord(char) < 32 or ord(char) == 127 for char in created)
            or not isinstance(aid, str) or _ID.fullmatch(aid) is None):
        raise AssetQueryCursorInvalid()
    return created, aid


def _times(issued, expires):
    if (type(issued) is not int or type(expires) is not int
            or not 0 <= issued <= 2**53 - 1 - CURSOR_TTL_SECONDS
            or expires - issued != CURSOR_TTL_SECONDS):
        raise AssetQueryCursorInvalid()


def _url64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AssetQueryCursorInvalid()
        result[key] = value
    return result


def _constant(_value):
    raise AssetQueryCursorInvalid()


class AssetQueryCursorCodec:
    def __init__(self, key: bytes, clock=time.time):
        if type(key) is not bytes or len(key) != 32 or not callable(clock):
            raise AssetQueryCursorUnavailable()
        self._key, self._clock = key, clock

    def _now(self):
        try:
            value = self._clock()
            if (type(value) not in (int, float) or not math.isfinite(value)
                    or not 0 <= value <= 2**53 - 1 - CURSOR_TTL_SECONDS):
                raise AssetQueryCursorUnavailable()
            return int(value)
        except AssetQueryCursorUnavailable:
            raise
        except Exception:
            raise AssetQueryCursorUnavailable() from None

    def encode(self, binding: str, revision: str, after: tuple[str, str],
               prior: CursorPosition | None = None) -> str:
        binding, revision, after = _digest(binding), _digest(revision), _after(after)
        current = self._now()
        if prior is None:
            issued, expires = current, current + CURSOR_TTL_SECONDS
        elif isinstance(prior, CursorPosition):
            issued, expires = prior.issued_at, prior.expires_at
            _times(issued, expires)
            if not issued <= current < expires:
                raise AssetQueryCursorRestart()
        else:
            raise AssetQueryCursorInvalid()
        raw = json.dumps({"v": 1, "binding": binding, "revision": revision,
                          "after": after, "iat": issued, "exp": expires},
                         sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                         allow_nan=False).encode("ascii")
        if len(raw) > MAX_PAYLOAD_BYTES:
            raise AssetQueryCursorInvalid()
        body = _url64(raw)
        signature = hmac.new(self._key, _DOMAIN + body.encode("ascii"), hashlib.sha256).hexdigest()
        token = "aq1." + body + "." + signature
        if len(token) > MAX_TOKEN_BYTES:
            raise AssetQueryCursorInvalid()
        return token

    def decode(self, token: str, binding: str, revision: str) -> CursorPosition:
        binding, revision = _digest(binding), _digest(revision)
        if (not isinstance(token, str) or not token.isascii()
                or not 1 <= len(token) <= MAX_TOKEN_BYTES):
            raise AssetQueryCursorInvalid()
        parts = token.split(".")
        if (len(parts) != 3 or parts[0] != "aq1" or not _URL64.fullmatch(parts[1])
                or len(parts[1]) > 4 * ((MAX_PAYLOAD_BYTES + 2) // 3)
                or not _SHA.fullmatch(parts[2])):
            raise AssetQueryCursorInvalid()
        body, supplied = parts[1:]
        expected = hmac.new(self._key, _DOMAIN + body.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(supplied, expected):
            raise AssetQueryCursorInvalid()
        # No JSON parsing of an unauthenticated token. Even authenticated
        # payloads are bounded and shape-checked; signatures are not schemas.
        try:
            raw = base64.b64decode(body + "=" * (-len(body) % 4), altchars=b"-_", validate=True)
            if len(raw) > MAX_PAYLOAD_BYTES or _url64(raw) != body:
                raise AssetQueryCursorInvalid()
            value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant)
            if (not isinstance(value, dict) or set(value) != _FIELDS
                    or type(value["v"]) is not int or value["v"] != 1):
                raise AssetQueryCursorInvalid()
            actual_binding, actual_revision = _digest(value["binding"]), _digest(value["revision"])
            after = _after(value["after"])
            issued, expires = value["iat"], value["exp"]
            _times(issued, expires)
        except (ValueError, TypeError, RecursionError, UnicodeError):
            raise AssetQueryCursorInvalid() from None
        if not hmac.compare_digest(actual_binding, binding):
            raise AssetQueryCursorInvalid()
        current = self._now()
        if not issued <= current < expires or not hmac.compare_digest(actual_revision, revision):
            raise AssetQueryCursorRestart()
        return CursorPosition(issued, expires, after)


def _regular(info):
    return stat.S_ISREG(info.st_mode) and not (
        getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _read_private_file(directory_fd, name, size):
    try:
        before = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    if (not _regular(before) or before.st_size != size or before.st_mode & 0o077
            or before.st_nlink != 1):
        raise AssetQueryCursorUnavailable()
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
    with os.fdopen(descriptor, "rb") as handle:
        if _identity(os.fstat(handle.fileno())) != _identity(before):
            raise AssetQueryCursorUnavailable()
        value = handle.read(size + 1)
        after = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if len(value) != size or _identity(after) != _identity(before):
            raise AssetQueryCursorUnavailable()
    return value


def _create_private_file(directory_fd, name, value):
    try:
        descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=directory_fd)
    except FileExistsError:
        # An unexpected concurrent creator must never be truncated; the caller
        # validates the completed file before accepting it.
        return
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    os.fsync(directory_fd)


def posix_signing_primitives_available() -> bool:
    """Report the POSIX directory-relative no-follow primitives."""
    return (os.open in os.supports_dir_fd and os.stat in os.supports_dir_fd
            and hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY"))


def windows_dpapi_available() -> bool:
    """Report the current-user DPAPI backend used when POSIX primitives are absent."""
    try:
        from ..windows_dpapi import available
    except ImportError:  # pragma: no cover - packaging boundary
        return False
    return available()


def signing_key_primitives_available() -> bool:
    """Report a usable safe signing-key backend, not filesystem or key health."""
    return posix_signing_primitives_available() or windows_dpapi_available()


def _windows_regular(entry) -> bool:
    return stat.S_ISREG(entry.st_mode) and not (
        getattr(entry, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _windows_identity(entry):
    return entry.st_dev, entry.st_ino, entry.st_size, entry.st_mtime_ns


def _windows_read(path: Path, maximum: int):
    """Read one private ordinary file and prove its identity did not change."""
    try:
        before = path.lstat()
    except FileNotFoundError:
        return None
    if (not _windows_regular(before) or before.st_nlink != 1
            or not 1 <= before.st_size <= maximum):
        raise AssetQueryCursorUnavailable()
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    descriptor = None
    try:
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if _windows_identity(opened) != _windows_identity(before):
            raise AssetQueryCursorUnavailable()
        value = os.read(descriptor, maximum + 1)
        after = path.lstat()
        if (len(value) != before.st_size
                or _windows_identity(after) != _windows_identity(before)):
            raise AssetQueryCursorUnavailable()
        return value
    except OSError:
        raise AssetQueryCursorUnavailable() from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _windows_create(path: Path, value: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError:
        # An unexpected concurrent creator must never be truncated; the caller
        # validates the completed file before accepting it.
        return
    except OSError:
        raise AssetQueryCursorUnavailable() from None
    try:
        os.write(descriptor, value)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _load_windows_signing_key(directory: Path) -> bytes:
    """Current-user DPAPI signing key for hosts without POSIX path primitives.

    Confidentiality comes from DPAPI scoped to the current Windows user, not from
    POSIX file modes. The key is only ever stored sealed; the independent identity
    marker carries the key digest so a missing, replaced, mismatched or
    interrupted key is refused instead of silently rotated. Entries must be
    ordinary single-link files whose identity is unchanged across the read. This
    primitive is not end-to-end acceptance: the runtime capability contract still
    reports the cursor as NOT_VERIFIED until desktop acceptance runs.
    """
    from ..windows_dpapi import DpapiUnavailable, protect, unprotect

    directory = Path(directory)
    try:
        directory.mkdir(mode=0o700, exist_ok=True)
        before = directory.lstat()
        if (not stat.S_ISDIR(before.st_mode) or stat.S_ISLNK(before.st_mode)
                or getattr(before, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            raise AssetQueryCursorUnavailable()
        key_path, marker_path = directory / WINDOWS_KEY_NAME, directory / IDENTITY_NAME
        marker_size = len(_IDENTITY_PREFIX) + 65
        marker = _windows_read(marker_path, marker_size)
        sealed = _windows_read(key_path, MAX_WINDOWS_BLOB_BYTES)
        if sealed is None:
            if marker is not None:
                raise AssetQueryCursorUnavailable()
            raw = secrets.token_bytes(32)
            _windows_create(key_path, protect(raw))
            sealed = _windows_read(key_path, MAX_WINDOWS_BLOB_BYTES)
            if sealed is None:
                raise AssetQueryCursorUnavailable()
        raw = unprotect(sealed)
        if type(raw) is not bytes or len(raw) != 32:
            raise AssetQueryCursorUnavailable()
        expected_marker = _IDENTITY_PREFIX + hashlib.sha256(raw).hexdigest().encode("ascii") + b"\n"
        if marker is None:
            _windows_create(marker_path, expected_marker)
            marker = _windows_read(marker_path, marker_size)
        if marker is None or not hmac.compare_digest(marker, expected_marker):
            raise AssetQueryCursorUnavailable()
        after_directory = directory.lstat()
        if (not stat.S_ISDIR(after_directory.st_mode)
                or getattr(after_directory, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
                or (after_directory.st_dev, after_directory.st_ino) != (before.st_dev, before.st_ino)):
            raise AssetQueryCursorUnavailable()
        return raw
    except (OSError, ValueError, TypeError, DpapiUnavailable):
        raise AssetQueryCursorUnavailable() from None


def _load_posix_signing_key(directory: Path) -> bytes:
    """Load/create the independent persistent cursor key under an owner lease.

    The caller holds the existing cross-process asset lease. Directory-relative
    no-follow opens prevent a substituted key/directory symlink from redirecting
    a read or creation. Platforms without those primitives fail explicitly;
    they do not fall back to unchecked path opens. The independent identity
    marker detects a missing or changed initialized key. An interrupted partial
    write needs operator repair; valid key creation interrupted before the
    marker can safely finish on retry. Neither file is replaced automatically.
    Complete loss of both files cannot be distinguished from first creation.
    """
    directory = Path(directory)
    if not signing_key_primitives_available():
        raise AssetQueryCursorUnavailable()
    descriptor = None
    try:
        directory.mkdir(mode=0o700, exist_ok=True)
        before = directory.lstat()
        if (not stat.S_ISDIR(before.st_mode) or stat.S_ISLNK(before.st_mode)
                or before.st_mode & 0o077):
            raise AssetQueryCursorUnavailable()
        descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        opened = os.fstat(descriptor)
        if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise AssetQueryCursorUnavailable()
        marker_size = len(_IDENTITY_PREFIX) + 65
        marker = _read_private_file(descriptor, IDENTITY_NAME, marker_size)
        result = _read_private_file(descriptor, KEY_NAME, 32)
        if result is None:
            if marker is not None:
                raise AssetQueryCursorUnavailable()
            _create_private_file(descriptor, KEY_NAME, secrets.token_bytes(32))
            result = _read_private_file(descriptor, KEY_NAME, 32)
            if result is None:
                raise AssetQueryCursorUnavailable()
        expected_marker = _IDENTITY_PREFIX + hashlib.sha256(result).hexdigest().encode("ascii") + b"\n"
        if marker is None:
            _create_private_file(descriptor, IDENTITY_NAME, expected_marker)
            marker = _read_private_file(descriptor, IDENTITY_NAME, marker_size)
        if marker is None or not hmac.compare_digest(marker, expected_marker):
            raise AssetQueryCursorUnavailable()
        after_directory = directory.lstat()
        if (not stat.S_ISDIR(after_directory.st_mode) or after_directory.st_mode & 0o077
                or (after_directory.st_dev, after_directory.st_ino) != (opened.st_dev, opened.st_ino)):
            raise AssetQueryCursorUnavailable()
        return result
    except (OSError, ValueError, TypeError):
        raise AssetQueryCursorUnavailable() from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def load_signing_key(directory: Path) -> bytes:
    """Load/create the persistent cursor signing key through a safe backend.

    POSIX hosts use the directory-relative no-follow contract. Windows hosts,
    which lack ``dir_fd``/``O_NOFOLLOW``/``O_DIRECTORY``, use the current-user
    DPAPI-sealed key with the same independent identity marker. Hosts with
    neither backend fail explicitly (``ASSET_QUERY_CURSOR_UNAVAILABLE``) and
    never fall back to an unchecked plaintext key path.
    """
    if not signing_key_primitives_available():
        raise AssetQueryCursorUnavailable()
    if posix_signing_primitives_available():
        return _load_posix_signing_key(directory)
    return _load_windows_signing_key(directory)
