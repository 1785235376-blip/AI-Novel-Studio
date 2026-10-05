"""Bounded, non-generating probes. All HTTP destinations are numeric loopback."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import struct
import time
import urllib.request
from pathlib import Path
from threading import Event
from typing import Any

from .discovery_types import local_endpoint, safe_local_path
from .service import _runtime_probe_opener

MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_MODELS = 512
MAX_FILES = 2000
MAX_ENTRIES = 5000
MAX_DEPTH = 3


class ProbeFailure(ValueError):
    pass


class LocalProbeClient:
    def __init__(self, timeout: float = 2.0):
        self.timeout = timeout
        self.open = _runtime_probe_opener().open

    def json(self, endpoint: str, path: str, *, body: dict | None = None) -> Any:
        endpoint = local_endpoint(endpoint)
        if not path.startswith('/') or path.startswith('//') or any(c in path for c in '?%#\\') or '..' in path.split('/'):
            raise ProbeFailure('LOCAL_AI_PROBE_PATH_REJECTED')
        request = urllib.request.Request(endpoint + path, data=json.dumps(body).encode() if body is not None else None,
                                         headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
        try:
            with self.open(request, timeout=self.timeout) as response:
                if not 200 <= response.status < 300:
                    raise ProbeFailure('LOCAL_AI_HTTP_UNAVAILABLE')
                deadline = time.monotonic() + self.timeout
                chunks = bytearray()
                read = getattr(response, 'read1', response.read)
                while True:
                    if time.monotonic() >= deadline:
                        raise ProbeFailure('LOCAL_AI_PROBE_TIMEOUT')
                    block = read(min(65536, MAX_RESPONSE_BYTES + 1 - len(chunks)))
                    if not block: break
                    chunks.extend(block)
                    if len(chunks) > MAX_RESPONSE_BYTES:
                        raise ProbeFailure('LOCAL_AI_RESPONSE_TOO_LARGE')
                payload = bytes(chunks)
                def reject_constant(_value): raise ValueError('non-finite JSON')
                result = json.loads(payload, parse_constant=reject_constant)
                if not isinstance(result, (dict, list)):
                    raise ProbeFailure('LOCAL_AI_INVALID_RESPONSE')
                return result
        except ProbeFailure:
            raise
        except TimeoutError as exc:
            raise ProbeFailure('LOCAL_AI_PROBE_TIMEOUT') from exc
        except Exception as exc:
            raise ProbeFailure('LOCAL_AI_PROBE_UNAVAILABLE') from exc


def candidate_id(runtime_type: str, endpoint: str, model_name: str, local_path: str = '') -> str:
    value = json.dumps([runtime_type, local_endpoint(endpoint), os.path.normcase(local_path) if local_path else model_name], ensure_ascii=False)
    return 'local-' + hashlib.sha256(value.encode()).hexdigest()[:24]


def infer_family(name: str) -> tuple[str, list[str]]:
    """Display declarations only. Naming alone never creates verified capability."""
    normalized = name.casefold().replace('\\', '/')
    for pattern, family, modality in (
        (r'qwen[-_. ]?image', 'QWEN_IMAGE', 'IMAGE'), (r'minimax[-_. ]?h3', 'MINIMAX_H3', 'VIDEO'),
        (r'seedvr2', 'SEEDVR2', 'RESTORATION'), (r'rife', 'RIFE', 'INTERPOLATION'),
        (r'z[-_. ]?image', 'ZIMAGE', 'IMAGE'), (r'flux', 'FLUX', 'IMAGE'),
        (r'wan(?=\d|[_ .-]|$)', 'WAN', 'VIDEO'), (r'ltx', 'LTX', 'VIDEO'), (r'qwen', 'QWEN', 'TEXT'),
        (r'stable[-_. ]?diffusion', 'STABLE_DIFFUSION', 'IMAGE'), (r'sdxl', 'STABLE_DIFFUSION', 'IMAGE'),
    ):
        if re.search(r'(?<![a-z])' + pattern, normalized):
            return family, [modality]
    return 'UNKNOWN', []


def gguf_metadata(path: Path) -> dict:
    """Header and limited metadata only: never tensor contents or whole model hashes."""
    result = {'file_exists': False, 'header_valid': False, 'metadata_complete': False}
    try:
        safe_local_path(str(path))
        if not path.is_file() or path.suffix.casefold() != '.gguf':
            return result
        stat = path.stat()
        result.update(file_exists=True, size=stat.st_size, modified_ns=stat.st_mtime_ns)
        with path.open('rb') as file:
            data = file.read(min(stat.st_size, 256 * 1024))
        if len(data) < 24 or data[:4] != b'GGUF':
            return result
        version, tensors, count = struct.unpack_from('<IQQ', data, 4)
        if version not in {2, 3} or not 0 < tensors < 10_000_000 or count > 100_000:
            return result
        result.update(header_valid=True, gguf_version=version, tensor_count=tensors)
        offset = 24
        def take(n):
            nonlocal offset
            if n < 0 or offset + n > len(data):
                raise ValueError('bounded metadata limit')
            value = data[offset:offset+n]; offset += n
            return value
        def string():
            length = struct.unpack('<Q', take(8))[0]
            if length > 65536: raise ValueError('string limit')
            return take(length).decode('utf-8')
        def value(kind, depth=0):
            if depth > 1: raise ValueError('array nesting')
            formats = {0:'B',1:'b',2:'H',3:'h',4:'I',5:'i',6:'f',7:'?',10:'Q',11:'q',12:'d'}
            if kind in formats:
                fmt = '<' + formats[kind]; return struct.unpack(fmt, take(struct.calcsize(fmt)))[0]
            if kind == 8: return string()
            if kind == 9:
                subtype, length = struct.unpack('<IQ', take(12))
                if length > 4096: raise ValueError('array limit')
                for _ in range(length): value(subtype, depth+1)
                return None
            raise ValueError('unknown type')
        for _ in range(min(count, 256)):
            key = string(); item = value(struct.unpack('<I', take(4))[0])
            if key in {'general.architecture', 'general.name', 'general.file_type'} or key.endswith('.context_length'):
                result[key] = item
        result['metadata_complete'] = count <= 256
    except (OSError, ValueError, struct.error, UnicodeError):
        pass
    return result


def scan_gguf_roots(roots: list[str], cancel: Event, deadline: float):
    entries = files = 0
    for root in roots:
        try:
            base = Path(safe_local_path(root))
            stack = [(base, 0)]
            while stack and not cancel.is_set() and time.monotonic() < deadline:
                directory, depth = stack.pop()
                with os.scandir(directory) as children:
                    for item in children:
                        entries += 1
                        if entries > MAX_ENTRIES or files >= MAX_FILES or cancel.is_set() or time.monotonic() >= deadline:
                            return
                        if item.is_symlink() or (getattr(item.stat(follow_symlinks=False), 'st_file_attributes', 0) & 0x400):
                            continue
                        if item.is_dir(follow_symlinks=False) and depth < MAX_DEPTH:
                            stack.append((Path(item.path), depth+1))
                        elif item.is_file(follow_symlinks=False) and item.name.casefold().endswith('.gguf'):
                            files += 1
                            yield Path(item.path)
        except (OSError, ValueError):
            continue


def host_hardware() -> dict:
    result = {'platform': platform.system(), 'architecture': platform.machine(), 'cpu': platform.processor() or platform.machine(),
              'ram_bytes': None, 'gpus': [], 'status': 'NOT_VERIFIED', 'notes': []}
    if platform.system() == 'Windows':
        try:
            from ..provider_runtime_v2_host_hardware_inventory import WindowsHostHardwareProbe
            facts = WindowsHostHardwareProbe().collect()
            result['ram_bytes'] = facts.physical_ram_bytes
            result['gpus'] = [{'vendor': {0x10DE:'NVIDIA',0x1002:'AMD',0x8086:'INTEL'}.get(g.pci_vendor_id, 'UNKNOWN'),
                               'name': getattr(g, 'name', '') or 'NOT_VERIFIED', 'dedicated_vram_bytes': g.dedicated_vram_bytes} for g in facts.gpus or ()]
            result['status'] = 'DETECTED'
        except Exception:
            result['notes'].append('HOST_HARDWARE_UNAVAILABLE')
    else:
        try: result['ram_bytes'] = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')
        except (ValueError, OSError, AttributeError): pass
        result['notes'].append('WINDOWS_GPU_INVENTORY_NOT_RUN')
    return result


def executable_metadata(path_value: str) -> dict:
    """Passive filesystem/Windows version-resource metadata, never --version."""
    result = {'executable_exists': False, 'version': None, 'version_source': 'NOT_VERIFIED', 'cuda_status': 'NOT_VERIFIED'}
    if not path_value: return result
    try:
        path = Path(safe_local_path(path_value))
        if not path.is_file(): return result
        result['executable_exists'] = True
        result['executable_size'] = path.stat().st_size
        # CUDA DLL presence is a component hint, not proof of a functional CUDA device.
        for index, sibling in enumerate(path.parent.iterdir()):
            if index >= 256: break
            if sibling.name.casefold().startswith('ggml-cuda') and sibling.suffix.casefold() == '.dll' and not sibling.is_symlink():
                result['cuda_status'] = 'COMPONENT_FOUND_NOT_VERIFIED'; break
        if platform.system() == 'Windows':
            import ctypes
            from ctypes import wintypes
            version = ctypes.WinDLL('version', use_last_error=True)
            size_function = version.GetFileVersionInfoSizeW
            size_function.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
            size_function.restype = wintypes.DWORD
            ignored = wintypes.DWORD()
            size = size_function(str(path), ctypes.byref(ignored))
            if not 0 < size <= 1024 * 1024: return result
            data = ctypes.create_string_buffer(size)
            get = version.GetFileVersionInfoW
            get.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
            get.restype = wintypes.BOOL
            if not get(str(path), 0, size, data): return result
            query = version.VerQueryValueW
            query.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.UINT)]
            query.restype = wintypes.BOOL
            pointer, length = ctypes.c_void_p(), wintypes.UINT()
            if query(data, '\\', ctypes.byref(pointer), ctypes.byref(length)) and length.value >= 52:
                fields = ctypes.cast(pointer, ctypes.POINTER(wintypes.DWORD))
                if fields[0] == 0xFEEF04BD:
                    high, low = fields[2], fields[3]
                    result.update(version=f'{high >> 16}.{high & 65535}.{low >> 16}.{low & 65535}', version_source='WINDOWS_FILE_VERSION_RESOURCE')
    except (OSError, ValueError, AttributeError):
        pass
    return result
