from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
from typing import Callable, Protocol


@dataclass(frozen=True)
class ProcessEvidence:
    pid: int
    parent_pid: int | None
    created_at: datetime | None
    executable: str | None
    argv: tuple[str, ...] | None
    port: int | None


@dataclass(frozen=True)
class TerminationResult:
    status: str
    pid: int | None
    reason: str


class ProcessHandle(Protocol):
    def evidence(self, *, port: int | None, inspector: Callable[..., ProcessEvidence | None]) -> ProcessEvidence | None: ...
    def terminate(self) -> bool: ...
    def close(self) -> None: ...


class WindowsProcessHandle:
    def __init__(self, pid: int) -> None:
        import ctypes
        from ctypes import wintypes

        PROCESS_TERMINATE = 0x0001
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        SYNCHRONIZE = 0x00100000
        self._ctypes = ctypes
        self._wintypes = wintypes
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        self._kernel32.OpenProcess.restype = wintypes.HANDLE
        self.handle = self._kernel32.OpenProcess(
            PROCESS_TERMINATE | PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE,
            False,
            pid,
        )
        self.error = ctypes.get_last_error() if not self.handle else 0
        self.pid = pid

    def evidence(self, *, port: int | None, inspector: Callable[..., ProcessEvidence | None]) -> ProcessEvidence | None:
        if not self.handle:
            return None
        creation = self._wintypes.FILETIME()
        exit_time = self._wintypes.FILETIME()
        kernel_time = self._wintypes.FILETIME()
        user_time = self._wintypes.FILETIME()
        if not self._kernel32.GetProcessTimes(self.handle, self._ctypes.byref(creation), self._ctypes.byref(exit_time), self._ctypes.byref(kernel_time), self._ctypes.byref(user_time)):
            return None
        ticks = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
        created_at = datetime.fromtimestamp((ticks - 116444736000000000) / 10_000_000, tz=datetime.now().astimezone().tzinfo)
        size = self._wintypes.DWORD(32768)
        executable_buffer = self._ctypes.create_unicode_buffer(size.value)
        if not self._kernel32.QueryFullProcessImageNameW(self.handle, 0, executable_buffer, self._ctypes.byref(size)):
            return None
        adjacent = inspector(self.pid, port=port)
        if adjacent is None:
            return None
        return ProcessEvidence(
            pid=self.pid,
            parent_pid=adjacent.parent_pid,
            created_at=created_at,
            executable=executable_buffer.value,
            argv=adjacent.argv,
            port=adjacent.port,
        )

    def evidence_with_known_command(
        self,
        *,
        parent_pid: int,
        argv: tuple[str, ...],
        port: int | None,
    ) -> ProcessEvidence | None:
        return self.evidence(
            port=port,
            inspector=lambda pid, port=None: ProcessEvidence(
                pid=pid,
                parent_pid=parent_pid,
                created_at=None,
                executable=None,
                argv=argv,
                port=port,
            ),
        )

    def terminate(self) -> bool:
        if not self.handle or not self._kernel32.TerminateProcess(self.handle, 1):
            return False
        self._kernel32.WaitForSingleObject(self.handle, 5000)
        return True

    def exited(self) -> bool:
        if not self.handle:
            return True
        exit_code = self._wintypes.DWORD()
        if not self._kernel32.GetExitCodeProcess(self.handle, self._ctypes.byref(exit_code)):
            return False
        return exit_code.value != 259

    def close(self) -> None:
        if self.handle:
            self._kernel32.CloseHandle(self.handle)
            self.handle = None


def _canonical_path(value: str) -> str:
    return os.path.normcase(os.path.abspath(value))


def process_identity(
    *, run_id: str, role: str, evidence: ProcessEvidence
) -> dict[str, object]:
    if evidence.created_at is None or evidence.executable is None or evidence.argv is None:
        raise ValueError("complete process evidence is required")
    return {
        "run_id": run_id,
        "role": role,
        "pid": evidence.pid,
        "parent_pid": evidence.parent_pid,
        "creation_time": evidence.created_at.isoformat(),
        "executable": evidence.executable,
        "argv": list(evidence.argv),
        "port": evidence.port,
    }


def identity_matches(
    recorded: dict[str, object],
    current: ProcessEvidence | None,
    *,
    expected_run_id: str,
    expected_role: str,
) -> tuple[bool, str]:
    required = {"run_id", "role", "pid", "creation_time", "executable", "argv"}
    if not required.issubset(recorded) or current is None:
        return False, "INSUFFICIENT_IDENTITY"
    if recorded.get("run_id") != expected_run_id:
        return False, "RUN_ID_MISMATCH"
    if recorded.get("role") != expected_role:
        return False, "ROLE_MISMATCH"
    if recorded.get("pid") != current.pid:
        return False, "PID_MISMATCH"
    if current.created_at is None or current.executable is None or current.argv is None:
        return False, "CURRENT_IDENTITY_UNKNOWN"
    try:
        recorded_time = datetime.fromisoformat(str(recorded["creation_time"]))
    except (TypeError, ValueError):
        return False, "INVALID_CREATION_TIME"
    if abs((recorded_time - current.created_at).total_seconds()) > 0.01:
        return False, "CREATION_TIME_MISMATCH"
    if _canonical_path(str(recorded["executable"])) != _canonical_path(current.executable):
        return False, "EXECUTABLE_MISMATCH"
    argv = recorded.get("argv")
    if not isinstance(argv, list) or tuple(str(value) for value in argv) != current.argv:
        return False, "COMMAND_IDENTITY_MISMATCH"
    if recorded.get("port") != current.port:
        return False, "PORT_MISMATCH"
    parent_pid = recorded.get("parent_pid")
    if parent_pid is not None and parent_pid != current.parent_pid:
        return False, "LINEAGE_MISMATCH"
    return True, "MATCH"


def inspect_process(pid: int, *, port: int | None = None) -> ProcessEvidence | None:
    if pid <= 0:
        return None


def terminate_if_still_owned(
    recorded: dict[str, object],
    *,
    expected_run_id: str,
    expected_role: str,
    inspector: Callable[..., ProcessEvidence | None] = inspect_process,
    handle_factory: Callable[[int], ProcessHandle] = WindowsProcessHandle,
) -> TerminationResult:
    pid = recorded.get("pid")
    if not isinstance(pid, int) or pid <= 0:
        return TerminationResult("UNKNOWN_IDENTITY_FAIL_CLOSED", None, "INVALID_PID")
    if os.name != "nt":
        return TerminationResult("UNKNOWN_IDENTITY_FAIL_CLOSED", pid, "UNSUPPORTED_PLATFORM")

    handle = handle_factory(pid)
    raw_handle = getattr(handle, "handle", True)
    if not raw_handle:
        error = int(getattr(handle, "error", 0))
        if error == 87:
            return TerminationResult("ALREADY_EXITED", pid, "PROCESS_GONE")
        return TerminationResult("UNKNOWN_IDENTITY_FAIL_CLOSED", pid, f"OPEN_PROCESS_{error}")
    try:
        port = recorded.get("port")
        handle_bound = handle.evidence(port=port if isinstance(port, int) else None, inspector=inspector)
        if handle_bound is None:
            return TerminationResult("UNKNOWN_IDENTITY_FAIL_CLOSED", pid, "FINAL_IDENTITY_QUERY_FAILED")
        matched, reason = identity_matches(
            recorded,
            handle_bound,
            expected_run_id=expected_run_id,
            expected_role=expected_role,
        )
        if not matched:
            status = "REJECTED_PID_REUSE" if reason == "CREATION_TIME_MISMATCH" else "REJECTED_IDENTITY_MISMATCH"
            return TerminationResult(status, pid, reason)
        if not handle.terminate():
            exited = getattr(handle, "exited", lambda: False)
            if exited():
                return TerminationResult("ALREADY_EXITED", pid, "PROCESS_EXITED_DURING_TERMINATION")
            return TerminationResult("TERMINATION_FAILED", pid, "TERMINATE_PROCESS_FAILED")
        return TerminationResult("TERMINATED", pid, "MATCH")
    finally:
        handle.close()
    if os.name != "nt":
        return None
    script = (
        "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false);"
        f"$p=Get-CimInstance Win32_Process -Filter 'ProcessId={pid}' -ErrorAction Stop;"
        f"$g=Get-Process -Id {pid} -ErrorAction Stop;"
        "[pscustomobject]@{pid=[int]$p.ProcessId;parent_pid=[int]$p.ParentProcessId;"
        "creation_time=$g.StartTime.ToUniversalTime().ToString('o');"
        "executable=$p.ExecutablePath;command_line=$p.CommandLine}|ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
            check=True,
        )
        payload = json.loads(completed.stdout)
        command_line = str(payload["command_line"])
        # CommandLineToArgvW parsing is exposed by the standard library on Windows.
        import ctypes
        from ctypes import wintypes

        argc = ctypes.c_int()
        shell32 = ctypes.windll.shell32
        shell32.CommandLineToArgvW.restype = ctypes.POINTER(wintypes.LPWSTR)
        pointer = shell32.CommandLineToArgvW(command_line, ctypes.byref(argc))
        if not pointer:
            return None
        try:
            argv = tuple(pointer[index] for index in range(argc.value))
        finally:
            ctypes.windll.kernel32.LocalFree(pointer)
        return ProcessEvidence(
            pid=int(payload["pid"]),
            parent_pid=int(payload["parent_pid"]),
            created_at=datetime.fromisoformat(str(payload["creation_time"])),
            executable=str(payload["executable"]),
            argv=argv,
            port=port,
        )
    except (OSError, subprocess.SubprocessError, TypeError, ValueError, KeyError, json.JSONDecodeError):
        return None


def classify_owner(
    *,
    launcher_pid: int,
    listener: ProcessEvidence,
    processes: dict[int, ProcessEvidence],
    launch_time: datetime,
    selected_port: int,
    expected_executable: str,
    expected_entrypoint: str,
) -> tuple[str, tuple[int, ...]]:
    if (
        listener.created_at is None
        or listener.executable is None
        or listener.argv is None
        or listener.port is None
    ):
        return "UNKNOWN", ()
    if listener.created_at < launch_time or listener.port != selected_port:
        return "UNRELATED", (listener.pid,)
    if listener.executable.casefold() != expected_executable.casefold():
        return "UNRELATED", (listener.pid,)
    if not any(Path(value).name.casefold() == expected_entrypoint.casefold() for value in listener.argv):
        return "UNRELATED", (listener.pid,)
    chain: list[int] = []
    current: ProcessEvidence | None = listener
    seen: set[int] = set()
    while current is not None and current.pid not in seen:
        seen.add(current.pid)
        chain.append(current.pid)
        if current.pid == launcher_pid:
            return ("DIRECT" if len(chain) == 1 else "DESCENDANT"), tuple(chain)
        current = processes.get(current.parent_pid) if current.parent_pid else None
    return "UNRELATED", tuple(chain)
