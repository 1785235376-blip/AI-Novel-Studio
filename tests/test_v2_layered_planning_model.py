"""Layered PLOT bridge through production routers and original Job/Broker owners.

Both API prefixes and the existing File/opt-in PostgreSQL fixtures run the same
contracts. Only the shipped synthetic route (or a bounded fake stream) is used;
these checks make no claim about real-model execution or literary quality.
"""
import copy
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from app.experimental.planning import digest
from app.experimental.planning_model import MARKER, MAX_OUTPUT_BYTES, output_schema
from app.experimental.ux import ReadContext
from test_r3_mounted_contracts import mounted, prefix, checked, scoped
from test_r4_broker_mounted import broker_app, route, wait_ledger


@pytest.fixture(autouse=True)
def synthetic_protocol_transport(monkeypatch):
    """Remove only the mock's cosmetic delay; production adapters are untouched."""
    from app.runtime import runtime
    monkeypatch.setattr(runtime.providers['mock'], 'delay_ms', 0)


def target(e):
    graph = checked(e.client.post(e.base + '/planning/graphs', headers=e.headers,
                                 json={'title': 'Layered source plan'}), 201)
    volume = checked(e.client.post(e.base + '/planning/nodes', headers=e.headers, json={
        'graph_id': graph['id'], 'parent_id': graph['root_node_id'], 'level': 'VOLUME',
        'title': 'The city volume', 'fields': {'goal': 'Preserve the parent intention'}}), 201)
    node = checked(e.client.post(e.base + '/planning/nodes', headers=e.headers, json={
        'graph_id': graph['id'], 'parent_id': volume['id'], 'level': 'CHAPTER',
        'title': 'The city gate', 'fields': {'goal': 'Enter the city',
            'character_objectives': {'alice': 'Enter'}, 'beats': {'author_beat': 'Keep this beat'}},
        'links': {'chapter_ids': [e.chapter['id']], 'character_ids': ['alice'],
                  'location_ids': ['city'], 'story_route_ids': ['main-route']}}), 201)
    return graph, volume, node


def request(e, node, **extra):
    return checked(e.client.post(e.base + '/planning/model/requests', headers=e.headers, json={
        'node_id': node['id'], 'expected_node_version': node['version'],
        'instruction': 'Propose two source-bound alternatives; retain human choice.', **extra}), 201)


def act(e, row, name, **extra):
    return checked(e.client.post(e.base + f'/planning/model/requests/{row["id"]}/{name}',
        headers=e.headers, json={'expected_version': row['version'], **extra}))


def ready(e, node=None):
    node = node or target(e)[2]
    return act(e, request(e, node), 'preview', route_id=route(e)['route_id'])


def dispatch(e, row):
    return act(e, row, 'dispatch', reviewed_preview_digest=row['model_preview']['preview_digest'])


def settle(e, row):
    wait_ledger(e, row['model_execution']['reservation_id'])
    return act(e, row, 'refresh')


def save(e, row, candidate=None, **extra):
    candidate = candidate or row['model_candidates'][0]
    return act(e, row, f'candidates/{candidate["id"]}/save',
               reviewed_candidates_digest=row['candidates_digest'], **extra)


def proposals(e):
    return checked(e.client.get(e.base + '/planning/proposals', headers=e.headers))['items']


def review(e, row, action):
    return checked(e.client.post(e.base + f'/planning/proposals/{row["id"]}/{action}',
        headers=e.headers, json={'expected_version': row['version']}))


def original_state(e):
    return copy.deepcopy((e.chapters.get(e.chapter['id']),
        {key: e.novels.data_set(e.nid, key) for key in ('characters', 'locations', 'canon', 'story_routes')}))


def test_exact_preview_synthetic_original_job_explicit_save_and_navigation(broker_app, monkeypatch):
    from app.author_request import request_payload
    from app.runtime import runtime
    e = broker_app; before = original_state(e); captured = []
    graph, volume, node = target(e)
    other = checked(e.client.post(e.prefix + f'/novels/{e.nid}/chapters', json={
        'title': 'Unselected', 'content': 'UNSELECTED_LAYERED_PRIVATE_SOURCE'}), 201)
    adapter = runtime.provider_registry.resolve('mock'); original = adapter.stream_text
    def stream(value):
        captured.append(request_payload(value))
        yield from original(value)
    monkeypatch.setattr(adapter, 'stream_text', stream)
    response = e.client.get(e.base + '/planning/model/catalog', headers=e.headers)
    catalog = checked(response)
    assert response.headers['cache-control'] == 'no-store'
    assert catalog['profile'] == 'LOCAL_ONLY' and catalog['max_cost_microusd'] == 0
    assert catalog['automatic_retry'] is False and catalog['model_called'] is False
    assert any(item['provider_id'] == 'mock' and item['synthetic'] for item in catalog['routes'])
    row = ready(e, node); preview = row['model_preview']
    assert not captured and not e.manager.jobs and not e.broker.ledger(e.nid, e.scope, 'local-author')
    assert row['status'] == 'MODEL_REQUEST' and proposals(e) == []
    assert checked(e.client.get(e.base + '/review-inbox', headers=e.headers))['items'] == []
    assert preview['request']['context'] == {} and preview['model_called'] is False
    assert preview['quality_verification'] == 'SYNTHETIC_PROTOCOL_ONLY'
    assert preview['actor'] == 'local-author' and preview['scope'] == e.scope
    assert preview['source_strategy'] == 'SAVED_LAYERED_NODE_AND_LINKED_CHAPTERS'
    assert preview['truncation'] == 'EACH_CHAPTER_FIRST_16000'
    author = preview['author']
    assert author['profile'] == 'LOCAL_ONLY' and author['request_scope']['source_mode'] == 'NONE'
    assert not any(author['request_scope'][key] for key in (
        'include_automatic_context', 'include_style_reference', 'include_plan_reference'))
    prompt = json.loads(author['instruction'].removeprefix(MARKER))
    assert prompt['contract'] == 'LAYERED_PLANNING_PLOT_V1'
    assert prompt['node'] == {key: node[key] for key in ('id', 'version', 'level', 'title', 'fields', 'links')}
    assert [item['id'] for item in prompt['ancestors']] == [graph['root_node_id'], volume['id']]
    assert prompt['chapters'] == [{'chapter_id': e.chapter['id'],
        'chapter_version': e.chapter['version'], 'content': e.chapter['content']}]
    assert prompt['output_schema'] == output_schema(2)
    source_range = preview['source_ranges'][e.chapter['id']]
    assert source_range == {**preview['sources'][e.chapter['id']], 'start': 0,
        'end': len(e.chapter['content']), 'excerpt_digest': digest(e.chapter['content'])}
    assert other['id'] not in preview['sources']
    assert 'UNSELECTED_LAYERED_PRIVATE_SOURCE' not in json.dumps(preview)
    assert preview['preview_digest'] == digest({key: value for key, value in preview.items() if key != 'preview_digest'})
    running = dispatch(e, row); completed = settle(e, running)
    assert captured == [preview['request']] and len(e.manager.jobs) == 1
    execution = completed['model_execution']
    assert execution['status'] == 'COMPLETED' and execution['receipt_state'] == 'RECORDED'
    assert execution['accounting']['status'] == 'SETTLED' and execution['accounting']['actual_microusd'] == 0
    assert execution['applied'] is False and completed['saved_proposals'] == {}
    job = e.manager.get(execution['job_id'])
    assert job.experimental_origin == 'layered_planning_model' and job.dispatch_hooks_required
    assert job.generation_max_output_bytes == MAX_OUTPUT_BYTES and job.generation_deadline
    candidates = completed['model_candidates']
    assert len(candidates) == 2 and completed['candidates_digest'] == digest(candidates)
    for candidate in candidates:
        assert candidate['analysis_source'] == 'SYNTHETIC_PROTOCOL_ONLY'
        assert candidate['fields']['character_objectives'] == node['fields']['character_objectives']
        assert candidate['fields']['beats']['author_beat'] == 'Keep this beat'
        proof = candidate['evidence'][0]
        assert e.chapter['content'][proof['start']:proof['end']] == proof['quote']
        assert proof['chapter_version'] == e.chapter['version'] and len(proof['content_sha256']) == 64
    assert proposals(e) == [] and original_state(e) == before
    replay = dispatch(e, row)
    assert replay['model_execution']['job_id'] == job.id and len(e.manager.jobs) == 1
    denied = e.client.post(e.prefix + f'/generation/{job.id}/accept', headers=e.headers, json={})
    assert denied.status_code == 409 and denied.json()['detail']['code'] == 'LAYERED_PLANNING_REVIEW_ONLY'
    tasks = checked(e.client.get(e.base + '/workspace/tasks', headers=e.headers))['items']
    task = next(item for item in tasks if item['authority'] == 'author_generation' and item['id'] == job.id)
    assert task['feature'] == 'advanced_planning_v2'
    assert task['owner_navigation'] == {'kind': 'feature', 'id': job.id, 'feature': 'advanced_planning_v2',
        'task_authority': 'planning_model_job', 'chapter_id': e.chapter['id'], 'version': e.chapter['version']}
    assert author['instruction'] not in json.dumps(tasks) and job.output not in json.dumps(tasks)
    saved = save(e, completed); saved_again = save(e, completed)
    assert saved['replayed'] is False and saved_again['replayed'] is True
    assert saved_again['proposal_id'] == saved['proposal_id'] and len(proposals(e)) == 1
    proposal = proposals(e)[0]
    assert proposal['id'] == saved['proposal_id'] and proposal['status'] == 'REVIEW'
    assert proposal['execution_mode'] == 'MOCK_ONLY' and proposal['target_version'] == node['version']
    assert proposal['model_provenance']['request_id'] == row['id']
    assert proposal['model_provenance']['job_id'] == job.id
    assert proposal['model_provenance']['evidence'] == candidates[0]['evidence']
    assert proposal['model_provenance']['synthetic'] and proposal['model_provenance']['quality_verification'] == 'NOT_VERIFIED'
    inbox = checked(e.client.get(e.base + '/review-inbox', headers=e.headers))['items']
    assert len(inbox) == 1 and inbox[0]['id'] == proposal['id']
    assert original_state(e) == before


def test_model_request_cannot_enter_original_proposal_review_history_or_restore(broker_app):
    e = broker_app; row = ready(e)
    base = e.base + f'/planning/proposals/{row["id"]}'
    for path in ('', '/history'):
        response = e.client.get(base + path, headers=e.headers)
        assert response.status_code == 422 and 'NOT_A_REVIEW_PROPOSAL' in response.text
        assert 'model_preview' not in response.text and MARKER not in response.text
    for action in ('approve', 'reject', 'reopen', 'archive', 'restore'):
        body = {'expected_version': row['version']}
        if action == 'restore': body['historical_version'] = 1
        response = e.client.post(base + '/' + action, headers=e.headers, json=body)
        assert response.status_code == 422 and 'NOT_A_REVIEW_PROPOSAL' in response.text
    assert proposals(e) == [] and not e.manager.jobs
    assert [item['id'] for item in checked(e.client.get(e.base + '/planning/model/requests', headers=e.headers))['items']] == [row['id']]


def test_saved_candidates_use_original_reject_reopen_history_cas_and_approve(broker_app):
    e = broker_app; before = original_state(e); graph, _, node = target(e)
    completed = settle(e, dispatch(e, ready(e, node)))
    first = save(e, completed)
    second = save(e, first['run'], completed['model_candidates'][1])
    rows = {item['id']: item for item in proposals(e)}
    a, b = rows[first['proposal_id']], rows[second['proposal_id']]
    compared = checked(e.client.post(e.base + '/planning/proposals/compare', headers=e.headers,
        json={'proposal_ids': [a['id'], b['id']]}))
    assert compared['target_node_id'] == node['id'] and 'ending_intent' in compared['differences']
    rejected = review(e, a, 'reject'); assert rejected['status'] == 'REJECTED'
    assert e.client.post(e.base + f'/planning/proposals/{a["id"]}/reopen', headers=e.headers,
        json={'expected_version': a['version']}).status_code == 409
    reopened = review(e, rejected, 'reopen'); assert reopened['status'] == 'REVIEW'
    historical = checked(e.client.get(e.base + f'/planning/proposals/{a["id"]}/history', headers=e.headers))['items']
    assert [item['status'] for item in historical] == ['REVIEW', 'REJECTED']
    restored = checked(e.client.post(e.base + f'/planning/proposals/{a["id"]}/restore', headers=e.headers,
        json={'expected_version': reopened['version'], 'historical_version': 1}))
    assert restored['status'] == 'REVIEW' and restored['restored_from_version'] == 1
    approved = review(e, restored, 'approve')
    assert approved['status'] == 'APPROVED' and approved['applied_node_version'] == node['version'] + 1
    nodes = checked(e.client.get(e.base + f'/planning/graphs/{graph["id"]}', headers=e.headers))['nodes']
    updated = next(item for item in nodes if item['id'] == node['id'])
    assert updated['fields'] == a['fields'] and updated['approved_proposal_id'] == a['id']
    assert e.client.post(e.base + f'/planning/proposals/{b["id"]}/approve', headers=e.headers,
        json={'expected_version': b['version']}).status_code == 409
    assert original_state(e) == before


def test_exact_preview_candidates_and_cas_required_before_writes(broker_app):
    e = broker_app; row = ready(e)
    path = e.base + f'/planning/model/requests/{row["id"]}'
    assert e.client.post(path + '/dispatch', headers=e.headers,
        json={'expected_version': row['version'], 'reviewed_preview_digest': '0' * 64}).status_code == 422
    assert e.client.post(path + '/dispatch', headers=e.headers,
        json={'expected_version': 1, 'reviewed_preview_digest': row['model_preview']['preview_digest']}).status_code == 409
    assert not e.manager.jobs
    completed = settle(e, dispatch(e, row)); cid = completed['model_candidates'][0]['id']
    assert e.client.post(path + f'/candidates/{cid}/save', headers=e.headers,
        json={'expected_version': completed['version'], 'reviewed_candidates_digest': '0' * 64}).status_code == 422
    conflict = e.client.post(path + f'/candidates/{cid}/save', headers=e.headers,
        json={'expected_version': 1, 'reviewed_candidates_digest': completed['candidates_digest']})
    assert conflict.status_code == 409 and 'model_preview' not in conflict.text and MARKER not in conflict.text
    assert proposals(e) == []


@pytest.mark.parametrize('changed', ['node', 'source', 'ancestor'])
@pytest.mark.parametrize('stage', ['preview', 'completed'])
def test_current_node_source_and_ancestor_fences_hide_stale_content(broker_app, changed, stage):
    e = broker_app; graph, ancestor, node = target(e); row = ready(e, node)
    if stage == 'completed': row = settle(e, dispatch(e, row))
    if changed == 'source':
        checked(e.client.put(e.prefix + f'/chapters/{e.chapter["id"]}', json={
            'version': e.chapter['version'], 'content': 'Changed current source without old content.'}))
    else:
        selected = node if changed == 'node' else ancestor
        checked(e.client.put(e.base + f'/planning/nodes/{selected["id"]}', headers=e.headers, json={
            'expected_version': selected['version'], 'title': 'Changed current planning context',
            'fields': selected['fields'], 'links': selected['links']}))
    stale = checked(e.client.get(e.base + f'/planning/model/requests/{row["id"]}', headers=e.headers))
    assert stale['stale'] and stale['model_preview'] is None and stale['model_candidates'] == []
    assert stale['candidates_digest'] is None and e.chapter['content'] not in json.dumps(stale)
    path = e.base + f'/planning/model/requests/{row["id"]}'
    if stage == 'preview':
        response = e.client.post(path + '/dispatch', headers=e.headers, json={
            'expected_version': row['version'], 'reviewed_preview_digest': row['model_preview']['preview_digest']})
        assert not e.manager.jobs
    else:
        response = e.client.post(path + f'/candidates/{row["model_candidates"][0]["id"]}/save', headers=e.headers,
            json={'expected_version': row['version'], 'reviewed_candidates_digest': row['candidates_digest']})
    assert response.status_code == 409 and proposals(e) == []


def bad_output(kind, e):
    if kind == 'json': return '```json\n{"candidates":[]}\n```'
    if kind == 'duplicate': return '{"candidates":[],"candidates":[]}'
    if kind == 'oversize': return 'x' * (MAX_OUTPUT_BYTES + 1)
    record = {'kind': 'PLOT', 'title': 'Invalid candidate', 'description': 'test',
        'acts': ['beginning', 'middle', 'ending'], 'conflict': 'test', 'climax': 'test', 'ending': 'test'}
    candidate = {'record': record, 'evidence': [{'chapter_id': e.chapter['id'],
        'start': 0, 'end': 5, 'quote': e.chapter['content'][:5]}]}
    if kind == 'quote': candidate['evidence'][0]['quote'] = 'wrong'
    if kind == 'references': record['character_ids'] = ['invented-model-character']
    if kind == 'chapter_ids': record['chapter_ids'] = [e.chapter['id']]
    if kind == 'privacy_level': record['privacy_level'] = 'LOCAL_ONLY'
    if kind == 'coercion': candidate['evidence'][0]['start'] = '0'
    if kind == 'unknown': record['permission'] = 'APPROVED'
    return json.dumps({'candidates': [candidate]})


@pytest.mark.parametrize('kind', ['json', 'duplicate', 'quote', 'references', 'chapter_ids', 'privacy_level',
                                 'coercion', 'unknown', 'oversize'])
def test_malformed_or_unproved_output_never_becomes_candidates_or_proposals(broker_app, monkeypatch, kind):
    from app.runtime import runtime
    e = broker_app; before = original_state(e)
    monkeypatch.setattr(runtime.providers['mock'], 'stream', lambda *args, **kwargs: iter([bad_output(kind, e)]))
    result = settle(e, dispatch(e, ready(e)))
    assert result['model_execution']['status'] == 'FAILED'
    assert result['model_execution']['failure_code'] == (
        'GENERATION_OUTPUT_LIMIT' if kind == 'oversize' else 'PLANNING_MODEL_OUTPUT_INVALID_OR_UNSUPPORTED_EVIDENCE')
    assert result['model_candidates'] == [] and result['candidates_digest'] is None and proposals(e) == []
    assert original_state(e) == before


def test_exact_preview_range_receipt_rejects_valid_quote_outside_that_excerpt(broker_app):
    """A real source quote is insufficient when the receipt exposed less text."""
    e = broker_app; row = ready(e)
    owner = e.experimental.planning_service.model_coordinator
    ctx = ReadContext(e.nid, e.scope, 'local-author', 'broker-host', None)
    stored = owner._row(ctx, row['id'], lambda: None)
    output = bad_output('valid', e)
    assert owner._parse_result(ctx, stored, output)[0]['evidence'][0]['quote'] == e.chapter['content'][:5]
    narrower = copy.deepcopy(stored)
    bound = narrower['model_preview']['source_ranges'][e.chapter['id']]
    bound.update(end=2, excerpt_digest=digest(e.chapter['content'][:2]))
    with pytest.raises(ValueError, match='OUTSIDE_EXACT_PREVIEW'):
        owner._parse_result(ctx, narrower, output)
    altered_digest = copy.deepcopy(stored)
    altered_digest['model_preview']['source_ranges'][e.chapter['id']]['excerpt_digest'] = '0' * 64
    with pytest.raises(ValueError, match='OUTSIDE_EXACT_PREVIEW'):
        owner._parse_result(ctx, altered_digest, output)
    assert not e.manager.jobs and proposals(e) == []


def test_disabled_registered_route_and_changed_budget_prevent_dispatch(broker_app):
    from dataclasses import replace
    from app.runtime import runtime
    e = broker_app; row = ready(e)
    path = e.base + f'/planning/model/requests/{row["id"]}/dispatch'
    payload = {'expected_version': row['version'], 'reviewed_preview_digest': row['model_preview']['preview_digest']}
    model = next(item for item in runtime.model_registry.descriptors() if item.provider_id == 'mock')
    runtime.model_registry.register(replace(model, enabled=False), replace=True)
    try:
        assert e.client.post(path, headers=e.headers, json=payload).status_code in {409, 422}
        assert not e.manager.jobs and not e.broker.ledger(e.nid, e.scope, 'local-author')
    finally:
        runtime.model_registry.register(model, replace=True)
    checked(e.client.put(e.base + '/model-broker/budget', headers=e.headers, json={
        'expected_version': 0, 'limit_microusd': 0, 'max_inflight': 1, 'require_known_estimate': True}))
    assert e.client.post(path, headers=e.headers, json=payload).status_code == 409
    assert not e.manager.jobs and not e.broker.ledger(e.nid, e.scope, 'local-author')


def test_parallel_dispatch_and_save_each_create_one_original_record(broker_app):
    e = broker_app; row = ready(e)
    path = e.base + f'/planning/model/requests/{row["id"]}'
    def send(_):
        return e.client.post(path + '/dispatch', headers=e.headers, json={
            'expected_version': row['version'], 'reviewed_preview_digest': row['model_preview']['preview_digest']})
    with ThreadPoolExecutor(max_workers=2) as pool: responses = list(pool.map(send, range(2)))
    assert all(response.status_code in {200, 409} for response in responses)
    running = next(checked(response) for response in responses if response.status_code == 200)
    assert len(e.manager.jobs) == 1 and len(e.broker.ledger(e.nid, e.scope, 'local-author')) == 1
    completed = settle(e, running); cid = completed['model_candidates'][0]['id']
    def persist(_):
        return e.client.post(path + f'/candidates/{cid}/save', headers=e.headers, json={
            'expected_version': completed['version'], 'reviewed_candidates_digest': completed['candidates_digest']})
    with ThreadPoolExecutor(max_workers=2) as pool: results = [checked(response) for response in pool.map(persist, range(2))]
    assert len({result['proposal_id'] for result in results}) == 1 and len(proposals(e)) == 1
    assert sorted(result['replayed'] for result in results) == [False, True]


def test_host_actor_branch_and_membership_permissions_fail_closed(broker_app, monkeypatch):
    e = broker_app; row = ready(e)
    path = e.base + f'/planning/model/requests/{row["id"]}'
    assert e.client.get(e.base + '/planning/model/catalog').status_code == 401
    assert e.client.get(path, headers={'X-Session-Token': 'untrusted-host'}).status_code == 401
    owner = e.experimental.planning_service.model_coordinator
    foreign = ReadContext(e.nid, e.scope, 'different-author', 'broker-host', None)
    with pytest.raises(ValueError, match='ACTOR'):
        owner.get_request(foreign, row['id'], lambda: None)
    assert owner.requests(foreign, lambda: None)['items'] == []
    e = scoped(e, monkeypatch)
    response = e.client.get(e.base + '/planning/model/catalog', headers=e.headers)
    assert response.status_code == 422 and 'LOCAL_CHAPTER_SCOPE_REQUIRED' in response.text
    assert e.client.post(e.base + '/planning/model/requests', headers=e.viewer_headers,
        json={'node_id': row['node_id'], 'expected_node_version': 1}).status_code == 403
    e.authorization.revoke_role(e.role, e.lead)
    assert e.client.get(e.base + '/planning/model/catalog', headers=e.headers).status_code == 403
    assert not e.manager.jobs


@pytest.mark.parametrize('disabled', ['advanced_planning_v2', 'model_broker_v2', 'author_context_inspector_v2', 'v1'])
def test_current_feature_dependencies_disable_catalog_and_dispatch(broker_app, monkeypatch, disabled):
    from app.experimental.flags import FLAGS
    e = broker_app; row = ready(e)
    if disabled == 'v1': monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    else: monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(flag for flag in FLAGS if flag != disabled))
    assert e.client.get(e.base + '/planning/model/catalog', headers=e.headers).status_code == 404
    assert e.client.post(e.base + f'/planning/model/requests/{row["id"]}/dispatch', headers=e.headers, json={
        'expected_version': row['version'], 'reviewed_preview_digest': row['model_preview']['preview_digest']}).status_code == 404
    assert not e.manager.jobs


def test_final_feature_revocation_before_adapter_send_blocks_execution(broker_app, monkeypatch):
    import time
    from app.runtime import runtime
    e = broker_app; row = ready(e); calls = []; original = e.broker.guard_dispatch
    def revoke(*args, **kwargs):
        result = original(*args, **kwargs)
        monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
        return result
    monkeypatch.setattr(e.broker, 'guard_dispatch', revoke)
    monkeypatch.setattr(runtime.providers['mock'], 'stream', lambda *args, **kwargs: (calls.append('unexpected') or iter(['bad'])))
    response = e.client.post(e.base + f'/planning/model/requests/{row["id"]}/dispatch', headers=e.headers, json={
        'expected_version': row['version'], 'reviewed_preview_digest': row['model_preview']['preview_digest']})
    assert response.status_code in {200, 404}
    deadline = time.monotonic() + 5
    while any(job.status not in e.manager.terminal for job in e.manager.jobs.values()) and time.monotonic() < deadline:
        time.sleep(.01)
    assert all(job.status in e.manager.terminal for job in e.manager.jobs.values()) and calls == []


def test_unknown_admission_keeps_reservation_and_never_replays(broker_app, monkeypatch):
    e = broker_app; row = ready(e)
    monkeypatch.setattr(e.manager, 'start_prepared', lambda job: (_ for _ in ()).throw(ValueError('synthetic uncertain admission')))
    response = e.client.post(e.base + f'/planning/model/requests/{row["id"]}/dispatch', headers=e.headers, json={
        'expected_version': row['version'], 'reviewed_preview_digest': row['model_preview']['preview_digest']})
    assert response.status_code == 422
    current = checked(e.client.get(e.base + f'/planning/model/requests/{row["id"]}', headers=e.headers))
    assert current['model_execution']['status'] == 'UNKNOWN'
    replay = dispatch(e, row)
    assert replay['model_execution'] == current['model_execution'] and not e.manager.jobs
    refreshed = act(e, replay, 'refresh')
    assert refreshed['model_execution']['receipt_state'] == 'UNKNOWN_NO_AUTOMATIC_REPLAY'
    assert refreshed['model_execution']['accounting']['status'] == 'RESERVED'
    assert refreshed['model_candidates'] == [] and proposals(e) == []


def test_cancel_discards_late_output_and_restart_preserves_no_replay(broker_app, monkeypatch):
    from app.jobs import JobManager
    from app.runtime import runtime
    e = broker_app; begun = Event(); release = Event()
    def stream(*args, **kwargs):
        begun.set()
        assert release.wait(5)
        yield '{"candidates":[]}'
    monkeypatch.setattr(runtime.providers['mock'], 'stream', stream)
    preview = ready(e); row = dispatch(e, preview)
    try:
        assert begun.wait(5)
        cancelled = act(e, row, 'cancel')
        assert cancelled['model_execution']['status'] == 'CANCELLED'
    finally:
        release.set()
    result = settle(e, cancelled)
    assert result['model_execution']['status'] == 'CANCELLED' and result['model_candidates'] == []
    assert e.manager.get(row['model_execution']['job_id']).output == ''
    restarted = JobManager(generations=e.manager.persistence, chapters=e.chapters,
        contexts=e.manager.contexts, canon=e.canon, snapshot_required=False)
    monkeypatch.setattr(e.experimental.planning_service.model_coordinator, 'manager', restarted)
    replay = dispatch(e, preview)
    assert replay['model_execution']['job_id'] == row['model_execution']['job_id']
    assert replay['model_execution']['status'] == 'CANCELLED' and proposals(e) == []


def test_restart_without_live_authority_cannot_publish_candidates_or_replay(broker_app, monkeypatch):
    from app.jobs import JobManager
    e = broker_app; preview = ready(e); row = dispatch(e, preview)
    wait_ledger(e, row['model_execution']['reservation_id'])
    restarted = JobManager(generations=e.manager.persistence, chapters=e.chapters,
        contexts=e.manager.contexts, canon=e.canon, snapshot_required=False)
    monkeypatch.setattr(e.experimental.planning_service.model_coordinator, 'manager', restarted)
    current = act(e, row, 'refresh')
    assert current['model_execution']['status'] == 'UNKNOWN'
    assert current['model_execution']['receipt_state'] == 'UNKNOWN_NO_AUTOMATIC_REPLAY'
    assert current['model_candidates'] == [] and proposals(e) == []
    again = dispatch(e, preview)
    assert again['model_execution']['job_id'] == row['model_execution']['job_id'] and len(restarted.jobs) == 1


def test_request_requires_saved_nonempty_linked_source_and_current_node(broker_app):
    e = broker_app
    graph = checked(e.client.post(e.base + '/planning/graphs', headers=e.headers, json={'title': 'Unlinked'}), 201)
    path = e.base + '/planning/model/requests'
    response = e.client.post(path, headers=e.headers,
        json={'node_id': graph['root_node_id'], 'expected_node_version': 1})
    assert response.status_code == 422 and 'LINK_ONE_TO_THREE' in response.text
    _, _, node = target(e)
    assert e.client.post(path, headers=e.headers, json={'node_id': node['id'], 'expected_node_version': 99}).status_code == 409
    checked(e.client.put(e.prefix + f'/chapters/{e.chapter["id"]}', json={'version': e.chapter['version'], 'content': ''}))
    response = e.client.post(path, headers=e.headers, json={'node_id': node['id'], 'expected_node_version': 1})
    assert response.status_code == 422 and 'SOURCE_EMPTY' in response.text
    assert checked(e.client.get(path, headers=e.headers))['items'] == [] and not e.manager.jobs
