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
    from app.asset_providers import AssetProviderRegistry, Automatic1111ImageProvider, AssetGenerationResult
    from app import asset_provider_config
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
    provider = Automatic1111ImageProvider(NoCalls(), "http://127.0.0.1:7860")
    registry.register("automatic1111", provider)
    e.config = {"automatic1111": {"default_model": "synthetic.safetensors", "enabled": True,
        "local": True, "requires_credential": False}}
    monkeypatch.setattr(asset_provider_config, "load", lambda: deepcopy(e.config))

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
    assert row["status"] == "QUEUED" and e.calls == []
    assert check(e.client.post(e.base + "/production/jobs", headers=e.headers, json=creation), 201)["id"] == row["id"]
    row = execute(e, row)
    assert row["status"] == "AWAITING_REVIEW" and len(e.calls) == 1
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
