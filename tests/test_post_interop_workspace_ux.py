"""New U01/U03/U07 continuation contracts, real File and opted-in PostgreSQL.

Synthetic manuscripts only. Original queues, transition methods, project roles
and persistence are exercised; no model, external provider or GPU dispatch.
"""
import json

import pytest
from fastapi import HTTPException

from app.jobs import mark_generation_origin
from app.experimental.store import ExperimentalStore
from app.experimental.ux import TaskReader, WorkspaceToolsService
from app.services.generation_service import GenerationService
from app.services.image_job_service import ImageJobService
from app.services.audiobook_service import AudiobookService
from test_r3_mounted_contracts import mounted, prefix, checked, scoped
from test_r4_mounted_workspaces import workspace
from test_r4_author_task_projection import add


def tasks(e, headers=None):
    return checked(e.client.get(e.base + '/workspace/tasks', headers=headers or {}))


def task(e, authority, rid, headers=None):
    return next(row for row in tasks(e, headers)['items'] if row['authority'] == authority and row['id'] == rid)


def cancel(e, row, headers=None):
    return e.client.post(e.base + f"/workspace/tasks/{row['authority']}/{row['id']}/cancel",
                         json={'expected_revision': row['revision']}, headers=headers or {})


def test_original_author_cancel_receipt_terminal_late_output_restart_and_model_identity(workspace, monkeypatch):
    e = workspace
    monkeypatch.setattr(e.api.jobs, 'jobs', {})
    monkeypatch.setattr(e.api.jobs, 'chapters', e.chapters)
    persistence = GenerationService(e.bundle.generations)
    monkeypatch.setattr(e.api.jobs, 'persistence', persistence)
    job = add(e); job.status = 'QUEUED'; job.requested_provider = 'local-fixture'; job.requested_model = 'model-fixture'
    monkeypatch.setattr(e.api.jobs, 'create', lambda *a, **k: pytest.fail('cancellation created another job'))
    row = task(e, 'author_generation', job.id)
    assert row['route_state'] == 'REQUESTED' and row['model_id'] == 'model-fixture'
    assert 'cancel' in row['actions'] and len(row['revision']) == 64
    result = checked(cancel(e, row))
    assert result['item']['status'] == 'CANCELLED' and result['cancellation_requested']
    assert 'PRIVATE' not in json.dumps(result)
    assert job.cancelled.is_set() and job.status == 'CANCELLED'
    e.api.jobs._emit(job, 'LATE_PROVIDER_OUTPUT')
    assert job.output == 'PRIVATE OUTPUT'
    assert persistence.get(job.id)['status'] == 'CANCELLED'
    assert cancel(e, row).status_code == 409
    assert 'cancel' not in task(e, 'author_generation', job.id)['actions']


def test_cancel_stale_terminal_and_feature_off_never_dispatch(workspace, monkeypatch):
    e = workspace
    monkeypatch.setattr(e.api.jobs, 'jobs', {})
    monkeypatch.setattr(e.api.jobs, 'chapters', e.chapters)
    job = add(e); job.status = 'QUEUED'; mark_generation_origin(job, 'author_context')
    row = task(e, 'author_generation', job.id)
    monkeypatch.setattr(e.api, 'cancel', lambda *a, **k: pytest.fail('stale/off cancellation dispatched'))
    job.status = 'COMPLETED'
    assert cancel(e, row).status_code == 409
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'workspace_tools_v2')
    assert cancel(e, row).status_code == 404
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    assert cancel(e, row).status_code == 404


def test_author_cancel_requires_current_project_writer_and_rechecks_revocation(workspace, monkeypatch):
    e = scoped(workspace, monkeypatch)
    monkeypatch.setattr(e.api.jobs, 'jobs', {})
    monkeypatch.setattr(e.api.jobs, 'chapters', e.chapters)
    job = add(e); job.status = 'QUEUED'
    row = task(e, 'author_generation', job.id, e.headers)
    assert cancel(e, row, e.viewer_headers).status_code == 403
    e.authorization.revoke_role(e.role, e.lead)
    assert cancel(e, row, e.headers).status_code == 403
    assert not job.cancelled.is_set()


def test_aggregate_task_and_diagnostic_late_revocation_discards_all_source_rows(workspace, monkeypatch):
    e = scoped(workspace, monkeypatch)
    service = e.experimental.workspace_tools_service
    def revoked(ctx):
        e.authorization.revoke_role(e.role, e.lead)
        return [{'id': 'PRIVATE_LATE_TASK', 'novel_id': e.nid, 'scope': e.scope, 'status': 'RUNNING'}]
    monkeypatch.setattr(service, 'task_readers', (TaskReader('fixture', 'Fixture', 'agents', revoked),))
    result = e.client.get(e.base + '/workspace/tasks', headers=e.headers)
    assert result.status_code == 403 and 'PRIVATE_LATE_TASK' not in result.text
    assert e.client.post(e.base + '/workspace/diagnostics/preview', json={}, headers=e.headers).status_code == 403


def test_import_team_cancel_use_original_cas_and_persist_on_restart(workspace):
    e = workspace
    imported = checked(e.client.post(e.base + '/imports/jobs', json={'chapter_ids': [e.chapter['id']],
        'chunk_size': 8000, 'overlap': 256, 'adapter_id': 'local-semantic-rules-v2'}), 201)
    team = checked(e.client.post(e.base + '/teams/runs', json={'recipe_id': 'outline_chapter_editor',
        'instruction': 'Synthetic proposal', 'chapter_ids': [e.chapter['id']]}), 201)
    for authority, record, path in [('semantic_import', imported, '/imports/jobs/'), ('agent_team', team, '/teams/runs/')]:
        row = task(e, authority, record['id'])
        assert 'cancel' in row['actions']
        result = checked(cancel(e, row))['item']
        assert result['status'] == 'CANCELLED' and result['version'] == record['version'] + 1
        assert checked(e.client.get(e.base + path + record['id']))['status'] == 'CANCELLED'
        assert cancel(e, row).status_code == 409
    # Recreate only the workspace projection; original owner records remain the authority.
    restarted = WorkspaceToolsService(ExperimentalStore(e.root, e.backend, e.url), e.novels, e.chapters,
                                     task_readers=e.experimental.workspace_tools_service.task_readers)
    from app.experimental.ux import ReadContext
    assert any(row['id'] == team['id'] and row['status'] == 'CANCELLED'
               for row in restarted.tasks(ReadContext(e.nid, e.scope, 'local-author'), lambda _: None)['items'])


def test_original_image_and_audio_tasks_cancel_without_dispatch(workspace, monkeypatch):
    e = workspace
    images = ImageJobService(e.root)
    monkeypatch.setattr(e.api, 'image_job_service', images)
    image = images.create(e.nid, None, {'provider_id': 'fixture', 'model_id': 'image', 'prompt': 'PRIVATE_IMAGE_PROMPT'})
    audio = AudiobookService(e.audio, e.assets).queue(e.nid, e.chapter,
        {'provider_id': 'fixture', 'model_id': 'tts', 'voice': 'synthetic'}, [])
    for authority, rid in [('images', image['id']), ('audio_tts', audio['id'])]:
        row = task(e, authority, rid)
        assert row['route_state'] == 'REQUESTED'
        result = checked(cancel(e, row))
        assert result['item']['status'] == 'CANCELLED'
        assert 'PRIVATE_IMAGE_PROMPT' not in json.dumps(result)
        assert e.chapter['content'] not in json.dumps(result)
    assert images.list(e.nid)[0]['status'] == 'CANCELLED'
    assert e.audio.load(e.nid)['jobs'][0]['status'] == 'CANCELLED'


def test_broader_original_search_precise_record_navigation_source_fence_and_branch_isolation(workspace, monkeypatch):
    e = workspace
    e.novels.upsert_volume(e.nid, 'ux-volume', {'title': '合成卷影', 'goal': 'PRIVATE_VOLUME_DETAIL'})
    e.novels.upsert_scene(e.nid, 'ux-scene', {'title': '合成场影', 'chapter_id': e.chapter['id'], 'purpose': 'PRIVATE_SCENE_DETAIL'})
    e.novels.upsert_timeline_event(e.nid, 'ux-time', {'title': '合成时影', 'description': 'PRIVATE_TIMELINE_DETAIL'})
    for kind, rid in [('volume', 'ux-volume'), ('scene', 'ux-scene'), ('timeline', 'ux-time')]:
        value = checked(e.client.get(e.base + '/workspace/search', params={'kind': kind, 'q': '合成'}))
        row = next(item for item in value['items'] if item['id'] == rid)
        assert 'PRIVATE_' not in json.dumps(value)
        target = {key: row[key] for key in ('kind', 'id', 'revision', 'offset')}
        resolved = checked(e.client.post(e.base + '/workspace/search/resolve', json=target))
        assert resolved['record_kind'] == kind and resolved['id'] == rid and resolved['feature'] == 'story'
        if kind == 'scene':
            e.novels.upsert_scene(e.nid, rid, {'title': '合成场影', 'chapter_id': e.chapter['id'], 'purpose': 'CHANGED_PRIVATE_DETAIL'})
            assert e.client.post(e.base + '/workspace/search/resolve', json=target).status_code == 409
    assert checked(e.client.get(e.base + '/workspace/search', params={'kind': 'novel'}))['items'][0]['id'] == e.nid
    e = scoped(e, monkeypatch)
    for kind in ('volume', 'scene', 'timeline', 'novel'):
        assert checked(e.client.get(e.base + '/workspace/search', params={'kind': kind}, headers=e.headers))['items'] == []


def test_review_inbox_original_ids_resume_and_exact_owner_navigation(workspace, monkeypatch):
    from app.experimental.inbox import ReviewBinding
    e = workspace
    row = {'id': 'review-original', 'novel_id': e.nid, 'scope': e.scope, 'status': 'REVIEW', 'version': 1, 'preview': 'PRIVATE_REVIEW_TEXT'}
    monkeypatch.setattr(e.experimental.inbox_service, 'bindings', {'fixture': ReviewBinding('fixture', lambda ctx: [row])})
    projected = task(e, 'review_inbox', 'fixture:review-original')
    assert projected['source'] == {'kind': 'feature', 'id': 'review-original', 'feature': 'unified_review_inbox',
                                   'task_authority': 'review_inbox', 'parent_id': 'fixture'}
    assert 'PRIVATE_REVIEW_TEXT' not in json.dumps(projected)
    saved = checked(e.client.put(e.base + '/workspace/resume', json={'stopping_note': 'Synthetic review next'}))['item']
    assert any(item['authority'] == 'review_inbox' for item in saved['pending_tasks'])
    search = checked(e.client.get(e.base + '/workspace/search', params={'kind': 'review'}))
    assert search['items'][0]['kind'] == 'review'
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'workspace_tools_v2')
    current = checked(e.client.get(e.base + '/workspace/resume'))['item']
    assert current['pending_tasks'] == [] and current['tasks_recovery_required']

def test_original_agent_working_stage_and_workflow_waiting_gate_cancel(workspace):
    e = workspace
    from app.actor_context import SessionContext
    e.sessions.register('workspace-owner', SessionContext('ux-session', 'ux-client', 'local-author', 'local-workspace'))
    headers = {'X-Session-Token': 'workspace-owner'}
    agent = checked(e.client.post(e.prefix + '/agent-jobs', headers=headers, json={'agent_id': 'planner', 'novel_id': e.nid, 'chapter': e.chapter['number'], 'instruction': 'PRIVATE_AGENT_PROMPT'}), 202)
    e.bundle.generations.save({**agent, 'status': 'WORKING'})
    projected = task(e, 'agents', agent['id'], headers)
    assert projected['stage_label'] == '运行中' and 'cancel' in projected['actions']
    assert checked(cancel(e, projected, headers))['item']['status'] == 'CANCELLED'
    assert e.agents.get(agent['id'])['status'] == 'CANCELLED'
    definition = checked(e.client.post(e.prefix + '/workflows', headers=headers, json={'novel_id': e.nid, 'title': 'Synthetic human gate',
        'nodes': [{'id': 'gate', 'type': 'manual_approval', 'name': 'Review', 'config': {}}], 'edges': []}), 201)
    run = checked(e.client.post(e.prefix + f"/workflows/{definition['id']}/runs", headers=headers, json={'input': {}, 'initiated_by': 'ignored'}), 202)
    projected = task(e, 'workflows', run['id'], headers)
    assert projected['source']['parent_id'] == definition['id']
    assert checked(cancel(e, projected, headers))['item']['status'] == 'CANCELLED'
    assert checked(e.client.get(e.prefix + '/workflow-runs/' + run['id'], headers=headers))['status'] == 'CANCELLED'


def test_motion_projection_and_cancel_stay_in_original_screenplay(workspace):
    e = workspace
    screenplay = e.screenplays.create(e.nid, 'Synthetic screenplay')
    e.screenplays._save_screenplay(e.nid, {**screenplay, 'motion_tasks': [{'id': 'motion-synthetic', 'status': 'PENDING',
        'provider_id': 'fixture-video', 'model_id': 'unconfigured', 'prompt': 'PRIVATE_VIDEO_PROMPT', 'progress': 0}]})
    projected = task(e, 'motion', 'motion-synthetic')
    assert projected['source']['parent_id'] == screenplay['id'] and projected['progress'] is None
    result = checked(cancel(e, projected))['item']
    assert result['status'] == 'CANCELLED' and 'PRIVATE_VIDEO_PROMPT' not in json.dumps(result)
    original = next(row for row in e.screenplays.list(e.nid) if row['id'] == screenplay['id'])
    assert original['motion_tasks'][0]['status'] == 'CANCELLED'
