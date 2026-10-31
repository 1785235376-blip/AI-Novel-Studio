"""Original File/API recovery of a queued formal node with a lost response.

Only original preview/create metadata and read-only recovery are exercised.
No model/provider execution, media read, acceptance or approval is performed.
The positive reconstructs fresh File services in this same test process.
"""
from copy import deepcopy
import hashlib
import json
from unittest.mock import Mock
from uuid import uuid4

from fastapi import HTTPException
import pytest

from app.actor_context import SessionContext
from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
from app.creative.production_execution import ProductionExecutionService
from app.experimental import api as experimental_api
from app.services.image_job_service import ImageJobService
from app.services.studio_image_execution import _binding
from test_cloud_formal_canvas_node import formal_node, command as formal_command
from test_studio_asset_query import rig, shared_scope


pytestmark = pytest.mark.file_backend_only
PROMPT = "Synthetic queue recovery prompt; no inference"


@pytest.fixture
def queue_recovery(formal_node, monkeypatch):
    e = formal_node
    e.resolve_url = e.base + "/production/jobs/image/resolve-create"
    forbidden = []
    # Exact resolution must not fall back to a projected list or latest Job.
    for target, name in ((ProductionExecutionService, "list"), (ImageJobService, "list_studio")):
        sentinel = Mock(side_effect=AssertionError("Exact queue recovery must not call " + name))
        monkeypatch.setattr(target, name, sentinel)
        forbidden.append(sentinel)
    yield e
    for sentinel in forbidden:
        sentinel.assert_not_called()


def target_command(e, *, request_id="original-formal-node-queue", scope=None, actor=None, headers=None):
    selected = scope or e.scope
    title = "One durable node queue intent"
    intent = {"contract": "studio-canvas-image-node-create/1", "project_id": e.nid,
        "scope": deepcopy(selected), "incarnation": e.workspace.store.incarnation(e.nid),
        "node_id": "queue-recovery-node", "title": title, "position": {"x": 48, "y": 80},
        "prompt_digest": hashlib.sha256(PROMPT.encode()).hexdigest()}
    body = {"request_id": "canvas-" + request_id, "expected_version": 0,
        "definition": {"schema_version": 1, "title": title, "cards": [], "viewport": {"x": 0, "y": 0, "zoom": 1}},
        "image_node_intent": intent}
    if actor is None:
        response = e.client.post(e.base + "/canvas-views", headers=headers or e.headers, json=body)
        assert response.status_code == 201, response.text
        target = response.json()
    else:
        # Explicit original-owner fixture setup for a different private actor;
        # this does not manufacture a Job state or an authorization grant.
        target = e.graph.canvas_views.create(e.nid, selected, actor, body, lambda: None)
    value = formal_command(e, target, scope=selected, request_id=request_id, prompt=PROMPT)
    for key in ("node_id", "title", "position", "prompt_digest"):
        value["canvas_image_node"][key] = deepcopy(intent[key])
    return target, value


def preview(e, value):
    response = e.client.post(e.base + "/production/preview", headers=e.headers, json=value)
    assert response.status_code == 200, response.text
    assert response.json()["automatic_dispatch"] is False
    return response.json()


def queue(e, value, reviewed=None):
    reviewed = reviewed or preview(e, value)
    response = e.client.post(e.base + "/production/jobs", headers=e.headers, json={
        "command": value, "reviewed_preview_digest": reviewed["preview_digest"]})
    assert response.status_code == 201, response.text
    row = response.json()
    assert row["status"] == "QUEUED" and row["attempt"] == 0 and row["output_candidate"] is None
    return row, reviewed


def lookup(value, reviewed):
    return {"request_id": value["request_id"], "request_digest": reviewed["request_digest"],
            "canvas_image_node": deepcopy(value["canvas_image_node"])}


def resolve(e, body, *, headers=None, nid=None):
    url = f"/api/projects/{nid}/studio/production/jobs/image/resolve-create" if nid else e.resolve_url
    return e.client.post(url, headers=e.headers if headers is None else headers, json=body)


def original_files(e, *, scope=None, actor=None):
    selected, principal = scope or e.scope, actor or e.actor
    paths = [e.graph.store.path(e.nid, selected),
        e.production.image_jobs.for_actor(principal)._path(e.nid, selected.get("branch_id")),
        e.rig.root / "novels" / e.nid / "creative_project_v2.json"]
    return {str(path.relative_to(e.rig.root)): (path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns)
            if path.exists() else None for path in paths}


def original_jobs(e, *, scope=None, actor=None):
    selected, principal = scope or e.scope, actor or e.actor
    path = e.production.image_jobs.for_actor(principal)._path(e.nid, selected.get("branch_id"))
    return json.loads(path.read_text()) if path.exists() else []


def assert_original(response, row):
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.json() == row
    assert response.json()["automatic_replay"] is False


def test_committed_queue_with_lost_response_recovers_exact_original_after_fresh_file_services(queue_recovery, monkeypatch):
    e = queue_recovery
    target, value = target_command(e)
    reviewed = preview(e, value)
    mounted = experimental_api.studio_production_service
    create_original = mounted.create

    def lose_ack(*args, **kwargs):
        create_original(*args, **kwargs)
        raise HTTPException(503, {"code": "SYNTHETIC_ORIGINAL_QUEUE_ACK_LOST"})

    with monkeypatch.context() as fault:
        fault.setattr(mounted, "create", lose_ack)
        failed = e.client.post(e.base + "/production/jobs", headers=e.headers, json={
            "command": value, "reviewed_preview_digest": reviewed["preview_digest"]})
        assert failed.status_code == 503, failed.text
    rows = original_jobs(e)
    assert len(rows) == 1 and rows[0]["status"] == "QUEUED" and rows[0]["attempt"] == 0
    job_id = rows[0]["id"]
    expected = e.client.get(e.base + f"/production/jobs/image/{job_id}", headers=e.headers).json()
    before = original_files(e)
    old = (e.graph, e.production, e.workspace.assets, e.production.image_jobs)
    e.reopen()
    assert all(a is not b for a, b in zip(old, (e.graph, e.production, e.workspace.assets, e.production.image_jobs)))
    assert_original(resolve(e, lookup(value, reviewed)), expected)
    assert_original(resolve(e, lookup(value, reviewed)), expected)
    assert original_files(e) == before
    assert len(original_jobs(e)) == 1
    assert e.client.get(e.base + f"/canvas-views/{target['id']}", headers=e.headers).json() == target


def test_original_create_idempotency_and_resolve_do_not_append_a_second_job(queue_recovery):
    e = queue_recovery
    _target, value = target_command(e)
    row, reviewed = queue(e, value)
    repeated, _ = queue(e, value, reviewed)
    assert repeated == row and len(original_jobs(e)) == 1
    later = deepcopy(value)
    later["request_id"] = "later-different-request"
    later_row, _ = queue(e, later)
    assert later_row["id"] != row["id"] and len(original_jobs(e)) == 2
    before = original_files(e)
    assert_original(resolve(e, lookup(value, reviewed)), row)
    assert original_files(e) == before


def test_not_found_snapshot_does_not_create_and_a_late_original_commit_needs_new_lookup(queue_recovery):
    e = queue_recovery
    _target, value = target_command(e)
    reviewed = preview(e, value)
    before = original_files(e)
    original_queue_directory = e.production.image_jobs.for_actor(e.actor)._path(e.nid, None).parent
    directory_existed = original_queue_directory.exists()
    missing = resolve(e, lookup(value, reviewed))
    assert missing.status_code == 404, missing.text
    assert original_files(e) == before and not original_jobs(e)
    assert original_queue_directory.exists() is directory_existed
    row, _ = queue(e, value, reviewed)
    committed = original_files(e)
    e.reopen()
    assert_original(resolve(e, lookup(value, reviewed)), row)
    assert original_files(e) == committed and len(original_jobs(e)) == 1


@pytest.mark.parametrize("field", ["request", "digest", "node", "prompt", "incarnation", "version", "project"])
def test_mismatched_request_or_capsule_never_recovers_a_latest_job(queue_recovery, field):
    e = queue_recovery
    _target, value = target_command(e)
    row, reviewed = queue(e, value)
    body = lookup(value, reviewed)
    if field == "request": body["request_id"] = "another-original-request"
    elif field == "digest": body["request_digest"] = "0" * 64
    elif field == "node": body["canvas_image_node"]["node_id"] = "another-node"
    elif field == "prompt": body["canvas_image_node"]["prompt_digest"] = "0" * 64
    elif field == "incarnation": body["canvas_image_node"]["incarnation"] = "file:00000000-0000-4000-8000-000000000001"
    elif field == "version": body["canvas_image_node"]["canvas_version"] += 1
    else:
        body["canvas_image_node"]["project_id"] = e.rig.project()
        body["canvas_image_node"]["scope"]["novel_id"] = body["canvas_image_node"]["project_id"]
    before = original_files(e)
    response = resolve(e, body)
    assert response.status_code == (404 if field == "request" else 409), response.text
    assert row["id"] not in response.text and original_files(e) == before


def test_target_version_aba_invalidates_recovery_without_changing_original_job(queue_recovery):
    e = queue_recovery
    target, value = target_command(e)
    row, reviewed = queue(e, value)
    changed = deepcopy(target["definition"])
    changed["title"] = "Changed target after the original queue"
    for version, definition in ((1, changed), (2, target["definition"])):
        response = e.client.put(e.base + f"/canvas-views/{target['id']}", headers=e.headers,
            json={"expected_version": version, "definition": definition})
        assert response.status_code == 200, response.text
    before = original_files(e)
    response = resolve(e, lookup(value, reviewed))
    assert response.status_code == 409, response.text
    assert original_files(e) == before
    assert e.client.get(e.base + f"/production/jobs/image/{row['id']}", headers=e.headers).json() == row


def test_a_client_node_marker_cannot_relabel_an_original_unbound_formal_job(queue_recovery):
    e = queue_recovery
    _target, bound = target_command(e)
    legacy = deepcopy(bound)
    del legacy["canvas_image_node"]
    row, reviewed = queue(e, legacy)
    assert "canvas_image_node" not in row["command"]
    before = original_files(e)
    # Correct original request digest is insufficient when the original
    # stored command never carried this node/canvas binding.
    response = resolve(e, lookup(bound, reviewed))
    assert response.status_code == 409, response.text
    assert row["id"] not in response.text and original_files(e) == before


def test_duplicate_original_request_rows_are_ambiguous_not_first_match(queue_recovery):
    e = queue_recovery
    _target, value = target_command(e)
    row, reviewed = queue(e, value)
    owner = e.production.image_jobs.for_actor(e.actor)

    def corrupt(rows):
        duplicate = deepcopy(rows[0]); duplicate["id"] = str(uuid4())
        duplicate["binding_digest"] = _binding(duplicate)
        rows.append(duplicate)
        return duplicate

    owner._mutate(e.nid, None, corrupt)
    before = original_files(e)
    response = resolve(e, lookup(value, reviewed))
    assert response.status_code == 409, response.text
    repeated = e.client.post(e.base + "/production/jobs", headers=e.headers, json={
        "command": value, "reviewed_preview_digest": reviewed["preview_digest"]})
    assert repeated.status_code == 409, repeated.text
    assert original_files(e) == before and row["id"] not in response.text


def test_duplicate_job_id_across_distinct_original_requests_is_not_resolved(queue_recovery):
    e = queue_recovery
    _target, first = target_command(e)
    row, reviewed = queue(e, first)
    later = deepcopy(first)
    later["request_id"] = "different-request-with-duplicate-job-id"
    other, _ = queue(e, later)
    owner = e.production.image_jobs.for_actor(e.actor)

    def corrupt(rows):
        duplicate = next(item for item in rows if item["id"] == other["id"])
        # Both commands/request digests come from actual original admissions.
        # Only persisted Job identity is deliberately corrupted, retaining
        # a valid immutable binding so request-only matching is insufficient.
        duplicate["id"] = row["id"]
        duplicate["binding_digest"] = _binding(duplicate)
        return duplicate

    owner._mutate(e.nid, None, corrupt)
    before = original_files(e)
    rows = original_jobs(e)
    assert len({item["context"]["request_id"] for item in rows}) == 2
    assert len({item["id"] for item in rows}) == 1
    response = resolve(e, lookup(first, reviewed))
    assert response.status_code == 409, response.text
    assert row["id"] not in response.text and original_files(e) == before


def test_original_host_revocation_and_same_token_binding_aba_refuse_late_resolution(queue_recovery, monkeypatch):
    e = queue_recovery
    _target, value = target_command(e)
    row, reviewed = queue(e, value)
    body = lookup(value, reviewed)
    original = experimental_api.studio_production_service.view
    fired = False

    def rotate_binding(*args, **kwargs):
        nonlocal fired
        result = original(*args, **kwargs)
        if not fired:
            fired = True
            e.rig.sessions.revoke(e.headers["X-Session-Token"])
            e.rig.sessions.register(e.headers["X-Session-Token"], SessionContext(
                "formal-node-test-session", "formal-node-test-client", e.actor, "formal-node-test-workspace"))
        return result

    before = original_files(e)
    with monkeypatch.context() as race:
        race.setattr(experimental_api.studio_production_service, "view", rotate_binding)
        denied = resolve(e, body)
        # Preserve original session/authentication status: generation expiry
        # may be 401, while a still-authenticated capability denial is 403.
        assert fired and denied.status_code in {401, 403}, denied.text
        assert row["id"] not in denied.text and original_files(e) == before
    assert_original(resolve(e, body), row)
    e.rig.sessions.revoke(e.headers["X-Session-Token"])
    denied = resolve(e, body)
    assert denied.status_code in {401, 403}, denied.text
    assert original_files(e) == before


def test_resolve_does_not_recompute_changed_provider_route_or_execute_the_job(queue_recovery, monkeypatch):
    e = queue_recovery
    _target, value = target_command(e)
    row, reviewed = queue(e, value)
    from app import asset_provider_config
    with monkeypatch.context() as read_only:
        probe = Mock(side_effect=AssertionError("Queue lookup must not recompute provider configuration"))
        read_only.setattr(asset_provider_config, "load", probe)
        before = original_files(e)
        assert_original(resolve(e, lookup(value, reviewed)), row)
        assert original_files(e) == before
        probe.assert_not_called()


def test_current_cancelled_original_row_is_read_without_requeue_or_old_version_guess(queue_recovery):
    e = queue_recovery
    _target, value = target_command(e)
    row, reviewed = queue(e, value)
    cancelled = e.client.post(e.base + f"/production/jobs/image/{row['id']}/cancel", headers=e.headers,
        json={"expected_version": row["version"], "expected_request_digest": row["request_digest"]})
    assert cancelled.status_code == 200, cancelled.text
    current = cancelled.json()
    assert current["status"] == "CANCELLED" and current["version"] > row["version"]
    before = original_files(e)
    assert_original(resolve(e, lookup(value, reviewed)), current)
    assert original_files(e) == before and len(original_jobs(e)) == 1


def test_other_actor_private_queue_is_not_discovered_by_request_id(queue_recovery):
    e = queue_recovery
    other = "another-private-author"
    _target, value = target_command(e, actor=other, request_id="other-private-request")
    reviewed = e.production.preview(e.nid, e.scope, other, value, lambda: None)[0]
    row = e.production.create(e.nid, e.scope, other, {"command": value,
        "reviewed_preview_digest": reviewed["preview_digest"]}, lambda: None)
    before = original_files(e), original_files(e, actor=other)
    response = resolve(e, lookup(value, reviewed))
    assert response.status_code == 404, response.text
    assert row["id"] not in response.text
    assert (original_files(e), original_files(e, actor=other)) == before


def test_source_read_revocation_uses_real_original_scope_authority_without_relaxing_shared_host(queue_recovery):
    e = queue_recovery
    scope, headers = shared_scope(e.rig)
    grant_scope = AuthorizationScope(ScopeKind.PROJECT, "query-workspace", e.nid)
    e.rig.grants.assign_permission(PermissionAssignment("queue-recovery-write", "reader", "domain.write",
        ModalityDomain.NOVEL, grant_scope, "fixture"))
    e.workspace.activate(e.nid, scope, "reader")
    _target, value = target_command(e, scope=scope, actor="reader", request_id="shared-original-queue")

    def guard(permission):
        def current():
            assert experimental_api.authorize(e.nid, headers["X-Session-Token"], scope["branch_id"], permission) == ("reader", scope)
        return current

    reviewed = e.production.preview(e.nid, scope, "reader", value, guard("domain.read"))[0]
    row = e.production.create(e.nid, scope, "reader", {"command": value,
        "reviewed_preview_digest": reviewed["preview_digest"]}, guard("domain.write"))
    before = original_files(e, scope=scope, actor="reader")
    # This unpackaged shared Host route intentionally remains unsupported;
    # no test bypasses it to manufacture a successful HTTP admission.
    assert resolve(e, lookup(value, reviewed), headers=headers).status_code == 403
    assert e.production.resolve_image_node_create(e.nid, scope, "reader", lookup(value, reviewed), guard("domain.read")) == row
    e.rig.grants.revoke_permission("query-read", "fixture")
    guard("domain.write")()
    with pytest.raises(HTTPException) as denied:
        e.production.resolve_image_node_create(e.nid, scope, "reader", lookup(value, reviewed), guard("domain.read"))
    assert denied.value.status_code == 403
    assert original_files(e, scope=scope, actor="reader") == before


def test_missing_project_identity_and_malformed_lookup_do_not_provision_or_leak(queue_recovery):
    e = queue_recovery
    _target, value = target_command(e)
    row, reviewed = queue(e, value)
    body = lookup(value, reviewed)
    variants = [{**deepcopy(body), "approved": True}, {**deepcopy(body), "actor_id": "other"},
                {**deepcopy(body), "canvas_image_node": None}]
    before = original_files(e)
    for variant in variants:
        response = resolve(e, variant)
        assert response.status_code == 422, response.text
        assert "input" not in response.text and str(e.rig.root) not in response.text
    foreign = e.rig.project()
    marker = e.rig.root / "novels" / foreign / "creative_project_v2.json"
    assert not marker.exists()
    response = resolve(e, body, nid=foreign)
    assert response.status_code in {404, 409}, response.text
    assert not marker.exists() and row["id"] not in response.text
    assert original_files(e) == before
