"""Windows-only, opt-in bounded asset reader; no owner is wired to it yet.

The caller owns the trusted asset root and its ancestors, the metadata and the
authority guard. Only its direct ``<asset-id>.bin`` child is admitted. This is
not descriptor confinement against hostile ancestor-directory ABA. Native
capability/type/identity failures never fall back to an ordinary pathname open.
"""
from __future__ import annotations

from contextlib import contextmanager
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import hashlib
import hmac
import os
from pathlib import Path
import re
import stat


MAX_BOUNDED_BYTES = 25 * 1024 * 1024  # Existing AssetLibraryService.MAX_BYTES.
CHUNK_BYTES = 65536
UNSUPPORTED = "ASSET_BOUNDED_READ_UNSUPPORTED"
LIMIT_INVALID = "ASSET_BOUNDED_READ_LIMIT_INVALID"
LIMIT = "ASSET_BOUNDED_READ_LIMIT"
INVALID = "ASSET_BOUNDED_CONTENT_INVALID"
UNAVAILABLE = "ASSET_BOUNDED_CONTENT_UNAVAILABLE"
_REPARSE, _DIRECTORY = 0x400, 0x10
_OPEN_REPARSE_POINT = 0x00200000
_GENERIC_READ, _READ_ATTRIBUTES, _SHARE_READ = 0x80000000, 0x80, 0x1
_MISSING_CAPABILITY_ERRORS = frozenset((1, 50, 87, 120))
_RESERVED = re.compile(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])", re.I)


class WindowsBoundedAssetError(ValueError):
    """A fixed, private-safe code; never an OS message, path or native handle."""
    def __init__(self, code):
        if code not in (UNSUPPORTED, LIMIT_INVALID, LIMIT, INVALID, UNAVAILABLE):
            raise ValueError("invalid bounded asset error code")
        self.code = code
        super().__init__(code)


def _fail(code, guard):
    # A revoked authority error takes priority over projecting a read error.
    guard()
    raise WindowsBoundedAssetError(code) from None


class _BasicInfo(ctypes.Structure):
    _fields_ = [(name, ctypes.c_int64) for name in
                ("creation", "access", "write", "change")] + [("attributes", wintypes.DWORD)]


class _StandardInfo(ctypes.Structure):
    _fields_ = [("allocation", ctypes.c_int64), ("size", ctypes.c_int64),
                ("links", wintypes.DWORD), ("delete_pending", ctypes.c_ubyte),
                ("directory", ctypes.c_ubyte)]


class _AttributeTagInfo(ctypes.Structure):
    _fields_ = [("attributes", wintypes.DWORD), ("tag", wintypes.DWORD)]


class _FileIdInfo(ctypes.Structure):
    _fields_ = [("volume", ctypes.c_uint64), ("file_id", ctypes.c_ubyte * 16)]


@dataclass(frozen=True)
class _Identity:
    volume: int
    file_id: bytes
    size: int
    creation: int
    write: int
    change: int


class _Kernel:
    def __init__(self):
        self.dll = ctypes.WinDLL("kernel32", use_last_error=True)
        self.dll.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                        ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                                        wintypes.HANDLE]
        self.dll.CreateFileW.restype = wintypes.HANDLE
        self.dll.GetFileType.argtypes = [wintypes.HANDLE]
        self.dll.GetFileType.restype = wintypes.DWORD
        self.dll.GetFileInformationByHandleEx.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                        ctypes.c_void_p, wintypes.DWORD]
        self.dll.GetFileInformationByHandleEx.restype = wintypes.BOOL
        self.dll.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                     ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        self.dll.ReadFile.restype = wintypes.BOOL
        self.dll.CloseHandle.argtypes = [wintypes.HANDLE]
        self.dll.CloseHandle.restype = wintypes.BOOL

    def open(self, path, access, guard):
        # Only a validated ordinary drive path reaches this method. The prefix
        # is derived internally; callers cannot supply an NT/device namespace.
        handle = self.dll.CreateFileW("\\\\?\\" + str(path), access, _SHARE_READ,
                                      None, 3, _OPEN_REPARSE_POINT, None)
        if handle in (None, ctypes.c_void_p(-1).value):
            _fail(UNAVAILABLE, guard)
        return handle

    def close(self, handle):
        return bool(self.dll.CloseHandle(handle))

    def _query(self, handle, kind, structure, guard):
        value = structure()
        if not self.dll.GetFileInformationByHandleEx(handle, kind, ctypes.byref(value),
                                                    ctypes.sizeof(value)):
            code = UNSUPPORTED if ctypes.get_last_error() in _MISSING_CAPABILITY_ERRORS else UNAVAILABLE
            _fail(code, guard)
        return value

    def identity(self, handle, guard):
        kind = self.dll.GetFileType(handle)
        if kind != 1:  # FILE_TYPE_DISK; pipes/characters/unknown never reach ReadFile.
            _fail(UNSUPPORTED if kind == 0 else INVALID, guard)
        attributes = self._query(handle, 9, _AttributeTagInfo, guard)
        standard = self._query(handle, 1, _StandardInfo, guard)
        basic = self._query(handle, 0, _BasicInfo, guard)
        identifier = self._query(handle, 18, _FileIdInfo, guard)
        if (attributes.attributes & (_REPARSE | _DIRECTORY) or attributes.tag
                or basic.attributes & (_REPARSE | _DIRECTORY) or standard.directory
                or standard.delete_pending or standard.size <= 0
                or not any(identifier.file_id)):
            _fail(INVALID, guard)
        return _Identity(identifier.volume, bytes(identifier.file_id), standard.size,
                         basic.creation, basic.write, basic.change)

    def read(self, handle, count, guard):
        buffer = ctypes.create_string_buffer(count)
        received = wintypes.DWORD()
        if not self.dll.ReadFile(handle, buffer, count, ctypes.byref(received), None):
            _fail(UNAVAILABLE, guard)
        if received.value > count:
            _fail(INVALID, guard)
        return buffer.raw[:received.value]


def _kernel_api():
    if os.name != "nt":
        raise WindowsBoundedAssetError(UNSUPPORTED)
    try:
        return _Kernel()
    except (AttributeError, OSError, ImportError):
        raise WindowsBoundedAssetError(UNSUPPORTED) from None


def windows_bounded_read_supported():
    """Native entry points exist; each opened volume must also pass queries."""
    try:
        _kernel_api()
    except WindowsBoundedAssetError:
        return False
    return True


def _validated_path(value, root, guard):
    if not isinstance(value, (str, Path)) or not isinstance(root, (str, Path)):
        _fail(INVALID, guard)
    path, directory = Path(value), Path(root)
    for item in (path, directory):
        if (not item.is_absolute() or not re.fullmatch(r"[A-Za-z]:", item.drive)
                or any(ord(c) < 32 for c in str(item))):
            _fail(INVALID, guard)
        for part in item.parts[1:]:
            if (part in (".", "..") or part.endswith((".", " ")) or ":" in part
                    or _RESERVED.fullmatch(part.split(".", 1)[0])):
                _fail(INVALID, guard)
    if (directory == Path(directory.anchor) or path.parent != directory
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,239}\.bin", path.name)):
        _fail(INVALID, guard)
    return path, directory


def _lstat(path, guard):
    try:
        return path.lstat()
    except OSError:
        _fail(UNAVAILABLE, guard)


def _root_identity(path, guard):
    info = _lstat(path, guard)
    if (not stat.S_ISDIR(info.st_mode) or info.st_ino <= 0
            or info.st_file_attributes & _REPARSE):
        _fail(INVALID, guard)
    return info.st_dev, info.st_ino


def _path_identity(path, guard):
    info = _lstat(path, guard)
    if (not stat.S_ISREG(info.st_mode) or info.st_ino <= 0
            or info.st_file_attributes & _REPARSE):
        _fail(INVALID, guard)
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


class WindowsAssetReadLease:
    """Thread-confined, single-use lease. No unbounded stream/handle is public."""
    def __init__(self, api, path, root, size, limit, digest, guard, read_budget=None):
        self._api, self._path, self._root = api, path, root
        self._size, self._limit, self._digest, self._guard = size, limit, digest, guard
        self._read_budget = read_budget
        self._handle, self._consumed = None, False

    def _admit(self):
        self._guard()
        self._root_before = _root_identity(self._root, self._guard)
        self._path_before = _path_identity(self._path, self._guard)
        if self._path_before[2] != self._size:
            _fail(INVALID, self._guard)
        self._guard()
        self._handle = self._api.open(self._path, _GENERIC_READ, self._guard)
        self._identity = self._api.identity(self._handle, self._guard)
        if self._identity.size != self._size:
            _fail(INVALID, self._guard)
        self.verify_current()

    def verify_current(self):
        self._guard()
        if self._handle is None:
            _fail(INVALID, self._guard)
        if (_root_identity(self._root, self._guard) != self._root_before
                or _path_identity(self._path, self._guard) != self._path_before
                or self._api.identity(self._handle, self._guard) != self._identity):
            _fail(INVALID, self._guard)
        probe = self._api.open(self._path, _READ_ATTRIBUTES, self._guard)
        try:
            if self._api.identity(probe, self._guard) != self._identity:
                _fail(INVALID, self._guard)
        except BaseException:
            self._api.close(probe)
            raise
        else:
            if not self._api.close(probe):
                _fail(UNAVAILABLE, self._guard)
        self._guard()

    def read_all(self):
        self._guard()
        if self._consumed or self._handle is None:
            _fail(INVALID, self._guard)
        self._consumed = True
        self.verify_current()
        parts, total, checksum = [], 0, hashlib.sha256()
        while total < (self._size if self._read_budget is not None else self._limit + 1):
            self._guard()
            count = min(CHUNK_BYTES, (self._size if self._read_budget is not None else self._limit + 1) - total)
            if self._read_budget is not None:
                count = self._read_budget.bounded_binary_allowance(count)
            block = self._api.read(self._handle, count, self._guard)
            if self._read_budget is not None:
                self._read_budget.charge_bounded_binary(len(block))
            self._guard()
            if not block:
                break
            total += len(block)
            if total > self._limit:
                _fail(INVALID, self._guard)
            parts.append(block)
            checksum.update(block)
        self.verify_current()
        if total != self._size or not hmac.compare_digest(checksum.hexdigest(), self._digest):
            _fail(INVALID, self._guard)
        data = b"".join(parts)
        self._guard()
        return data

    def _close(self, *, suppress=False):
        handle, self._handle = self._handle, None
        if handle is not None and not self._api.close(handle) and not suppress:
            _fail(UNAVAILABLE, self._guard)


@contextmanager
def open_windows_bounded_asset(path, *, trusted_root, expected_size, max_bytes,
                               expected_sha256, guard, read_budget=None):
    """Yield a native lease; caller authority exceptions remain unchanged.

    Missing API/volume capabilities fail closed. Only a local ordinary drive
    path is supported; UNC/device/ADS/DOS-device paths are not a fallback.
    Original owner/incarnation/approval checks remain the caller's job.
    """
    if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_BOUNDED_BYTES:
        raise WindowsBoundedAssetError(LIMIT_INVALID)
    if type(expected_size) is not int or not 0 < expected_size <= max_bytes:
        raise WindowsBoundedAssetError(LIMIT)
    if not callable(guard) or not isinstance(expected_sha256, str) or not re.fullmatch(r"[a-f0-9]{64}", expected_sha256):
        raise WindowsBoundedAssetError(INVALID)
    api = _kernel_api()
    guard()
    path, root = _validated_path(path, trusted_root, guard)
    lease = WindowsAssetReadLease(api, path, root, expected_size, max_bytes, expected_sha256, guard, read_budget)
    try:
        lease._admit()
        yield lease
    except BaseException:
        lease._close(suppress=True)
        raise
    else:
        lease._close()


def read_windows_bounded_asset(path, **kwargs):
    """Return verified bytes only after native close and the final authority fence."""
    with open_windows_bounded_asset(path, **kwargs) as lease:
        data = lease.read_all()
    kwargs["guard"]()
    return data
