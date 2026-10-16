"""P0 retirement contracts over mounted routes and original File/real PG owners.

No session, membership, permission or storage authority is replaced. Separate
real launcher bootstraps model independent actors; reselecting a bootstrap keeps
the exact session issued before deletion alive for the negative control.
"""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Event
from time import monotonic
from uuid import uuid4

import pytest

from app.authorization import AuthorizationScope, DomainRole, DomainRoleAssignment, ModalityDomain, PermissionAssignment, ScopeKind
from app.collaboration import Branch, Storyline, Workspace
from app.identity import User, WorkspaceMembership
from app.packaging.bootstrap_api import PackagedBootstrapRegistry
from app.packaging.local_session_bootstrap import LocalSessionBootstrap, TrustedLocalIdentity
from app.packaging.runtime_identity import RuntimeIdentity
from test_r3_mounted_contracts import checked, mounted, prefix, scoped


def role(e, actor, scope, *, admin=False):
    return e.authorization.assign_role(DomainRoleAssignment(uuid4().hex, actor,
        DomainRole.ADMIN if admin else DomainRole.DOMAIN_LEAD, ModalityDomain.NOVEL, scope, actor))


def permission(e, actor, scope):
    return e.authorization.assign_permission(PermissionAssignment(uuid4().hex, actor,
        "domain.read", ModalityDomain.NOVEL, scope, actor))


@pytest.fixture
def retirement(mounted, monkeypatch):
    import app.dependencies as dependencies
    e = scoped(mounted, monkeypatch)
    config = replace(e.config, enable_collaboration_runtime=True, enable_packaged_runtime=True)
    monkeypatch.setattr(e.api, "settings", config)
    monkeypatch.setattr(e.api, "authorization_service", e.authorization)
    monkeypatch.setattr(e.main, "settings", config)
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2,asset_lineage_v2")
    for name, value in (("store", e.store), ("novels", e.novels), ("chapters", e.chapters)):
        monkeypatch.setattr(e.experimental.creative_service, name, value)
    e.admin, e.new_actor = "admin-" + uuid4().hex, "new-" + uuid4().hex
    for actor in (e.admin, e.new_actor):
        e.identity.create_user(User(actor, actor))
        e.identity.add_membership(WorkspaceMembership("m-" + actor, actor, e.workspace))
    e.workspace_grant = role(e, e.admin, AuthorizationScope(ScopeKind.WORKSPACE, e.workspace), admin=True)
    for scope in (AuthorizationScope(ScopeKind.PROJECT, e.workspace, e.nid),
                  AuthorizationScope(ScopeKind.STORYLINE, e.workspace, e.nid, e.storyline)):
        role(e, e.lead, scope)
        permission(e, e.viewer, scope)
    e.bootstraps = {}

    def activate(actor, *, workspace=None, branch=None):
        workspace = workspace or e.workspace
        key = actor, workspace
        if key not in e.bootstraps:
            manager = LocalSessionBootstrap(runtime=RuntimeIdentity.create(), sessions=e.sessions,
                trusted_identity=TrustedLocalIdentity(actor, workspace), expected_origin="http://127.0.0.1:4173")
            token = manager.exchange(bootstrap_secret=manager.take_launcher_secret(),
                runtime_instance_id=manager.runtime.runtime_instance_id,
                origin=manager.expected_origin, remote_host="127.0.0.1").session_token
            registry = PackagedBootstrapRegistry(expected_origin=manager.expected_origin)
            registry.configure(manager)
            e.bootstraps[key] = registry, token
        registry, token = e.bootstraps[key]
        monkeypatch.setattr(e.main, "packaged_bootstrap_registry", registry)
        monkeypatch.setattr(dependencies, "packaged_bootstrap_registry", registry)
        return {"X-Session-Token": token, **({"X-Branch-ID": branch} if branch else {})}

    e.activate = activate
    e.old_headers = activate(e.lead, branch=e.branch)
    e.url = e.prefix + f"/novels/{e.nid}"
    e.documents = e.url + "/experimental/creative/documents"
    return e


def independent(title="Synthetic current draft"):
    return {"mode": "SCREENPLAY", "title": title, "source_independent": True}


def forbidden(response):
    assert response.status_code == 403, response.text
    assert response.json()["detail"]["code"] == "PROJECT_SCOPE_FORBIDDEN", response.text
    assert "PRIVATE_RETIRED" not in response.text


def rows(e):
    return {"roles": deepcopy(e.bundle.authorization.list_role_assignments()),
        "permissions": deepcopy(e.bundle.authorization.list_permission_assignments()),
        "audits": deepcopy(e.bundle.authorization.list_audit_events()),
        "memberships": deepcopy(e.bundle.identity.list_memberships()),
        "bindings": deepcopy(e.bundle.scope.list("project_workspaces")),
        "storylines": deepcopy(e.bundle.scope.list("storylines")),
        "branches": deepcopy(e.bundle.scope.list("branches"))}


def recreate(e, *, workspace=None):
    workspace = workspace or e.workspace
    headers = e.activate(e.admin, workspace=workspace)
    assert checked(e.client.post(e.prefix + "/novels", headers=headers,
        json={"id": e.nid, "title": "Exactly the same public project"}), 201)["id"] == e.nid
    assert e.bundle.scope.project_workspace(e.nid) == workspace
    return headers


def grant_new_incarnation(e, *, workspace=None, reuse_branch=False):
    workspace = workspace or e.workspace
    sid = e.storyline if reuse_branch else "new-storyline-" + uuid4().hex
    bid = e.branch if reuse_branch else "new-branch-" + uuid4().hex
    e.scopes.create_storyline(Storyline(sid, workspace, e.nid, "Current storyline"))
    e.scopes.create_branch(Branch(bid, workspace, e.nid, sid, "Current branch"))
    role(e, e.new_actor, AuthorizationScope(ScopeKind.PROJECT, workspace, e.nid))
    return e.activate(e.new_actor, workspace=workspace, branch=bid), {
        "mode": "collaboration", "novel_id": e.nid, "workspace_id": workspace,
        "storyline_id": sid, "branch_id": bid}


@pytest.mark.parametrize("deletion", ["api", "repository"])
def test_delete_retires_project_authority_without_erasing_workspace_or_audit(retirement, deletion):
    e = retirement
    unrelated = e.novels.create({"id": "retained-" + uuid4().hex, "title": "Unrelated retained project"})["id"]
    try:
        e.scopes.link_project(e.workspace, unrelated)
        role(e, e.lead, AuthorizationScope(ScopeKind.PROJECT, e.workspace, unrelated))
        permission(e, e.viewer, AuthorizationScope(ScopeKind.PROJECT, e.workspace, unrelated))
        before = rows(e)
        if deletion == "api":
            response = e.client.delete(e.url, headers=e.activate(e.admin))
            assert response.status_code == 204, response.text
        else:
            e.novels.delete(e.nid)
        after = rows(e)
        for kind in ("roles", "permissions"):
            assert after[kind] == [item for item in before[kind] if item["scope"].get("project_id") != e.nid]
        assert e.bundle.scope.project_workspace(e.nid) is None
        assert after["bindings"] == [item for item in before["bindings"] if item["id"] != e.nid]
        for kind in ("storylines", "branches"):
            assert after[kind] == [item for item in before[kind] if item.get("project_id") != e.nid]
        assert after["memberships"] == before["memberships"]
        assert {item["id"]: item for item in after["audits"]}.items() >= {item["id"]: item for item in before["audits"]}.items()
        assert e.workspace_grant in after["roles"]
        assert e.novels.get(unrelated)["id"] == unrelated
        recreate(e)
        # Public branch IDs are also deliberately reused. Deleting only branch
        # metadata, while retaining its grants, must not satisfy this contract.
        fresh, _ = grant_new_incarnation(e, reuse_branch=True)
        current = checked(e.client.post(e.documents, headers=fresh, json=independent()), 201)
        assert checked(e.client.get(e.documents + "/" + current["id"], headers=fresh)) == current
        old = e.activate(e.lead, branch=e.branch)
        assert old == e.old_headers
        assert e.sessions.resolve(old["X-Session-Token"]).actor_id == e.lead
        forbidden(e.client.post(e.documents, headers=old, json=independent("Unauthorized new draft")))
        forbidden(e.client.get(e.documents, headers=old))
        forbidden(e.client.get(e.documents + "/" + current["id"], headers=old))
        reader = e.activate(e.viewer, branch=e.branch)
        forbidden(e.client.get(e.documents, headers=reader))
    finally:
        e.novels.delete(unrelated)


@pytest.mark.parametrize("cross_workspace", [False, True])
def test_recreated_incarnation_isolates_data_assets_and_idempotency(retirement, cross_workspace):
    from app.creative.graph import CreativeGraphService
    from test_v2_independent_workspace import services, upload
    e = retirement
    workspace = services(e.root, e.backend, e.config.database_url or "", e.novels, e.chapters)
    graph = CreativeGraphService(e.store, workspace)
    old_doc = checked(e.client.post(e.documents, headers=e.activate(e.lead, branch=e.branch),
        json=independent("PRIVATE_RETIRED")), 201)
    scope = dict(e.scope)
    old_identity = workspace.store.incarnation(e.nid)
    asset_body = upload(key="same-public-import-key")
    old_asset = workspace.import_asset(e.nid, scope, e.admin, asset_body)
    graph_body = {"request_id": "same-public-create-key", "definition": {"title": "Retained private graph", "nodes": [], "edges": []}}
    old_graph = graph.create(e.nid, scope, e.admin, graph_body)
    assert graph.create(e.nid, scope, e.admin, graph_body)["id"] == old_graph["id"]
    assert e.client.delete(e.url, headers=e.activate(e.admin)).status_code == 204
    target = e.workspace
    if cross_workspace:
        target = "new-workspace-" + uuid4().hex
        e.scopes.create_workspace(Workspace(target, "New incarnation workspace"))
        for actor in (e.admin, e.new_actor):
            e.identity.add_membership(WorkspaceMembership(uuid4().hex, actor, target))
        role(e, e.admin, AuthorizationScope(ScopeKind.WORKSPACE, target), admin=True)
    recreate(e, workspace=target)
    fresh, fresh_scope = grant_new_incarnation(e, workspace=target, reuse_branch=not cross_workspace)
    assert workspace.store.incarnation(e.nid) != old_identity
    assert checked(e.client.get(e.documents, headers=fresh)) == {"items": []}
    assert e.client.get(e.documents + "/" + old_doc["id"], headers=fresh).status_code == 404
    assert graph.list(e.nid, fresh_scope, e.admin) == {"items": []}
    with pytest.raises(FileNotFoundError):
        graph.get(e.nid, fresh_scope, e.admin, old_graph["id"])
    with pytest.raises(FileNotFoundError):
        workspace.asset(e.nid, fresh_scope, old_asset["id"])
    for suffix in ("", "/download"):
        response = e.client.get(e.prefix + f"/assets/{old_asset['id']}" + suffix,
            params={"novel_id": e.nid}, headers=fresh)
        assert response.status_code == 404, response.text
    new_asset = workspace.import_asset(e.nid, fresh_scope, e.admin, asset_body)
    new_graph = graph.create(e.nid, fresh_scope, e.admin, graph_body)
    assert new_asset["id"] != old_asset["id"]
    assert new_graph["id"] != old_graph["id"]
    assert workspace.import_asset(e.nid, fresh_scope, e.admin, asset_body)["id"] == new_asset["id"]
    assert graph.create(e.nid, fresh_scope, e.admin, graph_body)["id"] == new_graph["id"]
    current = checked(e.client.post(e.documents, headers=fresh, json=independent()), 201)
    assert checked(e.client.get(e.documents + "/" + current["id"], headers=fresh)) == current
    old = e.activate(e.lead, branch=e.branch)
    assert old == e.old_headers
    forbidden(e.client.post(e.documents, headers=old, json=independent()))
    forbidden(e.client.get(e.documents, headers=old))
    for suffix in ("", "/download"):
        forbidden(e.client.get(e.prefix + f"/assets/{old_asset['id']}" + suffix,
            params={"novel_id": e.nid}, headers=old))


@pytest.mark.parametrize("after_link", [False, True])
def test_create_and_link_failure_never_leaves_orphan_novel_or_binding(retirement, monkeypatch, after_link):
    e = retirement
    nid = "failed-linked-" + uuid4().hex
    before = rows(e)
    original = e.scopes.link_project
    def fail(workspace_id, project_id, **kwargs):
        if after_link:
            original(workspace_id, project_id, **kwargs)
        raise ValueError("SYNTHETIC_LINK_FAILURE")
    with monkeypatch.context() as patch:
        patch.setattr(e.scopes, "link_project", fail)
        response = e.client.post(e.prefix + "/novels", headers=e.activate(e.admin), json={"id": nid, "title": nid})
        assert response.status_code == 400, response.text
        assert response.json()["detail"] == "SYNTHETIC_LINK_FAILURE"
    assert all(item["id"] != nid for item in e.novels.list())
    assert e.bundle.scope.project_workspace(nid) is None
    assert rows(e) == before
    # Failure must not poison this public ID's subsequent legitimate creation.
    created = checked(e.client.post(e.prefix + "/novels", headers=e.activate(e.admin), json={"id": nid, "title": nid}), 201)
    assert created["id"] == nid and e.bundle.scope.project_workspace(nid) == e.workspace
    e.novels.delete(nid)


def test_failed_original_create_rolls_back_its_partial_novel(retirement, monkeypatch):
    e = retirement
    nid = "failed-create-" + uuid4().hex
    before = rows(e)
    # Both branches invoke the actual original owner before the injected fault.
    # PostgreSQL's transaction entrypoint must remain in the shared session.
    method = "_create_in_session" if e.backend == "postgres" else "create"
    original = getattr(e.bundle.novels, method)
    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise ValueError("SYNTHETIC_CREATE_FAILURE")
    with monkeypatch.context() as patch:
        patch.setattr(e.bundle.novels, method, fail)
        response = e.client.post(e.prefix + "/novels", headers=e.activate(e.admin), json={"id": nid, "title": nid})
        assert response.status_code == 400, response.text
        assert response.json()["detail"] == "SYNTHETIC_CREATE_FAILURE"
    assert all(item["id"] != nid for item in e.novels.list())
    assert e.bundle.scope.project_workspace(nid) is None
    assert rows(e) == before


def test_cross_workspace_same_id_creation_cannot_damage_existing_project(retirement):
    e = retirement
    foreign = "foreign-" + uuid4().hex
    e.scopes.create_workspace(Workspace(foreign, "Foreign workspace"))
    e.identity.add_membership(WorkspaceMembership(uuid4().hex, e.admin, foreign))
    role(e, e.admin, AuthorizationScope(ScopeKind.WORKSPACE, foreign), admin=True)
    before, novel = rows(e), e.novels.get(e.nid)
    response = e.client.post(e.prefix + "/novels", headers=e.activate(e.admin, workspace=foreign),
        json={"id": e.nid, "title": "Foreign collision must not replace original"})
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "Already exists: " + e.nid
    assert e.novels.get(e.nid) == novel
    assert rows(e) == before
    assert e.bundle.scope.project_workspace(e.nid) == e.workspace
    response = e.client.post(e.documents, headers=e.activate(e.lead, branch=e.branch), json=independent())
    assert response.status_code == 201, response.text


def test_delayed_old_authorized_delete_cannot_retire_recreated_incarnation(retirement, monkeypatch):
    e = retirement
    entered, release = Event(), Event()
    old = e.activate(e.lead, branch=e.branch)
    token = old["X-Session-Token"]
    original = e.api._authorize_novel_project
    delayed = False
    def authorize(novel_id, session_token, permission, **kwargs):
        nonlocal delayed
        result = original(novel_id, session_token, permission, **kwargs)
        if session_token == token and permission == "domain.write" and not delayed:
            delayed = True
            entered.set()
            assert release.wait(20), "coordinating recreation did not finish"
        return result
    monkeypatch.setattr(e.api, "_authorize_novel_project", authorize)
    with ThreadPoolExecutor(max_workers=1) as pool:
        stale = pool.submit(e.client.delete, e.url, headers=old)
        try:
            assert entered.wait(10), "old request never reached its initial authorization"
            response = e.client.delete(e.url, headers=e.activate(e.admin))
            assert response.status_code == 204, response.text
            recreate(e)
            fresh, _ = grant_new_incarnation(e, reuse_branch=True)
            current = checked(e.client.post(e.documents, headers=fresh, json=independent()), 201)
            # Restore the same original launcher before releasing the delayed
            # request: revoking its session must not hide stale authorization.
            assert e.activate(e.lead, branch=e.branch) == old
        finally:
            release.set()
        forbidden(stale.result(timeout=15))
    fresh = e.activate(e.new_actor, branch=e.branch)
    assert e.novels.get(e.nid)["id"] == e.nid
    assert checked(e.client.get(e.documents + "/" + current["id"], headers=fresh)) == current


@pytest.mark.parametrize("kind", ["role", "permission"])
def test_inflight_grant_finishes_before_retirement_and_cannot_reappear(retirement, monkeypatch, kind):
    e = retirement
    actor, assignment_id = "inflight-" + uuid4().hex, uuid4().hex
    e.identity.create_user(User(actor, actor))
    e.identity.add_membership(WorkspaceMembership("m-" + actor, actor, e.workspace))
    old = e.activate(actor, branch=e.branch)
    scope = AuthorizationScope(ScopeKind.PROJECT, e.workspace, e.nid)
    assignment = (DomainRoleAssignment(assignment_id, actor, DomainRole.DOMAIN_LEAD, ModalityDomain.NOVEL, scope, e.admin)
                  if kind == "role" else PermissionAssignment(assignment_id, actor, "domain.write", ModalityDomain.NOVEL, scope, e.admin))
    entered, release, deleting, deleted = Event(), Event(), Event(), Event()
    original = e.authorization._validate_scope
    def validate(value):
        result = original(value)
        if value == scope and not entered.is_set():
            entered.set()
            assert release.wait(20), "grant lease never released"
        return result
    monkeypatch.setattr(e.authorization, "_validate_scope", validate)
    headers = e.activate(e.admin)
    def delete():
        deleting.set()
        result = e.client.delete(e.url, headers=headers)
        deleted.set()
        return result
    with ThreadPoolExecutor(max_workers=2) as pool:
        grant = pool.submit(getattr(e.authorization, "assign_" + kind), assignment)
        try:
            assert entered.wait(10), "grant never reached real scope validation"
            removal = pool.submit(delete)
            assert deleting.wait(5)
            assert not deleted.wait(.3), "retirement overtook an in-flight original-owner grant"
        finally:
            release.set()
        assert grant.result(timeout=15)["id"] == assignment_id
        response = removal.result(timeout=15)
        assert response.status_code == 204, response.text
    assert not [row for row in e.bundle.authorization.list_role_assignments() if row["scope"].get("project_id") == e.nid]
    assert not [row for row in e.bundle.authorization.list_permission_assignments() if row["scope"].get("project_id") == e.nid]
    assert any(row["target_id"] == assignment_id for row in e.bundle.authorization.list_audit_events())
    recreate(e)
    fresh, _ = grant_new_incarnation(e, reuse_branch=True)
    assert e.client.post(e.documents, headers=fresh, json=independent()).status_code == 201
    assert e.activate(actor, branch=e.branch) == old
    assert e.sessions.resolve(old["X-Session-Token"]).actor_id == actor
    forbidden(e.client.post(e.documents, headers=old, json=independent()))


def test_other_process_unrelated_grant_survives_retirement_rollback(retirement, monkeypatch):
    e = retirement
    foreign, gid = "unrelated-" + uuid4().hex, uuid4().hex
    e.scopes.create_workspace(Workspace(foreign, "Unrelated authorization workspace"))
    e.identity.add_membership(WorkspaceMembership(uuid4().hex, e.viewer, foreign))
    before, novel = rows(e), e.novels.get(e.nid)
    entered, release = Event(), Event()
    original = e.bundle.scope.retire_project
    def fail(*args, **kwargs):
        original(*args, **kwargs)
        entered.set()
        assert release.wait(30), "cross-process writer did not finish coordination"
        raise ValueError("SYNTHETIC_CROSS_PROCESS_ROLLBACK")
    monkeypatch.setattr(e.bundle.scope, "retire_project", fail)
    ready = e.root / "unrelated-grant-ready"
    script = """import json,os,sys
from pathlib import Path
from app.config import Settings
from app.repositories.factory import create_repository_bundle
from app.services.authorization_service import AuthorizationService
from app.services.collaboration_scope_service import CollaborationScopeService
from app.authorization import AuthorizationScope,DomainRole,DomainRoleAssignment,ModalityDomain,ScopeKind
v=json.loads(sys.argv[1]);root=Path(v['root'])
bundle=create_repository_bundle(Settings(storage_backend=v['backend'],database_url=os.environ.get('TEST_POSTGRES_DATABASE_URL',''),novel_data=root),data_root=root)
service=AuthorizationService(bundle.authorization,CollaborationScopeService(bundle.scope,bundle.novels))
Path(v['ready']).write_text('ready',encoding='utf-8')
row=service.assign_role(DomainRoleAssignment(v['gid'],v['actor'],DomainRole.DOMAIN_LEAD,ModalityDomain.NOVEL,AuthorizationScope(ScopeKind.WORKSPACE,v['workspace']),v['actor']))
assert row['id']==v['gid']
if v['backend']=='postgres':bundle.novels.database.engine.dispose()
"""
    headers = e.activate(e.admin)
    process = None
    with ThreadPoolExecutor(max_workers=1) as pool:
        removal = pool.submit(e.client.delete, e.url, headers=headers)
        try:
            assert entered.wait(10), "retirement never reached transactional scope mutation"
            process = subprocess.Popen([sys.executable, "-B", "-c", script, json.dumps({"root": str(e.root),
                "backend": e.backend, "ready": str(ready), "gid": gid, "actor": e.viewer, "workspace": foreign})],
                cwd=Path(__file__).resolve().parents[1], env=os.environ.copy(),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            deadline = monotonic() + 10
            while not ready.exists() and monotonic() < deadline and process.poll() is None:
                Event().wait(.02)
            assert ready.exists(), "real child repository failed to initialize"
            if e.backend == "file":
                Event().wait(.3)
                assert process.poll() is None, "other-process File writer bypassed the shared authorization transaction"
            else:
                stdout, stderr = process.communicate(timeout=15)
                assert process.returncode == 0, stdout + stderr
        finally:
            release.set()
        response = removal.result(timeout=15)
        assert response.status_code == 400, response.text
        assert response.json()["detail"] == "SYNTHETIC_CROSS_PROCESS_ROLLBACK"
    if process is not None and e.backend == "file":
        stdout, stderr = process.communicate(timeout=15)
        assert process.returncode == 0, stdout + stderr
    after = rows(e)
    assert e.novels.get(e.nid) == novel
    for kind in ("permissions", "bindings", "storylines", "branches", "memberships"):
        assert after[kind] == before[kind]
    assert all(item in after["roles"] for item in before["roles"])
    assert any(item["id"] == gid and item["scope"]["workspace_id"] == foreign for item in after["roles"])
    assert all(item in after["audits"] for item in before["audits"])
    assert any(item["target_id"] == gid for item in after["audits"])


@pytest.mark.parametrize("owner", ["scope", "authorization"])
def test_retirement_failure_rolls_back_novel_scope_grants_and_audit(retirement, monkeypatch, owner):
    e = retirement
    before, novel = rows(e), e.novels.get(e.nid)
    repository = getattr(e.bundle, owner)
    original = repository.retire_project
    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise ValueError("SYNTHETIC_RETIREMENT_FAILURE")
    with monkeypatch.context() as patch:
        patch.setattr(repository, "retire_project", fail)
        response = e.client.delete(e.url, headers=e.activate(e.admin))
        assert response.status_code == 400, response.text
        assert response.json()["detail"] == "SYNTHETIC_RETIREMENT_FAILURE"
    assert e.novels.get(e.nid) == novel
    assert rows(e) == before
    # This is a surviving original grant after rollback, not a fabricated allow.
    response = e.client.post(e.documents, headers=e.activate(e.lead, branch=e.branch), json=independent())
    assert response.status_code == 201, response.text
