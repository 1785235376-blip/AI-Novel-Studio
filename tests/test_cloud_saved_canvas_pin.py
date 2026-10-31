"""Saved original-owner manual asset cards; no generated-result acceptance.

These cases prove display persistence only. Synthetic manual Asset state is
created through its original project scope. Legacy APPROVED markers are fixture
setup and never become formal production provenance. No review or media work.
"""
import copy

import pytest

from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
from app.creative.graph import CreativeGraphService
from app.creative.service import CreativeService
from app.creative.workspace import IndependentWorkspaceService
from app.experimental import api as experimental_api
from app.experimental.media import MediaService
from app.experimental.production_lineage import ProductionLineageService
from app.experimental.store import ExperimentalStore, canonical
from app.repository import now
from app.services.asset_library_service import AssetLibraryService
from test_cloud_canvas_image_queue import queue_command
from test_cloud_canvas_review_readback import review_readback
from test_studio_asset_query import rig, shared_scope


pytestmark = pytest.mark.file_backend_only


def reference(asset):
    return {"asset_id": asset["id"], "version": asset["version"], "digest": asset["sha256"], "kind": asset["kind"]}


def definition(asset):
    return {"schema_version": 1, "title": "Explicit manual asset display card",
            "cards": [{"id": "original-image-card", "position": {"x": 40, "y": 80}, "asset": reference(asset)}],
            "viewport": {"x": 0, "y": 0, "zoom": 1}}


@pytest.fixture
def saved_canvas(review_readback, monkeypatch):
    e = review_readback
    e.scope = e.rig.scope
    e.base = f"/api/projects/{e.nid}/studio/canvas-views"

    def mount(workspace):
        # Routes close over these original service objects. Keep the mounted
        # invocation/resolver and swap only the temporary File owner instances.
        mounted_workspace = experimental_api.independent_workspace_service
        for name, value in workspace.__dict__.items():
            monkeypatch.setattr(mounted_workspace, name, value)
        fresh = CreativeGraphService(workspace.store, workspace)
        mounted_graph = experimental_api.creative_graph_service
        for name, value in fresh.__dict__.items():
            monkeypatch.setattr(mounted_graph, name, value)
        e.graph = mounted_graph

    e.mount = mount
    mount(e.rig.workspace)
    return e


def create(e, asset, *, headers=None, request_id="manual-card-create"):
    response = e.client.post(e.base, headers=headers, json={"request_id": request_id,
        "expected_version": 0, "definition": definition(asset)})
    assert response.status_code == 201, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def save_body(e, view, *, headers=None):
    history = e.client.get(f"{e.base}/{view['id']}/history", headers=headers)
    assert history.status_code == 200, history.text
    history = history.json()
    assert history["current_version"] == view["version"]
    assert history["current_definition_digest"] == view["definition_digest"]
    changed = copy.deepcopy(view["definition"])
    changed["cards"][0]["position"]["x"] += 24
    return {"expected_version": view["version"], "expected_incarnation": history["incarnation"],
            "expected_definition_digest": view["definition_digest"],
            "expected_card": {"card_id": view["definition"]["cards"][0]["id"],
                              "source": view["definition"]["cards"][0]["asset"]}, "definition": changed}


def source_state(e, scope=None):
    return canonical(e.graph.store.read(e.nid, scope or e.scope))


def test_manual_original_owner_create_full_cas_save_and_cold_reopen(saved_canvas):
    e = saved_canvas
    asset = e.rig.seed("manual-known-bytes.png")
    view = create(e, asset)
    assert view["definition"]["cards"][0]["asset"] == reference(asset)
    assert view["reference_states"] == [{"card_id": "original-image-card", "state": "CURRENT_METADATA", "filename": asset["filename"]}]
    body = save_body(e, view)
    response = e.client.put(f"{e.base}/{view['id']}", json=body)
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["version"] == 2 and saved["definition"] == body["definition"]
    assert saved["execution_authority"] is False and saved["binary_content_verified"] is False
    raw = ExperimentalStore(e.rig.root, "file", "")
    assets = AssetLibraryService(e.rig.root)
    creative = CreativeService(raw, e.rig.novels, e.rig.workspace.creative.chapters)
    media = MediaService(raw, e.rig.novels, e.rig.workspace.creative.chapters, assets)
    lineage = ProductionLineageService(raw, e.rig.novels, e.rig.workspace.creative.chapters, assets, media)
    e.mount(IndependentWorkspaceService(creative, assets, lineage))
    assert e.client.get(f"{e.base}/{saved['id']}").json() == saved
    history = e.client.get(f"{e.base}/{saved['id']}/history").json()
    assert history["incarnation"] == body["expected_incarnation"] and history["current_version"] == 2
    assert [entry["version"] for entry in history["items"]] == [1, 2]
    assert saved["id"] in [row["id"] for row in e.client.get(e.base).json()["items"]]


def test_each_original_save_fence_rejects_without_partial_scope_write(saved_canvas):
    e = saved_canvas
    view = create(e, e.rig.seed("manual-fenced.png"))
    body = save_body(e, view)
    before = source_state(e)
    for key, replacement in (("expected_version", 2), ("expected_definition_digest", "0" * 64),
                             ("expected_incarnation", "retired-project-incarnation"),
                             ("expected_card", {"card_id": "missing-origin-card", "source": body["expected_card"]["source"]})):
        changed = {**copy.deepcopy(body), key: replacement}
        response = e.client.put(f"{e.base}/{view['id']}", json=changed)
        assert response.status_code == 409, response.text
        assert source_state(e) == before
        assert e.client.get(f"{e.base}/{view['id']}").json() == view


@pytest.mark.parametrize("invalid_source", ["stale-version", "other-project"])
def test_original_card_source_rejections_leave_existing_canvas_unchanged(saved_canvas, invalid_source):
    e = saved_canvas
    asset = e.rig.seed("manual-current-card.png")
    view = create(e, asset)
    body = save_body(e, view)
    if invalid_source == "stale-version":
        with e.rig.workspace._asset_scope(e.nid, e.scope):
            e.assets.update_metadata(asset["id"], {"scene_id": "changed-scene"}, expected_version=asset["version"])
    else:
        foreign = e.rig.seed("foreign-card.png", project_id=e.rig.project())
        body["definition"]["cards"][0]["asset"] = reference(foreign)
    before = source_state(e)
    response = e.client.put(f"{e.base}/{view['id']}", json=body)
    assert response.status_code == 409, response.text
    assert source_state(e) == before
    current = e.client.get(f"{e.base}/{view['id']}").json()
    assert current["version"] == view["version"] and current["definition_digest"] == view["definition_digest"]


def test_saved_card_scope_and_revoked_permissions_use_real_original_authority(saved_canvas):
    e = saved_canvas
    scope, headers = shared_scope(e.rig)
    grant_scope = AuthorizationScope(ScopeKind.PROJECT, "query-workspace", e.nid)
    e.rig.grants.assign_permission(PermissionAssignment("canvas-write", "reader", "domain.write", ModalityDomain.NOVEL, grant_scope, "fixture"))
    view = create(e, e.rig.seed("shared-manual-card.png", scope_value=scope), headers=headers)
    body = save_body(e, view, headers=headers)
    before = source_state(e, scope)
    other_branch = {**headers, "X-Branch-Id": "query-branch-b"}
    assert e.client.get(f"{e.base}/{view['id']}", headers=other_branch).status_code == 404
    assert e.client.put(f"{e.base}/{view['id']}", headers=other_branch, json=body).status_code == 404
    assert source_state(e, scope) == before
    e.rig.grants.revoke_permission("canvas-write", "fixture")
    assert e.client.put(f"{e.base}/{view['id']}", headers=headers, json=body).status_code == 403
    assert source_state(e, scope) == before
    assert e.client.get(f"{e.base}/{view['id']}", headers=headers).status_code == 200
    e.rig.grants.revoke_permission("query-read", "fixture")
    for suffix in ("", "/history"):
        assert e.client.get(f"{e.base}/{view['id']}{suffix}", headers=headers).status_code == 403
    assert source_state(e, scope) == before


def test_legacy_approved_marker_cannot_mint_formal_canvas_asset_provenance(saved_canvas):
    e = saved_canvas
    view = create(e, e.rig.seed("unchanged-manual-card.png"))
    queued = e.owner.create(e.nid, None, queue_command(e.nid), "legacy-approved-fixture")
    legacy_asset = e.rig.seed("synthetic-legacy-accepted.png")
    with e.rig.workspace._asset_scope(e.nid, e.scope):
        legacy_asset = e.assets.update_metadata(legacy_asset["id"], {
            "source_job_id": queued["id"], "provider_id": queued["provider_id"], "model_id": queued["model_id"], "approved_at": now()})
    assert "_studio_result_origin" not in legacy_asset and "_origin_provenance" not in legacy_asset

    def mark_synthetic_approved(rows):
        row = e.owner._find(rows, queued["id"])
        row.update(status="SUCCEEDED", approval_status="APPROVED", attempt=1, asset_id=legacy_asset["id"], updated_at=now())
        return row

    e.owner._mutate(e.nid, None, mark_synthetic_approved)
    original_jobs = e.client.get(f"/api/novels/{e.nid}/image-jobs").json()
    assert original_jobs["items"][0]["approval_status"] == "APPROVED"
    with pytest.raises(ValueError, match="^CREATIVE_ASSET_ADAPTER_REQUIRED$"):
        e.rig.workspace._validate_asset_row(e.nid, e.scope, legacy_asset)
    body = save_body(e, view)
    body["definition"]["cards"][0]["asset"] = reference(legacy_asset)
    before = source_state(e)
    response = e.client.put(f"{e.base}/{view['id']}", json=body)
    assert response.status_code == 409, response.text
    refused_create = e.client.post(e.base, json={"request_id": "legacy-cannot-create", "expected_version": 0, "definition": definition(legacy_asset)})
    assert refused_create.status_code == 409, refused_create.text
    assert source_state(e) == before
    assert e.client.get(f"{e.base}/{view['id']}").json() == view
    assert e.client.get(f"/api/novels/{e.nid}/image-jobs").json() == original_jobs
