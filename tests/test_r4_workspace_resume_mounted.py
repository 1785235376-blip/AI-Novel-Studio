"""U01 mounted composition uses real preferences and original JobManager IDs."""
import json

from test_r3_mounted_contracts import mounted, prefix, checked
from test_r4_mounted_workspaces import workspace
from test_r4_author_task_projection import add


def test_mounted_resume_reuses_pins_and_original_jobs_without_execution(workspace, monkeypatch):
    e = workspace
    monkeypatch.setattr(e.api.jobs, 'jobs', {})
    monkeypatch.setattr(e.api.jobs, 'chapters', e.chapters)
    job = add(e)
    monkeypatch.setattr(e.api.jobs, 'create', lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('unexpected execution')))
    focus_path = e.base + '/writing-focus'
    reference = next(row for row in checked(e.client.get(focus_path + '/references'))['items'] if row['kind'] == 'chapter')
    preference = checked(e.client.put(focus_path + '/preferences', json={'expected_version': 0,
        'preferences': {'font_size': 24}, 'pins': [{key: reference[key] for key in ('kind', 'id', 'revision')}]}))
    path = e.base + '/workspace/resume'
    saved = checked(e.client.put(path, json={'chapter_id': e.chapter['id'], 'chapter_version': e.chapter['version'],
        'view': {'focus_active': True, 'references_visible': False},
        'layout': {'search_query': 'Alice', 'task_query': job.id, 'show_failed_only': True}}))['item']
    assert any(task['id'] == job.id and task['source']['chapter_id'] == e.chapter['id'] for task in saved['pending_tasks'])
    assert 'PRIVATE' not in json.dumps(saved)
    target = checked(e.client.post(path + '/resolve', json={'expected_version': saved['version']}))
    assert target['workspace']['focus_preferences']['font_size'] == 24
    assert target['workspace']['view']['references_visible'] is False
    assert checked(e.client.get(focus_path + '/preferences')) == preference
    assert len(e.api.jobs.jobs) == 1 and job.status == 'COMPLETED'
    job.status = 'ACCEPTED'
    current = checked(e.client.get(path))['item']
    assert next(task for task in current['pending_tasks'] if task['id'] == job.id)['status'] == 'ACCEPTED'
    e.api.jobs.jobs.clear()
    missing = checked(e.client.get(path))['item']
    assert missing['tasks_recovery_required'] is True
    assert job.id not in json.dumps(missing['pending_tasks'])
    assert 'pending_task_refs' not in missing
