"""Synthetic workspace-tools contracts, File and opt-in real PostgreSQL."""
import copy
import json
import os
import threading
import uuid
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.experimental.store import ExperimentalStore
from app.experimental.common import StaleSourceError
from app.experimental.ux import WorkspaceToolsService, ReadContext, TaskReader, MAX_CHARACTERS
from app.experimental.ux_api import create_ux_router
from app.services.v1_capability_service import CapabilityVersionConflict


@pytest.fixture(params=[pytest.param('file', marks=pytest.mark.file_backend_only), pytest.param('postgres', marks=pytest.mark.postgres_backend_only)])
def ux_env(tmp_path, request):
    backend = request.param
    url = os.getenv('TEST_POSTGRES_DATABASE_URL', '')
    if backend == 'postgres' and not url:
        pytest.skip('NOT_RUN: real PostgreSQL endpoint unavailable')
    nid = 'ux-' + uuid.uuid4().hex
    rows = [{'id': f'chapter-{n}', 'novel_id': nid, 'version': 1, 'title': f'第{n}章 风起', 'content': f'合成小说第{n}章，阿青来到石城。' * 5} for n in range(1, 13)]
    datasets = {'characters': [{'id': 'qing', 'name': '阿青', 'aliases': ['小青'], 'secret_text': '真实不可泄漏的角色秘密'}, {'id': 'hidden', 'name': '不可见人物', 'hidden': True}], 'locations': [{'id': 'stone', 'name': '石城'}], 'foreshadowing': [{'id': 'clue', 'title': '旧信'}]}
    novels = SimpleNamespace(get=lambda got: {'id': nid} if got == nid else (_ for _ in ()).throw(FileNotFoundError(got)), data_set=lambda got, name: copy.deepcopy(datasets[name]))
    chapters = SimpleNamespace(list=lambda got: copy.deepcopy(rows))
    store = ExperimentalStore(tmp_path, backend, url)
    service = WorkspaceToolsService(store, novels, chapters)
    ctx = ReadContext(nid, {'mode': 'local', 'novel_id': nid}, 'alice')
    env = SimpleNamespace(service=service, ctx=ctx, rows=rows, datasets=datasets, store=store, novels=novels, chapters=chapters, backend=backend, url=url, root=tmp_path)
    yield env
    if backend == 'postgres':
        with store._connect() as conn:
            conn.execute('DELETE FROM experimental_scope_documents WHERE novel_id = %s', (nid,))


def saved(e, **extra):
    return e.service.save_resume(e.ctx, {'chapter_id': 'chapter-1', 'chapter_version': 1, 'anchor': {'offset': 6, 'scroll': 123}, 'stopping_note': '明天检查旧信', **extra})['item']


def test_resume_restart_actor_scope_and_history(ux_env):
    e = ux_env
    first = saved(e)
    restarted = WorkspaceToolsService(ExperimentalStore(e.root, e.backend, e.url), e.novels, e.chapters)
    assert restarted.resume(e.ctx)['item']['stopping_note'] == '明天检查旧信'
    other = ReadContext(e.ctx.novel_id, e.ctx.scope, 'bob')
    assert restarted.resume(other)['item'] is None
    assert restarted.resume_history(other)['items'] == []
    second = saved(e, expected_version=first['version'], stopping_note='已处理')
    assert second['version'] == 2
    assert e.service.resume_history(e.ctx)['items'][0]['stopping_note'] == '明天检查旧信'
    target = e.service.resolve_resume(e.ctx, {'expected_version': 2})
    assert target['anchor'] == {'offset': 6, 'scroll': 123} and target['id'] == 'chapter-1'
    assert e.rows[0]['version'] == 1


def test_resume_cas_concurrency_and_stale_source(ux_env):
    e = ux_env
    saved(e)
    errors, successes = [], []
    barrier = threading.Barrier(2)
    def change(note):
        barrier.wait()
        try:
            successes.append(saved(e, expected_version=1, stopping_note=note))
        except CapabilityVersionConflict:
            errors.append('conflict')
    threads = [threading.Thread(target=change, args=(str(n),)) for n in range(2)]
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    assert len(successes) == len(errors) == 1
    e.rows[0]['version'] = 2
    assert e.service.resume(e.ctx)['availability'] == 'STALE'
    with pytest.raises(StaleSourceError):
        e.service.resolve_resume(e.ctx, {'expected_version': 2})
    target = e.service.resolve_resume(e.ctx, {'expected_version': 2, 'open_current': True})
    assert target['anchor'] == {'offset': 0, 'scroll': 0} and target['version'] == 2
    with pytest.raises(StaleSourceError): saved(e, expected_version=2)
    e.rows.pop(0)
    assert e.service.resume(e.ctx)['availability'] == 'UNAVAILABLE'
    with pytest.raises(FileNotFoundError): e.service.resolve_resume(e.ctx, {'expected_version': 2, 'open_current': True})


def test_resume_layout_reset_and_strict_fields(ux_env):
    e = ux_env
    first = saved(e)
    with e.store.transaction(e.ctx.novel_id, e.ctx.scope) as doc:
        next(iter(doc['collections'][e.service.RESUMES].values()))['layout'] = {'invalid': 'unsafe'}
    assert e.service.resume(e.ctx)['item']['layout_recovery_required'] is True
    reset = e.service.reset_layout(e.ctx, 1)['item']
    assert not reset['layout_recovery_required'] and reset['stopping_note'] == first['stopping_note']
    with pytest.raises(ValueError): saved(e, expected_version=2, layout={'token': 'fake'})
    with pytest.raises(ValueError): saved(e, expected_version=2, recent_commands=['delete-all'])
    with pytest.raises(ValueError): saved(e, expected_version=2, anchor={'offset': 999999, 'scroll': 0})
    with pytest.raises(FileNotFoundError): saved(e, expected_version=2, pinned_chapter_ids=['other-project'])


def test_search_chinese_alias_literal_index_update_delete_and_secret_safety(ux_env):
    e = ux_env
    first = e.service.search(e.ctx, '小青')
    assert [(x['id'], x['title']) for x in first['items']] == [('qing', '阿青')]
    assert '秘密' not in json.dumps(first, ensure_ascii=False)
    assert not e.service.search(e.ctx, '不可见')['items']
    assert not e.service.search(e.ctx, '.*')['items']
    assert e.service.search(e.ctx, '阿青')['updated_documents'] == 0
    old = e.service.search(e.ctx, '合成', chapter_id='chapter-1')['items'][0]
    e.rows[0]['content'] = '新版本测试'; e.rows[0]['version'] = 2
    result = e.service.search(e.ctx, '新版本')
    assert result['updated_documents'] == 1 and result['items'][0]['id'] == 'chapter-1'
    with pytest.raises(StaleSourceError): e.service.resolve(e.ctx, {k: old[k] for k in ('kind', 'id', 'revision', 'offset')})
    e.rows.pop(0)
    with pytest.raises(FileNotFoundError): e.service.resolve(e.ctx, {'kind': 'chapter', 'id': old['id'], 'revision': old['revision'], 'open_current': True})
    assert not e.service.search(e.ctx, '新版本')['items']


def test_search_branch_fail_closed_and_actor_cache_isolation(ux_env):
    e = ux_env
    branch = ReadContext(e.ctx.novel_id, {'mode': 'collaboration', 'novel_id': e.ctx.novel_id, 'workspace_id': 'w', 'storyline_id': 's', 'branch_id': 'b'}, 'alice')
    result = e.service.search(branch, '阿青')
    assert result['items'] == [] and result['branch_sources_available'] is False
    assert e.service.resume(branch)['item'] is None
    with pytest.raises(FileNotFoundError): e.service.save_resume(branch, {'chapter_id': 'chapter-1', 'chapter_version': 1})
    e.service.entity_readers = {'character': lambda ctx: []}
    assert not e.service.search(e.ctx, '小青')['items']
    assert all('secret' not in json.dumps(row) for index in e.service._indexes.values() for row in index.values())


def test_search_bounded_million_character_index_and_safe_rebuild(ux_env):
    e = ux_env
    e.rows[0]['content'] = '汉' * 1_000_000
    first = e.service.search(e.ctx, '汉', kind='chapter')
    assert len(first['items']) == 1 and len(first['items'][0]['snippet']) <= 160
    assert e.service.search(e.ctx, '汉')['updated_documents'] == 0
    e.rows[1]['content'] = '字' * MAX_CHARACTERS
    assert e.service.search(e.ctx, '字')['truncated'] is True
    assert e.service.search(e.ctx, '汉', rebuild=True)['items'][0]['id'] == 'chapter-1'


def test_task_authorities_projection_partial_failure_and_unknown_cost(ux_env):
    e = ux_env
    tasks = [{'id': 'job-1', 'novel_id': e.ctx.novel_id, 'status': 'RUNNING', 'recoverable': True, 'prompt': 'must-not-leak', 'api_key': 'secret', 'cost': 999}, {'id': 'foreign', 'novel_id': 'elsewhere', 'status': 'FAILED'}]
    def denied(ctx): raise HTTPException(403, 'private')
    def broken(ctx): raise ValueError('postgresql://synthetic-secret')
    e.service.task_readers = (TaskReader('media', '图片', 'assets', lambda ctx: tasks), TaskReader('denied', '不可见', 'assets', denied), TaskReader('export', '导出', 'exports', broken))
    result = e.service.tasks(e.ctx, lambda flag: None)
    assert [x['id'] for x in result['items']] == ['job-1']
    task = result['items'][0]
    assert task['status'] == 'UNKNOWN' and task['progress'] is None
    assert task['cost'] == {'estimate': None, 'actual': None, 'state': 'UNKNOWN'}
    assert task['actions'] == ['open_source']
    assert result['unavailable'] == [{'authority': 'export', 'label': '导出', 'reason': 'SOURCE_UNAVAILABLE'}]
    assert 'secret' not in json.dumps(result) and 'prompt' not in json.dumps(result)
    assert len(e.service.tasks(e.ctx, lambda flag: None, failed_only=True)['items']) == 1


def test_diagnostics_allowlist_rejects_synthetic_credential_codes_paths_and_prompts(ux_env):
    e = ux_env
    poisons = ['sk-SYNTHETIC-KEY', '/home/private/story.txt', 'C:\\Users\\Author\\story.docx', 'postgresql://user:pass@local/db', 'cookie=SESSION_SECRET', 'PROMPT_ORIGINAL', 'SECRET_KEY_USING_ONLY_UPPERCASE']
    rows = [{'id': poison, 'novel_id': e.ctx.novel_id, 'title': poison, 'prompt': poison, 'status': poison, 'error_code': poison, 'history': [{'status': poison}]} for poison in poisons]
    e.service.task_readers = (TaskReader('agent', '文本', 'agents', lambda ctx: rows),)
    result = e.service.diagnostics(e.ctx, {}, lambda flag: None)
    serialized = json.dumps(result, ensure_ascii=False)
    assert all(poison not in serialized for poison in poisons)
    assert result['sections']['error_codes'] == ['UNCLASSIFIED']
    assert e.service.diagnostics(e.ctx, {'include_environment': False, 'include_task_states': False, 'include_error_codes': False}, lambda flag: None)['sections'] == {}


def test_mounted_router_flags_authority_cas_history_diagnosis(ux_env):
    e = ux_env
    state = {'enabled': True, 'allowed': True}; calls = []
    def gate(flag):
        assert flag == 'workspace_tools_v2'
        if not state['enabled']: raise HTTPException(404)
    def authorize(nid, token, branch, permission):
        calls.append((token, branch, permission))
        if not state['allowed']: raise HTTPException(403)
        return token or 'alice', e.ctx.scope
    app = FastAPI(); app.include_router(create_ux_router(e.service, authorize, gate))
    client = TestClient(app); base = f'/novels/{e.ctx.novel_id}/experimental/workspace'
    response = client.put(base + '/resume', json={'chapter_id': 'chapter-1', 'chapter_version': 1})
    assert response.status_code == 200 and response.json()['item']['version'] == 1
    assert calls[-1][-1] == 'domain.write'
    assert client.put(base + '/resume', json={'expected_version': 0}).status_code == 409
    assert client.get(base + '/resume', headers={'X-Session-Token': 'bob'}).json()['item'] is None
    assert client.get(base + '/search?q=阿青').status_code == 200
    assert client.post(base + '/resume/resolve', json={'expected_version': 1}).status_code == 200
    assert client.get(base + '/resume/history').status_code == 200
    preview = client.post(base + '/diagnostics/preview', json={}).json()
    assert client.post(base + '/diagnostics/export', json={'preview_digest': preview['preview_digest']}).headers['content-disposition'].endswith('"workspace-diagnostics.json"')
    assert client.post(base + '/diagnostics/preview', json={'prompt': 'must-not-enter'}).status_code == 422
    state['allowed'] = False
    assert client.get(base + '/search?q=阿青').status_code == 403
    state['enabled'] = False
    assert client.get(base + '/resume').status_code == 404
    assert client.post(base + '/search/rebuild').status_code == 404
    assert client.post(base + '/diagnostics/preview', json={}).status_code == 404


def test_editor_document_coordinates_not_markdown_or_utf16(ux_env):
    e = ux_env
    e.rows[0]['content'] = '# Markdown projection should never decide editor anchors'
    e.rows[0]['document'] = {'type': 'doc', 'content': [
        {'type': 'heading', 'content': [{'type': 'text', 'text': '序章😀'}]},
        {'type': 'bulletList', 'content': [{'type': 'listItem', 'content': [
            {'type': 'paragraph', 'content': [{'type': 'text', 'text': 'Straße阿青'}]}]}]},
    ]}
    item = e.service.search(e.ctx, '阿青', chapter_id='chapter-1')['items'][0]
    assert item['offset'] == len('序章😀\nStraße')
    assert item['coordinate'] == 'EDITOR_TEXT_CODEPOINT'
    assert 'Markdown' not in item['snippet']
    saved(e, anchor={'offset': item['offset'], 'scroll': 0})
    result = e.service.resolve_resume(e.ctx, {'expected_version': 1})
    assert result['coordinate'] == 'EDITOR_TEXT_CODEPOINT' and result['anchor']['offset'] == item['offset']


def test_diagnostic_export_requires_unchanged_preview(ux_env):
    e = ux_env
    tasks = [{'id': 'job', 'novel_id': e.ctx.novel_id, 'status': 'RUNNING'}]
    e.service.task_readers = (TaskReader('agent', '文本', 'agents', lambda ctx: tasks),)
    preview = e.service.diagnostics(e.ctx, {}, lambda flag: None)
    assert e.service.export_diagnostics(e.ctx, {'preview_digest': preview['preview_digest']}, lambda flag: None) == preview
    tasks[0]['status'] = 'FAILED'
    with pytest.raises(StaleSourceError):
        e.service.export_diagnostics(e.ctx, {'preview_digest': preview['preview_digest']}, lambda flag: None)
    with pytest.raises(ValueError):
        e.service.export_diagnostics(e.ctx, {}, lambda flag: None)

def test_AUDIT_authorized_collaboration_exports_are_projected(ux_env):
    from app.services.export_job_service import ExportJobService
    e = ux_env
    ctx = ReadContext(e.ctx.novel_id, {'mode': 'collaboration', 'novel_id': e.ctx.novel_id, 'workspace_id': 'w', 'storyline_id': 's', 'branch_id': 'b'}, 'alice')
    row = ExportJobService.public({'id': 'authorized-export', 'novel_id': e.ctx.novel_id, 'status': 'failed', 'permission_context': {**ctx.scope, 'actor_id': 'alice'}})
    e.service.task_readers = (TaskReader('exports', '导出任务', 'exports', lambda _: {'items': [row], 'next_offset': None}),)
    assert [item['id'] for item in e.service.tasks(ctx, lambda _: None)['items']] == ['authorized-export']

def test_AUDIT_real_export_pagination_is_not_reported_complete(ux_env):
    e = ux_env
    row = {'id': 'export', 'novel_id': e.ctx.novel_id, 'status': 'queued', 'permission_context': e.ctx.scope}
    e.service.task_readers = (TaskReader('exports', '导出任务', 'exports', lambda _: {'items': [row], 'next_offset': 100}),)
    assert e.service.tasks(e.ctx, lambda _: None)['truncated'] is True


def test_exports_recognized_envelope_rejects_cross_actor_branch_and_project(ux_env):
    from app.services.export_job_service import ExportJobService
    e = ux_env
    scope = {'mode': 'collaboration', 'novel_id': e.ctx.novel_id, 'workspace_id': 'w', 'storyline_id': 's', 'branch_id': 'b'}
    ctx = ReadContext(e.ctx.novel_id, scope, 'alice')
    valid = {**scope, 'actor_id': 'alice', 'permission': 'domain.read'}
    rows = [ExportJobService.public({'id': 'own', 'novel_id': e.ctx.novel_id, 'status': 'failed', 'permission_context': valid})]
    for key, value in [('actor_id', 'bob'), ('branch_id', 'other'), ('storyline_id', 'other'), ('workspace_id', 'other'), ('novel_id', 'other'), ('mode', 'local')]:
        rows.append(ExportJobService.public({'id': 'denied-' + key, 'novel_id': e.ctx.novel_id, 'status': 'failed', 'permission_context': {**valid, key: value}}))
    rows.append({'id': 'top-level-spoof', 'novel_id': e.ctx.novel_id, 'status': 'failed', 'branch_id': 'b'})
    e.service.task_readers = (TaskReader('exports', '导出任务', 'exports', lambda _: {'items': rows, 'next_offset': 100}),)
    result = e.service.tasks(ctx, lambda _: None)
    assert [task['id'] for task in result['items']] == ['own']
    assert result['truncated'] is True
    denied = ReadContext(e.ctx.novel_id, scope, 'mallory')
    result = e.service.tasks(denied, lambda _: None)
    assert result['items'] == [] and result['truncated'] is False
    assert 'permission_context' not in json.dumps(result)
    # Other authorities cannot borrow an export envelope to bypass branch scope.
    e.service.task_readers = (TaskReader('agents', '文本任务', 'agents', lambda _: {'items': rows[:1]}),)
    assert e.service.tasks(ctx, lambda _: None)['items'] == []


def test_local_export_scope_never_imports_collaboration_owner(ux_env):
    e = ux_env
    rows = [
        {'id': 'local', 'novel_id': e.ctx.novel_id, 'status': 'queued', 'permission_context': e.ctx.scope},
        {'id': 'foreign-actor', 'novel_id': e.ctx.novel_id, 'status': 'queued', 'permission_context': {**e.ctx.scope, 'actor_id': 'bob'}},
        {'id': 'foreign-branch', 'novel_id': e.ctx.novel_id, 'status': 'queued', 'permission_context': {**e.ctx.scope, 'branch_id': 'b'}},
    ]
    e.service.task_readers = (TaskReader('exports', '导出任务', 'exports', lambda _: {'items': rows, 'next_offset': None}),)
    result = e.service.tasks(e.ctx, lambda _: None)
    assert [task['id'] for task in result['items']] == ['local']
    assert result['truncated'] is False
