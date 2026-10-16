"""Original-registry image composition, injected responses only; File and real PG."""
import base64
import copy
import json
import threading
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from app.asset_providers import AssetProviderRegistry, AssetGenerationResult
from app.experimental.media import MediaService, MediaAdapterRegistry, MockImageWorkflowAdapter, MediaWorkflowRequest, production_environment
from app.experimental.model_broker import ModelBrokerService
from app.experimental.model_benchmark import ModelBenchmarkService
from app.experimental.production_lineage import ProductionLineageService
from app.experimental.change_impact import ChangeImpactService
from app.experimental.planning import PlanningService
from app.experimental.story_graph import StoryGraphService
from app.experimental.audiobook import AudiobookV2Service
from app.model_center.discovery_bridge import LocalDiscoveryBridge, LocalImageAdapter
from app.runtime import Runtime
from app.stable_identity import StableIdentityStore
from test_r3_media_support import rig

FLAGS = {'author_context_inspector_v2', 'world_character_engines_v2', 'model_broker_v2', 'model_benchmark_v2', 'media_adapter_registry', 'cover_storyboard_generation',
         'production_manifest_v2', 'change_impact_v2', 'temporal_story_graph_v2', 'asset_lineage_v2'}


@pytest.fixture
def local_media(rig, monkeypatch):
    r = rig
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(FLAGS))
    monkeypatch.delenv('V1_ACCEPTANCE_MODE', raising=False)
    runtime = Runtime(StableIdentityStore(r.root / 'registered-identities.json'))
    originals = AssetProviderRegistry()
    candidate = {'id': 'fixture-image-checkpoint', 'provider_id': 'fixture-local-image', 'model_name': 'fixture.ckpt',
        'display_name': 'Injected original image route', 'runtime_type': 'AUTOMATIC1111',
        'runtime_config': {'endpoint': 'http://127.0.0.1:7860', 'type': 'AUTOMATIC1111'},
        'enabled': True, 'enable_eligible': True, 'enabled_at': 'first-enable', 'verified_capabilities': ['IMAGE'],
        'evidence': {'model_listed': True, 'sha256': 'a' * 64, 'filename': '/private/model.ckpt'},
        'runtime_fingerprint': 'config-one', 'model_evidence_fingerprint': 'weights-one'}
    checks, calls = [], []
    discovery = SimpleNamespace(lock=threading.RLock(), registrations={candidate['id']: copy.deepcopy(candidate)},
        configured_runtime_sources=[], check_model_dispatch=lambda value: checks.append(value['id']))
    bridge = LocalDiscoveryBridge(discovery, runtime, originals)
    bridge(candidate)
    original = originals.get(candidate['provider_id'])
    png = MockImageWorkflowAdapter().generate(MediaWorkflowRequest('fixture', 'cover_generation', 'mock', {}, 1, {}, 'fixture'))[0].content
    class Reply:
        def raise_for_status(self): pass
        def json(self): return {'images': [base64.b64encode(png).decode()]}
    class Transport:
        def post(self, url, **kwargs):
            calls.append({'url': url, **kwargs})
            return Reply()
    original.delegate.transport = Transport()
    registry = MediaAdapterRegistry(original_registry=originals)
    media = MediaService(r.store, r.novels, r.chapters, r.assets, r.screenplays, registry, production_capture_enabled=lambda: True)
    broker = ModelBrokerService(r.store, r.novels, r.chapters, runtime=runtime, media_registry=registry)
    media.broker, media.broker_enabled = broker, lambda: True
    bench = ModelBenchmarkService(r.store, r.novels, r.chapters, broker=broker, media=media)
    production = ProductionLineageService(r.store, r.novels, r.chapters, r.assets, media, broker=broker, broker_enabled=lambda: True)
    impact = ChangeImpactService(r.store, r.novels, r.chapters, StoryGraphService(r.store, r.novels, r.chapters), production,
        PlanningService(r.store, r.novels, r.chapters), AudiobookV2Service(r.store, r.novels, r.chapters, r.assets), enabled=lambda f: f in FLAGS)
    route = next(row for row in broker.candidates() if row.get('adapter_id', '').startswith('registered-image:'))
    return SimpleNamespace(r=r, runtime=runtime, original=original, originals=originals, discovery=discovery, bridge=bridge,
        registry=registry, media=media, broker=broker, bench=bench, production=production, impact=impact,
        route=route, checks=checks, calls=calls, candidate=candidate)


def price(e, amount=0):
    now = datetime.now(timezone.utc)
    return e.broker.configure_price(e.r.nid, e.r.scope, e.r.actor, {'route_id': e.route['route_id'],
        'route_fingerprint': e.route['fingerprint'], 'reserve_microusd': amount, 'source': 'Explicit local test estimate, not invoice',
        'as_of': now.isoformat(), 'expires_at': (now + timedelta(days=1)).isoformat(), 'expected_version': 0})


def benchmark(e):
    r = e.r
    test_set = e.bench.create_set(r.nid, r.scope, r.actor, {'title': 'Single image fixture', 'cases': [
        {'title': 'Image fixture', 'kind': 'IMAGE_WORKFLOW', 'prompt': 'Synthetic blue square'}]})
    return e.bench.start(r.nid, r.scope, r.actor, {'set_id': test_set['id'], 'expected_set_version': 1,
        'route_id': e.route['route_id'], 'request_id': 'one'})


def completed_cover(e):
    r = e.r
    brief = e.media.create_cover(r.nid, r.scope, r.actor, {'title': 'Cover fixture', 'chapter_ids': [r.chapter['id']]})
    task = e.media.queue(r.nid, r.scope, r.actor, {'brief_id': brief['id'], 'expected_brief_version': 1,
        'adapter_id': e.route['adapter_id'], 'candidate_count': 1, 'parameters': {'seed': 19, 'width': 512, 'negative_prompt': 'PRIVATE_NEGATIVE_PROMPT_FIXTURE'}})
    quote = e.media.preflight_registered(r.nid, r.scope, r.actor, task['id'], 1)
    assert quote['ready']
    task = e.media.execute_registered(r.nid, r.scope, r.actor, task['id'], 1,
        quote['broker_decision_id'], quote['broker_decision_version'])
    return task


def reconcile_finished_fixture(e):
    for entry in e.broker.ledger(e.r.nid, e.r.scope, e.r.actor):
        if entry['status'] == 'UNKNOWN_UPSTREAM':
            e.broker.reconcile(e.r.nid, e.r.scope, e.r.actor, entry['id'], {
                'expected_version': entry['version'], 'actual_microusd': 0,
                'evidence_note': 'Injected transport fixture completed; no external provider or invoice.',
                'upstream_terminal_confirmed': True})


def test_catalog_projects_only_original_enabled_adapters_without_probing(local_media):
    e = local_media
    assert not e.calls and not e.checks
    definition = next(d for d in e.registry.definitions()['items'] if d['adapter_id'] == e.route['adapter_id'])
    assert definition['runnable'] and definition['local'] and definition['state'] == 'CONTRACT_VERIFIED'
    env = production_environment(e.registry.resolve(e.route['adapter_id'], 'cover_generation'))
    assert env['model_digest'] == 'a' * 64 and not env['deterministic']
    assert env['registration']['model_digest_source'] == 'RUNTIME_REPORTED_SHA256'
    assert '/private/' not in json.dumps(env)
    e.discovery.registrations[e.candidate['id']]['enabled'] = False
    assert not any(d['adapter_id'] == e.route['adapter_id'] for d in e.registry.definitions()['items'])
    assert not e.calls and not e.checks


def test_one_image_benchmark_persists_original_job_measured_outputs_and_pending_review(local_media):
    e = local_media; r = e.r
    with pytest.raises(ValueError, match='NO_LEGAL_ROUTE'): benchmark(e)
    price(e); run = benchmark(e)
    assert not e.calls
    result = e.bench.step(r.nid, r.scope, r.actor, run['id'], run['version'])
    assert result['status'] == 'COMPLETED' and len(e.calls) == 1 and len(e.checks) == 1
    receipt = result['results'][0]['media_receipt']
    assert receipt['status'] == 'SUCCEEDED'
    assert receipt['outputs'][0]['media']['width'] == 16 and receipt['outputs'][0]['media']['height'] == 16
    assert receipt['outputs'][0]['status'] == 'PENDING_REVIEW'
    task = e.media.get(r.nid, r.scope, e.media.TASKS, receipt['task_id'])
    assert task['benchmark_run_id'] == run['id'] and task['observed_environment']['model_digest'] == 'a' * 64
    evidence = e.bench.evidence(r.nid, r.scope)[0]
    assert evidence['verification'] == 'LOCAL_ADAPTER_EXECUTED' and evidence['quality_score'] is None
    assert evidence['parameters']['seed'] == 0 and evidence['routing_eligible']
    assert e.calls[0]['json']['override_settings'] == {'sd_model_checkpoint': 'fixture.ckpt'}


def test_image_benchmark_identity_change_and_metadata_source_change_stop_dispatch(local_media):
    e = local_media; r = e.r; price(e); run = benchmark(e)
    e.discovery.registrations[e.candidate['id']]['evidence']['sha256'] = 'b' * 64
    with pytest.raises(ValueError, match='ROUTE_CHANGED'): e.bench.step(r.nid, r.scope, r.actor, run['id'], 1)
    assert not e.calls
    e.discovery.registrations[e.candidate['id']]['evidence']['sha256'] = 'a' * 64
    def changed(_):
        e.discovery.registrations[e.candidate['id']]['runtime_fingerprint'] = 'changed-after-probe'
    e.discovery.check_model_dispatch = changed
    result = e.bench.step(r.nid, r.scope, r.actor, run['id'], 1)
    assert result['status'] == 'FAILED' and not e.calls
    assert result['results'][0]['media_receipt']['status'] == 'FAILED'
    assert e.broker.ledger(r.nid, r.scope, r.actor)[0]['dispatched'] is False


def test_local_task_rejects_references_and_multiple_candidates(local_media):
    e = local_media; r = e.r
    brief = e.media.create_cover(r.nid, r.scope, r.actor, {'title': 'Fixture'})
    with pytest.raises(ValueError, match='ONE_IMAGE_PER_TASK'):
        e.media.queue(r.nid, r.scope, r.actor, {'brief_id': brief['id'], 'expected_brief_version': 1,
            'adapter_id': e.route['adapter_id'], 'candidate_count': 2})
    adapter = e.registry.resolve(e.route['adapter_id'], 'cover_generation')
    with pytest.raises(ValueError, match='REFERENCE_CONDITIONING_UNSUPPORTED'):
        adapter.validate_request({'reference_asset_ids': ['reference']}, 1)
    assert not e.calls


def test_registered_refresh_manifest_and_replay_keep_origin_seed_budget_and_review(local_media, monkeypatch):
    e = local_media; r = e.r; price(e); original = completed_cover(e)
    reconcile_finished_fixture(e)
    r.chapters.save(r.chapter['id'], {'content': 'Updated chapter content.'})
    plan = e.impact.preflight(r.nid, r.scope, r.actor, {'source': {'kind': 'CHAPTER', 'id': r.chapter['id']},
        'selected': [{'key': 'MEDIA_TASK:' + original['id'], 'expected_version': original['version']}]})
    assert plan['ready'] and plan['cost']['state'] == 'ESTIMATE' and plan['cost']['estimate_microusd'] == 0
    refreshed = e.impact.prepare(r.nid, r.scope, r.actor, plan['id'], {'expected_version': 1,
        'preflight_digest': plan['preflight_digest'], 'idempotency_key': 'refresh'})['items'][0]
    completed = e.impact.execute(r.nid, r.scope, r.actor, refreshed['id'], 1)
    assert completed['status'] == 'SUCCEEDED' and len(e.calls) == 2
    reconcile_finished_fixture(e)
    manifest = e.production.capture(r.nid, r.scope, r.actor, {'task_id': completed['task_id'], 'expected_task_version': completed['task_version']})
    assert manifest['seed'] == {'state': 'RECORDED', 'value': 19}
    exported = e.production.export(r.nid, r.scope, manifest['id'])
    assert exported['seed']['value'] == 19
    assert 'PRIVATE_NEGATIVE_PROMPT_FIXTURE' not in json.dumps([manifest, exported])
    preflight = e.production.preflight(r.nid, r.scope, r.actor, manifest['id'], 1)
    assert preflight['ready'] and not preflight['states']['deterministic'] and not preflight['states']['rebuildable']
    replay = e.production.replay(r.nid, r.scope, r.actor, manifest['id'], {'expected_version': 1,
        'preflight_digest': preflight['preflight_digest'], 'idempotency_key': 'replay',
        'broker_decision_id': preflight['broker_decision_id'], 'broker_decision_version': preflight['broker_decision_version']})
    completed_replay = e.production.execute_replay(r.nid, r.scope, r.actor, replay['id'], 1)
    assert completed_replay['status'] == 'SUCCEEDED' and len(e.calls) == 3
    assert e.calls[-1]['json']['seed'] == 19
    assert all(o['status'] == 'PENDING_REVIEW' for o in completed_replay['outputs'])
    assert e.media.get(r.nid, r.scope, e.media.TASKS, original['id'])['proposal_ids'] == original['proposal_ids']
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(FLAGS - {'change_impact_v2'}))
    assert e.production.manifests(r.nid, r.scope)['items'] == []
    assert e.production.replays(r.nid, r.scope, r.actor)['items'] == []
    assert all(t['id'] not in {completed['task_id'], replay['task_id']} for t in e.media.tasks(r.nid, r.scope))


def test_unknown_model_hash_remains_unknown_and_cannot_replay(local_media):
    e = local_media; r = e.r
    e.discovery.registrations[e.candidate['id']]['evidence'].pop('sha256')
    e.route = next(row for row in e.broker.candidates() if row.get('adapter_id') == e.route['adapter_id'])
    price(e); task = completed_cover(e)
    manifest = e.production.capture(r.nid, r.scope, r.actor, {'task_id': task['id'], 'expected_task_version': task['version']})
    assert manifest['environment']['model_digest'] is None
    assert 'EXACT_MODEL_IDENTITY_REQUIRED' in e.production.preflight(r.nid, r.scope, r.actor, manifest['id'], 1)['blockers']


def test_current_comfy_checkpoint_projection_keeps_missing_weight_evidence_unknown(local_media):
    e = local_media
    candidate = copy.deepcopy(e.candidate)
    candidate.update(runtime_type='COMFYUI', runtime_config={'endpoint': 'http://127.0.0.1:8188', 'type': 'COMFYUI'},
        evidence={'loader_bindings': [{'node_class': 'CheckpointLoaderSimple', 'input_field': 'ckpt_name'}]})
    e.discovery.registrations[candidate['id']] = candidate
    e.bridge(candidate)
    adapter = e.registry.resolve(e.route['adapter_id'], 'cover_generation')
    assert production_environment(adapter)['model_digest'] is None
    assert not e.calls and not e.checks
    candidate['evidence']['loader_bindings'] = [{'node_class': 'UNETLoader', 'input_field': 'unet_name'}]
    assert not any(d['adapter_id'] == e.route['adapter_id'] for d in e.registry.definitions()['items'])


def test_ordinary_registered_task_requires_current_price_and_source_before_last_mile(local_media):
    e = local_media; r = e.r; price(e)
    brief = e.media.create_cover(r.nid, r.scope, r.actor, {'title': 'Bound cover', 'chapter_ids': [r.chapter['id']]})
    task = e.media.queue(r.nid, r.scope, r.actor, {'brief_id': brief['id'], 'expected_brief_version': 1,
        'adapter_id': e.route['adapter_id'], 'candidate_count': 1})
    quote = e.media.preflight_registered(r.nid, r.scope, r.actor, task['id'], 1)
    e.discovery.check_model_dispatch = lambda _: r.chapters.save(r.chapter['id'], {'content': 'Updated while checking model metadata.'})
    with pytest.raises(ValueError):
        e.media.execute_registered(r.nid, r.scope, r.actor, task['id'], 1, quote['broker_decision_id'], quote['broker_decision_version'])
    assert not e.calls
    entry = e.broker.ledger(r.nid, r.scope, r.actor)[0]
    assert entry['status'] == 'RELEASED' and not entry['dispatched']


def test_registered_benchmark_video_boundary_and_incompatible_text_route_are_explicit(local_media):
    e = local_media; r = e.r
    video = e.bench.create_set(r.nid, r.scope, r.actor, {'title': 'Imported video', 'cases': [
        {'title': 'Video', 'kind': 'VIDEO_WORKFLOW', 'prompt': 'Synthetic fixture'}]})
    with pytest.raises(ValueError, match='VIDEO_LOCAL_ADMISSION_UNAVAILABLE'):
        e.bench.start(r.nid, r.scope, r.actor, {'set_id': video['id'], 'expected_set_version': 1,
            'route_id': e.route['route_id'], 'request_id': 'video'})
    text = e.bench.create_set(r.nid, r.scope, r.actor, {'title': 'Text', 'cases': [
        {'title': 'Text', 'kind': 'SHORT_REVIEW', 'prompt': 'Synthetic fixture'}]})
    with pytest.raises(ValueError, match='CAPABILITY_MISMATCH'):
        e.bench.start(r.nid, r.scope, r.actor, {'set_id': text['id'], 'expected_set_version': 1,
            'route_id': e.route['route_id'], 'request_id': 'text'})
    assert not e.calls


def test_registered_media_cancellation_discards_late_result_and_preserves_unknown_billing(local_media):
    from concurrent.futures import ThreadPoolExecutor
    e = local_media; r = e.r; price(e)
    brief = e.media.create_cover(r.nid, r.scope, r.actor, {'title': 'Cancelled original local fixture'})
    task = e.media.queue(r.nid, r.scope, r.actor, {'brief_id': brief['id'], 'expected_brief_version': 1,
        'adapter_id': e.route['adapter_id'], 'candidate_count': 1})
    quote = e.media.preflight_registered(r.nid, r.scope, r.actor, task['id'], 1)
    entered, release = threading.Event(), threading.Event()
    transport = e.original.delegate.transport
    original_post = transport.post
    def blocked(url, **kwargs):
        entered.set()
        assert release.wait(15)
        return original_post(url, **kwargs)
    transport.post = blocked
    with ThreadPoolExecutor() as pool:
        future = pool.submit(e.media.execute_registered, r.nid, r.scope, r.actor, task['id'], 1,
            quote['broker_decision_id'], quote['broker_decision_version'])
        try:
            assert entered.wait(15)
            running = e.media.get(r.nid, r.scope, e.media.TASKS, task['id'])
            e.media.transition(r.nid, r.scope, r.actor, task['id'], 'cancel', running['version'])
        finally:
            release.set()
        assert future.result(15)['status'] == 'CANCELLED'
    assert e.media.proposals(r.nid, r.scope) == []
    ledger = e.broker.ledger(r.nid, r.scope, r.actor)[0]
    assert ledger['status'] == 'UNKNOWN_UPSTREAM' and ledger['actual_microusd'] is None
    assert len(e.calls) == 1


def test_registered_quote_is_bound_to_exact_queued_task(local_media):
    e = local_media; r = e.r; price(e)
    brief = e.media.create_cover(r.nid, r.scope, r.actor, {'title': 'Two explicit tasks'})
    request = {'brief_id': brief['id'], 'expected_brief_version': 1, 'adapter_id': e.route['adapter_id'], 'candidate_count': 1}
    first = e.media.queue(r.nid, r.scope, r.actor, request)
    second = e.media.queue(r.nid, r.scope, r.actor, request)
    quote = e.media.preflight_registered(r.nid, r.scope, r.actor, first['id'], 1)
    with pytest.raises(ValueError, match='FRESH_TASK_PREFLIGHT_REQUIRED'):
        e.media.execute_registered(r.nid, r.scope, r.actor, second['id'], 1,
            quote['broker_decision_id'], quote['broker_decision_version'])
    assert not e.calls and e.broker.ledger(r.nid, r.scope, r.actor) == []
    assert e.media.get(r.nid, r.scope, e.media.TASKS, second['id'])['status'] == 'QUEUED'
