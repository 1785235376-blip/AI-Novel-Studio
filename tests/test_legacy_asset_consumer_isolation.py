"""Legacy asset consumers keep the same project/branch isolation as Studio.

Runs over the existing synthetic rig (real mounted routes, File owners, real
session/membership/grant authority from ``test_studio_asset_query``). Focus:
legacy ``/novels/{nid}/assets`` and ``/assets/{id}`` reads, download/delete,
cross-project export and image-job entry points, and a branch-scoped grant that
must never satisfy a project-level media permission (branch-scoped export access
with an explicit branch selection is an intentional, separate contract).
"""
from __future__ import annotations

import pytest

from test_studio_asset_query import rig, shared_scope  # noqa: F401 - pytest fixture/helper

pytestmark = pytest.mark.file_backend_only


def _assert_denied(response, marker=None):
    assert response.status_code == 403, (response.status_code, response.text[:240])
    if marker:
        assert marker not in response.text


def test_legacy_asset_routes_deny_cross_project_access(rig):
    scope, headers = shared_scope(rig)
    other = rig.project()
    foreign = rig.seed("foreign.png", project_id=other)
    # The foreign asset exists for its own owner on disk (owner-scope load).
    assert rig.assets._load(foreign["id"])["novel_id"] == other

    for method, path in (
        ("get", f"/api/novels/{other}/assets"),
        ("get", f"/api/assets/{foreign['id']}?novel_id={other}"),
        ("get", f"/api/assets/{foreign['id']}/download?novel_id={other}"),
        ("delete", f"/api/assets/{foreign['id']}?novel_id={other}"),
        ("get", f"/api/novels/{other}/image-jobs"),
        ("get", f"/api/exports?novel_id={other}"),
        ("get", f"/api/novels/{other}/export"),
    ):
        response = getattr(rig.client, method)(path, headers=headers)
        _assert_denied(response, "foreign")
    # A legacy media route disabled in collaboration mode stays fail-closed and
    # never returns another project's data.
    legacy_visual = rig.client.get(f"/api/novels/{other}/visual-memories", headers=headers)
    assert legacy_visual.status_code in {403, 501}, legacy_visual.text
    assert "foreign" not in legacy_visual.text
    assert rig.assets._load(foreign["id"])["novel_id"] == other


def test_same_project_cross_branch_asset_does_not_leak(rig):
    from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind

    scope, headers = shared_scope(rig)
    rig.grants.assign_permission(PermissionAssignment(
        "query-write", "reader", "domain.write", ModalityDomain.NOVEL,
        AuthorizationScope(ScopeKind.PROJECT, "query-workspace", rig.nid), "fixture"))
    other_branch = {**scope, "branch_id": "query-branch-b"}
    foreign = rig.seed("branch-b.png", scope_value=other_branch)
    headers_a = {**headers, "X-Branch-Id": "query-branch-a"}

    listed = rig.client.get(f"/api/novels/{rig.nid}/assets", headers=headers_a)
    assert listed.status_code == 200, listed.text
    assert foreign["id"] not in listed.text
    for suffix in ("", "/download"):
        response = rig.client.get(
            f"/api/assets/{foreign['id']}{suffix}?novel_id={rig.nid}", headers=headers_a)
        assert response.status_code == 404, (suffix, response.status_code)
        assert "branch-b.png" not in response.text
    denied_delete = rig.client.delete(
        f"/api/assets/{foreign['id']}?novel_id={rig.nid}", headers=headers_a)
    assert denied_delete.status_code == 404, denied_delete.text
    assert rig.assets._load(foreign["id"])["novel_id"] == rig.nid


def test_branch_scoped_grant_is_not_a_project_level_media_permission(rig):
    from app.actor_context import SessionContext
    from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
    from app.identity import User, WorkspaceMembership

    shared_scope(rig)
    rig.identities.create_user(User("branch-only", "Branch Only"))
    rig.identities.add_membership(WorkspaceMembership("member-branch-only", "branch-only",
                                                      "query-workspace"))
    rig.sessions.register("token-branch-only",
                          SessionContext("session-branch-only", "client", "branch-only",
                                         "query-workspace"))
    rig.grants.assign_permission(PermissionAssignment(
        "query-branch-read", "branch-only", "domain.read", ModalityDomain.NOVEL,
        AuthorizationScope(ScopeKind.BRANCH, "query-workspace", rig.nid, "query-story",
                           "query-branch-a"), "fixture"))
    with_branch = {"X-Session-Token": "token-branch-only", "X-Branch-Id": "query-branch-a"}
    # Project-level media routes require a project-scope grant even when a branch
    # header is supplied; a branch grant is not a project media permission.
    for path in (f"/api/novels/{rig.nid}/assets",
                 f"/api/novels/{rig.nid}/image-jobs"):
        _assert_denied(rig.client.get(path, headers=with_branch))
    # Export listing without an explicit branch selection is project-level.
    no_branch = {"X-Session-Token": "token-branch-only"}
    _assert_denied(rig.client.get(f"/api/exports?novel_id={rig.nid}", headers=no_branch))
    # An explicit branch selection is the established branch-scoped export
    # contract; a branch grant legitimately authorizes that one branch.
    branch_exports = rig.client.get(f"/api/exports?novel_id={rig.nid}&branch_id=query-branch-a",
                                    headers=no_branch)
    assert branch_exports.status_code == 200, branch_exports.text
    assert branch_exports.json()["items"] == []
