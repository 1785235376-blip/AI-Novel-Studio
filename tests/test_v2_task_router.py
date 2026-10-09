"""Narrative routing uses original live registries; never executes or falls back."""
import copy

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.experimental.common import StaleSourceError
from app.experimental.model_broker import BrokerRequest, NARRATIVE_TASK_CAPABILITIES
from app.experimental.model_broker_api import create_model_broker_router
from app.experimental.research_vision import SyntheticResearchVisionProvider
from test_r3_planning import planning_env
from test_r4_model_broker import env


def task(e, task_type='DIRECTOR_NOTES', **extra):
    return e.service.preview_task(e.nid, e.scope, 'writer', {
        'task_type': task_type, 'chapter_ids': [e.order[0]], **extra})


@pytest.mark.parametrize('task_type', list(NARRATIVE_TASK_CAPABILITIES))
def test_task_routes_only_exact_capability_and_never_dispatches(env, task_type):
    e = env
    before = copy.deepcopy(e.chapters)
    result = task(e, task_type, allow_synthetic=True)
    assert result['request']['capability'] == NARRATIVE_TASK_CAPABILITIES[task_type]
    assert result['request']['task_type'] == task_type
    assert result['request']['profile'] == 'LOCAL_ONLY'
    assert result['request']['max_cost_microusd'] == 0
    assert result['execution_authorized'] is False
    assert result['automatic_fallback'] is False
    assert not e.service.ledger(e.nid, e.scope, 'writer')
    assert e.chapters == before
    if result['chosen']:
        assert result['chosen']['capability'] == NARRATIVE_TASK_CAPABILITIES[task_type]
        assert result['chosen']['cloud'] is False
    else:
        assert result['status'] == 'NO_LEGAL_ROUTE'


def test_task_cannot_override_capability_locality_or_spending(env):
    for extra in ({'capability': 'TEXT'}, {'profile': 'HYBRID'}, {'max_cost_microusd': 1},
                  {'allow_cloud_fallback': True}):
        with pytest.raises(ValueError):
            task(env, 'FRAME_ANALYSIS', **extra)
    with pytest.raises(ValueError):
        task(env, 'UNKNOWN')
    with pytest.raises(ValueError, match='TASK_CAPABILITY_MISMATCH'):
        BrokerRequest(task_type='FRAME_ANALYSIS', capability='TEXT')


def test_absent_vision_does_not_mislabel_text_or_discovery_as_inference(env):
    result = task(env, 'FRAME_ANALYSIS', allow_synthetic=True)
    assert result['chosen'] is None
    assert all(not candidate['eligible'] for candidate in result['candidates'])
    assert not any(candidate['capability'] == 'VISION' for candidate in result['candidates'])


def test_vision_provider_owner_binding_review_boundary_and_restart_fence(env):
    e = env
    provider = SyntheticResearchVisionProvider()
    e.service.vision_resolver = lambda: provider
    assert task(e, 'FRAME_ANALYSIS')['chosen'] is None
    result = task(e, 'FRAME_ANALYSIS', allow_synthetic=True)
    chosen = result['chosen']
    assert chosen['capability'] == 'VISION'
    assert chosen['verification'] == 'SYNTHETIC_PROTOCOL_ONLY'
    assert chosen['executor'] == 'original.research_analysis'
    assert chosen['identity']['model_version'] == '1'
    assert result['execution_authorized'] is False
    e.service.vision_resolver = lambda: SyntheticResearchVisionProvider()
    with pytest.raises(StaleSourceError, match='ROUTE_CHANGED'):
        e.service.reserve(e.nid, e.scope, 'writer', result['id'], 1, 'one', 'job')
    e.service.vision_resolver = lambda: None
    assert task(e, 'FRAME_ANALYSIS', allow_synthetic=True)['chosen'] is None


def test_task_refuses_implicit_cloud_and_fences_source_and_authority(env, monkeypatch):
    e = env
    cloud = {**e.route, 'cloud': True}
    monkeypatch.setattr(e.service, 'candidates', lambda: [copy.deepcopy(cloud)])
    assert task(e, allow_synthetic=True)['chosen'] is None
    def revoked():
        raise ValueError('permission revoked')
    before = e.store.read(e.nid, e.scope)
    with pytest.raises(ValueError, match='revoked'):
        e.service.preview_task(e.nid, e.scope, 'writer', {'task_type': 'DIRECTOR_NOTES'}, revoked)
    assert e.store.read(e.nid, e.scope) == before


def test_mounted_task_preview_requires_both_flags_and_host_session(env):
    e = env
    flags = {'model_broker_v2', 'narrative_production_v2'}
    def require_flag(name):
        if name not in flags:
            raise HTTPException(404, 'disabled')
    def authorize(nid, token, branch, permission):
        if nid != e.nid or token != 'host':
            raise HTTPException(403, 'denied')
        return 'writer', e.scope
    def host(token):
        if token != 'host':
            raise HTTPException(403, 'host required')
    app = FastAPI()
    app.include_router(create_model_broker_router(e.service, authorize, require_flag, host))
    client = TestClient(app)
    base = f'/novels/{e.nid}/experimental/model-broker'
    value = {'task_type': 'DIRECTOR_NOTES', 'allow_synthetic': True}
    assert client.post(base + '/task-preview', json=value).status_code == 403
    response = client.post(base + '/task-preview', json=value, headers={'X-Session-Token': 'host'})
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert response.json()['chosen']['capability'] == 'TEXT'
    capabilities = client.get(base + '/task-capabilities', headers={'X-Session-Token': 'host'}).json()
    assert capabilities['human_review_required'] is True
    assert len(capabilities['tasks']) == 7
    flags.remove('narrative_production_v2')
    assert client.post(base + '/task-preview', json=value, headers={'X-Session-Token': 'host'}).status_code == 404
    assert client.get(base + '/task-capabilities', headers={'X-Session-Token': 'host'}).status_code == 404


def test_vision_recipe_requires_image_understanding_operation(env):
    provider = SyntheticResearchVisionProvider()
    provider.capability = provider.capability.model_copy(update={'operations': ['OCR']})
    env.service.vision_resolver = lambda: provider
    result = task(env, 'FRAME_ANALYSIS', allow_synthetic=True)
    assert result['chosen'] is None
    vision = next(row for row in result['candidates'] if row['capability'] == 'VISION')
    assert 'TASK_OPERATION_NOT_SUPPORTED' in vision['reasons']


def test_narrative_job_origins_preserve_generation_feature_fences():
    from app.jobs import GENERATION_ORIGINS
    required = frozenset({'narrative_production_v2', 'author_context_inspector_v2', 'model_broker_v2'})
    assert GENERATION_ORIGINS['narrative_task_model'] == required
    assert GENERATION_ORIGINS['creative_director_model'] == required
