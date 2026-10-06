"""A01 real deterministic rules, File and actual PostgreSQL persistence contracts."""
from copy import deepcopy
import json
import threading

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.experimental.common import StaleSourceError
from app.experimental.flags import FLAGS
from app.experimental.planning import PlanningService
from app.experimental.story_simulator import StorySimulatorService, transition
from app.experimental.story_simulator_api import create_story_simulator_router
from app.experimental.story_graph import StoryGraphService
from app.experimental.store import ExperimentalStore
from app.services.v1_capability_service import CapabilityVersionConflict
from test_r3_planning import planning_env
from test_r4_story_graph import relation, learn


@pytest.fixture
def env(planning_env, monkeypatch):
    e = planning_env
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join((*FLAGS, 'story_simulator_v2')))
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'false')
    e.graph = StoryGraphService(e.store, e.novels, e.chapter_service)
    e.sim = StorySimulatorService(e.store, e.novels, e.chapter_service, e.service, e.graph)
    e.plan = e.service.create_graph(e.nid, e.scope, 'author', {'title': 'Existing plan', 'links': {'chapter_ids': [e.order[3]]}})
    return e


def event(id='e1', **kwargs):
    return {'id': id, 'title': 'Open the gate', 'at': 1, **kwargs}


def request(e, **kwargs):
    context = e.sim.context(e.nid, e.scope, {'chapter_id': e.order[3], 'expected_version': 1, 'character_id': 'alice', 'world_time': kwargs.get('world_time')})
    return {'chapter_ids': [e.order[3]], 'expected_versions': {e.order[3]: 1}, 'chapter_id': e.order[3], 'character_id': 'alice',
            'context_digest': context['context_digest'], 'node_id': e.plan['root_node_id'], 'expected_node_version': 1,
            'character_goal': 'Reach the city', 'motivation_hypothesis': 'The author suspects loyalty motivates her.',
            'routes': [{'id': 'route-a', 'title': 'A visible route', 'events': [event()]}], **kwargs}


def run(e, **kwargs):
    return e.sim.create_run(e.nid, e.scope, 'author', request(e, **kwargs))


def step(e, row):
    return e.sim.step(e.nid, e.scope, 'author', row['id'], row['version'])


def complete(e, row):
    while row['status'] in {'READY', 'RUNNING'}: row = step(e, row)
    return row


def save(e, row, route='route-a'):
    return e.sim.save(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version'], 'route_id': route})


def test_all_four_rule_classes_and_atomic_failed_state(env):
    e = env
    r = run(e, world_time=4, assumptions=['key'], resources={'coin': 1}, hard_constraints={'forbidden_facts': ['dead']}, routes=[{'id': 'route-a', 'title': 'Invalid route', 'events': [event(at=3, requires=['bridge'], adds=['dead'], resource_delta={'coin': -2}, requires_knowledge=['unknown'])]}])
    result = step(e, r); route = result['routes'][0]
    assert {v['code'] for v in route['violations']} == {'UNMET_PREREQUISITE', 'TEMPORAL_ORDER', 'INACCESSIBLE_KNOWLEDGE', 'RESOURCE_CONFLICT', 'HARD_CONSTRAINT'}
    assert not route['steps'][0]['applied']
    raw = e.sim.get(e.nid, e.scope, e.sim.RUNS, r['id'])
    assert raw['routes'][0]['state'] == {'facts': ['key'], 'resources': {'coin': 1}, 'time': 4}
    assert result['model_called'] is False and result['model_budget'] == 0
    assert not any(k in json.dumps(result) for k in ('probability', 'score', 'success_percent'))


def test_manual_candidate_comparison_reproducibility_and_real_restart(env):
    e = env; before = deepcopy((e.rows, e.chapters))
    body = request(e, assumptions=['key'], resources={'coin': 1}, routes=[{'id': 'route-a', 'title': 'Use the key', 'events': [event(requires=['key'], adds=['inside'])]}, {'id': 'route-b', 'title': 'Pay guard', 'events': [event(resource_delta={'coin': -2}, question='Will the guard negotiate?')]}])
    a = complete(e, e.sim.create_run(e.nid, e.scope, 'author', body)); b = complete(e, e.sim.create_run(e.nid, e.scope, 'author', body))
    assert a['id'] != b['id'] and a['request_digest'] == b['request_digest'] and a['result_digest'] == b['result_digest']
    assert a['routes'] == b['routes'] and len(a['routes']) == 2
    assert a['routes'][0]['steps'][0]['applied'] and not a['routes'][1]['steps'][0]['applied']
    restarted = StorySimulatorService(ExperimentalStore(e.root, e.backend, e.url), e.novels, e.chapter_service, e.service, e.graph)
    assert restarted.run(e.nid, e.scope, a['id'])['routes'] == a['routes']
    assert (e.rows, e.chapters) == before


def test_cycle_step_branch_budget_and_cancel_bounds(env):
    e = env
    with pytest.raises(ValueError, match='branch limit'): run(e, max_branches=1, routes=[{'id': 'a', 'title': 'a', 'events': [event()]}, {'id': 'b', 'title': 'b', 'events': [event()]}])
    for invalid in ({'max_steps': 33}, {'max_branches': 9}, {'model_budget': 1}, {'model_id': 'mock-planner'}):
        with pytest.raises(ValueError): run(e, **invalid)
    r = run(e, world_time=0, max_steps=1, routes=[{'id': 'route-a', 'title': 'Bounded', 'events': [event('one'), event('two', at=2)]}])
    r = step(e, r); assert r['status'] == 'COMPLETED' and r['expansions'] == 1 and r['routes'][0]['status'] == 'LIMIT_REACHED'
    with pytest.raises(ValueError, match='cannot expand'): step(e, r)
    r = run(e, world_time=0, routes=[{'id': 'route-a', 'title': 'Cycle', 'events': [event('same', at=0), event('never', at=1)]}])
    r = step(e, r); assert r['expansions'] == 1 and r['routes'][0]['violations'][0]['code'] == 'CYCLE_STOPPED'
    r = run(e); r = e.sim.cancel(e.nid, e.scope, 'author', r['id'], 1)
    with pytest.raises(ValueError, match='cannot expand'): step(e, r)
    with pytest.raises(ValueError, match='finish'): save(e, r)
    assert e.sim.run(e.nid, e.scope, r['id'])['expansions'] == 0


def test_known_fact_ids_reused_hidden_facts_never_enter_context_or_counts(env):
    e = env; marker = 'HIDDEN_VILLAIN_SECRET_紫钥匙'
    hidden = relation(e, marker); learn(e, hidden, character='bob', chapter=1)
    ctx = e.sim.context(e.nid, e.scope, {'chapter_id': e.order[3], 'expected_version': 1, 'character_id': 'alice'})
    assert not ctx['knowledge'] and marker not in json.dumps(ctx) and hidden['id'] not in json.dumps(ctx)
    r = run(e); assert marker not in json.dumps(r) and r['expansions'] == 0
    with pytest.raises(ValueError, match='unavailable'): run(e, knowledge_ids=[hidden['id']])
    known = relation(e, 'Key opens gate'); fact = learn(e, known)
    r = run(e, knowledge_ids=[fact['id']], routes=[{'id': 'route-a', 'title': 'Known path', 'events': [event(requires_knowledge=[fact['id']], foreshadowing_links=[known['id']])]}])
    r = complete(e, r); assert r['routes'][0]['steps'][0]['applied']
    assert marker not in json.dumps(r)
    e.graph.review(e.nid, e.scope, 'author', fact['id'], 'archive', fact['version'])
    stale = e.sim.run(e.nid, e.scope, r['id'])
    assert stale['stale'] and stale['routes'] == [] and 'provenance' not in stale


@pytest.mark.parametrize('change', ['text', 'version', 'privacy', 'branch', 'delete', 'archive', 'node', 'character'])
def test_current_source_privacy_target_and_deletion_invalidate_every_result(env, change):
    from app.source_privacy import content_digest, review_source_privacy
    e = env; r = complete(e, run(e)); cid = e.order[3]
    if change == 'text': e.chapters[cid]['content'] += 'changed'
    elif change == 'version': e.chapters[cid]['version'] += 1
    elif change == 'privacy':
        chapter = e.chapters[cid]; review_source_privacy(chapter, None, 'author', 'CLOUD_ALLOWED', chapter['version'], content_digest(chapter), e.root)
    elif change == 'branch': e.chapters[cid]['branch_id'] = 'another'
    elif change == 'delete': del e.chapters[cid]; e.order.remove(cid)
    elif change == 'archive': e.order.remove(cid)
    elif change == 'character': e.rows['characters'].clear()
    else:
        e.service.edit_node(e.nid, e.scope, 'author', e.plan['root_node_id'], {'expected_version': 1, 'title': 'Changed plan'})
    result = e.sim.run(e.nid, e.scope, r['id'])
    assert result['stale'] and not result['routes'] and 'source_version' not in result
    with pytest.raises((StaleSourceError, ValueError, FileNotFoundError)): save(e, r)
    assert not e.service.proposals(e.nid, e.scope)


def test_pending_review_reuses_original_planning_authority_and_never_auto_accepts(env):
    e = env; before = deepcopy((e.chapters, e.rows)); r = complete(e, run(e)); saved = save(e, r)
    p = e.service.proposal(e.nid, e.scope, saved['proposal_id'])
    assert p['status'] == 'REVIEW' and p['execution_mode'] == 'DETERMINISTIC_MANUAL'
    assert p['simulation_provenance']['input_digest'] == r['request_digest']
    assert e.service.graph(e.nid, e.scope, e.plan['id'])['nodes'][0]['status'] == 'DRAFT'
    refreshed = e.sim.run(e.nid, e.scope, r['id']); assert save(e, refreshed) == saved
    assert len(e.service.proposals(e.nid, e.scope)) == 1
    approved = e.service.review(e.nid, e.scope, 'reviewer', p['id'], 'approve', 1)
    assert approved['status'] == 'APPROVED' and not e.service.proposal(e.nid, e.scope, p['id'])['stale']
    assert (e.chapters, e.rows) == before


@pytest.mark.parametrize('change', ['disabled', 'v1', 'knowledge', 'validator_missing'])
def test_legacy_planning_views_acceptance_history_and_conflicts_cannot_bypass(env, monkeypatch, change):
    e = env; known = relation(e); learned = learn(e, known)
    r = complete(e, run(e)); p = save(e, r)['proposal_id']
    if change == 'disabled': monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'advanced_planning_v2')
    elif change == 'v1': monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    elif change == 'validator_missing': e.service = PlanningService(e.store, e.novels, e.chapter_service)
    else: e.graph.review(e.nid, e.scope, 'reviewer', learned['id'], 'archive', learned['version'])
    assert e.service.proposals(e.nid, e.scope) == [] and e.service.list_review_items(e.nid, e.scope) == []
    for action in [lambda: e.service.proposal(e.nid, e.scope, p), lambda: e.service.history(e.nid, e.scope, p),
                   lambda: e.service.review(e.nid, e.scope, 'reviewer', p, 'approve', 900),
                   lambda: e.service.review(e.nid, e.scope, 'reviewer', p, 'reject', 1),
                   lambda: e.service.restore(e.nid, e.scope, 'author', p, 1, 1)]:
        with pytest.raises(StaleSourceError): action()


def test_final_authority_recheck_rolls_back_expansion_and_proposal(env):
    e = env; r = run(e); calls = []
    def deny_later():
        calls.append(1)
        if len(calls) >= 3: raise ValueError('REVOKED')
    with pytest.raises(ValueError, match='REVOKED'):
        e.sim.step(e.nid, e.scope, 'author', r['id'], 1, reauthorize=deny_later)
    assert e.sim.run(e.nid, e.scope, r['id'])['expansions'] == 0
    r = complete(e, r); calls.clear()
    with pytest.raises(ValueError, match='REVOKED'):
        e.sim.save(e.nid, e.scope, 'author', r['id'], {'expected_version': r['version'], 'route_id': 'route-a'}, reauthorize=deny_later)
    assert not e.service.proposals(e.nid, e.scope)


def test_concurrent_step_cas_has_single_expansion(env):
    e = env; r = run(e); barrier = threading.Barrier(2); outcomes = []
    def worker():
        barrier.wait()
        try: step(e, r); outcomes.append('ok')
        except CapabilityVersionConflict: outcomes.append('conflict')
    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    assert sorted(outcomes) == ['conflict', 'ok'] and e.sim.run(e.nid, e.scope, r['id'])['expansions'] == 1


def test_mounted_domain_router_current_authority_and_scope(env):
    e = env; app = FastAPI(); live = {'actor': 'author', 'enabled': True}
    def authorize(nid, token, branch, permission):
        if token != 'test' or permission != 'domain.write': raise HTTPException(403)
        return live['actor'], e.scope
    def flag(name):
        if not live['enabled']: raise HTTPException(404)
    app.include_router(create_story_simulator_router(e.sim, authorize, flag)); client = TestClient(app)
    base = f'/novels/{e.nid}/experimental/story-simulator'; headers = {'x-session-token': 'test'}
    assert client.get(base + '/runs').status_code == 403
    started = client.post(base + '/runs', json=request(e), headers=headers)
    assert started.status_code == 201 and started.headers['cache-control'] == 'no-store'
    rid = started.json()['id']
    result = client.post(base + f'/runs/{rid}/step', json={'expected_version': 1}, headers=headers)
    assert result.status_code == 200 and result.json()['status'] == 'COMPLETED'
    original = e.sim.catalog
    def revoke(nid, scope):
        result = original(nid, scope); live['actor'] = 'another'; return result
    e.sim.catalog = revoke
    assert client.get(base + '/catalog', headers=headers).status_code == 409
    live['enabled'] = False
    assert client.get(base + '/runs', headers=headers).status_code == 404


def test_maximum_manual_branch_product_is_fixed_and_cannot_expand_further(env):
    e = env
    routes = [{'id': f'route-{i}', 'title': f'Route {i}', 'motivation_hypothesis': f'Explicit motive {i}',
               'events': [event(f'event-{j}', at=j + 1) for j in range(32)]} for i in range(8)]
    row = complete(e, run(e, max_steps=32, max_branches=8, routes=routes))
    assert row['expansions'] == 256 and len(row['routes']) == 8
    assert all(r['cursor'] == 32 for r in row['routes'])
    assert row['routes'][0]['motivation_hypothesis'] != row['routes'][1]['motivation_hypothesis']
    with pytest.raises(ValueError, match='cannot expand'): step(e, row)


def test_stale_cancel_version_conflict_redacts_old_inputs(env):
    e = env; row = run(e)
    e.chapters[e.order[3]]['content'] = 'Changed'
    with pytest.raises(CapabilityVersionConflict) as failed:
        e.sim.cancel(e.nid, e.scope, 'author', row['id'], 999)
    assert failed.value.current['stale'] and failed.value.current['routes'] == []
    assert 'request' not in failed.value.current and 'input' not in failed.value.current
    cancelled = e.sim.cancel(e.nid, e.scope, 'author', row['id'], 1)
    assert cancelled['status'] == 'CANCELLED' and cancelled['stale']


def test_source_changed_during_final_handoff_rolls_back_pending_proposal(env):
    e = env; row = complete(e, run(e)); calls = []
    def change_at_commit():
        calls.append(1)
        if len(calls) == 3: e.chapters[e.order[3]]['content'] += ' changed at final boundary'
    with pytest.raises(StaleSourceError):
        e.sim.save(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version'], 'route_id': 'route-a'}, reauthorize=change_at_commit)
    assert e.store.read(e.nid, e.scope)['collections'].get(e.service.PROPOSALS, {}) == {}
