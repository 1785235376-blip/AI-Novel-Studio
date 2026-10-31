"""Workspace-scoped coordination for multi-file File backend mutations."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import os
import stat
from threading import RLock
from threading import local
from pathlib import Path
from weakref import WeakValueDictionary

_guard = RLock()
_locks: dict[tuple[str, str], RLock] = {}
# Cold observations share the identical in-process mutex with other active
# users, but do not enroll it in the original strict-mode warm registry.
_cold_locks = WeakValueDictionary()
_thread_state = local()
_existing_only = ContextVar('workspace_existing_coordination_only', default=False)
_existing_disk_memory_lock = ContextVar('workspace_existing_disk_memory_lock', default=False)


@contextmanager
def isolate_coordination_request_context():
    """Clear an independent request's inherited coordination policy."""
    token = _existing_only.set(False)
    memory_token = _existing_disk_memory_lock.set(False)
    try:
        yield
    finally:
        _existing_disk_memory_lock.reset(memory_token)
        _existing_only.reset(token)


class ReadOnlyCoordinationUnavailable(RuntimeError):
    def __init__(self):
        super().__init__('STUDIO_USAGE_STRICT_READ_ONLY_UNAVAILABLE')


@contextmanager
def existing_coordination_only(enabled=True):
    """Retain original coordination without initializing filesystem facilities.

    Original mutations/admission initialize these facilities explicitly. This
    capability never warms a path or replaces the original locking protocol.
    """
    token = _existing_only.set(_existing_only.get() or enabled)
    memory_token = _existing_disk_memory_lock.set(False) if enabled else None
    try:
        yield
    finally:
        if memory_token is not None:
            _existing_disk_memory_lock.reset(memory_token)
        _existing_only.reset(token)


@contextmanager
def existing_disk_coordination_only():
    """Observe only existing disk locks, permitting a cold process RLock.

    Registering a process-local RLock is not disk initialization. The normal
    strict file open, identity and byte lock checks remain mandatory. An
    enclosing stricter policy may not be upgraded by an inner caller.
    """
    already_strict = _existing_only.get()
    memory_token = _existing_disk_memory_lock.set(
        _existing_disk_memory_lock.get() or not already_strict)
    token = _existing_only.set(True)
    try:
        yield
    finally:
        _existing_only.reset(token)
        _existing_disk_memory_lock.reset(memory_token)


def strict_coordination_active():
    return _existing_only.get()


def workspace_mutation_lock(root: Path, workspace_id: str) -> RLock:
    key = (str(Path(root).resolve()), str(workspace_id))
    with _guard:
        if _existing_only.get():
            lock = _locks.get(key)
            if lock is None and _existing_disk_memory_lock.get():
                lock = _cold_locks.get(key)
                if lock is None:
                    lock = RLock()
                    _cold_locks[key] = lock
            if lock is None:
                raise ReadOnlyCoordinationUnavailable()
            return lock
        lock = _locks.get(key)
        if lock is None:
            # If a cold observation is already active, the original writer
            # must reuse its mutex rather than create a second object.
            lock = _cold_locks.get(key)
            if lock is None:
                lock = RLock()
            _locks[key] = lock
        return lock


def _existing_lock(root, workspace_id):
    """Open a populated original lock without create, truncate, or mkdir."""
    directory = Path(root) / '.workspace-mutation-locks'
    path = directory / (hashlib.sha256(str(workspace_id).encode('utf-8')).hexdigest() + '.lock')
    descriptor = None
    def identity(info):
        if (not stat.S_ISREG(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400
                or (os.name == 'nt' and info.st_size < 1)):
            raise ReadOnlyCoordinationUnavailable()
        return info.st_dev, info.st_ino
    try:
        folder = directory.lstat()
        if not stat.S_ISDIR(folder.st_mode) or getattr(folder, 'st_file_attributes', 0) & 0x400:
            raise ReadOnlyCoordinationUnavailable()
        before = identity(path.lstat())
        descriptor = os.open(path, os.O_RDWR | getattr(os, 'O_BINARY', 0)
                             | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
        if identity(os.fstat(descriptor)) != before or identity(path.lstat()) != before:
            raise ReadOnlyCoordinationUnavailable()
        handle = os.fdopen(descriptor, 'r+b')
        descriptor = None
        return handle, path, before
    except OSError:
        raise ReadOnlyCoordinationUnavailable() from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


@contextmanager
def workspace_mutation(root: Path, workspace_id: str):
    lock = workspace_mutation_lock(root, workspace_id)
    with lock:
        key = (str(Path(root).resolve()), str(workspace_id))
        depths = getattr(_thread_state, "depths", None)
        if depths is None:
            depths = _thread_state.depths = {}
        if depths.get(key, 0):
            depths[key] += 1
            try:
                yield
            finally:
                depths[key] -= 1
            return

        strict = _existing_only.get()
        if strict:
            handle, lock_path, original_identity = _existing_lock(root, workspace_id)
        else:
            lock_dir = Path(root) / ".workspace-mutation-locks"
            lock_dir.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256(str(workspace_id).encode("utf-8")).hexdigest()
            handle = (lock_dir / f"{digest}.lock").open("a+b")
        try:
            try:
                _lock_file(handle, initialize=not strict)
            except OSError:
                if strict:
                    raise ReadOnlyCoordinationUnavailable() from None
                raise
            if strict:
                try:
                    current = lock_path.lstat()
                    if ((current.st_dev, current.st_ino) != original_identity
                            or not stat.S_ISREG(current.st_mode)
                            or getattr(current, 'st_file_attributes', 0) & 0x400):
                        raise ReadOnlyCoordinationUnavailable()
                except OSError:
                    raise ReadOnlyCoordinationUnavailable() from None
            depths[key] = 1
            try:
                yield
            finally:
                depths.pop(key, None)
                try:
                    _unlock_file(handle)
                except OSError:
                    if strict:
                        raise ReadOnlyCoordinationUnavailable() from None
                    raise
        finally:
            try:
                handle.close()
            except OSError:
                if strict:
                    raise ReadOnlyCoordinationUnavailable() from None
                raise


def _lock_file(handle, *, initialize=True) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        # A Windows byte-range lock also denies reads from that byte. Inspect
        # file metadata rather than reading another process's locked byte;
        # the second writer must wait in locking(), not fail before acquiring.
        if os.fstat(handle.fileno()).st_size == 0:
            if not initialize:
                raise ReadOnlyCoordinationUnavailable()
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)


def _unlock_file(handle) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
