"""OS process adapter for the frozen Host-owned Test Worker spawn spec.

The only executable image is the current host interpreter. The only entrypoint
is the Host-owned bootstrap file resolved from this module's location. There
is no `command: str`, no argv from plugin data, and no generic runner.

Independent review of PR #24 found that copying `os.environ` (and inheriting
PYTHONPATH) let attacker-controlled `sitecustomize` / stdlib shadows execute
in the child. This adapter now uses isolated interpreter flags (`-I -S`) and
an explicit environment allowlist. That is Python startup isolation, not an
OS sandbox.
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
HOST_TEST_WORKER_BOOTSTRAP_NAME = "plugin_test_worker_bootstrap.py"

_OWNED_PIDS: set[int] = set()
_OWNED_LOCK = threading.Lock()

_POSIX_ENV_ALLOWLIST = ("TMPDIR", "LANG", "LC_ALL", "LC_CTYPE", "TZ")
_WINDOWS_ENV_ALLOWLIST = ("SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "TEMP", "TMP")


def host_owned_root() -> Path:
    """Application root derived from this Host-owned module, not cwd or env."""
    return Path(__file__).resolve().parents[1]


def host_test_worker_bootstrap_path() -> Path:
    path = Path(__file__).resolve().parent / HOST_TEST_WORKER_BOOTSTRAP_NAME
    if path.name != HOST_TEST_WORKER_BOOTSTRAP_NAME or not path.is_file():
        raise RuntimeError("HOST_TEST_WORKER_BOOTSTRAP_INVALID")
    return path


def host_test_worker_argv() -> tuple[str, ...]:
    """Frozen argv after the interpreter. Callers cannot replace these."""
    return ("-I", "-S", "-u", str(host_test_worker_bootstrap_path()))


# Import-time snapshot used by tests that assert the frozen flag prefix.
HOST_TEST_WORKER_ARGV: tuple[str, ...] = ("-I", "-S", "-u")


def build_host_test_worker_environment() -> dict[str, str]:
    """Explicit allowlist. Parent PYTHON* variables are never copied."""
    names = _WINDOWS_ENV_ALLOWLIST if os.name == "nt" else _POSIX_ENV_ALLOWLIST
    env = _copy_allowlisted(os.environ, names)
    leaked = [key for key in env if key.upper().startswith("PYTHON")]
    if leaked:
        raise RuntimeError("HOST_TEST_WORKER_PYTHON_ENV_FORBIDDEN")
    return env


def _copy_allowlisted(source: Mapping[str, str], names: tuple[str, ...]) -> dict[str, str]:
    env: dict[str, str] = {}
    if os.name == "nt":
        lookup = {key.upper(): (key, value) for key, value in source.items()}
        for name in names:
            hit = lookup.get(name.upper())
            if hit is None:
                continue
            key, value = hit
            if key.upper().startswith("PYTHON"):
                continue
            env[key] = value
        return env
    for name in names:
        value = source.get(name)
        if value is None:
            continue
        if name.upper().startswith("PYTHON"):
            continue
        env[name] = value
    return env


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
    bootstrap = host_test_worker_bootstrap_path()
    root = host_owned_root()
    popen_kwargs: dict[str, object] = {
        "args": [sys.executable, *host_test_worker_argv()],
        "stdin": subprocess.PIPE,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "cwd": str(root),
        "env": build_host_test_worker_environment(),
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
