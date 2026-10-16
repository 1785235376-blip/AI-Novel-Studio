"""Original-owner File guards must finish while retirement waits for a project.

The probe uses a child process so a lock-order regression fails within a bounded
time and cannot strand the rest of pytest behind deadlocked daemon threads.
"""
import os
from pathlib import Path
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

pytestmark = pytest.mark.file_backend_only


def test_creative_project_guard_reads_do_not_deadlock_waiting_retirement(tmp_path):
    script = r'''
import json, os, sys
from pathlib import Path
from threading import Event, Thread
from app.authorization import AuthorizationScope, DomainRole, DomainRoleAssignment, ModalityDomain, ScopeKind
from app.creative.project_store import BINDING, CreativeProjectStore
from app.experimental.store import ExperimentalStore
from app.repository import FileRepository
from app.repositories.file.novel import FileNovelRepository
from app.repositories.file.scope import FileAuthorizationRepository, FileScopeRepository
from app.services.authorization_service import AuthorizationService
from app.services.collaboration_scope_service import CollaborationScopeService

root = Path(sys.argv[1]); backend = FileRepository(root)
nid = backend.create_novel({'id': 'guard-retirement-race', 'title': 'Original owner'})['id']
scopes = FileScopeRepository(root); auth = FileAuthorizationRepository(root)
scopes.create('workspaces', {'id': 'workspace', 'name': 'Workspace'})
scopes.link_project(nid, 'workspace')
authority = AuthorizationService(auth, CollaborationScopeService(scopes, FileNovelRepository(backend)))
scope = AuthorizationScope(ScopeKind.PROJECT, 'workspace', nid)
authority.assign_role(DomainRoleAssignment('grant', 'author', DomainRole.DOMAIN_LEAD, ModalityDomain.NOVEL, scope, 'author'))
store = CreativeProjectStore(ExperimentalStore(root)); graph_scope = {'mode': 'local', 'novel_id': nid}
original = store.incarnation(nid)
project_held, authorization_held = Event(), Event()
outcomes = {}

def guarded_write():
    try:
        with store.transaction(nid, graph_scope) as document:
            project_held.set()
            assert authorization_held.wait(5), 'retirement did not take its authorization transaction'
            # These are the real read paths used by project-held creative guards.
            assert authority.is_allowed('author', 'domain.write', ModalityDomain.NOVEL, scope)
            assert auth.list_role_assignments('author')
            assert auth.list_permission_assignments('author') == []
            assert auth.list_audit_events()
            document['collections'].setdefault('creative_graph_definitions_v2', {})['probe'] = {BINDING: original}
        outcomes['writer'] = 'committed'
    except BaseException as exc:
        outcomes['writer'] = type(exc).__name__ + ': ' + str(exc)

def retire():
    try:
        with auth.mutation():
            authorization_held.set()
            backend.delete_novel(nid, scopes=scopes, authorization=auth)
        outcomes['retirement'] = 'committed'
    except BaseException as exc:
        outcomes['retirement'] = type(exc).__name__ + ': ' + str(exc)

writer = Thread(target=guarded_write, daemon=True); writer.start()
assert project_held.wait(5), 'creative transaction did not acquire the project'
deletion = Thread(target=retire, daemon=True); deletion.start()
writer.join(8); deletion.join(8)
if writer.is_alive() or deletion.is_alive():
    print(json.dumps({'deadlock': True, 'outcomes': outcomes}), flush=True)
    os._exit(2)
assert outcomes == {'writer': 'committed', 'retirement': 'committed'}, outcomes
assert not (backend.novels / nid).exists()
assert scopes.project_workspace(nid) is None
assert auth.list_role_assignments('author') == []
assert auth.list_audit_events(), 'retirement erased historical grant evidence'
backend.create_novel({'id': nid, 'title': 'Replacement owner'})
assert store.incarnation(nid) != original
assert store.read(nid, graph_scope)['collections']['creative_graph_definitions_v2'] == {}
print(json.dumps({'deadlock': False, 'outcomes': outcomes}), flush=True)
'''
    result = subprocess.run([sys.executable, '-B', '-c', script, str(tmp_path)],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"deadlock": false' in result.stdout


def test_unrelated_scope_write_survives_reserved_project_creation_rollback(tmp_path, monkeypatch):
    from app.actor_context import ActorContext, SessionContext
    from app.application.persistence import AtomicPathMutationPort
    from app.repository import FileRepository
    from app.repositories.file.novel import FileNovelRepository
    from app.repositories.file.scope import FileAuthorizationRepository, FileScopeRepository

    backend = FileRepository(tmp_path)
    scopes, authorization = FileScopeRepository(tmp_path), FileAuthorizationRepository(tmp_path)
    scopes.create('workspaces', {'id': 'workspace', 'name': 'Original workspace'})
    actor = ActorContext('author', 'workspace', SessionContext('session', 'client', 'author', 'workspace'))
    port = AtomicPathMutationPort(FileNovelRepository(backend), scopes, authorization)
    audit_entered, release, scope_started, scope_finished = Event(), Event(), Event(), Event()

    def fail_audit(_event):
        audit_entered.set()
        assert release.wait(10), 'rollback coordination was not released'
        raise RuntimeError('SYNTHETIC_RESERVED_CREATE_AUDIT_FAILURE')

    def unrelated_scope_write():
        scope_started.set()
        scopes.create('workspaces', {'id': 'unrelated', 'name': 'Unrelated workspace'})
        scope_finished.set()

    monkeypatch.setattr(port.audit, 'append', fail_audit)
    with ThreadPoolExecutor(max_workers=2) as pool:
        creation = pool.submit(port.create_project, 'workspace', 'Rollback project', '', actor)
        try:
            assert audit_entered.wait(5), 'reserved create never reached its original audit owner'
            write = pool.submit(unrelated_scope_write)
            assert scope_started.wait(5)
            assert not scope_finished.wait(.2), 'unrelated scope writer bypassed the snapshot transaction'
        finally:
            release.set()
        with pytest.raises(RuntimeError, match='SYNTHETIC_RESERVED_CREATE_AUDIT_FAILURE'):
            creation.result(timeout=10)
        write.result(timeout=10)
    assert backend.list_novels() == []
    assert scopes.list('project_workspaces') == []
    assert scopes.list('storylines') == []
    assert scopes.list('branches') == []
    assert scopes.get('workspaces', 'workspace')['name'] == 'Original workspace'
    assert scopes.get('workspaces', 'unrelated')['name'] == 'Unrelated workspace'
