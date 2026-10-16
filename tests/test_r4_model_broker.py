"""Live registry routing, concurrent accounting and bounded real adapter evidence."""
import copy
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.config import settings
from app.experimental.common import StaleSourceError
from app.experimental.model_broker import ModelBrokerService, digest
from app.experimental.model_broker_api import create_model_broker_router
from app.experimental.model_benchmark import ModelBenchmarkService
from app.experimental.model_benchmark_api import create_model_benchmark_router
from app.experimental.media import MediaAdapterRegistry
from app.model_runtime import LegacyTextProviderAdapter, ProviderDescriptor, ModelDescriptor, Modality
from app.runtime import Runtime
from app.stable_identity import StableIdentityStore
from app.services.v1_capability_service import CapabilityVersionConflict
from test_r3_planning import planning_env


@pytest.fixture
def env(planning_env):
    e = planning_env
    e.runtime = Runtime(StableIdentityStore(e.root / 'identities.json'))
    e.service = ModelBrokerService(e.store, e.novels, e.chapter_service, runtime=e.runtime, media_registry=MediaAdapterRegistry())
    e.bench = ModelBenchmarkService(e.store, e.novels, e.chapter_service, broker=e.service)
    e.service.evidence_reader = e.bench.evidence
    e.route = next(r for r in e.service.candidates() if r['provider_id'] == 'mock')
    return e


def preview(e, **kwargs):
    return e.service.preview(e.nid, e.scope, 'writer', {'chapter_ids': [e.order[0]], 'policy': 'CUSTOM',
        'preferred_route': e.route['route_id'], 'allow_synthetic': True, **kwargs})


def reserve(e, row, key='one', job='job-1'):
    return e.service.reserve(e.nid, e.scope, 'writer', row['id'], row['version'], key, job)


def test_candidates_are_actual_registered_adapters_not_static_families(env):
    e = env
    result = preview(e)
    assert result['chosen']['provider_id'] == 'mock'
    assert result['chosen']['cost_state'] == 'KNOWN_SYNTHETIC_ZERO'
    assert result['execution_authorized'] is False
    assert next(c for c in result['candidates'] if c['provider_id'] == 'ollama')['eligible'] is False
    assert not any(c['model_id'] == 'flux' for c in result['candidates'])
    media = next(c for c in result['candidates'] if c.get('adapter_id') == 'mock-image-v1')
    chosen = preview(e, capability='IMAGE', preferred_route=media['route_id'])
    assert chosen['chosen']['adapter_id'] == 'mock-image-v1'
    assert not preview(e, allow_synthetic=False)['chosen']
    assert not preview(e, context_tokens=9000)['chosen']
    assert 'QUALITY_EVIDENCE_UNAVAILABLE_NO_QUALITY_RANKING' in preview(e, policy='QUALITY')['warnings']


def test_disabled_model_replaced_adapter_and_changed_sources_fence_reservation(env):
    e = env; row = preview(e)
    model = next(m for m in e.runtime.model_registry.descriptors() if m.provider_id == 'mock')
    e.runtime.model_registry.register(replace(model, enabled=False), replace=True)
    with pytest.raises(StaleSourceError): reserve(e, row)
    e.runtime.model_registry.register(model, replace=True)
    row = preview(e)
    descriptor = next(p for p in e.runtime.provider_registry.descriptors() if p.provider_id == 'mock')
    e.runtime.provider_registry.register(descriptor, LegacyTextProviderAdapter('mock', e.runtime.providers['mock']), replace=True)
    with pytest.raises(StaleSourceError): reserve(e, row)
    row = preview(e); e.chapters[e.order[0]]['content'] += 'unsaved-change'
    with pytest.raises(StaleSourceError): reserve(e, row)


def test_atomic_idempotent_reserve_and_concurrency_limit(env):
    e = env; row = preview(e)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: reserve(e, row), range(4)))
    assert len({r['id'] for r in results}) == 1
    assert e.service.budget(e.nid, e.scope)['inflight'] == 1
    with pytest.raises(ValueError, match='IDEMPOTENCY'): reserve(e, row, job='other')
    with pytest.raises(ValueError, match='CONCURRENCY'): reserve(e, row, key='two', job='job-2')
    released = e.service.finalize(e.nid, e.scope, 'writer', results[0]['id'], 'job-1', 'CANCELLED')
    assert released['status'] == 'RELEASED' and released['actual_microusd'] == 0
    assert e.service.finalize(e.nid, e.scope, 'writer', released['id'], 'job-1', 'FAILED') == released
    with pytest.raises(ValueError, match='TERMINAL'): e.service.guard_dispatch(e.nid, e.scope, 'writer', released['id'], 'job-1')


def test_guard_reauthorization_blocks_and_synthetic_settlement_is_exact(env):
    e = env; row = preview(e); entry = reserve(e, row)
    def revoked(): raise ValueError('permission revoked')
    with pytest.raises(ValueError, match='revoked'): e.service.guard_dispatch(e.nid, e.scope, 'writer', entry['id'], 'job-1', revoked)
    first = e.service.guard_dispatch(e.nid, e.scope, 'writer', entry['id'], 'job-1')
    assert first == e.service.guard_dispatch(e.nid, e.scope, 'writer', entry['id'], 'job-1')
    final = e.service.finalize(e.nid, e.scope, 'writer', entry['id'], 'job-1', 'CANCELLED')
    assert final['status'] == 'SETTLED' and final['cost_state'] == 'KNOWN_SYNTHETIC_ZERO'
    assert not e.service.ledger(e.nid, e.scope, 'other')


def test_unknown_cost_not_free_and_dispatched_unknown_retains_hold(env, monkeypatch):
    e = env
    real = {**e.route, 'synthetic': False}
    monkeypatch.setattr(e.service, 'candidates', lambda: [copy.deepcopy(real)])
    assert 'PRICE_ESTIMATE_REQUIRED' in preview(e)['candidates'][0]['reasons']
    stamp = datetime.now(timezone.utc)
    price = {'route_id': real['route_id'], 'route_fingerprint': real['fingerprint'], 'reserve_microusd': 40,
        'source': 'Synthetic billing fixture', 'as_of': stamp.isoformat(), 'expires_at': (stamp + timedelta(days=1)).isoformat(), 'expected_version': 0}
    e.service.configure_price(e.nid, e.scope, 'writer', price)
    e.service.configure_budget(e.nid, e.scope, 'writer', {'expected_version': 0, 'limit_microusd': 50, 'max_inflight': 2})
    row = preview(e); entry = reserve(e, row)
    e.service.guard_dispatch(e.nid, e.scope, 'writer', entry['id'], 'job-1')
    final = e.service.finalize(e.nid, e.scope, 'writer', entry['id'], 'job-1', 'CANCELLED')
    assert final['status'] == 'UNKNOWN_UPSTREAM' and final['actual_microusd'] is None
    assert e.service.budget(e.nid, e.scope)['committed_microusd'] == 40
    assert 'PROJECT_BUDGET_EXCEEDED' in preview(e)['candidates'][0]['reasons']
    with pytest.raises(CapabilityVersionConflict): e.service.configure_budget(e.nid, e.scope, 'writer', {'expected_version': 0})


def test_local_only_never_selects_cloud_even_with_forged_privacy_request(env, monkeypatch):
    e = env
    cloud = {**e.route, 'cloud': True}
    monkeypatch.setattr(e.service, 'candidates', lambda: [cloud])
    assert 'LOCAL_ONLY_POLICY' in preview(e)['candidates'][0]['reasons']
    assert 'CURRENT_SOURCE_PRIVACY_BLOCKS_CLOUD' in preview(e, profile='HYBRID')['candidates'][0]['reasons']
    with pytest.raises(ValueError): preview(e, privacy_level='CLOUD_ALLOWED')


def test_price_changes_and_version_conflicts_do_not_dispatch(env):
    e = env; row = preview(e)
    e.service.configure_budget(e.nid, e.scope, 'writer', {'expected_version': 0, 'limit_microusd': 0})
    with pytest.raises(StaleSourceError, match='BUDGET'): reserve(e, row)
    with pytest.raises(CapabilityVersionConflict): e.service.reserve(e.nid, e.scope, 'writer', row['id'], 99, 'key', 'job')
    with pytest.raises(ValueError, match='ACTOR'): e.service.reserve(e.nid, e.scope, 'other', row['id'], 1, 'key', 'job')


def create_set(e, **kwargs):
    return e.bench.create_set(e.nid, e.scope, 'writer', {'title': 'Synthetic protocol',
        'cases': [{'title': 'Nonempty Chinese', 'kind': 'CHINESE_CONTINUATION', 'prompt': '以中文写一句合成故事。'}], **kwargs})


def start(e, test_set):
    return e.bench.start(e.nid, e.scope, 'writer', {'set_id': test_set['id'], 'expected_set_version': test_set['version'], 'route_id': e.route['route_id'], 'request_id': 'benchmark-one'})


def test_benchmark_runs_actual_adapter_captures_exact_payload_and_invalidates(env, monkeypatch):
    e = env; test_set = create_set(e)
    captured = []
    adapter = e.runtime.provider_registry.resolve('mock')
    original = adapter.generate_text
    def execute(request): captured.append(request); return original(request)
    monkeypatch.setattr(adapter, 'generate_text', execute)
    run = start(e, test_set)
    assert not captured
    finished = e.bench.step(e.nid, e.scope, 'writer', run['id'], run['version'])
    assert finished['status'] == 'COMPLETED'
    assert len(captured) == 1 and captured[0].prompt == '以中文写一句合成故事。'
    assert captured[0].parameters.max_output_tokens == 128
    evidence = e.bench.evidence(e.nid, e.scope)[0]
    assert evidence['origin'] == 'EXECUTED' and evidence['evidence_state'] == 'CURRENT'
    assert evidence['metrics']['latency_ms'] >= 0 and evidence['metrics']['sample_count'] == 1
    assert evidence['tokens_per_second'] is None and evidence['quality_score'] is None
    assert evidence['verification'] == 'SYNTHETIC_PROTOCOL_ONLY'
    assert preview(e)['chosen']['evidence_ids'] == [evidence['id']]
    with pytest.raises((ValueError, CapabilityVersionConflict)): e.bench.step(e.nid, e.scope, 'writer', run['id'], run['version'])
    changed = {k: test_set[k] for k in ('title', 'cases', 'repetitions', 'max_output_tokens', 'timeout_seconds', 'max_cost_microusd')}
    changed['title'] = 'Revised benchmark'
    e.bench.update_set(e.nid, e.scope, 'writer', test_set['id'], 1, changed)
    assert e.bench.evidence(e.nid, e.scope)[0]['evidence_state'] == 'HISTORICAL'
    assert preview(e)['chosen']['evidence_ids'] == []


def test_benchmark_budget_bounds_cancel_and_import_is_not_authority(env):
    e = env; test_set = create_set(e, repetitions=2)
    run = start(e, test_set)
    run = e.bench.cancel(e.nid, e.scope, 'writer', run['id'], run['version'])
    with pytest.raises(ValueError, match='NOT_READY'): e.bench.step(e.nid, e.scope, 'writer', run['id'], run['version'])
    row = e.bench.import_evidence(e.nid, e.scope, 'writer', {'set_id': test_set['id'], 'expected_set_version': 1,
        'route_id': e.route['route_id'], 'route_fingerprint': e.route['fingerprint'], 'input_hash': digest('input'),
        'workflow_hash': digest('workflow'), 'model_id': 'mock-writer', 'runtime_version': 'test', 'adapter_hash': digest('adapter'),
        'latency_ms': 0.1, 'sample_count': 2, 'error_count': 0, 'provenance': 'Offline user-supplied fixture'})
    assert row['origin'] == 'IMPORTED_UNVERIFIED' and not row['routing_eligible']
    assert not preview(e)['chosen']['evidence_ids']
    with pytest.raises(ValueError): create_set(e, repetitions=3, cases=[{'title':str(i), 'kind':'SHORT_REVIEW', 'prompt':'Synthetic'} for i in range(3)])
    e.bench.invalidate(e.nid, e.scope, 'writer', row['id'], 1)
    assert e.bench.evidence(e.nid, e.scope)[0]['evidence_state'] == 'HISTORICAL'


def test_benchmark_late_cancel_does_not_publish_output_or_new_evidence(env, monkeypatch):
    e = env; test_set = create_set(e); run = start(e, test_set)
    adapter = e.runtime.provider_registry.resolve('mock'); original = adapter.generate_text
    def cancelled(request):
        result = original(request)
        current = e.bench.get(e.nid, e.scope, e.bench.RUNS, run['id'])
        e.bench.cancel(e.nid, e.scope, 'writer', run['id'], current['version'])
        return result
    monkeypatch.setattr(adapter, 'generate_text', cancelled)
    result = e.bench.step(e.nid, e.scope, 'writer', run['id'], run['version'])
    assert result['status'] == 'CANCELLED' and result['results'] == []
    assert e.bench.evidence(e.nid, e.scope) == []


def test_router_host_project_feature_gates_and_safe_validation(env):
    e = env; state = {'enabled': True, 'host': True, 'allowed': True}
    def flag(name):
        if not state['enabled']: raise HTTPException(404)
    def host(token):
        if not state['host']: raise HTTPException(401)
    def authorize(nid, token, branch, permission):
        if not state['allowed']: raise HTTPException(403)
        return 'writer', e.scope
    app = FastAPI(); app.include_router(create_model_broker_router(e.service, authorize, flag, host))
    app.include_router(create_model_benchmark_router(e.bench, authorize, flag, host))
    c = TestClient(app); base = f'/novels/{e.nid}/experimental'
    assert c.get(base + '/model-broker/status').status_code == 200
    invalid = c.post(base + '/model-broker/preview', json={'secret': 'SHOULD_NOT_ECHO'})
    assert invalid.status_code == 422 and 'SHOULD_NOT_ECHO' not in invalid.text
    for key, expected in [('enabled', 404), ('host', 401), ('allowed', 403)]:
        state[key] = False
        assert c.get(base + '/model-broker/status').status_code == expected
        assert c.get(base + '/model-benchmarks/status').status_code == expected
        state[key] = True


def test_credential_rotation_changes_opaque_route_fence_without_leaking_secret(env, monkeypatch):
    from app.openai_compatible import CompatibleProviderConfig, OpenAICompatibleTextProvider
    from app.credential_vault import CredentialVault, MemoryBackend
    e = env
    secret_state = MemoryBackend()
    vault = CredentialVault(backend_impl=secret_state)
    monkeypatch.setattr('app.credential_vault.credential_vault', vault)
    object.__setattr__(settings, 'enable_cloud', True)
    adapter = OpenAICompatibleTextProvider(CompatibleProviderConfig('openai', 'https://example.invalid/v1', 'UNSET_BROKER_FIXTURE_KEY'))
    e.runtime.provider_registry.register(ProviderDescriptor('openai', 'Fixture cloud', 'remote', frozenset({Modality.TEXT}), True, True), adapter, replace=True)
    e.runtime.model_registry.register(ModelDescriptor('fixture-model', 'openai', 'Fixture', Modality.TEXT, frozenset({'generate', 'stream'}), streaming=True), replace=True)
    vault.set('openai', 'synthetic-before-credential')
    old = next(r for r in e.service.candidates() if r['provider_id'] == 'openai')
    vault.set('openai', 'synthetic-after-credential')
    current = next(r for r in e.service.candidates() if r['provider_id'] == 'openai')
    assert current['fingerprint'] != old['fingerprint']
    assert 'synthetic-before-credential' not in str(old) and 'synthetic-after-credential' not in str(current)
    vault.clear('openai')
    revoked = next(r for r in e.service.candidates() if r['provider_id'] == 'openai')
    assert not revoked['available'] and 'CREDENTIAL_UNAVAILABLE' in revoked['reasons']


def test_usage_settlement_releases_only_known_difference_and_overrun_fences_admission(env, monkeypatch):
    e = env; real = {**e.route, 'synthetic': False}
    monkeypatch.setattr(e.service, 'candidates', lambda: [copy.deepcopy(real)])
    stamp = datetime.now(timezone.utc)
    e.service.configure_price(e.nid, e.scope, 'writer', {'route_id': real['route_id'], 'route_fingerprint': real['fingerprint'],
        'reserve_microusd': 10, 'input_per_million_microusd': 1000000, 'output_per_million_microusd': 1000000,
        'source': 'Synthetic provider unit fixture', 'as_of': stamp.isoformat(), 'expires_at': (stamp + timedelta(days=1)).isoformat(), 'expected_version': 0})
    row = preview(e); entry = reserve(e, row)
    e.service.guard_dispatch(e.nid, e.scope, 'writer', entry['id'], 'job-1')
    settled = e.service.finalize(e.nid, e.scope, 'writer', entry['id'], 'job-1', 'COMPLETED', {'input_tokens': 2, 'output_tokens': 3})
    assert settled['actual_microusd'] == 5 and e.service.budget(e.nid, e.scope)['committed_microusd'] == 5
    row = preview(e); entry = reserve(e, row, 'next', 'job-2')
    e.service.guard_dispatch(e.nid, e.scope, 'writer', entry['id'], 'job-2')
    settled = e.service.finalize(e.nid, e.scope, 'writer', entry['id'], 'job-2', 'COMPLETED', {'input_tokens': 20, 'output_tokens': 30})
    assert settled['actual_microusd'] == 50 and settled['overrun']
    assert 'UPSTREAM_OVERRUN_REQUIRES_RECONCILIATION' in preview(e)['candidates'][0]['reasons']


def test_blind_small_sample_preference_persists_without_fabricated_quality_score(env):
    e = env; test_set = create_set(e)
    a = start(e, test_set); e.bench.step(e.nid, e.scope, 'writer', a['id'], a['version'])
    b = e.bench.start(e.nid, e.scope, 'writer', {'set_id': test_set['id'], 'expected_set_version': 1, 'route_id': e.route['route_id'], 'request_id': 'second-sample'})
    e.bench.step(e.nid, e.scope, 'writer', b['id'], b['version'])
    evidence = e.bench.evidence(e.nid, e.scope)
    comparison = e.bench.compare_blind(e.nid, e.scope, 'writer', evidence[0]['id'], evidence[1]['id'])
    assert len(comparison['samples']) == 2 and comparison['sample_count'] == 1
    assert 'evidence_ids' not in comparison and 'reveal' not in comparison
    voted = e.bench.vote_blind(e.nid, e.scope, 'writer', comparison['id'], 1, 'TIE')
    assert voted['choice'] == 'TIE' and len(voted['reveal']) == 2
    assert all(r['quality_score'] is None for r in e.bench.evidence(e.nid, e.scope))
    with pytest.raises(CapabilityVersionConflict): e.bench.vote_blind(e.nid, e.scope, 'writer', comparison['id'], 1, 'A')


def test_hardware_hard_constraint_requires_current_real_capacity(env, monkeypatch):
    e = env
    monkeypatch.setattr(e.service, 'hardware_capacity', lambda: {'state': 'UNAVAILABLE', 'ram_mib': None, 'vram_mib': None})
    assert 'HOST_CAPACITY_UNKNOWN_OR_INSUFFICIENT' in preview(e, min_host_vram_mib=100)['candidates'][0]['reasons']
    monkeypatch.setattr(e.service, 'hardware_capacity', lambda: {'state': 'HOST_TOTAL_CAPACITY', 'ram_mib': 1000, 'vram_mib': 500})
    row = preview(e, min_host_vram_mib=100)
    assert row['chosen']
    entry = reserve(e, row)
    monkeypatch.setattr(e.service, 'hardware_capacity', lambda: {'state': 'UNAVAILABLE', 'ram_mib': None, 'vram_mib': None})
    with pytest.raises(StaleSourceError, match='HOST_CAPACITY'): e.service.guard_dispatch(e.nid, e.scope, 'writer', entry['id'], 'job-1')


def test_manual_upstream_reconciliation_requires_terminal_confirmation_and_cas(env, monkeypatch):
    e = env; real = {**e.route, 'synthetic': False}
    monkeypatch.setattr(e.service, 'candidates', lambda: [copy.deepcopy(real)])
    stamp = datetime.now(timezone.utc)
    e.service.configure_price(e.nid, e.scope, 'writer', {'route_id': real['route_id'], 'route_fingerprint': real['fingerprint'], 'reserve_microusd': 40,
        'source': 'Synthetic bill fixture', 'as_of': stamp.isoformat(), 'expires_at': (stamp + timedelta(days=1)).isoformat(), 'expected_version': 0})
    row = preview(e); entry = reserve(e, row)
    data = {'expected_version': entry['version'], 'actual_microusd': 25, 'upstream_terminal_confirmed': True, 'evidence_note': 'Synthetic verified upstream receipt'}
    with pytest.raises(ValueError, match='NOT_ALLOWED'): e.service.reconcile(e.nid, e.scope, 'writer', entry['id'], data)
    e.service.guard_dispatch(e.nid, e.scope, 'writer', entry['id'], 'job-1')
    entry = e.service.finalize(e.nid, e.scope, 'writer', entry['id'], 'job-1', 'UNKNOWN')
    data['expected_version'] = entry['version']
    with pytest.raises(ValueError): e.service.reconcile(e.nid, e.scope, 'writer', entry['id'], {**data, 'upstream_terminal_confirmed': False})
    with pytest.raises(ValueError, match='AUTHORITY'): e.service.reconcile(e.nid, e.scope, 'other', entry['id'], data)
    current = e.service.reconcile(e.nid, e.scope, 'writer', entry['id'], data)
    assert current['status'] == 'RECONCILED' and current['cost_state'] == 'USER_REPORTED_UPSTREAM_BILL'
    assert current['actual_microusd'] == 25 and current['history'][-1]['status'] == 'UNKNOWN_UPSTREAM'
    assert e.service.budget(e.nid, e.scope)['inflight'] == 0
    with pytest.raises(CapabilityVersionConflict): e.service.reconcile(e.nid, e.scope, 'writer', entry['id'], data)


def test_registered_local_adapter_executes_real_loopback_transport_with_exact_limits(env):
    import json
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from app.model_center.discovery_bridge import LocalTextAdapter
    e = env; captured = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            captured.append((self.path, json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
            content = json.dumps({'choices': [{'message': {'content': '合成服务器返回的真实传输测试。'}}]}).encode()
            self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(content))); self.end_headers(); self.wfile.write(content)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        candidate = {'id': 'loopback-model', 'provider_id': 'loopback-test', 'model_name': 'synthetic-fixture',
            'enabled_at': 'fixture-epoch', 'model_evidence_fingerprint': digest('synthetic-server-v1'), 'runtime_fingerprint': digest('fixture-runtime-v1'),
            'source_locality': 'LOCAL_VERIFIED', 'evidence': {'runtime_version': 'fixture-1'},
            'runtime_config': {'type': 'OPENAI_COMPATIBLE', 'management': 'EXTERNAL', 'endpoint': f'http://127.0.0.1:{server.server_port}', 'model_id': 'synthetic-fixture'}}
        bridge = SimpleNamespace(guard=lambda rid: copy.deepcopy(candidate), service=SimpleNamespace(check_model_dispatch=lambda row: None))
        adapter = LocalTextAdapter(bridge, candidate)
        e.runtime.provider_registry.register(ProviderDescriptor('loopback-test', 'Isolated local fixture', 'local', frozenset({Modality.TEXT}), True, True), adapter)
        e.runtime.model_registry.register(ModelDescriptor('loopback-model', 'loopback-test', 'Synthetic loopback', Modality.TEXT, frozenset({'generate', 'stream'}), streaming=True))
        route = next(r for r in e.service.candidates() if r['provider_id'] == 'loopback-test')
        assert route['available'] and not route['synthetic']  # No implicit free-price claim for real adapter.
        stamp = datetime.now(timezone.utc)
        e.service.configure_price(e.nid, e.scope, 'writer', {'route_id': route['route_id'], 'route_fingerprint': route['fingerprint'],
            'reserve_microusd': 0, 'source': 'Explicit synthetic local HTTP fixture fee estimate', 'as_of': stamp.isoformat(), 'expires_at': (stamp + timedelta(days=1)).isoformat(), 'expected_version': 0})
        test_set = create_set(e, max_output_tokens=47)
        run = e.bench.start(e.nid, e.scope, 'writer', {'set_id': test_set['id'], 'expected_set_version': 1, 'route_id': route['route_id'], 'request_id': 'real-local-transport'})
        result = e.bench.step(e.nid, e.scope, 'writer', run['id'], run['version'])
        assert result['status'] == 'COMPLETED'
        assert captured == [('/v1/chat/completions', {'model': 'synthetic-fixture', 'messages': [{'role': 'user', 'content': '以中文写一句合成故事。'}], 'stream': False, 'temperature': 0, 'max_tokens': 47})]
        evidence = e.bench.evidence(e.nid, e.scope)[0]
        assert evidence['verification'] == 'LOCAL_ADAPTER_EXECUTED' and evidence['quality_score'] is None
        candidate['model_evidence_fingerprint'] = digest('synthetic-server-v2')
        assert e.bench.evidence(e.nid, e.scope)[0]['evidence_state'] == 'HISTORICAL'
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=3)


def test_broker_generate_coordinator_contract_duplicate_receipt_starts_original_job_once(env):
    import uuid
    e = env; quote = preview(e); started = []
    def prepare(nid, body, token, branch):
        if body.preview_digest != 'a' * 64: raise HTTPException(409, {'code': 'AUTHOR_PREVIEW_STALE'})
        return SimpleNamespace(id=str(uuid.uuid4()), status='QUEUED', usage=None)
    def start_job(job):
        job.before_dispatch()
        started.append(job.id)
        job.status = 'COMPLETED'
        job.on_terminal()
        return job
    def authorize(nid, token, branch, permission): return 'writer', e.scope
    app = FastAPI(); app.include_router(create_model_broker_router(e.service, authorize, lambda flag: None, lambda token: None,
        prepare_author=prepare, manager=SimpleNamespace(start_prepared=start_job)))
    client = TestClient(app); path = f'/novels/{e.nid}/experimental/model-broker/generate'
    value = {'preview_id': quote['id'], 'expected_version': quote['version'], 'request_id': 'click-one',
        'author': {'novel_id': e.nid, 'chapter_id': e.order[0], 'chapter_version': 1, 'operation': 'continue',
                   'provider_id': 'mock', 'model_id': 'mock-writer', 'profile': 'LOCAL_ONLY', 'preview_digest': 'a' * 64}}
    assert client.post(path, json={**value, 'expected_version': 999}).status_code == 409
    first = client.post(path, json=value)
    assert first.status_code == 202, first.text
    duplicate = client.post(path, json=value)
    assert duplicate.status_code == 202 and duplicate.json()['job_id'] == first.json()['job_id']
    assert started == [first.json()['job_id']]
    assert e.service.ledger(e.nid, e.scope, 'writer')[0]['status'] == 'SETTLED'
    assert client.post(path, json={**value, 'author': {**value['author'], 'instruction': 'changed'}}).status_code == 409
    invalid = {**value, 'request_id': 'click-two', 'author': {**value['author'], 'preview_digest': 'b' * 64}}
    assert client.post(path, json=invalid).status_code == 409
    assert len(e.service.ledger(e.nid, e.scope, 'writer')) == 1


def test_http_benchmark_cancel_remains_responsive_during_adapter_call(env, monkeypatch):
    import asyncio
    import httpx
    e = env; test_set = create_set(e); run = start(e, test_set)
    entered, release = threading.Event(), threading.Event()
    adapter = e.runtime.provider_registry.resolve('mock'); original = adapter.generate_text
    def slow(request):
        entered.set()
        assert release.wait(5)
        return original(request)
    monkeypatch.setattr(adapter, 'generate_text', slow)
    app = FastAPI(); app.include_router(create_model_benchmark_router(e.bench, lambda *args: ('writer', e.scope), lambda *args: None, lambda *args: None))
    base = f'/novels/{e.nid}/experimental/model-benchmarks'
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fixture') as client:
            task = asyncio.create_task(client.post(base + f'/runs/{run["id"]}/step', json={'expected_version': run['version']}))
            try:
                assert await asyncio.to_thread(entered.wait, 3)
                status = await asyncio.wait_for(client.get(base + '/status'), timeout=2)
                current = status.json()['runs'][0]
                assert current['status'] == 'RUNNING'
                cancelled = await asyncio.wait_for(client.post(base + f'/runs/{run["id"]}/cancel', json={'expected_version': current['version']}), timeout=2)
                assert cancelled.status_code == 200 and cancelled.json()['status'] == 'CANCELLED'
            finally:
                release.set()
            result = await task
            assert result.json()['status'] == 'CANCELLED' and result.json()['results'] == []
    asyncio.run(exercise())
    assert not e.bench.evidence(e.nid, e.scope)


def test_orphaned_executor_projection_requires_explicit_confirmed_reconciliation(env):
    e = env; decision = preview(e); entry = reserve(e, decision)
    e.service.guard_dispatch(e.nid, e.scope, 'writer', entry['id'], 'job-1')
    lost = SimpleNamespace(status='FAILED', on_terminal=None, terminal_hook_status=None,
        public=lambda: {'id': 'job-1', 'chapter_id': e.order[0], 'status': 'FAILED', 'output': ''})
    app = FastAPI(); app.include_router(create_model_broker_router(e.service, lambda *args: ('writer', e.scope), lambda *args: None, lambda *args: None,
        manager=SimpleNamespace(get=lambda _: lost)))
    client = TestClient(app); base = f'/novels/{e.nid}/experimental/model-broker'
    state = client.get(base + f'/jobs/{entry["id"]}').json()
    assert state['orphan_reconciliation_available'] and state['recovery']
    assert state['ledger']['status'] == 'DISPATCHED'  # A read never releases a hold.
    body = {'expected_version': state['ledger']['version'], 'actual_microusd': 0, 'upstream_terminal_confirmed': True, 'evidence_note': 'Synthetic checked termination'}
    assert client.post(base + f'/ledger/{entry["id"]}/reconcile', json=body).status_code == 422
    lost.status = 'GENERATING'
    assert client.post(base + f'/ledger/{entry["id"]}/reconcile', json={**body, 'original_executor_stopped_confirmed': True}).status_code == 422
    lost.status = 'FAILED'
    response = client.post(base + f'/ledger/{entry["id"]}/reconcile', json={**body, 'original_executor_stopped_confirmed': True})
    assert response.status_code == 200 and response.json()['reconciled_orphan'] is True
    assert response.json()['cost_state'] == 'USER_REPORTED_UPSTREAM_BILL'
