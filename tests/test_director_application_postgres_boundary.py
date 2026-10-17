"""Actual mounted PG storage must reject unsupported pending review before writes."""
from dataclasses import replace
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from app.actor_context import SessionContext
from app.trusted_sessions import TrustedSessionResolver
from app.creative.generation import DirectorModelCoordinator
from app.repositories.postgres.generation import PostgresGenerationRepository
from app.services.generation_service import GenerationService
from creative_director_execution_fixture import FLAGS, ForbiddenOwner
from test_v2_creative_project_lifecycle import rig
from test_v2_independent_director_adoption import board


@pytest.mark.postgres_backend_only
@pytest.mark.parametrize('rig', ['postgres'], indirect=True)
@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_actual_pg_host_neither_advertises_nor_executes_file_only_pending(rig, monkeypatch, prefix):
    import app.main as main
    import app.api as legacy
    import app.experimental.api as experimental
    e = rig
    e.actor = 'local-author'
    e.documents = e.service
    board(e)
    forbidden = ForbiddenOwner()
    manager = ForbiddenOwner()
    manager.persistence = GenerationService(PostgresGenerationRepository(e.novels.novels.database))
    jobs_before = manager.persistence.load_all()
    e.service.proposals.generation = DirectorModelCoordinator(e.service.proposals, forbidden, forbidden, manager)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', FLAGS)
    monkeypatch.delenv('V1_ACCEPTANCE_MODE', raising=False)
    sessions = TrustedSessionResolver()
    sessions.register('synthetic-pg-host', SessionContext('pg-session', 'pg-client', e.actor, 'pg-workspace'))
    monkeypatch.setattr(main, 'settings', replace(main.settings,
        enable_packaged_runtime=False, enable_collaboration_runtime=False))
    monkeypatch.setattr(legacy, 'settings', replace(legacy.settings,
        enable_packaged_runtime=False, enable_collaboration_runtime=False))
    monkeypatch.setattr(main, 'trusted_session_resolver', sessions)
    monkeypatch.setattr(legacy, 'novel_service', e.novels)
    for name, value in vars(e.service).items():
        monkeypatch.setattr(experimental.creative_service, name, value)
    client = TestClient(main.app, client=('127.0.0.1', 41000), base_url='http://127.0.0.1:8000')
    base = prefix + f'/novels/{e.nid}/experimental/creative/director-proposals'
    headers = {'X-Session-Token': 'synthetic-pg-host'}
    before = deepcopy(e.store.read(e.nid, e.scope))
    result = client.get(base + '/model-capabilities', headers=headers)
    assert result.status_code == 200, result.text
    assert 'independent_director_contract' not in result.json()
    response = client.post(base + f'/{e.row["id"]}/model-v1/preview', headers=headers,
                           json={'expected_version': 1, 'route_id': 'unused-route',
                                 'allow_synthetic': False, 'max_output_tokens': 512, 'temperature': 0.0})
    assert response.status_code == 409, response.text
    value = response.json()
    assert set(value) == {'code', 'message', 'request_id', 'detail', 'details'}
    assert value['code'] == value['message'] == 'DIRECTOR_MODEL_ACTION_NOT_CONFIRMED'
    assert value['detail'] == value['details'] == {'code': value['code']}
    assert isinstance(value['request_id'], str) and value['request_id']
    assert 'postgresql' not in response.text and e.nid not in response.text
    assert e.store.read(e.nid, e.scope) == before
    assert manager.persistence.load_all() == jobs_before
