"""V2 passive host environment inventory. No imports of model code or weight loads."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import stat
import struct
import time
from pathlib import Path
from threading import Event

from .discovery_probes import MAX_DEPTH, MAX_ENTRIES, MAX_FILES, gguf_metadata, infer_family
from .discovery_types import EnvironmentModelFile, EnvironmentScanRoot, safe_local_path

MAX_METADATA_BYTES = 256 * 1024
MAX_ROOTS = 32


def common_model_roots(*, home: Path | None = None, environ=None, system: str | None = None) -> list[str]:
    """Fixed Windows model locations, never drives, registry, PATH or recursive home scans."""
    if (system or platform.system()) != 'Windows':
        return []
    home = home or Path.home()
    environ = os.environ if environ is None else environ
    roots = [home / '.lmstudio' / 'models', home / '.cache' / 'lm-studio' / 'models',
             home / '.cache' / 'huggingface' / 'hub', home / '.ollama' / 'models',
             home / 'ComfyUI' / 'models', home / 'Documents' / 'ComfyUI' / 'models',
             home / 'ComfyUI_windows_portable' / 'ComfyUI' / 'models',
             home / 'stable-diffusion-webui' / 'models' / 'Stable-diffusion']
    for key in ('OLLAMA_MODELS', 'HF_HUB_CACHE', 'HUGGINGFACE_HUB_CACHE'):
        if environ.get(key): roots.append(Path(environ[key]))
    if environ.get('HF_HOME'): roots.append(Path(environ['HF_HOME']) / 'hub')
    result = []
    for root in roots:
        try:
            value = safe_local_path(str(root))
            if os.path.normcase(value) not in {os.path.normcase(v) for v in result}: result.append(value)
        except (ValueError, OSError):
            continue
    return result[:16]


def environment_roots(configured: list[str], include_common: bool = True) -> list[dict]:
    roots, seen = [], set()
    for source, paths in [('CONFIGURED', configured), ('COMMON', common_model_roots() if include_common else [])]:
        for path in paths:
            key = os.path.normcase(path)
            if key in seen: continue
            seen.add(key)
            roots.append(EnvironmentScanRoot(path=path, source=source).model_dump())
    return roots[:MAX_ROOTS]


def _metadata_bytes(path: Path, limit: int, *, safetensors_header: bool = False) -> tuple[bytes, os.stat_result]:
    """Check links twice and use no-follow open where supported; read only bounded metadata."""
    safe_local_path(str(path))
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(descriptor, 'rb') as file:
        facts = os.fstat(file.fileno())
        if not stat.S_ISREG(facts.st_mode): raise ValueError('not a regular file')
        safe_local_path(str(path))
        if safetensors_header:
            prefix = file.read(8)
            length = struct.unpack('<Q', prefix)[0] if len(prefix) == 8 else 0
            return prefix + (file.read(length) if 2 <= length <= limit else b''), facts
        return file.read(limit), facts


def safetensors_metadata(path: Path) -> dict:
    """Inspect the bounded JSON header. Never deserialize tensors or pickle formats."""
    result = {'file_exists': False, 'header_valid': False}
    try:
        data, facts = _metadata_bytes(path, MAX_METADATA_BYTES, safetensors_header=True)
        result.update(file_exists=True, size=facts.st_size, modified_ns=facts.st_mtime_ns)
        if len(data) < 8: return result
        length = struct.unpack('<Q', data[:8])[0]
        if not 2 <= length <= MAX_METADATA_BYTES or 8 + length > len(data): return result
        def unique_pairs(pairs):
            value = {}
            for key, item in pairs:
                if key in value: raise ValueError('duplicate key')
                value[key] = item
            return value
        header = json.loads(data[8:8 + length].decode('utf-8'), object_pairs_hook=unique_pairs)
        if not isinstance(header, dict) or not header or len(header) > 4096: return result
        tensors, intervals = 0, []
        widths = {'BOOL':1,'U8':1,'I8':1,'F8_E4M3':1,'F8_E5M2':1,'I16':2,'U16':2,'F16':2,'BF16':2,
                  'I32':4,'U32':4,'F32':4,'I64':8,'U64':8,'F64':8}
        for name, value in header.items():
            if name == '__metadata__':
                if not isinstance(value, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in value.items()): return result
                continue
            if not isinstance(value, dict): return result
            shape, offsets = value.get('shape'), value.get('data_offsets')
            if not isinstance(shape, list) or len(shape) > 16 or not all(type(n) is int and 0 <= n <= 2**40 for n in shape): return result
            if not isinstance(offsets, list) or len(offsets) != 2 or not all(type(n) is int for n in offsets): return result
            begin, end = offsets
            if not 0 <= begin <= end <= facts.st_size - 8 - length: return result
            if not isinstance(value.get('dtype'), str) or value['dtype'] not in widths: return result
            elements = 1
            for dimension in shape: elements *= dimension
            if elements * widths[value['dtype']] != end - begin: return result
            intervals.append((begin, end)); tensors += 1
        cursor = 0
        for begin, end in sorted(intervals):
            if begin != cursor: return result
            cursor = end
        if not tensors or cursor != facts.st_size - 8 - length: return result
        result.update(header_valid=True, tensor_count=tensors)
    except (OSError, ValueError, UnicodeError, RecursionError, struct.error):
        pass
    return result


def diffusion_metadata(path: Path) -> dict:
    """A Diffusers model_index is metadata, never an instruction to import its classes."""
    result = {'file_exists': False, 'header_valid': False}
    try:
        data, facts = _metadata_bytes(path, MAX_METADATA_BYTES + 1)
        result.update(file_exists=True, size=facts.st_size, modified_ns=facts.st_mtime_ns)
        if len(data) > MAX_METADATA_BYTES: return result
        payload = json.loads(data)
        name = payload.get('_class_name') if isinstance(payload, dict) else None
        if isinstance(name, str) and 0 < len(name) <= 128 and name.isidentifier():
            result.update(header_valid=True, pipeline_class=name)
    except (OSError, ValueError, UnicodeError, RecursionError):
        pass
    return result


def scan_environment_files(roots: list[dict], cancel: Event, deadline: float, errors: list[dict]):
    """Shared global entry/file/depth budgets. Unreadable subtrees do not hide other roots."""
    entries = files = 0
    seen = set()
    for root in roots:
        if cancel.is_set(): root['status'] = 'CANCELLED'; continue
        if time.monotonic() >= deadline or entries >= MAX_ENTRIES or files >= MAX_FILES:
            root['status'] = 'BOUNDED'; continue
        try:
            base = Path(safe_local_path(root['path']))
            if not base.exists(): root['status'] = 'NOT_FOUND'; continue
            if not base.is_dir(): raise ValueError('not directory')
        except ValueError:
            root['status'] = 'REJECTED'; errors.append({'code':'LOCAL_AI_ROOT_REJECTED','root':root['path']}); continue
        except OSError:
            root['status'] = 'UNREADABLE'; errors.append({'code':'LOCAL_AI_ROOT_UNREADABLE','root':root['path']}); continue
        root['status'] = 'SCANNED'
        stack = [(base, 0)]
        while stack:
            if cancel.is_set(): root['status'] = 'CANCELLED'; break
            if time.monotonic() >= deadline or entries >= MAX_ENTRIES or files >= MAX_FILES:
                root['status'] = 'BOUNDED'; break
            directory, depth = stack.pop()
            try:
                safe_local_path(str(directory))
                with os.scandir(directory) as children:
                    for item in children:
                        if cancel.is_set() or time.monotonic() >= deadline or entries >= MAX_ENTRIES or files >= MAX_FILES:
                            root['status'] = 'CANCELLED' if cancel.is_set() else 'BOUNDED'; break
                        entries += 1
                        try:
                            facts = item.stat(follow_symlinks=False)
                            if item.is_symlink() or (getattr(facts, 'st_file_attributes', 0) & 0x400): continue
                            if item.is_dir(follow_symlinks=False):
                                if depth < MAX_DEPTH: stack.append((Path(item.path), depth + 1))
                                else: root['status'] = 'BOUNDED'
                                continue
                            if not item.is_file(follow_symlinks=False): continue
                            path = Path(item.path)
                            kind = {'.gguf':'GGUF', '.safetensors':'SAFETENSORS'}.get(path.suffix.casefold())
                            if path.name == 'model_index.json': kind = 'DIFFUSERS'
                            if not kind: continue
                            canonical = safe_local_path(str(path))
                            if os.path.normcase(canonical) in seen: continue
                            seen.add(os.path.normcase(canonical)); files += 1
                            inspect = {'GGUF':gguf_metadata, 'SAFETENSORS':safetensors_metadata, 'DIFFUSERS':diffusion_metadata}[kind]
                            evidence = inspect(path)
                            if not evidence.get('file_exists'):
                                errors.append({'code':'LOCAL_AI_MODEL_FILE_UNREADABLE','root':root['path']}); continue
                            family, capabilities = infer_family(path.parent.name if kind == 'DIFFUSERS' else path.name)
                            yield EnvironmentModelFile(id='file-' + hashlib.sha256(os.path.normcase(canonical).encode()).hexdigest()[:24],
                                path=canonical, name=path.parent.name if kind == 'DIFFUSERS' else path.name, format=kind,
                                source=root['source'], root=root['path'], size_bytes=evidence['size'], modified_ns=evidence['modified_ns'],
                                header_valid=evidence['header_valid'], family=family, declared_capabilities=capabilities,
                                notes=['METADATA_ONLY', 'RUNTIME_BINDING_REQUIRED', *([] if evidence['header_valid'] else ['HEADER_NOT_VERIFIED'])]).model_dump()
                        except (OSError, ValueError):
                            root['status'] = 'UNREADABLE'
            except (OSError, ValueError):
                root['status'] = 'UNREADABLE'
        if root['status'] == 'UNREADABLE': errors.append({'code':'LOCAL_AI_ROOT_UNREADABLE','root':root['path']})
    if any(root['status'] == 'BOUNDED' for root in roots): errors.append({'code':'LOCAL_AI_FILESYSTEM_BUDGET_REACHED'})


def windows_acceleration_components() -> dict:
    """Trusted system DLL presence only; never load CUDA, DirectML or user model code."""
    unknown = {'status':'NOT_RUN','source':'NOT_RUN','inference_verified':False}
    result = {'cuda':dict(unknown), 'directml':dict(unknown)}
    if platform.system() != 'Windows': return result
    try:
        import ctypes
        from ctypes import wintypes
        # Only the OS API already used by HardwareInventory; no PATH-based DLL lookup.
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        query = kernel32.GetSystemDirectoryW
        query.argtypes = [wintypes.LPWSTR, wintypes.UINT]
        query.restype = wintypes.UINT
        buffer = ctypes.create_unicode_buffer(32768)
        length = query(buffer, len(buffer))
        if not 0 < length < len(buffer): raise OSError('system directory unavailable')
        directory = Path(safe_local_path(buffer.value))
        for key, filename in [('cuda','nvcuda.dll'), ('directml','DirectML.dll')]:
            path = Path(safe_local_path(str(directory / filename)))
            result[key] = {'status':'COMPONENT_FOUND_NOT_VERIFIED' if path.is_file() else 'NOT_FOUND',
                           'source':'WINDOWS_SYSTEM_COMPONENT_METADATA','inference_verified':False}
    except (OSError, ValueError, AttributeError):
        for key in result: result[key] = {'status':'NOT_VERIFIED','source':'WINDOWS_SYSTEM_COMPONENT_METADATA','inference_verified':False}
    return result
