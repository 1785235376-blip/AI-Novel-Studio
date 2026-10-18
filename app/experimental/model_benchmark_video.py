"""Bounded video samples over the original Studio owner; no queue or transport.

All observations include orchestration/polling, not model inference. A zero
estimate never proves an actual bill; host compute and hardware are unmeasured.
"""
from __future__ import annotations

import copy
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import time

from .common import StaleSourceError, check_version, change_row, new_row, now
from .model_broker import digest, implementation_hash

CONTRACT = 'studio-video-benchmark/1'
PRESET = {'width': 256, 'height': 256, 'duration_seconds': 1, 'frame_rate': 8, 'seed': 7}
FLAGS = ('model_benchmark_v2', 'model_broker_v2', 'narrative_production_v2', 'ai_execution_v2')
BINDING_KEYS = {'contract', 'run_id', 'index', 'actor', 'scope_key', 'incarnation', 'set_hash', 'route_fingerprint'}


def validate_binding(value, context):
    if (not isinstance(value, dict) or set(value) != BINDING_KEYS or value.get('contract') != CONTRACT
            or type(value.get('index')) is not int or not 0 <= value['index'] < 6
            or any(value.get(k) != context.get(k) for k in ('actor', 'scope_key', 'incarnation'))):
        raise ValueError('BENCHMARK_VIDEO_BINDING_INVALID')
    for key in ('run_id', 'scope_key', 'set_hash', 'route_fingerprint'):
        if not isinstance(value.get(key), str) or len(value[key]) != 64 or any(c not in '0123456789abcdef' for c in value[key]):
            raise ValueError('BENCHMARK_VIDEO_BINDING_INVALID')
    return copy.deepcopy(value)


def video_candidates(runtime, registry):
    from ..model_center.discovery_bridge import LocalVideoAdapter
    from ..services.studio_video_provider import ComfyUIVideoProvider
    from ..services.studio_video_provider_recipes import build_workflow, timing
    recipes = type('VideoRecipeImplementation', (), {'build': staticmethod(build_workflow), 'timing': staticmethod(timing)})
    rows = []
    for pid, adapter in list(registry.items()):
        if type(adapter) is not LocalVideoAdapter:
            continue
        try:
            config = adapter.studio_configuration()
            candidate = adapter.bridge.guard(adapter.candidate['id'])
            if pid != candidate['provider_id'] or not adapter.capabilities().get('text_to_video'):
                continue
            identity = {'provider_id': pid, 'model_id': candidate['id'],
                'adapter_hash': implementation_hash(LocalVideoAdapter), 'delegate_hash': implementation_hash(ComfyUIVideoProvider),
                'workflow_hash': digest([config['video_recipe'], implementation_hash(recipes)]),
                'registration_digest': config['registration_digest'], 'model_version': candidate.get('model_evidence_fingerprint'),
                'runtime_hash': candidate.get('runtime_fingerprint'), 'runtime_version': candidate.get('evidence', {}).get('runtime_version'),
                'quantization': None, 'hardware_hash': None, 'source_locality': 'LOCAL_VERIFIED',
                'license_confirmed': bool(candidate.get('license_confirmed')), 'license_state': 'USER_CONFIRMED_LOCAL_USE',
                'definition': {'operations': ['text_to_video']},
                'execution_node_id': str(runtime.execution_node_identity.store.get('execution_node', 'local') or '')}
            reasons = [] if identity['license_confirmed'] else ['LICENSE_CONFIRMATION_REQUIRED']
            rows.append({'route_id': digest(['studio-video', pid, candidate['id']]), 'provider_id': pid,
                'model_id': candidate['id'], 'display_name': candidate.get('display_name') or candidate['family'],
                'capability': 'VIDEO', 'context_window': None, 'cloud': False, 'synthetic': False,
                'candidate_profile': 'LOCAL_STUDIO_VIDEO_V1', 'identity': identity,
                # Reopened original jobs bind the exact persisted registration,
                # not a process address. Production still pins the live adapter
                # instance and rechecks its configuration on each wire action.
                'fingerprint': digest(identity), 'binding_hash': digest(identity),
                'available': not reasons, 'reasons': reasons, 'verification': 'ADAPTER_CONTRACT_ONLY'})
        except (ValueError, KeyError, TypeError, RuntimeError):
            continue
    return rows


class VideoBenchmarkCoordinator:
    def __init__(self, benchmark, production):
        self.bench, self.production, self.broker = benchmark, production, benchmark.broker

    @staticmethod
    def _flags(execution=True):
        from .flags import require_flag
        for flag in FLAGS if execution else ('model_benchmark_v2', 'narrative_production_v2'): require_flag(flag)

    def visible(self, nid, row):
        try:
            with self.production.store.existing_owner_only():
                return row.get('studio_incarnation') == self.production.store.incarnation(nid)
        except (FileNotFoundError, ValueError):
            return False

    def _read(self, nid, scope, actor, rid, guard, *, current=True):
        guard(); self._flags(execution=current)
        row = self.bench.get(nid, scope, self.bench.RUNS, rid)
        if row.get('video_contract') != CONTRACT or row['created_by'] != actor or not self.visible(nid, row):
            raise FileNotFoundError(rid)
        if current:
            test_set = self.bench.get(nid, scope, self.bench.SETS, row['set_id'])
            if test_set['version'] != row['set_version'] or self.bench.set_hash(test_set) != row['set_hash']:
                raise StaleSourceError('BENCHMARK_SET_CHANGED')
            route = self.broker.current_route(row['route_id'])
            if not route['available'] or route['cloud'] or route['fingerprint'] != row['route_fingerprint']:
                raise StaleSourceError('BENCHMARK_ROUTE_CHANGED')
        guard()
        return row

    @contextmanager
    def _transaction(self, nid, scope, actor, rid, guard, *, version=None):
        # Original raw scope -> project order, never across original job calls.
        with self.bench.store.transaction(nid, scope) as document:
            with self.production.store.owner_lease(nid):
                guard()
                row = document['collections'].get(self.bench.RUNS, {}).get(rid)
                if (not row or row['created_by'] != actor or row.get('scope') != scope
                        or row.get('studio_incarnation') != self.production.store.incarnation(nid)):
                    raise FileNotFoundError(rid)
                if version is not None: check_version(row, version)
                yield document, row
                guard()

    def start(self, nid, scope, actor, body, test_set, guard):
        self._flags(); base = self.production._base(nid, scope, actor, guard)
        if {case['kind'] for case in test_set['cases']} != {'VIDEO_WORKFLOW'}:
            raise ValueError('BENCHMARK_MIXED_MODALITIES_UNSUPPORTED')
        if any(case['rule'] != 'NONEMPTY' for case in test_set['cases']):
            raise ValueError('BENCHMARK_VIDEO_DECODE_RULE_REQUIRED')
        if test_set['max_cost_microusd'] != 0:
            raise ValueError('BENCHMARK_VIDEO_ZERO_EXTERNAL_PROVIDER_BUDGET_REQUIRED')
        route = self.broker.current_route(body.route_id)
        if (route['capability'] != 'VIDEO' or route.get('candidate_profile') != 'LOCAL_STUDIO_VIDEO_V1'
                or not route['available'] or route['cloud']):
            raise ValueError('BENCHMARK_LOCAL_REGISTERED_VIDEO_ROUTE_REQUIRED')
        key = digest([actor, body.request_id, base['incarnation']])
        input_hash = digest(body.model_dump(exclude={'request_id'}))
        old = next((r for r in self.bench.runs(nid, scope, actor) if r['id'] == key), None)
        if old:
            if old['input_hash'] != input_hash: raise ValueError('BENCHMARK_IDEMPOTENCY_MISMATCH')
            return old
        preview = self.broker.preview(nid, scope, actor, {'capability': 'VIDEO', 'policy': 'CUSTOM',
            'preferred_route': body.route_id, 'profile': 'LOCAL_ONLY', 'max_cost_microusd': 0,
            'require_confirmed_license': True}, guard)
        if not preview['chosen']: raise ValueError('BENCHMARK_NO_LEGAL_ROUTE')
        with self.bench.store.transaction(nid, scope) as document:
            with self.production.store.owner_lease(nid):
                guard()
                if self.production.store.incarnation(nid) != base['incarnation']:
                    raise StaleSourceError('BENCHMARK_VIDEO_OWNER_CHANGED')
                latest = document['collections'][self.bench.SETS][body.set_id]
                check_version(latest, body.expected_set_version)
                rows = document['collections'].setdefault(self.bench.RUNS, {})
                if key in rows:
                    if rows[key]['input_hash'] != input_hash: raise ValueError('BENCHMARK_IDEMPOTENCY_MISMATCH')
                    return copy.deepcopy(rows[key])
                row = new_row(nid, scope, actor, {'status': 'READY', 'input_hash': input_hash,
                    'video_contract': CONTRACT, 'studio_incarnation': base['incarnation'],
                    'set_id': body.set_id, 'set_version': test_set['version'], 'set_hash': self.bench.set_hash(test_set),
                    'route_id': body.route_id, 'route_fingerprint': route['fingerprint'], 'route_identity': route['identity'],
                    'preview_id': preview['id'], 'preview_version': preview['version'],
                    'total': len(test_set['cases']) * test_set['repetitions'], 'completed': 0, 'results': [],
                    'capability': 'VIDEO', 'video_samples': {}, 'video_sample': None,
                    'preset': copy.deepcopy(PRESET), 'cold_start_state': 'NOT_MEASURED', 'automatic_replay': False})
                row['id'] = key; rows[key] = row
                return copy.deepcopy(row)

    def preview(self, nid, scope, actor, rid, version, guard):
        row = self._read(nid, scope, actor, rid, guard); check_version(row, version)
        if row['status'] != 'READY' or row['completed'] >= row['total']:
            raise ValueError('BENCHMARK_RUN_NOT_READY')
        test_set = self.bench.get(nid, scope, self.bench.SETS, row['set_id'])
        index = row['completed']; case = test_set['cases'][index % len(test_set['cases'])]
        route = self.broker.current_route(row['route_id'])
        binding = {'contract': CONTRACT, 'run_id': rid, 'index': index, 'actor': actor,
            'scope_key': self.production.store.key(nid, scope), 'incarnation': row['studio_incarnation'],
            'set_hash': row['set_hash'], 'route_fingerprint': row['route_fingerprint']}
        command = {'operation_id': 'm7.video.t2v', 'request_id': 'benchmark-' + digest([rid, index]),
            'provider_id': route['provider_id'], 'model_id': route['model_id'], 'prompt': case['prompt'],
            'parameters': copy.deepcopy(PRESET), 'source_snapshots': [], 'allow_cloud': False}
        production_preview, context, _ = self.production.preview(nid, scope, actor, command, guard, benchmark_binding=binding)
        sample = {'index': index, 'binding': binding, 'status': 'PREVIEWED', 'job': None,
            'job_id': digest([context['scope_key'], context['incarnation'], actor, context['request_id']]),
            'request_digest': context['request_digest'], 'reservation_id': None,
            'preview': {'production_preview': production_preview,
                'preview_digest': digest([binding, production_preview['preview_digest'], row['preview_id'], row['preview_version']])}}
        with self._transaction(nid, scope, actor, rid, guard, version=version) as (_, live):
            change_row(live, actor, version, lambda r: r.update(video_sample=sample))
            return copy.deepcopy(live)

    def publication_guard(self, nid, scope, actor, context, document):
        """Read only the supplied scope snapshot; safe before asset/project locks."""
        self._flags()
        binding = validate_binding(context['benchmark_binding'], context)
        row = document['collections'].get(self.bench.RUNS, {}).get(binding['run_id'])
        sample = (row or {}).get('video_samples', {}).get(str(binding['index']))
        test_set = document['collections'].get(self.bench.SETS, {}).get((row or {}).get('set_id'))
        if (not row or row.get('studio_incarnation') != binding['incarnation'] or row['created_by'] != actor
                or row['scope'] != scope or row['status'] not in {'RUNNING', 'READY', 'COMPLETED'}
                or not sample or sample['binding'] != binding or sample['request_digest'] != context['request_digest']
                or not test_set or test_set['version'] != row['set_version'] or self.bench.set_hash(test_set) != row['set_hash']):
            raise StaleSourceError('BENCHMARK_VIDEO_AUTHORITY_CHANGED')
        if sample.get('status') != 'COMPLETED':
            if row['status'] != 'RUNNING' or datetime.now(timezone.utc) >= datetime.fromisoformat(sample['deadline_at']):
                raise StaleSourceError('BENCHMARK_VIDEO_CANCELLED_OR_TIMEOUT')
        return row, sample

    def guard_dispatch(self, nid, scope, actor, context):
        binding = context['benchmark_binding']
        row = self._read(nid, scope, actor, binding['run_id'], lambda: None)
        document = self.bench.store.read(nid, scope)
        _, sample = self.publication_guard(nid, scope, actor, context, document)
        if row['status'] != 'RUNNING' or not sample.get('reservation_id'):
            raise StaleSourceError('BENCHMARK_VIDEO_RESERVATION_REQUIRED')
        self.broker.guard_dispatch(nid, scope, actor, sample['reservation_id'], sample['job_id'],
            lambda: self._active(nid, scope, actor, context))

    def _active(self, nid, scope, actor, context):
        self._read(nid, scope, actor, context['benchmark_binding']['run_id'], lambda: None)
        self.publication_guard(nid, scope, actor, context, self.bench.store.read(nid, scope))

    @staticmethod
    def _action(job):
        from ..creative.production_execution_models import MediaJobAction
        return MediaJobAction(expected_version=job['version'], expected_request_digest=job['request_digest'])

    def _job(self, nid, scope, actor, sample, guard):
        return self.production.get(nid, scope, actor, 'video', sample['job_id'], guard, benchmark_binding=sample['binding'])

    def candidate(self, nid, scope, actor, rid, index, guard):
        row = self._read(nid, scope, actor, rid, guard, current=False)
        sample = row['video_samples'].get(str(index))
        if not sample: raise FileNotFoundError(rid)
        return self.production.candidate(nid, scope, actor, 'video', sample['job_id'], guard,
            benchmark_binding=sample['binding'])

    def validate_outputs(self, nid, scope, actor, row, guard):
        self._read(nid, scope, actor, row['id'], guard)
        for result in row['results']:
            meta, _ = self.candidate(nid, scope, actor, row['id'], result['index'], guard)
            candidate = (result.get('media_receipt') or {}).get('output_candidate') or {}
            if meta['id'] != candidate.get('id') or meta['sha256'] != candidate.get('digest'):
                raise StaleSourceError('BENCHMARK_VIDEO_OUTPUT_CHANGED')

    def _save_sample(self, nid, scope, actor, rid, sample, guard, *, status=None):
        with self._transaction(nid, scope, actor, rid, guard) as (_, row):
            existing = row.get('video_samples', {}).get(str(sample['index']))
            active = row.get('video_sample') or {}
            if (row['status'] != 'RUNNING' or not existing or existing['binding'] != sample['binding']
                    or active.get('index') != sample['index'] or active.get('binding') != sample['binding']
                    or existing.get('status') in {'COMPLETED', 'FAILED'}):
                return copy.deepcopy(row)
            def update(r):
                r['video_samples'][str(sample['index'])] = copy.deepcopy(sample)
                r['video_sample'] = copy.deepcopy(sample)
                if status: r['status'] = status
            change_row(row, actor, row['version'], update)
            return copy.deepcopy(row)

    def execute(self, nid, scope, actor, rid, version, reviewed_preview_digest, guard):
        from ..creative.production_execution_models import MediaCreate
        row = self._read(nid, scope, actor, rid, guard); check_version(row, version)
        sample = copy.deepcopy(row.get('video_sample'))
        if not sample or sample['preview']['preview_digest'] != reviewed_preview_digest:
            raise ValueError('BENCHMARK_VIDEO_EXACT_PREVIEW_REQUIRED')
        continued = row['status'] == 'RUNNING'
        if continued:
            job = self._job(nid, scope, actor, sample, guard)
            if job['status'] != 'QUEUED' or sample.get('status') not in {'QUEUED', 'ADMISSION_UNKNOWN'}:
                raise ValueError('BENCHMARK_VIDEO_ALREADY_SUBMITTED')
        elif row['status'] != 'READY' or sample['index'] != row['completed']:
            raise ValueError('BENCHMARK_RUN_NOT_READY')
        original = sample['preview']['production_preview']
        refreshed = self.production.preview(nid, scope, actor, original['command'], guard, benchmark_binding=sample['binding'])[0]
        if refreshed != original: raise StaleSourceError('BENCHMARK_VIDEO_PREVIEW_CHANGED')
        test_set = self.bench.get(nid, scope, self.bench.SETS, row['set_id'])
        if not continued:
            sample.update(status='ADMISSION_RESERVED', started_at=now(),
                deadline_at=(datetime.now(timezone.utc) + timedelta(seconds=test_set['timeout_seconds'])).isoformat())
        with self._transaction(nid, scope, actor, rid, guard, version=version) as (_, live):
            def claim(r):
                r['status'] = 'RUNNING'; r['video_samples'][str(sample['index'])] = copy.deepcopy(sample); r['video_sample'] = copy.deepcopy(sample)
            change_row(live, actor, version, claim)
        started = time.perf_counter()
        try:
            if not continued:
                reservation = self.broker.reserve(nid, scope, actor, row['preview_id'], row['preview_version'],
                    'video-' + digest([rid, sample['index']]), sample['job_id'],
                    lambda: self._active(nid, scope, actor, {**sample['binding'], 'benchmark_binding': sample['binding'], 'request_digest': sample['request_digest']}),
                    authorization_digest=digest([sample['binding'], sample['request_digest']]))
                sample['reservation_id'] = reservation['id']
                self._save_sample(nid, scope, actor, rid, sample, guard)
                job = self.production.create(nid, scope, actor, MediaCreate(command=original['command'],
                    reviewed_preview_digest=original['preview_digest']), guard, benchmark_binding=sample['binding'])
                sample.update(job=job, status='QUEUED')
                self._save_sample(nid, scope, actor, rid, sample, guard)
            self._active(nid, scope, actor, {**sample['binding'], 'benchmark_binding': sample['binding'], 'request_digest': sample['request_digest']})
            job = self.production.execute(nid, scope, actor, 'video', sample['job_id'], self._action(job), guard,
                benchmark_binding=sample['binding'])
            sample['submit_action_ms'] = round((time.perf_counter() - started) * 1000, 3)
            return self._observe(nid, scope, actor, rid, sample, job, guard)
        except Exception:
            sample['status'] = 'ADMISSION_UNKNOWN'
            job_missing = False
            try:
                # Receipt-only cleanup cannot grant execution authority. It
                # remains useful after Host revocation and never calls a wire.
                job = self._job(nid, scope, actor, sample, lambda: None)
                sample.update(job=job, status=job['status'])
            except FileNotFoundError: job_missing = True
            except ValueError: pass
            reservation_id = digest([actor, 'video-' + digest([rid, sample['index']])])
            with self._transaction(nid, scope, actor, rid, lambda: None) as (document, live):
                entry = document['collections'].get(self.broker.LEDGER, {}).get(reservation_id)
                if entry and (entry.get('job_id') != sample['job_id'] or entry.get('authorization_digest') != digest([sample['binding'], sample['request_digest']])):
                    raise StaleSourceError('BENCHMARK_VIDEO_RESERVATION_CHANGED')
                if entry: sample['reservation_id'] = entry['id']
                if (job_missing and entry is None and sample.get('reservation_id') is None
                        and live['status'] == 'RUNNING' and live['video_sample']['binding'] == sample['binding']):
                    # A proven pre-admission denial made neither a reservation
                    # nor a job. Keep the explicit preview retryable; this does
                    # not free a hold or retry any original send.
                    sample['status'] = 'PREVIEWED'
                    for key in ('started_at', 'deadline_at'): sample.pop(key, None)
                    def unclaimed(r):
                        r.update(status='READY', video_sample=copy.deepcopy(sample))
                        r['video_samples'].pop(str(sample['index']), None)
                    change_row(live, actor, live['version'], unclaimed)
            self._save_sample(nid, scope, actor, rid, sample, lambda: None)
            # A cancel can win while admission is writing its original receipt.
            latest = self._read(nid, scope, actor, rid, lambda: None, current=False)
            if latest['status'] == 'CANCELLED':
                self._cancel_owner(nid, scope, actor, sample, guard)
            raise

    def refresh(self, nid, scope, actor, rid, version, guard):
        return self._continue(nid, scope, actor, rid, version, guard, reconcile=False)

    def reconcile(self, nid, scope, actor, rid, version, guard):
        return self._continue(nid, scope, actor, rid, version, guard, reconcile=True)

    def _continue(self, nid, scope, actor, rid, version, guard, *, reconcile):
        row = self._read(nid, scope, actor, rid, guard); check_version(row, version)
        if row['status'] != 'RUNNING': raise ValueError('BENCHMARK_RUN_NOT_RUNNING')
        sample = copy.deepcopy(row['video_sample'])
        job = self._job(nid, scope, actor, sample, guard)
        if (datetime.now(timezone.utc) >= datetime.fromisoformat(sample['deadline_at'])
                and job['status'] not in {'AWAITING_REVIEW', 'FAILED', 'CANCELLED'}):
            return self.cancel(nid, scope, actor, rid, version, guard)
        started = time.perf_counter()
        if reconcile and job['status'] in {'RUNNING', 'SEND_RESERVED', 'UNKNOWN', 'RESULT_READY', 'REVIEWING'}:
            job = self.production.reconcile(nid, scope, actor, 'video', job['id'], self._action(job), guard, benchmark_binding=sample['binding'])
        elif not reconcile and job['status'] in {'REMOTE_RUNNING', 'RESULT_READY', 'UNKNOWN'}:
            job = self.production.refresh_video(nid, scope, actor, job['id'], self._action(job), guard, benchmark_binding=sample['binding'])
        sample['observation_action_ms'] = round((time.perf_counter() - started) * 1000, 3)
        return self._observe(nid, scope, actor, rid, sample, job, guard)

    def _observe(self, nid, scope, actor, rid, sample, job, guard):
        sample.update(job=job, status=job['status'])
        if job['status'] not in {'AWAITING_REVIEW', 'FAILED'}:
            return self._save_sample(nid, scope, actor, rid, sample, guard)
        if job['status'] == 'AWAITING_REVIEW':
            self.production.candidate(nid, scope, actor, 'video', job['id'], guard, benchmark_binding=sample['binding'])
        if sample.get('reservation_id'):
            self.broker.finalize(nid, scope, actor, sample['reservation_id'], job['id'],
                'COMPLETED' if job['status'] == 'AWAITING_REVIEW' else 'FAILED')
        with self._transaction(nid, scope, actor, rid, guard) as (document, row):
            if row['status'] != 'RUNNING': return copy.deepcopy(row)
            captured = row['video_samples'].get(str(sample['index']))
            if not captured or captured['binding'] != sample['binding']: raise StaleSourceError('BENCHMARK_VIDEO_SAMPLE_CHANGED')
            if any(r['index'] == sample['index'] for r in row['results']): return copy.deepcopy(row)
            test_set = document['collections'][self.bench.SETS][row['set_id']]
            if test_set['version'] != row['set_version']: raise StaleSourceError('BENCHMARK_SET_CHANGED')
            elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(sample['started_at'])).total_seconds() * 1000
            elapsed = round(elapsed, 3) if 0 <= elapsed <= 3600000 else None
            passed = job['status'] == 'AWAITING_REVIEW'
            result = {'index': sample['index'], 'case_title': test_set['cases'][sample['index'] % len(test_set['cases'])]['title'],
                'rule': 'NONEMPTY', 'passed': passed, 'output': '', 'input_hash': sample['request_digest'],
                'error_code': None if passed else job.get('error_code') or 'ORIGINAL_VIDEO_FAILED',
                'latency_ms': None, 'observed_task_latency_ms': elapsed, 'warmth': 'NOT_MEASURED',
                'measurement_scope': 'OBSERVED_TASK_INCLUDING_ADMISSION_POLLING_AND_VALIDATION',
                'reservation_id': sample.get('reservation_id'),
                'media_receipt': {'owner': 'video', 'task_id': job['id'], 'request_digest': job['request_digest'],
                    'status': job['status'], 'output_candidate': copy.deepcopy(job['output_candidate']),
                    'measurement': copy.deepcopy(job.get('media_measurement'))}}
            sample['status'] = 'COMPLETED' if passed else 'FAILED'
            results = row['results'] + [result]
            state = 'FAILED' if not passed else 'COMPLETED' if len(results) == row['total'] else 'READY'
            def update(r):
                r.update(results=results, completed=len(results), status=state, video_sample=copy.deepcopy(sample))
                r['video_samples'][str(sample['index'])] = copy.deepcopy(sample)
            change_row(row, actor, row['version'], update)
            if state in {'FAILED', 'COMPLETED'}:
                eid = digest([CONTRACT, rid, 'evidence'])
                evidence = new_row(nid, scope, actor, {'status': 'RECORDED', 'origin': 'EXECUTED',
                    'run_id': rid, 'set_id': row['set_id'], 'set_version': row['set_version'], 'set_hash': row['set_hash'],
                    'studio_incarnation': row['studio_incarnation'], 'route_id': row['route_id'],
                    'route_fingerprint': row['route_fingerprint'], 'route_identity': row['route_identity'],
                    'input_hash': digest([r['input_hash'] for r in results]), 'workflow_hash': row['route_identity']['workflow_hash'],
                    'parameters': copy.deepcopy(PRESET), 'capability': 'VIDEO', 'routing_eligible': False,
                    'metrics': {'sample_count': len(results), 'error_count': sum(bool(r['error_code']) for r in results),
                        'error_rate': sum(bool(r['error_code']) for r in results) / len(results), 'latency_ms': None,
                        'observed_task_latency_ms': sum(r['observed_task_latency_ms'] for r in results) / len(results)
                            if all(r['observed_task_latency_ms'] is not None for r in results) else None,
                        'rule_pass_count': sum(r['passed'] for r in results),
                        'measurement_scope': 'OBSERVED_TASK_INCLUDING_ADMISSION_POLLING_AND_VALIDATION'},
                    'verification': 'LOCAL_ADAPTER_EXECUTED', 'quality_score': None, 'tokens_per_second': None,
                    'gpu_memory_bytes': None, 'inference_latency_ms': None, 'generation_fps': None,
                    'cold_start_state': 'NOT_MEASURED', 'cost_state': 'SEE_BROKER_LEDGER',
                    'output_policy': 'PRIVATE_CANDIDATE_THEN_EXPLICIT_ORIGINAL_REVIEW'})
                evidence['id'] = eid
                document['collections'].setdefault(self.bench.EVIDENCE, {}).setdefault(eid, evidence)
                row['evidence_id'] = eid
            return copy.deepcopy(row)

    def _cancel_owner(self, nid, scope, actor, sample, guard):
        if not sample: return
        try: job = self._job(nid, scope, actor, sample, guard)
        except FileNotFoundError: job = None
        if job and job['status'] in {'QUEUED', 'RUNNING', 'SEND_RESERVED', 'REMOTE_RUNNING', 'RESULT_READY', 'UNKNOWN', 'AWAITING_REVIEW'}:
            job = self.production.cancel(nid, scope, actor, 'video', job['id'], self._action(job), guard, benchmark_binding=sample['binding'])
        if sample.get('reservation_id'):
            entry = self.broker.get(nid, scope, self.broker.LEDGER, sample['reservation_id'])
            # Local discard does not stop Comfy compute. Preserve inflight even
            # with a zero estimate until explicit original-stop reconciliation.
            if not entry['dispatched']:
                self.broker.finalize(nid, scope, actor, entry['id'], sample['job_id'], 'CANCELLED')
        return job

    def cancel(self, nid, scope, actor, rid, version, guard):
        row = self._read(nid, scope, actor, rid, guard, current=False); check_version(row, version)
        if row['status'] not in {'READY', 'RUNNING'}: raise ValueError('BENCHMARK_RUN_TERMINAL')
        with self._transaction(nid, scope, actor, rid, guard, version=version) as (_, live):
            change_row(live, actor, version, lambda r: r.update(status='CANCELLED'))
            result = copy.deepcopy(live)
        job = self._cancel_owner(nid, scope, actor, row.get('video_sample'), guard)
        if job:
            with self._transaction(nid, scope, actor, rid, guard) as (_, live):
                if live['status'] == 'CANCELLED':
                    sample = copy.deepcopy(live['video_sample']); sample.update(job=job, status='CANCELLED')
                    def observed(r):
                        r['video_sample'] = copy.deepcopy(sample)
                        r['video_samples'][str(sample['index'])] = copy.deepcopy(sample)
                    change_row(live, actor, live['version'], observed)
                    result = copy.deepcopy(live)
        return result
