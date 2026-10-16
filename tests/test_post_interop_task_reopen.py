"""U07 additive original-owner result pointers preserve the legacy task shape."""
import json
import pytest
from app.jobs import mark_generation_origin
from test_r3_mounted_contracts import mounted, prefix, checked, scoped
from test_r4_mounted_workspaces import workspace
from test_r4_author_task_projection import add

OWNERS = [
    ('declarative_agent', 'declarative_agents_v2', 'declarative_model_job'),
    ('story_simulator_model', 'story_simulator_v2', 'simulator_model_job'),
    ('multilingual_translation', 'multilingual_editions_v2', 'translation_model_job'),
    ('narrative_judge_model', 'narrative_quality_judge_v2', 'judge_model_job'),
]

@pytest.mark.parametrize('origin,feature,owner', OWNERS)
def test_exact_owner_pointer_is_additive_current_and_no_generic_accept(workspace, monkeypatch, origin, feature, owner):
    e = workspace
    monkeypatch.setattr(e.api.jobs, 'jobs', {}); monkeypatch.setattr(e.api.jobs, 'chapters', e.chapters)
    job = add(e); mark_generation_origin(job, origin)
    result = checked(e.client.get(e.base + '/workspace/tasks'))
    row = next(row for row in result['items'] if row['id'] == job.id)
    assert row['source'] == {'kind': 'feature', 'id': job.id, 'feature': feature}
    assert row['owner_navigation'] == {**row['source'], 'task_authority': owner, 'chapter_id': job.chapter_id, 'version': job.base_chapter_version}
    assert row['actions'] == ['open_source'] and 'PRIVATE OUTPUT' not in json.dumps(row)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'workspace_tools_v2,author_context_inspector_v2,model_broker_v2')
    assert not any(row['id'] == job.id for row in checked(e.client.get(e.base + '/workspace/tasks'))['items'])


def test_owner_pointer_does_not_survive_project_role_revocation(workspace, monkeypatch):
    e = scoped(workspace, monkeypatch)
    monkeypatch.setattr(e.api.jobs, 'jobs', {}); monkeypatch.setattr(e.api.jobs, 'chapters', e.chapters)
    job = add(e); mark_generation_origin(job, 'narrative_judge_model')
    assert any(row.get('owner_navigation', {}).get('id') == job.id for row in checked(e.client.get(e.base + '/workspace/tasks', headers=e.headers))['items'])
    e.authorization.revoke_role(e.role, e.lead)
    response = e.client.get(e.base + '/workspace/tasks', headers=e.headers)
    assert response.status_code == 403 and job.id not in response.text
