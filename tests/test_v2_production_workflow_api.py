"""Phase7 unified production workflow closed routes.

The routes are mounted on a real FastAPI app with the real studio router and the
real File store; only the original authority resolution is replaced by a stub, so
the permission string, the scope admission and the error mapping are exercised
end to end. Run with ``scripts/run_v2_checks.py`` and an owned ``--basetemp``.
"""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

FLAGS = "narrative_production_v2,asset_lineage_v2"
WORKFLOW = "/api/projects/{nid}/studio/production/workflow"
INTENT = WORKFLOW + "/intent"


def services(root, backend, url, novels, chapters):
    from app.creative.service import CreativeService
    from app.creative.workspace import IndependentWorkspaceService
    from app.experimental.media import MediaService
    from app.experimental.production_lineage import ProductionLineageService
    from app.experimental.store import ExperimentalStore
    from app.services.asset_library_service import AssetLibraryService
    raw_store = ExperimentalStore(root, backend, url)
    assets = AssetLibraryService(root)
    creative = CreativeService(raw_store, novels, chapters)
    media = MediaService(raw_store, novels, chapters, assets)
    lineage = ProductionLineageService(raw_store, novels, chapters, assets, media)
    return IndependentWorkspaceService(creative, assets, lineage)


@pytest.fixture
def rig(tmp_path, monkeypatch):
    from app.config import Settings
    from app.repositories.factory import create_repository_bundle
    from app.services import NovelService, ChapterService
    root = Path(__file__).resolve().parents[1]
    assert Path(os.environ["PROJECT_ROOT"]).resolve() == root
    for key in ("LOCALAPPDATA", "NOVEL_DATA_PATH"):
        assert Path(os.environ[key]).resolve().is_relative_to(root / ".runtime")
    assert tmp_path.resolve().is_relative_to(root / ".runtime")
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", FLAGS)
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    bundle = create_repository_bundle(
        Settings(storage_backend="file", database_url="", novel_data=tmp_path,
                 enable_cloud=False, mock_provider=True), data_root=tmp_path)
    novels, chapters = NovelService(bundle.novels, bundle.chapters), ChapterService(bundle.chapters)
    nid = "phase7-route-" + uuid4().hex
    novels.create({"id": nid, "title": "Phase7 workflow routes"})
    workspace = services(tmp_path, "file", "", novels, chapters)
    flags = []

    def authorize(project_id, token, branch, permission):
        if token not in {"valid-session", "read-only-session"}:
            raise HTTPException(403, {"code": "CREATIVE_AUTHORITY_INVALID"})
        if token == "read-only-session" and permission != "domain.read":
            raise HTTPException(403, {"code": "CREATIVE_AUTHORITY_INVALID"})
        return "phase7-author", {"mode": "local", "novel_id": project_id}

    def require_flag(flag):
        flags.append(flag)

    from app.creative.workspace_api import create_independent_workspace_router
    app = FastAPI()
    app.include_router(create_independent_workspace_router(
        workspace, authorize, require_flag,
        create_project=lambda body, token: (_ for _ in ()).throw(AssertionError("not used")),
        workspace_writer=lambda token: "phase7-author"), prefix="/api")
    yield SimpleNamespace(nid=nid, client=TestClient(app, raise_server_exceptions=False),
                          workspace=workspace, flags=flags, root=tmp_path)
    assert flags == ["narrative_production_v2"] * len(flags)


def _auth(token="valid-session"):
    return {"x-session-token": token}


def test_projection_route_returns_the_contract(rig):
    response = rig.client.get(WORKFLOW.format(nid=rig.nid), headers=_auth())
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["contract"] == "studio-production-workflow/1" and body["project_id"] == rig.nid
    assert [row["id"] for row in body["modules"]] == [
        "director", "storyboard", "image", "video", "audio", "timeline", "asset"]
    assert body["dashboard"]["stages_total"] == 7
    assert body["advisory_only"] is True and body["execution_authority"] is False


def test_routes_require_original_authority(rig):
    assert rig.client.get(WORKFLOW.format(nid=rig.nid)).status_code == 403
    assert rig.client.post(INTENT.format(nid=rig.nid), json={"expected_version": None, "values": [],
                                                            "preset": None}).status_code == 403
    read_only = rig.client.post(INTENT.format(nid=rig.nid), headers=_auth("read-only-session"),
                                json={"expected_version": None, "values": [], "preset": None})
    assert read_only.status_code == 403
    assert rig.client.get(WORKFLOW.format(nid=rig.nid), headers=_auth()).status_code == 200


def test_unknown_project_is_not_disclosed(rig):
    response = rig.client.get(WORKFLOW.format(nid="phase7-missing-" + uuid4().hex), headers=_auth())
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "EXPERIMENTAL_NOT_FOUND"


def test_intent_route_is_versioned_and_conflict_is_explicit(rig):
    first = rig.client.post(INTENT.format(nid=rig.nid), headers=_auth(), json={
        "expected_version": None, "preset": "editing",
        "values": [{"intent_id": "blank", "label": "空白创作", "selected": True}]})
    assert first.status_code == 200, first.text
    assert first.json()["version"] == 1 and first.json()["preset"] == "EDITING"

    conflict = rig.client.post(INTENT.format(nid=rig.nid), headers=_auth(), json={
        "expected_version": None, "values": [], "preset": None})
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "PRODUCTION_WORKFLOW_INTENT_CONFLICT"

    second = rig.client.post(INTENT.format(nid=rig.nid), headers=_auth(), json={
        "expected_version": 1, "values": [{"intent_id": "custom", "label": "舞台剧", "selected": True}],
        "preset": None})
    assert second.status_code == 200 and second.json()["version"] == 2
    assert second.json()["preset"] == "EDITING"
    assert rig.client.get(WORKFLOW.format(nid=rig.nid), headers=_auth()).json()["creative_intent"]["version"] == 2


def test_intent_route_rejects_unknown_keys_and_values(rig):
    unknown_key = rig.client.post(INTENT.format(nid=rig.nid), headers=_auth(),
                                  json={"expected_version": None, "values": [], "preset": None, "note": "x"})
    assert unknown_key.status_code == 422
    unknown_intent = rig.client.post(INTENT.format(nid=rig.nid), headers=_auth(), json={
        "expected_version": None, "values": [{"intent_id": "nope", "label": "x", "selected": True}], "preset": None})
    assert unknown_intent.status_code == 422
    assert unknown_intent.json()["detail"]["code"] == "PRODUCTION_WORKFLOW_INTENT_INVALID"


def test_only_the_declared_methods_reach_the_workflow_paths():
    from app.creative.workspace_api import is_independent_studio_route
    assert is_independent_studio_route("GET", "/api/projects/P1/studio/production/workflow")
    assert is_independent_studio_route("POST", "/api/projects/P1/studio/production/workflow/intent")
    for method, path in (("PUT", "/api/projects/P1/studio/production/workflow"),
                         ("DELETE", "/api/projects/P1/studio/production/workflow"),
                         ("GET", "/api/projects/P1/studio/production/workflow/intent"),
                         ("POST", "/api/projects/P1/studio/production/workflow"),
                         ("GET", "/api/projects/P1/studio/production/workflow/intent/extra")):
        assert not is_independent_studio_route(method, path), (method, path)
