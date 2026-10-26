"""Request-local preventive input and JSON-complexity admission for usages.

Only readers calling ``read`` are covered. These limits bound encoded input and
JSON shape before the original owner's decoder runs; they are not a process RSS
limit. No filesystem writes, permission cache, or replacement owner live here.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
import hashlib
import os
import re
import stat
import time

_active = ContextVar('studio_usage_read_budget', default=None)
_boundary = re.compile(br'[\s{}\[\],:"]')
_non_space = re.compile(br'\S')
_reserved_windows = re.compile(r'(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])', re.I)


class UsageBudgetError(RuntimeError):
    def __init__(self):
        super().__init__('STUDIO_USAGE_RESOURCE_UNAVAILABLE')


def _read_checkpoint(stage, path):
    """Deterministic synthetic-test barrier; no production callback or I/O."""


def _checkpoint(stage, path):
    try:
        _read_checkpoint(stage, path)
    except OSError:
        # A blocked synthetic competing writer is an unavailable observation,
        # never a successful mutation or an ignored test-hook failure.
        raise UsageBudgetError() from None


def _fingerprint(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _regular(info):
    return stat.S_ISREG(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400


@lru_cache(maxsize=1)
def _windows_read_api():
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.GetFileType.argtypes = [wintypes.HANDLE]
    kernel.GetFileType.restype = wintypes.DWORD
    kernel.GetFileInformationByHandleEx.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                  ctypes.c_void_p, wintypes.DWORD]
    kernel.GetFileInformationByHandleEx.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    return kernel


def _open_windows_read(path):
    import ctypes
    from ctypes import wintypes
    import msvcrt
    # Only ordinary absolute drive paths reach the native namespace prefix.
    # Ancestor-directory confinement/ABA remains the original owner's boundary.
    if (not path.is_absolute() or not re.fullmatch(r'[A-Za-z]:', path.drive)
            or any(ord(value) < 32 for value in str(path))):
        raise UsageBudgetError()
    for part in path.parts[1:]:
        if (part in {'.', '..'} or part.endswith(('.', ' ')) or ':' in part
                or _reserved_windows.fullmatch(part.split('.', 1)[0])):
            raise UsageBudgetError()
    kernel = _windows_read_api()
    # Deny direct writers, including writers already open before admission.
    # FILE_SHARE_DELETE retains the original atomic-replace owner protocol.
    handle = kernel.CreateFileW('\\\\?\\' + str(path), 0x80000000, 0x1 | 0x4,
                                None, 3, 0x00200000, None)
    if handle in (None, ctypes.c_void_p(-1).value):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if kernel.GetFileType(handle) != 1:  # FILE_TYPE_DISK, before any read.
            raise UsageBudgetError()
        attributes = (wintypes.DWORD * 2)()
        if not kernel.GetFileInformationByHandleEx(handle, 9, ctypes.byref(attributes),
                                                   ctypes.sizeof(attributes)):
            raise ctypes.WinError(ctypes.get_last_error())
        if attributes[0] & (0x400 | 0x10) or attributes[1]:
            raise UsageBudgetError()
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        handle = None  # The CRT descriptor now owns the native handle.
        try:
            return os.fdopen(descriptor, 'rb', buffering=0)
        except BaseException:
            os.close(descriptor)
            raise
    finally:
        if handle is not None:
            kernel.CloseHandle(handle)


def _open_read(path):
    if os.name == 'nt':
        try:
            return _open_windows_read(path)
        except (AttributeError, ImportError):
            raise UsageBudgetError() from None
    if os.name != 'posix':
        raise UsageBudgetError()
    # Admission must not block when a regular file is replaced with a FIFO,
    # nor follow a symlink installed between lstat and open.
    if not hasattr(os, 'O_NOFOLLOW') or not hasattr(os, 'O_NONBLOCK'):
        raise UsageBudgetError()
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        return os.fdopen(descriptor, 'rb', buffering=0)
    except BaseException:
        os.close(descriptor)
        raise


class UsageReadBudget:
    MAX_SCOPE_BYTES = 4 * 1024 * 1024
    MAX_BINARY_BYTES = 25 * 1024 * 1024
    MAX_READ_BYTES = 256 * 1024 * 1024
    MAX_READS = 8192
    MAX_SECONDS = 30
    READ_CHUNK_BYTES = 64 * 1024
    MAX_JSON_DEPTH = 64
    MAX_JSON_STRING_BYTES = 256 * 1024
    MAX_JSON_NUMBER_BYTES = 1024
    MAX_JSON_TOKENS = 100_000
    MAX_REQUEST_JSON_TOKENS = 64_000_000
    MAX_JSON_CACHED_SHAPES = 64

    def __init__(self):
        self.read_bytes = self.reads = 0
        self.json_tokens = self.json_documents = self.json_input_bytes = 0
        # Shape metadata only: no paths, raw/decoded documents, or permissions.
        # The small cache retains only bounded digest/limit/count metadata.
        self._json_shapes = {}
        self.deadline = time.monotonic() + self.MAX_SECONDS

    def check(self):
        if time.monotonic() > self.deadline:
            raise UsageBudgetError()

    def snapshot(self):
        """Internal diagnostics only: no file names, identities, or content."""
        return {'reads': self.reads, 'read_bytes': self.read_bytes,
                'json_tokens': self.json_tokens, 'json_documents': self.json_documents,
                'json_input_bytes': self.json_input_bytes}

    def _preflight_json(self, data):
        """Bound shape without building a JSON object graph or decoding strings.

        This is admission, not a second syntax parser. The original owner still
        validates syntax, duplicate-key policy and schema. Raw numeric JSON is
        accepted, preserving the existing read()->str contract.
        """
        position = depth = tokens = 0
        size = len(data)
        self.json_input_bytes += size
        shape_key = (hashlib.sha256(data).digest(), self.MAX_JSON_DEPTH,
                     self.MAX_JSON_STRING_BYTES, self.MAX_JSON_NUMBER_BYTES, self.MAX_JSON_TOKENS)
        cached_tokens = self._json_shapes.get(shape_key)
        if cached_tokens is not None:
            self._json_shapes.pop(shape_key)
            self._json_shapes[shape_key] = cached_tokens
            remaining = max(0, self.MAX_REQUEST_JSON_TOKENS - self.json_tokens)
            self.json_tokens += min(cached_tokens, remaining + 1)
            if cached_tokens > remaining:
                raise UsageBudgetError()
            self.check()
            self.json_documents += 1
            return
        while position < size:
            value = data[position]
            if value in b' \t\r\n\v\f':
                match = _non_space.search(data, position)
                if match is None:
                    break
                position = match.start()
                value = data[position]
            tokens += 1
            self.json_tokens += 1
            if tokens > self.MAX_JSON_TOKENS or self.json_tokens > self.MAX_REQUEST_JSON_TOKENS:
                raise UsageBudgetError()
            if not tokens % 1024:
                self.check()
            if value == 34:
                start = position + 1
                end = start
                while True:
                    end = data.find(b'"', end)
                    if end < 0 or end - start > self.MAX_JSON_STRING_BYTES:
                        raise UsageBudgetError()
                    slash = end - 1
                    while slash >= start and data[slash] == 92:
                        slash -= 1
                    if (end - slash - 1) % 2 == 0:
                        break
                    end += 1
                position = end + 1
            elif value in b'{[':
                depth += 1
                if depth > self.MAX_JSON_DEPTH:
                    raise UsageBudgetError()
                position += 1
            elif value in b'}]':
                depth -= 1
                if depth < 0:
                    raise UsageBudgetError()
                position += 1
            elif value in b',:':
                position += 1
            else:
                match = _boundary.search(data, position)
                end = match.start() if match else size
                if end - position > self.MAX_JSON_NUMBER_BYTES:
                    raise UsageBudgetError()
                position = end
        self.check()
        if self.MAX_JSON_CACHED_SHAPES > 0:
            if len(self._json_shapes) >= self.MAX_JSON_CACHED_SHAPES:
                self._json_shapes.pop(next(iter(self._json_shapes)))
            self._json_shapes[shape_key] = tokens
        self.json_documents += 1

    def _read_bytes(self, path, limit, maximum):
        self.check()
        # Attempted reads and every actual chunk stay charged after a failure;
        # nested owner reads, reauthorization and retries cannot reset a scope.
        self.reads += 1
        if self.reads > self.MAX_READS:
            raise UsageBudgetError()
        if limit is None:
            limit = maximum
        if type(limit) is not int or limit <= 0:
            raise UsageBudgetError()
        limit = min(limit, maximum)
        remaining = self.MAX_READ_BYTES - self.read_bytes
        info = path.lstat()
        if not _regular(info) or info.st_size > min(limit, remaining):
            raise UsageBudgetError()
        _checkpoint('before_open', path)
        data = bytearray()
        try:
            handle = _open_read(path)
        except OSError:
            # Initial absence keeps the original owner's missing-file policy.
            # Disappearance after admission must never become an empty result.
            raise UsageBudgetError() from None
        with handle as stream:
            opened = os.fstat(stream.fileno())
            if not _regular(opened) or _fingerprint(opened) != _fingerprint(info):
                raise UsageBudgetError()
            # A changing file is rejected after each bounded chunk. Never ask
            # an untrusted stream to read the full document or an unbounded EOF.
            while len(data) < opened.st_size:
                self.check()
                count = min(self.READ_CHUNK_BYTES, opened.st_size - len(data),
                            limit - len(data), self.MAX_READ_BYTES - self.read_bytes)
                if count <= 0:
                    raise UsageBudgetError()
                chunk = stream.read(count)
                self.read_bytes += len(chunk)
                if not chunk or len(chunk) > count:
                    raise UsageBudgetError()
                data.extend(chunk)
                _checkpoint('after_chunk', path)
                if _fingerprint(os.fstat(stream.fileno())) != _fingerprint(opened):
                    raise UsageBudgetError()
            final = os.fstat(stream.fileno())
        # Also fence replacement of the path while its old handle was open.
        try:
            current = path.lstat()
        except FileNotFoundError:
            raise UsageBudgetError() from None
        if (not _regular(current) or _fingerprint(final) != _fingerprint(opened)
                or _fingerprint(current) != _fingerprint(opened)):
            raise UsageBudgetError()
        return data

    def read_binary(self, path, limit=None):
        """Binary integrity readers share the same cumulative request budget."""
        return bytes(self._read_bytes(path, limit, self.MAX_BINARY_BYTES))

    def read(self, path, limit=None):
        data = self._read_bytes(path, limit, self.MAX_SCOPE_BYTES)
        _checkpoint('before_json_preflight', path)
        self._preflight_json(data)
        try:
            return data.decode('utf-8')
        except UnicodeError:
            raise UsageBudgetError() from None


def current_usage_budget():
    return _active.get()


@contextmanager
def usage_read_budget(enabled=True, *, fresh=False):
    if not enabled or (_active.get() is not None and not fresh):
        yield _active.get()
        return
    budget = UsageReadBudget()
    token = _active.set(budget)
    try:
        yield budget
    finally:
        _active.reset(token)
