"""A01 production coordinator, actual author/broker/jobs, labeled captured transport.

File and real PostgreSQL through both mounted prefixes. No paid calls, download,
real-inference quality claim or independent review is performed here.
"""
import copy
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import time

import pytest
from test_r3_mounted_contracts import mounted, prefix, checked, scoped
from test_r4_broker_mounted import broker_app, route, wait_ledger
from test_r4_story_simulator_mounted import start


def candidate(**change):
    return {'id': 'model-a', 'title': 'Synthetic alternate gate', 'motivation_hypothesis': 'Unverified author-facing hypothesis',
        'evidence_ids': [], 'events': [{'id': 'e1', 'title': 'Try without a key', 'at': 1, 'requires': ['key'], 'question': 'Where is the key?'},
                                     {'id': 'e2', 'title': 'Wait for a guide', 'at': 2, 'adds': ['guide-arrived']}], **change}


def action(e, row, name, status=200, **extra):
    return checked(e.client.post(e.base + f'/story-simulator/runs/{row["id"]}/{name}', headers=e.headers,
        json={'expected_version': row['version'], **extra}), status)


def ready(e):
    row, _, _ = start(e)
    row = action(e, row, 'step')
    return action(e, row, 'model/preview', route_id=route(e)['route_id'])


def dispatch(e, row):
    return action(e, row, 'model/dispatch', reviewed_preview_digest=row['model_preview']['preview_digest'])


def settle(e, row):
    wait_ledger(e, row['model_execution']['reservation_id'])
    return action(e, row, 'model/refresh')


def choose(e, row, cid='model-a'):
    return action(e, row, 'model/select', status=201, candidate_id=cid,
        reviewed_preview_digest=row['model_preview']['preview_digest'], reviewed_candidates_digest=row['model_candidates_digest'])


def capture(monkeypatch, value=None):
    from app.runtime import runtime
    calls = []
    output = json.dumps({'routes': [candidate()]}) if value is None else value
    def stream(prompt, model, **kwargs):
        calls.append({'prompt': prompt, 'model': model, 'kwargs': kwargs})
        yield output
    monkeypatch.setattr(runtime.providers['mock'], 'stream', stream)
    return calls


def test_original_production_candidate_flow_exact_character_request_manual_selection_and_review(broker_app, monkeypatch):
    e = broker_app; calls = capture(monkeypatch); before = copy.deepcopy(e.chapters.get(e.chapter['id']))
    row = ready(e); preview = row['model_preview']
    assert not e.manager.jobs and not calls
    assert preview['source_strategy'] == 'A05_CHARACTER_ONLY_NO_MANUSCRIPT'
    assert preview['author']['character_id'] == 'alice' and preview['author']['profile'] == 'LOCAL_ONLY'
    assert 'character_viewpoint' in preview['request']['context']
    assert e.chapter['content'] not in json.dumps(preview['request'])
    assert preview['execution_available'] and preview['broker']['chosen']['synthetic']
    assert preview['broker']['chosen']['price']['reserve_microusd'] == 0
    running = dispatch(e, row); assert len(e.manager.jobs) == 1
    assert dispatch(e, row)['model_execution']['job_id'] == running['model_execution']['job_id']
    result = settle(e, running)
    assert result['model_execution']['status'] == 'CANDIDATES' and result['model_execution']['accounting']['status'] == 'SETTLED'
    assert result['model_candidates'][0]['rules']['violations'][0]['code'] == 'UNMET_PREREQUISITE'
    assert result['model_candidates'][0]['rules']['steps'][1]['applied']
    assert result['model_candidates'][0]['quality_verification'] == 'NOT_RUN'
    assert len(calls) == 1 and calls[0]['prompt'] == preview['request']['prompt']
    job = e.manager.get(running['model_execution']['job_id'])
    assert job.experimental_origin == 'story_simulator_model' and job.character_context_resolver
    assert set(job.required_experimental_features) >= {'story_simulator_v2', 'model_broker_v2', 'character_mind_v2'}
    assert e.client.post(e.prefix + '/generation/' + job.id + '/accept', headers=e.headers, json={}).status_code == 409
    adopted = choose(e, result)
    assert adopted['status'] == 'READY' and adopted['expansions'] == 0 and adopted['id'] != row['id']
    assert choose(e, result)['id'] == adopted['id']
    assert not checked(e.client.get(e.base + '/planning/proposals'))['items']
    adopted = action(e, adopted, 'step'); adopted = action(e, adopted, 'step')
    saved = action(e, adopted, 'save', status=201, route_id='model-a')
    proposal = checked(e.client.get(e.base + '/planning/proposals/' + saved['proposal_id']))
    assert proposal['status'] == 'REVIEW' and proposal['simulation_provenance']['run_id'] == adopted['id']
    assert proposal['execution_mode'] == 'MODEL_CANDIDATE_MANUAL_SELECTION'
    assert proposal['simulation_provenance']['model_adoption']['job_id'] == job.id
    assert e.chapters.get(e.chapter['id']) == before and e.novels.data_set(e.nid, 'canon') == []
    approved = checked(e.client.post(e.base + '/planning/proposals/' + proposal['id'] + '/approve', headers=e.headers, json={'expected_version': proposal['version']}))
    assert approved['status'] == 'APPROVED'
    assert not checked(e.client.get(e.base + '/planning/proposals/' + proposal['id']))['stale']
    assert e.chapters.get(e.chapter['id']) == before


def test_known_zero_model_id_is_configured_without_implicit_send_and_manual_rules_come_first(broker_app):
    e = broker_app; original, _, body = start(e)
    value = checked(e.client.post(e.base + '/story-simulator/runs', headers=e.headers, json={**body, 'model_id': route(e)['model_id']}), 201)
    assert value['status'] == 'READY' and not e.manager.jobs
    response = e.client.post(e.base + f'/story-simulator/runs/{original["id"]}/model/preview', headers=e.headers,
        json={'expected_version': original['version'], 'route_id': route(e)['route_id']})
    assert response.status_code == 422 and 'COMPLETE_MANUAL_RULES_FIRST' in response.text


@pytest.mark.parametrize('output', [
    'not JSON', '{"routes":[],"routes":[]}', json.dumps({'routes': [candidate(tool='execute')]}),
    json.dumps({'routes': [candidate(evidence_ids=['knowledge:unknown-secret'])]}),
    json.dumps({'routes': [candidate(events=[{'id': 'e', 'title': 'bad numeric type', 'at': '1'}])]}),
    json.dumps({'routes': [candidate(events=[{'id': 'e', 'title': 'x' * 241, 'at': 1}])]}),
    json.dumps({'routes': [candidate(), candidate()]}),
    json.dumps({'routes': [candidate(id=str(i)) for i in range(4)]}),
    json.dumps({'routes': [candidate(events=[{'id': str(i), 'title': 'too many', 'at': i} for i in range(9)])]}),
])
def test_model_schema_evidence_and_user_step_branch_bounds_discard_untrusted_results(broker_app, monkeypatch, output):
    e = broker_app; calls = capture(monkeypatch, output)
    result = settle(e, dispatch(e, ready(e)))
    assert len(calls) == 1 and result['model_execution']['status'] == 'DISCARDED'
    assert not result['model_candidates'] and len(e.manager.jobs) == 1
    assert not checked(e.client.get(e.base + '/planning/proposals'))['items']


def test_simulator_checks_inaccessible_knowledge_time_resources_and_hard_rules(broker_app, monkeypatch):
    e = broker_app
    capture(monkeypatch, json.dumps({'routes': [candidate(events=[{'id': 'bad', 'title': 'Hypothesis cannot know', 'at': 1,
        'requires_knowledge': ['unknown'], 'foreshadowing_links': ['hidden-edge'], 'resource_delta': {'coin': -1}}])]}))
    result = settle(e, dispatch(e, ready(e)))
    codes = {v['code'] for v in result['model_candidates'][0]['rules']['violations']}
    assert codes == {'INACCESSIBLE_KNOWLEDGE', 'UNAVAILABLE_FORESHADOWING', 'RESOURCE_CONFLICT'}


def test_hidden_villain_fact_never_enters_preview_or_original_adapter_request(broker_app, monkeypatch):
    from test_r4_story_graph import relation, learn
    e = broker_app; e.novels.upsert_character(e.nid, 'bob', {'name': 'Bob', 'privacy_level': 'LOCAL_ONLY'})
    e.graph = e.experimental.story_graph_service; e.order = [e.chapter['id']] * 4
    marker = 'SYNTHETIC_VILLAIN_ONLY_SECRET_紫钥匙'
    hidden = relation(e, marker); learn(e, hidden, character='bob')
    calls = capture(monkeypatch); row = ready(e)
    assert marker not in json.dumps(row['model_preview']) and hidden['id'] not in json.dumps(row['model_preview'])
    result = settle(e, dispatch(e, row))
    assert result['model_execution']['status'] == 'CANDIDATES'
    assert marker not in json.dumps(calls) and hidden['id'] not in json.dumps(calls)
    learn(e, hidden, character='alice')
    stale = checked(e.client.get(e.base + '/story-simulator/runs/' + result['id']))
    assert stale['stale'] and not stale['routes'] and not stale.get('model_candidates')
    assert e.client.post(e.base + f'/story-simulator/runs/{result["id"]}/model/select', headers=e.headers, json={
        'expected_version': result['version'], 'reviewed_preview_digest': result['model_preview']['preview_digest'],
        'reviewed_candidates_digest': result['model_candidates_digest'], 'candidate_id': 'model-a'}).status_code == 409


def test_model_exact_preview_host_and_feature_gates(broker_app, monkeypatch):
    e = broker_app; row = ready(e); path = e.base + f'/story-simulator/runs/{row["id"]}/model/dispatch'
    payload = {'expected_version': row['version'], 'reviewed_preview_digest': row['model_preview']['preview_digest']}
    assert e.client.post(path, json=payload).status_code == 401
    assert e.client.post(path, headers=e.headers, json={**payload, 'reviewed_preview_digest': '0' * 64}).status_code == 422
    from app.experimental.flags import FLAGS
    for disabled in ('story_simulator_v2', 'model_broker_v2', 'character_mind_v2', 'author_context_inspector_v2'):
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(f for f in FLAGS if f != disabled))
        assert e.client.post(path, headers=e.headers, json=payload).status_code == 404
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(FLAGS)); monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    assert e.client.post(path, headers=e.headers, json=payload).status_code == 404 and not e.manager.jobs


@pytest.mark.parametrize('stage', ['dispatch', 'select', 'saved_review'])
def test_current_source_fence_at_send_selection_and_original_planning_approval(broker_app, monkeypatch, stage):
    e = broker_app; capture(monkeypatch); row = ready(e); original = row
    if stage != 'dispatch': row = settle(e, dispatch(e, row))
    if stage == 'saved_review':
        adopted = choose(e, row); adopted = action(e, adopted, 'step'); adopted = action(e, adopted, 'step')
        saved = action(e, adopted, 'save', status=201, route_id='model-a')
    checked(e.client.put(e.prefix + f'/chapters/{e.chapter["id"]}', json={'version': e.chapter['version'], 'content': 'SYNTHETIC_NEW_SOURCE'}))
    if stage == 'dispatch':
        response = e.client.post(e.base + f'/story-simulator/runs/{row["id"]}/model/dispatch', headers=e.headers, json={'expected_version': row['version'], 'reviewed_preview_digest': original['model_preview']['preview_digest']})
        assert not e.manager.jobs
    elif stage == 'select':
        response = e.client.post(e.base + f'/story-simulator/runs/{row["id"]}/model/select', headers=e.headers, json={'expected_version': row['version'], 'reviewed_preview_digest': original['model_preview']['preview_digest'], 'reviewed_candidates_digest': row['model_candidates_digest'], 'candidate_id': 'model-a'})
    else:
        response = e.client.post(e.base + '/planning/proposals/' + saved['proposal_id'] + '/approve', headers=e.headers, json={'expected_version': 1})
    assert response.status_code == 409


@pytest.mark.parametrize('stage', ['dispatch', 'select'])
def test_budget_change_invalidates_send_and_candidate_adoption(broker_app, monkeypatch, stage):
    e = broker_app; capture(monkeypatch); row = ready(e)
    if stage == 'select': row = settle(e, dispatch(e, row))
    checked(e.client.put(e.base + '/model-broker/budget', headers=e.headers, json={'expected_version': 0, 'limit_microusd': 0, 'max_inflight': 1, 'require_known_estimate': True}))
    response = e.client.post(e.base + f'/story-simulator/runs/{row["id"]}/model/' + stage, headers=e.headers, json={
        'expected_version': row['version'], 'reviewed_preview_digest': row['model_preview']['preview_digest'],
        **({'candidate_id': 'model-a', 'reviewed_candidates_digest': row['model_candidates_digest']} if stage == 'select' else {})})
    assert response.status_code == 409
    if stage == 'dispatch': assert not e.manager.jobs


def test_parallel_admission_only_one_original_job_and_reservation(broker_app, monkeypatch):
    e = broker_app; capture(monkeypatch); row = ready(e)
    path = e.base + f'/story-simulator/runs/{row["id"]}/model/dispatch'
    payload = {'expected_version': row['version'], 'reviewed_preview_digest': row['model_preview']['preview_digest']}
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: e.client.post(path, headers=e.headers, json=payload), range(2)))
    assert all(r.status_code in {200, 409} for r in responses) and any(r.status_code == 200 for r in responses)
    assert len(e.manager.jobs) == 1 and len(e.broker.ledger(e.nid, e.scope, 'local-author')) == 1


def test_unknown_admission_is_durable_no_replay_even_when_result_refreshes(broker_app, monkeypatch):
    e = broker_app; row = ready(e)
    monkeypatch.setattr(e.manager, 'start_prepared', lambda job: (_ for _ in ()).throw(ValueError('SYNTHETIC_LOST_ADMISSION')))
    response = e.client.post(e.base + f'/story-simulator/runs/{row["id"]}/model/dispatch', headers=e.headers, json={
        'expected_version': row['version'], 'reviewed_preview_digest': row['model_preview']['preview_digest']})
    assert response.status_code == 422
    unknown = checked(e.client.get(e.base + '/story-simulator/runs/' + row['id']))
    assert unknown['model_execution']['status'] == 'UNKNOWN'
    assert action(e, unknown, 'model/refresh')['model_execution']['status'] == 'UNKNOWN'
    assert dispatch(e, row)['model_execution']['job_id'] == unknown['model_execution']['job_id'] and not e.manager.jobs
    ledger = e.broker.ledger(e.nid, e.scope, 'local-author'); assert len(ledger) == 1 and ledger[0]['status'] == 'RESERVED'


def test_cancel_inflight_never_appends_late_result_or_replays(broker_app, monkeypatch):
    from app.runtime import runtime
    e = broker_app; started = Event(); release = Event(); calls = []
    def stream(*args, **kwargs):
        calls.append(1); started.set(); assert release.wait(5); yield json.dumps({'routes': [candidate()]})
    monkeypatch.setattr(runtime.providers['mock'], 'stream', stream)
    original = ready(e); running = dispatch(e, original)
    try:
        assert started.wait(5)
        cancelled = action(e, running, 'model/cancel')
        assert cancelled['model_execution']['status'] == 'CANCELLED'
    finally: release.set()
    wait_ledger(e, running['model_execution']['reservation_id'])
    result = action(e, cancelled, 'model/refresh')
    assert not result['model_candidates'] and result['model_execution']['status'] == 'CANCELLED'
    assert dispatch(e, original)['model_execution']['status'] == 'CANCELLED' and len(calls) == 1
    assert e.manager.get(running['model_execution']['job_id']).output == ''


@pytest.mark.parametrize('adopted', [False, True])
def test_restart_cannot_import_previous_output_or_approve_adopted_result(broker_app, monkeypatch, adopted):
    from app.jobs import JobManager
    e = broker_app; capture(monkeypatch); running = dispatch(e, ready(e)); wait_ledger(e, running['model_execution']['reservation_id'])
    if adopted:
        result = action(e, running, 'model/refresh'); selected = choose(e, result)
        selected = action(e, selected, 'step'); selected = action(e, selected, 'step')
        saved = action(e, selected, 'save', status=201, route_id='model-a')
    restarted = JobManager(generations=e.manager.persistence, chapters=e.chapters, contexts=e.manager.contexts, canon=e.canon, snapshot_required=False)
    monkeypatch.setattr(e.experimental.story_simulator_service.model_coordinator, 'manager', restarted)
    if adopted:
        assert checked(e.client.get(e.base + '/story-simulator/runs/' + selected['id']))['stale']
        assert e.client.post(e.base + '/planning/proposals/' + saved['proposal_id'] + '/approve', headers=e.headers, json={'expected_version': 1}).status_code == 409
    else:
        result = action(e, running, 'model/refresh')
        assert result['model_execution']['status'] == 'UNKNOWN' and not result['model_candidates']
        assert result['model_execution']['receipt_state'] == 'UNKNOWN_NO_AUTOMATIC_REPLAY'


def test_output_stream_bound_and_last_hop_flag_revocation_use_original_executor(broker_app, monkeypatch):
    e = broker_app; calls = capture(monkeypatch, 'X' * 64001)
    result = settle(e, dispatch(e, ready(e)))
    job = e.manager.get(result['model_execution']['job_id'])
    assert job.error_code == 'GENERATION_OUTPUT_LIMIT' and job.output == '' and not result['model_candidates']
    assert len(calls) == 1

@pytest.fixture
def captured_local(broker_app, monkeypatch):
    """Real Runtime/registered discovery adapter; captured local HTTP, no model."""
    from app.runtime import Runtime
    from app.stable_identity import StableIdentityStore
    from app.asset_providers import AssetProviderRegistry
    from app.model_center.discovery_bridge import LocalDiscoveryBridge
    from test_local_ai_discovery import service, scan, approve_license
    from test_local_ai_discovery_egress import OllamaWire
    e = broker_app
    runtime = Runtime(StableIdentityStore(e.root / 'simulator-captured-identities.json'))
    discovery = service(e.root / 'simulator-captured-local'); wire = OllamaWire(); discovery.client = wire.client()
    discovery.route_bridge = LocalDiscoveryBridge(discovery, runtime, AssetProviderRegistry())
    candidate_route = scan(discovery)['candidates'][0]
    discovery.validate(candidate_route['id']); discovery.register(candidate_route['id']); approve_license(discovery, candidate_route['id']); discovery.enable(candidate_route['id'])
    adapter = runtime.provider_registry.resolve(candidate_route['provider_id']); adapter.client = wire.client()
    wire.response_text = json.dumps({'routes': [candidate()]}); wire.calls.clear()
    monkeypatch.setattr(e.broker, 'runtime', runtime)
    monkeypatch.setattr('app.jobs.runtime', runtime)
    monkeypatch.setattr('app.experimental.author_context_api.runtime', runtime)
    monkeypatch.setattr(e.api, 'runtime', runtime)
    e.local_route = next(r for r in e.broker.candidates() if r['provider_id'] == candidate_route['provider_id'])
    assert e.local_route['available'], e.local_route
    e.wire, e.discovery, e.candidate_route = wire, discovery, candidate_route
    from datetime import datetime, timedelta, timezone
    stamp = datetime.now(timezone.utc)
    e.zero_price = {'route_id': e.local_route['route_id'], 'route_fingerprint': e.local_route['fingerprint'], 'reserve_microusd': 0,
        'input_per_million_microusd': 0, 'output_per_million_microusd': 0, 'source': 'CAPTURED_LOCAL_TRANSPORT_NO_PROVIDER_FEE',
        'as_of': stamp.isoformat(), 'expires_at': (stamp + timedelta(days=1)).isoformat(), 'expected_version': 0}
    return e


def local_ready(e, configure_price=True):
    if configure_price: checked(e.client.put(e.base + '/model-broker/price', headers=e.headers, json=e.zero_price))
    row, _, _ = start(e); row = action(e, row, 'step')
    return action(e, row, 'model/preview', route_id=e.local_route['route_id'])


def test_configured_local_original_adapter_serialization_requires_known_zero_price(captured_local):
    e = captured_local
    blocked = local_ready(e, configure_price=False)
    assert not blocked['model_preview']['execution_available'] and not e.wire.generations
    row = local_ready(e)
    result = settle(e, dispatch(e, row))
    assert result['model_execution']['status'] == 'CANDIDATES'
    assert result['model_execution']['accounting']['actual_microusd'] == 0
    assert result['model_execution']['quality_verification'] == 'NOT_RUN'
    assert len(e.wire.generations) == 1 and e.wire.generations[0][2]['prompt'] == row['model_preview']['request']['prompt']
    assert e.chapter['content'] not in json.dumps(e.wire.generations)
    selected = choose(e, result); assert selected['status'] == 'READY'


@pytest.mark.parametrize('stage,change', [('dispatch', 'disable'), ('select', 'disable'), ('select', 'price')])
def test_configured_route_revocation_or_real_price_edit_blocks_send_and_adoption(captured_local, stage, change):
    e = captured_local; row = local_ready(e)
    if stage == 'select': row = settle(e, dispatch(e, row))
    if change == 'disable': e.discovery.disable(e.candidate_route['id'])
    else:
        checked(e.client.put(e.base + '/model-broker/price', headers=e.headers,
            json={**e.zero_price, 'source': 'CHANGED_ZERO_FEE_EVIDENCE', 'expected_version': 1}))
    response = e.client.post(e.base + f'/story-simulator/runs/{row["id"]}/model/' + stage, headers=e.headers, json={
        'expected_version': row['version'], 'reviewed_preview_digest': row['model_preview']['preview_digest'],
        **({'candidate_id': 'model-a', 'reviewed_candidates_digest': row['model_candidates_digest']} if stage == 'select' else {})})
    assert response.status_code == 409
    if stage == 'dispatch': assert not e.wire.generations and not e.manager.jobs
    fresh = checked(e.client.get(e.base + '/story-simulator/runs/' + row['id']))
    assert fresh['model_unavailable'] and not fresh['model_preview'] and not fresh['model_candidates']


def test_last_hop_revocation_never_sends_to_original_provider(broker_app, monkeypatch):
    e = broker_app; calls = capture(monkeypatch); original = e.broker.guard_dispatch; row = ready(e)
    def revoked(*args, **kwargs):
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
        return original(*args, **kwargs)
    monkeypatch.setattr(e.broker, 'guard_dispatch', revoked)
    response = e.client.post(e.base + f'/story-simulator/runs/{row["id"]}/model/dispatch', headers=e.headers, json={
        'expected_version': row['version'], 'reviewed_preview_digest': row['model_preview']['preview_digest']})
    assert response.status_code in {200, 404}
    stored = e.store.read(e.nid, e.scope)['collections'][e.experimental.story_simulator_service.RUNS][row['id']]
    job = e.manager.get(stored['model_execution']['job_id'])
    deadline = time.monotonic() + 5
    while (job.status not in e.manager.terminal or job.terminal_hook_status is None) and time.monotonic() < deadline: time.sleep(.01)
    assert job.status == 'FAILED' and not job.output and not calls


def test_stale_model_cancel_conflict_does_not_echo_hidden_request(broker_app, monkeypatch):
    e = broker_app; capture(monkeypatch); result = settle(e, dispatch(e, ready(e)))
    checked(e.client.put(e.prefix + f'/chapters/{e.chapter["id"]}', json={'version': e.chapter['version'], 'content': 'SYNTHETIC_CHANGED'}))
    response = e.client.post(e.base + f'/story-simulator/runs/{result["id"]}/model/cancel', headers=e.headers, json={'expected_version': 900})
    assert response.status_code == 409
    current = response.json()['detail']['current']; assert current['stale'] and 'model_preview' not in current and 'model_candidates' not in current
    cancelled = action(e, result, 'model/cancel'); assert cancelled['stale']


def test_shipped_exact_marker_mock_protocol_is_explicitly_labeled_and_never_a_generic_response(broker_app):
    from app.experimental.story_simulator_model import MARKER, synthetic_simulator_response
    e = broker_app
    assert synthetic_simulator_response('ordinary user instruction') is None
    assert synthetic_simulator_response(MARKER + '{"contract":"unrelated"}') is None
    result = settle(e, dispatch(e, ready(e)))
    assert result['model_execution']['status'] == 'CANDIDATES'
    assert result['model_candidates'][0]['id'] == 'synthetic-local-route'
    assert 'SYNTHETIC_PROTOCOL_ONLY' in result['model_candidates'][0]['rules']['motivation_hypothesis']
    assert result['model_candidates'][0]['quality_verification'] == 'NOT_RUN'


def test_model_endpoints_follow_original_collaboration_membership_and_never_read_base_scope(broker_app, monkeypatch):
    e = broker_app; row = ready(e); e = scoped(e, monkeypatch)
    body = {'expected_version': row['version'], 'route_id': route(e)['route_id']}
    path = e.base + f'/story-simulator/runs/{row["id"]}/model/preview'
    assert e.client.post(path, headers=e.viewer_headers, json=body).status_code == 403
    assert e.client.post(path, headers=e.headers, json=body).status_code == 404
    e.authorization.revoke_role(e.role, e.lead)
    assert e.client.post(path, headers=e.headers, json=body).status_code == 403


def test_lost_live_job_cannot_be_selected_or_exposed_as_replayable(broker_app, monkeypatch):
    e = broker_app; capture(monkeypatch); result = settle(e, dispatch(e, ready(e)))
    e.manager.jobs.clear()
    current = checked(e.client.get(e.base + '/story-simulator/runs/' + result['id']))
    assert current['model_unavailable'] and not current['model_candidates']
    response = e.client.post(e.base + f'/story-simulator/runs/{result["id"]}/model/select', headers=e.headers, json={
        'expected_version': result['version'], 'reviewed_preview_digest': result['model_preview']['preview_digest'],
        'reviewed_candidates_digest': result['model_candidates_digest'], 'candidate_id': 'model-a'})
    assert response.status_code == 409 and not e.manager.jobs
