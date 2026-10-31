"""Minimal Windows DPAPI wrapper for small application-owned secrets.

Only the current-user scope is used (``CRYPTPROTECT_UI_FORBIDDEN`` with no
``CRYPTPROTECT_LOCAL_MACHINE``): the same Windows user principal can unseal the
blob, another user or a copied profile cannot. This module supplies the missing
protection primitive for the asset-query cursor signing key on hosts where the
POSIX ``dir_fd``/``O_NOFOLLOW``/``O_DIRECTORY`` contract is unavailable. It is
inert on non-Windows hosts and does not import ``WinDLL`` at module import time.
"""
from __future__ import annotations

import ctypes
import os

CRYPTPROTECT_UI_FORBIDDEN = 0x1
MAX_SECRET_BYTES = 64
MAX_ENTROPY_BYTES = 256
MAX_BLOB_BYTES = 4096


class DpapiUnavailable(RuntimeError):
    """DPAPI is not usable on this host or refused the requested operation."""


def available() -> bool:
    """Report whether the DPAPI binding can be used on this interpreter."""
    return os.name == "nt"


def _blob_buffer(data: bytes):
    buffer = ctypes.create_string_buffer(data, len(data))
    return buffer


def _crypt32():
    try:
        return ctypes.WinDLL("crypt32", use_last_error=True)
    except (AttributeError, OSError) as exc:  # pragma: no cover - non-Windows
        raise DpapiUnavailable("DPAPI_UNAVAILABLE") from exc


def _kernel32():
    try:
        return ctypes.WinDLL("kernel32", use_last_error=True)
    except (AttributeError, OSError) as exc:  # pragma: no cover - non-Windows
        raise DpapiUnavailable("DPAPI_UNAVAILABLE") from exc


_DATA_BLOB = None


def _structures():
    global _DATA_BLOB
    if _DATA_BLOB is not None:
        return _DATA_BLOB
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    _DATA_BLOB = DATA_BLOB
    return DATA_BLOB


def _input_blob(data: bytes):
    DATA_BLOB = _structures()
    buffer = _blob_buffer(data)
    return DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))), buffer


def _validate(data: object, *, limit: int) -> bytes:
    if type(data) is not bytes or not 1 <= len(data) <= limit:
        raise DpapiUnavailable("DPAPI_INPUT_INVALID")
    return data


def _seal(data: bytes) -> bytes:
    DATA_BLOB = _structures()
    crypt32 = _crypt32()
    input_blob, input_buffer = _input_blob(data)
    output_blob = DATA_BLOB()
    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(DATA_BLOB), ctypes.c_wchar_p, ctypes.POINTER(DATA_BLOB),
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(DATA_BLOB),
    ]
    crypt32.CryptProtectData.restype = ctypes.c_int
    ok = crypt32.CryptProtectData(ctypes.byref(input_blob), "PoemSeed app secret", None,
                                  None, None, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(output_blob))
    del input_buffer
    if not ok:
        raise DpapiUnavailable("DPAPI_PROTECT_FAILED")
    try:
        if not output_blob.pbData or output_blob.cbData <= 0 or output_blob.cbData > MAX_BLOB_BYTES:
            raise DpapiUnavailable("DPAPI_PROTECT_FAILED")
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        _kernel32().LocalFree(output_blob.pbData)


def protect(secret: bytes) -> bytes:
    """Seal one small secret for the current Windows user."""
    if not available():
        raise DpapiUnavailable("DPAPI_UNAVAILABLE")
    return _seal(_validate(secret, limit=MAX_SECRET_BYTES))


def unprotect(blob: bytes) -> bytes:
    """Unseal one blob produced by :func:`protect`, failing closed otherwise."""
    if not available():
        raise DpapiUnavailable("DPAPI_UNAVAILABLE")
    DATA_BLOB = _structures()
    crypt32 = _crypt32()
    input_blob, input_buffer = _input_blob(_validate(blob, limit=MAX_BLOB_BYTES))
    output_blob = DATA_BLOB()
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(DATA_BLOB), ctypes.c_void_p, ctypes.POINTER(DATA_BLOB),
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(DATA_BLOB),
    ]
    crypt32.CryptUnprotectData.restype = ctypes.c_int
    ok = crypt32.CryptUnprotectData(ctypes.byref(input_blob), None, None, None, None,
                                    CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(output_blob))
    del input_buffer
    if not ok:
        raise DpapiUnavailable("DPAPI_UNPROTECT_FAILED")
    try:
        if not output_blob.pbData or not 0 < output_blob.cbData <= MAX_SECRET_BYTES:
            raise DpapiUnavailable("DPAPI_UNPROTECT_FAILED")
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        _kernel32().LocalFree(output_blob.pbData)
