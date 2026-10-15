"""R3-U3 P0-I — 展示遮罩（redacted）与单修订正文读取的一致性实测。

静态观察：Library/Detail 投影在 `redacted` 为真时会遮蔽正文（state=REDACTED），而
`revision_body()` 读取的是已授权的原始字节，本身不看该修订的 redacted 标记。因此同一份
历史修订可能在列表里被遮罩，却在比较接口返回 COMPLETE。

这**不自动等于越权**：此前决策已固定 redacted 是**展示遮罩**，不是加密或保密权限，
获授权者的原始资产读取契约不得被擅自改写。这里先用真实 File 服务与真实路由做实测，
确认真实行为，再决定最小一致性修复。
"""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.creative.prompt_authoring_models import PromptCreateIn, PromptRevisionIn

HARNESS_MISSING = "requires the isolated runner (scripts/run_v2_checks.py) that sets PROJECT_ROOT"

TEXT_1 = "被标记为展示遮罩的第一版正文\n"
TEXT_2 = "第二版正文（未遮罩）\n"


@pytest.fixture
def rig(tmp_path, monkeypatch):
    if os.environ.get("PROJECT_ROOT") is None:
        pytest.skip(HARNESS_MISSING)
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.creative.bible_workspace import BibleWorkspaceService
    from app.creative.prompt_authoring import PromptAuthoringService
    from app.creative.prompt_workspace import PromptWorkspaceService
    from app.creative.service import CreativeService
    from app.creative.workspace import IndependentWorkspaceService
    from app.experimental.media import MediaService
    from app.experimental.production_lineage import ProductionLineageService
    from app.experimental.store import ExperimentalStore
    from app.experimental.world import WorldService
    from app.repositories.factory import create_repository_bundle
    from app.services import ChapterService, NovelService
    from app.services.asset_library_service import AssetLibraryService

    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2,asset_lineage_v2")
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    bundle = create_repository_bundle(
        Settings(storage_backend="file", database_url="", novel_data=tmp_path,
                 enable_cloud=False, mock_provider=True), data_root=tmp_path)
    novels, chapters = NovelService(bundle.novels, bundle.chapters), ChapterService(bundle.chapters)
    nid = "r3ui-" + uuid4().hex
    novels.create({"id": nid, "title": "R3UI"})
    raw = ExperimentalStore(tmp_path, "file", "")
    creative = CreativeService(raw, novels, chapters)
    assets = AssetLibraryService(tmp_path)
    workspace = IndependentWorkspaceService(
        creative, assets, ProductionLineageService(raw, novels, chapters, assets,
                                                   MediaService(raw, novels, chapters, assets)))
    bible = BibleWorkspaceService(workspace, WorldService(raw, novels, chapters))
    library = PromptWorkspaceService(workspace, bible)
    authoring = PromptAuthoringService(workspace, bible)

    def authorize(project_id, token, branch, permission):
        if token not in {"author-a", "author-b"}:
            raise HTTPException(403, {"code": "CREATIVE_AUTHORITY_INVALID"})
        return token, {"mode": "local", "novel_id": project_id}

    from app.creative.workspace_api import create_independent_workspace_router
    app = FastAPI()
    app.include_router(create_independent_workspace_router(
        workspace, authorize, lambda flag: None,
        create_project=lambda body, token: (_ for _ in ()).throw(AssertionError("unused")),
        workspace_writer=lambda token: "author-a", bible_service=bible,
        prompt_service=library, prompt_authoring_service=authoring), prefix="/api")
    return SimpleNamespace(client=TestClient(app), nid=nid, assets=assets, workspace=workspace,
                           scope={"mode": "local", "novel_id": nid})


def _family(rig, *, first_redacted: bool, second_redacted: bool):
    """A private family whose first revision is marked as display-masked."""
    head = {"x-session-token": "author-a"}
    root = f"/api/projects/{rig.nid}/studio/prompts"
    first = rig.client.post(root, headers=head, json=PromptCreateIn.model_validate(dict(
        text=TEXT_1, purpose="IMAGE", origin="MANUAL", redacted=first_redacted,
        request_id="p0i-1")).model_dump()).json()
    family = first["family_id"]
    second = rig.client.post(f"{root}/{family}/revisions", headers=head,
                             json=PromptRevisionIn.model_validate(dict(
                                 text=TEXT_2, purpose="IMAGE", origin="MANUAL",
                                 redacted=second_redacted, request_id="p0i-2",
                                 expected_previous_asset_id=first["asset_id"],
                                 expected_revision=1)).model_dump()).json()
    return root, family, first, second


def test_the_library_masks_a_redacted_revision(rig):
    """The premise: the list projection really does mask it."""
    root, family, first, _ = _family(rig, first_redacted=True, second_redacted=False)
    entry = rig.client.get(root, headers={"x-session-token": "author-a"}).json()["entries"][0]
    # The head (revision 2) is not masked, so this call is about the version rows.
    detail = rig.client.get(f"{root}/{family}", headers={"x-session-token": "author-a"}).json()
    versions = {row["revision"]: row for row in detail["versions"]}
    assert versions[1]["redacted"] is True
    assert versions[2]["redacted"] is False
    assert entry["family_id"] == family


def test_the_revision_body_route_still_returns_the_masked_revision_text(rig):
    """MEASURED CURRENT BEHAVIOUR — the inconsistency P0-I is about.

    `revision_body` serves the authorised original bytes and does not consult the
    revision's display-mask flag, so a revision the list masks can come back COMPLETE here.
    This is recorded, not asserted as desirable: the fix must be a UI presentation decision,
    not a change to the owner's authorised read contract.
    """
    root, family, first, _ = _family(rig, first_redacted=True, second_redacted=False)
    body = rig.client.get(f"{root}/{family}/revisions/{first['asset_id']}/body",
                          headers={"x-session-token": "author-a"}).json()
    assert body["state"] == "COMPLETE"
    assert body["value"] == TEXT_1
    assert body["verified"] is True


def test_an_unauthorised_author_gets_no_text_from_either_route(rig):
    """No permission: neither the list, the detail nor the body route may leak."""
    root, family, first, second = _family(rig, first_redacted=True, second_redacted=False)
    other = {"x-session-token": "author-b"}
    library = rig.client.get(root, headers=other).json()
    assert library["prompt_count"] == 0
    assert TEXT_1 not in rig.client.get(root, headers=other).text
    for asset_id in (first["asset_id"], second["asset_id"]):
        response = rig.client.get(f"{root}/{family}/revisions/{asset_id}/body", headers=other)
        assert response.status_code in (403, 404, 422), response.text
        assert TEXT_1 not in response.text and TEXT_2 not in response.text
    detail = rig.client.get(f"{root}/{family}", headers=other)
    assert detail.status_code in (403, 404, 422)
    assert TEXT_1 not in detail.text


def test_the_masked_revision_is_not_served_to_a_foreign_project_scope(rig):
    """A cross-project read must not obtain the masked or unmasked bytes."""
    root, family, first, _ = _family(rig, first_redacted=True, second_redacted=False)
    assert TEXT_1 not in rig.client.get(root, headers={"x-session-token": "author-b"}).text
    assert first["asset_id"]
