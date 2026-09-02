"""Windows AppContainer prototype for the Host-owned Test Worker.

Phase 2B adds a real OS security boundary around the existing Host-owned
test worker. It is not third-party plugin execution, not a generic spawn
API, and not a Job-Object-as-sandbox claim.

Non-Windows: raise WINDOWS_SANDBOX_UNAVAILABLE. Never fall back to an
unsandboxed process.

Windows: CreateAppContainerProfile + PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES.
Network capabilities are none. Job Object is resource / process-tree
containment only (KILL_ON_JOB_CLOSE, ActiveProcessLimit=1).

ACL changes are confined to the per-run staging directory. This module
never modifies the Python installation, repo root, user profile, or
system policy.

The Python runtime is *copied* into staging. Hardlinks are forbidden:
ACLing a hardlink would mutate the original installation.
"""

from __future__ import annotations

import os
import shutil
import socket
import sys
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from app.plugin_worker_process import (
    OwnedWorkerProcess,
    build_host_test_worker_environment,
    host_owned_root,
)
from app.plugin_worker_sandbox_errors import (
    PROCESS_MEMORY_LIMIT_BYTES,
    REASON_PYTHON_APPCONTAINER_COMPATIBILITY_BLOCKED,
    REASON_SANDBOX_ACL_FAILED,
    REASON_SANDBOX_JOB_ASSIGNMENT_FAILED,
    REASON_SANDBOX_LAUNCH_FAILED,
    REASON_SANDBOX_PROFILE_CREATE_FAILED,
    REASON_SANDBOX_SID_FAILED,
    REASON_SANDBOX_STAGING_FAILED,
    REASON_SANDBOX_TOKEN_VERIFICATION_FAILED,
    REASON_WINDOWS_SANDBOX_UNAVAILABLE,
    SandboxError,
)

__all__ = (
    "PROCESS_MEMORY_LIMIT_BYTES",
    "REASON_PYTHON_APPCONTAINER_COMPATIBILITY_BLOCKED",
    "REASON_SANDBOX_ACL_FAILED",
    "REASON_SANDBOX_JOB_ASSIGNMENT_FAILED",
    "REASON_SANDBOX_LAUNCH_FAILED",
    "REASON_SANDBOX_PROFILE_CREATE_FAILED",
    "REASON_SANDBOX_SID_FAILED",
    "REASON_SANDBOX_STAGING_FAILED",
    "REASON_SANDBOX_TOKEN_VERIFICATION_FAILED",
    "REASON_WINDOWS_SANDBOX_UNAVAILABLE",
    "STAGED_WORKER_FILES",
    "SandboxError",
    "SandboxLaunch",
    "live_appcontainer_profiles",
    "live_job_handles",
    "live_staging_directories",
    "spawn_sandboxed_host_test_worker",
)

PROFILE_NAME_PREFIX = "AI-Novel-Studio.TestWorker."
STAGED_WORKER_FILES = (
    "plugin_test_worker_bootstrap.py",
    "plugin_test_worker.py",
    "plugin_worker_protocol.py",
)
LIB_EXCLUDE = frozenset({
    "test",
    "tests",
    "idlelib",
    "turtledemo",
    "tkinter",
    "ensurepip",
    "venv",
    "distutils",
    "site-packages",
})
ENV_SANDBOX_IN = "ANS_SANDBOX_IN"
ENV_SANDBOX_OUT = "ANS_SANDBOX_OUT"
ENV_SANDBOX_TMP = "ANS_SANDBOX_TMP"
ENV_FORBIDDEN_READ = "ANS_PROBE_FORBIDDEN_READ"
ENV_FORBIDDEN_WRITE = "ANS_PROBE_FORBIDDEN_WRITE"
ENV_LOOPBACK_PORT = "ANS_PROBE_LOOPBACK_PORT"

_LIVE_LOCK = threading.Lock()
_LIVE_PROFILES: set[str] = set()
_LIVE_STAGING: set[str] = set()
_LIVE_JOBS: set[int] = set()


@dataclass
class SandboxLaunch:
    owned: OwnedWorkerProcess
    profile_name: str
    staging_root: Path
    app_dir: Path
    runtime_dir: Path
    in_dir: Path
    out_dir: Path
    tmp_dir: Path
    host_sentinel_dir: Path
    forbidden_read_path: Path
    forbidden_write_path: Path
    input_path: Path
    appcontainer_sid_present: bool
    token_is_appcontainer: bool
    staged_file_count: int
    staged_bytes: int
    memory_limit_bytes: int | None
    memory_limit_ready: bool
    loopback_port: int
    job_handle: int | None
    _cleanup: Callable[[], None] = field(repr=False)
    _closed: bool = False

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._cleanup()


def live_appcontainer_profiles() -> tuple[str, ...]:
    with _LIVE_LOCK:
        return tuple(sorted(_LIVE_PROFILES))


def live_staging_directories() -> tuple[str, ...]:
    with _LIVE_LOCK:
        return tuple(sorted(_LIVE_STAGING))


def live_job_handles() -> tuple[int, ...]:
    with _LIVE_LOCK:
        return tuple(sorted(_LIVE_JOBS))


def spawn_sandboxed_host_test_worker() -> SandboxLaunch:
    """Frozen Host-owned AppContainer spawn. No executable/args/env/cwd parameters."""
    if sys.platform != "win32":
        raise SandboxError(REASON_WINDOWS_SANDBOX_UNAVAILABLE)
    return _launch_windows_appcontainer()


def _require_windows() -> None:
    if sys.platform != "win32":
        raise SandboxError(REASON_WINDOWS_SANDBOX_UNAVAILABLE)


def _launch_windows_appcontainer() -> SandboxLaunch:
    _require_windows()
    from app.plugin_worker_windows_api import Win32

    win = Win32()
    run_id = uuid.uuid4().hex
    profile_name = PROFILE_NAME_PREFIX + run_id[:16]
    root = host_owned_root()
    staging_root = root / ".runtime" / "plugin-sandbox" / run_id / "staging"
    host_sentinel_dir = root / ".runtime" / "plugin-sandbox" / run_id / "host"
    sid = None
    job = None
    attr_state: dict[str, Any] = {}
    proc_info = None
    pipes: dict[str, int] = {}
    listener: socket.socket | None = None
    registered_profile = False
    registered_staging = False

    def cleanup() -> None:
        _cleanup_launch(
            win,
            proc_info=proc_info,
            job=job,
            attr_state=attr_state,
            pipes=pipes,
            sid=sid,
            profile_name=profile_name,
            registered_profile=registered_profile,
            staging_root=staging_root,
            host_sentinel_dir=host_sentinel_dir,
            registered_staging=registered_staging,
            listener=listener,
        )

    try:
        staging_root.mkdir(parents=True, exist_ok=False)
        host_sentinel_dir.mkdir(parents=True, exist_ok=False)
        with _LIVE_LOCK:
            _LIVE_STAGING.add(str(staging_root))
        registered_staging = True

        app_dir = staging_root / "app"
        runtime_dir = staging_root / "runtime"
        in_dir = staging_root / "in"
        out_dir = staging_root / "out"
        tmp_dir = staging_root / "tmp"
        for folder in (app_dir, runtime_dir, in_dir, out_dir, tmp_dir):
            folder.mkdir()

        _stage_worker_code(app_dir)
        staged_files, staged_bytes = _stage_python_runtime(runtime_dir)
        worker_count, worker_bytes = _count_tree(app_dir)
        staged_files += worker_count
        staged_bytes += worker_bytes

        input_path = in_dir / "input.txt"
        input_path.write_text("SANDBOX_INPUT_OK", encoding="utf-8")
        forbidden_read_path = host_sentinel_dir / "forbidden_read.txt"
        forbidden_write_path = host_sentinel_dir / "forbidden_write.txt"
        forbidden_read_path.write_text(uuid.uuid4().hex, encoding="utf-8")
        forbidden_write_path.write_text("UNCHANGED", encoding="utf-8")

        listener, loopback_port = _bind_loopback()

        sid = win.create_or_derive_profile(profile_name)
        with _LIVE_LOCK:
            _LIVE_PROFILES.add(profile_name)
        registered_profile = True

        # ACL only these staging paths. Never repo root, user profile, or the
        # original Python installation. host_sentinel_dir is intentionally omitted.
        win.grant_appcontainer_acl(str(staging_root), sid, execute=True, write=False)
        win.grant_appcontainer_acl(str(runtime_dir), sid, execute=True, write=False)
        win.grant_appcontainer_acl(str(app_dir), sid, execute=True, write=False)
        win.grant_appcontainer_acl(str(in_dir), sid, execute=False, write=False)
        win.grant_appcontainer_acl(str(out_dir), sid, execute=False, write=True)
        win.grant_appcontainer_acl(str(tmp_dir), sid, execute=False, write=True)

        python_exe = runtime_dir / "python.exe"
        bootstrap = app_dir / "plugin_test_worker_bootstrap.py"
        if not python_exe.is_file() or not bootstrap.is_file():
            raise SandboxError(REASON_SANDBOX_STAGING_FAILED)

        env = _sandbox_environment(
            in_dir=in_dir,
            out_dir=out_dir,
            tmp_dir=tmp_dir,
            forbidden_read=forbidden_read_path,
            forbidden_write=forbidden_write_path,
            loopback_port=loopback_port,
        )
        pipes = win.create_stdio_pipes()
        job, memory_ready = win.create_job_object()
        with _LIVE_LOCK:
            if job:
                _LIVE_JOBS.add(int(job))

        cmdline = win.quote_args([str(python_exe), "-I", "-S", "-u", str(bootstrap)])
        proc_info, attr_state = win.create_appcontainer_process(
            application=str(python_exe),
            cmdline=cmdline,
            cwd=str(staging_root),
            env=env,
            sid=sid,
            pipes=pipes,
        )
        win.assign_to_job(job, proc_info.hProcess)
        token_is_appcontainer, sid_present = win.verify_process_is_appcontainer(proc_info.hProcess)
        if not token_is_appcontainer:
            win.terminate_process(proc_info.hProcess)
            raise SandboxError(REASON_SANDBOX_TOKEN_VERIFICATION_FAILED)
        win.resume_thread(proc_info.hThread)
        try:
            win.close_handle(int(proc_info.hThread) if proc_info.hThread else 0)
        except Exception:
            pass
        proc_info.hThread = None

        owned = OwnedWorkerProcess(win.wrap_process(proc_info, pipes))
        return SandboxLaunch(
            owned=owned,
            profile_name=profile_name,
            staging_root=staging_root,
            app_dir=app_dir,
            runtime_dir=runtime_dir,
            in_dir=in_dir,
            out_dir=out_dir,
            tmp_dir=tmp_dir,
            host_sentinel_dir=host_sentinel_dir,
            forbidden_read_path=forbidden_read_path,
            forbidden_write_path=forbidden_write_path,
            input_path=input_path,
            appcontainer_sid_present=sid_present,
            token_is_appcontainer=token_is_appcontainer,
            staged_file_count=staged_files,
            staged_bytes=staged_bytes,
            memory_limit_bytes=PROCESS_MEMORY_LIMIT_BYTES if memory_ready else None,
            memory_limit_ready=memory_ready,
            loopback_port=loopback_port,
            job_handle=int(job) if job else None,
            _cleanup=cleanup,
        )
    except Exception:
        cleanup()
        raise


def _stage_worker_code(app_dir: Path) -> None:
    src_app = Path(__file__).resolve().parent
    for name in STAGED_WORKER_FILES:
        src = src_app / name
        if src.name != name or not src.is_file():
            raise SandboxError(REASON_SANDBOX_STAGING_FAILED)
        shutil.copy2(src, app_dir / name)
    (app_dir / "__init__.py").write_text("# host-owned staged worker package\n", encoding="utf-8")


def _stage_python_runtime(dest: Path) -> tuple[int, int]:
    """Copy interpreter + stdlib into staging. Never hardlink (ACL would leak)."""
    prefix = Path(getattr(sys, "base_prefix", sys.prefix))
    src_exe = Path(getattr(sys, "base_executable", "") or sys.executable)
    if not src_exe.is_file():
        src_exe = prefix / "python.exe"
    if not src_exe.is_file():
        raise SandboxError(REASON_PYTHON_APPCONTAINER_COMPATIBILITY_BLOCKED)
    try:
        shutil.copy2(src_exe, dest / "python.exe")
        for pattern in ("python*.dll", "vcruntime*.dll", "ucrtbase.dll", "python*.zip"):
            for item in prefix.glob(pattern):
                if item.is_file():
                    shutil.copy2(item, dest / item.name)
        lib = prefix / "Lib"
        if lib.is_dir():
            _copy_tree(lib, dest / "Lib", exclude=LIB_EXCLUDE)
        dlls = prefix / "DLLs"
        if dlls.is_dir():
            _copy_tree(dlls, dest / "DLLs", exclude=frozenset())
    except OSError as exc:
        raise SandboxError(REASON_PYTHON_APPCONTAINER_COMPATIBILITY_BLOCKED) from exc
    if not (dest / "python.exe").is_file():
        raise SandboxError(REASON_PYTHON_APPCONTAINER_COMPATIBILITY_BLOCKED)
    return _count_tree(dest)


def _copy_tree(src: Path, dst: Path, *, exclude: frozenset[str]) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for entry in src.iterdir():
        if entry.name in exclude or entry.name == "__pycache__":
            continue
        target = dst / entry.name
        if entry.is_dir():
            _copy_tree(entry, target, exclude=exclude)
        elif entry.is_file():
            shutil.copy2(entry, target)


def _count_tree(root: Path) -> tuple[int, int]:
    count = 0
    size = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name != "__pycache__"]
        for name in filenames:
            path = Path(dirpath) / name
            try:
                size += path.stat().st_size
            except OSError:
                continue
            count += 1
    return count, size


def _sandbox_environment(
    *,
    in_dir: Path,
    out_dir: Path,
    tmp_dir: Path,
    forbidden_read: Path,
    forbidden_write: Path,
    loopback_port: int,
) -> dict[str, str]:
    env = build_host_test_worker_environment()
    env["TEMP"] = str(tmp_dir)
    env["TMP"] = str(tmp_dir)
    env[ENV_SANDBOX_IN] = str(in_dir)
    env[ENV_SANDBOX_OUT] = str(out_dir)
    env[ENV_SANDBOX_TMP] = str(tmp_dir)
    env[ENV_FORBIDDEN_READ] = str(forbidden_read)
    env[ENV_FORBIDDEN_WRITE] = str(forbidden_write)
    env[ENV_LOOPBACK_PORT] = str(loopback_port)
    leaked = [key for key in env if key.upper().startswith("PYTHON")]
    if leaked:
        raise SandboxError(REASON_SANDBOX_LAUNCH_FAILED)
    return env


def _bind_loopback() -> tuple[socket.socket, int]:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(0.1)
    port = int(listener.getsockname()[1])
    return listener, port


def _cleanup_launch(
    win: Any,
    *,
    proc_info: Any,
    job: Any,
    attr_state: dict[str, Any],
    pipes: dict[str, int],
    sid: Any,
    profile_name: str,
    registered_profile: bool,
    staging_root: Path,
    host_sentinel_dir: Path,
    registered_staging: bool,
    listener: socket.socket | None,
) -> None:
    if proc_info is not None:
        try:
            win.terminate_process(proc_info.hProcess)
            win.wait_process(proc_info.hProcess, 1000)
        except Exception:
            pass
        try:
            if proc_info.hThread:
                win.close_handle(proc_info.hThread)
        except Exception:
            pass
        try:
            if proc_info.hProcess:
                win.close_handle(proc_info.hProcess)
        except Exception:
            pass
    if job:
        try:
            win.close_handle(job)
        except Exception:
            pass
        with _LIVE_LOCK:
            _LIVE_JOBS.discard(int(job))
    try:
        win.free_attribute_list(attr_state)
    except Exception:
        pass
    for handle in list(pipes.values()):
        try:
            win.close_handle(handle)
        except Exception:
            pass
    if listener is not None:
        try:
            listener.close()
        except OSError:
            pass
    if sid is not None:
        try:
            win.free_sid(sid)
        except Exception:
            pass
    if registered_profile:
        try:
            win.delete_profile(profile_name)
        except Exception:
            pass
        with _LIVE_LOCK:
            _LIVE_PROFILES.discard(profile_name)
    parent = staging_root.parent if staging_root.exists() else host_sentinel_dir.parent
    try:
        if parent.exists():
            shutil.rmtree(parent, ignore_errors=True)
    except OSError:
        pass
    if registered_staging:
        with _LIVE_LOCK:
            _LIVE_STAGING.discard(str(staging_root))
