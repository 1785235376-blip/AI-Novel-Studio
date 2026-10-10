"""Branch jobs use the original live HTTP/SSE transport and durable job owner."""
from types import SimpleNamespace

import pytest

from app.authorization import AuthorizationScope, ScopeKind
from app.experimental.flags import RUNTIME_FLAGS
from app.identity import IdentityStatus
from app.jobs import JobManager
from app.services.generation_service import GenerationService
from test_surface_branch_manuscript_mounted import branch_env, create
from test_r3_mounted_contracts import mounted, prefix
from test_shared_generation_stream_authority import wire, BEFORE, AFTER


def retained_mainline_job(e, manager):
    from uuid import uuid4
    from app.jobs import Job
    actor = e.sessions.resolve(e.lead)
    job = Job(str(uuid4()), 'polish', e.nid, e.chapter['id'], '', 'LOCAL_ONLY',
              status='FAILED', output='RETAINED_MAINLINE_OUTPUT_MUST_NOT_DISCLOSE',
              base_chapter_version=e.chapter['version'], actor_id=actor.actor_id, session_id=actor.session_id,
              client_id=actor.client_id, workspace_id=e.workspace, scope_type='BRANCH', scope_id=e.branch,
              scope={'kind': 'BRANCH', 'workspace_id': e.workspace, 'project_id': e.nid,
                     'storyline_id': e.storyline, 'branch_id': e.branch})
    manager.jobs[job.id] = job; manager._persist(job)
    return job


@pytest.fixture
def stream_app(branch_env, monkeypatch):
    e = branch_env; e.branch_chapter = create(e); e.observers = []
    manager = JobManager(generations=GenerationService(e.bundle.generations), chapters=e.chapters,
                         contexts=SimpleNamespace(), canon=e.canon, snapshot_required=True, collaboration_updates=e.application)
    monkeypatch.setattr(e.api, 'jobs', manager); e.manager = manager
    e.headers = {'X-Session-Token': e.lead, 'X-Branch-ID': e.branch}
    def prepare():
        scope = AuthorizationScope(ScopeKind.BRANCH, e.workspace, e.nid, e.storyline, e.branch)
        job = manager.prepare_job('polish', {'novel_id': e.nid, 'chapter_id': e.branch_chapter['id'], 'profile': 'LOCAL_ONLY'},
                                  actor=e.sessions.resolve(e.lead), scope=scope)
        job.status = 'GENERATING'; job.output = BEFORE; manager.jobs[job.id] = job; manager._persist(job)
        return job
    e.prepare = prepare
    return e


@pytest.mark.parametrize('change', ['membership', 'session', 'feature', 'archive', 'deleted'])
def test_branch_live_stream_closes_before_revoked_tail_and_does_not_cancel_owner(wire, monkeypatch, change):
    e = wire; job = e.prepare(); observer = e.subscribe(job)
    assert observer.next_event()['chunk'] == BEFORE
    if change == 'membership': e.identity.set_membership_status(e.lead, e.workspace, IdentityStatus.INACTIVE)
    elif change == 'session': e.sessions.revoke(e.lead)
    elif change == 'feature': monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(flag for flag in RUNTIME_FLAGS if flag != 'branch_manuscript_v1'))
    else:
        archived = e.owner.archive(e.ctx, e.branch_chapter['id'], True, 1)
        if change == 'deleted': e.owner.delete(e.ctx, e.branch_chapter['id'], archived['version'])
    with job.condition:
        job.output += AFTER; job.condition.notify_all()
    observer.assert_clean_close()
    assert AFTER.encode() not in observer.raw and job.status == 'GENERATING' and not job.cancelled.is_set()
    assert e.chapters.get(e.chapter['id']) == e.chapter


def test_branch_cancel_retry_guard_restart_recovery_and_task_source_projection(branch_env, monkeypatch):
    from app.experimental.author_task_projection import create_author_task_reader
    from app.experimental.flags import require_flag
    e = branch_env; chapter = create(e)
    manager = JobManager(generations=GenerationService(e.bundle.generations), chapters=e.chapters,
                         contexts=SimpleNamespace(), canon=e.canon, snapshot_required=True, collaboration_updates=e.application)
    monkeypatch.setattr(e.api, 'jobs', manager)
    scope = AuthorizationScope(ScopeKind.BRANCH, e.workspace, e.nid, e.storyline, e.branch)
    job = manager.prepare_job('polish', {'novel_id': e.nid, 'chapter_id': chapter['id'], 'profile': 'LOCAL_ONLY'},
                              actor=e.sessions.resolve(e.lead), scope=scope)
    job.status = 'GENERATING'; manager.jobs[job.id] = job; manager._persist(job)
    tasks = create_author_task_reader(manager, e.api._workbench_authorize, require_flag, e.api.generation)
    assert tasks(e.ctx)['items'][0]['chapter_id'] == chapter['id']
    cancelled = e.client.post(e.prefix + f'/generation/{job.id}/cancel', headers=e.headers)
    assert cancelled.status_code == 200 and manager.get(job.id).status == 'CANCELLED'
    assert e.client.post(e.prefix + f'/generation/{job.id}/retry', headers=e.headers).status_code == 409
    assert e.client.post(e.prefix + f'/generation/{job.id}/reject', headers=e.headers).status_code == 409
    assert e.client.post(e.prefix + f'/generation/{job.id}/accept', headers=e.headers, json={'expected_version': 1}).status_code == 400
    # Simulate a distinct admitted job interrupted by process restart. The
    # original owner changes it durably to FAILED, never restarts the model.
    interrupted = manager.prepare_job('polish', {'novel_id': e.nid, 'chapter_id': chapter['id'], 'profile': 'LOCAL_ONLY'},
                                      actor=e.sessions.resolve(e.lead), scope=scope)
    interrupted.status = 'GENERATING'; manager._persist(interrupted)
    restarted = JobManager(generations=GenerationService(e.bundle.generations), chapters=e.chapters,
                           contexts=SimpleNamespace(), canon=e.canon, snapshot_required=True, collaboration_updates=e.application)
    assert restarted.get(interrupted.id).status == 'FAILED'
    assert restarted.persistence.get(interrupted.id)['status'] == 'FAILED'
    assert restarted.get(job.id).status == 'CANCELLED' and e.owner.read(e.ctx, chapter['id'])['version'] == 1


@pytest.mark.parametrize('change', ['legacy_unmarked', 'missing', 'session_revoked', 'role_revoked'])
def test_branch_retry_is_never_legacy_replay_and_checks_current_authority(branch_env, monkeypatch, change):
    e = branch_env; chapter = create(e)
    manager = JobManager(generations=GenerationService(e.bundle.generations), chapters=e.chapters,
                         contexts=SimpleNamespace(), canon=e.canon, snapshot_required=True, collaboration_updates=e.application)
    monkeypatch.setattr(e.api, 'jobs', manager)
    scope = AuthorizationScope(ScopeKind.BRANCH, e.workspace, e.nid, e.storyline, e.branch)
    job = manager.prepare_job('polish', {'novel_id': e.nid, 'chapter_id': chapter['id'], 'profile': 'LOCAL_ONLY'},
                              actor=e.sessions.resolve(e.lead), scope=scope)
    job.status = 'FAILED'; job.experimental_origin = None; job.required_experimental_features = []
    manager.jobs[job.id] = job; manager._persist(job)
    if change == 'missing':
        archived = e.owner.archive(e.ctx, chapter['id'], True, 1)
        e.owner.delete(e.ctx, chapter['id'], archived['version'])
    elif change == 'session_revoked': e.sessions.revoke(e.lead)
    elif change == 'role_revoked': e.authorization.revoke_role(e.role, e.lead)
    calls = []
    monkeypatch.setattr(manager, 'create', lambda *args, **kwargs: calls.append('DISPATCH_NOT_ALLOWED'))
    response = e.client.post(e.prefix + f'/generation/{job.id}/retry', headers=e.headers)
    assert response.status_code == {'legacy_unmarked': 409, 'missing': 403, 'session_revoked': 401, 'role_revoked': 403}[change]
    if change == 'legacy_unmarked': assert response.json()['detail']['code'] == 'AUTHOR_PREVIEW_REQUIRED'
    assert not calls and len(manager.jobs) == 1


def test_branch_deleted_source_retains_terminal_recovery_but_cannot_admit_or_expose_jobs(branch_env, monkeypatch):
    from app.experimental.author_task_projection import create_author_task_reader
    from app.experimental.flags import require_flag
    e = branch_env; chapter = create(e)
    manager = JobManager(generations=GenerationService(e.bundle.generations), chapters=e.chapters,
                         contexts=SimpleNamespace(), canon=e.canon, snapshot_required=True, collaboration_updates=e.application)
    scope = AuthorizationScope(ScopeKind.BRANCH, e.workspace, e.nid, e.storyline, e.branch)
    payload = {'novel_id': e.nid, 'chapter_id': chapter['id'], 'profile': 'LOCAL_ONLY'}
    actor = e.sessions.resolve(e.lead)
    job = manager.prepare_job('polish', payload, actor=actor, scope=scope)
    job.status = 'GENERATING'; job.output = 'Retained synthetic draft'; manager._persist(job)
    archived = e.owner.archive(e.ctx, chapter['id'], True, 1)
    e.owner.delete(e.ctx, chapter['id'], archived['version'])
    restarted = JobManager(generations=GenerationService(e.bundle.generations), chapters=e.chapters,
                           contexts=SimpleNamespace(), canon=e.canon, snapshot_required=True, collaboration_updates=e.application)
    assert restarted.get(job.id).status == 'FAILED' and restarted.persistence.get(job.id)['status'] == 'FAILED'
    assert restarted.get(job.id).output == 'Retained synthetic draft'
    with pytest.raises(FileNotFoundError): restarted.prepare_job('polish', payload, actor=actor, scope=scope)
    monkeypatch.setattr(e.api, 'jobs', restarted)
    assert e.client.get(e.prefix + f'/generation/{job.id}', headers=e.headers).status_code == 403
    tasks = create_author_task_reader(restarted, e.api._workbench_authorize, require_flag, e.api.generation)
    assert tasks(e.ctx)['items'] == []
    assert e.client.post(e.prefix + f'/generation/{job.id}/retry', headers=e.headers).status_code == 403
    assert e.chapters.get(e.chapter['id']) == e.chapter


@pytest.mark.parametrize('change', ['session', 'role', 'feature', 'source', 'missing_hook'])
def test_branch_provider_dispatch_requires_live_session_and_source(branch_env, monkeypatch, change):
    from fastapi import HTTPException
    from app.model_runtime import ModelRuntimeError
    import app.dependencies as dependencies
    import app.jobs as jobs_module
    e = branch_env; chapter = create(e); dispatched = []
    monkeypatch.setattr(dependencies, 'membership_authorization_service', e.membership)
    monkeypatch.setattr(jobs_module, 'runtime', SimpleNamespace(is_remote_text_provider=lambda _: False))
    manager = JobManager(generations=GenerationService(e.bundle.generations), chapters=e.chapters,
                         contexts=SimpleNamespace(), canon=e.canon, snapshot_required=True, collaboration_updates=e.application)
    scope = AuthorizationScope(ScopeKind.BRANCH, e.workspace, e.nid, e.storyline, e.branch)
    actor = e.sessions.resolve(e.lead)
    body = e.api.GenerateIn(novel_id=e.nid, chapter_id=chapter['id'], profile='LOCAL_ONLY')
    hook = e.api._registered_branch_generation_authorization(body, e.lead, e.branch, actor, scope)
    job = manager.prepare_job('polish', body.model_dump(), actor=actor, scope=scope, **hook)
    job.before_dispatch = lambda: dispatched.append('DISPATCHED')
    route = SimpleNamespace(provider='synthetic', model='synthetic')
    manager._guard_author_request(job, route)  # Current source/session is valid.
    if change == 'session': e.sessions.revoke(e.lead)
    elif change == 'role': e.authorization.revoke_role(e.role, e.lead)
    elif change == 'feature': monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    elif change == 'source': e.owner.archive(e.ctx, chapter['id'], True, 1)
    else: job.request_authorization = None
    with pytest.raises((HTTPException, PermissionError, ModelRuntimeError)):
        manager._guard_author_request(job, route, dispatch=True)
    assert not dispatched and e.chapters.get(e.chapter['id']) == e.chapter


def test_retained_mainline_id_never_discloses_branch_job_over_read_sse_or_retry(wire):
    import http.client
    from copy import deepcopy
    e = wire; job = retained_mainline_job(e, e.manager)
    before = deepcopy(e.manager.persistence.get(job.id))
    assert job.experimental_origin is None and job.required_experimental_features == []
    for method, suffix in [('GET', ''), ('GET', '/events'), ('POST', '/retry')]:
        connection = http.client.HTTPConnection('127.0.0.1', e.port, timeout=5)
        try:
            connection.request(method, e.prefix + f'/generation/{job.id}' + suffix, headers=e.headers)
            response = connection.getresponse(); body = response.read()
            assert response.status == 403 and job.output.encode() not in body
            assert not response.getheader('Content-Type', '').startswith('text/event-stream')
        finally: connection.close()
    assert e.manager.persistence.get(job.id) == before and e.chapters.get(e.chapter['id']) == e.chapter


def test_unregistered_legacy_generation_adapter_retains_its_read_contract(branch_env, monkeypatch):
    e = branch_env
    monkeypatch.delattr(e.chapters, 'branch_authority')
    manager = JobManager(generations=GenerationService(e.bundle.generations), chapters=e.chapters,
                         contexts=SimpleNamespace(), canon=e.canon, snapshot_required=True, collaboration_updates=e.application)
    monkeypatch.setattr(e.api, 'jobs', manager)
    job = retained_mainline_job(e, manager)
    response = e.client.get(e.prefix + f'/generation/{job.id}', headers=e.headers)
    assert response.status_code == 200 and response.json()['output'] == job.output


def test_branch_identity_classification_is_project_bound_and_canonical():
    from app.repositories.branch_manuscript import is_branch_chapter_id
    token = '01234567-89ab-cdef-0123-456789abcdef'
    for nid in ('project', 'legacy:~b-component', 'legacy:~b' + token):
        assert is_branch_chapter_id(nid, nid + ':~b' + token)
        for cid in (nid + ':1', nid + ':~' + token, nid + ':~b' + token.upper(),
                    nid + ':~b' + token + ':v1', nid + ':~bmalformed', 'foreign:~b' + token):
            assert not is_branch_chapter_id(nid, cid)
