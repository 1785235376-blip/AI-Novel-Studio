"""Windows file change-time identity for tamper-evident receipt reads.

Windows stat exposes the creation time as st_ctime rather than the NTFS
ChangeTime, so an in-place write that keeps the size and restores mtime/atime is
invisible to Python metadata. GetFileInformationByHandleEx(FileBasicInfo)
exposes the real ChangeTime. This helper is read-only and returns None when the
platform or handle does not provide it, so callers keep their existing
fail-closed checks on every platform.

Defect: Windows receipt reads could not reject a same-size in-place rewrite with
restored timestamps (test_v2_windows_timeline_receipt_identity). Fix: include the
NTFS change time in the receipt snapshot on Windows.
"""
from __future__ import annotations

import ctypes
import os
import sys
from functools import lru_cache
from typing import Any

_FILE_READ_ATTRIBUTES = 0x0080
_SHARE_READ_WRITE_DELETE = 0x00000007
_OPEN_EXISTING = 3
_FILE_BASIC_INFO_CLASS = 0


@lru_cache(maxsize=1)
def _api() -> tuple[Any, Any, Any] | None:
    if sys.platform != "win32":
        return None
    from ctypes import wintypes

    class FILE_BASIC_INFO(ctypes.Structure):
        _fields_ = [
            ("CreationTime", ctypes.c_int64),
            ("LastAccessTime", ctypes.c_int64),
            ("LastWriteTime", ctypes.c_int64),
            ("ChangeTime", ctypes.c_int64),
            ("FileAttributes", wintypes.DWORD),
        ]

    kernel32 = ctypes.WinDLL("Kernel32.dll", use_last_error=True)
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.GetFileInformationByHandleEx.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
    ]
    kernel32.GetFileInformationByHandleEx.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    return kernel32, FILE_BASIC_INFO, wintypes


def _change_time_of_handle(handle: int) -> int | None:
    api = _api()
    if api is None or not handle or handle == -1:
        return None
    kernel32, file_basic_info, wintypes = api
    info = file_basic_info()
    ok = kernel32.GetFileInformationByHandleEx(
        wintypes.HANDLE(handle), _FILE_BASIC_INFO_CLASS, ctypes.byref(info), ctypes.sizeof(info))
    if not ok:
        return None
    return int(info.ChangeTime)


def change_time_ns(*, path: str | os.PathLike[str] | None = None, fd: int | None = None) -> int | None:
    """Return the NTFS change time (100 ns units) for a path or an open descriptor.

    Returns None on non-Windows platforms or when the identity cannot be read;
    callers must never treat None as proof of an unchanged file.
    """
    if (path is None) == (fd is None):
        raise ValueError("exactly one of path or fd is required")
    api = _api()
    if api is None:
        return None
    kernel32, _file_basic_info, wintypes = api
    if fd is not None:
        import msvcrt

        try:
            handle = msvcrt.get_osfhandle(fd)
        except OSError:
            return None
        return _change_time_of_handle(handle)
    handle = kernel32.CreateFileW(
        os.fspath(path), _FILE_READ_ATTRIBUTES, _SHARE_READ_WRITE_DELETE,
        None, _OPEN_EXISTING, 0, None)
    if handle is None or handle == wintypes.HANDLE(-1).value:
        return None
    try:
        return _change_time_of_handle(handle)
    finally:
        kernel32.CloseHandle(handle)
