"""Original JobManager U07 projection, mounted File/opt-in real PG contracts."""
import json

import pytest

from app.jobs import Job, mark_generation_origin
from app.experimental.author_task_projection import MAX_AUTHOR_TASKS
from test_r3_mounted_contracts import mounted, prefix, scoped, checked


@pytest.fixture
def author_tasks(mounted, monkeypatch):
    e = mounted
    monkeypatch.setattr(e.api.jobs, 'jobs', {})
    monkeypatch.setattr(e.api.jobs, 'chapters', e.chapters)
    return e


def add(e, jid='original-author', **changes):
    job = Job(jid, 'continue', e.nid, e.chapter['id'], 'PRIVATE PROMPT', 'LOCAL_ONLY',
              source='PRIVATE SOURCE', output='PRIVATE OUTPUT', status='COMPLETED',
              base_chapter_version=e.chapter['version'], error='PRIVATE ERROR', **changes)
    if e.scope.get('mode') == 'collaboration':
        job.actor_id, job.workspace_id = e.lead, e.workspace
        job.scope = {'kind': 'BRANCH', 'workspace_id': e.workspace, 'project_id': e.nid,
                     'storyline_id': e.storyline, 'branch_id': e.branch}
    e.api.jobs.jobs[jid] = job
    return job


def read(e, headers=None):
    result = checked(e.client.get(e.base + '/workspace/tasks', headers=headers or {}))
    return result, [row for row in result['items'] if row['authority'] == 'author_generation']


def test_original_job_source_is_safe_and_no_execution_or_history_store(author_tasks, monkeypatch):
    e = author_tasks
    job = add(e)
    job.error_code = 'PRIVATE_TOKEN_ERROR'
    monkeypatch.setattr(e.api.jobs, 'create', lambda *a, **kw: pytest.fail('projection created a job'))
    monkeypatch.setattr(e.api.jobs, '_persist', lambda *a, **kw: pytest.fail('projection persisted a job'))
    result, rows = read(e)
    assert len(rows) == 1 and rows[0]['status'] == 'COMPLETED'
    assert rows[0]['source'] == {'kind': 'generation', 'id': job.id, 'chapter_id': job.chapter_id, 'version': job.base_chapter_version}
    assert 'PRIVATE' not in json.dumps(result)
    assert rows[0]['error_code'] == 'UNCLASSIFIED'
    assert rows[0]['progress'] is None and rows[0]['history'] == [] and not rows[0]['stale']
    original = checked(e.client.get(e.prefix + '/generation/' + job.id))
    assert original['output'] == 'PRIVATE OUTPUT' and original['base_chapter_version'] == job.base_chapter_version
    assert job.status == 'COMPLETED' and len(e.api.jobs.jobs) == 1
    e.chapters.save(job.chapter_id, {'version': job.base_chapter_version, 'content': 'Changed saved draft'})
    assert read(e)[1][0]['stale'] is True


def test_foreign_missing_and_archived_sources_are_not_counted(author_tasks):
    e = author_tasks
    foreign = add(e, 'foreign'); foreign.novel_id = 'other-private-project'
    missing = add(e, 'missing'); missing.chapter_id = 'nonexistent-private-chapter'
    scoped_job = add(e, 'scoped'); scoped_job.actor_id = 'other-author'; scoped_job.scope = {'branch_id': 'private-branch'}
    no_version = add(e, 'no-source-version'); no_version.base_chapter_version = None
    corrupt_origin = add(e, 'corrupt-origin'); corrupt_origin.experimental_origin = 'unknown-origin'
    archived_chapter = e.chapters.create(e.nid, {'title': 'Archived source', 'content': 'PRIVATE ARCHIVED SOURCE'})
    archived_chapter = e.chapters.get(archived_chapter['id'])
    e.chapters.archive(archived_chapter['id'], archived_chapter['version'])
    archived = add(e, 'archived'); archived.chapter_id = archived_chapter['id']
    result, rows = read(e)
    assert rows == [] and not result['truncated']
    assert not any(secret in json.dumps(result) for secret in ('other-private-project', 'private-branch', 'nonexistent-private-chapter'))


def test_origin_flags_off_v1_and_settlement_remain_authoritative(author_tasks, monkeypatch):
    e = author_tasks
    job = add(e)
    mark_generation_origin(job, 'model_broker')
    job.dispatch_hooks_required = True
    assert read(e)[1][0]['status'] == 'SETTLING'
    assert read(e)[1][0]['stage_label'] == '结算确认中'
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'workspace_tools_v2')
    assert read(e)[1] == []
    assert e.client.get(e.prefix + '/generation/' + job.id).status_code == 404
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    assert e.client.get(e.base + '/workspace/tasks').status_code == 404


def test_current_original_actor_branch_and_revocation(author_tasks, monkeypatch):
    e = scoped(author_tasks, monkeypatch)
    job = add(e)
    wrong_actor = add(e, 'wrong-actor'); wrong_actor.actor_id = e.viewer
    wrong_branch = add(e, 'wrong-branch'); wrong_branch.scope = {**job.scope, 'branch_id': e.other_branch}
    wrong_storyline = add(e, 'wrong-storyline'); wrong_storyline.scope = {**job.scope, 'storyline_id': 'other'}
    wrong_workspace = add(e, 'wrong-workspace'); wrong_workspace.scope = {**job.scope, 'workspace_id': 'other'}
    wrong_project = add(e, 'wrong-project'); wrong_project.scope = {**job.scope, 'project_id': 'other'}
    assert [row['id'] for row in read(e, e.headers)[1]] == [job.id]
    assert [row['id'] for row in read(e, e.viewer_headers)[1]] == ['wrong-actor']
    assert e.client.get(e.prefix + '/generation/' + job.id, headers=e.viewer_headers).status_code == 403
    e.authorization.revoke_role(e.role, e.lead)
    assert e.client.get(e.base + '/workspace/tasks', headers=e.headers).status_code == 403
    assert e.client.get(e.prefix + '/generation/' + job.id, headers=e.headers).status_code == 403


def test_authority_revoked_during_projection_returns_no_rows(author_tasks, monkeypatch):
    e = scoped(author_tasks, monkeypatch)
    add(e)
    original = e.api.generation
    def revoke(*args, **kwargs):
        value = original(*args, **kwargs)
        e.authorization.revoke_role(e.role, e.lead)
        return value
    monkeypatch.setattr(e.api, 'generation', revoke)
    result = e.client.get(e.base + '/workspace/tasks', headers=e.headers)
    assert 'original-author' not in result.text and 'PRIVATE' not in result.text
    assert result.status_code in {200, 403}


def test_origin_disabled_during_original_read_returns_no_rows(author_tasks, monkeypatch):
    e = author_tasks
    job = add(e)
    mark_generation_origin(job, 'model_broker')
    original = e.api.generation
    def disable(*args, **kwargs):
        value = original(*args, **kwargs)
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'workspace_tools_v2')
        return value
    monkeypatch.setattr(e.api, 'generation', disable)
    result, rows = read(e)
    assert rows == [] and not result['truncated']


def test_only_authorized_visible_extra_row_sets_has_more(author_tasks):
    e = author_tasks
    for index in range(MAX_AUTHOR_TASKS):
        add(e, f'author-{index}')
    hidden = add(e, 'last-private'); hidden.novel_id = 'another-project'
    result, rows = read(e)
    assert len(rows) == MAX_AUTHOR_TASKS and not result['truncated']
    add(e, 'visible-extra')
    result, rows = read(e)
    assert len(rows) == MAX_AUTHOR_TASKS and result['truncated']
    assert rows[0]['id'] == 'visible-extra'


def test_projection_is_bounded_without_disclosing_hidden_window_size(monkeypatch):
    import threading
    from types import SimpleNamespace
    from app.experimental.author_task_projection import create_author_task_reader, MAX_AUTHOR_TASK_SCAN
    from app.experimental.ux import ReadContext
    ctx = ReadContext('local-project', {'mode': 'local', 'novel_id': 'local-project'}, 'local-author')
    jobs = {str(i): Job(str(i), 'continue', 'foreign-project', 'private-chapter', '', 'LOCAL_ONLY')
            for i in range(MAX_AUTHOR_TASK_SCAN + 20)}
    reads = []
    def get(jid):
        reads.append(jid)
        return jobs[jid]
    manager = SimpleNamespace(lock=threading.Lock(), jobs=jobs, get=get,
                              chapters=SimpleNamespace(get=lambda _: pytest.fail('read a foreign chapter')))
    reader = create_author_task_reader(manager, lambda *args: (ctx.actor, ctx.scope), lambda _: None,
                                      lambda *args: pytest.fail('read a foreign generation'))
    assert reader(ctx) == {'items': [], 'has_more': False}
    assert len(reads) == MAX_AUTHOR_TASK_SCAN


def test_factory_rechecks_captured_identity_and_feature_before_any_scan():
    from types import SimpleNamespace
    from fastapi import HTTPException
    from app.experimental.author_task_projection import create_author_task_reader
    from app.experimental.ux import ReadContext
    ctx = ReadContext('local-project', {'mode': 'local', 'novel_id': 'local-project'}, 'local-author')
    manager = SimpleNamespace()  # Any manager access would fail the test.
    with pytest.raises(HTTPException) as changed:
        create_author_task_reader(manager, lambda *args: ('other', ctx.scope), lambda _: None, None)(ctx)
    assert changed.value.status_code == 403
    def off(_):
        raise HTTPException(404)
    with pytest.raises(HTTPException) as disabled:
        create_author_task_reader(manager, lambda *args: pytest.fail('authorized while off'), off, None)(ctx)
    assert disabled.value.status_code == 404
