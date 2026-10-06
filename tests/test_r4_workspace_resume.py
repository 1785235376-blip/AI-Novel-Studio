"""U01 restoration closes the loop through the original U04/U07 authorities.

Synthetic File contracts and the same cases against opt-in real PostgreSQL.
No second reference store, job submission, or model adapter is involved.
"""
import copy
import json

import pytest
from fastapi import HTTPException

from app.experimental.common import StaleSourceError
from app.experimental.ux import Layout, ReadContext, TaskReader, WorkspaceToolsService
from app.experimental.writing_focus import WritingFocusService
from test_r4_workspace_tools import ux_env, saved


def focus(e):
    service = WritingFocusService(e.store, e.novels, e.chapters)
    e.service.focus_reader = lambda ctx: {'preferences': service.preferences(ctx), 'pins': service.pinned(ctx)}
    source = service._source(e.ctx, 'chapter', 'chapter-2')
    pin = {key: source[key] for key in ('kind', 'id', 'revision')}
    service.save_preferences(e.ctx, {'expected_version': 0, 'preferences': {'font_size': 24}, 'pins': [pin]})
    return service, pin


def test_resume_reopens_original_preference_version_filters_and_task_ids(ux_env):
    e = ux_env
    authority, pin = focus(e)
    e.service.task_readers = (
        TaskReader('author_generation', '正文生成', 'history', lambda ctx: [
            {'id': 'original-ready', 'novel_id': ctx.novel_id, 'status': 'COMPLETED',
             'chapter_id': 'chapter-1', 'base_chapter_version': 1, 'output': 'must not copy output'}]),
        TaskReader('media', '媒体', 'assets', lambda ctx: [
            {'id': 'original-running', 'novel_id': ctx.novel_id, 'status': 'RUNNING', 'prompt': 'must not copy prompt'},
            {'id': 'done', 'novel_id': ctx.novel_id, 'status': 'COMPLETED'}]),
    )
    first = saved(e, layout={'search_query': '旧信', 'search_kind': 'chapter', 'search_current_chapter': True,
                            'task_query': '原任务', 'show_failed_only': True, 'section': 'tasks'},
                  view={'focus_active': True, 'references_visible': False})
    assert {task['id'] for task in first['pending_tasks']} == {'original-ready', 'original-running'}
    assert first['focus_state'] == 'READY'
    stored = e.store.read(e.ctx.novel_id, e.ctx.scope)['collections'][e.service.RESUMES][e.service._owner(e.ctx.actor)]
    assert stored['focus_preferences_version'] == 1
    assert stored['pending_task_refs'] == [{'authority': 'author_generation', 'id': 'original-ready'}, {'authority': 'media', 'id': 'original-running'}]
    encoded = json.dumps(stored)
    assert 'must not copy' not in encoded and pin['revision'] not in encoded and 'font_size' not in encoded
    restarted = WorkspaceToolsService(e.store, e.novels, e.chapters, focus_reader=e.service.focus_reader, task_readers=e.service.task_readers)
    target = restarted.resolve_resume(e.ctx, {'expected_version': first['version']})
    assert target['workspace']['layout']['search_query'] == '旧信'
    assert target['workspace']['layout']['show_failed_only'] is True
    assert target['workspace']['view'] == {'focus_active': True, 'references_visible': False}
    assert target['workspace']['focus_preferences']['font_size'] == 24
    assert authority.preferences(e.ctx)['version'] == 1
    assert e.rows[0]['version'] == 1


def test_changed_or_unreadable_original_reference_never_replays_old_cards(ux_env):
    e = ux_env
    authority, pin = focus(e)
    saved(e)
    e.rows[1]['content'] = 'changed source'; e.rows[1]['version'] += 1
    current = e.service.resume(e.ctx)['item']
    assert current['reference_recovery_required'] is True
    assert 'changed source' not in json.dumps(current)
    assert authority.pinned(e.ctx)['items'][0]['card'] is None
    authority.save_preferences(e.ctx, {'expected_version': 1, 'preferences': {'font_size': 16}, 'pins': []})
    target = e.service.resolve_resume(e.ctx, {'expected_version': 1})
    assert target['workspace']['focus_state'] == 'CHANGED'
    assert 'focus_preferences' not in target['workspace']
    assert authority.preferences(e.ctx)['pins'] == []
    assert authority.preferences(e.ctx)['preferences']['font_size'] == 16
    reset = e.service.reset_layout(e.ctx, 1)['item']
    assert reset['view'] == {'focus_active': False, 'references_visible': True}
    assert reset['stopping_note'] == '明天检查旧信'
    assert authority.preferences(e.ctx)['version'] == 2


def test_disabled_reference_authority_is_not_read_or_restored(ux_env):
    e = ux_env
    authority, pin = focus(e)
    saved(e)
    def forbidden_read(ctx):
        pytest.fail('disabled source was read')
    e.service.focus_reader = forbidden_read
    def disabled(flag):
        raise HTTPException(404, 'disabled')
    row = e.service.resume(e.ctx, disabled)['item']
    assert row['focus_state'] == 'UNAVAILABLE'
    target = e.service.resolve_resume(e.ctx, {'expected_version': 1}, disabled)
    assert 'focus_preferences' not in target['workspace']
    assert authority.preferences(e.ctx)['pins'] == [pin]


def test_pending_task_projection_rechecks_current_scope_and_permission(ux_env):
    e = ux_env
    rows = [{'id': 'private-original', 'novel_id': e.ctx.novel_id, 'status': 'FAILED'}]
    e.service.task_readers = (TaskReader('media', '媒体', 'assets', lambda ctx: rows),)
    saved(e)
    rows[0]['novel_id'] = 'foreign'
    row = e.service.resume(e.ctx)['item']
    assert row['pending_tasks'] == [] and row['tasks_recovery_required']
    assert 'private-original' not in json.dumps(row)
    def denied(ctx):
        raise HTTPException(403, 'revoked')
    e.service.task_readers = (TaskReader('media', '媒体', 'assets', denied),)
    assert 'private-original' not in json.dumps(e.service.resume(e.ctx))
    other = ReadContext(e.ctx.novel_id, e.ctx.scope, 'bob')
    assert e.service.resume(other)['item'] is None
    branch = ReadContext(e.ctx.novel_id, {**e.ctx.scope, 'branch_id': 'other'}, e.ctx.actor)
    assert e.service.resume(branch)['item'] is None


def test_pending_task_capture_is_bounded_and_does_not_store_body_or_execute(ux_env):
    e = ux_env
    e.service.task_readers = (TaskReader('jobs', '原任务', 'agents', lambda ctx: [
        {'id': str(i), 'novel_id': ctx.novel_id, 'status': 'RUNNING', 'prompt': 'secret'} for i in range(60)]),)
    first = saved(e)
    assert len(first['pending_tasks']) == 50 and first['tasks_capture_partial']
    assert 'secret' not in json.dumps(e.store.read(e.ctx.novel_id, e.ctx.scope))
    for _ in range(3):
        e.service.resolve_resume(e.ctx, {'expected_version': 1})
    assert e.service.resume(e.ctx)['item']['version'] == 1


def test_capture_rejects_source_or_authority_change_before_metadata_commit(ux_env):
    e = ux_env
    def change_source(ctx):
        e.rows[0]['version'] += 1
        return []
    e.service.task_readers = (TaskReader('jobs', '原任务', 'agents', change_source),)
    with pytest.raises(StaleSourceError):
        saved(e)
    assert e.service.resume(e.ctx)['item'] is None
    e.service.task_readers = ()
    def revoked():
        raise HTTPException(403, 'revoked')
    with pytest.raises(HTTPException):
        e.service.save_resume(e.ctx, {'stopping_note': 'not committed'}, reauthorize=revoked)
    assert e.service.resume(e.ctx)['item'] is None


def test_legacy_layout_upgrades_in_read_projection_only(ux_env):
    e = ux_env
    saved(e)
    with e.store.transaction(e.ctx.novel_id, e.ctx.scope) as doc:
        row = doc['collections'][e.service.RESUMES][e.service._owner(e.ctx.actor)]
        row['layout'] = {'density': 'advanced', 'section': 'resume', 'show_failed_only': True}
        row.pop('view'); row.pop('focus_preferences_version'); row.pop('pending_task_refs')
    before = copy.deepcopy(e.store.read(e.ctx.novel_id, e.ctx.scope))
    current = e.service.resume(e.ctx)['item']
    assert current['layout']['search_query'] == '' and current['layout']['show_failed_only'] is True
    assert current['view'] == {'focus_active': False, 'references_visible': True}
    assert e.store.read(e.ctx.novel_id, e.ctx.scope) == before
    e.service.reset_layout(e.ctx, 1)
    assert e.service.resume(e.ctx)['item']['layout'] == Layout().model_dump()


def test_read_rechecks_actor_after_original_authority_lookup(ux_env):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.experimental.ux_api import create_ux_router
    e = ux_env
    saved(e)
    current_actor = ['alice']
    def source(ctx):
        current_actor[0] = 'bob'
        return {'preferences': {'version': 0, 'preferences': {}, 'recovery_required': False}, 'pins': {'items': []}}
    e.service.focus_reader = source
    app = FastAPI()
    app.include_router(create_ux_router(e.service, lambda *args: (current_actor[0], e.ctx.scope), lambda flag: None))
    response = TestClient(app).get(f'/novels/{e.ctx.novel_id}/experimental/workspace/resume')
    assert response.status_code == 403
    assert '明天检查旧信' not in response.text


@pytest.mark.parametrize('action', ['save', 'reset'])
@pytest.mark.parametrize('revocation', ['flag', 'actor'])
def test_write_rechecks_current_authority_inside_transaction_before_any_metadata_change(ux_env, monkeypatch, action, revocation):
    from contextlib import contextmanager
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.experimental.ux_api import create_ux_router
    e = ux_env
    saved(e, layout={'search_query': 'preserve filter'}, view={'references_visible': False})
    before = copy.deepcopy(e.store.read(e.ctx.novel_id, e.ctx.scope))
    allowed, current_actor = [True], ['alice']
    original_transaction = e.store.transaction
    @contextmanager
    def change_after_preflight(*args):
        with original_transaction(*args) as doc:
            if revocation == 'flag':
                allowed[0] = False
            else:
                current_actor[0] = 'bob'
            yield doc
    monkeypatch.setattr(e.store, 'transaction', change_after_preflight)
    def require_flag(flag):
        if not allowed[0]:
            raise HTTPException(404, 'disabled')
    app = FastAPI()
    app.include_router(create_ux_router(e.service, lambda *args: (current_actor[0], e.ctx.scope), require_flag))
    client = TestClient(app)
    base = f'/novels/{e.ctx.novel_id}/experimental/workspace/resume'
    response = client.put(base, json={'expected_version': 1, 'stopping_note': 'must not save'}) if action == 'save' else client.post(base + '/reset-layout', json={'expected_version': 1})
    assert response.status_code == (404 if revocation == 'flag' else 403)
    assert e.store.read(e.ctx.novel_id, e.ctx.scope) == before
    assert e.rows[0]['version'] == 1
