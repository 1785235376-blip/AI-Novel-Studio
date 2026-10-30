"""Private same-host execution claims for the original File export owner.

Locks are held through queued futures and exporter finalization, never unlinked.
This is not a distributed lease or an exactly-once external-effect protocol.
Live fork without exec while claims are held is outside this helper's contract.
"""
from __future__ import annotations

import errno
import hashlib
import os
from pathlib import Path
import stat
from threading import Lock

_registry_lock = Lock()
_registry: set[tuple[int, str, str]] = set()


class ExportExecutionUnavailable(RuntimeError):
    pass


def _regular(info):
    return stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and not (getattr(info, 'st_file_attributes', 0) & 0x400)


def _identity(info):
    return info.st_dev, info.st_ino


def _try_lock(handle):
    if os.name == 'nt':
        import msvcrt
        if os.fstat(handle.fileno()).st_size == 0:
            handle.write(b'0'); handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}: return False
            raise
    elif os.name == 'posix':
        import fcntl
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN}: return False
            raise
    else:
        raise ExportExecutionUnavailable('unsupported execution lock platform')
    return True


class ExecutionClaim:
    def __init__(self, handle, key):
        self._handle, self._key = handle, key
        self._guard = Lock()

    def release(self):
        with self._guard:
            handle, self._handle = self._handle, None
            if handle is None: return
            try:
                # Closing releases the process-local handle and its OS claim.
                handle.close()
            finally:
                with _registry_lock:
                    _registry.discard(self._key)


def try_execution_claim(root: Path, job_id: str) -> ExecutionClaim | None:
    """Return a held claim, None only for contention, otherwise fail closed."""
    root = Path(root).resolve(strict=True)
    if not isinstance(job_id, str) or not job_id:
        raise ExportExecutionUnavailable('invalid export identity')
    key = (os.getpid(), str(root), job_id)
    with _registry_lock:
        if key in _registry: return None
        _registry.add(key)
    handle = None
    descriptor = None
    try:
        directory = root / '.export-execution-locks'
        directory.mkdir(exist_ok=True)
        folder = directory.lstat()
        if not stat.S_ISDIR(folder.st_mode) or stat.S_ISLNK(folder.st_mode) or getattr(folder, 'st_file_attributes', 0) & 0x400:
            raise ExportExecutionUnavailable('unsafe execution lock directory')
        path = directory / (hashlib.sha256(job_id.encode('utf-8')).hexdigest() + '.lock')
        descriptor = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0), 0o600)
        opened = os.fstat(descriptor)
        if not _regular(opened) or _identity(path.lstat()) != _identity(opened):
            raise ExportExecutionUnavailable('unsafe execution lock file')
        handle = os.fdopen(descriptor, 'r+b'); descriptor = None
        if not _try_lock(handle):
            handle.close(); handle = None
            return None
        if _identity(directory.lstat()) != _identity(folder) or _identity(path.lstat()) != _identity(opened):
            raise ExportExecutionUnavailable('execution lock identity changed')
        claim = ExecutionClaim(handle, key)
        handle = None
        return claim
    except OSError as exc:
        raise ExportExecutionUnavailable('execution lock unavailable') from exc
    finally:
        if descriptor is not None: os.close(descriptor)
        if handle is not None: handle.close()
        # A successful claim keeps its registry entry until explicit release.
        if 'claim' not in locals():
            with _registry_lock: _registry.discard(key)
