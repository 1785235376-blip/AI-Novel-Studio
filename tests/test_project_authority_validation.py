"""Shared project authority through mounted routes and original role services.

The imported fixture parametrizes both API aliases and File/real PostgreSQL.
No authorization, membership, or trusted-session method is replaced.
"""
import base64
from contextlib import contextmanager
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.actor_context import SessionContext
from app.authorization import (
    AuthorizationScope, DomainRole, DomainRoleAssignment, ModalityDomain,
    PermissionAssignment, ScopeKind,
)
from app.collaboration import Branch, Storyline, Workspace
from app.identity import IdentityStatus, WorkspaceMembership
from test_r3_mounted_contracts import checked, mounted, prefix, scoped


def project_read(e, *, kind="permission", permission="domain.read", domain=ModalityDomain.NOVEL):
    scope = AuthorizationScope(ScopeKind.PROJECT, e.workspace, e.nid)
    if kind == "role":
        grant = DomainRoleAssignment(uuid4().hex, e.lead, DomainRole.DOMAIN_LEAD, domain, scope, e.lead)
        e.authorization.assign_role(grant)
    else:
        grant = PermissionAssignment(uuid4().hex, e.lead, permission, domain, scope, e.lead)
        e.authorization.assign_permission(grant)
    return grant


def asset(e, *, branch=None):
    return e.assets.create(e.nid, "synthetic.txt", base64.b64encode(b"SYNTHETIC_SCOPED_ASSET").decode(),
                           "text/plain", "file", branch_id=branch or e.branch)


def asset_reads(e, item, *, headers=None, novel_id=None):
    headers = e.headers if headers is None else headers
    nid = novel_id or e.nid
    return (
        e.client.get(e.prefix + f"/novels/{nid}/assets", headers=headers),
        e.client.get(e.prefix + f"/assets/{item['id']}", params={"novel_id": nid}, headers=headers),
        e.client.get(e.prefix + f"/assets/{item['id']}/download", params={"novel_id": nid}, headers=headers),
    )


def forbidden(responses, code="PROJECT_SCOPE_FORBIDDEN", status=403):
    for response in responses:
        assert checked(response, status)["detail"]["code"] == code
        assert "SYNTHETIC_SCOPED_ASSET" not in response.text


def readable(e, item, *, headers=None):
    listing, metadata, download = asset_reads(e, item, headers=headers)
    assert [row["id"] for row in checked(listing)] == [item["id"]]
    assert checked(metadata)["id"] == item["id"]
    assert download.status_code == 200, download.text
    assert download.content == b"SYNTHETIC_SCOPED_ASSET"


@contextmanager
def another_project(e, *, workspace=None, linked=True):
    nid = "authority-other-" + uuid4().hex
    e.novels.create({"id": nid, "title": "Synthetic other project"})
    try:
        if linked:
            e.scopes.link_project(workspace or e.workspace, nid)
        yield nid
    finally:
        e.novels.delete(nid)


@pytest.mark.parametrize("flags", ["off", "v1"])
def test_valid_project_read_does_not_require_a_branch_scope(mounted, monkeypatch, flags):
    e = scoped(mounted, monkeypatch)
    if flags == "off":
        monkeypatch.setenv("EXPERIMENTAL_FEATURES", "")
    else:
        monkeypatch.setenv("V1_ACCEPTANCE_MODE", "true")
    grant = project_read(e)
    actor = e.sessions.resolve(e.lead)
    # The original authority accepts this genuine PROJECT scope. The router
    # must not send it to the narrower collaboration branch validator first.
    e.membership.require(actor, "domain.read", ModalityDomain.NOVEL, grant.scope)
    response = e.client.get(e.prefix + f"/novels/{e.nid}/media-tasks", headers=e.headers)
    assert checked(response) == {"novel_id": e.nid, "audiobook": [], "motion": []}
    resolved_actor, scope = e.api._authorize_novel_project(e.nid, e.lead, "domain.read")
    assert resolved_actor == actor
    assert scope == grant.scope


def test_assets_require_project_authority_and_preserve_branch_partition(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch)
    item = asset(e)
    other = asset(e, branch=e.other_branch)
    # Original branch role is real and sufficient for branch reads, but cannot
    # satisfy the deliberately stronger PROJECT check for assets.
    forbidden(asset_reads(e, item))
    project_read(e)
    before = (e.authorization.repository.list_role_assignments(e.lead),
              e.authorization.repository.list_permission_assignments(e.lead))
    readable(e, item)
    assert e.client.get(e.prefix + f"/assets/{other['id']}", params={"novel_id": e.nid},
                        headers=e.headers).status_code == 404
    assert before == (e.authorization.repository.list_role_assignments(e.lead),
                      e.authorization.repository.list_permission_assignments(e.lead))


def test_project_read_inherits_downward_but_never_supplies_a_missing_branch(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch)
    e.authorization.revoke_role(e.role, e.lead)
    project_read(e)
    item = asset(e)
    # Existing AuthorizationScope.contains deliberately inherits a PROJECT
    # grant into valid descendant branches; no separate branch grant is needed.
    readable(e, item)
    forbidden(asset_reads(e, item, headers={"X-Session-Token": e.lead}),
              code="BRANCH_SCOPE_REQUIRED", status=400)


@pytest.mark.parametrize("permission,domain", [
    ("domain.write", ModalityDomain.NOVEL),
    ("domain.read", ModalityDomain.IMAGE),
])
def test_project_permission_and_domain_are_not_inferred_from_branch_role(mounted, monkeypatch, permission, domain):
    e = scoped(mounted, monkeypatch)
    project_read(e, permission=permission, domain=domain)
    forbidden(asset_reads(e, asset(e)))


@pytest.mark.parametrize("kind", ["permission", "role"])
def test_project_grant_revocation_is_applied_on_every_read(mounted, monkeypatch, kind):
    e = scoped(mounted, monkeypatch)
    grant = project_read(e, kind=kind)
    item = asset(e)
    readable(e, item)
    getattr(e.authorization, "revoke_" + kind)(grant.id, e.lead)
    forbidden(asset_reads(e, item))


def test_revoked_membership_denies_even_retained_project_and_branch_roles(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch)
    project_read(e, kind="role")
    item = asset(e)
    readable(e, item)
    e.identity.set_membership_status(e.lead, e.workspace, IdentityStatus.INACTIVE)
    forbidden(asset_reads(e, item))
    with pytest.raises(HTTPException) as denied:
        e.api._authorize_novel_project(e.nid, e.lead, "domain.read", branch_id=e.branch)
    assert denied.value.status_code == 403


@pytest.mark.parametrize("same_workspace", [True, False])
def test_project_grants_never_authorize_another_project(mounted, monkeypatch, same_workspace):
    e = scoped(mounted, monkeypatch)
    project_read(e)
    item = asset(e)
    workspace = e.workspace
    if not same_workspace:
        workspace = "other-workspace-" + uuid4().hex
        e.scopes.create_workspace(Workspace(workspace, "Other workspace"))
    with another_project(e, workspace=workspace) as nid:
        forbidden(asset_reads(e, item, novel_id=nid))


def test_current_project_workspace_mapping_is_required(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch)
    project_read(e)
    with another_project(e, linked=False) as nid:
        forbidden(asset_reads(e, asset(e), novel_id=nid))


def test_current_session_workspace_must_match_even_with_memberships_in_both(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch)
    project_read(e)
    item = asset(e)
    readable(e, item)
    workspace = "other-workspace-" + uuid4().hex
    e.scopes.create_workspace(Workspace(workspace, "Other workspace"))
    e.identity.add_membership(WorkspaceMembership(uuid4().hex, e.lead, workspace))
    e.sessions.register(e.lead, SessionContext("new-session", "new-client", e.lead, workspace))
    forbidden(asset_reads(e, item))


def test_cross_project_branch_is_denied_before_asset_reads(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch)
    project_read(e)
    item = asset(e)
    with another_project(e) as nid:
        storyline, branch = "s-" + uuid4().hex, "b-" + uuid4().hex
        e.scopes.create_storyline(Storyline(storyline, e.workspace, nid, "Other story"))
        e.scopes.create_branch(Branch(branch, e.workspace, nid, storyline, "Other branch"))
        forbidden(asset_reads(e, item, headers={**e.headers, "X-Branch-ID": branch}),
                  code="ADAPTATION_SCOPE_FORBIDDEN")
        with pytest.raises(HTTPException) as denied:
            e.api._authorize_novel_project(e.nid, e.lead, "domain.read", branch_id=branch)
        assert denied.value.status_code == 403
        assert denied.value.detail["code"] == "PROJECT_SCOPE_FORBIDDEN"


def test_declared_branch_scope_still_validates_its_storyline_parent(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch)
    project_read(e)
    path = e.prefix + f"/novels/{e.nid}/creation-records"
    assert e.client.get(path, headers=e.headers).status_code == 200
    # Seed an invalid stored relation through the real repository, not a
    # mocked authority. The scope-level validator must reject its missing
    # storyline even though the branch claims this workspace and project.
    branch = "invalid-parent-" + uuid4().hex
    e.scopes.repository.create("branches", {
        "id": branch, "workspace_id": e.workspace, "project_id": e.nid,
        "storyline_id": "missing-" + uuid4().hex, "name": "Invalid parent",
    })
    forbidden((e.client.get(path, headers={**e.headers, "X-Branch-ID": branch}),))


@pytest.mark.parametrize("token,code", [(None, "SESSION_REQUIRED"), ("unknown", "INVALID_SESSION")])
def test_asset_read_still_requires_a_current_trusted_session(mounted, monkeypatch, token, code):
    e = scoped(mounted, monkeypatch)
    project_read(e)
    headers = {"X-Branch-ID": e.branch}
    if token:
        headers["X-Session-Token"] = token
    forbidden(asset_reads(e, asset(e), headers=headers), code=code, status=401)
