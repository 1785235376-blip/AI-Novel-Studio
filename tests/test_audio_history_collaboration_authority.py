"""Audio-history restore under original collaboration authority.

Covers session revocation and membership deactivation after preview: the restore
and history-read paths must fail closed through the original session/membership
authority and must not append a version. File/Windows synthetic only; no real
provider or PostgreSQL.
"""
from __future__ import annotations

import hashlib

import pytest

from app.config import settings
from app.identity import IdentityStatus
from test_audio_history_status_readonly import snapshot
from test_studio_asset_query import rig, shared_scope

pytestmark = pytest.mark.file_backend_only


@pytest.fixture
def collab_history():
    """Collaboration project with a captured audio asset and read+write grants."""
    from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
    from test_studio_asset_query import shared_scope as make_scope
    previous = settings.enable_audio_asset_history
    object.__setattr__(settings, "enable_audio_asset_history", True)
    e = None
    try:
        # The shared_scope helper builds workspace/storyline/branches, users and
        # reader read-grant; it returns the collaboration scope and headers.
        # rig fixture is injected separately, so this fixture only provides the
        # flag; tests call shared_scope themselves.
        yield previous
    finally:
        object.__setattr__(settings, "enable_audio_asset_history", previous)


def setup_collab(e, scope, headers):
    from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
    e.grants.assign_permission(PermissionAssignment(
        "query-write", "reader", "domain.write", ModalityDomain.NOVEL,
        AuthorizationScope(ScopeKind.PROJECT, "query-workspace", e.nid), "fixture"))
    e.workspace.activate(e.nid, scope, "reader")
    return headers


def build_captured(e, scope, headers):
    asset = e.seed("collab-history.wav", "audio", scope_value=scope,
                       required_features=("narrative_production_v2",))
    with e.workspace._asset_scope(e.nid, scope):
        e.assets.update_metadata(asset["id"], {"approved_at": "2026-10-01T00:00:00+00:00"}, branch_id=scope.get("branch_id"))
        e.assets.update_metadata(asset["id"], {"approved_at": None}, branch_id=scope.get("branch_id"))
    listing = e.client.get(
        f"/api/v1/projects/{e.nid}/studio/assets/{asset['id']}/history", headers=headers)
    assert listing.status_code == 200, listing.text
    items = listing.json()["items"]
    assert [item["asset_version"] for item in items] == [3, 2, 1]
    return asset, items[1]["version_id"]


def preview(e, asset, target, headers):
    response = e.client.post(
        f"/api/v1/projects/{e.nid}/studio/assets/{asset['id']}/history/{target}/restore/preview",
        headers=headers, json={"expected_version": 3})
    assert response.status_code == 200, response.text
    return response.json()


def restore(e, asset, target, headers, digest):
    return e.client.post(
        f"/api/v1/projects/{e.nid}/studio/assets/{asset['id']}/history/{target}/restore",
        headers=headers, json={"expected_version": 3, "expected_restore_digest": digest})


def test_revoked_session_fails_restore_and_history_read_closed(collab_history, rig):
    e = rig
    scope, headers = shared_scope(e)
    headers = setup_collab(e, scope, headers)
    asset, target = build_captured(e, scope, headers)
    plan = preview(e, asset, target, headers)
    e.sessions.revoke("token-reader")
    before = snapshot(e.root)
    denied = restore(e, asset, target, headers, plan["restore_digest"])
    assert denied.status_code in {401, 403}, denied.text
    read = e.client.get(
        f"/api/v1/projects/{e.nid}/studio/assets/{asset['id']}/history", headers=headers)
    assert read.status_code in {401, 403}, read.text
    assert snapshot(e.root) == before
    with e.workspace._asset_scope(e.nid, scope):
        meta = e.assets._load(asset["id"])
    assert meta["version"] == 3 and "_audio_history_restore_origin" not in meta


def test_deactivated_membership_fails_restore_closed(collab_history, rig):
    e = rig
    scope, headers = shared_scope(e)
    headers = setup_collab(e, scope, headers)
    asset, target = build_captured(e, scope, headers)
    plan = preview(e, asset, target, headers)
    e.identities.set_membership_status("reader", "query-workspace", IdentityStatus.INACTIVE)
    before = snapshot(e.root)
    denied = restore(e, asset, target, headers, plan["restore_digest"])
    assert denied.status_code in {401, 403}, denied.text
    assert snapshot(e.root) == before
    with e.workspace._asset_scope(e.nid, scope):
        meta = e.assets._load(asset["id"])
    assert meta["version"] == 3 and "_audio_history_restore_origin" not in meta


def test_restore_without_write_grant_is_denied_before_append(collab_history, rig):
    e = rig
    scope, headers = shared_scope(e)
    asset = e.seed("read-only.wav", "audio", scope_value=scope,
                       required_features=("narrative_production_v2",))
    with e.workspace._asset_scope(e.nid, scope):
        e.assets.update_metadata(asset["id"], {"approved_at": "2026-10-01T00:00:00+00:00"}, branch_id=scope.get("branch_id"))
    e.workspace.activate(e.nid, scope, "reader")
    listing = e.client.get(
        f"/api/v1/projects/{e.nid}/studio/assets/{asset['id']}/history", headers=headers)
    assert listing.status_code == 200, listing.text
    target = listing.json()["items"][0]["version_id"]
    preview_response = e.client.post(
        f"/api/v1/projects/{e.nid}/studio/assets/{asset['id']}/history/{target}/restore/preview",
        headers=headers, json={"expected_version": 2})
    assert preview_response.status_code == 200, preview_response.text
    before = snapshot(e.root)
    denied = e.client.post(
        f"/api/v1/projects/{e.nid}/studio/assets/{asset['id']}/history/{target}/restore",
        headers=headers,
        json={"expected_version": 2,
              "expected_restore_digest": preview_response.json()["restore_digest"]})
    assert denied.status_code in {401, 403}, denied.text
    assert snapshot(e.root) == before
    with e.workspace._asset_scope(e.nid, scope):
        assert e.assets._load(asset["id"])["version"] == 2


