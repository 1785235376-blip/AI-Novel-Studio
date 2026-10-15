"""Capture the REAL backend prompt projections as a fixed synthetic fixture.

The R3-U3 directive requires contract verification driven by real producer output rather
than hand-written TS objects. This script runs the real service + real routes in an isolated
File environment, creates a private prompt family with **synthetic** text (never user
content), and writes the actual JSON for:

  GET /api/projects/{nid}/studio/prompts
  GET /api/projects/{nid}/studio/prompts/{family_id}
  GET /api/projects/{nid}/studio/prompts/{family_id}/revisions/{asset_id}/body

into `frontend/src/prompt/__fixtures__/`. The frontend contract test then decodes those
files, so a decoder that disagrees with the producer fails in CI instead of in the browser.

Run: python scripts/capture_prompt_contract_fixture.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("EXPERIMENTAL_FEATURES", "narrative_production_v2,asset_lineage_v2")
os.environ.pop("V1_ACCEPTANCE_MODE", None)

OUT = ROOT / "frontend" / "src" / "prompt" / "__fixtures__"

# Synthetic test content only — invented for this fixture, not taken from any user.
TEXT_1 = "合成测试正文第一版\n第二行 🙂\n"
TEXT_2 = "合成测试正文第二版，改动若干 🙂🙂\n第三行\n"


def main() -> int:
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.creative.bible_workspace import BibleWorkspaceService
    from app.creative.prompt_authoring import PromptAuthoringService
    from app.creative.prompt_authoring_models import PromptCreateIn, PromptRevisionIn
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

    tmp = Path(tempfile.mkdtemp(prefix="prompt-fixture-"))
    bundle = create_repository_bundle(
        Settings(storage_backend="file", database_url="", novel_data=tmp,
                 enable_cloud=False, mock_provider=True), data_root=tmp)
    novels = NovelService(bundle.novels, bundle.chapters)
    chapters = ChapterService(bundle.chapters)
    nid = "fixture-" + uuid4().hex
    novels.create({"id": nid, "title": "Fixture"})
    novels.upsert_character(nid, "c1", {"name": "合成角色"})
    raw = ExperimentalStore(tmp, "file", "")
    creative = CreativeService(raw, novels, chapters)
    assets = AssetLibraryService(tmp)
    workspace = IndependentWorkspaceService(
        creative, assets, ProductionLineageService(raw, novels, chapters, assets,
                                                   MediaService(raw, novels, chapters, assets)))
    bible = BibleWorkspaceService(workspace, WorldService(raw, novels, chapters))
    library = PromptWorkspaceService(workspace, bible)
    authoring = PromptAuthoringService(workspace, bible)

    def authorize(project_id, token, branch, permission):
        if token != "author-a":
            raise HTTPException(403, {"code": "CREATIVE_AUTHORITY_INVALID"})
        return token, {"mode": "local", "novel_id": project_id}

    from app.creative.workspace_api import create_independent_workspace_router
    app = FastAPI()
    app.include_router(create_independent_workspace_router(
        workspace, authorize, lambda flag: None,
        create_project=lambda body, token: (_ for _ in ()).throw(AssertionError("unused")),
        workspace_writer=lambda token: "author-a", bible_service=bible,
        prompt_service=library, prompt_authoring_service=authoring), prefix="/api")
    client = TestClient(app)
    headers = {"x-session-token": "author-a"}

    root = f"/api/projects/{nid}/studio/prompts"
    first = client.post(root, headers=headers, json=PromptCreateIn.model_validate(dict(
        text=TEXT_1, negative_prompt="低质量", purpose="IMAGE", origin="MANUAL",
        model_reference="flux-1", parameters={"steps": 28}, seed=7,
        character_ids=["c1"], change_note="合成初稿", change_reason="合成第一版",
        request_id="fixture-req-1")).model_dump()).json()
    family = first["family_id"]
    second = client.post(f"{root}/{family}/revisions", headers=headers,
                         json=PromptRevisionIn.model_validate(dict(
                             text=TEXT_2, negative_prompt="低质量, 模糊", purpose="IMAGE",
                             origin="MANUAL", model_reference="flux-2",
                             parameters={"steps": 40}, seed=8, character_ids=["c1"],
                             change_note="合成第二版", change_reason="合成调整",
                             request_id="fixture-req-2",
                             expected_previous_asset_id=first["asset_id"],
                             expected_revision=1)).model_dump()).json()

    OUT.mkdir(parents=True, exist_ok=True)
    written = []
    payloads = {
        "library.json": client.get(root, headers=headers).json(),
        "detail.json": client.get(f"{root}/{family}", headers=headers).json(),
        "revision-1-body.json": client.get(
            f"{root}/{family}/revisions/{first['asset_id']}/body", headers=headers).json(),
        "revision-2-body.json": client.get(
            f"{root}/{family}/revisions/{second['asset_id']}/body", headers=headers).json(),
        "empty-library.json": None,
    }
    # An empty library from a second, clean project: the "no prompts yet" producer shape.
    empty_nid = "fixture-empty-" + uuid4().hex
    novels.create({"id": empty_nid, "title": "Empty"})

    def authorize_empty(project_id, token, branch, permission):
        return token, {"mode": "local", "novel_id": project_id}

    app2 = FastAPI()
    app2.include_router(create_independent_workspace_router(
        workspace, authorize_empty, lambda flag: None,
        create_project=lambda body, token: (_ for _ in ()).throw(AssertionError("unused")),
        workspace_writer=lambda token: "author-a", bible_service=bible,
        prompt_service=library, prompt_authoring_service=authoring), prefix="/api")
    payloads["empty-library.json"] = TestClient(app2).get(
        f"/api/projects/{empty_nid}/studio/prompts", headers=headers).json()

    for name, payload in payloads.items():
        path = OUT / name
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(name)
    print("wrote:", ", ".join(written))
    print("library keys:", sorted(payloads["library.json"].keys()))
    print("entry keys:", sorted(payloads["library.json"]["entries"][0].keys()))
    print("bindings keys:", sorted(payloads["library.json"]["entries"][0]["bindings"].keys()))
    print("contract:", payloads["library.json"].get("contract"),
          "/", payloads["detail.json"].get("contract"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
