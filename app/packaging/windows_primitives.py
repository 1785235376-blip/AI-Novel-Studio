from __future__ import annotations

import ctypes
import getpass
import hashlib
import os
import socket
from ctypes import wintypes
from dataclasses import dataclass
from typing import Iterable

from .runtime_identity import ProcessIdentity, RuntimeIdentity, RuntimeRole


class SingleInstanceError(RuntimeError):
    pass


class PortConflictError(RuntimeError):
    pass


def product_mutex_name(product: str = "AI-Novel-Studio") -> str:
    user = f"{os.environ.get('USERDOMAIN', '')}\\{getpass.getuser()}"
    user_key = hashlib.sha256(user.encode("utf-8")).hexdigest()[:20]
    return f"Local\\{product}.Runtime.{user_key}"


class WindowsNamedMutex:
    ERROR_ALREADY_EXISTS = 183

    def __init__(self, name: str | None = None):
        self.name = name or product_mutex_name()
        self._handle: int | None = None
        self._owned = False

    def acquire(self) -> None:
        _require_windows()
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        handle = kernel32.CreateMutexW(None, True, self.name)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        if ctypes.get_last_error() == self.ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            raise SingleInstanceError("AI-Novel-Studio 已在当前用户会话中运行。")
        self._handle = int(handle)
        self._owned = True

    def release(self) -> None:
        if self._handle is None:
            return
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        if self._owned and not kernel32.ReleaseMutex(wintypes.HANDLE(self._handle)):
            raise ctypes.WinError(ctypes.get_last_error())
        kernel32.CloseHandle(wintypes.HANDLE(self._handle))
        self._handle = None
        self._owned = False

    def __enter__(self) -> "WindowsNamedMutex":
        self.acquire()
        return self

    def __exit__(self, *_: object) -> None:
        self.release()


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong), ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong), ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong), ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class _BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _BASIC_LIMIT_INFORMATION), ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class WindowsJobObject:
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
    PROCESS_TERMINATE = 0x0001
    PROCESS_SET_QUOTA = 0x0100

    def __init__(self, name: str | None = None):
        _require_windows()
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        handle = self._kernel32.CreateJobObjectW(None, name)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        self._handle: int | None = int(handle)
        limits = _EXTENDED_LIMIT_INFORMATION()
        limits.BasicLimitInformation.LimitFlags = self.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        ok = self._kernel32.SetInformationJobObject(
            wintypes.HANDLE(self._handle), self.JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(limits), ctypes.sizeof(limits),
        )
        if not ok:
            error = ctypes.get_last_error()
            self.close()
            raise ctypes.WinError(error)

    def assign_pid(self, pid: int) -> None:
        if self._handle is None:
            raise RuntimeError("Job Object is closed")
        access = self.PROCESS_TERMINATE | self.PROCESS_SET_QUOTA
        process = self._kernel32.OpenProcess(access, False, pid)
        if not process:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not self._kernel32.AssignProcessToJobObject(
                wintypes.HANDLE(self._handle), wintypes.HANDLE(process)
            ):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            self._kernel32.CloseHandle(wintypes.HANDLE(process))

    def terminate(self, exit_code: int = 1) -> None:
        if self._handle is not None and not self._kernel32.TerminateJobObject(
            wintypes.HANDLE(self._handle), exit_code
        ):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self) -> None:
        if self._handle is not None:
            self._kernel32.CloseHandle(wintypes.HANDLE(self._handle))
            self._handle = None


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260),
    ]


class WindowsProcessInspector:
    """Reads OS identity and joins it to launcher-owned nonce registration."""

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    TH32CS_SNAPPROCESS = 0x00000002
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
    WINDOWS_TO_UNIX_EPOCH_SECONDS = 11644473600

    def __init__(self):
        _require_windows()
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._registrations: dict[int, tuple[RuntimeRole, str, str]] = {}

    def register(self, pid: int, role: RuntimeRole, runtime: RuntimeIdentity) -> None:
        self._registrations[pid] = (
            role, runtime.runtime_instance_id, runtime.ownership_nonce_hash,
        )

    def unregister(self, pid: int) -> None:
        self._registrations.pop(pid, None)

    def inspect(self, pid: int) -> ProcessIdentity | None:
        registration = self._registrations.get(pid)
        if registration is None:
            return None
        process = self._kernel32.OpenProcess(self.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not process:
            return None
        try:
            executable = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(executable))
            if not self._kernel32.QueryFullProcessImageNameW(
                wintypes.HANDLE(process), 0, executable, ctypes.byref(size)
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            creation = wintypes.FILETIME();exit_time = wintypes.FILETIME()
            kernel = wintypes.FILETIME();user = wintypes.FILETIME()
            if not self._kernel32.GetProcessTimes(
                wintypes.HANDLE(process), ctypes.byref(creation), ctypes.byref(exit_time),
                ctypes.byref(kernel), ctypes.byref(user),
            ):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            self._kernel32.CloseHandle(wintypes.HANDLE(process))
        role, instance_id, nonce_hash = registration
        ticks = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
        return ProcessIdentity(
            role=role, pid=pid,
            creation_timestamp=ticks / 10_000_000 - self.WINDOWS_TO_UNIX_EPOCH_SECONDS,
            executable_path=executable.value, parent_pid=self._parent_pid(pid),
            runtime_instance_id=instance_id, ownership_nonce_hash=nonce_hash,
        )

    def _parent_pid(self, pid: int) -> int:
        snapshot = self._kernel32.CreateToolhelp32Snapshot(self.TH32CS_SNAPPROCESS, 0)
        if snapshot == self.INVALID_HANDLE_VALUE:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            entry = _PROCESSENTRY32W();entry.dwSize = ctypes.sizeof(entry)
            if not self._kernel32.Process32FirstW(wintypes.HANDLE(snapshot), ctypes.byref(entry)):
                raise ctypes.WinError(ctypes.get_last_error())
            while True:
                if entry.th32ProcessID == pid:
                    return int(entry.th32ParentProcessID)
                if not self._kernel32.Process32NextW(wintypes.HANDLE(snapshot), ctypes.byref(entry)):
                    break
        finally:
            self._kernel32.CloseHandle(wintypes.HANDLE(snapshot))
        raise ProcessLookupError(pid)


@dataclass
class LoopbackPortReservations:
    sockets: dict[RuntimeRole, socket.socket]
    ports: dict[RuntimeRole, int]

    def release(self, role: RuntimeRole) -> None:
        reserved = self.sockets.pop(role, None)
        if reserved is not None:
            reserved.close()

    def close(self) -> None:
        for reserved in list(self.sockets.values()):
            reserved.close()
        self.sockets.clear()


def reserve_loopback_ports(
    roles: Iterable[RuntimeRole] = (
        RuntimeRole.POSTGRESQL, RuntimeRole.BACKEND, RuntimeRole.FRONTEND,
    ), *, host: str = "127.0.0.1",
    requested: dict[RuntimeRole, int] | None = None,
) -> LoopbackPortReservations:
    if host != "127.0.0.1":
        raise ValueError("Packaged runtime listeners must bind only to 127.0.0.1")
    sockets: dict[RuntimeRole, socket.socket] = {}
    ports: dict[RuntimeRole, int] = {}
    try:
        for role in roles:
            reserved = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            reserved.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            try:
                reserved.bind((host, int((requested or {}).get(role, 0))))
                reserved.listen(1)
            except OSError as exc:
                reserved.close()
                raise PortConflictError(f"端口不可用：{role.value}") from exc
            sockets[role] = reserved
            ports[role] = int(reserved.getsockname()[1])
        if len(set(ports.values())) != len(ports):
            raise PortConflictError("运行时端口发生冲突")
        return LoopbackPortReservations(sockets=sockets, ports=ports)
    except Exception:
        for reserved in sockets.values():
            reserved.close()
        raise


def _require_windows() -> None:
    if os.name != "nt":
        raise OSError("Windows runtime ownership primitives require Windows")
