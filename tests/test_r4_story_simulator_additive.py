"""Additive reconciliation scenarios and their minimal independent fixture support."""

from __future__ import annotations

from copy import deepcopy

import pytest

from app.experimental.flags import FLAGS

from app.experimental.planning import PlanningService

from app.experimental.story_simulator import StorySimulatorService

from app.experimental.story_graph import StoryGraphService

from app.experimental.store import ExperimentalStore

from support_reconciliation_test_r3_planning import planning_env

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

def test_saved_route_reopens_exact_original_proposal_constraints_and_review_after_restart(env):
    """Navigation consumes durable original IDs; no parallel handoff persistence."""
    e = env
    before = deepcopy((e.chapters, e.rows))
    checked = complete(e, run(e, assumptions=['author hypothesis'],
                              hard_constraints={'forbidden_facts': ['forbidden outcome']}))
    saved = save(e, checked)
    store = ExperimentalStore(e.root, e.backend, e.url)
    planning = PlanningService(store, e.novels, e.chapter_service)
    graph = StoryGraphService(store, e.novels, e.chapter_service)
    simulator = StorySimulatorService(store, e.novels, e.chapter_service, planning, graph)
    proposal = planning.proposal(e.nid, e.scope, saved['proposal_id'])
    provenance = proposal['simulation_provenance']
    reopened = simulator.run(e.nid, e.scope, provenance['run_id'])
    assert proposal['status'] == 'REVIEW' and not proposal['stale']
    assert reopened['routes'][0]['saved_proposal_id'] == proposal['id']
    assert provenance['route_id'] == reopened['routes'][0]['id']
    assert provenance['input_digest'] == reopened['request_digest']
    assert provenance['result_digest'] == reopened['result_digest']
    assert reopened['input']['assumptions'] == ['author hypothesis']
    assert reopened['input']['hard_constraints']['forbidden_facts'] == ['forbidden outcome']
    captures = reopened['provenance']['source_versions']
    assert set(captures) == set(proposal['sources'])
    assert {cid: {key: capture[key] for key in ('version', 'digest')}
            for cid, capture in captures.items()} == proposal['sources']
    approved = planning.review(e.nid, e.scope, 'reviewer', proposal['id'], 'approve', proposal['version'])
    assert approved['status'] == 'APPROVED'
    assert planning.history(e.nid, e.scope, proposal['id'])
    assert (e.chapters, e.rows) == before
