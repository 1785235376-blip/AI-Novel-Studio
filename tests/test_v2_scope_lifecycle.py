"""Original scope writes and pre-upgrade orphan authority lifecycle contracts."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.authorization import AuthorizationScope, DomainRole, DomainRoleAssignment, ModalityDomain, PermissionAssignment, ScopeKind
from app.collaboration import Branch, Storyline, Workspace
from test_v2_project_retirement import (checked, forbidden, grant_new_incarnation, independent,
    mounted, prefix, recreate, retirement, role, rows)


@pytest.fixture(params=[pytest.param("file", marks=pytest.mark.file_backend_only),
                       pytest.param("postgres", marks=pytest.mark.postgres_backend_only)])
def scope_owner(request, tmp_path):
    from app.config import Settings
    from app.repositories.factory import create_repository_bundle
    from app.services import NovelService
    from app.services.collaboration_scope_service import CollaborationScopeService
    backend = request.param
    url = os.environ.get("TEST_POSTGRES_DATABASE_URL", "") if backend == "postgres" else ""
    if backend == "postgres":
        assert url, "real PostgreSQL requires the dedicated test endpoint"
    root = Path(__file__).resolve().parents[1]
    assert tmp_path.resolve().is_relative_to(root / ".runtime")
    bundle = create_repository_bundle(Settings(storage_backend=backend, database_url=url, novel_data=tmp_path), data_root=tmp_path)
    novels = NovelService(bundle.novels, bundle.chapters)
    scopes = CollaborationScopeService(bundle.scope, bundle.novels)
    nid, wid = "scope-owner-" + uuid4().hex, "scope-workspace-" + uuid4().hex
    novels.create({"id": nid, "title": nid})
    scopes.create_workspace(Workspace(wid, "Scope lifecycle workspace"))
    e = SimpleNamespace(bundle=bundle, novels=novels, scopes=scopes, nid=nid, workspace=wid,
                        storyline="storyline-" + uuid4().hex, branch="branch-" + uuid4().hex)
    try:
        yield e
    finally:
        try:
            novels.delete(nid)
        except FileNotFoundError:
            pass
        if backend == "postgres":
            bundle.novels.database.engine.dispose()


@pytest.mark.parametrize("operation", ["link", "storyline", "branch"])
def test_scope_write_finishes_under_original_owner_lease_before_retirement(scope_owner, monkeypatch, operation):
    e = scope_owner
    if operation != "link":
        e.scopes.link_project(e.workspace, e.nid)
    if operation == "branch":
        e.scopes.create_storyline(Storyline(e.storyline, e.workspace, e.nid, "Parent"))
    entered, release, deleting, deleted = Event(), Event(), Event(), Event()
    if operation == "link":
        original = e.scopes.novels.get
        def pause(nid):
            result = original(nid)
            entered.set()
            assert release.wait(20)
            return result
        monkeypatch.setattr(e.scopes.novels, "get", pause)
        write = lambda: e.scopes.link_project(e.workspace, e.nid)
    elif operation == "storyline":
        original = e.bundle.scope.project_workspace
        def pause(nid):
            result = original(nid)
            if not entered.is_set():
                entered.set()
                assert release.wait(20)
            return result
        monkeypatch.setattr(e.bundle.scope, "project_workspace", pause)
        write = lambda: e.scopes.create_storyline(Storyline(e.storyline, e.workspace, e.nid, "In flight"))
    else:
        original = e.bundle.scope.get
        def pause(kind, identity):
            result = original(kind, identity)
            if kind == "storylines" and identity == e.storyline and not entered.is_set():
                entered.set()
                assert release.wait(20)
            return result
        monkeypatch.setattr(e.bundle.scope, "get", pause)
        write = lambda: e.scopes.create_branch(Branch(e.branch, e.workspace, e.nid, e.storyline, "In flight"))
    def delete():
        deleting.set()
        e.novels.delete(e.nid)
        deleted.set()
    with ThreadPoolExecutor(max_workers=2) as pool:
        writer = pool.submit(write)
        try:
            assert entered.wait(10)
            remover = pool.submit(delete)
            assert deleting.wait(5)
            overtook = deleted.wait(.3)
        finally:
            release.set()
        writer.result(timeout=15)
        remover.result(timeout=15)
    assert not overtook, "retirement overtook validated scope write and allowed stale metadata resurrection"
    assert e.bundle.scope.project_workspace(e.nid) is None
    assert e.bundle.scope.list("storylines", project_id=e.nid) == []
    assert e.bundle.scope.list("branches", project_id=e.nid) == []
    e.novels.create({"id": e.nid, "title": "New incarnation"})
    e.scopes.link_project(e.workspace, e.nid)
    e.scopes.create_storyline(Storyline(e.storyline, e.workspace, e.nid, "Fresh"))
    e.scopes.create_branch(Branch(e.branch, e.workspace, e.nid, e.storyline, "Fresh"))


def legacy_orphan(e, monkeypatch):
    """Reproduce historical deletion through HTTP while faulting retirement only."""
    old = checked(e.client.post(e.documents, headers=e.activate(e.lead, branch=e.branch),
                               json=independent("PRIVATE_RETIRED")), 201)
    before = rows(e)
    with monkeypatch.context() as patch:
        patch.setattr(e.bundle.scope, "retire_project", lambda *args, **kwargs: None)
        patch.setattr(e.bundle.authorization, "retire_project", lambda *args, **kwargs: None)
        response = e.client.delete(e.url, headers=e.activate(e.admin))
        assert response.status_code == 204, response.text
    assert not [item for item in e.novels.list() if item["id"] == e.nid]
    assert e.bundle.scope.project_workspace(e.nid) == e.workspace
    after = rows(e)
    for kind in ("roles", "permissions", "bindings", "storylines", "branches", "memberships"):
        assert after[kind] == before[kind]
    return old, after


def test_same_workspace_recreation_retires_preupgrade_orphan_authority(retirement, monkeypatch):
    e = retirement
    old, before = legacy_orphan(e, monkeypatch)
    recreate(e)
    assert not [item for item in e.bundle.authorization.list_role_assignments() if item["scope"].get("project_id") == e.nid]
    assert not [item for item in e.bundle.authorization.list_permission_assignments() if item["scope"].get("project_id") == e.nid]
    assert e.bundle.scope.list("storylines", project_id=e.nid) == []
    assert e.bundle.scope.list("branches", project_id=e.nid) == []
    fresh, _ = grant_new_incarnation(e, reuse_branch=True)
    overview = checked(e.client.get(e.url + "/overview", headers={"X-Session-Token": fresh["X-Session-Token"]}))
    assert overview["novel"]["id"] == e.nid and overview["counts"]["chapters"] == 0
    assert overview["readiness"]["state"] == "NEEDS_CONTENT" and overview["placeholder"] is False
    current = checked(e.client.post(e.documents, headers=fresh, json=independent()), 201)
    assert checked(e.client.get(e.documents + "/" + current["id"], headers=fresh)) == current
    assert e.client.get(e.documents + "/" + old["id"], headers=fresh).status_code == 404
    old_headers = e.activate(e.lead, branch=e.branch)
    assert old_headers == e.old_headers
    forbidden(e.client.post(e.documents, headers=old_headers, json=independent()))
    forbidden(e.client.get(e.documents, headers=old_headers))
    assert all(item in e.bundle.authorization.list_audit_events() for item in before["audits"])


def test_foreign_workspace_orphan_conflict_never_creates_or_changes_owner(retirement, monkeypatch):
    e = retirement
    legacy_orphan(e, monkeypatch)
    foreign = "foreign-orphan-" + uuid4().hex
    e.scopes.create_workspace(Workspace(foreign, "Foreign orphan request"))
    from app.identity import WorkspaceMembership
    e.identity.add_membership(WorkspaceMembership(uuid4().hex, e.admin, foreign))
    role(e, e.admin, AuthorizationScope(ScopeKind.WORKSPACE, foreign), admin=True)
    before = rows(e)
    response = e.client.post(e.prefix + "/novels", headers=e.activate(e.admin, workspace=foreign),
                             json={"id": e.nid, "title": "Foreign orphan collision"})
    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "project already belongs to another workspace"
    assert not [item for item in e.novels.list() if item["id"] == e.nid]
    assert rows(e) == before
    # Restore through the legitimate owner lifecycle, never manual row cleanup.
    recreate(e)


def test_orphan_cleanup_and_new_link_failure_restore_exact_legacy_state(retirement, monkeypatch):
    e = retirement
    _, before = legacy_orphan(e, monkeypatch)
    original = e.scopes.link_project
    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise ValueError("SYNTHETIC_ORPHAN_LINK_FAILURE")
    with monkeypatch.context() as patch:
        patch.setattr(e.scopes, "link_project", fail)
        response = e.client.post(e.prefix + "/novels", headers=e.activate(e.admin),
            json={"id": e.nid, "title": "Failed legacy cleanup recreation"})
        assert response.status_code == 400, response.text
        assert response.json()["detail"] == "SYNTHETIC_ORPHAN_LINK_FAILURE"
    assert not [item for item in e.novels.list() if item["id"] == e.nid]
    assert rows(e) == before
    recreate(e)


@pytest.mark.parametrize("kind", ["role", "permission"])
def test_missing_owner_rejects_grants_even_when_legacy_binding_remains(retirement, monkeypatch, kind):
    e = retirement
    _, before = legacy_orphan(e, monkeypatch)
    scope = AuthorizationScope(ScopeKind.PROJECT, e.workspace, e.nid)
    item = (DomainRoleAssignment(uuid4().hex, e.new_actor, DomainRole.DOMAIN_LEAD, ModalityDomain.NOVEL, scope, e.admin)
            if kind == "role" else PermissionAssignment(uuid4().hex, e.new_actor, "domain.write", ModalityDomain.NOVEL, scope, e.admin))
    with pytest.raises(ValueError, match="project does not exist"):
        getattr(e.authorization, "assign_" + kind)(item)
    assert rows(e) == before
    recreate(e)


@pytest.mark.parametrize("operation", ["storyline", "branch"])
def test_audited_scope_port_holds_owner_until_scope_and_audit_commit(scope_owner, monkeypatch, operation):
    from app.actor_context import ActorContext, SessionContext
    from app.application.persistence import AtomicPathMutationPort
    e = scope_owner
    e.scopes.link_project(e.workspace, e.nid)
    if operation == "branch":
        e.scopes.create_storyline(Storyline(e.storyline, e.workspace, e.nid, "Parent"))
    actor = ActorContext("scope-author", e.workspace, SessionContext("scope-session", "scope-client", "scope-author", e.workspace))
    port = AtomicPathMutationPort(e.bundle.novels, e.bundle.scope, e.bundle.authorization)
    entered, release, deleting, deleted = Event(), Event(), Event(), Event()
    calls = 0
    if operation == "storyline":
        original = e.bundle.scope.project_workspace
        def pause(project_id):
            nonlocal calls
            result = original(project_id)
            calls += 1
            if calls == 2:
                entered.set()
                assert release.wait(20)
            return result
        monkeypatch.setattr(e.bundle.scope, "project_workspace", pause)
        write = lambda: port.create_storyline(e.workspace, e.nid, "Audited in flight", actor)
    else:
        original = e.bundle.scope.get
        def pause(kind, identity):
            nonlocal calls
            result = original(kind, identity)
            if kind == "storylines" and identity == e.storyline:
                calls += 1
                if calls == 2:
                    entered.set()
                    assert release.wait(20)
            return result
        monkeypatch.setattr(e.bundle.scope, "get", pause)
        write = lambda: port.create_branch(e.workspace, e.nid, e.storyline, "Audited in flight", actor)
    def delete():
        deleting.set()
        e.novels.delete(e.nid)
        deleted.set()
    with ThreadPoolExecutor(max_workers=2) as pool:
        writer = pool.submit(write)
        try:
            assert entered.wait(10)
            remover = pool.submit(delete)
            assert deleting.wait(5)
            assert not deleted.wait(.3), "retirement overtook audited scope creation"
        finally:
            release.set()
        saved = writer.result(timeout=15)
        remover.result(timeout=15)
    assert e.bundle.scope.project_workspace(e.nid) is None
    assert e.bundle.scope.list("storylines", project_id=e.nid) == []
    assert e.bundle.scope.list("branches", project_id=e.nid) == []
    assert any(item["target_id"] == saved["id"] for item in e.bundle.authorization.list_audit_events())
    e.novels.create({"id": e.nid, "title": "Fresh owner after audited scope"})


@pytest.mark.parametrize("operation", ["storyline", "branch"])
def test_real_admin_router_postwrite_reauthorization_rolls_back_scope_and_audit(retirement, monkeypatch, operation):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.application.persistence import AtomicPathMutationPort
    from app.collaboration_admin import CollaborationAdminService, create_collaboration_admin_router
    from app.identity import IdentityStatus
    e = retirement
    port = AtomicPathMutationPort(e.bundle.novels, e.bundle.scope, e.bundle.authorization)
    service = CollaborationAdminService(sessions=e.sessions, identity=e.identity,
        authorization=e.authorization, scopes=e.scopes, path_mutations=port)
    app = FastAPI()
    app.include_router(create_collaboration_admin_router(service, prefix=e.prefix + "/collaboration/admin"))
    original, calls = service.actor, 0
    def actor(token, workspace_id):
        nonlocal calls
        calls += 1
        if calls == 3:
            # The real owner has written its scope and audit in an uncommitted
            # transaction. Revoke actual membership before the final guard.
            e.identity.set_membership_status(e.lead, e.workspace, IdentityStatus.INACTIVE)
        return original(token, workspace_id)
    monkeypatch.setattr(service, "actor", actor)
    before = rows(e)
    url = e.prefix + f"/collaboration/admin/workspaces/{e.workspace}/projects/{e.nid}/storylines"
    if operation == "branch":
        url += f"/{e.storyline}/branches"
    with TestClient(app) as client:
        response = client.post(url, headers=e.activate(e.lead, branch=e.branch), json={"name": "Must roll back after real revoke"})
    assert calls == 3, "the real mutation port must invoke both authorization checkpoints"
    assert response.status_code == 403, response.text
    assert response.json()["detail"]["code"] == "INACTIVE_MEMBERSHIP"
    after = rows(e)
    for kind in ("roles", "permissions", "bindings", "storylines", "branches", "audits"):
        assert after[kind] == before[kind]
    assert e.novels.get(e.nid)["id"] == e.nid
