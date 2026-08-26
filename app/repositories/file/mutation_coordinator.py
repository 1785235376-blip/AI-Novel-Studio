"""Workspace-scoped coordination for multi-file File backend mutations."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import os
from threading import RLock
from threading import local
from pathlib import Path

_guard = RLock()
_locks: dict[tuple[str, str], RLock] = {}
_thread_state = local()


def workspace_mutation_lock(root: Path, workspace_id: str) -> RLock:
    key = (str(Path(root).resolve()), str(workspace_id))
    with _guard:
        return _locks.setdefault(key, RLock())


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

        lock_dir = Path(root) / ".workspace-mutation-locks"
        lock_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(str(workspace_id).encode("utf-8")).hexdigest()
        handle = (lock_dir / f"{digest}.lock").open("a+b")
        try:
            _lock_file(handle)
            depths[key] = 1
            try:
                yield
            finally:
                depths.pop(key, None)
                _unlock_file(handle)
        finally:
            handle.close()


def _lock_file(handle) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        if handle.read(1) == b"":
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
