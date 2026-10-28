"""Independent File authority adversarial tests; no quota store or model calls."""
from contextlib import contextmanager
from threading import Event, Thread
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
from app.collaboration_admin import CollaborationAdminService
from app.creative.project_quota_authority import project_quota_authority
from app.identity import IdentityStatus
from test_studio_asset_query import rig, shared_scope


@pytest.fixture
def shared(rig, monkeypatch):
    from app import api
    scope, _ = shared_scope(rig)
    admin = CollaborationAdminService(sessions=rig.sessions, identity=rig.identities,
        authorization=rig.grants, scopes=rig.scopes)
    monkeypatch.setattr(api, 'collaboration_admin_service', admin)
    monkeypatch.setattr(api, 'authorization_service', rig.grants)
    rig.workspace.store.incarnation(rig.nid)
    return rig, scope


def grant(rig, scope, kind, grant_id='write'):
    fields = {'workspace_id': scope['workspace_id'], 'project_id': rig.nid}
    if kind == ScopeKind.BRANCH:
        fields.update(storyline_id=scope['storyline_id'], branch_id=scope['branch_id'])
    rig.grants.assign_permission(PermissionAssignment(grant_id, 'reader', 'domain.write',
        ModalityDomain.NOVEL, AuthorizationScope(kind, **fields), 'fixture'))


def checked(rig, scope, callback=lambda: None):
    with project_quota_authority(rig.workspace, rig.nid, scope, 'reader', 'token-reader', lambda: None) as identity:
        assert identity == rig.workspace.store.incarnation(rig.nid)
        callback()


def test_branch_write_does_not_grant_project_management(shared):
    rig, scope = shared
    grant(rig, scope, ScopeKind.BRANCH)
    marker = rig.root / 'novels' / rig.nid / 'creative_project_v2.json'
    marker.unlink()
    with pytest.raises(HTTPException) as error:
        checked(rig, scope)
    assert error.value.status_code == 403
    assert not marker.exists()


def test_project_write_is_original_project_manager(shared):
    rig, scope = shared
    grant(rig, scope, ScopeKind.PROJECT)
    checked(rig, scope)


def test_workspace_admin_permission_is_original_project_manager(shared):
    rig, scope = shared
    rig.grants.assign_permission(PermissionAssignment('workspace-admin', 'reader', 'workspace.admin',
        ModalityDomain.NOVEL, AuthorizationScope(ScopeKind.WORKSPACE, scope['workspace_id']), 'fixture'))
    checked(rig, scope)


def test_inactive_member_and_expired_session_cannot_enter(shared):
    rig, scope = shared
    grant(rig, scope, ScopeKind.PROJECT)
    rig.identities.set_membership_status('reader', scope['workspace_id'], IdentityStatus.INACTIVE)
    with pytest.raises(HTTPException): checked(rig, scope)
    rig.identities.set_membership_status('reader', scope['workspace_id'], IdentityStatus.ACTIVE)
    rig.sessions.revoke('token-reader')
    with pytest.raises(HTTPException): checked(rig, scope)


def test_revoke_restore_membership_between_observation_and_lease_rejected(shared, monkeypatch):
    from app import api
    rig, scope = shared
    grant(rig, scope, ScopeKind.PROJECT)
    original = api._workbench_authority_lease
    @contextmanager
    def changed(*args):
        rig.identities.set_membership_status('reader', scope['workspace_id'], IdentityStatus.INACTIVE)
        rig.identities.set_membership_status('reader', scope['workspace_id'], IdentityStatus.ACTIVE)
        with original(*args): yield
    monkeypatch.setattr(api, '_workbench_authority_lease', changed)
    with pytest.raises(HTTPException) as error: checked(rig, scope)
    assert error.value.status_code == 403


def test_revoke_regrant_project_permission_between_observation_and_lease_rejected(shared, monkeypatch):
    from app import api
    rig, scope = shared
    grant(rig, scope, ScopeKind.PROJECT)
    original = api._workbench_authority_lease
    @contextmanager
    def changed(*args):
        rig.grants.revoke_permission('write', 'fixture')
        grant(rig, scope, ScopeKind.PROJECT)
        with original(*args): yield
    monkeypatch.setattr(api, '_workbench_authority_lease', changed)
    with pytest.raises(HTTPException) as error: checked(rig, scope)
    assert error.value.status_code == 403


def test_session_revoke_regrant_between_observation_and_lease_rejected(shared, monkeypatch):
    from app import api
    rig, scope = shared
    grant(rig, scope, ScopeKind.PROJECT)
    original = api._workbench_authority_lease
    old = rig.sessions.resolve('token-reader').session
    @contextmanager
    def changed(*args):
        rig.sessions.revoke('token-reader')
        rig.sessions.register('token-reader', old)
        with original(*args): yield
    monkeypatch.setattr(api, '_workbench_authority_lease', changed)
    with pytest.raises(HTTPException) as error: checked(rig, scope)
    assert error.value.status_code == 403


def test_project_reincarnation_between_observation_and_lease_rejected(shared, monkeypatch):
    from app import api
    import json
    rig, scope = shared
    grant(rig, scope, ScopeKind.PROJECT)
    original = api._workbench_authority_lease
    marker = rig.root / 'novels' / rig.nid / 'creative_project_v2.json'
    @contextmanager
    def changed(*args):
        row = json.loads(marker.read_text(encoding='utf-8'))
        row['project_incarnation'] = str(uuid4())
        marker.write_text(json.dumps(row), encoding='utf-8')
        with original(*args): yield
    monkeypatch.setattr(api, '_workbench_authority_lease', changed)
    with pytest.raises(HTTPException) as error: checked(rig, scope)
    assert error.value.status_code == 403


@pytest.mark.parametrize('change', ['membership', 'session', 'grant'])
def test_revocation_waits_for_mutation_commit(shared, change):
    rig, scope = shared
    grant(rig, scope, ScopeKind.PROJECT)
    started, finished = Event(), Event()
    failures = []
    def revoke():
        started.set()
        try:
            if change == 'membership':
                rig.identities.set_membership_status('reader', scope['workspace_id'], IdentityStatus.INACTIVE)
            elif change == 'session':
                rig.sessions.revoke('token-reader')
            else:
                rig.grants.revoke_permission('write', 'fixture')
        except Exception as exc:
            failures.append(exc)
        finally:
            finished.set()
    def mutation():
        worker = Thread(target=revoke, daemon=True)
        worker.start()
        assert started.wait(5)
        assert not finished.wait(.1)
    checked(rig, scope, mutation)
    assert finished.wait(5)
    assert not failures


def test_postgres_is_explicitly_unsupported(shared, monkeypatch):
    rig, scope = shared
    monkeypatch.setattr(rig.workspace.store.store, 'backend', 'postgres')
    with pytest.raises(HTTPException) as error: checked(rig, scope)
    assert error.value.status_code == 409


def test_local_mode_uses_original_guard_and_incarnation(rig):
    observed = []
    with project_quota_authority(rig.workspace, rig.nid, rig.scope, 'local-author', None,
                                 lambda: observed.append('guard')) as identity:
        assert identity == rig.workspace.store.incarnation(rig.nid)
    assert len(observed) == 3


def test_wrong_mode_cannot_bypass_shared_authority(shared):
    rig, _ = shared
    with pytest.raises(HTTPException):
        with project_quota_authority(rig.workspace, rig.nid,
                                     {'mode': 'local', 'novel_id': rig.nid},
                                     'local-author', None, lambda: None):
            pytest.fail('shared authority bypassed')
