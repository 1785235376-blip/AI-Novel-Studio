"""Narrow R3 planning compatibility: final current-authority and provenance guards."""
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.experimental.common import StaleSourceError
from app.experimental.planning import PlanningService
from app.experimental.planning_api import create_planning_router
from test_r3_planning import planning_env, graph, proposal


def test_final_review_authority_failure_rolls_back_node_and_proposal(planning_env):
    e = planning_env; g = graph(e); p = proposal(e, g['root_node_id'])
    def revoked(): raise ValueError('AUTHORITY_REVOKED')
    with pytest.raises(ValueError, match='AUTHORITY_REVOKED'):
        e.service.review(e.nid, e.scope, 'reviewer', p['id'], 'approve', 1, reauthorize=revoked)
    assert e.service.proposal(e.nid, e.scope, p['id'])['status'] == 'REVIEW'
    assert e.service.graph(e.nid, e.scope, g['id'])['nodes'][0]['version'] == 1
    e.service.review(e.nid, e.scope, 'reviewer', p['id'], 'reject', 1)
    with pytest.raises(ValueError, match='AUTHORITY_REVOKED'):
        e.service.restore(e.nid, e.scope, 'writer', p['id'], 2, 1, reauthorize=revoked)
    assert e.service.proposal(e.nid, e.scope, p['id'])['status'] == 'REJECTED'


def test_provenance_without_transient_validator_is_never_read_or_accepted(planning_env):
    e = planning_env; g = graph(e); p = proposal(e, g['root_node_id'])
    with e.store.transaction(e.nid, e.scope) as state:
        state['collections'][e.service.PROPOSALS][p['id']]['simulation_provenance'] = {'run_id': 'source'}
    service = PlanningService(e.store, e.novels, e.chapter_service)
    assert service.proposals(e.nid, e.scope) == [] and service.list_review_items(e.nid, e.scope) == []
    with pytest.raises(StaleSourceError): service.history(e.nid, e.scope, p['id'])
    with pytest.raises(StaleSourceError): service.proposal(e.nid, e.scope, p['id'])
    with pytest.raises(StaleSourceError): service.review(e.nid, e.scope, 'reviewer', p['id'], 'approve', 99)


def test_planning_http_reauthorizes_final_review_and_restore(planning_env, monkeypatch):
    e = planning_env; g = graph(e); p = proposal(e, g['root_node_id']); active = {'actor': 'writer'}
    def authorize(nid, token, branch, permission):
        if token != 'test': raise HTTPException(403)
        return active['actor'], e.scope
    app = FastAPI(); app.include_router(create_planning_router(e.service, authorize, lambda name: None))
    client = TestClient(app); base = f'/novels/{e.nid}/experimental/planning/proposals/{p["id"]}'; headers = {'x-session-token': 'test'}
    original = e.service._assert_fresh
    def changed(*args, **kwargs):
        original(*args, **kwargs); active['actor'] = 'other'
    monkeypatch.setattr(e.service, '_assert_fresh', changed)
    response = client.post(base + '/approve', headers=headers, json={'expected_version': 1})
    assert response.status_code == 409 and response.json()['detail']['code'] == 'PLANNING_AUTHORITY_CHANGED'
    monkeypatch.setattr(e.service, '_assert_fresh', original)
    assert e.service.proposal(e.nid, e.scope, p['id'])['status'] == 'REVIEW'
