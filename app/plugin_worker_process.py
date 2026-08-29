"""OS process adapter for the frozen Host-owned Test Worker spawn spec.

The only executable image is the current host interpreter. The only module
is `app.plugin_test_worker`. There is no `command: str`, no argv from plugin
data, and no generic runner. Windows vs POSIX differences stay here.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
from pathlib import Path
from typing import IO

from app.plugin_worker_protocol import MAX_STDERR_BYTES

HOST_TEST_WORKER_MODULE = "app.plugin_test_worker"
HOST_TEST_WORKER_ARGV: tuple[str, ...] = ("-u", "-m", HOST_TEST_WORKER_MODULE)

_OWNED_PIDS: set[int] = set()
_OWNED_LOCK = threading.Lock()
_REPO_ROOT = str(Path(__file__).resolve().parents[1])


class OwnedWorkerProcess:
    """Ownership-aware wrapper around one host-owned test worker Popen."""

    def __init__(self, proc: subprocess.Popen[bytes]):
        self.proc = proc
        self.pid = int(proc.pid)
        with _OWNED_LOCK:
            _OWNED_PIDS.add(self.pid)

    @property
    def stdin(self) -> IO[bytes]:
        assert self.proc.stdin is not None
        return self.proc.stdin

    @property
    def stdout(self) -> IO[bytes]:
        assert self.proc.stdout is not None
        return self.proc.stdout

    @property
    def stderr(self) -> IO[bytes]:
        assert self.proc.stderr is not None
        return self.proc.stderr

    def poll(self) -> int | None:
        return self.proc.poll()

    def wait(self, timeout: float | None = None) -> int:
        return self.proc.wait(timeout=timeout)


def owned_alive_pids() -> tuple[int, ...]:
    with _OWNED_LOCK:
        pids = tuple(_OWNED_PIDS)
    alive: list[int] = []
    for pid in pids:
        if _pid_alive(pid):
            alive.append(pid)
    return tuple(alive)


def spawn_host_test_worker() -> OwnedWorkerProcess:
    """Start the frozen host-owned test worker. Not a generic command runner."""
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = _REPO_ROOT if not existing else _REPO_ROOT + os.pathsep + existing
    popen_kwargs: dict[str, object] = {
        "args": [sys.executable, *HOST_TEST_WORKER_ARGV],
        "stdin": subprocess.PIPE,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "cwd": _REPO_ROOT,
        "env": env,
        "bufsize": 0,
    }
    if os.name == "posix":
        popen_kwargs["start_new_session"] = True
    proc = subprocess.Popen(**popen_kwargs)  # type: ignore[arg-type]
    return OwnedWorkerProcess(proc)


def terminate_owned_worker(owned: OwnedWorkerProcess, *, grace_s: float = 0.4) -> None:
    proc = owned.proc
    if proc.poll() is None:
        _terminate_tree(proc, grace_s=grace_s)
    _close_quietly(proc.stdin)
    _close_quietly(proc.stdout)
    _close_quietly(proc.stderr)
    with _OWNED_LOCK:
        _OWNED_PIDS.discard(owned.pid)


def drain_stderr_bounded(stream: IO[bytes], sink: bytearray, *, limit: int = MAX_STDERR_BYTES) -> None:
    try:
        while True:
            chunk = stream.read(256)
            if not chunk:
                return
            remaining = limit - len(sink)
            if remaining <= 0:
                continue
            sink.extend(chunk[:remaining])
    except (OSError, ValueError):
        return


def _terminate_tree(proc: subprocess.Popen[bytes], *, grace_s: float) -> None:
    if os.name == "posix":
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout=grace_s)
            return
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            return
        return
    proc.terminate()
    try:
        proc.wait(timeout=grace_s)
        return
    except subprocess.TimeoutExpired:
        pass
    proc.kill()
    try:
        proc.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        return


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "posix":
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True
    if os.name == "nt":  # pragma: no cover - exercised on Windows hosts
        try:
            import ctypes
            SYNCHRONIZE = 0x00100000
            handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return False
    return False


def _close_quietly(stream: IO[bytes] | None) -> None:
    if stream is None:
        return
    try:
        stream.close()
    except OSError:
        return
