"""Narrow Windows File fence for interrupted scope replacements.

This observes at most one matching name using the native name-filtered query;
it never enumerates other scopes, opens the candidate, claims its ownership,
charges bytes, deletes it or reconciles the project. Only original File
writers cooperating on the same host and scope lock are covered. Other file
names and other owners still require a separate capacity/recovery protocol.
"""
from __future__ import annotations

import os
from pathlib import Path


UNRECONCILED = 'EXPERIMENTAL_SCOPE_UNRECONCILED'


def reject_suspected_scope_residue(path: Path):
    # Preserve existing non-Windows behaviour; that combination is not
    # verified by this narrow fence and is not safe project admission.
    if os.name != 'nt':
        return
    import ctypes
    from ctypes import wintypes

    class FindData(ctypes.Structure):
        _fields_ = [('attributes', wintypes.DWORD),
                    ('creation', wintypes.FILETIME), ('access', wintypes.FILETIME),
                    ('write', wintypes.FILETIME), ('size_high', wintypes.DWORD),
                    ('size_low', wintypes.DWORD), ('reserved0', wintypes.DWORD),
                    ('reserved1', wintypes.DWORD), ('name', wintypes.WCHAR * 260),
                    ('short_name', wintypes.WCHAR * 14)]

    try:
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.FindFirstFileW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(FindData)]
        kernel.FindFirstFileW.restype = wintypes.HANDLE
        kernel.FindClose.argtypes = [wintypes.HANDLE]
        kernel.FindClose.restype = wintypes.BOOL
        name = os.path.abspath(os.fspath(path))
        # Extended-length syntax is derived from the server-owned absolute
        # path, never supplied as a client-selected device path.
        if name.startswith('\\\\'):
            name = '\\\\?\\UNC\\' + name[2:]
        else:
            name = '\\\\?\\' + name
        data = FindData()
        handle = kernel.FindFirstFileW(name + '.*.tmp', ctypes.byref(data))
        if handle in (None, ctypes.c_void_p(-1).value):
            error = ctypes.get_last_error()
            # No matching name, or the scope directory itself does not exist.
            if error in (2, 3):
                return
            raise ValueError(UNRECONCILED)
        if not kernel.FindClose(handle):
            raise ValueError(UNRECONCILED)
        raise ValueError(UNRECONCILED)
    except (AttributeError, OSError, ImportError):
        raise ValueError(UNRECONCILED) from None
