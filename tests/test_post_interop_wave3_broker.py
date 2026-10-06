"""Policies and evidence projections cannot invent quality or cloud consent."""
import copy
import pytest
from app.experimental.common import StaleSourceError
from test_r3_planning import planning_env
from test_r4_model_broker import env, preview, create_set, start


def test_privacy_first_and_local_first_fallback_remain_explicit(env, monkeypatch):
    e = env; remote = {**e.route, 'cloud': True}
    monkeypatch.setattr(e.service, 'candidates', lambda: [copy.deepcopy(remote)])
    arguments = {'chapter_ids': [], 'allow_synthetic': True, 'profile': 'HYBRID'}
    local = e.service.preview(e.nid, e.scope, 'writer', {**arguments, 'policy': 'LOCAL_FIRST'})
    assert local['chosen'] is None and 'LOCAL_TO_CLOUD_FALLBACK_NOT_APPROVED' in local['candidates'][0]['reasons']
    private = e.service.preview(e.nid, e.scope, 'writer', {**arguments, 'policy': 'PRIVACY_FIRST', 'allow_cloud_fallback': True})
    assert private['chosen'] is None and 'PRIVACY_FIRST_LOCAL_ONLY' in private['candidates'][0]['reasons']
    allowed = e.service.preview(e.nid, e.scope, 'writer', {**arguments, 'policy': 'LOCAL_FIRST', 'allow_cloud_fallback': True})
    assert allowed['chosen']['cloud'] is True and allowed['execution_authorized'] is False and allowed['automatic_fallback'] is False


def test_local_first_does_not_promote_preferred_cloud_over_legal_local(env, monkeypatch):
    e = env; remote = {**e.route, 'cloud': True, 'route_id': 'cloud-fixture'}
    monkeypatch.setattr(e.service, 'candidates', lambda: [copy.deepcopy(remote), copy.deepcopy(e.route)])
    row = e.service.preview(e.nid, e.scope, 'writer', {'allow_synthetic': True, 'policy': 'LOCAL_FIRST', 'profile': 'HYBRID', 'allow_cloud_fallback': True, 'preferred_route': 'cloud-fixture'})
    assert row['chosen']['cloud'] is False


def test_license_constraints_fence_dispatch_and_unknown_is_not_confirmed(env, monkeypatch):
    e = env; original = {**e.route, 'synthetic': False, 'identity': {**e.route['identity'], 'license_confirmed': False}}
    monkeypatch.setattr(e.service, 'candidates', lambda: [copy.deepcopy(original)])
    row = preview(e, require_confirmed_license=True)
    assert 'LICENSE_CONFIRMATION_REQUIRED' in row['candidates'][0]['reasons']
    assert row['candidates'][0]['license_confirmed'] is False


@pytest.mark.parametrize('policy', ['BALANCED', 'QUALITY_FIRST', 'SPEED_FIRST', 'COST_FIRST', 'PRIVACY_FIRST'])
def test_policy_aliases_preserve_unknown_quality_and_explain_order(env, policy):
    e = env; row = preview(e, policy=policy)
    assert row['chosen'] and row['chosen']['quality_score'] is None
    assert row['policy_explanation']['quality'] == 'NOT_MEASURED_NOT_RANKED'
    assert row['execution_authorized'] is False
    if policy == 'BALANCED': assert row['policy_explanation']['balanced_factors'] == ['CURRENT_COST_RANK', 'CURRENT_LATENCY_RANK', 'CLOUD_PENALTY']


def test_profiles_separate_catalog_from_contract_measurements(env):
    e = env
    before = next(r for r in e.bench.capability_profiles(e.nid, e.scope)['items'] if r['route_id'] == e.route['route_id'])
    assert before['evidence_tiers'] == ['CATALOG_CLAIM'] and before['measurements'] == []
    assert before['context']['tier'] == 'CATALOG_CLAIM' and before['throughput'] is None
    run = start(e, create_set(e)); completed = e.bench.step(e.nid, e.scope, 'writer', run['id'], run['version'])
    assert completed['status'] == 'COMPLETED'
    profile = next(r for r in e.bench.capability_profiles(e.nid, e.scope)['items'] if r['route_id'] == e.route['route_id'])
    assert profile['evidence_tiers'] == ['CATALOG_CLAIM', 'CONTRACT_TESTED']
    assert profile['measurements'][0]['metrics']['sample_count'] == 1
    assert profile['user_verified'] is False and profile['literary_quality'] is None and profile['memory_usage'] is None
    evidence = e.bench.evidence(e.nid, e.scope)[0]
    e.bench.invalidate(e.nid, e.scope, 'writer', evidence['id'], evidence['version'])
    assert next(r for r in e.bench.capability_profiles(e.nid, e.scope)['items'] if r['route_id'] == e.route['route_id'])['measurements'] == []


def test_user_verified_evidence_requires_completed_current_outputs_and_never_scores_quality(env):
    e = env; run = start(e, create_set(e)); e.bench.step(e.nid, e.scope, 'writer', run['id'], run['version'])
    evidence = e.bench.evidence(e.nid, e.scope)[0]
    body = {'expected_version': evidence['version'], 'reviewed_identity_and_outputs': True, 'note': 'Checked only these synthetic protocol outputs.'}
    review = e.bench.review_evidence(e.nid, e.scope, 'writer', evidence['id'], body)
    assert review['synthetic'] is True and review['quality_score'] is None and review['routing_weight'] is None
    assert e.bench.review_evidence(e.nid, e.scope, 'writer', evidence['id'], body)['id'] == review['id']
    with pytest.raises(FileNotFoundError): e.bench.review_evidence(e.nid, e.scope, 'other', evidence['id'], body)
    profile = next(r for r in e.bench.capability_profiles(e.nid, e.scope)['items'] if r['route_id'] == e.route['route_id'])
    assert profile['user_verified'] is True and 'USER_VERIFIED' in profile['evidence_tiers'] and 'LOCALLY_BENCHMARKED' not in profile['evidence_tiers']
    e.bench.invalidate(e.nid, e.scope, 'writer', evidence['id'], evidence['version'])
    assert not next(r for r in e.bench.capability_profiles(e.nid, e.scope)['items'] if r['route_id'] == e.route['route_id'])['user_verified']
    with pytest.raises(ValueError, match='CURRENT_EXECUTED'): e.bench.review_evidence(e.nid, e.scope, 'writer', evidence['id'], body)


def test_capability_profiles_and_review_api_use_existing_host_and_project_authority(env):
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient
    from app.experimental.model_benchmark_api import create_model_benchmark_router
    e = env; flags = {'model_benchmark_v2'}
    def flag(name):
        if name not in flags: raise HTTPException(404, 'disabled')
    def host(token):
        if token != 'valid': raise HTTPException(401, 'host session required')
    def authorize(nid, token, branch, permission): return 'writer', e.scope
    app = FastAPI(); app.include_router(create_model_benchmark_router(e.bench, authorize, flag, host))
    client = TestClient(app); base = f'/novels/{e.nid}/experimental/model-benchmarks'; headers = {'X-Session-Token': 'valid'}
    assert client.get(base + '/profiles').status_code == 401
    response = client.get(base + '/profiles', headers=headers)
    assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
    assert response.json()['catalog_is_measurement'] is False
    flags.clear()
    assert client.get(base + '/profiles', headers=headers).status_code == 404
