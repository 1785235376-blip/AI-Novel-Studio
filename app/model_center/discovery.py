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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from .discovery_probes import LocalProbeClient, ProbeFailure, candidate_id, executable_metadata, gguf_metadata, host_hardware, infer_family, scan_gguf_roots, ollama_remote_declaration, ollama_locality_evidence, read_ollama_local_metadata
from .discovery_types import DiscoverySettingsInput, LocalRuntimeInput, RegistrationInput, safe_local_path
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
            roots = DiscoverySettingsInput(scan_roots=data['settings']['scan_roots']).model_dump()
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

    def _persist(self, settings=None, registrations=None):
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

    def configure_roots(self, values: DiscoverySettingsInput):
        with self.lock:
            settings = {**self.settings, 'scan_roots': values.scan_roots}
            self._persist(settings=settings); self.settings = settings
            return copy.deepcopy(settings)

    def configure_runtime(self, value: LocalRuntimeInput, runtime_id: str | None = None):
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
            self._persist(settings=settings, registrations=records)
            self.settings, self.registrations = settings, records
            for r in changed:
                self._control_epochs[r['id']] = self._control_epochs.get(r['id'], 0) + 1
                self._publish_model(r); self._bridge(r)
            return copy.deepcopy(item)

    def _runtimes(self):
        defaults = [LocalRuntimeInput(name='Ollama', type='OLLAMA', endpoint='http://127.0.0.1:11434', modality='TEXT'),
                    LocalRuntimeInput(name='ComfyUI', type='COMFYUI', endpoint='http://127.0.0.1:8188'),
                    LocalRuntimeInput(name='Automatic1111', type='AUTOMATIC1111', endpoint='http://127.0.0.1:7860', modality='IMAGE')]
        result = [{'id': 'discovery-' + item.type.lower(), **item.model_dump()} for item in defaults]
        for item in self.center.runtimes.values():
            if item.runtime_type not in {RuntimeType.LLAMA_CPP, RuntimeType.COMFYUI} or item.id.startswith('local-'): continue
            try:
                config = LocalRuntimeInput(name=item.id, type=str(item.runtime_type), endpoint=item.base_url,
                    management=str(item.management), executable=item.executable, model_path=item.model_path,
                    context_size=item.context_size or 8192, gpu_layers=item.gpu_layers or 0,
                    threads=item.threads, batch_size=item.batch_size, health_endpoint=item.health_endpoint)
                result.append({'id': item.id, **config.model_dump()})
            except ValueError: continue
        # Explicit user entries supersede default endpoint probes, without duplicate candidates.
        result += self.configured_runtime_sources
        result += self.settings['runtimes']
        unique = {}
        for item in result: unique[(item['type'], item['endpoint'], item.get('model_path', ''))] = item
        return list(unique.values())[:20]

    def start_scan(self):
        with self.lock:
            if self.scan and self.scan['status'] == 'RUNNING': return copy.deepcopy(self.scan)
            self.cancel_event = threading.Event()
            job = {'id': uuid4().hex, 'status': 'RUNNING', 'runtimes': [], 'candidates': [], 'errors': [],
                   'started_at': now(), 'finished_at': None}
            self.scan = job
            runtimes, roots = copy.deepcopy(self._runtimes()), list(self.settings['scan_roots'])
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
        deadline = time.monotonic() + 45
        try:
            hardware = self.hardware_probe()
            with self.lock: self.hardware = hardware
            candidates = {}
            for runtime in runtimes:
                if cancel.is_set() or time.monotonic() >= deadline: break
                report, found = self._probe(runtime, cancel)
                with self.lock:
                    job['runtimes'].append(report)
                    self._reconcile_detected_runtime(runtime, report, found)
                    for candidate in found: candidates[candidate['id']] = candidate
                    job['candidates'] = list(candidates.values())
                    if report['status'] not in {'RUNNING', 'DISCOVERED'}:
                        job['errors'].append({'runtime_id': runtime['id'], 'code': report['notes'][-1] if report['notes'] else report['status']})
            llama = next((r for r in runtimes if r['type'] == 'LLAMA_CPP'), None)
            if llama:
                for path in scan_gguf_roots(roots, cancel, deadline):
                    candidate = self._candidate(llama, path.name, local_path=str(path), evidence=gguf_metadata(path))
                    with self.lock:
                        candidates.setdefault(candidate['id'], candidate)
                        job['candidates'] = list(candidates.values())
            with self.lock:
                if time.monotonic() >= deadline: job['errors'].append({'code': 'LOCAL_AI_SCAN_BUDGET_REACHED'})
        except Exception:
            with self.lock: job['errors'].append({'code': 'LOCAL_AI_SCAN_FAILED'})
        finally:
            with self.lock:
                job['status'] = 'CANCELLED' if cancel.is_set() else ('PARTIAL' if job['errors'] else 'COMPLETED')
                job['finished_at'] = now()

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

    def _probe(self, runtime, cancel):
        report = {key: runtime[key] for key in ('id', 'name', 'type', 'endpoint', 'management')}
        report.update(status='NOT_FOUND', version=None, notes=[])
        found = []
        def get(path):
            if cancel.is_set(): raise ProbeFailure('LOCAL_AI_CANCELLED')
            return self.client.json(runtime['endpoint'], path)
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
                for name, loaders in names.items():
                    found.append(self._candidate(runtime, name, family_hint=' '.join(loaders), evidence={
                        'model_listed': True, 'model_file_exists': None, 'loader_nodes': loaders, 'loader_bindings': bindings[name],
                        'node_classes': nodes, 'nodes_fingerprint': digest(info), 'workflow_status': 'NOT_CONFIGURED', 'generation_verified': False}))
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
                report.update(executable_metadata(executable or ''))
                report['notes'].append('EXECUTABLE_NOT_EXECUTED')
                if path:
                    found.append(self._candidate(runtime, Path(path).name, local_path=path, evidence=gguf_metadata(Path(path))))
                try:
                    payload = get(runtime.get('health_endpoint') or '/v1/models')
                    if not isinstance(payload, dict): raise ProbeFailure('LOCAL_AI_INVALID_RESPONSE')
                    listed = payload.get('data', [])
                    report['available_models'] = [item['id'] for item in listed[:512] if isinstance(item, dict) and isinstance(item.get('id'), str)] if isinstance(listed, list) else []
                    for item in found: item['evidence']['runtime_advertised_models'] = report['available_models']
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
                    if isinstance(model, dict) and isinstance(model.get('id'), str) and len(model['id']) <= 256:
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
        return report, found

    def _find(self, identifier):
        for item in (self.scan or {}).get('candidates', []):
            if item['id'] == identifier: return copy.deepcopy(item)
        if identifier in self.registrations: return copy.deepcopy(self.registrations[identifier])
        raise KeyError(identifier)

    def validate(self, identifier):
        with self.lock:
            candidate = self._find(identifier)
            expected_epoch = self._control_epochs.get(identifier, 0)
            saved = self.registrations.get(identifier)
            if saved:
                for field in ('workflow_adapter_id','license_confirmed'): candidate[field] = saved.get(field, '' if field == 'workflow_adapter_id' else False)
            runtime = next((r for r in self._runtimes() if r['id'] == candidate['runtime_id']), candidate['runtime_config'])
            fingerprint = digest(runtime)
        # Metadata-only validation; never generation or --version.
        report, detected = self._probe(runtime, threading.Event())
        current = next((item for item in detected if item['id'] == identifier), None)
        evidence = current['evidence'] if current else {}
        notes, verified = ['INFERENCE_NOT_RUN', 'CURRENT_GPU_NOT_VERIFIED'], []
        kind = runtime['type']
        if kind == 'LLAMA_CPP':
            evidence = gguf_metadata(Path(candidate['local_path']))
            architecture = str(evidence.get('general.architecture', '')).casefold()
            if evidence.get('header_valid') and architecture.startswith(('qwen', 'llama', 'gemma', 'mistral', 'phi', 'deepseek')):
                verified = ['TEXT']
            if not evidence.get('header_valid'): notes.append('GGUF_HEADER_INVALID')
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
                checked = self.ollama_metadata_check(runtime, candidate['model_name'])
                evidence.update(checked)
                notes.extend(checked['locality_blockers'])
                candidate['source_locality'] = checked['source_locality']
                candidate['local'] = checked['source_locality'] == 'LOCAL_VERIFIED'
                candidate['source'] = 'OLLAMA_HOSTED' if checked['source_locality'] == 'REMOTE' else 'OLLAMA'
                capabilities = checked['reported_capabilities']
                if checked['source_locality'] == 'LOCAL_VERIFIED':
                    if 'completion' in capabilities: verified.append('TEXT')
                    if 'vision' in capabilities: verified.append('VISION')
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
        with self.lock:
            latest_runtime = next((r for r in self._runtimes() if r['id'] == runtime['id']), runtime)
            if fingerprint != digest(latest_runtime) or expected_epoch != self._control_epochs.get(identifier, 0):
                raise ValueError('LOCAL_AI_CONFIGURATION_CHANGED')
            if self.scan:
                self.scan['candidates'] = [candidate if item['id'] == identifier else item for item in self.scan['candidates']]
            if identifier in self.registrations:
                records = {**self.registrations, identifier: candidate}
                self._persist(registrations=records); self.registrations = records
                self._control_epochs[identifier] = expected_epoch + 1
                self._publish_model(candidate); self._bridge(candidate)
            return copy.deepcopy(candidate)

    def ollama_metadata_check(self, runtime, model_name):
        from ..providers import OllamaProvider
        return read_ollama_local_metadata(self.client, runtime['endpoint'], model_name,
                                          OllamaProvider(runtime['endpoint']).list_models)

    def _invalidate_registration(self, identifier, reason, evidence=None):
        with self.lock:
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
            self.registrations = records
            self._control_epochs[identifier] = self._control_epochs.get(identifier, 0) + 1
            try: self._persist(registrations=records)
            except ValueError: self.persistence_error = 'LOCAL_AI_CONFIG_WRITE_FAILED'
            self._publish_model(blocked); self._bridge(blocked)

    def _reconcile_detected_runtime(self, runtime, report, found):
        if runtime['type'] != 'OLLAMA': return
        observed = {item['id']: item for item in found}
        for identifier, record in list(self.registrations.items()):
            if not record.get('enabled') or record['runtime_id'] != runtime['id']: continue
            current = observed.get(identifier)
            if not current or report['status'] != 'RUNNING':
                self._invalidate_registration(identifier, 'OLLAMA_LOCALITY_UNVERIFIED')
                continue
            evidence = current['evidence']
            if ollama_remote_declaration(evidence) == 'REMOTE':
                self._invalidate_registration(identifier, 'OLLAMA_REMOTE_MODEL_BLOCKED', {**evidence, 'source_locality':'REMOTE'})
            elif any(evidence.get(key) != record.get('evidence', {}).get(key) for key in ('digest', 'size', 'details', 'remote_model', 'remote_host')):
                self._invalidate_registration(identifier, 'OLLAMA_IDENTITY_CHANGED', evidence)

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
            if note in {'RUNTIME_REQUIRED','GGUF_HEADER_INVALID','RUNTIME_MODEL_PATH_MISMATCH','RUNTIME_MODEL_UNVERIFIED','MODEL_OR_RUNTIME_NOT_FOUND','WORKFLOW_ADAPTER_REQUIRED','ADAPTER_REQUIRED','OLLAMA_REMOTE_MODEL_BLOCKED','OLLAMA_LOCALITY_UNVERIFIED','OLLAMA_IDENTITY_CHANGED'}: blockers.append(note)
        if candidate.get('license_required') and not candidate.get('license_confirmed'): blockers.append('LICENSE_VALIDATION_REQUIRED')
        if candidate['runtime_config'].get('credential_required'): blockers.append('LOCAL_AI_CREDENTIAL_BINDING_REQUIRED')
        candidate['enable_blockers'] = list(dict.fromkeys(blockers))
        candidate['enable_eligible'] = not blockers
        if 'LICENSE_VALIDATION_REQUIRED' in blockers: candidate['status'] = 'LICENSE_REQUIRED'
        elif 'GGUF_HEADER_INVALID' in blockers:
            candidate['status'] = 'INCOMPATIBLE'; candidate['compatible'] = 'UNSUPPORTED'
        elif blockers: candidate['status'] = 'VALIDATION_REQUIRED'

    def register(self, identifier):
        with self.lock:
            if identifier in self.registrations: return copy.deepcopy(self.registrations[identifier])
            candidate = self._find(identifier)
            if not candidate.get('validated_at'): raise ValueError('LOCAL_AI_VALIDATE_BEFORE_REGISTER')
            candidate.update(enabled=False, registered_at=now())
            records = {**self.registrations, identifier: candidate}
            self._persist(registrations=records); self.registrations = records
            self._control_epochs[identifier] = self._control_epochs.get(identifier, 0) + 1
            self._publish_model(candidate)
            return copy.deepcopy(candidate)

    def configure_registration(self, identifier, value: RegistrationInput):
        with self.lock:
            candidate = copy.deepcopy(self.registrations[identifier])
            if value.workflow_adapter_id and not any(a['id'] == value.workflow_adapter_id for a in self.workflow_adapters):
                raise ValueError('LOCAL_AI_WORKFLOW_ADAPTER_UNKNOWN')
            changed = candidate.get('workflow_adapter_id') != value.workflow_adapter_id
            candidate.update(**value.model_dump(), enabled=False)
            if changed: candidate.update(validated_at=None, verified_capabilities=[])
            self._eligibility(candidate)
            records = {**self.registrations, identifier: candidate}
            self._persist(registrations=records); self.registrations = records
            self._control_epochs[identifier] = self._control_epochs.get(identifier, 0) + 1
            self._publish_model(candidate); self._bridge(candidate)
            return copy.deepcopy(candidate)

    def enable(self, identifier):
        # Revalidate immediately before explicit enable; newer controls win by CAS.
        with self.lock:
            if identifier not in self.registrations: raise KeyError(identifier)
            expected_epoch = self._control_epochs.get(identifier, 0)
        candidate = self.validate(identifier)
        with self.lock:
            if identifier not in self.registrations: raise KeyError(identifier)
            if self._control_epochs.get(identifier, 0) != expected_epoch + 1:
                raise ValueError('LOCAL_AI_CONFIGURATION_CHANGED')
            if not candidate['enable_eligible']: raise ValueError('LOCAL_AI_ENABLE_BLOCKED:' + ','.join(candidate['enable_blockers']))
            candidate.update(enabled=True, status='DEGRADED', enabled_at=now())
            # Validate adapters before committing enabled state; callback never launches.
            self._bridge(candidate)
            records = {**self.registrations, identifier: candidate}
            try: self._persist(registrations=records)
            except ValueError:
                self._bridge({**candidate, 'enabled': False}); raise
            self.registrations = records
            self._control_epochs[identifier] = expected_epoch + 2
            self._publish_model(candidate)
            return copy.deepcopy(candidate)

    def disable(self, identifier):
        with self.lock:
            candidate = {**self.registrations[identifier], 'enabled': False, 'status': 'DISABLED'}
            records = {**self.registrations, identifier: candidate}
            self._persist(registrations=records); self.registrations = records
            self._control_epochs[identifier] = self._control_epochs.get(identifier, 0) + 1
            self._bridge(candidate); self._publish_model(candidate)
            return copy.deepcopy(candidate)

    def remove(self, identifier):
        with self.lock:
            candidate = self.registrations[identifier]
            records = {key:value for key,value in self.registrations.items() if key != identifier}
            self._persist(registrations=records); self.registrations = records
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
