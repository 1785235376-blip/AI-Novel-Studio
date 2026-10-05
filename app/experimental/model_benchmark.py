"""User-triggered, bounded local test steps through the existing text model node.

Each step runs at most one saved case. There is no background executor, startup
benchmark, paid provider, executable workflow import, or fabricated performance.
"""
from __future__ import annotations
import copy
import json
import threading
import time
from dataclasses import asdict
from typing import Literal
from pydantic import Field, model_validator
from ..author_request import request_payload
from ..model_runtime import TextGenerationRequest, TextGenerationParameters, TextModelNodeInput
from .common import DomainService, StaleSourceError, check_version, change_row, new_row, now
from .model_broker import Strict, digest

FEATURE = 'model_benchmark_v2'
TASK_KINDS = ['CHINESE_CONTINUATION', 'STRUCTURED_EXTRACTION', 'SHORT_REVIEW', 'TOOL_PROTOCOL', 'IMAGE_WORKFLOW', 'VIDEO_WORKFLOW']


class BenchmarkCase(Strict):
    title: str = Field(min_length=1, max_length=120)
    kind: Literal['CHINESE_CONTINUATION', 'STRUCTURED_EXTRACTION', 'SHORT_REVIEW', 'TOOL_PROTOCOL', 'IMAGE_WORKFLOW', 'VIDEO_WORKFLOW']
    prompt: str = Field(min_length=1, max_length=3000)
    rule: Literal['NONEMPTY', 'CONTAINS', 'JSON_KEYS'] = 'NONEMPTY'
    expected: list[str] = Field(default_factory=list, max_length=20)
    @model_validator(mode='after')
    def bounded(self):
        if any(not v or len(v) > 100 for v in self.expected): raise ValueError('BENCHMARK_EXPECTED_TOO_LARGE')
        if self.rule != 'NONEMPTY' and not self.expected: raise ValueError('BENCHMARK_EXPECTED_REQUIRED')
        return self


class BenchmarkSetInput(Strict):
    title: str = Field(min_length=1, max_length=120)
    cases: list[BenchmarkCase] = Field(min_length=1, max_length=6)
    repetitions: int = Field(default=1, ge=1, le=3)
    max_output_tokens: int = Field(default=128, ge=1, le=512)
    timeout_seconds: int = Field(default=30, ge=1, le=120)
    max_cost_microusd: int = Field(default=0, ge=0, le=10**9)
    @model_validator(mode='after')
    def samples(self):
        if len(self.cases) * self.repetitions > 6: raise ValueError('BENCHMARK_MAX_SIX_SAMPLES')
        return self


class BenchmarkRunInput(Strict):
    set_id: str = Field(min_length=1, max_length=160)
    expected_set_version: int = Field(ge=1)
    route_id: str = Field(min_length=1, max_length=160)
    request_id: str = Field(min_length=1, max_length=160)


class EvidenceImportInput(Strict):
    set_id: str = Field(min_length=1, max_length=160)
    expected_set_version: int = Field(ge=1)
    route_id: str = Field(min_length=1, max_length=160)
    route_fingerprint: str = Field(pattern=r'^[0-9a-f]{64}$')
    input_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    workflow_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    model_id: str = Field(min_length=1, max_length=240)
    runtime_version: str = Field(min_length=1, max_length=160)
    adapter_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    quantization: str | None = Field(default=None, max_length=80)
    hardware_hash: str | None = Field(default=None, pattern=r'^[0-9a-f]{64}$')
    latency_ms: float = Field(ge=0, le=3600000, allow_inf_nan=False)
    sample_count: int = Field(ge=1, le=1000)
    error_count: int = Field(ge=0, le=1000)
    provenance: str = Field(min_length=1, max_length=500)
    @model_validator(mode='after')
    def errors(self):
        if self.error_count > self.sample_count: raise ValueError('BENCHMARK_ERROR_COUNT_INVALID')
        return self


class ModelBenchmarkService(DomainService):
    SETS = 'benchmark_sets_v2'
    RUNS = 'benchmark_runs_v2'
    EVIDENCE = 'benchmark_evidence_v2'

    def __init__(self, store, novels, chapters, *, broker):
        super().__init__(store, novels, chapters)
        self.broker = broker

    @staticmethod
    def set_hash(row):
        return digest({k: row[k] for k in ('title', 'cases', 'repetitions', 'max_output_tokens', 'timeout_seconds', 'max_cost_microusd')})

    def create_set(self, nid, scope, actor, value):
        body = BenchmarkSetInput.model_validate(value)
        return self.create(nid, scope, actor, self.SETS, {**body.model_dump(), 'status': 'READY', 'model_called': False})

    def update_set(self, nid, scope, actor, rid, expected_version, value):
        body = BenchmarkSetInput.model_validate(value)
        return self.mutate(nid, scope, actor, self.SETS, rid, expected_version, lambda r: r.update(body.model_dump()))

    def sets(self, nid, scope):
        return self.list(nid, scope, self.SETS)

    def evidence(self, nid, scope):
        routes = {r['route_id']: r for r in self.broker.candidates()}
        sets = {r['id']: r for r in self.sets(nid, scope)}
        rows = self.list(nid, scope, self.EVIDENCE)
        for row in rows:
            route, test_set = routes.get(row['route_id']), sets.get(row['set_id'])
            reasons = []
            if not route or not route['available'] or route['fingerprint'] != row['route_fingerprint']: reasons.append('MODEL_RUNTIME_ADAPTER_OR_AUTHORITY_CHANGED')
            if not test_set or self.set_hash(test_set) != row['set_hash'] or test_set['version'] != row['set_version']: reasons.append('TEST_SET_CHANGED')
            if row['origin'] == 'IMPORTED_UNVERIFIED' and route and any(row.get(key) != route['identity'].get(key) for key in ('model_id', 'runtime_version', 'adapter_hash', 'workflow_hash', 'quantization', 'hardware_hash')): reasons.append('IMPORTED_IDENTITY_NOT_CURRENT')
            if row['status'] == 'INVALIDATED': reasons.append('EXPLICITLY_INVALIDATED')
            row['evidence_state'] = 'HISTORICAL' if reasons else 'CURRENT'
            row['invalidation_reasons'] = reasons
            row['routing_eligible'] = not reasons and row['origin'] == 'EXECUTED'
        return sorted(rows, key=lambda r: r['created_at'], reverse=True)

    def import_evidence(self, nid, scope, actor, value):
        body = EvidenceImportInput.model_validate(value)
        test_set = self.get(nid, scope, self.SETS, body.set_id)
        check_version(test_set, body.expected_set_version)
        row = self.create(nid, scope, actor, self.EVIDENCE, {**body.model_dump(exclude={'expected_set_version', 'latency_ms', 'sample_count', 'error_count'}),
            'set_hash': self.set_hash(test_set), 'set_version': test_set['version'], 'origin': 'IMPORTED_UNVERIFIED', 'status': 'RECORDED',
            'metrics': {'latency_ms': body.latency_ms, 'sample_count': body.sample_count, 'error_count': body.error_count,
                        'error_rate': body.error_count / body.sample_count},
            'verification': 'USER_SUPPLIED_NOT_EXECUTED_HERE', 'quality_score': None, 'tokens_per_second': None, 'gpu_memory_bytes': None,
            'routing_eligible': False, 'cold_start_state': 'NOT_MEASURED', 'cost_state': 'UNKNOWN'})
        return next(r for r in self.evidence(nid, scope) if r['id'] == row['id'])

    def invalidate(self, nid, scope, actor, rid, expected_version):
        return self.mutate(nid, scope, actor, self.EVIDENCE, rid, expected_version, lambda r: r.update(status='INVALIDATED'))

    def start(self, nid, scope, actor, value, guard=lambda: None):
        body = BenchmarkRunInput.model_validate(value)
        test_set = self.get(nid, scope, self.SETS, body.set_id)
        check_version(test_set, body.expected_set_version)
        if any(c['kind'] in {'IMAGE_WORKFLOW', 'VIDEO_WORKFLOW'} for c in test_set['cases']):
            raise ValueError('BENCHMARK_WORKFLOW_EXECUTOR_NOT_INTEGRATED_IMPORT_EVIDENCE_ONLY')
        route = self.broker.current_route(body.route_id)
        if not route['available'] or route['cloud']: raise ValueError('BENCHMARK_LOCAL_REGISTERED_ROUTE_REQUIRED')
        guard()
        preview = self.broker.preview(nid, scope, actor, {'policy': 'CUSTOM', 'preferred_route': body.route_id,
            'profile': 'LOCAL_ONLY', 'allow_synthetic': route['synthetic'], 'max_cost_microusd': test_set['max_cost_microusd']}, guard)
        if not preview['chosen']: raise ValueError('BENCHMARK_NO_LEGAL_ROUTE')
        amount = (preview['chosen']['price'] or {}).get('reserve_microusd')
        total = len(test_set['cases']) * test_set['repetitions']
        if amount is None or amount * total > test_set['max_cost_microusd']: raise ValueError('BENCHMARK_TOTAL_BUDGET_EXCEEDED')
        key = digest([actor, body.request_id])
        with self.store.transaction(nid, scope) as doc:
            guard()
            rows = doc['collections'].setdefault(self.RUNS, {})
            old = rows.get(key)
            input_hash = digest(body.model_dump(exclude={'request_id'}))
            if old:
                if old['input_hash'] != input_hash: raise ValueError('BENCHMARK_IDEMPOTENCY_MISMATCH')
                return copy.deepcopy(old)
            row = new_row(nid, scope, actor, {'status': 'READY', 'input_hash': input_hash,
                'set_id': body.set_id, 'set_version': test_set['version'], 'set_hash': self.set_hash(test_set),
                'route_id': body.route_id, 'route_fingerprint': route['fingerprint'], 'route_identity': route['identity'],
                'preview_id': preview['id'], 'preview_version': preview['version'], 'total': total,
                'completed': 0, 'results': [], 'cold_start_state': 'NOT_MEASURED', 'automatic_replay': False})
            row['id'] = key
            rows[key] = row
            return copy.deepcopy(row)

    def runs(self, nid, scope, actor):
        return sorted((r for r in self.list(nid, scope, self.RUNS) if r['created_by'] == actor), key=lambda r: r['created_at'], reverse=True)[:100]

    def cancel(self, nid, scope, actor, rid, version):
        def transition(row):
            if row['created_by'] != actor: raise ValueError('BENCHMARK_ACTOR_MISMATCH')
            if row['status'] not in {'READY', 'RUNNING'}: raise ValueError('BENCHMARK_RUN_TERMINAL')
            row['status'] = 'CANCELLED'
        return self.mutate(nid, scope, actor, self.RUNS, rid, version, transition)

    def step(self, nid, scope, actor, rid, version, guard=lambda: None):
        row = self.get(nid, scope, self.RUNS, rid)
        check_version(row, version)
        if row['created_by'] != actor: raise ValueError('BENCHMARK_ACTOR_MISMATCH')
        if row['status'] != 'READY' or row['completed'] >= row['total']: raise ValueError('BENCHMARK_RUN_NOT_READY')
        test_set = self.get(nid, scope, self.SETS, row['set_id'])
        if self.set_hash(test_set) != row['set_hash'] or test_set['version'] != row['set_version']: raise StaleSourceError('BENCHMARK_SET_CHANGED')
        route = self.broker.current_route(row['route_id'])
        if not route['available'] or route['cloud'] or route['fingerprint'] != row['route_fingerprint']: raise StaleSourceError('BENCHMARK_ROUTE_CHANGED')
        guard()
        index = row['completed']
        case = test_set['cases'][index % len(test_set['cases'])]
        sample_id = f'{rid}:{index}'
        # Claim the step with CAS before reserving or calling the adapter.
        def claim(current):
            guard()
            if current['status'] != 'READY': raise ValueError('BENCHMARK_RUN_NOT_READY')
            current['status'] = 'RUNNING'
        claimed = self.mutate(nid, scope, actor, self.RUNS, rid, version, claim)
        reservation = None
        cancellation = threading.Event()
        deadline = time.monotonic() + test_set['timeout_seconds']
        def live_guard():
            guard()
            current = self.get(nid, scope, self.RUNS, rid)
            if current['status'] != 'RUNNING' or current['version'] != claimed['version'] or time.monotonic() >= deadline:
                cancellation.set()
                raise StaleSourceError('BENCHMARK_CANCELLED_OR_TIMEOUT')
            latest = self.get(nid, scope, self.SETS, row['set_id'])
            if latest['version'] != row['set_version']: raise StaleSourceError('BENCHMARK_SET_CHANGED')
        start = time.perf_counter()
        response, failure, output, input_hash = None, None, '', None
        timer = threading.Timer(test_set['timeout_seconds'], cancellation.set)
        timer.daemon = True
        try:
            reservation = self.broker.reserve(nid, scope, actor, row['preview_id'], row['preview_version'], sample_id, sample_id, live_guard)
            def dispatch():
                live_guard()
                self.broker.guard_dispatch(nid, scope, actor, reservation['id'], sample_id, live_guard)
            request = TextGenerationRequest(provider_id=route['provider_id'], model_id=route['model_id'], prompt=case['prompt'],
                parameters=TextGenerationParameters(temperature=0, max_output_tokens=test_set['max_output_tokens']),
                metadata={'purpose': 'bounded_benchmark', 'synthetic_input': 'true'}, job_id=sample_id,
                cancellation=cancellation, dispatch_guard=dispatch)
            input_hash = digest(request_payload(request))
            timer.start()
            response = self.broker.runtime.prepare_text_route(route['provider_id'], route['model_id']).execute(TextModelNodeInput(request)).response
            live_guard()
            output = response.text[:20000]
        except Exception:
            failure = 'CANCELLED_OR_TIMEOUT' if cancellation.is_set() else 'ADAPTER_OR_CURRENT_AUTHORITY_FAILED'
        finally:
            timer.cancel()
            if reservation:
                self.broker.finalize(nid, scope, actor, reservation['id'], sample_id, 'FAILED' if failure else 'COMPLETED', asdict(response.usage) if response and response.usage else None)
        elapsed = round((time.perf_counter() - start) * 1000, 3)
        passed = False
        if not failure:
            if case['rule'] == 'NONEMPTY': passed = bool(output.strip())
            elif case['rule'] == 'CONTAINS': passed = all(v in output for v in case['expected'])
            else:
                try:
                    parsed = json.loads(output)
                    passed = isinstance(parsed, dict) and all(v in parsed for v in case['expected'])
                except (ValueError, TypeError): passed = False
        with self.store.transaction(nid, scope) as doc:
            current = doc['collections'][self.RUNS][rid]
            if current['status'] != 'RUNNING' or current['version'] != claimed['version']:
                return copy.deepcopy(current)  # Cancelled work never publishes late output.
            try: live_guard()
            except Exception:
                change_row(current, actor, current['version'], lambda r: r.update(status='FAILED', error_code='BENCHMARK_CURRENT_AUTHORITY_CHANGED'))
                return copy.deepcopy(current)
            result = {'index': index, 'case_title': case['title'], 'rule': case['rule'], 'passed': passed,
                      'output': output, 'error_code': failure, 'latency_ms': elapsed,
                      'input_hash': input_hash,
                      'reservation_id': reservation['id'] if reservation else None, 'warmth': 'NOT_MEASURED'}
            results = current['results'] + [result]
            state = 'FAILED' if failure else 'COMPLETED' if len(results) == current['total'] else 'READY'
            change_row(current, actor, current['version'], lambda r: r.update(status=state, completed=len(results), results=results))
            if state in {'COMPLETED', 'FAILED'} and input_hash is not None:
                count = len(results)
                evidence = new_row(nid, scope, actor, {'status': 'RECORDED', 'origin': 'EXECUTED',
                    'run_id': rid, 'set_id': row['set_id'], 'set_version': row['set_version'], 'set_hash': row['set_hash'],
                    'route_id': route['route_id'], 'route_fingerprint': route['fingerprint'], 'route_identity': route['identity'],
                    'input_hash': digest([r['input_hash'] for r in results]), 'workflow_hash': route['identity']['workflow_hash'],
                    'parameters': {'temperature': 0, 'max_output_tokens': test_set['max_output_tokens']},
                    'metrics': {'sample_count': count, 'error_count': sum(bool(r['error_code']) for r in results),
                                'error_rate': sum(bool(r['error_code']) for r in results) / count,
                                'latency_ms': round(sum(r['latency_ms'] for r in results) / count, 3),
                                'rule_pass_count': sum(r['passed'] for r in results)},
                    'verification': 'SYNTHETIC_PROTOCOL_ONLY' if route['synthetic'] else 'LOCAL_ADAPTER_EXECUTED',
                    'quality_score': None, 'tokens_per_second': None, 'gpu_memory_bytes': None,
                    'cold_start_state': 'NOT_MEASURED', 'literary_quality': 'NOT_EVALUATED_SMALL_SAMPLE',
                    'cost_state': 'SEE_BROKER_LEDGER'})
                doc['collections'].setdefault(self.EVIDENCE, {})[evidence['id']] = evidence
                current['evidence_id'] = evidence['id']
            return copy.deepcopy(current)

    def compare_blind(self, nid, scope, actor, left_id, right_id):
        """Hide route labels until one explicit preference; never derive a rank."""
        import secrets
        if left_id == right_id: raise ValueError('BENCHMARK_DISTINCT_RESULTS_REQUIRED')
        evidence = {r['id']: r for r in self.evidence(nid, scope)}
        selected = [evidence.get(left_id), evidence.get(right_id)]
        if any(not r or r['origin'] != 'EXECUTED' or r['evidence_state'] != 'CURRENT' for r in selected):
            raise ValueError('BENCHMARK_CURRENT_EXECUTED_RESULTS_REQUIRED')
        if selected[0]['set_hash'] != selected[1]['set_hash'] or selected[0]['input_hash'] != selected[1]['input_hash']:
            # Input hashes include provider identity. Compare saved case/parameter
            # hashes instead; each output remains bound to its exact own input.
            if selected[0]['set_hash'] != selected[1]['set_hash'] or selected[0]['parameters'] != selected[1]['parameters']:
                raise ValueError('BENCHMARK_COMPARABLE_INPUTS_REQUIRED')
        runs = [self.get(nid, scope, self.RUNS, r['run_id']) for r in selected]
        if any(r['created_by'] != actor or r['status'] != 'COMPLETED' for r in runs): raise ValueError('BENCHMARK_OWN_COMPLETED_RUNS_REQUIRED')
        if secrets.randbits(1): selected.reverse(); runs.reverse()
        row = self.create(nid, scope, actor, 'benchmark_blind_preferences_v2', {'status': 'REVIEW',
            'evidence_ids': [r['id'] for r in selected], 'evidence_versions': [r['version'] for r in selected],
            'samples': [{'label': label, 'outputs': [r['output'] for r in run['results']]} for label, run in zip(('A', 'B'), runs)],
            'sample_count': min(r['metrics']['sample_count'] for r in selected), 'choice': None,
            'limitation': 'SMALL_SAMPLE_PERSONAL_PREFERENCE_NO_GLOBAL_RANKING'})
        return self._public_comparison(row)

    @staticmethod
    def _public_comparison(row):
        return copy.deepcopy({key: value for key, value in row.items() if key not in {'evidence_ids', 'evidence_versions', 'history'}})

    def vote_blind(self, nid, scope, actor, rid, version, choice):
        if choice not in {'A', 'B', 'TIE', 'NEITHER'}: raise ValueError('BENCHMARK_PREFERENCE_INVALID')
        row = self.get(nid, scope, 'benchmark_blind_preferences_v2', rid)
        if row['created_by'] != actor: raise ValueError('BENCHMARK_ACTOR_MISMATCH')
        current = {r['id']: r for r in self.evidence(nid, scope)}
        selected = [current.get(identifier) for identifier in row['evidence_ids']]
        if any(not r or r['evidence_state'] != 'CURRENT' or r['version'] != expected for r, expected in zip(selected, row['evidence_versions'])):
            raise StaleSourceError('BENCHMARK_EVIDENCE_CHANGED')
        def vote(record):
            if record['status'] != 'REVIEW': raise ValueError('BENCHMARK_PREFERENCE_ALREADY_RECORDED')
            record.update(status='RECORDED', choice=choice, reveal=[{'label': label, 'route_id': r['route_id'],
                'verification': r['verification']} for label, r in zip(('A', 'B'), selected)])
        return self._public_comparison(self.mutate(nid, scope, actor, 'benchmark_blind_preferences_v2', rid, version, vote))

    def comparisons(self, nid, scope, actor):
        rows = [r for r in self.list(nid, scope, 'benchmark_blind_preferences_v2') if r['created_by'] == actor]
        return [self._public_comparison(r) for r in sorted(rows, key=lambda r: r['created_at'], reverse=True)[:100]]
