"""Original File/API formal-node intent and refusal boundaries, without media.

These cases stop at the original QUEUED Job. They never execute a provider,
inspect/download candidate bytes, approve a Job, or manufacture production
origin/provenance. Approved-result persistence is deliberately NOT_RUN here.
"""
from copy import deepcopy
import hashlib
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.actor_context import SessionContext
from app.asset_providers import AssetProviderRegistry, Automatic1111ImageProvider
from app.audio_production_store import AudioProductionStore
from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
from app.creative.canvas_view_models import CanvasViewDefinition
from app.creative.graph import CreativeGraphService
from app.creative.production_execution import ProductionExecutionService
from app.creative.production_execution_models import MediaCommand
from app.creative.service import CreativeService
from app.creative.workspace import IndependentWorkspaceService
from app.experimental import api as experimental_api
from app.experimental.media import MediaService
from app.experimental.production_lineage import ProductionLineageService
from app.experimental.store import ExperimentalStore, canonical
from app.services.asset_library_service import AssetLibraryService
from app.services.image_job_service import ImageJobService
from test_studio_asset_query import rig, shared_scope


pytestmark = pytest.mark.file_backend_only
FLAGS = ("narrative_production_v2,asset_lineage_v2,ai_execution_v2,"
         "model_broker_v2,author_context_inspector_v2")


class NoExternalCalls:
    def __getattr__(self, name):
        raise AssertionError("Formal-node metadata tests must not call " + name)


@pytest.fixture
def formal_node(rig, monkeypatch):
    from app import asset_provider_config, media_files
    from app.services import image_job_service, studio_image_execution

    monkeypatch.setenv("EXPERIMENTAL_FEATURES", FLAGS)
    registry = AssetProviderRegistry()
    registry.register("automatic1111", Automatic1111ImageProvider(NoExternalCalls(), "http://127.0.0.1:7860"))
    # Configure only the original metadata resolver. This adapter is never
    # invoked and no model, endpoint probe or real transport is available.
    monkeypatch.setattr(asset_provider_config, "load", lambda: {"automatic1111": {
        "default_model": "synthetic-no-weights.safetensors", "enabled": True,
        "local": True, "requires_credential": False}})
    e = SimpleNamespace(rig=rig, client=rig.client, nid=rig.nid, scope=rig.scope,
        actor="local-author", headers={"X-Session-Token": "formal-node-test-host"}, registry=registry)
    e.original_execute = ProductionExecutionService.execute
    rig.sessions.register("formal-node-test-host", SessionContext(
        "formal-node-test-session", "formal-node-test-client", e.actor, "formal-node-test-workspace"))

    forbidden = []
    for target, name in ((ImageJobService, "execute_studio"), (ImageJobService, "accept_studio"),
                         (ImageJobService, "execute"), (ImageJobService, "accept"),
                         (ProductionExecutionService, "execute"), (ProductionExecutionService, "review"),
                         (ProductionExecutionService, "candidate"),
                         (AssetLibraryService, "content"), (AssetLibraryService, "_verified_content"),
                         (image_job_service, "inspect_image"), (image_job_service, "fetch_media_bytes"),
                         (studio_image_execution, "inspect_image"), (studio_image_execution, "fetch_media_bytes"),
                         (media_files, "inspect_image"), (media_files, "fetch_media_bytes")):
        sentinel = Mock(side_effect=AssertionError("Metadata-only formal-node tests must not call " + name))
        monkeypatch.setattr(target, name, sentinel)
        forbidden.append(sentinel)

    def mount(workspace):
        production = ProductionExecutionService(workspace, ImageJobService(rig.root / "formal-node-jobs"),
            registry, NoExternalCalls(), {}, {}, AudioProductionStore(rig.root / "formal-node-audio"),
            NoExternalCalls(), NoExternalCalls())
        graph = CreativeGraphService(workspace.store, workspace)
        graph.configure_media(production)
        for mounted, fresh in ((experimental_api.independent_workspace_service, workspace),
                               (experimental_api.creative_graph_service, graph),
                               (experimental_api.studio_production_service, production)):
            # Existing routes close over these objects. Replace only their
            # temporary original File services, retaining real API authority.
            for name, value in fresh.__dict__.items():
                monkeypatch.setattr(mounted, name, value, raising=False)
        e.workspace, e.production, e.graph = workspace, production, graph

    def reopen():
        raw = ExperimentalStore(rig.root, "file", "")
        assets = AssetLibraryService(rig.root)
        creative = CreativeService(raw, rig.novels, rig.workspace.creative.chapters)
        media = MediaService(raw, rig.novels, rig.workspace.creative.chapters, assets)
        lineage = ProductionLineageService(raw, rig.novels, rig.workspace.creative.chapters, assets, media)
        mount(IndependentWorkspaceService(creative, assets, lineage))

    e.mount, e.reopen = mount, reopen
    mount(rig.workspace)
    e.base = f"/api/projects/{e.nid}/studio"
    activated = e.client.post(e.base + "/activate", headers=e.headers)
    assert activated.status_code == 200, activated.text
    yield e
    for sentinel in forbidden:
        sentinel.assert_not_called()


def create_target(e, *, headers=None, request_id="formal-node-empty-target"):
    response = e.client.post(e.base + "/canvas-views", headers=headers or e.headers, json={
        "request_id": request_id, "expected_version": 0,
        "definition": {"schema_version": 1, "title": "One explicit image-node target", "cards": [],
                       "viewport": {"x": 0, "y": 0, "zoom": 1}}})
    assert response.status_code == 201, response.text
    return response.json()


def command(e, target, *, scope=None, request_id="formal-one-node", prompt="A synthetic node intent; no inference"):
    return {"operation_id": "m5.image.t2i", "request_id": request_id,
        "provider_id": "automatic1111", "model_id": "synthetic-no-weights.safetensors",
        "prompt": prompt, "parameters": {"width": 64, "height": 64, "steps": 1, "seed": 42},
        "allow_cloud": False, "source_snapshots": [], "license_note": "Synthetic queue-only test",
        "canvas_image_node": {"contract": "studio-canvas-image-node/1", "project_id": e.nid,
            "scope": deepcopy(scope or e.scope), "incarnation": e.workspace.store.incarnation(e.nid),
            "canvas_id": target["id"], "canvas_version": target["version"],
            "canvas_digest": target["definition_digest"], "node_id": "generation-node-one",
            "title": "Explicit generation node", "position": {"x": 48, "y": 80},
            "prompt_digest": hashlib.sha256(prompt.encode("utf-8")).hexdigest()}}


def queue(e, value):
    preview = e.client.post(e.base + "/production/preview", headers=e.headers, json=value)
    assert preview.status_code == 200, preview.text
    assert preview.json()["automatic_dispatch"] is False
    response = e.client.post(e.base + "/production/jobs", headers=e.headers, json={
        "command": value, "reviewed_preview_digest": preview.json()["preview_digest"]})
    assert response.status_code == 201, response.text
    return response.json(), preview.json()


def result_body(e, target, job):
    # Deliberately nonexistent output pin. A queued Job has no admitted result,
    # and user-supplied output identity can never upgrade it to APPROVED.
    return {"confirmed": True, "expected_incarnation": e.workspace.store.incarnation(e.nid),
        "expected_version": target["version"], "expected_definition_digest": target["definition_digest"],
        "job_id": job["id"], "job_version": job["version"], "job_request_digest": job["request_digest"],
        "asset": {"asset_id": "never-created-output", "version": 1, "digest": "b" * 64, "kind": "image"}}


def owner_bytes(e, scope=None):
    scope = scope or e.scope
    path = e.production.image_jobs.for_actor(e.actor)._path(e.nid, scope.get("branch_id"))
    return canonical(e.graph.store.read(e.nid, scope)), path.read_bytes() if path.exists() else None


def test_formal_t2i_node_queue_is_original_owner_idempotent_and_cold_readable(formal_node):
    e = formal_node
    target = create_target(e)
    value = command(e, target)
    queued, preview = queue(e, value)
    assert queued["status"] == "QUEUED" and queued["attempt"] == 0
    assert queued["output_candidate"] is None and queued["approved_asset_version"] is None
    assert queued["command"]["canvas_image_node"] == preview["command"]["canvas_image_node"]
    assert queued["command"]["canvas_image_node"] == value["canvas_image_node"]
    repeated, _ = queue(e, value)
    assert repeated == queued
    before = owner_bytes(e)
    e.reopen()
    read = e.client.get(e.base + f"/production/jobs/image/{queued['id']}", headers=e.headers)
    assert read.status_code == 200 and read.json() == queued
    assert read.json()["automatic_replay"] is False
    reopened = e.client.get(e.base + f"/canvas-views/{target['id']}", headers=e.headers)
    assert reopened.status_code == 200 and reopened.json() == target
    assert reopened.json()["definition"]["cards"] == []
    assert "image_node_origin" not in reopened.json()["definition"]
    assert owner_bytes(e) == before


def test_unapproved_formal_job_cannot_save_a_result_or_partially_write_canvas(formal_node):
    e = formal_node
    target = create_target(e)
    job, _ = queue(e, command(e, target))
    body = result_body(e, target, job)
    before = owner_bytes(e)
    url = e.base + f"/canvas-views/{target['id']}/image-node-result"
    for _ in range(2):
        response = e.client.post(url, headers=e.headers, json=body)
        assert response.status_code == 409, response.text
        assert response.headers["cache-control"] == "no-store"
        assert owner_bytes(e) == before
    assert e.client.get(e.base + f"/canvas-views/{target['id']}", headers=e.headers).json() == target


def test_one_original_request_cannot_be_rebound_to_a_different_node(formal_node):
    e = formal_node
    target = create_target(e)
    value = command(e, target)
    job, _ = queue(e, value)
    changed = deepcopy(value)
    changed["canvas_image_node"]["node_id"] = "another-generation-node"
    preview = e.client.post(e.base + "/production/preview", headers=e.headers, json=changed)
    assert preview.status_code == 200, preview.text
    before = owner_bytes(e)
    response = e.client.post(e.base + "/production/jobs", headers=e.headers, json={
        "command": changed, "reviewed_preview_digest": preview.json()["preview_digest"]})
    assert response.status_code == 422, response.text
    assert owner_bytes(e) == before
    read = e.client.get(e.base + f"/production/jobs/image/{job['id']}", headers=e.headers)
    assert read.status_code == 200 and read.json() == job


def test_generic_canvas_create_and_save_cannot_mint_a_client_result_origin(formal_node):
    e = formal_node
    target = create_target(e)
    value = command(e, target)
    job, _ = queue(e, value)
    body = result_body(e, target, job)
    # This is untrusted request JSON, never persisted or treated as an
    # APPROVED Job or formal Asset receipt by the test setup.
    definition = deepcopy(target["definition"])
    definition["cards"] = [{"id": value["canvas_image_node"]["node_id"],
        "position": value["canvas_image_node"]["position"], "asset": body["asset"]}]
    definition["image_node_origin"] = {"contract": "studio-canvas-image-node-result/1",
        "target": value["canvas_image_node"], "job_id": job["id"], "job_version": job["version"],
        "job_request_digest": job["request_digest"], "asset": body["asset"]}
    before = owner_bytes(e)
    create = e.client.post(e.base + "/canvas-views", headers=e.headers, json={
        "request_id": "client-must-not-mint-origin", "expected_version": 0, "definition": definition})
    assert create.status_code == 409, create.text
    assert owner_bytes(e) == before
    save = e.client.put(e.base + f"/canvas-views/{target['id']}", headers=e.headers, json={
        "expected_version": target["version"], "definition": definition})
    assert save.status_code == 409, save.text
    assert owner_bytes(e) == before


@pytest.mark.parametrize("change", ["prompt", "cloud", "position-bool", "version", "digest", "incarnation", "project"])
def test_node_intent_changes_fail_closed_before_queue_creation(formal_node, change):
    e = formal_node
    target = create_target(e)
    value = command(e, target)
    if change == "prompt": value["prompt"] += " changed without a new node digest"
    elif change == "cloud": value["allow_cloud"] = True
    elif change == "position-bool": value["canvas_image_node"]["position"]["x"] = True
    elif change == "version": value["canvas_image_node"]["canvas_version"] += 1
    elif change == "digest": value["canvas_image_node"]["canvas_digest"] = "0" * 64
    elif change == "incarnation": value["canvas_image_node"]["incarnation"] = "file:00000000-0000-0000-0000-000000000000"
    elif change == "project":
        value["canvas_image_node"]["project_id"] = e.rig.project()
        value["canvas_image_node"]["scope"]["novel_id"] = value["canvas_image_node"]["project_id"]
    before = owner_bytes(e)
    response = e.client.post(e.base + "/production/preview", headers=e.headers, json=value)
    assert response.status_code in ({422} if change in {"prompt", "cloud", "position-bool"} else {409}), response.text
    assert owner_bytes(e) == before


def test_changed_saved_target_invalidates_previously_reviewed_queue_preview(formal_node):
    e = formal_node
    target = create_target(e)
    value = command(e, target)
    preview = e.client.post(e.base + "/production/preview", headers=e.headers, json=value)
    assert preview.status_code == 200, preview.text
    definition = deepcopy(target["definition"])
    definition["title"] += " explicitly edited"
    saved = e.client.put(e.base + f"/canvas-views/{target['id']}", headers=e.headers, json={
        "expected_version": target["version"], "definition": definition})
    assert saved.status_code == 200, saved.text
    before = owner_bytes(e)
    response = e.client.post(e.base + "/production/jobs", headers=e.headers, json={
        "command": value, "reviewed_preview_digest": preview.json()["preview_digest"]})
    assert response.status_code == 409, response.text
    assert owner_bytes(e) == before


def test_changed_saved_target_blocks_explicit_execute_before_original_owner_claim(formal_node, monkeypatch):
    e = formal_node
    target = create_target(e)
    job, _ = queue(e, command(e, target))
    definition = deepcopy(target["definition"])
    definition["title"] += " changed after the original queue receipt"
    saved = e.client.put(e.base + f"/canvas-views/{target['id']}", headers=e.headers, json={
        "expected_version": target["version"], "definition": definition})
    assert saved.status_code == 200, saved.text
    before = owner_bytes(e)
    # Exercise only the facade's metadata preclaim rejection. The original
    # ImageJob execute_studio, provider transport and every media operation
    # remain raising sentinels, so an invalid target cannot start execution.
    monkeypatch.setattr(ProductionExecutionService, "execute", e.original_execute)
    response = e.client.post(e.base + f"/production/jobs/image/{job['id']}/execute", headers=e.headers,
        json={"expected_version": job["version"], "expected_request_digest": job["request_digest"]})
    assert response.status_code == 409, response.text
    assert owner_bytes(e) == before
    read = e.client.get(e.base + f"/production/jobs/image/{job['id']}", headers=e.headers)
    assert read.status_code == 200 and read.json() == job
    assert read.json()["status"] == "QUEUED" and read.json()["attempt"] == 0


def test_new_result_route_does_not_accept_client_approval_markers_or_implicit_confirmation(formal_node):
    e = formal_node
    target = create_target(e)
    job, _ = queue(e, command(e, target))
    original = result_body(e, target, job)
    before = owner_bytes(e)
    variants = [{**original, "confirmed": False}, {**original, "confirmed": 1},
                {**original, "approved": True}, {**original, "status": "APPROVED"},
                {**original, "_studio_result_origin": {"contract": "studio-production-result/1"}}]
    for body in variants:
        response = e.client.post(e.base + f"/canvas-views/{target['id']}/image-node-result", headers=e.headers, json=body)
        assert response.status_code == 422, response.text
        assert response.json()["detail"] == {"code": "CREATIVE_CANVAS_REQUEST_INVALID"}
        assert "input" not in response.text and str(e.rig.root) not in response.text
        assert owner_bytes(e) == before


def test_original_canvas_and_unbound_command_serialization_remain_unchanged(formal_node):
    e = formal_node
    target = create_target(e)
    assert CanvasViewDefinition.model_validate(target["definition"]).model_dump() == target["definition"]
    value = command(e, target)
    del value["canvas_image_node"]
    legacy = MediaCommand.model_validate(value).model_dump()
    assert "canvas_image_node" not in legacy
    job, preview = queue(e, value)
    assert "canvas_image_node" not in preview["command"]
    assert "canvas_image_node" not in job["command"]
    assert job["status"] == "QUEUED" and job["output_candidate"] is None


def test_result_route_keeps_original_scope_and_revoked_write_authority(formal_node):
    e = formal_node
    scope, headers = shared_scope(e.rig)
    grant_scope = AuthorizationScope(ScopeKind.PROJECT, "query-workspace", e.nid)
    e.rig.grants.assign_permission(PermissionAssignment("formal-node-write", "reader", "domain.write",
        ModalityDomain.NOVEL, grant_scope, "fixture"))
    target = create_target(e, headers=headers)
    # Host-private model API is deliberately unavailable in unpackaged shared
    # mode. Build only the original scoped queue metadata directly, retaining
    # the real result route's membership and permission checks below.
    e.workspace.activate(e.nid, scope, "reader")
    value = command(e, target, scope=scope, request_id="shared-formal-node")
    preview = e.production.preview(e.nid, scope, "reader", value, lambda: None)[0]
    job = e.production.create(e.nid, scope, "reader", {"command": value,
        "reviewed_preview_digest": preview["preview_digest"]}, lambda: None)
    body = result_body(e, target, job)
    e.actor = "reader"
    before = owner_bytes(e, scope)
    url = e.base + f"/canvas-views/{target['id']}/image-node-result"
    wrong_branch = e.client.post(url, headers={**headers, "X-Branch-Id": "query-branch-b"}, json=body)
    assert wrong_branch.status_code == 404, wrong_branch.text
    assert owner_bytes(e, scope) == before
    e.rig.grants.revoke_permission("formal-node-write", "fixture")
    denied = e.client.post(url, headers=headers, json=body)
    assert denied.status_code == 403, denied.text
    assert owner_bytes(e, scope) == before
    assert e.client.get(e.base + f"/canvas-views/{target['id']}", headers=headers).status_code == 200
    e.rig.grants.revoke_permission("query-read", "fixture")
    assert e.client.get(e.base + f"/canvas-views/{target['id']}", headers=headers).status_code == 403
    assert owner_bytes(e, scope) == before


def test_result_route_requires_source_read_even_when_write_grant_remains(formal_node):
    e = formal_node
    scope, headers = shared_scope(e.rig)
    grant_scope = AuthorizationScope(ScopeKind.PROJECT, "query-workspace", e.nid)
    e.rig.grants.assign_permission(PermissionAssignment("formal-node-write", "reader", "domain.write",
        ModalityDomain.NOVEL, grant_scope, "fixture"))
    target = create_target(e, headers=headers)
    e.workspace.activate(e.nid, scope, "reader")
    value = command(e, target, scope=scope, request_id="read-revoked-formal-node")
    preview = e.production.preview(e.nid, scope, "reader", value, lambda: None)[0]
    job = e.production.create(e.nid, scope, "reader", {"command": value,
        "reviewed_preview_digest": preview["preview_digest"]}, lambda: None)
    body = result_body(e, target, job)
    e.actor = "reader"
    before = owner_bytes(e, scope)
    e.rig.grants.revoke_permission("query-read", "fixture")
    # The original write grant remains effective: a plain CanvasView update
    # still succeeds. Association additionally needs current source read.
    saved = e.client.put(e.base + f"/canvas-views/{target['id']}", headers=headers, json={
        "expected_version": target["version"], "definition": target["definition"]})
    assert saved.status_code == 200, saved.text
    assert saved.json()["version"] == target["version"] + 1
    before_association = owner_bytes(e, scope)
    response = e.client.post(e.base + f"/canvas-views/{target['id']}/image-node-result", headers=headers, json=body)
    assert response.status_code == 403, response.text
    assert owner_bytes(e, scope) == before_association
    assert before_association[1] == before[1]
