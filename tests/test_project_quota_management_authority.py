"""Branchless management checks against the original File authority owners."""
from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import sys
from threading import Event, Thread
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.actor_context import SessionContext
from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
from app.collaboration import Workspace, Storyline, Branch
from app.collaboration_admin import CollaborationAdminService
from app.creative.project_quota_management_authority import project_management_lease
from app.identity import User, WorkspaceMembership, IdentityStatus
from test_studio_asset_query import rig


@pytest.fixture
def shared_project(rig, monkeypatch):
    from app import api
    object.__setattr__(rig.settings, 'enable_collaboration_runtime', True)
    rig.scopes.create_workspace(Workspace('ws', 'Synthetic'))
    rig.scopes.link_project('ws', rig.nid)
    rig.identities.create_user(User('manager', 'Manager'))
    rig.identities.add_membership(WorkspaceMembership('member', 'manager', 'ws'))
    rig.sessions.register('token', SessionContext('session', 'client', 'manager', 'ws'))
    admin = CollaborationAdminService(sessions=rig.sessions, identity=rig.identities,
        authorization=rig.grants, scopes=rig.scopes)
    monkeypatch.setattr(api, 'collaboration_admin_service', admin)
    monkeypatch.setattr(api, 'authorization_service', rig.grants)
    rig.workspace.store.incarnation(rig.nid)
    return rig


def add_grant(rig, permission='domain.write', kind=ScopeKind.PROJECT, grant_id='grant'):
    kw = {'workspace_id': 'ws'}
    if kind != ScopeKind.WORKSPACE: kw['project_id'] = rig.nid
    if kind == ScopeKind.BRANCH: kw.update(storyline_id='story', branch_id='branch')
    rig.grants.assign_permission(PermissionAssignment(grant_id, 'manager', permission,
        ModalityDomain.NOVEL, AuthorizationScope(kind, **kw), 'fixture'))


@pytest.mark.parametrize('permission,kind', [('domain.write', ScopeKind.PROJECT),
                                               ('workspace.admin', ScopeKind.WORKSPACE)])
def test_management_without_any_branch(shared_project, permission, kind):
    rig = shared_project
    add_grant(rig, permission, kind)
    assert not rig.scopes.repository.list('branches')
    with project_management_lease(rig.workspace, rig.nid, 'token') as binding:
        assert binding == {'novel_id': rig.nid, 'incarnation': rig.workspace.store.incarnation(rig.nid)}
        assert getattr(rig.assets._scope, 'binding', None) is None


def test_branch_writer_is_not_project_manager(shared_project):
    rig = shared_project
    rig.scopes.create_storyline(Storyline('story', 'ws', rig.nid, 'Story'))
    rig.scopes.create_branch(Branch('branch', 'ws', rig.nid, 'story', 'Branch'))
    add_grant(rig, kind=ScopeKind.BRANCH)
    with pytest.raises(HTTPException) as error:
        with project_management_lease(rig.workspace, rig.nid, 'token'): pytest.fail()
    assert error.value.status_code == 403


def test_different_workspace_never_enters(shared_project):
    rig = shared_project
    rig.scopes.create_workspace(Workspace('other', 'Other'))
    rig.identities.add_membership(WorkspaceMembership('member-other', 'manager', 'other'))
    rig.sessions.register('other-token', SessionContext('session-other', 'client', 'manager', 'other'))
    rig.grants.assign_permission(PermissionAssignment('other-admin', 'manager', 'workspace.admin', ModalityDomain.NOVEL,
        AuthorizationScope(ScopeKind.WORKSPACE, 'other'), 'fixture'))
    with pytest.raises(HTTPException) as error:
        with project_management_lease(rig.workspace, rig.nid, 'other-token'): pytest.fail()
    assert error.value.status_code == 403


@pytest.mark.parametrize('change', ['session', 'membership', 'grant', 'topology', 'incarnation'])
def test_aba_between_observation_and_original_lease_rejected(shared_project, monkeypatch, change):
    from app import api
    import json
    rig = shared_project
    add_grant(rig)
    original = api._workbench_authority_lease
    @contextmanager
    def altered(*args):
        if change == 'session':
            session = rig.sessions.resolve('token').session
            rig.sessions.revoke('token'); rig.sessions.register('token', session)
        elif change == 'membership':
            rig.identities.set_membership_status('manager', 'ws', IdentityStatus.INACTIVE)
            rig.identities.set_membership_status('manager', 'ws', IdentityStatus.ACTIVE)
        elif change == 'grant':
            rig.grants.revoke_permission('grant', 'fixture'); add_grant(rig)
        elif change == 'topology':
            rig.scopes.repository.retire_project(rig.nid)
            rig.scopes.link_project('ws', rig.nid)
        else:
            marker = rig.root / 'novels' / rig.nid / 'creative_project_v2.json'
            row = json.loads(marker.read_text(encoding='utf-8'))
            row['project_incarnation'] = str(uuid4())
            marker.write_text(json.dumps(row), encoding='utf-8')
        with original(*args): yield
    monkeypatch.setattr(api, '_workbench_authority_lease', altered)
    with pytest.raises(HTTPException) as error:
        with project_management_lease(rig.workspace, rig.nid, 'token'): pytest.fail()
    assert error.value.status_code == 403


@pytest.mark.parametrize('change', ['session', 'membership', 'grant', 'topology'])
def test_existing_authority_mutation_waits_for_quota_commit(shared_project, change):
    rig = shared_project
    add_grant(rig)
    started, finished = Event(), Event()
    errors = []
    def compete():
        started.set()
        try:
            if change == 'session': rig.sessions.revoke('token')
            elif change == 'membership': rig.identities.set_membership_status('manager', 'ws', IdentityStatus.INACTIVE)
            elif change == 'grant': rig.grants.revoke_permission('grant', 'fixture')
            else: rig.scopes.repository.retire_project(rig.nid)
        except Exception as exc: errors.append(exc)
        finally: finished.set()
    with project_management_lease(rig.workspace, rig.nid, 'token'):
        worker = Thread(target=compete, daemon=True)
        worker.start(); assert started.wait(5)
        assert not finished.wait(.1)
    assert finished.wait(5) and not errors


def test_local_mode_retains_original_workbench_authority(rig):
    with project_management_lease(rig.workspace, rig.nid, None) as identity:
        assert identity['incarnation'] == rig.workspace.store.incarnation(rig.nid)


def test_other_storage_owner_fails_closed(shared_project, monkeypatch):
    rig = shared_project
    monkeypatch.setattr(rig.workspace.store.store, 'backend', 'postgres')
    with pytest.raises(HTTPException) as error:
        with project_management_lease(rig.workspace, rig.nid, 'token'): pytest.fail()
    assert error.value.status_code == 409


@pytest.mark.skipif(os.environ.get('QUOTA_LOCK_PROBE_CHILD') != '1', reason='subprocess-only lock probe')
def test_lock_order_competes_with_asset_guard_child(shared_project, monkeypatch):
    from app import api
    rig = shared_project
    add_grant(rig)
    rig.scopes.create_storyline(Storyline('story', 'ws', rig.nid, 'Story'))
    rig.scopes.create_branch(Branch('branch', 'ws', rig.nid, 'story', 'Branch'))
    scope = {'mode': 'collaboration', 'novel_id': rig.nid, 'workspace_id': 'ws',
             'storyline_id': 'story', 'branch_id': 'branch'}
    ready, proceed, entered, completed = Event(), Event(), Event(), Event()
    failures = []
    original = api._workbench_authority_lease
    @contextmanager
    def observed(*args):
        ready.set()
        assert proceed.wait(5)
        with original(*args):
            print('manager-authority-entered', flush=True)
            entered.set()
            yield
    monkeypatch.setattr(api, '_workbench_authority_lease', observed)
    def manager():
        try:
            with project_management_lease(rig.workspace, rig.nid, 'token'):
                print('manager-completed', flush=True)
        except Exception as exc: failures.append(exc)
        finally: completed.set()
    worker = Thread(target=manager, daemon=True)
    worker.start()
    assert ready.wait(5)
    with rig.workspace._asset_scope(rig.nid, scope):
        proceed.set()
        assert entered.wait(5)
        # Original asset callers reauthorize while holding asset -> project;
        # they must not wait on the manager's authorization mutation lock.
        assert api._workbench_authorize(rig.nid, 'token', 'branch', 'domain.write')[0] == 'manager'
        print('asset-guard-completed', flush=True)
    assert completed.wait(5) and not failures


def test_lock_order_competes_with_asset_guard_subprocess():
    env = dict(os.environ, QUOTA_LOCK_PROBE_CHILD='1')
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-s',
        str(Path(__file__).resolve()) + '::test_lock_order_competes_with_asset_guard_child'],
        env=env, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    for marker in ('manager-authority-entered', 'asset-guard-completed', 'manager-completed'):
        assert marker in result.stdout
