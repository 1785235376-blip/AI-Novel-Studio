"""Real original File/API empty-create recovery; no production/media work.

The lost-ack case injects only a metadata response failure after the original
create commits. File persistence, reconstruction, authority and resolve routes
remain real. No approved Job, Asset or production provenance is manufactured.
"""
from copy import deepcopy
import hashlib
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi import HTTPException
import pytest

from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
from app.creative.canvas_view_models import CANVAS_VIEWS, CanvasViewCreate
from app.creative.graph import CreativeGraphService
from app.creative.production_execution import ProductionExecutionService
from app.creative.service import CreativeService
from app.creative.workspace import IndependentWorkspaceService
from app.experimental import api as experimental_api
from app.experimental.media import MediaService
from app.experimental.production_lineage import ProductionLineageService
from app.experimental.store import ExperimentalStore, canonical
from app.services.asset_library_service import AssetLibraryService
from app.services.image_job_service import ImageJobService
from test_cloud_formal_canvas_node import formal_node, command as formal_command
from test_studio_asset_query import rig, shared_scope


pytestmark = pytest.mark.file_backend_only


@pytest.fixture
def recovery(rig, monkeypatch):
    from app import media_files
    from app.services import image_job_service, studio_image_execution

    forbidden = []
    for target, name in ((ProductionExecutionService, "preview"), (ProductionExecutionService, "create"),
                         (ProductionExecutionService, "execute"), (ProductionExecutionService, "review"),
                         (ProductionExecutionService, "candidate"),
                         (ImageJobService, "create_studio"), (ImageJobService, "execute_studio"),
                         (ImageJobService, "accept_studio"), (ImageJobService, "create"),
                         (ImageJobService, "execute"), (ImageJobService, "accept"),
                         (AssetLibraryService, "create"), (AssetLibraryService, "content"),
                         (AssetLibraryService, "_verified_content"),
                         (image_job_service, "inspect_image"), (image_job_service, "fetch_media_bytes"),
                         (studio_image_execution, "inspect_image"), (studio_image_execution, "fetch_media_bytes"),
                         (media_files, "inspect_image"), (media_files, "fetch_media_bytes")):
        sentinel = Mock(side_effect=AssertionError("Empty-create recovery cannot call " + name))
        monkeypatch.setattr(target, name, sentinel)
        forbidden.append(sentinel)
    e = SimpleNamespace(rig=rig, client=rig.client, nid=rig.nid, scope=rig.scope,
                        base=f"/api/projects/{rig.nid}/studio/canvas-views")

    def mount(workspace):
        graph = CreativeGraphService(workspace.store, workspace)
        for mounted, fresh in ((experimental_api.independent_workspace_service, workspace),
                               (experimental_api.creative_graph_service, graph)):
            # Routes retain original authority and close over these objects.
            for name, value in fresh.__dict__.items():
                monkeypatch.setattr(mounted, name, value, raising=False)
        e.graph, e.workspace = graph, workspace

    def reopen():
        raw, assets = ExperimentalStore(rig.root, "file", ""), AssetLibraryService(rig.root)
        creative = CreativeService(raw, rig.novels, rig.workspace.creative.chapters)
        media = MediaService(raw, rig.novels, rig.workspace.creative.chapters, assets)
        lineage = ProductionLineageService(raw, rig.novels, rig.workspace.creative.chapters, assets, media)
        mount(IndependentWorkspaceService(creative, assets, lineage))

    e.reopen = reopen
    mount(rig.workspace)
    activated = e.client.post(f"/api/projects/{e.nid}/studio/activate")
    assert activated.status_code == 200, activated.text
    yield e
    for sentinel in forbidden:
        sentinel.assert_not_called()


def creation(e, *, request_id="explicit-empty-node-create", scope=None, node_id="image-node-one"):
    title = "One explicitly confirmed empty node"
    intent = {"contract": "studio-canvas-image-node-create/1", "project_id": e.nid,
        "scope": deepcopy(scope or e.scope), "incarnation": e.workspace.store.incarnation(e.nid),
        "node_id": node_id, "title": title, "position": {"x": 48, "y": 80},
        "prompt_digest": hashlib.sha256(b"Synthetic node prompt; no inference").hexdigest()}
    return {"request_id": request_id, "expected_version": 0,
        "definition": {"schema_version": 1, "title": title, "cards": [], "viewport": {"x": 0, "y": 0, "zoom": 1}},
        "image_node_intent": intent}


def lookup_body(value):
    return {"request_id": value["request_id"], "expected_incarnation": value["image_node_intent"]["incarnation"],
            "image_node_intent": deepcopy(value["image_node_intent"])}


def create(e, value, *, headers=None):
    response = e.client.post(e.base, headers=headers, json=value)
    assert response.status_code == 201, response.text
    return response.json()


def resolve(e, value, *, headers=None, nid=None):
    base = f"/api/projects/{nid or e.nid}/studio/canvas-views"
    return e.client.post(base + "/resolve-create", headers=headers, json=lookup_body(value))


def scope_bytes(e, scope=None):
    path = e.graph.store.path(e.nid, scope or e.scope)
    info = path.stat()
    return path.read_bytes(), info.st_ino, info.st_mtime_ns


def assert_envelope(response, value, canvas):
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.json() == {"contract": "studio-canvas-image-node-resolve/1",
        "request_id": value["request_id"], "image_node_intent": value["image_node_intent"],
        "incarnation": value["image_node_intent"]["incarnation"], "canvas": canvas}
    assert canvas["version"] == 1 and canvas["definition"]["cards"] == []
    assert canvas["execution_authority"] is False and canvas["binary_content_verified"] is False


def test_committed_create_with_lost_ack_resolves_after_real_file_owner_reconstruction(recovery, monkeypatch):
    e = recovery
    value = creation(e)

    def lose_saved_response(*_args, **_kwargs):
        raise HTTPException(503, {"code": "SYNTHETIC_CREATE_ACK_LOST"})

    # The original create commits before calling its final get. Only that
    # response step fails; no recovery is implemented by replaying create.
    with monkeypatch.context() as fault:
        fault.setattr(e.graph.canvas_views, "get", lose_saved_response)
        response = e.client.post(e.base, json=value)
        assert response.status_code == 503, response.text
    rows = e.graph.store.read(e.nid, e.scope)["collections"][CANVAS_VIEWS]
    assert len(rows) == 1
    saved_id = next(iter(rows))
    before = scope_bytes(e)
    old_graph, old_store, old_assets = e.graph, e.graph.store, e.workspace.assets
    e.reopen()
    assert e.graph is not old_graph and e.graph.store is not old_store and e.workspace.assets is not old_assets
    observed = resolve(e, value)
    canvas = e.client.get(f"{e.base}/{saved_id}").json()
    assert_envelope(observed, value, canvas)
    assert_envelope(resolve(e, value), value, canvas)
    assert scope_bytes(e) == before


def test_original_create_is_idempotent_but_request_cannot_rebind_to_another_node(recovery):
    e = recovery
    value = creation(e)
    saved = create(e, value)
    assert create(e, value) == saved
    before = scope_bytes(e)
    changed = deepcopy(value)
    changed["image_node_intent"]["node_id"] = "a-different-node"
    response = e.client.post(e.base, json=changed)
    assert response.status_code == 422, response.text
    assert resolve(e, changed).status_code == 409
    assert_envelope(resolve(e, value), value, saved)
    assert scope_bytes(e) == before


def test_absence_is_observation_only_and_a_later_commit_requires_another_explicit_lookup(recovery):
    e = recovery
    value = creation(e)
    before = scope_bytes(e)
    absent = resolve(e, value)
    assert absent.status_code == 404 and absent.json()["detail"] == {"code": "CREATIVE_CANVAS_CREATE_NOT_FOUND"}
    assert scope_bytes(e) == before
    # Deterministic order: lookup finishes while the original create has not
    # committed, then that original request arrives. Lookup never created it.
    saved = create(e, value)
    committed = scope_bytes(e)
    e.reopen()
    assert_envelope(resolve(e, value), value, saved)
    assert scope_bytes(e) == committed


@pytest.mark.parametrize("field", ["node", "position", "title", "prompt", "incarnation", "project"])
def test_changed_intent_or_owner_never_selects_the_latest_canvas(recovery, field):
    e = recovery
    value = creation(e)
    create(e, value)
    changed = deepcopy(value)
    intent = changed["image_node_intent"]
    if field == "node": intent["node_id"] = "other-node"
    elif field == "position": intent["position"]["x"] += 24
    elif field == "title": intent["title"] = "Other title"
    elif field == "prompt": intent["prompt_digest"] = "0" * 64
    elif field == "incarnation": intent["incarnation"] = "file:00000000-0000-4000-8000-000000000000"
    elif field == "project":
        intent["project_id"] = e.rig.project()
        intent["scope"]["novel_id"] = intent["project_id"]
    before = scope_bytes(e)
    response = resolve(e, changed)
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == {"code": "CREATIVE_CANVAS_CREATE_CHANGED"}
    assert scope_bytes(e) == before


def test_legacy_empty_create_remains_compatible_but_cannot_be_relabelled_by_browser_intent(recovery):
    e = recovery
    value = creation(e)
    legacy = deepcopy(value)
    del legacy["image_node_intent"]
    assert "image_node_intent" not in CanvasViewCreate.model_validate(legacy).model_dump()
    saved = create(e, legacy)
    assert create(e, legacy) == saved
    before = scope_bytes(e)
    response = resolve(e, value)
    assert response.status_code == 409, response.text
    assert "image_node_intent" not in e.graph.store.read(e.nid, e.scope)["collections"][CANVAS_VIEWS][saved["id"]]
    assert scope_bytes(e) == before


def test_changed_canvas_version_and_definition_aba_are_not_recovered_as_initial_create(recovery):
    e = recovery
    value = creation(e)
    saved = create(e, value)
    altered = deepcopy(saved["definition"])
    altered["title"] = "A changed current canvas"
    update = e.client.put(f"{e.base}/{saved['id']}", json={"expected_version": 1, "definition": altered})
    assert update.status_code == 200, update.text
    assert resolve(e, value).status_code == 409
    restored = e.client.put(f"{e.base}/{saved['id']}", json={"expected_version": 2, "definition": saved["definition"]})
    assert restored.status_code == 200 and restored.json()["version"] == 3
    assert restored.json()["definition_digest"] == saved["definition_digest"]
    before = scope_bytes(e)
    assert resolve(e, value).status_code == 409
    assert e.client.post(e.base, json=value).status_code == 409
    assert scope_bytes(e) == before


def test_ambiguous_original_request_records_fail_closed_without_repair_or_first_match(recovery):
    e = recovery
    value = creation(e)
    saved = create(e, value)
    # Deliberate original-store corruption fixture, never a source/review grant.
    with e.graph.store.transaction(e.nid, e.scope) as state:
        rows = state["collections"][CANVAS_VIEWS]
        duplicate = deepcopy(rows[saved["id"]])
        duplicate["id"] = "duplicate-original-request"
        rows[duplicate["id"]] = duplicate
    before = scope_bytes(e)
    assert resolve(e, value).status_code == 409
    assert e.client.post(e.base, json=value).status_code == 409
    assert scope_bytes(e) == before


def grant(e, principal, permission, grant_id):
    e.rig.grants.assign_permission(PermissionAssignment(grant_id, principal, permission, ModalityDomain.NOVEL,
        AuthorizationScope(ScopeKind.PROJECT, "query-workspace", e.nid), "fixture"))


def test_same_request_id_stays_actor_private_and_wrong_branch_or_project_has_no_match(recovery):
    e = recovery
    scope, headers = shared_scope(e.rig)
    grant(e, "reader", "domain.write", "recover-reader-write")
    grant(e, "no-grants", "domain.read", "recover-other-read")
    grant(e, "no-grants", "domain.write", "recover-other-write")
    value = creation(e, scope=scope)
    own = create(e, value, headers=headers)
    other_headers = {**headers, "X-Session-Token": "token-no-grants"}
    assert resolve(e, value, headers=other_headers).status_code == 404
    other = create(e, value, headers=other_headers)
    assert own["id"] != other["id"]
    before = scope_bytes(e, scope)
    assert_envelope(resolve(e, value, headers=headers), value, own)
    assert_envelope(resolve(e, value, headers=other_headers), value, other)
    wrong_branch = resolve(e, value, headers={**headers, "X-Branch-Id": "query-branch-b"})
    assert wrong_branch.status_code == 409, wrong_branch.text
    foreign = resolve(e, value, headers=headers, nid=e.rig.project())
    assert foreign.status_code == 403, foreign.text
    assert own["id"] not in wrong_branch.text + foreign.text
    assert scope_bytes(e, scope) == before


def test_revoked_read_blocks_recovery_while_the_original_write_grant_remains(recovery):
    e = recovery
    scope, headers = shared_scope(e.rig)
    grant(e, "reader", "domain.write", "recover-still-write")
    value = creation(e, scope=scope)
    saved = create(e, value, headers=headers)
    e.rig.grants.revoke_permission("query-read", "fixture")
    control = e.client.put(f"{e.base}/{saved['id']}", headers=headers,
        json={"expected_version": 1, "definition": saved["definition"]})
    assert control.status_code == 200, control.text
    before = scope_bytes(e, scope)
    denied = resolve(e, value, headers=headers)
    assert denied.status_code == 403 and denied.json()["detail"] == {"code": "CREATIVE_CANVAS_CREATE_FORBIDDEN"}
    assert saved["id"] not in denied.text and scope_bytes(e, scope) == before


def test_browser_marker_and_malformed_lookup_never_create_authority_or_echo_private_input(recovery):
    e = recovery
    value = creation(e)
    create(e, value)
    original = lookup_body(value)
    variants = [{**deepcopy(original), "approved": True}, {**deepcopy(original), "actor_id": "other-actor"},
                {**deepcopy(original), "image_node_intent": None}]
    bad_position = deepcopy(original)
    bad_position["image_node_intent"]["position"]["x"] = True
    variants.append(bad_position)
    before = scope_bytes(e)
    for payload in variants:
        response = e.client.post(e.base + "/resolve-create", json=payload)
        assert response.status_code == 422, response.text
        assert response.json()["detail"] == {"code": "CREATIVE_CANVAS_REQUEST_INVALID"}
        assert "input" not in response.text and str(e.rig.root) not in response.text
    assert scope_bytes(e) == before


def test_read_permission_revoked_during_lookup_rejects_the_late_result(recovery, monkeypatch):
    e = recovery
    scope, headers = shared_scope(e.rig)
    grant(e, "reader", "domain.write", "recover-race-write")
    value = creation(e, scope=scope)
    saved = create(e, value, headers=headers)
    original = e.graph.canvas_views._presentation
    fired = False

    def revoke_before_response(*args, **kwargs):
        nonlocal fired
        result = original(*args, **kwargs)
        if not fired:
            fired = True
            e.rig.grants.revoke_permission("query-read", "fixture")
        return result

    before = scope_bytes(e, scope)
    monkeypatch.setattr(e.graph.canvas_views, "_presentation", revoke_before_response)
    response = resolve(e, value, headers=headers)
    assert fired and response.status_code == 403, response.text
    assert saved["id"] not in response.text and scope_bytes(e, scope) == before


def test_resolve_does_not_provision_a_missing_original_project_identity(recovery):
    e = recovery
    other = e.rig.project()
    marker = e.rig.root / "novels" / other / "creative_project_v2.json"
    assert not marker.exists()
    value = creation(e)
    value["image_node_intent"]["project_id"] = other
    value["image_node_intent"]["scope"]["novel_id"] = other
    scope_path = e.graph.store.path(other, value["image_node_intent"]["scope"])
    assert not scope_path.exists()
    response = resolve(e, value, nid=other)
    assert response.status_code == 404, response.text
    assert not marker.exists() and not scope_path.exists()


@pytest.mark.parametrize("field", ["node", "prompt"])
def test_original_metadata_preview_cannot_rebind_an_intent_bound_empty_canvas(formal_node, field):
    # This separate original production fixture permits metadata preview only.
    # It still prohibits execute, review, accept, candidate/media operations.
    e = formal_node
    e.base += "/canvas-views"
    value = creation(e)
    saved = create(e, value, headers=e.headers)
    command = formal_command(e, saved, prompt="Synthetic node prompt; no inference")
    for name in ("node_id", "title", "position", "prompt_digest"):
        command["canvas_image_node"][name] = deepcopy(value["image_node_intent"][name])
    preview_url = f"/api/projects/{e.nid}/studio/production/preview"
    control = e.client.post(preview_url, headers=e.headers, json=command)
    assert control.status_code == 200, control.text
    if field == "node":
        command["canvas_image_node"]["node_id"] = "another-original-node"
    else:
        command["prompt"] += " changed with a correct SHA"
        command["canvas_image_node"]["prompt_digest"] = hashlib.sha256(command["prompt"].encode()).hexdigest()
    before = scope_bytes(e)
    rejected = e.client.post(preview_url, headers=e.headers, json=command)
    assert rejected.status_code == 409, rejected.text
    assert scope_bytes(e) == before
