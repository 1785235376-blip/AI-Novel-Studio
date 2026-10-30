"""Independent original-authority counterexamples for canvas result admission.

Queued rows are used only for early denial controls; they cannot represent a
successful adoption. Approved-result cases use the separate original pipeline.
"""
from copy import deepcopy

import pytest

from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
from app.identity import IdentityStatus
from test_studio_asset_query import rig, shared_scope
from test_cloud_formal_canvas_node import formal_node, create_target, command, result_body, owner_bytes as _owner_bytes

pytestmark = pytest.mark.file_backend_only


def owner_bytes(e, scope=None):
    # Detect even byte-identical replacement of either business owner.
    from hashlib import sha256
    scope = scope or e.scope
    paths = [e.graph.store.store.path(e.nid, scope),
             e.production.image_jobs.for_actor(e.actor)._path(e.nid, scope.get('branch_id'))]
    files = {str(p): (p.stat().st_mtime_ns, sha256(p.read_bytes()).hexdigest())
             for p in paths if p.exists()}
    return _owner_bytes(e, scope), files


@pytest.fixture
def shared_queued(formal_node):
    e = formal_node
    scope, headers = shared_scope(e.rig)
    grant_scope = AuthorizationScope(ScopeKind.PROJECT, "query-workspace", e.nid)
    e.rig.grants.assign_permission(PermissionAssignment("independent-write", "reader", "domain.write",
        ModalityDomain.NOVEL, grant_scope, "independent fixture"))
    target = create_target(e, headers=headers)
    e.workspace.activate(e.nid, scope, "reader")
    value = command(e, target, scope=scope, request_id="independent-shared-queued")
    preview = e.production.preview(e.nid, scope, "reader", value, lambda: None)[0]
    job = e.production.create(e.nid, scope, "reader", {"command": value,
        "reviewed_preview_digest": preview["preview_digest"]}, lambda: None)
    e.actor, e.scope, e.headers = "reader", scope, headers
    return e, target, result_body(e, target, job)


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
@pytest.mark.parametrize("denial,expected", [("missing",401),("invalid",401),("revoked",401),
    ("read",403),("write",403),("membership",403),("other-actor",403),("branch",404)])
def test_real_shared_authority_denials_preserve_all_owner_bytes(shared_queued, prefix, denial, expected):
    e, target, body = shared_queued
    headers = deepcopy(e.headers)
    if denial == "missing": headers.pop("X-Session-Token")
    elif denial == "invalid": headers["X-Session-Token"] = "invalid-session-token"
    elif denial == "revoked": e.rig.sessions.revoke("token-reader")
    elif denial == "read": e.rig.grants.revoke_permission("query-read", "independent fixture")
    elif denial == "write": e.rig.grants.revoke_permission("independent-write", "independent fixture")
    elif denial == "membership": e.rig.identities.set_membership_status("reader", "query-workspace", IdentityStatus.INACTIVE)
    elif denial == "other-actor": headers["X-Session-Token"] = "token-no-grants"
    elif denial == "branch": headers["X-Branch-Id"] = "query-branch-b"
    before = owner_bytes(e)
    result = e.client.post(prefix + f"/projects/{e.nid}/studio/canvas-views/{target['id']}/image-node-result",
        headers=headers, json=body)
    assert result.status_code == expected, result.text
    assert owner_bytes(e) == before
    assert "never-created-output" not in result.text
    if expected != 401:
        assert result.headers["cache-control"] == "no-store"


def test_authorized_shared_queued_control_is_not_fake_success(shared_queued):
    e, target, body = shared_queued
    before = owner_bytes(e)
    result = e.client.post(e.base + f"/canvas-views/{target['id']}/image-node-result", headers=e.headers, json=body)
    assert result.status_code == 409, result.text
    assert owner_bytes(e) == before


def test_plain_canvas_write_only_compatibility_is_not_broadened_to_association(shared_queued):
    e, target, body = shared_queued
    e.rig.grants.revoke_permission("query-read", "independent fixture")
    result = e.client.put(e.base + f"/canvas-views/{target['id']}", headers=e.headers,
        json={"expected_version":target["version"], "definition":target["definition"]})
    assert result.status_code == 200, result.text
    assert result.json()["version"] == target["version"] + 1
    before = owner_bytes(e)
    denied = e.client.post(e.base + f"/canvas-views/{target['id']}/image-node-result", headers=e.headers, json=body)
    assert denied.status_code == 403
    assert owner_bytes(e) == before

from test_canvas_adoption_auth import canvas_studio, studio, approved_canvas, snapshot


@pytest.mark.parametrize("field", ["incarnation", "target-version", "target-digest", "job-id", "job-version", "job-digest", "asset-id", "asset-version", "asset-digest", "unconfirmed"])
def test_approved_source_cannot_be_rebound_by_request_tampering(canvas_studio, field):
    e = canvas_studio
    target, row, body = approved_canvas(e)
    changed = deepcopy(body)
    if field == "incarnation": changed["expected_incarnation"] = "invalid-incarnation"
    elif field == "target-version": changed["expected_version"] += 1
    elif field == "target-digest": changed["expected_definition_digest"] = "0" * 64
    elif field == "job-id": changed["job_id"] = "not-the-approved-job"
    elif field == "job-version": changed["job_version"] += 1
    elif field == "job-digest": changed["job_request_digest"] = "0" * 64
    elif field == "asset-id": changed["asset"]["asset_id"] = "not-the-approved-asset"
    elif field == "asset-version": changed["asset"]["version"] += 1
    elif field == "asset-digest": changed["asset"]["digest"] = "0" * 64
    elif field == "unconfirmed": changed["confirmed"] = False
    before = snapshot(e)
    response = e.client.post(e.base + f"/canvas-views/{target['id']}/image-node-result", headers=e.headers, json=changed)
    assert response.status_code in {404,409,422}, response.text
    assert snapshot(e) == before
    original = e.client.get(e.base + f"/canvas-views/{target['id']}", headers=e.headers)
    assert original.status_code == 200 and original.json() == target
    assert len(e.calls) == 1


def test_approved_job_cannot_be_attached_to_another_canvas(canvas_studio):
    e = canvas_studio
    target, row, body = approved_canvas(e)
    second = e.client.post(e.base + '/canvas-views', headers=e.headers, json={
        'request_id':'independent-other-canvas', 'expected_version':0, 'definition':target['definition']})
    assert second.status_code == 201, second.text
    other = second.json()
    changed = {**body, 'expected_version':other['version'], 'expected_definition_digest':other['definition_digest']}
    before = snapshot(e)
    response = e.client.post(e.base + f"/canvas-views/{other['id']}/image-node-result", headers=e.headers, json=changed)
    assert response.status_code == 409, response.text
    assert snapshot(e) == before


def test_valid_adoption_preserves_exact_provenance_and_only_one_history_step(canvas_studio):
    e = canvas_studio
    target, row, body = approved_canvas(e)
    url = e.base + f"/canvas-views/{target['id']}"
    result = e.client.post(url + '/image-node-result', headers=e.headers, json=body)
    assert result.status_code == 200, result.text
    result = result.json()
    origin = result['definition']['image_node_origin']
    assert origin['target']['canvas_id'] == target['id']
    assert origin['target']['canvas_digest'] == target['definition_digest']
    assert origin['asset'] == body['asset']
    assert origin['job_request_digest'] == row['request_digest']
    assert result['version'] == 2 and result['capacity']['history_used'] == 1
    e.reopen()
    read = e.client.get(url, headers=e.headers)
    assert read.status_code == 200 and read.json() == result


@pytest.mark.parametrize('revocation', ['read','write','membership','session','actor','scope'])
def test_authority_revocation_after_route_admission_is_rechecked(shared_queued, monkeypatch, revocation):
    from app.creative.canvas_views import CreativeCanvasViews
    e, target, body = shared_queued
    original = CreativeCanvasViews.image_node_result
    if revocation == 'actor':
        grant_scope = AuthorizationScope(ScopeKind.PROJECT, 'query-workspace', e.nid)
        for permission in ('domain.read', 'domain.write'):
            e.rig.grants.assign_permission(PermissionAssignment('late-other-'+permission, 'no-grants', permission, ModalityDomain.NOVEL, grant_scope, 'independent fixture'))
    observed = []
    def late(owner, nid, scope, actor, rid, value, guard=lambda: None):
        observed.append((actor, deepcopy(scope)))
        if revocation == 'read': e.rig.grants.revoke_permission('query-read', 'independent late hook')
        elif revocation == 'write': e.rig.grants.revoke_permission('independent-write', 'independent late hook')
        elif revocation == 'membership': e.rig.identities.set_membership_status('reader','query-workspace',IdentityStatus.INACTIVE)
        elif revocation == 'session': e.rig.sessions.revoke('token-reader')
        elif revocation == 'actor':
            from app.actor_context import SessionContext
            e.rig.sessions.register('token-reader', SessionContext('other-session','client','no-grants','query-workspace'))
        elif revocation == 'scope':
            from app.collaboration import Workspace
            e.rig.scopes.create_workspace(Workspace('late-workspace','Synthetic changed workspace'))
            e.rig.scopes.repository.retire_project(e.nid)
            e.rig.scopes.link_project('late-workspace', e.nid)
        return original(owner, nid, scope, actor, rid, value, guard)
    monkeypatch.setattr(CreativeCanvasViews, 'image_node_result', late)
    before = owner_bytes(e)
    result = e.client.post(e.base + f"/canvas-views/{target['id']}/image-node-result", headers=e.headers, json=body)
    assert observed == [('reader', e.scope)], observed
    assert result.status_code == (401 if revocation == 'session' else 403), result.text
    assert owner_bytes(e) == before


def test_project_reincarnation_after_admission_never_receives_old_canvas_result(canvas_studio, monkeypatch):
    from app.creative.canvas_views import CreativeCanvasViews
    e = canvas_studio
    target, row, body = approved_canvas(e)
    original = CreativeCanvasViews.image_node_result
    old_incarnation = body['expected_incarnation']
    seen = []
    def reincarnate(owner, nid, scope, actor, rid, value, guard=lambda: None):
        e.rig.novels.delete(nid)
        assert e.rig.project(nid) == nid
        new = e.workspace.store.incarnation(nid)
        assert new != old_incarnation
        seen.append(new)
        return original(owner, nid, scope, actor, rid, value, guard)
    monkeypatch.setattr(CreativeCanvasViews, 'image_node_result', reincarnate)
    result = e.client.post(e.base + f"/canvas-views/{target['id']}/image-node-result", headers=e.headers, json=body)
    assert len(seen) == 1
    assert result.status_code in (403,409), result.text
    assert e.workspace.store.incarnation(e.nid) == seen[0]
    from app.creative.canvas_view_models import CANVAS_VIEWS
    assert e.graph.store.read(e.nid,e.scope)['collections'].get(CANVAS_VIEWS,{}) == {}
    assert len(e.calls) == 1


def test_approved_job_cannot_be_attached_to_another_project(canvas_studio):
    e = canvas_studio
    target, row, body = approved_canvas(e)
    other_nid = e.rig.project()
    other_base = f'/api/projects/{other_nid}/studio'
    activated = e.client.post(other_base+'/activate', headers=e.headers)
    assert activated.status_code == 200, activated.text
    created = e.client.post(other_base+'/canvas-views', headers=e.headers, json={
        'request_id':'independent-cross-project', 'expected_version':0, 'definition':target['definition']})
    assert created.status_code == 201, created.text
    other = created.json()
    changed = {**body, 'expected_incarnation':e.workspace.store.incarnation(other_nid),
        'expected_version':other['version'], 'expected_definition_digest':other['definition_digest']}
    before = snapshot(e)
    response = e.client.post(other_base + f"/canvas-views/{other['id']}/image-node-result", headers=e.headers, json=changed)
    assert response.status_code in (404,409), response.text
    assert snapshot(e) == before
    current = e.client.get(other_base+f"/canvas-views/{other['id']}", headers=e.headers)
    assert current.status_code == 200 and current.json() == other
