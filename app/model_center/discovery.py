"""Local AI Detect -> Validate -> Register -> explicit Enable.

No discovery/validation path launches executables, loads weights, generates content,
reads prompts or sends host facts to a cloud provider. Registrations are host-local.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
import threading
import time
from dataclasses import replace
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from .discovery_probes import LocalProbeClient, ProbeFailure, candidate_id, executable_metadata, gguf_metadata, host_hardware, infer_family, scan_gguf_roots, ollama_remote_declaration, ollama_locality_evidence, read_ollama_local_metadata
from .discovery_types import AIEnvironmentReport, DiscoverySettingsInput, LocalRuntimeInput, RegistrationInput, safe_local_path
from .discovery_environment import environment_roots, scan_environment_files
from .discovery_prerequisites import (catalog_requirements, prerequisite_template, observe_object_info,
    unknown_observations, failed_evidence_status)
from .discovery_scope import (PREVIEW_LIMIT, PREVIEW_TTL_SECONDS, SCAN_BUDGET_SECONDS, PLANNING_BUDGET_SECONDS,
    ScopeCancellation, build_plan, fingerprint, require_guard, planning_check, planning_lock)
from .domain import Capability, ModelDefinition, ModelStatus, RuntimeDefinition, RuntimeManagement, RuntimeType


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


class LocalDiscoveryService:
    def __init__(self, center, path: Path | None = None, *, client=None, hardware_probe=None, route_bridge: Callable | None = None):
        self.center, self.path = center, path
        self.client = client or LocalProbeClient()
        self.hardware_probe = hardware_probe or host_hardware
        self.route_bridge = route_bridge
        self.lock = threading.RLock()
        self.settings = {'scan_roots': [], 'runtimes': []}
        self.configured_runtime_sources: list[dict] = []
        self.registrations: dict[str, dict] = {}
        self._control_epochs: dict[str, int] = {}
        self.scan: dict | None = None
        self.cancel_event = threading.Event()
        self._scope_instance = uuid4().hex
        self._scope_previews: dict[str, dict] = {}
        self.hardware = {'status': 'NOT_VERIFIED', 'notes': ['SCAN_REQUIRED'], 'gpus': []}
        self.persistence_error = None
        self.workflow_adapters = [{'id': 'comfy-sd-checkpoint-v1', 'display_name': 'Stable Diffusion checkpoint (T2I)',
            'family': 'STABLE_DIFFUSION', 'capability': 'IMAGE', 'model_loader': 'CheckpointLoaderSimple', 'model_input': 'ckpt_name', 'required_nodes': ['CheckpointLoaderSimple', 'KSampler', 'EmptyLatentImage', 'CLIPTextEncode', 'VAEDecode', 'SaveImage']}]
        self._load()

    def _load(self):
        if not self.path or not self.path.is_file(): return
        try:
            if self.path.stat().st_size > 4 * 1024 * 1024: raise ValueError('oversize')
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if data.get('schema_version') != 1: raise ValueError('schema')
            roots = DiscoverySettingsInput(scan_roots=data['settings']['scan_roots'], include_common_model_dirs=data['settings'].get('include_common_model_dirs', True)).model_dump()
            runtimes = data['settings'].get('runtimes', [])
            if not isinstance(runtimes, list) or len(runtimes) > 16: raise ValueError('runtimes')
            roots['runtimes'] = [{'id': item['id'], **LocalRuntimeInput.model_validate({k:v for k,v in item.items() if k != 'id'}).model_dump()} for item in runtimes]
            records = data.get('registrations', {})
            if not isinstance(records, dict) or len(records) > 2048: raise ValueError('registrations')
            self.settings = roots
            # Rehydrated registrations never inherit stale readiness or routing authority.
            # Explicit validation and Enable are required after restart (no network at import).
            for key, value in records.items():
                if not isinstance(value, dict) or value.get('id') != key: raise ValueError('registration')
                value = copy.deepcopy(value)
                value.update(enabled=False, status='DISABLED', validated_at=None, enable_eligible=False,
                             enable_blockers=['REVALIDATION_REQUIRED'], verified=False, verified_capabilities=[])
                self.registrations[key] = value
                self._publish_model(value)
        except (OSError, ValueError, KeyError, TypeError):
            self.persistence_error = 'LOCAL_AI_CONFIG_READ_FAILED'
            self.settings = {'scan_roots': [], 'runtimes': []}
            self.registrations = {}

    @staticmethod
    def _guard(guard):
        if guard is not None: require_guard(guard)

    def _persist(self, settings=None, registrations=None, *, guard=None):
        self._guard(guard)
        if not self.path: return
        payload = {'schema_version': 1, 'settings': settings if settings is not None else self.settings,
                   'registrations': registrations if registrations is not None else self.registrations}
        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=self.path.parent, prefix='.discovery-', suffix='.tmp', delete=False) as file:
                temporary = Path(file.name)
                json.dump(payload, file, ensure_ascii=False, indent=2)
                file.flush(); os.fsync(file.fileno())
            self._guard(guard)
            os.replace(temporary, self.path)
            temporary = None
        except OSError as exc:
            raise ValueError('LOCAL_AI_CONFIG_WRITE_FAILED') from exc
        finally:
            if temporary:
                try: temporary.unlink()
                except OSError: pass

    def snapshot(self):
        with self.lock:
            return copy.deepcopy({'scan': self.scan, 'registrations': list(self.registrations.values()),
                'settings': self.settings, 'hardware': self.hardware, 'workflow_adapters': self.workflow_adapters,
                'persistence_error': self.persistence_error})

    def configure_roots(self, values: DiscoverySettingsInput, *, guard=None):
        self._guard(guard)
        with self.lock:
            settings = {**self.settings, 'scan_roots': values.scan_roots}
            if 'include_common_model_dirs' in values.model_fields_set:
                settings['include_common_model_dirs'] = values.include_common_model_dirs
            self._persist(settings=settings, guard=guard); self.settings = settings
            return copy.deepcopy(settings)

    def configure_runtime(self, value: LocalRuntimeInput, runtime_id: str | None = None, *, guard=None):
        self._guard(guard)
        with self.lock:
            runtimes = list(self.settings['runtimes'])
            if runtime_id and not any(r['id'] == runtime_id for r in runtimes): raise KeyError(runtime_id)
            if not runtime_id and len(runtimes) >= 16: raise ValueError('LOCAL_AI_RUNTIME_LIMIT')
            item = {'id': runtime_id or 'local-runtime-' + uuid4().hex[:16], **value.model_dump()}
            if any(r['id'] != item['id'] and (r['type'], r['endpoint'], r['model_path']) == (item['type'], item['endpoint'], item['model_path']) for r in runtimes):
                raise ValueError('LOCAL_AI_DUPLICATE_RUNTIME')
            settings = {**self.settings, 'runtimes': [r for r in runtimes if r['id'] != item['id']] + [item]}
            records = copy.deepcopy(self.registrations)
            changed = [r for r in records.values() if r['runtime_id'] == item['id']]
            for r in changed:
                r.update(enabled=False, status='DISABLED', validated_at=None, enable_eligible=False,
                         enable_blockers=['REVALIDATION_REQUIRED'], verified_capabilities=[])
            self._persist(settings=settings, registrations=records, guard=guard)
            self.settings, self.registrations = settings, records
            for r in changed:
                self._control_epochs[r['id']] = self._control_epochs.get(r['id'], 0) + 1
                self._publish_model(r); self._bridge(r)
            return copy.deepcopy(item)

    @staticmethod
    def _environment_enabled():
        from ..experimental.flags import enabled_flags
        return 'narrative_production_v2' in enabled_flags()

    def environment_report(self):
        # This reads the last explicit scan; it never probes on GET or at startup.
        with self.lock:
            job = self.scan or {}
            services = []
            for report in job.get('runtimes', []):
                candidates = [item for item in job.get('candidates', []) if item['runtime_id'] == report['id']]
                services.append({key: report.get(key) for key in ('id', 'name', 'type', 'endpoint', 'status', 'version')})
                services[-1].update(notes=report.get('notes', []), available_models=list(dict.fromkeys(
                    [*report.get('available_models', []), *[item['model_name'] for item in candidates]]))[:512],
                    candidate_ids=[item['id'] for item in candidates])
            return AIEnvironmentReport(scan_id=job.get('id'), status=job.get('status', 'NOT_SCANNED'),
                started_at=job.get('started_at'), finished_at=job.get('finished_at'), hardware=copy.deepcopy(self.hardware),
                services=services, model_files=copy.deepcopy(job.get('model_files', [])),
                workflow_prerequisites=copy.deepcopy(job.get('workflow_prerequisites')),
                roots=copy.deepcopy(job.get('roots', [])), errors=copy.deepcopy(job.get('errors', []))).model_dump()

    def _runtimes(self, *, center_runtimes=None, settings=None, configured_sources=None, environment=None, plan_check=None):
        if plan_check is not None: plan_check()
        settings = self.settings if settings is None else settings
        configured_sources = self.configured_runtime_sources if configured_sources is None else configured_sources
        environment = self._environment_enabled() if environment is None else environment
        defaults = [LocalRuntimeInput(name='Ollama', type='OLLAMA', endpoint='http://127.0.0.1:11434', modality='TEXT'),
                    LocalRuntimeInput(name='ComfyUI', type='COMFYUI', endpoint='http://127.0.0.1:8188'),
                    LocalRuntimeInput(name='Automatic1111', type='AUTOMATIC1111', endpoint='http://127.0.0.1:7860', modality='IMAGE')]
        if environment:
            defaults += [LocalRuntimeInput(name='LM Studio', type='OPENAI_COMPATIBLE_LOCAL', endpoint='http://127.0.0.1:1234', modality='TEXT'),
                         LocalRuntimeInput(name='llama.cpp', type='LLAMA_CPP', endpoint='http://127.0.0.1:8080', modality='TEXT')]
        result = [{'id': 'discovery-' + item.type.lower(), **item.model_dump()} for item in defaults]
        for item in (self.center.runtimes.values() if center_runtimes is None else center_runtimes):
            if plan_check is not None: plan_check()
            if item.runtime_type not in {RuntimeType.LLAMA_CPP, RuntimeType.COMFYUI} or item.id.startswith('local-'): continue
            try:
                config = LocalRuntimeInput(name=item.id, type=str(item.runtime_type), endpoint=item.base_url,
                    management=str(item.management), executable=item.executable, model_path=item.model_path,
                    context_size=item.context_size or 8192, gpu_layers=item.gpu_layers or 0,
                    threads=item.threads, batch_size=item.batch_size, health_endpoint=item.health_endpoint)
                result.append({'id': item.id, **config.model_dump()})
            except ValueError: continue
            if plan_check is not None: plan_check()
        # Explicit user entries supersede default endpoint probes, without duplicate candidates.
        result += configured_sources
        result += settings['runtimes']
        unique = {}
        for item in result:
            if plan_check is not None: plan_check()
            unique[(item['type'], item['endpoint'], item.get('model_path', ''))] = item
        return list(unique.values())[:20]

    def _scope_plan(self, include_common_model_dirs, guard=None, deadline=None):
        deadline = time.monotonic() + PLANNING_BUDGET_SECONDS if deadline is None else deadline
        check = lambda: planning_check(guard, deadline)
        check()
        # Never hold a discovery lock while taking the ModelCenter lock. The
        # resulting immutable inputs, not live owners, are passed to the worker.
        with planning_lock(getattr(self.center, '_config_lock', None), guard, deadline):
            center_runtimes = copy.deepcopy(list(self.center.runtimes.values()))
            component_rows, component_identity, definition_status = catalog_requirements(self.center.models, self.center.components)
        with planning_lock(self.lock, guard, deadline):
            settings = copy.deepcopy(self.settings)
            sources = copy.deepcopy(self.configured_runtime_sources)
            environment = self._environment_enabled()
            runtimes = self._runtimes(center_runtimes=center_runtimes, settings=settings,
                                      configured_sources=sources, environment=environment, plan_check=check)
            plan = build_plan(runtimes, settings, include_common_model_dirs, environment=environment,
                              timeout=getattr(self.client, 'timeout', 2.0),
                              response_bytes=getattr(self.client, 'max_response_bytes', 4 * 1024 * 1024), registrations=self.registrations, guard=guard, deadline=deadline)
            plan['adapter_identity'] = {'client': id(self.client), 'hardware_probe': id(self.hardware_probe)}
            plan['configured_sources'] = sources
            plan['workflow_definition_identity'] = []
            plan['prerequisite_template'] = prerequisite_template(runtimes, self.workflow_adapters, component_rows,
                definition_status, identities=plan['workflow_definition_identity'])
            plan['component_definition_identity'] = component_identity
            check()
            return plan

    @staticmethod
    def _scope_principal(principal):
        if not isinstance(principal, str) or not 0 < len(principal) <= 1024:
            raise ValueError('LOCAL_AI_SCOPE_PRINCIPAL_MISMATCH')

    def preview_scan_scope(self, include_common_model_dirs: bool, principal: str, guard):
        deadline = time.monotonic() + PLANNING_BUDGET_SECONDS
        self._scope_principal(principal)
        require_guard(guard)
        try:
            plan = self._scope_plan(include_common_model_dirs, guard, deadline)
        except (OSError, ValueError, TypeError) as exc:
            if str(exc) in {'LOCAL_AI_SCOPE_REVOKED', 'LOCAL_AI_SCOPE_BUDGET_REACHED'}: raise
            raise ValueError('LOCAL_AI_SCOPE_INVALID') from exc
        require_guard(guard)
        with planning_lock(self.lock, guard, deadline):
            timestamp = time.monotonic()
            self._scope_previews = {key: row for key, row in self._scope_previews.items()
                                    if row['expires'] > timestamp}
            current_digest = (self.scan or {}).get('consent', {}).get('scope_digest')
            while len(self._scope_previews) >= PREVIEW_LIMIT:
                oldest = next(key for key in self._scope_previews if key != current_digest)
                del self._scope_previews[oldest]
            token = fingerprint([self._scope_instance, principal, uuid4().hex, plan])
            planning_check(guard, deadline)
            self._scope_previews[token] = {'principal': principal, 'plan': plan,
                                           'expires': timestamp + PREVIEW_TTL_SECONDS, 'scan_id': None}
            return {**copy.deepcopy(plan['public']), 'scope_digest': token}

    def _issued_scope(self, scope_digest, principal):
        if not isinstance(scope_digest, str) or not scope_digest:
            raise ValueError('LOCAL_AI_SCOPE_REQUIRED')
        row = self._scope_previews.get(scope_digest)
        if row is None: raise ValueError('LOCAL_AI_SCOPE_INVALID')
        if row['principal'] != principal: raise ValueError('LOCAL_AI_SCOPE_PRINCIPAL_MISMATCH')
        if time.monotonic() >= row['expires']: raise ValueError('LOCAL_AI_SCOPE_EXPIRED')
        if row.get('stale'): raise ValueError('LOCAL_AI_SCOPE_STALE')
        if row['scan_id'] and (not self.scan or row['scan_id'] != self.scan['id']):
            raise ValueError('LOCAL_AI_SCOPE_CONSUMED')
        return row

    def start_consented_scan(self, scope_digest: str, principal: str, guard):
        deadline = time.monotonic() + PLANNING_BUDGET_SECONDS
        self._scope_principal(principal)
        require_guard(guard)
        with planning_lock(self.lock, guard, deadline):
            row = self._issued_scope(scope_digest, principal)
            if row['scan_id']:
                require_guard(guard)
                return copy.deepcopy(self.scan)
            expected = copy.deepcopy(row['plan'])
        try:
            effective = self._scope_plan(expected['public']['include_common_model_dirs'], guard, deadline)
        except (OSError, ValueError, TypeError) as exc:
            if str(exc) in {'LOCAL_AI_SCOPE_REVOKED', 'LOCAL_AI_SCOPE_BUDGET_REACHED'}: raise
            effective = None
        require_guard(guard)
        with planning_lock(self.lock, guard, deadline):
            row = self._issued_scope(scope_digest, principal)
            if row['scan_id']: return copy.deepcopy(self.scan)
            if (effective != expected or self.settings != expected['settings']
                    or self.configured_runtime_sources != expected['configured_sources']
                    or id(self.client) != expected['adapter_identity']['client']
                    or id(self.hardware_probe) != expected['adapter_identity']['hardware_probe']
                    or not self._environment_enabled()):
                row['stale'] = True
                raise ValueError('LOCAL_AI_SCOPE_STALE')
            if self.scan and self.scan['status'] == 'RUNNING':
                raise ValueError('LOCAL_AI_SCOPE_CONFLICT')
            def scan_guard():
                require_guard(guard)
                if not self._environment_enabled(): raise ValueError('LOCAL_AI_SCOPE_REVOKED')
            cancel = ScopeCancellation(scan_guard, expected, self.client, self.hardware_probe)
            cancel.verify_paths(deadline=deadline)
            planning_check(guard, deadline)  # Last admission check before publishing or starting work.
            job = {'id': uuid4().hex, 'status': 'RUNNING', 'runtimes': [], 'candidates': [], 'errors': [],
                   'started_at': now(), 'finished_at': None, 'environment_schema_version': 2,
                   'model_files': [], 'roots': copy.deepcopy(expected['roots']),
                   'consent': {'scope_digest': scope_digest, 'confirmed_at': now(), 'execution_scope': 'BACKEND_HOST'}}
            job['workflow_prerequisites'] = {'schema_version': 1, 'scan_id': job['id'], 'scan_status': 'RUNNING',
                                           **copy.deepcopy(expected['prerequisite_template'])}
            self.hardware = {'status': 'NOT_VERIFIED', 'notes': ['SCAN_PENDING'], 'gpus': []}
            self.cancel_event, self.scan, row['scan_id'] = cancel, job, job['id']
            try:
                threading.Thread(target=self._scan, args=(job, copy.deepcopy(expected['runtimes']),
                    list(expected['configured_roots']), cancel), daemon=True, name='local-ai-discovery').start()
            except Exception:
                cancel.set()
                job.update(status='CANCELLED', finished_at=now())
                self._finish_prerequisites(job)
                job['errors'].append({'code': 'LOCAL_AI_SCAN_FAILED'})
            return copy.deepcopy(job)

    def start_scan(self):
        return self._start_scan()

    def start_legacy_http_scan(self, guard):
        require_guard(guard)
        if self._environment_enabled(): raise ValueError('LOCAL_AI_SCOPE_CONFIRMATION_REQUIRED')
        def legacy_guard():
            require_guard(guard)
            if self._environment_enabled(): raise ValueError('LOCAL_AI_SCOPE_CONFIRMATION_REQUIRED')
        return self._start_scan(legacy_guard=legacy_guard)

    def _start_scan(self, *, legacy_guard=None):
        with getattr(self.center, '_config_lock', nullcontext()):
            center_runtimes = copy.deepcopy(list(self.center.runtimes.values()))
            component_rows, _, definition_status = (catalog_requirements(self.center.models, self.center.components)
                if self._environment_enabled() else ([], [], 'COMPLETE'))
        with self.lock:
            environment = self._environment_enabled()
            if legacy_guard is not None:
                if environment: raise ValueError('LOCAL_AI_SCOPE_CONFIRMATION_REQUIRED')
                require_guard(legacy_guard)

            if self.scan and self.scan['status'] == 'RUNNING': return copy.deepcopy(self.scan)
            self.cancel_event = (ScopeCancellation(legacy_guard, None, self.client, self.hardware_probe)
                                 if legacy_guard is not None else threading.Event())
            job = {'id': uuid4().hex, 'status': 'RUNNING', 'runtimes': [], 'candidates': [], 'errors': [],
                   'started_at': now(), 'finished_at': None}
            if environment:
                self.hardware = {'status': 'NOT_VERIFIED', 'notes': ['SCAN_PENDING'], 'gpus': []}
                job.update(environment_schema_version=2, model_files=[], roots=environment_roots(
                    self.settings['scan_roots'], self.settings.get('include_common_model_dirs', True)))
            self.scan = job
            runtimes, roots = copy.deepcopy(self._runtimes(environment=environment, center_runtimes=center_runtimes)), list(self.settings['scan_roots'])
            if environment:
                job['workflow_prerequisites'] = {'schema_version': 1, 'scan_id': job['id'], 'scan_status': 'RUNNING',
                    **prerequisite_template(runtimes, self.workflow_adapters, component_rows, definition_status)}
            threading.Thread(target=self._scan, args=(job, runtimes, roots, self.cancel_event), daemon=True, name='local-ai-discovery').start()
            return copy.deepcopy(job)

    def cancel_scan(self, scan_id):
        with self.lock:
            if not self.scan or self.scan['id'] != scan_id: raise KeyError(scan_id)
            self.cancel_event.set()
            # Worker publishes completed partial results and terminal state after bounded current probe.
            return copy.deepcopy(self.scan)

    def get_scan(self, scan_id):
        with self.lock:
            if not self.scan or self.scan['id'] != scan_id: raise KeyError(scan_id)
            return copy.deepcopy(self.scan)

    def _scan(self, job, runtimes, roots, cancel):
        limits = cancel.plan['public']['limits'] if isinstance(cancel, ScopeCancellation) and cancel.plan else None
        deadline = time.monotonic() + (limits['scan_budget_seconds'] if limits else SCAN_BUDGET_SECONDS)
        try:
            if isinstance(cancel, ScopeCancellation): cancel.verify_paths()
            if not cancel.is_set():
                try:
                    probe = cancel.hardware_probe if isinstance(cancel, ScopeCancellation) else self.hardware_probe
                    hardware = probe(cancel=cancel) if probe is host_hardware else probe()
                    with self.lock:
                        if not cancel.is_set(): self.hardware = hardware
                except Exception:
                    with self.lock:
                        if cancel.is_set(): raise ValueError('LOCAL_AI_CANCELLED')
                        self.hardware = {'status': 'NOT_VERIFIED', 'notes': ['HOST_HARDWARE_UNAVAILABLE'], 'gpus': []}
                        job['errors'].append({'code': 'LOCAL_AI_HARDWARE_UNAVAILABLE'})
            candidates = {}
            for runtime in runtimes:
                if cancel.is_set() or time.monotonic() >= deadline: break
                try:
                    prerequisites = [row for row in job.get('workflow_prerequisites', {}).get('workflows', [])
                                     if row['runtime_id'] == runtime['id']]
                    report, found = self._probe(runtime, cancel, deadline=deadline, prerequisites=prerequisites)
                except Exception:
                    report = {key: runtime[key] for key in ('id', 'name', 'type', 'endpoint', 'management')}
                    report.update(status='NOT_FOUND', version=None, notes=['LOCAL_AI_PROBE_INVALID'])
                    report['_prerequisite_observations'] = unknown_observations(prerequisites, 'MALFORMED')
                    found = []
                with self.lock:
                    if isinstance(cancel, ScopeCancellation) and cancel.is_set(): break
                    observations = report.pop('_prerequisite_observations', [])
                    if 'workflow_prerequisites' in job:
                        updates = {(row['runtime_id'], row['adapter_id']): row for row in observations}
                        job['workflow_prerequisites']['workflows'] = [updates.get((row['runtime_id'], row['adapter_id']), row)
                            for row in job['workflow_prerequisites']['workflows']]
                    job['runtimes'].append(report)
                    self._reconcile_detected_runtime(runtime, report, found,
                        cancel=cancel if isinstance(cancel, ScopeCancellation) else None, deadline=deadline)
                    for candidate in found: candidates[candidate['id']] = candidate
                    job['candidates'] = list(candidates.values())
                    if report['status'] not in {'RUNNING', 'DISCOVERED'}:
                        job['errors'].append({'runtime_id': runtime['id'], 'code': report['notes'][-1] if report['notes'] else report['status']})
            if isinstance(cancel, ScopeCancellation):
                cancel.verify_paths([row['path'] for row in cancel.plan['roots']] if cancel.plan else [])
            llama = next((r for r in runtimes if r['type'] == 'LLAMA_CPP'), None)
            if job.get('environment_schema_version') == 2:
                # Work on private copies; publish coherent partial observations under the lock.
                scan_roots, file_errors = copy.deepcopy(job['roots']), []
                for item in scan_environment_files(scan_roots, cancel, deadline, file_errors, limits=limits):
                    if cancel.is_set(): break
                    if llama and item['format'] == 'GGUF':
                        path = Path(item['path'])
                        matches = [c for c in candidates.values() if os.path.normcase(c.get('local_path', '')) == os.path.normcase(str(path))]
                        if not matches:
                            candidate = self._candidate(llama, path.name, local_path=str(path), evidence=gguf_metadata(path, cancel=cancel, max_bytes=limits['max_metadata_bytes'] if limits else None))
                            candidates.setdefault(candidate['id'], candidate)
                            matches = [candidate]
                        item['candidate_ids'] = [c['id'] for c in matches]
                    with self.lock:
                        if cancel.is_set(): break
                        job['model_files'].append(item)
                        job['candidates'] = list(candidates.values())
                        job['roots'] = copy.deepcopy(scan_roots)
                with self.lock:
                    if cancel.is_set(): raise ValueError('LOCAL_AI_CANCELLED')
                    job['roots'] = scan_roots
                    job['errors'].extend(file_errors)
            elif llama:
                for path in scan_gguf_roots(roots, cancel, deadline):
                    if cancel.is_set(): break
                    candidate = self._candidate(llama, path.name, local_path=str(path), evidence=gguf_metadata(path, cancel=cancel, max_bytes=limits['max_metadata_bytes'] if limits else None))
                    with self.lock:
                        if cancel.is_set(): break
                        candidates.setdefault(candidate['id'], candidate)
                        job['candidates'] = list(candidates.values())
            with self.lock:
                if time.monotonic() >= deadline: job['errors'].append({'code': 'LOCAL_AI_SCAN_BUDGET_REACHED'})
        except Exception:
            with self.lock:
                if not cancel.is_set(): job['errors'].append({'code': 'LOCAL_AI_SCAN_FAILED'})
        finally:
            with self.lock:
                if cancel.is_set() and getattr(cancel, 'reason', None):
                    job['errors'].append({'code': cancel.reason})
                job['status'] = 'CANCELLED' if cancel.is_set() else ('PARTIAL' if job['errors'] else 'COMPLETED')
                job['finished_at'] = now()
                self._finish_prerequisites(job)

    @staticmethod
    def _finish_prerequisites(job):
        report = job.get('workflow_prerequisites')
        if report is None: return
        report['scan_status'] = job['status']
        if job['status'] == 'CANCELLED':
            report['workflows'] = unknown_observations(report['workflows'], 'CANCELLED')
        elif any(error.get('code') == 'LOCAL_AI_SCAN_BUDGET_REACHED' for error in job['errors']):
            report['workflows'] = [unknown_observations([row], 'BOUNDED')[0]
                                  if row['evidence_status'] == 'NOT_SCANNED' else row for row in report['workflows']]

    def _candidate(self, runtime, name, *, local_path='', evidence=None, family_hint=''):
        evidence = evidence or {}
        family, capabilities = infer_family(name)
        if family == 'UNKNOWN' and family_hint: family, capabilities = infer_family(family_hint)
        if runtime['type'] in {'OLLAMA', 'LLAMA_CPP'} and not capabilities: capabilities = ['TEXT']
        if runtime['type'] == 'AUTOMATIC1111': capabilities = ['IMAGE']
        if not capabilities and runtime.get('model_id') == name and runtime.get('modality') != 'UNKNOWN':
            capabilities = [runtime['modality']]
        # Runtime presence is never a license grant. Unknown/restricted licenses
        # need the user's explicit local-use review acknowledgment.
        license_required = True
        identifier = candidate_id(runtime['type'], runtime['endpoint'], name, local_path)
        return {'id': identifier, 'candidate_id': identifier, 'provider_id': 'discovery-' + identifier, 'display_name': name, 'model_id': identifier, 'family': family,
            'modality': capabilities[0] if capabilities else 'UNKNOWN', 'declared_capabilities': capabilities,
            'verified_capabilities': [], 'runtime_id': runtime['id'], 'runtime_type': runtime['type'],
            'source': runtime['type'], 'model_name': name, 'local_path': local_path, 'local': True,
            'status': 'DISCOVERED', 'compatible': 'NOT_VERIFIED', 'verified': False, 'enabled': False,
            'validated_at': None, 'validation_notes': ['CAPABILITY_UNVERIFIED', 'INFERENCE_NOT_RUN'],
            'evidence': evidence, 'runtime_config': copy.deepcopy(runtime), 'license_required': license_required,
            'license_status': 'REVIEW_REQUIRED', 'license_confirmed': False, 'workflow_adapter_id': '', 'enable_eligible': False,
            'enable_blockers': ['VALIDATION_REQUIRED']}

    def _probe(self, runtime, cancel, *, deadline=None, prerequisites=None):
        report = {key: runtime[key] for key in ('id', 'name', 'type', 'endpoint', 'management')}
        report.update(status='NOT_FOUND', version=None, notes=[])
        found = []
        prerequisites = prerequisites or []
        prerequisite_info = None
        prerequisite_received = False
        prerequisite_failure = 'UNAVAILABLE'
        def get(path):
            if cancel.is_set(): raise ProbeFailure('LOCAL_AI_CANCELLED')
            if deadline is not None and time.monotonic() >= deadline: raise ProbeFailure('LOCAL_AI_SCAN_BUDGET_REACHED')
            if isinstance(cancel, ScopeCancellation):
                cancel.allow_request(runtime, path)
                result = cancel.client.json(runtime['endpoint'], path)
            else:
                result = self.client.json(runtime['endpoint'], path)
            if isinstance(cancel, ScopeCancellation) and cancel.is_set(): raise ProbeFailure('LOCAL_AI_CANCELLED')
            return result
        try:
            kind = runtime['type']
            if runtime.get('credential_required'):
                raise ProbeFailure('LOCAL_AI_CREDENTIAL_BINDING_REQUIRED')
            if kind == 'OLLAMA':
                from ..providers import OllamaProvider
                models = OllamaProvider(runtime['endpoint']).list_models(read_json=get, include_details=True, strict=True)
                for model in models:
                    if isinstance(model, dict) and isinstance(model.get('name'), str) and 0 < len(model['name']) <= 256:
                        candidate = self._candidate(runtime, model['name'], evidence={key:model[key] for key in ('size','modified_at','digest','details','remote_model','remote_host') if key in model})
                        remote = ollama_remote_declaration(model)
                        candidate.update(local=False, source_locality='REMOTE' if remote == 'REMOTE' else 'NOT_VERIFIED')
                        if remote == 'REMOTE':
                            candidate.update(source='OLLAMA_HOSTED', validation_notes=['OLLAMA_REMOTE_MODEL_BLOCKED'], enable_blockers=['OLLAMA_REMOTE_MODEL_BLOCKED'])
                        found.append(candidate)
                try:
                    version = get('/api/version')
                    if isinstance(version, dict) and isinstance(version.get('version'), str): report['version'] = version['version'][:100]
                except ProbeFailure:
                    report['notes'].append('RUNTIME_VERSION_NOT_AVAILABLE')
            elif kind == 'COMFYUI':
                stats = get('/system_stats'); info = get('/object_info')
                prerequisite_info, prerequisite_received = info, True
                if not isinstance(stats, dict) or not isinstance(info, dict): raise ProbeFailure('LOCAL_AI_INVALID_RESPONSE')
                report['version'] = str((stats.get('system') if isinstance(stats.get('system'), dict) else {}).get('comfyui_version') or '')[:100] or None
                nodes = sorted(str(key) for key in info)[:4096]
                names, bindings = {}, {}
                for node, definition in list(info.items())[:4096]:
                    if not isinstance(definition, dict): continue
                    inputs = definition.get('input')
                    if not isinstance(inputs, dict): continue
                    for fields in inputs.values():
                        if not isinstance(fields, dict): continue
                        for field, schema in fields.items():
                            if field not in {'ckpt_name','unet_name','model_name','model','checkpoint','checkpoint_name','model_path'}: continue
                            if not isinstance(schema, list) or not schema or not isinstance(schema[0], list): continue
                            for name in schema[0][:512]:
                                if not isinstance(name, str) or not 0 < len(name) <= 256: continue
                                if len(names) >= 512 and name not in names: continue
                                names.setdefault(name, []).append(str(node))
                                bindings.setdefault(name, []).append({'node_class': str(node), 'input_field': field})
                nodes_fingerprint = digest(info)
                for name, loaders in names.items():
                    found.append(self._candidate(runtime, name, family_hint=' '.join(loaders), evidence={
                        'model_listed': True, 'model_file_exists': None, 'loader_nodes': loaders, 'loader_bindings': bindings[name],
                        'node_classes': nodes, 'nodes_fingerprint': nodes_fingerprint, 'workflow_status': 'NOT_CONFIGURED', 'generation_verified': False}))
            elif kind == 'AUTOMATIC1111':
                payload = get('/sdapi/v1/sd-models')
                if not isinstance(payload, list): raise ProbeFailure('LOCAL_AI_INVALID_RESPONSE')
                for model in payload[:512]:
                    name = model.get('title') or model.get('model_name') if isinstance(model, dict) else None
                    if isinstance(name, str) and 0 < len(name) <= 256:
                        found.append(self._candidate(runtime, name, evidence={'model_listed': True, 'sha256': model.get('sha256'), 'filename': model.get('filename')}))
            elif kind == 'LLAMA_CPP':
                path = runtime.get('model_path')
                executable = runtime.get('executable')
                if isinstance(cancel, ScopeCancellation):
                    cancel.verify_paths([value for value in (path, executable, str(Path(executable).parent) if executable else '') if value])
                report.update(executable_metadata(executable or '', cancel=cancel))
                report['notes'].append('EXECUTABLE_NOT_EXECUTED')
                if path:
                    found.append(self._candidate(runtime, Path(path).name, local_path=path, evidence=gguf_metadata(Path(path), cancel=cancel)))
                try:
                    payload = get(runtime.get('health_endpoint') or '/v1/models')
                    if not isinstance(payload, dict): raise ProbeFailure('LOCAL_AI_INVALID_RESPONSE')
                    listed = payload.get('data', [])
                    report['available_models'] = [item['id'] for item in listed[:512] if isinstance(item, dict) and isinstance(item.get('id'), str) and 0 < len(item['id']) <= 256] if isinstance(listed, list) else []
                    for item in found: item['evidence']['runtime_advertised_models'] = report['available_models']
                    # A model-list-only server has no verified local file or architecture.
                    if not path:
                        for name in report['available_models']:
                            if 0 < len(name) <= 256:
                                found.append(self._candidate(runtime, name, evidence={'model_listed': True, 'runtime_advertised_models': report['available_models']}))
                    if isinstance(payload, dict) and payload.get('version'):
                        report['version'] = str(payload['version'])[:100]
                except ProbeFailure:
                    if found or report['executable_exists']:
                        report['status'] = 'DISCOVERED'; report['notes'].append('EXTERNAL_RUNTIME_NOT_RUNNING')
                        return report, found
                    raise
            elif kind == 'OPENAI_COMPATIBLE_LOCAL':
                payload = get('/models' if runtime['endpoint'].endswith('/v1') else '/v1/models')
                if not isinstance(payload, dict) or not isinstance(payload.get('data'), list): raise ProbeFailure('LOCAL_AI_INVALID_RESPONSE')
                for model in payload['data'][:512]:
                    if isinstance(model, dict) and isinstance(model.get('id'), str) and 0 < len(model['id']) <= 256:
                        found.append(self._candidate(runtime, model['id'], evidence={'model_listed': True, 'protocol': 'OPENAI_COMPATIBLE'}))
            else:
                if not runtime.get('health_endpoint'): raise ProbeFailure('LOCAL_AI_HEALTH_ENDPOINT_REQUIRED')
                get(runtime['health_endpoint'])
                if runtime.get('model_id'):
                    found.append(self._candidate(runtime, runtime['model_id'], evidence={'health_reachable': True}))
            report['status'] = 'RUNNING'
        except (ProbeFailure, ValueError, OSError, TypeError, AttributeError) as exc:
            report['notes'].append(str(exc) if isinstance(exc, ProbeFailure) else 'LOCAL_AI_PROBE_INVALID')
            report['status'] = 'CANCELLED' if cancel.is_set() else 'NOT_FOUND'
            prerequisite_failure = failed_evidence_status(report['notes'][-1])
        if prerequisites:
            report['_prerequisite_observations'] = (unknown_observations(prerequisites, 'CANCELLED') if cancel.is_set()
                else unknown_observations(prerequisites, 'BOUNDED') if deadline is not None and time.monotonic() >= deadline
                else observe_object_info(prerequisites, prerequisite_info, found) if prerequisite_received and report['status'] == 'RUNNING'
                else unknown_observations(prerequisites, prerequisite_failure))
        return report, found

    def _find(self, identifier):
        for item in (self.scan or {}).get('candidates', []):
            if item['id'] == identifier: return copy.deepcopy(item)
        if identifier in self.registrations: return copy.deepcopy(self.registrations[identifier])
        raise KeyError(identifier)

    def validate(self, identifier, *, guard=None):
        self._guard(guard)
        with self.lock:
            candidate = self._find(identifier)
            expected_epoch = self._control_epochs.get(identifier, 0)
            saved = self.registrations.get(identifier)
            if saved:
                for field in ('workflow_adapter_id','license_confirmed'): candidate[field] = saved.get(field, '' if field == 'workflow_adapter_id' else False)
            runtime = next((r for r in self._runtimes() if r['id'] == candidate['runtime_id']), candidate['runtime_config'])
            fingerprint = digest(runtime)
        # Metadata-only validation; never generation or --version.
        validation_cancel = ScopeCancellation(guard, None, self.client, self.hardware_probe) if guard is not None else threading.Event()
        self._guard(guard)
        report, detected = self._probe(runtime, validation_cancel)
        self._guard(guard)
        current = next((item for item in detected if item['id'] == identifier), None)
        evidence = current['evidence'] if current else {}
        notes, verified = ['INFERENCE_NOT_RUN', 'CURRENT_GPU_NOT_VERIFIED'], []
        kind = runtime['type']
        if kind == 'LLAMA_CPP':
            evidence = gguf_metadata(Path(candidate['local_path']), cancel=validation_cancel) if candidate['local_path'] else {'header_valid': False}
            architecture = str(evidence.get('general.architecture', '')).casefold()
            if evidence.get('header_valid') and architecture.startswith(('qwen', 'llama', 'gemma', 'mistral', 'phi', 'deepseek')):
                verified = ['TEXT']
            if not candidate['local_path']: notes.append('RUNTIME_MODEL_FILE_UNVERIFIED')
            elif not evidence.get('header_valid'): notes.append('GGUF_HEADER_INVALID')
            if not report.get('executable_exists') and report['status'] != 'RUNNING': notes.append('RUNTIME_REQUIRED')
            if runtime['management'] == 'EXTERNAL':
                if runtime.get('model_path') != candidate['local_path']: notes.append('RUNTIME_MODEL_PATH_MISMATCH')
                expected = runtime.get('model_id') or Path(candidate['local_path']).name
                if expected not in report.get('available_models', []): notes.append('RUNTIME_MODEL_UNVERIFIED')
            notes.extend(['EXECUTABLE_VERSION_NOT_VERIFIED', 'CUDA_NOT_VERIFIED'])
            if runtime.get('gpu_layers', 0) > 0:
                notes.append('CPU_OFFLOAD_MAY_BE_REQUIRED')
            if evidence.get('size', 0) > (self.hardware.get('ram_bytes') or 0):
                notes.append('MEMORY_AND_CONTEXT_NOT_VERIFIED')
        elif current and report['status'] == 'RUNNING':
            if kind == 'OLLAMA':
                checked = self.ollama_metadata_check(runtime, candidate['model_name'], cancel=validation_cancel)
                evidence.update(checked)
                notes.extend(checked['locality_blockers'])
                candidate['source_locality'] = checked['source_locality']
                candidate['local'] = checked['source_locality'] == 'LOCAL_VERIFIED'
                candidate['source'] = 'OLLAMA_HOSTED' if checked['source_locality'] == 'REMOTE' else 'OLLAMA'
                capabilities = checked['reported_capabilities']
                if checked['source_locality'] == 'LOCAL_VERIFIED':
                    if 'completion' in capabilities: verified.append('TEXT')
                    if 'vision' in capabilities: verified.append('VISION')
                    from ..experimental.flags import enabled_flags
                    if 'embedding' in capabilities and 'visual_embeddings' in enabled_flags(): verified.append('EMBEDDING')
                    if 'embedding' in capabilities and 'completion' not in capabilities: notes.append('TEXT_GENERATION_UNSUPPORTED')
            elif kind == 'AUTOMATIC1111': verified = ['IMAGE']
            elif kind == 'COMFYUI':
                adapter = next((a for a in self.workflow_adapters if a['id'] == candidate.get('workflow_adapter_id')), None)
                if not adapter and candidate['family'] == 'STABLE_DIFFUSION':
                    adapter = self.workflow_adapters[0]; candidate['workflow_adapter_id'] = adapter['id']
                bound = bool(adapter and {'node_class': adapter['model_loader'], 'input_field': adapter['model_input']} in evidence.get('loader_bindings', []))
                if adapter and bound and adapter['family'] == candidate['family'] and set(adapter['required_nodes']) <= set(evidence.get('node_classes', [])):
                    verified = [adapter['capability']]; evidence['workflow_status'] = 'STRUCTURE_VALIDATED_NOT_GENERATED'
                else: notes.append('WORKFLOW_ADAPTER_REQUIRED')
            elif kind == 'OPENAI_COMPATIBLE_LOCAL': notes.append('CAPABILITY_UNVERIFIED')
            else: notes.append('ADAPTER_REQUIRED')
        else: notes.append('MODEL_OR_RUNTIME_NOT_FOUND')
        if not verified: notes.append('CAPABILITY_UNVERIFIED')
        observed_identity = {key: evidence[key] for key in ('digest', 'sha256', 'size', 'modified_ns', 'general.architecture', 'locality_fingerprint') if key in evidence}
        model_evidence_fingerprint = digest(observed_identity) if observed_identity else None
        previous_fingerprint = saved.get('model_evidence_fingerprint') if saved else None
        if previous_fingerprint and previous_fingerprint != model_evidence_fingerprint:
            candidate['license_confirmed'] = False
            notes.append('MODEL_CHANGED_REVIEW_REQUIRED')
        candidate['model_evidence_fingerprint'] = model_evidence_fingerprint
        candidate.update(runtime_config=runtime, runtime_fingerprint=fingerprint, evidence=evidence,
            verified_capabilities=verified, validated_at=now(), verified=False, enabled=False,
            status='VALIDATION_REQUIRED', compatible='POSSIBLY_COMPATIBLE' if verified else 'NOT_VERIFIED',
            validation_notes=list(dict.fromkeys(notes)))
        self._eligibility(candidate)
        self._guard(guard)
        with self.lock:
            self._guard(guard)
            latest_runtime = next((r for r in self._runtimes() if r['id'] == runtime['id']), runtime)
            if fingerprint != digest(latest_runtime) or expected_epoch != self._control_epochs.get(identifier, 0):
                raise ValueError('LOCAL_AI_CONFIGURATION_CHANGED')
            if identifier in self.registrations:
                records = {**self.registrations, identifier: candidate}
                self._persist(registrations=records, guard=guard); self.registrations = records
                self._control_epochs[identifier] = expected_epoch + 1
                self._publish_model(candidate); self._bridge(candidate)
            if self.scan:
                self.scan['candidates'] = [candidate if item['id'] == identifier else item for item in self.scan['candidates']]
            return copy.deepcopy(candidate)

    def ollama_metadata_check(self, runtime, model_name, *, cancel=None):
        from ..providers import OllamaProvider
        return read_ollama_local_metadata(self.client, runtime['endpoint'], model_name,
                                          OllamaProvider(runtime['endpoint']).list_models, cancel=cancel)

    def _invalidate_registration(self, identifier, reason, evidence=None, *, cancel=None):
        with self.lock:
            if cancel is not None: cancel.check()
            live = self.registrations.get(identifier)
            if not live: return
            blocked = copy.deepcopy(live)
            blocked.update(enabled=False, enable_eligible=False, verified_capabilities=[],
                status='VALIDATION_REQUIRED', compatible='NOT_VERIFIED', local=False,
                source_locality=(evidence or {}).get('source_locality', 'NOT_VERIFIED'),
                enable_blockers=[reason], license_confirmed=False,
                validation_notes=list(dict.fromkeys([*live.get('validation_notes', []), reason])))
            if evidence: blocked['evidence'].update(evidence)
            if blocked['source_locality'] == 'REMOTE': blocked['source'] = 'OLLAMA_HOSTED'
            records = {**self.registrations, identifier: blocked}
            if cancel is not None: cancel.check()
            try: self._persist(registrations=records, guard=cancel.check if cancel is not None else None)
            except ValueError:
                if cancel is not None: cancel.check()
                self.persistence_error = 'LOCAL_AI_CONFIG_WRITE_FAILED'
            self.registrations = records
            self._control_epochs[identifier] = self._control_epochs.get(identifier, 0) + 1
            self._publish_model(blocked); self._bridge(blocked)

    def _observed_registration(self, record, found, *, cancel=None):
        current = next((item for item in found if item['id'] == record['id']), None)
        if record['runtime_type'] == 'LLAMA_CPP':
            # Registered GGUFs may come from bounded roots rather than the
            # runtime's single configured default file. Recheck their own path.
            if cancel is not None: cancel.allow_registration(record['id'], record)
            return {**record, 'evidence': gguf_metadata(Path(record['local_path']), cancel=cancel)}
        return current

    def _observation_problem(self, record, report, current):
        kind = record['runtime_type']
        if not current: return 'MODEL_OR_RUNTIME_NOT_FOUND'
        evidence, previous = current['evidence'], record.get('evidence', {})
        if kind == 'OLLAMA':
            if report['status'] != 'RUNNING': return 'OLLAMA_LOCALITY_UNVERIFIED'
            if ollama_remote_declaration(evidence) == 'REMOTE': return 'OLLAMA_REMOTE_MODEL_BLOCKED'
            keys = ('digest', 'size', 'details', 'remote_model', 'remote_host')
        elif kind == 'LLAMA_CPP':
            if not evidence.get('header_valid'): return 'GGUF_HEADER_INVALID'
            config = record['runtime_config']
            if config['management'] == 'MANAGED':
                if not report.get('executable_exists'): return 'RUNTIME_REQUIRED'
            elif (report['status'] != 'RUNNING' or (config.get('model_id') or Path(record['local_path']).name) not in report.get('available_models', [])):
                return 'RUNTIME_MODEL_UNVERIFIED'
            keys = ('file_exists', 'header_valid', 'size', 'modified_ns', 'general.architecture')
        elif kind == 'COMFYUI':
            if report['status'] != 'RUNNING': return 'MODEL_OR_RUNTIME_NOT_FOUND'
            adapter = next((item for item in self.workflow_adapters if item['id'] == record.get('workflow_adapter_id')), None)
            if (not adapter or not set(adapter['required_nodes']) <= set(evidence.get('node_classes', [])) or
                    {'node_class':adapter['model_loader'], 'input_field':adapter['model_input']} not in evidence.get('loader_bindings', [])):
                return 'WORKFLOW_ADAPTER_REQUIRED'
            keys = ('model_listed', 'nodes_fingerprint', 'loader_bindings')
        elif kind == 'AUTOMATIC1111':
            if report['status'] != 'RUNNING' or not evidence.get('model_listed'): return 'MODEL_OR_RUNTIME_NOT_FOUND'
            keys = ('model_listed', 'sha256', 'filename')
        else:
            return 'ADAPTER_REQUIRED'
        if any(evidence.get(key) != previous.get(key) for key in keys): return 'LOCAL_MODEL_EVIDENCE_CHANGED'
        return None

    def _reconcile_detected_runtime(self, runtime, report, found, *, cancel=None, deadline=None):
        for identifier, record in list(self.registrations.items()):
            if cancel is not None: cancel.check()
            if deadline is not None and time.monotonic() >= deadline: break
            if not record.get('enabled') or record['runtime_id'] != runtime['id']: continue
            current = self._observed_registration(record, found, cancel=cancel)
            if cancel is not None: cancel.check()
            reason = self._observation_problem(record, report, current)
            if reason:
                evidence = dict(current['evidence']) if current else {}
                if reason == 'OLLAMA_REMOTE_MODEL_BLOCKED': evidence['source_locality'] = 'REMOTE'
                if cancel is not None: cancel.check()
                self._invalidate_registration(identifier, reason, evidence, cancel=cancel)

    def check_model_dispatch(self, candidate):
        if candidate['runtime_type'] == 'OLLAMA': return self.check_ollama_dispatch(candidate)
        report, found = self._probe(candidate['runtime_config'], threading.Event())
        current = self._observed_registration(candidate, found)
        reason = self._observation_problem(candidate, report, current)
        if reason:
            self._invalidate_registration(candidate['id'], reason, current['evidence'] if current else None)
            raise ValueError('LOCAL_AI_' + reason)
        return current['evidence']

    def check_ollama_dispatch(self, candidate):
        checked = self.ollama_metadata_check(candidate['runtime_config'], candidate['model_name'])
        previous = candidate.get('evidence', {}).get('locality_fingerprint')
        reason = (checked['locality_blockers'] or ['OLLAMA_IDENTITY_CHANGED'])[0]
        if checked['source_locality'] != 'LOCAL_VERIFIED' or not previous or checked['locality_fingerprint'] != previous:
            # A stale local classification loses routing authority even on disk failure.
            self._invalidate_registration(candidate['id'], reason, checked)
            raise ValueError('LOCAL_AI_' + reason)
        return checked

    def _eligibility(self, candidate):
        blockers = []
        if not candidate.get('validated_at'): blockers.append('VALIDATION_REQUIRED')
        if not candidate.get('verified_capabilities'): blockers.append('CAPABILITY_UNVERIFIED')
        for note in candidate.get('validation_notes', []):
            if note in {'RUNTIME_REQUIRED','GGUF_HEADER_INVALID','RUNTIME_MODEL_FILE_UNVERIFIED','RUNTIME_MODEL_PATH_MISMATCH','RUNTIME_MODEL_UNVERIFIED','MODEL_OR_RUNTIME_NOT_FOUND','WORKFLOW_ADAPTER_REQUIRED','ADAPTER_REQUIRED','OLLAMA_REMOTE_MODEL_BLOCKED','OLLAMA_LOCALITY_UNVERIFIED','OLLAMA_IDENTITY_CHANGED','LOCAL_MODEL_EVIDENCE_CHANGED'}: blockers.append(note)
        if candidate.get('license_required') and not candidate.get('license_confirmed'): blockers.append('LICENSE_VALIDATION_REQUIRED')
        if candidate['runtime_config'].get('credential_required'): blockers.append('LOCAL_AI_CREDENTIAL_BINDING_REQUIRED')
        candidate['enable_blockers'] = list(dict.fromkeys(blockers))
        candidate['enable_eligible'] = not blockers
        if 'LICENSE_VALIDATION_REQUIRED' in blockers: candidate['status'] = 'LICENSE_REQUIRED'
        elif 'GGUF_HEADER_INVALID' in blockers:
            candidate['status'] = 'INCOMPATIBLE'; candidate['compatible'] = 'UNSUPPORTED'
        elif blockers: candidate['status'] = 'VALIDATION_REQUIRED'

    def register(self, identifier, *, guard=None):
        self._guard(guard)
        with self.lock:
            if identifier in self.registrations: return copy.deepcopy(self.registrations[identifier])
            candidate = self._find(identifier)
            if not candidate.get('validated_at'): raise ValueError('LOCAL_AI_VALIDATE_BEFORE_REGISTER')
            candidate.update(enabled=False, registered_at=now())
            records = {**self.registrations, identifier: candidate}
            self._persist(registrations=records, guard=guard); self.registrations = records
            self._control_epochs[identifier] = self._control_epochs.get(identifier, 0) + 1
            self._publish_model(candidate)
            return copy.deepcopy(candidate)

    def configure_registration(self, identifier, value: RegistrationInput, *, guard=None):
        self._guard(guard)
        with self.lock:
            candidate = copy.deepcopy(self.registrations[identifier])
            if value.workflow_adapter_id and not any(a['id'] == value.workflow_adapter_id for a in self.workflow_adapters):
                raise ValueError('LOCAL_AI_WORKFLOW_ADAPTER_UNKNOWN')
            changed = candidate.get('workflow_adapter_id') != value.workflow_adapter_id
            candidate.update(**value.model_dump(), enabled=False)
            if changed: candidate.update(validated_at=None, verified_capabilities=[])
            self._eligibility(candidate)
            records = {**self.registrations, identifier: candidate}
            self._persist(registrations=records, guard=guard); self.registrations = records
            self._control_epochs[identifier] = self._control_epochs.get(identifier, 0) + 1
            self._publish_model(candidate); self._bridge(candidate)
            return copy.deepcopy(candidate)

    def enable(self, identifier, *, guard=None):
        self._guard(guard)
        # Revalidate immediately before explicit enable; newer controls win by CAS.
        with self.lock:
            if identifier not in self.registrations: raise KeyError(identifier)
            expected_epoch = self._control_epochs.get(identifier, 0)
        candidate = self.validate(identifier, guard=guard)
        with self.lock:
            if identifier not in self.registrations: raise KeyError(identifier)
            if self._control_epochs.get(identifier, 0) != expected_epoch + 1:
                raise ValueError('LOCAL_AI_CONFIGURATION_CHANGED')
            if not candidate['enable_eligible']: raise ValueError('LOCAL_AI_ENABLE_BLOCKED:' + ','.join(candidate['enable_blockers']))
            candidate.update(enabled=True, status='DEGRADED', enabled_at=now())
            # Validate adapters before committing enabled state; callback never launches.
            self._guard(guard)
            self._bridge(candidate)
            records = {**self.registrations, identifier: candidate}
            try: self._persist(registrations=records, guard=guard)
            except ValueError:
                self._bridge({**candidate, 'enabled': False}); raise
            self.registrations = records
            self._control_epochs[identifier] = expected_epoch + 2
            self._publish_model(candidate)
            return copy.deepcopy(candidate)

    def disable(self, identifier, *, guard=None):
        self._guard(guard)
        with self.lock:
            candidate = {**self.registrations[identifier], 'enabled': False, 'status': 'DISABLED'}
            records = {**self.registrations, identifier: candidate}
            self._persist(registrations=records, guard=guard); self.registrations = records
            self._control_epochs[identifier] = self._control_epochs.get(identifier, 0) + 1
            self._bridge(candidate); self._publish_model(candidate)
            return copy.deepcopy(candidate)

    def remove(self, identifier, *, guard=None):
        self._guard(guard)
        with self.lock:
            candidate = self.registrations[identifier]
            records = {key:value for key,value in self.registrations.items() if key != identifier}
            self._persist(registrations=records, guard=guard); self.registrations = records
            self._control_epochs[identifier] = self._control_epochs.get(identifier, 0) + 1
            self._bridge({**candidate, 'enabled': False})
            self.center.models.pop(identifier, None)
            return {'removed': True, 'model_files_deleted': False}

    def _bridge(self, candidate):
        if self.route_bridge: self.route_bridge(copy.deepcopy(candidate))

    def _publish_model(self, candidate):
        runtime_type = getattr(RuntimeType, candidate['runtime_type'], RuntimeType.CUSTOM_HTTP)
        identity_id = None
        if self.center.identity_store:
            from ..stable_identity import canonical_model_identity_key
            identity_id = self.center.identity_store.get_or_create('model', canonical_model_identity_key(candidate['provider_id'], candidate['id']))
        self.center.models[candidate['id']] = ModelDefinition(candidate['id'], candidate['display_name'], candidate['family'], '', 'discovered',
            tuple(Capability(value) for value in candidate['declared_capabilities'] if value in Capability._value2member_map_),
            runtime_type, 'GGUF' if candidate['local_path'] else 'RUNTIME_MODEL', source=candidate['source'],
            local_paths=(candidate['local_path'],) if candidate['local_path'] else (),
            status=ModelStatus.DEGRADED if candidate.get('enabled') else ModelStatus.DISABLED,
            metadata={'local_discovery': True, 'enabled': candidate.get('enabled', False),
                'declared_capabilities': candidate['declared_capabilities'], 'verified_capabilities': candidate['verified_capabilities'],
                'validation_status': candidate['status'], 'inference_verified': False, 'runtime_id': candidate['runtime_id']}, identity_id=identity_id)

    def media_routes(self):
        with self.lock:
            records = copy.deepcopy([r for r in self.registrations.values() if r.get('enabled') and 'IMAGE' in r.get('verified_capabilities', [])])
        health = {}
        rows = []
        for record in records:
            endpoint = record['runtime_config']['endpoint']
            key = (record['runtime_type'], endpoint)
            if key not in health:
                path = '/system_stats' if key[0] == 'COMFYUI' else '/sdapi/v1/sd-models'
                try:
                    self.client.json(endpoint, path)
                    health[key] = True
                except ProbeFailure:
                    health[key] = False
            rows.append({'provider_id': record['provider_id'], 'display_name': record['display_name'],
                         'endpoint': endpoint, 'default_model': record['id'],
                         'api_style': 'automatic1111' if record['runtime_type'] == 'AUTOMATIC1111' else 'comfyui',
                         'local': True, 'enabled': True, 'requires_credential': False,
                         'credential_configured': True, 'configured': True, 'registered': True,
                         'reachable': health[key], 'secret': None, 'inference_verified': False})
        return rows
