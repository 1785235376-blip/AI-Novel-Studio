"""Legacy review routes cannot bypass a derived experiment's own authority."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.creation_workbench_api import create_workbench_router
from app.services.creation_workbench_service import CreationWorkbenchService, CommentIn
from app.services.v1_capability_service import V1CapabilityService
from test_r3_planning import planning_env


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_original_comments_work_but_derived_judge_threads_are_always_fenced(planning_env, monkeypatch, prefix):
    e = planning_env
    creation = CreationWorkbenchService(V1CapabilityService(e.root, e.novels, e.chapter_service, None), e.chapter_service, e.novels)
    derived = creation.create_comment(e.nid, e.scope, 'author', CommentIn(chapter_id=e.order[0], chapter_version=1, text='PRIVATE_DERIVED_FINDING'))
    rows = creation._rows('review_threads'); rows[0]['narrative_judge'] = {'decision': 'PENDING'}
    creation.store._write('review_threads', rows)
    ordinary = creation.create_comment(e.nid, e.scope, 'author', CommentIn(chapter_id=e.order[0], chapter_version=1, text='An ordinary comment'))
    authorize = lambda nid, token, branch, permission: ('author', e.scope)
    app = FastAPI(); app.include_router(create_workbench_router(creation, authorize), prefix=prefix)
    client = TestClient(app); base = prefix + '/novels/' + e.nid
    for acceptance in ('false', 'true'):
        monkeypatch.setenv('V1_ACCEPTANCE_MODE', acceptance)
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', '' if acceptance == 'false' else 'narrative_quality_judge_v2,advanced_planning_v2,world_character_engines_v2,unified_review_inbox')
        response = client.get(base + '/review-threads')
        assert response.status_code == 200
        assert [row['id'] for row in response.json()['items']] == [ordinary['id']]
        assert 'PRIVATE_DERIVED_FINDING' not in response.text
        blocked = client.post(base + '/review-threads/' + derived['id'] + '/resolve', json={'expected_version': derived['version']})
        assert blocked.status_code == 404
    resolved = client.post(base + '/review-threads/' + ordinary['id'] + '/resolve', json={'expected_version': 1})
    assert resolved.status_code == 200 and resolved.json()['status'] == 'RESOLVED'
    assert creation._rows('review_threads')[0]['narrative_judge']['decision'] == 'PENDING'
