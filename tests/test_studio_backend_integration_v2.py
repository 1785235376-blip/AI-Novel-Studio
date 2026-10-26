"""Mounted File/HTTP storyboard production loop; only provider generation is fake.

Original application authority, queue, executor, binary validation, publication,
manual review, creative writeback and cold reopen are exercised unchanged.
"""
from copy import deepcopy
from io import BytesIO
from types import SimpleNamespace
import base64

import pytest
from PIL import Image

from test_studio_asset_query import rig

pytestmark = pytest.mark.file_backend_only


class NoCalls:
    def __getattr__(self, name):
        raise AssertionError("Unexpected external dependency: " + name)


@pytest.fixture
def studio(rig, monkeypatch):
    from app.actor_context import SessionContext
    from app.asset_providers import AssetProviderRegistry, AssetGenerationResult
    from app import dependencies, asset_provider_config
    from app.audio_production_store import AudioProductionStore
    from app.creative.production_execution import ProductionExecutionService
    from app.creative.service import CreativeService
    from app.creative.workspace import IndependentWorkspaceService
    from app.experimental import api
    from app.experimental.media import MediaService
    from app.experimental.production_lineage import ProductionLineageService
    from app.experimental.store import ExperimentalStore
    from app.services.asset_library_service import AssetLibraryService
    from app.services.image_job_service import ImageJobService
    from app.services.video_assembly_service import VideoAssemblyService

    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2,asset_lineage_v2,ai_execution_v2,model_broker_v2,author_context_inspector_v2")
    e = SimpleNamespace(rig=rig, client=rig.client, nid=rig.nid, scope=rig.scope,
        actor="local-author", headers={"X-Session-Token": "studio-integration-host"}, calls=[])
    rig.sessions.register("studio-integration-host", SessionContext("studio-session", "studio-client", e.actor, "studio-workspace"))
    image = BytesIO()
    Image.new("RGB", (64, 64), (20, 110, 170)).save(image, format="PNG")
    e.png = image.getvalue()
    registry = AssetProviderRegistry()
    e.config_path = rig.root / "asset-providers.json"
    monkeypatch.setenv("ASSET_PROVIDER_CONFIG_PATH", str(e.config_path))
    monkeypatch.setattr(dependencies, "asset_provider_registry", registry)
    e.configuration = {"endpoint": "http://127.0.0.1:7860", "default_model": "synthetic.safetensors",
        "api_style": "automatic1111", "enabled": True, "local": True, "requires_credential": False}
    response = e.client.put("/api/asset-providers/automatic1111", headers=e.headers, json=e.configuration)
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["registered"] and asset_provider_config.load()["automatic1111"]["default_model"] == "synthetic.safetensors"
    provider = registry.get("automatic1111")
    e.provider, e.registry = provider, registry

    def generate(request):
        request.dispatch_guard()
        e.calls.append(request)
        return AssetGenerationResult(request.provider_id, request.model_id,
            "data:image/png;base64," + base64.b64encode(e.png).decode())
    monkeypatch.setattr(provider, "generate", generate)

    def mount(workspace):
        production = ProductionExecutionService(workspace, ImageJobService(rig.root / "integration-jobs"), registry,
            VideoAssemblyService(rig.root, workspace.assets), {}, {}, AudioProductionStore(rig.root / "integration-audio"), NoCalls(), NoCalls())
        for mounted, fresh in ((api.independent_workspace_service, workspace),
                               (api.creative_service, workspace.creative),
                               (api.studio_production_service, production)):
            for name, value in fresh.__dict__.items():
                monkeypatch.setattr(mounted, name, value, raising=False)
        e.workspace, e.production = workspace, production

    def reopen():
        store = ExperimentalStore(rig.root, "file", "")
        assets = AssetLibraryService(rig.root)
        creative = CreativeService(store, rig.novels, rig.workspace.creative.chapters)
        media = MediaService(store, rig.novels, rig.workspace.creative.chapters, assets)
        lineage = ProductionLineageService(store, rig.novels, rig.workspace.creative.chapters, assets, media)
        mount(IndependentWorkspaceService(creative, assets, lineage))

    e.reopen = reopen
    mount(rig.workspace)
    e.base = f"/api/projects/{e.nid}/studio"
    e.creative = f"/api/novels/{e.nid}/experimental/creative"
    check(e.client.post(e.base + "/activate", headers=e.headers))
    e.document_input = {"mode": "STORYBOARD", "title": "One original storyboard", "source_independent": True,
        "scenes": [{"id": "scene-one", "sequence": 1, "heading": "Courtyard"}],
        "shots": [{"id": "shot-one", "number": 1, "scene_id": "scene-one", "frame_prompt": "A blue courtyard"}]}
    e.document = check(e.client.post(e.creative + "/documents", headers=e.headers, json=e.document_input), 201)
    e.doc_url = e.creative + "/documents/" + e.document["id"]
    e.storyboard = check(e.client.get(e.doc_url + "/storyboard", headers=e.headers))
    yield e


def check(response, status=200):
    assert response.status_code == status, response.text
    assert response.headers.get("cache-control") == "no-store"
    return response.json()


def shot_action(e, receipt=None):
    receipt = receipt or e.storyboard
    shot = receipt["shots"][0]
    return {"expected_version": receipt["document_snapshot"]["version"],
        "shot_version": shot["shot_version"], "shot_digest": shot["shot_digest"]}


def request(e, request_id="storyboard-one"):
    return check(e.client.post(e.doc_url + "/shots/shot-one/image-request", headers=e.headers, json={
        **shot_action(e), "request_id": request_id,
        "provider": {"operation_id": "m5.image.t2i", "provider_id": "automatic1111", "model_id": "synthetic.safetensors"},
        "parameters": {"width": 64, "height": 64, "steps": 1, "seed": 42}}))


def queue(e, prepared=None):
    prepared = prepared or request(e)
    preview = check(e.client.post(e.base + "/production/preview", headers=e.headers, json=prepared["command"]))
    body = {"command": prepared["command"], "reviewed_preview_digest": preview["preview_digest"]}
    row = check(e.client.post(e.base + "/production/jobs", headers=e.headers, json=body), 201)
    return row, body


def action(row):
    return {"expected_version": row["version"], "expected_request_digest": row["request_digest"]}


def job_url(e, row):
    return e.base + "/production/jobs/image/" + row["id"]


def execute(e, row):
    return check(e.client.post(job_url(e, row) + "/execute", headers=e.headers, json=action(row)))


def review(e, row):
    return check(e.client.post(job_url(e, row) + "/review", headers=e.headers, json={
        **action(row), "reviewed_output_digest": row["output_candidate"]["digest"]}))


def test_storyboard_original_executor_manual_writeback_reopens(studio):
    e = studio
    prepared = request(e)
    assert not prepared["automatic_dispatch"] and not prepared["model_called"] and e.calls == []
    row, creation = queue(e, prepared)
    # Exact published frontend 048c5ebb command envelope for this ordinary
    # storyboard path; formal canvas_image_node remains a separate blocker.
    assert set(row["command"]) <= {"operation_id", "request_id", "provider_id", "model_id", "prompt", "parameters",
        "source_snapshots", "allow_cloud", "license_note", "image_source", "image_references", "mask_source",
        "video_reference", "video_frames", "storyboard_shot", "storyboard_speech", "audio_profile", "image_layers", "canvas_return"}
    assert row["status"] == "QUEUED" and e.calls == []
    assert check(e.client.post(e.base + "/production/jobs", headers=e.headers, json=creation), 201)["id"] == row["id"]
    row = execute(e, row)
    assert row["status"] == "AWAITING_REVIEW" and len(e.calls) == 1
    candidate = e.client.get(job_url(e, row) + "/candidate", headers=e.headers)
    assert candidate.status_code == 200 and candidate.content == e.png
    assert check(e.client.get(e.doc_url + "/storyboard", headers=e.headers))["shots"][0]["image_asset"] is None
    row = review(e, row)
    assert row["status"] == "APPROVED"
    asset = {"asset_id": row["output_candidate"]["id"], "version": row["approved_asset_version"],
        "digest": row["output_candidate"]["digest"], "kind": "image"}
    result = check(e.client.post(e.doc_url + "/shots/shot-one/image-binding", headers=e.headers,
        json={**shot_action(e), "asset": asset}))
    assert result["shots"][0]["image_asset"] == asset and not result["approved"]
    e.reopen()
    assert check(e.client.get(e.doc_url + "/storyboard", headers=e.headers)) == result
    assert check(e.client.get(job_url(e, row), headers=e.headers))["status"] == "APPROVED"
    assert len(e.calls) == 1


def edit_shot(e, *, frame_prompt="Changed author shot", shots=None):
    document = check(e.client.get(e.doc_url, headers=e.headers))
    value = deepcopy(e.document_input)
    if shots is not None:
        value["shots"] = shots
    else:
        value["shots"][0]["frame_prompt"] = frame_prompt
    return check(e.client.put(e.doc_url, headers=e.headers, json={**value, "expected_version": document["version"]}))


def test_configuration_validation_save_read_and_dispatch_binding(studio):
    from app import asset_provider_config
    e = studio
    saved_bytes = e.config_path.read_bytes()
    invalid = e.client.put("/api/asset-providers/automatic1111", headers=e.headers,
        json={**e.configuration, "endpoint": "file:///never-network"})
    assert invalid.status_code in {400, 422} and e.config_path.read_bytes() == saved_bytes
    providers = check(e.client.get(e.base + "/production/providers", headers=e.headers))
    assert "synthetic.safetensors" in str(providers) and not e.calls
    row, _ = queue(e)
    assert row["provider"]["model_id"] == "synthetic.safetensors"
    changed = {**e.configuration, "default_model": "changed.safetensors"}
    saved = e.client.put("/api/asset-providers/automatic1111", headers=e.headers, json=changed)
    assert saved.status_code == 200 and saved.json()["registered"]
    assert asset_provider_config.load()["automatic1111"]["default_model"] == "changed.safetensors"
    result = execute(e, row)
    assert result["status"] == "FAILED" and result["output_candidate"] is None and not e.calls
    e.reopen()
    assert check(e.client.get(job_url(e, row), headers=e.headers))["status"] == "FAILED"


def test_saved_configuration_change_invalidates_reviewed_preview(studio):
    e = studio
    prepared = request(e)
    preview = check(e.client.post(e.base + "/production/preview", headers=e.headers, json=prepared["command"]))
    changed = e.client.put("/api/asset-providers/automatic1111", headers=e.headers,
        json={**e.configuration, "default_model": "changed.safetensors"})
    assert changed.status_code == 200
    response = e.client.post(e.base + "/production/jobs", headers=e.headers,
        json={"command": prepared["command"], "reviewed_preview_digest": preview["preview_digest"]})
    assert response.status_code == 422
    assert e.production._image(e.actor)._load(e.nid, None) == [] and not e.calls


def test_source_revision_before_dispatch_refuses_without_provider(studio):
    e = studio
    row, _ = queue(e)
    edit_shot(e)
    response = e.client.post(job_url(e, row) + "/execute", headers=e.headers, json=action(row))
    assert response.status_code == 409 and not e.calls
    e.reopen()
    assert check(e.client.get(job_url(e, row), headers=e.headers))["status"] == "QUEUED"


def test_deleted_recreated_shot_rejects_old_pin(studio):
    e = studio
    original = deepcopy(e.document_input["shots"])
    edit_shot(e, shots=[])
    edit_shot(e, shots=original)
    reopened = check(e.client.get(e.doc_url + "/storyboard", headers=e.headers))
    assert reopened["shots"][0]["shot_version"] == e.storyboard["shots"][0]["shot_version"] + 1
    assert reopened["shots"][0]["shot_digest"] == e.storyboard["shots"][0]["shot_digest"]
    response = e.client.post(e.doc_url + "/shots/shot-one/image-request", headers=e.headers,
        json={**shot_action(e), "expected_version": reopened["document_snapshot"]["version"],
            "request_id": "recreated-shot", "provider": {"operation_id": "m5.image.t2i",
                "provider_id": "automatic1111", "model_id": "synthetic.safetensors"}})
    assert response.status_code == 409 and not e.calls


def test_private_candidate_cannot_bind_before_manual_review(studio):
    e = studio
    row, _ = queue(e)
    row = execute(e, row)
    output = row["output_candidate"]
    response = e.client.post(e.doc_url + "/shots/shot-one/image-binding", headers=e.headers,
        json={**shot_action(e), "asset": {"asset_id": output["id"], "version": output["version"],
            "digest": output["digest"], "kind": "image"}})
    assert response.status_code in {404, 422}, response.text
    assert check(e.client.get(e.doc_url + "/storyboard", headers=e.headers)) == e.storyboard
    assert check(e.client.get(job_url(e, row), headers=e.headers))["status"] == "AWAITING_REVIEW"


def test_review_and_writeback_retries_never_duplicate_asset_or_version(studio):
    e = studio
    row, _ = queue(e)
    awaiting = execute(e, row)
    approved = review(e, awaiting)
    assert review(e, awaiting) == approved
    pin = {"asset_id": approved["output_candidate"]["id"], "version": approved["approved_asset_version"],
        "digest": approved["output_candidate"]["digest"], "kind": "image"}
    body = {**shot_action(e), "asset": pin}
    bound = check(e.client.post(e.doc_url + "/shots/shot-one/image-binding", headers=e.headers, json=body))
    retry = e.client.post(e.doc_url + "/shots/shot-one/image-binding", headers=e.headers, json=body)
    assert retry.status_code == 409
    e.reopen()
    assert check(e.client.get(e.doc_url + "/storyboard", headers=e.headers)) == bound
    assert len(e.calls) == 1


def test_cancelled_original_job_is_not_replayed(studio):
    e = studio
    row, _ = queue(e)
    cancelled = check(e.client.post(job_url(e, row) + "/cancel", headers=e.headers, json=action(row)))
    assert cancelled["status"] == "CANCELLED"
    e.reopen()
    response = e.client.post(job_url(e, row) + "/execute", headers=e.headers, json=action(cancelled))
    assert response.status_code == 422
    assert check(e.client.get(job_url(e, row), headers=e.headers))["status"] == "CANCELLED" and not e.calls


def test_original_execution_gate_remains_opt_in(studio, monkeypatch):
    e = studio
    row, _ = queue(e)
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2,asset_lineage_v2")
    observed = check(e.client.get(job_url(e, row), headers=e.headers))
    assert observed["status"] == "QUEUED"
    denied = e.client.post(job_url(e, row) + "/execute", headers=e.headers, json=action(row))
    assert denied.status_code in {404, 422} and not e.calls


def test_stale_job_cas_refuses_dispatch(studio):
    e = studio
    row, _ = queue(e)
    response = e.client.post(job_url(e, row) + "/execute", headers=e.headers,
        json={**action(row), "expected_version": row["version"] + 1})
    assert response.status_code in {409, 422} and not e.calls
    assert check(e.client.get(job_url(e, row), headers=e.headers))["status"] == "QUEUED"


def test_metadata_refresh_and_reopen_do_not_execute_or_change_saved_inputs(studio):
    from app.experimental.store import canonical
    e = studio
    row, _ = queue(e)
    queue_path = e.production._image(e.actor)._path(e.nid, None)
    before = (queue_path.read_bytes(), canonical(e.workspace.store.read(e.nid, e.scope)), e.config_path.read_bytes())
    for _ in range(3):
        assert check(e.client.get(job_url(e, row), headers=e.headers))["status"] == "QUEUED"
        assert check(e.client.get(e.doc_url + "/storyboard", headers=e.headers)) == e.storyboard
        page = check(e.client.get(e.base + "/production/jobs?owner=image&limit=1&offset=0", headers=e.headers))
        assert page["total"] == 1 and page["items"][0]["id"] == row["id"]
    e.reopen()
    assert (queue_path.read_bytes(), canonical(e.workspace.store.read(e.nid, e.scope)), e.config_path.read_bytes()) == before
    assert not e.calls


def test_uncertain_provider_result_survives_reopen_without_automatic_replay(studio, monkeypatch):
    e = studio
    def uncertain(request):
        request.dispatch_guard()
        e.calls.append(request)
        raise ConnectionError("synthetic connection closed after send")
    monkeypatch.setattr(e.provider, "generate", uncertain)
    row, _ = queue(e)
    row = execute(e, row)
    assert row["status"] == "UNKNOWN" and row["output_candidate"] is None
    assert row["automatic_replay"] is False and len(e.calls) == 1
    e.reopen()
    observed = check(e.client.get(job_url(e, row), headers=e.headers))
    assert observed["status"] == "UNKNOWN"
    reconciled = check(e.client.post(job_url(e, row) + "/reconcile", headers=e.headers, json=action(observed)))
    assert reconciled["status"] == "UNKNOWN" and len(e.calls) == 1
    retried = e.client.post(job_url(e, row) + "/execute", headers=e.headers, json=action(reconciled))
    assert retried.status_code == 422 and len(e.calls) == 1
    assert check(e.client.get(e.doc_url + "/storyboard", headers=e.headers)) == e.storyboard


def test_wrong_review_digest_retains_private_candidate(studio):
    e = studio
    row, _ = queue(e)
    row = execute(e, row)
    response = e.client.post(job_url(e, row) + "/review", headers=e.headers,
        json={**action(row), "reviewed_output_digest": "0" * 64})
    assert response.status_code == 422
    assert check(e.client.get(job_url(e, row), headers=e.headers))["status"] == "AWAITING_REVIEW"
    assert check(e.client.get(e.doc_url + "/storyboard", headers=e.headers)) == e.storyboard


def test_revoked_session_cannot_observe_or_adopt_private_candidate(studio):
    e = studio
    row, _ = queue(e)
    row = execute(e, row)
    queue_path = e.production._image(e.actor)._path(e.nid, None)
    before = queue_path.read_bytes()
    e.rig.sessions.revoke("studio-integration-host")
    for path in (job_url(e, row), job_url(e, row) + "/candidate", e.doc_url + "/storyboard"):
        assert e.client.get(path, headers=e.headers).status_code == 401
    response = e.client.post(job_url(e, row) + "/review", headers=e.headers,
        json={**action(row), "reviewed_output_digest": row["output_candidate"]["digest"]})
    assert response.status_code == 401 and queue_path.read_bytes() == before and len(e.calls) == 1


def test_revocation_while_waiting_for_queue_owner_does_not_persist(studio, monkeypatch):
    from app.services.image_job_service import ImageJobService
    e = studio
    prepared = request(e)
    preview = check(e.client.post(e.base + "/production/preview", headers=e.headers, json=prepared["command"]))
    original = ImageJobService._mutate
    def revoke_at_owner(owner, nid, branch, operation):
        def late(rows):
            e.rig.sessions.revoke("studio-integration-host")
            return operation(rows)
        return original(owner, nid, branch, late)
    monkeypatch.setattr(ImageJobService, "_mutate", revoke_at_owner)
    response = e.client.post(e.base + "/production/jobs", headers=e.headers, json={
        "command": prepared["command"], "reviewed_preview_digest": preview["preview_digest"]})
    assert response.status_code == 401, response.text
    assert e.production._image(e.actor)._load(e.nid, None) == []
    assert not e.calls


def test_storyboard_change_after_preview_cannot_enter_queue(studio, monkeypatch):
    from app.creative.production_execution import ProductionExecutionService
    e = studio
    prepared = request(e)
    preview = check(e.client.post(e.base + "/production/preview", headers=e.headers, json=prepared["command"]))
    original = ProductionExecutionService.preview
    def change_after_preview(owner, *args, **kwargs):
        result = original(owner, *args, **kwargs)
        payload = deepcopy(e.document_input)
        payload["shots"][0]["frame_prompt"] = "Changed after the reviewed preview"
        check(e.client.put(e.doc_url, headers=e.headers, json={**payload, "expected_version": e.document["version"]}))
        return result
    monkeypatch.setattr(ProductionExecutionService, "preview", change_after_preview)
    response = e.client.post(e.base + "/production/jobs", headers=e.headers, json={
        "command": prepared["command"], "reviewed_preview_digest": preview["preview_digest"]})
    assert response.status_code == 409, response.text
    assert e.production._image(e.actor)._load(e.nid, None) == []
    assert not e.calls
