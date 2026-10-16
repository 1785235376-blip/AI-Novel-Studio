"""Real mounted File / opt-in PostgreSQL first-use, with original write ports."""
import copy
import threading
from uuid import uuid4

import pytest
from app.experimental.first_use import FirstUseContext, FirstUseService, COLLECTION, SAMPLE_DOCUMENT, SAMPLE_TITLE
from test_r3_mounted_contracts import mounted, prefix, checked, scoped


@pytest.fixture
def first_use(mounted, monkeypatch):
    e = mounted
    e.first_use = e.experimental.first_use_service
    monkeypatch.setattr(e.first_use, 'store', e.store)
    e.first_base = e.prefix + '/experimental/first-use/sample'
    e.first_contexts = [FirstUseContext('local-author', None)]
    assert e.first_use._read(e.first_contexts[0]) is None
    yield e
    # Exact receipt-owned cleanup; never delete by title or wildcard.
    for ctx in e.first_contexts:
        row = e.first_use._read(ctx)
        if row:
            nid = row.get('project_id') or row.get('reserved_project_id')
            if nid:
                try:
                    assert e.novels.get(nid)['title'] == SAMPLE_TITLE
                    if ctx.workspace_id:
                        e.api.collaboration_admin_service.path_mutations.delete_project(ctx.workspace_id, nid, e.sessions.resolve(ctx.token))
                    else:
                        e.novels.delete(nid)
                except (FileNotFoundError, KeyError):
                    pass
        key, scope = e.first_use.journal(ctx)
        if e.backend == 'postgres':
            with e.store._connect() as conn:
                conn.execute('DELETE FROM experimental_scope_documents WHERE scope_key = %s', (e.store.key(key, scope),))


def start(e, body=None, headers=None):
    return checked(e.client.post(e.first_base, json=body or {}, headers=headers or {}))['item']


def test_local_create_write_save_reopen_export_uses_original_authorities(first_use):
    e = first_use
    original = copy.deepcopy(e.chapters.get(e.chapter['id']))
    before = {n['id'] for n in e.novels.list()}
    item = start(e)
    assert item['stage'] == 'READY', item
    assert item['synthetic'] and item['can_open'] and item['path'] is None
    assert item['project_id'] not in before
    assert {n['id'] for n in e.novels.list()} == before | {item['project_id']}
    assert e.chapters.get(item['chapter_id'])['document'] == SAMPLE_DOCUMENT
    assert len(e.chapters.list(item['project_id'])) == 1
    assert start(e)['id'] == item['id']
    assert len(e.chapters.list(item['project_id'])) == 1
    response = e.client.get(e.first_base)
    assert response.headers['cache-control'] == 'no-store'
    assert 'reserved_project_id' not in response.text and 'initial_document' not in response.text
    chapter = checked(e.client.get(e.prefix + '/chapters/' + item['chapter_id']))
    prose = chapter['content'] + '\n\n我写下自己的结尾。'
    saved = checked(e.client.put(e.prefix + '/chapters/' + item['chapter_id'], json={'content': prose, 'version': chapter['version'], 'source': 'MANUAL_SAVE'}))
    reopened = checked(e.client.get(e.prefix + '/chapters/' + item['chapter_id']))
    assert reopened == saved and '自己的结尾' in reopened['content']
    export = checked(e.client.get(e.prefix + f"/novels/{item['project_id']}/export", params={'format': 'txt'}))
    assert '自己的结尾' in export['content']
    assert e.chapters.get(e.chapter['id']) == original
    restarted = FirstUseService(e.store, e.first_use.authority)
    assert restarted.inspect(e.first_contexts[0])['item']['id'] == item['id']


def test_default_off_acceptance_and_unexpected_body_fail_closed(first_use, monkeypatch):
    e = first_use
    for body in ({'project_id': e.nid}, {'workspace_id': ''}, {'provider': 'paid'}):
        assert e.client.post(e.first_base, json=body).status_code == 422
    assert e.client.post(e.first_base, json={}, headers={'X-Session-Token': 'not-local'}).status_code == 400
    for variable, value in [('EXPERIMENTAL_FEATURES', ''), ('V1_ACCEPTANCE_MODE', 'true')]:
        with monkeypatch.context() as change:
            change.setenv(variable, value)
            for method, suffix in [('get', ''), ('post', ''), ('post', '/recover')]:
                response = getattr(e.client, method)(e.first_base + suffix, **({'json': {}} if method == 'post' else {}))
                assert response.status_code == 404
    assert e.first_use._read(e.first_contexts[0]) is None


def test_unknown_project_create_is_durable_and_never_retried(first_use, monkeypatch):
    e = first_use
    original = e.first_use.authority.create_project
    calls = []
    def lost(ctx, row):
        result = original(ctx, row)
        calls.append(result['id'])
        raise OSError('synthetic transport loss after original commit')
    monkeypatch.setattr(e.first_use.authority, 'create_project', lost)
    item = start(e)
    assert item['stage'] == 'CREATING_PROJECT' and not item['can_open']
    assert start(e)['id'] == item['id']
    assert checked(e.client.post(e.first_base + '/recover', json={}))['item']['id'] == item['id']
    assert len(calls) == 1
    assert len(e.chapters.list(calls[0])) == 0


def test_known_project_survives_navigation_failure_and_explicit_recovery(first_use, monkeypatch):
    e = first_use
    target = e.first_use.authority.target
    def unavailable(*args, **kwargs):
        raise FileNotFoundError('synthetic read failure')
    with monkeypatch.context() as change:
        change.setattr(e.first_use.authority, 'target', unavailable)
        assert e.client.post(e.first_base, json={}).status_code == 404
    retained = checked(e.client.get(e.first_base))['item']
    assert retained['project_id'] and retained['stage'] == 'PROJECT_READY'
    assert not e.chapters.list(retained['project_id'])
    recovered = checked(e.client.post(e.first_base + '/recover', json={}))['item']
    assert recovered['stage'] == 'READY' and recovered['project_id'] == retained['project_id']


def test_known_chapter_retained_before_hydration_failure(first_use, monkeypatch):
    e = first_use
    with monkeypatch.context() as change:
        change.setattr(e.first_use.authority, 'read_chapter', lambda *args: (_ for _ in ()).throw(FileNotFoundError('synthetic read failure')))
        assert e.client.post(e.first_base, json={}).status_code == 404
    row = checked(e.client.get(e.first_base))['item']
    assert row['stage'] == 'CHAPTER_CREATED' and row['chapter_id']
    recovered = checked(e.client.post(e.first_base + '/recover', json={}))['item']
    assert recovered['stage'] == 'READY' and recovered['chapter_id'] == row['chapter_id']


def test_unknown_chapter_create_preserves_project_without_duplicate(first_use, monkeypatch):
    e = first_use
    original = e.first_use.authority.create_chapter
    def lost(ctx, row):
        original(ctx, row)
        raise OSError('synthetic lost chapter receipt')
    monkeypatch.setattr(e.first_use.authority, 'create_chapter', lost)
    item = start(e)
    assert item['stage'] == 'CREATING_CHAPTER' and item['can_open'] and not item['can_recover']
    for _ in range(2):
        checked(e.client.post(e.first_base + '/recover', json={}))
        start(e)
    assert len(e.chapters.list(item['project_id'])) == 1


@pytest.mark.parametrize('after_commit', [False, True])
def test_unknown_save_reconciles_only_exact_version_and_document(first_use, monkeypatch, after_commit):
    e = first_use
    original = e.first_use.authority.save_chapter
    def lost(ctx, row):
        if after_commit:
            original(ctx, row)
        raise OSError('synthetic save uncertainty')
    with monkeypatch.context() as change:
        change.setattr(e.first_use.authority, 'save_chapter', lost)
        item = start(e)
    assert item['stage'] == 'SAVING_SAMPLE'
    recovered = checked(e.client.post(e.first_base + '/recover', json={}))['item']
    assert recovered['stage'] == 'READY'
    chapter = e.chapters.get(item['chapter_id'])
    assert chapter['version'] == 2 and chapter['document'] == SAMPLE_DOCUMENT
    assert len(e.chapters.history(chapter['id'])) == 1


def test_concurrent_user_edit_never_overwritten_during_recovery(first_use, monkeypatch):
    e = first_use
    with monkeypatch.context() as change:
        change.setattr(e.first_use.authority, 'save_chapter', lambda *args: (_ for _ in ()).throw(OSError('synthetic interruption')))
        item = start(e)
    changed = e.chapters.save(item['chapter_id'], {'content': '我的未覆盖新版本', 'version': 1})
    recovered = checked(e.client.post(e.first_base + '/recover', json={}))['item']
    assert recovered['stage'] == 'SOURCE_CHANGED' and recovered['can_open']
    assert e.chapters.get(item['chapter_id']) == changed


def test_flag_revoked_between_original_steps_stops_following_mutation(first_use, monkeypatch):
    e = first_use
    original = e.first_use.authority.create_project
    def revoke(ctx, row):
        result = original(ctx, row)
        monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
        return result
    monkeypatch.setattr(e.first_use.authority, 'create_project', revoke)
    assert e.client.post(e.first_base, json={}).status_code == 404
    row = e.first_use._read(e.first_contexts[0])
    assert row['project_id'] and row['stage'] == 'PROJECT_READY'
    assert not e.chapters.list(row['project_id'])


def test_concurrent_start_creates_exactly_one_project_and_chapter(first_use, monkeypatch):
    e = first_use
    original = e.first_use.authority.create_project
    arrived, release = threading.Event(), threading.Event()
    calls, responses = [], []
    def blocked(ctx, row):
        calls.append(row['id']); arrived.set(); assert release.wait(10)
        return original(ctx, row)
    monkeypatch.setattr(e.first_use.authority, 'create_project', blocked)
    worker = threading.Thread(target=lambda: responses.append(e.first_use.start(e.first_contexts[0])))
    worker.start()
    try:
        assert arrived.wait(10)
        pending = e.first_use.start(e.first_contexts[0])['item']
        assert pending['stage'] == 'CREATING_PROJECT'
    finally:
        release.set(); worker.join(10)
    assert len(calls) == 1 and responses[0]['item']['stage'] == 'READY'


def setup_scoped(e, monkeypatch):
    from app.application.audit_service import AuditService
    from app.application.collaboration_service import CollaborationApplicationService
    from app.application.persistence import AtomicPathMutationPort, create_atomic_chapter_audit_port
    from app.collaboration_admin import CollaborationAdminService
    from app.collaboration_api import CollaborationReadService
    from app.authorization import AuthorizationScope, DomainRole, DomainRoleAssignment, ModalityDomain, ScopeKind
    scoped(e, monkeypatch)
    application = CollaborationApplicationService(e.membership, create_atomic_chapter_audit_port(e.bundle.chapters, e.bundle.authorization), AuditService(e.bundle.authorization))
    admin = CollaborationAdminService(sessions=e.sessions, identity=e.identity, authorization=e.authorization, scopes=e.scopes,
        path_mutations=AtomicPathMutationPort(e.bundle.novels, e.bundle.scope, e.bundle.authorization))
    reader = CollaborationReadService(sessions=e.sessions, membership_authorization=e.membership, identity=e.identity,
        authorization=e.authorization, scopes=e.scopes, chapters=e.chapters, generations=None, lore_repository=e.bundle.lore,
        novels=e.bundle.novels, collaboration_application=application)
    monkeypatch.setattr(e.api, 'collaboration_admin_service', admin)
    monkeypatch.setattr(e.api, 'collaboration_application_service', application)
    monkeypatch.setattr(e.first_use.authority, 'collaboration', reader)
    role = 'first-use-admin-' + uuid4().hex
    e.authorization.assign_role(DomainRoleAssignment(role, e.lead, DomainRole.ADMIN, ModalityDomain.NOVEL,
        AuthorizationScope(ScopeKind.WORKSPACE, e.workspace), e.lead))
    e.first_contexts.append(FirstUseContext(e.lead, e.workspace, e.lead))
    return role


def test_scoped_original_project_chapter_audit_and_current_permissions(first_use, monkeypatch):
    e = first_use
    role = setup_scoped(e, monkeypatch)
    assert e.client.post(e.first_base, json={}).status_code == 401
    assert e.client.post(e.first_base, json={}, headers=e.headers).status_code == 400
    assert e.client.post(e.first_base, json={'workspace_id': e.workspace}, headers=e.viewer_headers).status_code == 403
    item = start(e, {'workspace_id': e.workspace}, e.headers)
    assert item['stage'] == 'READY', item
    path = item['path']
    assert path['workspace_id'] == e.workspace and path['project_id'] != e.nid
    assert e.chapters.get(item['chapter_id'])['document'] == SAMPLE_DOCUMENT
    actions = [r['action'] for r in e.bundle.authorization.list_audit_events() if r.get('scope', {}).get('project_id') == item['project_id']]
    assert all(action in actions for action in ['PROJECT_CREATED', 'CHAPTER_CREATED', 'CHAPTER_UPDATED'])
    assert checked(e.client.get(e.first_base, params={'workspace_id': e.workspace}, headers=e.viewer_headers))['item'] is None
    from app.authorization import AuthorizationScope, DomainRole, DomainRoleAssignment, ModalityDomain, ScopeKind
    e.authorization.assign_role(DomainRoleAssignment('backup-admin-' + uuid4().hex, e.viewer, DomainRole.ADMIN,
        ModalityDomain.NOVEL, AuthorizationScope(ScopeKind.WORKSPACE, e.workspace), e.lead))
    e.authorization.revoke_role(role, e.lead)
    assert e.client.get(e.first_base, params={'workspace_id': e.workspace}, headers=e.headers).status_code == 403
    assert e.client.post(e.first_base + '/recover', json={'workspace_id': e.workspace}, headers=e.headers).status_code == 403


def test_permission_revocation_after_project_receipt_stops_chapter_creation(first_use, monkeypatch):
    from app.authorization import AuthorizationScope, DomainRole, DomainRoleAssignment, ModalityDomain, ScopeKind
    e = first_use
    role = setup_scoped(e, monkeypatch)
    e.authorization.assign_role(DomainRoleAssignment('second-admin-' + uuid4().hex, e.viewer, DomainRole.ADMIN,
        ModalityDomain.NOVEL, AuthorizationScope(ScopeKind.WORKSPACE, e.workspace), e.lead))
    original = e.first_use.authority.create_project
    def revoke(ctx, row):
        created = original(ctx, row)
        e.authorization.revoke_role(role, e.lead)
        return created
    monkeypatch.setattr(e.first_use.authority, 'create_project', revoke)
    assert e.client.post(e.first_base, json={'workspace_id': e.workspace}, headers=e.headers).status_code == 403
    row = e.first_use._read(e.first_contexts[-1])
    assert row['project_id'] and row['stage'] == 'PROJECT_READY'
    assert not e.chapters.list(row['project_id'])
    assert e.client.post(e.first_base + '/recover', json={'workspace_id': e.workspace}, headers=e.headers).status_code == 403
    assert not e.chapters.list(row['project_id'])


def test_deleted_sample_is_not_recreated_on_repeat(first_use):
    e = first_use
    item = start(e)
    e.novels.delete(item['project_id'])
    repeated = start(e)
    assert repeated['id'] == item['id'] and repeated['availability'] == 'UNAVAILABLE'
    assert not repeated.get('can_open') and not repeated.get('can_recover')
    assert all(row['id'] != item['project_id'] for row in e.novels.list())
