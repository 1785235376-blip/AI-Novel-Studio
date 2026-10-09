"""Ephemeral, principal-bound consent for the existing local discovery worker.

Planning uses bounded path metadata only. It never enumerates directories, opens
model contents, contacts a service, or collects hardware facts.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import platform
import stat
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from .discovery_environment import MAX_METADATA_BYTES, environment_roots
from .discovery_probes import MAX_MODELS, MAX_RESPONSE_BYTES
from .discovery_types import LocalRuntimeInput, safe_local_path

PREVIEW_LIMIT = 16
PREVIEW_TTL_SECONDS = 120
SCAN_BUDGET_SECONDS = 45
PLANNING_BUDGET_SECONDS = 5


def fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def require_guard(guard):
    try:
        if not callable(guard) or guard() is False:
            raise ValueError('revoked')
    except Exception as exc:
        raise ValueError('LOCAL_AI_SCOPE_REVOKED') from exc


def planning_check(guard=None, deadline=None):
    if guard is not None: require_guard(guard)
    if deadline is not None and time.monotonic() >= deadline:
        raise ValueError('LOCAL_AI_SCOPE_BUDGET_REACHED')


@contextmanager
def planning_lock(lock, guard, deadline):
    """Do not turn bounded metadata planning into an unbounded owner-lock wait."""
    planning_check(guard, deadline)
    if lock is None:
        yield
        return
    acquired = False
    try:
        while not acquired:
            planning_check(guard, deadline)
            acquired = lock.acquire(timeout=min(.05, max(0, deadline - time.monotonic())))
        planning_check(guard, deadline)
        yield
    finally:
        if acquired: lock.release()


def path_identity(value: str, *, guard=None, deadline=None) -> dict:
    """No contents or enumeration; reject links and non-regular filesystem objects."""
    planning_check(guard, deadline)
    if not isinstance(value, str) or not 0 < len(value) <= 2048 or len(Path(value).parts) > 128:
        raise ValueError('LOCAL_AI_SCOPE_INVALID')
    path = Path(safe_local_path(value))
    planning_check(guard, deadline)
    try:
        facts = path.stat(follow_symlinks=False)
    except FileNotFoundError:
        facts = None
    planning_check(guard, deadline)
    if facts is None: return {'path': str(path), 'exists': False}
    if not (stat.S_ISREG(facts.st_mode) or stat.S_ISDIR(facts.st_mode)):
        raise ValueError('LOCAL_AI_SCOPE_INVALID')
    return {'path': str(path), 'exists': True, 'device': facts.st_dev, 'inode': facts.st_ino,
            'mode': facts.st_mode, 'size': facts.st_size, 'modified_ns': facts.st_mtime_ns}


def probe_paths(runtime: dict) -> list[str]:
    if runtime['credential_required']:
        return []  # Existing scanner fails closed before any probe or file access.
    kind = runtime['type']
    if kind == 'OLLAMA': return ['/api/tags', '/api/version']
    if kind == 'COMFYUI': return ['/system_stats', '/object_info']
    if kind == 'AUTOMATIC1111': return ['/sdapi/v1/sd-models']
    if kind == 'LLAMA_CPP': return [runtime['health_endpoint'] or '/v1/models']
    if kind == 'OPENAI_COMPATIBLE_LOCAL':
        return ['/models' if runtime['endpoint'].endswith('/v1') else '/v1/models']
    return [runtime['health_endpoint']] if runtime['health_endpoint'] else []


def build_plan(runtimes: list[dict], settings: dict, include_common: bool, *, environment: bool,
               timeout: float, response_bytes: int = MAX_RESPONSE_BYTES, registrations: dict | None = None,
               guard=None, deadline=None) -> dict:
    planning_check(guard, deadline)
    if type(include_common) is not bool or not environment:
        raise ValueError('LOCAL_AI_SCOPE_INVALID')
    if not isinstance(timeout, (float, int)) or isinstance(timeout, bool) or not math.isfinite(timeout) or not 0 < timeout <= 2:
        raise ValueError('LOCAL_AI_SCOPE_INVALID')
    from . import discovery_environment as scanner
    if type(response_bytes) is not int or not 0 < response_bytes <= MAX_RESPONSE_BYTES:
        raise ValueError('LOCAL_AI_SCOPE_INVALID')
    if len(runtimes) > 20 or len(settings.get('scan_roots', [])) > 16:
        raise ValueError('LOCAL_AI_SCOPE_INVALID')
    validated, services, inspections, identities = [], [], [], {}

    def inspect(kind, path, entries, maximum):
        facts = path_identity(path, guard=guard, deadline=deadline)
        identities[facts['path']] = facts
        inspections.append({'kind': kind, 'path': facts['path'], 'max_entries': entries, 'max_bytes': maximum})
        return facts['path']

    for runtime in runtimes:
        planning_check(guard, deadline)
        identifier = runtime.get('id')
        if not isinstance(identifier, str) or not 0 < len(identifier) <= 256:
            raise ValueError('LOCAL_AI_SCOPE_INVALID')
        try:
            row = {'id': identifier, **LocalRuntimeInput.model_validate({key: value for key, value in runtime.items() if key != 'id'}).model_dump()}
        except (ValueError, TypeError) as exc:
            raise ValueError('LOCAL_AI_SCOPE_INVALID') from exc
        planning_check(guard, deadline)
        validated.append(row)
        services.append({**{key: row[key] for key in ('id', 'name', 'type', 'endpoint', 'management')},
                         'probe_paths': probe_paths(row)})
        if row['type'] == 'LLAMA_CPP' and not row['credential_required']:
            if row['model_path']:
                inspect('CONFIGURED_GGUF_HEADER', row['model_path'], 1, MAX_METADATA_BYTES)
            if row['executable']:
                inspect('EXECUTABLE_VERSION_RESOURCE', row['executable'], 1, 1024 * 1024)
                inspect('EXECUTABLE_DIRECTORY_SIBLINGS', str(Path(row['executable']).parent), 256, 0)
    for path in settings['scan_roots']: path_identity(path, guard=guard, deadline=deadline)
    registration_paths = {}
    runtime_ids = {row['id'] for row in validated}
    for identifier, record in (registrations or {}).items():
        planning_check(guard, deadline)
        if not record.get('enabled') or record.get('runtime_type') != 'LLAMA_CPP' or record.get('runtime_id') not in runtime_ids:
            continue
        if len(registration_paths) >= 2048: raise ValueError('LOCAL_AI_SCOPE_INVALID')
        path = inspect('REGISTERED_GGUF_HEADER', record.get('local_path', ''), 1, MAX_METADATA_BYTES)
        registration_paths[identifier] = {'path': path, 'runtime_id': record['runtime_id']}
    planning_check(guard, deadline)
    roots = environment_roots(settings['scan_roots'], include_common)
    planning_check(guard, deadline)
    for root in roots:
        root['path'] = inspect('RECURSIVE_MODEL_METADATA', root['path'], scanner.MAX_ENTRIES, scanner.MAX_METADATA_BYTES + 8)
    public = {'schema_version': 1, 'execution_scope': 'BACKEND_HOST',
              'include_common_model_dirs': include_common, 'services': services,
              'roots': [{key: root[key] for key in ('path', 'source')} for root in roots],
              'metadata_inspections': inspections,
              'hardware_categories': ['OS_PLATFORM', 'CPU_ARCHITECTURE', 'CPU_LOGICAL_COUNT', 'PHYSICAL_RAM',
                                      'WINDOWS_DXGI_GPU_AND_VRAM', 'WINDOWS_SYSTEM_CUDA_DIRECTML_COMPONENT_METADATA'],
              'limits': {'planning_budget_seconds': PLANNING_BUDGET_SECONDS,
                         'scan_budget_seconds': SCAN_BUDGET_SECONDS, 'request_timeout_seconds': timeout,
                         'max_services': 20, 'max_models_per_service': MAX_MODELS,
                         'max_response_bytes': response_bytes, 'max_roots': scanner.MAX_ROOTS,
                         'max_http_requests': sum(len(row['probe_paths']) for row in services),
                         'max_entries': scanner.MAX_ENTRIES, 'max_files': scanner.MAX_FILES, 'max_depth': scanner.MAX_DEPTH,
                         'max_metadata_bytes': scanner.MAX_METADATA_BYTES, 'max_metadata_read_bytes': scanner.MAX_METADATA_BYTES + 8,
                         'max_executable_siblings': 256, 'max_executable_version_bytes': 1024 * 1024,
                         'max_windows_gpu_adapters': 128, 'max_registration_metadata_inspections': 2048,
                         'preview_ttl_seconds': PREVIEW_TTL_SECONDS},
              'inference_status': 'NOT_RUN', 'requires_confirmation': True,
              'side_effects': {'launches': False, 'loads_weights': False, 'registers': False, 'enables': False,
                               'cloud_calls': False, 'persists_settings': False,
                               'may_disable_stale_registrations': True, 'persists_registration_safety_updates': True}}
    # All execution inputs, including hidden adapter options and path identity, are
    # committed. The public digest is nonce-bound by the issuing service.
    planning_check(guard, deadline)
    return {'public': public, 'runtimes': validated, 'roots': roots,
            'configured_roots': list(settings['scan_roots']), 'settings': copy.deepcopy(settings),
            'identities': identities, 'registration_paths': registration_paths,
            'platform': platform.system(), 'environment': environment}


class ScopeCancellation:
    """Existing Event-compatible worker cancellation with live host authorization."""
    def __init__(self, guard, plan: dict | None, client, hardware_probe):
        self.event = threading.Event()
        self.guard, self.plan, self.hardware_probe = guard, copy.deepcopy(plan), hardware_probe
        self.client = copy.copy(client)
        if plan is not None and hasattr(self.client, 'timeout'):
            self.client.timeout = plan['public']['limits']['request_timeout_seconds']
        if plan is not None and hasattr(self.client, 'max_response_bytes'):
            self.client.max_response_bytes = plan['public']['limits']['max_response_bytes']
        self.reason = None

    def set(self):
        self.event.set()

    def is_set(self):
        if self.event.is_set(): return True
        try:
            require_guard(self.guard)
        except ValueError:
            self.reason = 'LOCAL_AI_SCOPE_REVOKED'
            self.event.set()
        return self.event.is_set()

    def check(self):
        if self.is_set(): raise ValueError(self.reason or 'LOCAL_AI_CANCELLED')

    def verify_paths(self, paths=None, *, deadline=None):
        self.check()
        if self.plan is None: return
        try:
            for path in self.plan['identities'] if paths is None else paths:
                expected = self.plan['identities'][path]
                self.check()
                if path_identity(path, guard=self.check, deadline=deadline) != expected:
                    raise ValueError('changed')
        except (ValueError, OSError) as exc:
            code = 'LOCAL_AI_SCOPE_BUDGET_REACHED' if str(exc) == 'LOCAL_AI_SCOPE_BUDGET_REACHED' else 'LOCAL_AI_SCOPE_STALE'
            self.reason = self.reason or code
            self.event.set()
            raise ValueError(self.reason) from None
        self.check()

    def allow_request(self, runtime, path):
        self.check()
        if self.plan is None: return
        if not any(row['id'] == runtime['id'] and row['endpoint'] == runtime['endpoint'] and path in row['probe_paths']
                   for row in self.plan['public']['services']):
            self.reason = 'LOCAL_AI_SCOPE_INVALID'
            self.event.set()
            raise ValueError(self.reason)

    def allow_registration(self, identifier, record):
        self.check()
        if self.plan is None: return
        expected = self.plan['registration_paths'].get(identifier)
        if expected != {'path': record.get('local_path'), 'runtime_id': record.get('runtime_id')}:
            self.reason = 'LOCAL_AI_SCOPE_STALE'
            self.event.set()
            raise ValueError(self.reason)
        self.verify_paths([expected['path']])
