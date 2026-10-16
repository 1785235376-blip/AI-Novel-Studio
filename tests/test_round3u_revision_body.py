"""R3-U2 — the narrow single-revision body read, on a real private prompt revision.

The directive's concern: the generic `GET /studio/assets/{aid}/download` route calls the
asset owner's `content` **without** the resolved actor, and R3-W prompt drafts are private
`owner_actor_id` assets. So an author could not be assumed to be able to read their own
historical revision bodies — and without that, a "version comparison" could only compare
version numbers and digests while pretending to diff text.

These tests exercise the real routes on a real private revision.
"""
from __future__ import annotations

import base64
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.creative import prompt_asset as prompt
from app.creative.prompt_authoring_models import PromptCreateIn

HARNESS_MISSING = "requires the isolated runner (scripts/run_v2_checks.py) that sets PROJECT_ROOT"

TEXT_1 = "第一版正文\n第二行 🙂\n"
TEXT_2 = "第二版正文，改了很多 🙂🙂\n第三行\n"


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
    nid = "r3u2-" + uuid4().hex
    novels.create({"id": nid, "title": "R3U2"})
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
        create_project=lambda body, token: (_ for _ in ()).throw(AssertionError("not used")),
        workspace_writer=lambda token: "author-a", bible_service=bible,
        prompt_service=library, prompt_authoring_service=authoring), prefix="/api")
    return SimpleNamespace(client=TestClient(app), nid=nid, assets=assets, workspace=workspace,
                           library=library, authoring=authoring,
                           scope={"mode": "local", "novel_id": nid})


def _body(request_id, text=TEXT_1, **over):
    base = dict(text=text, purpose="IMAGE", origin="MANUAL", request_id=request_id)
    base.update(over)
    return PromptCreateIn.model_validate(base)


def _revision(request_id, previous_id, revision, text=TEXT_2, **over):
    from app.creative.prompt_authoring_models import PromptRevisionIn
    base = dict(text=text, purpose="IMAGE", origin="MANUAL", request_id=request_id,
                expected_previous_asset_id=previous_id, expected_revision=revision)
    base.update(over)
    return PromptRevisionIn.model_validate(base)


def _two_revisions(rig):
    """A private (author-owned) family with two revisions."""
    first = rig.client.post(f"/api/projects/{rig.nid}/studio/prompts",
                            headers={"x-session-token": "author-a"},
                            json=_body("req-1").model_dump()).json()
    second = rig.client.post(
        f"/api/projects/{rig.nid}/studio/prompts/{first['family_id']}/revisions",
        headers={"x-session-token": "author-a"},
        json=_revision("req-2", first["asset_id"], 1).model_dump()).json()
    return first, second


def test_the_asset_is_private_to_its_author(rig):
    """Establishes the premise: this really is a private owner asset."""
    first, _ = _two_revisions(rig)
    with rig.workspace._asset_scope(rig.nid, rig.scope):
        rows = rig.assets.list(rig.nid, branch_id=None, actor_id="author-a")
        row = next(item for item in rows if item["id"] == first["asset_id"])
        assert row.get("_owner_actor_id") == "author-a"
        # An actor-less read cannot see it — which is why the generic download route,
        # which drops the actor, cannot serve an author's own revision.
        with pytest.raises(FileNotFoundError):
            rig.assets.content(first["asset_id"], branch_id=None)


def test_the_author_can_read_both_real_revision_bodies(rig):
    """The R3-U2 gap: the author must be able to read each revision's actual text."""
    first, second = _two_revisions(rig)
    for receipt, expected in ((first, TEXT_1), (second, TEXT_2)):
        response = rig.client.get(
            f"/api/projects/{rig.nid}/studio/prompts/{first['family_id']}"
            f"/revisions/{receipt['asset_id']}/body",
            headers={"x-session-token": "author-a"})
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["state"] == "COMPLETE"
        assert payload["value"] == expected           # the real text, byte-exact
        assert payload["revision"] == receipt["revision"]
        assert payload["verified"] is True
        assert payload["digest_of"] == "ORIGINAL_BYTES"
        assert payload["digest"] == prompt.digest(expected.encode("utf-8"))
        assert payload["available"] is True


def test_the_two_bodies_really_differ_so_a_text_diff_is_meaningful(rig):
    first, second = _two_revisions(rig)
    def body(receipt):
        return rig.client.get(
            f"/api/projects/{rig.nid}/studio/prompts/{first['family_id']}"
            f"/revisions/{receipt['asset_id']}/body",
            headers={"x-session-token": "author-a"}).json()
    a, b = body(first), body(second)
    assert a["value"] != b["value"]
    assert a["digest"] != b["digest"]


def test_another_author_gets_nothing_and_no_prompt_text_leaks(rig):
    first, _ = _two_revisions(rig)
    response = rig.client.get(
        f"/api/projects/{rig.nid}/studio/prompts/{first['family_id']}"
        f"/revisions/{first['asset_id']}/body",
        headers={"x-session-token": "author-b"})
    # Any refusal is acceptable; what matters is that nothing readable came back.
    assert response.status_code in (403, 404, 422), response.text
    assert TEXT_1 not in response.text
    assert TEXT_2 not in response.text


def test_a_cross_family_read_is_refused(rig):
    first, second = _two_revisions(rig)
    other = rig.client.post(f"/api/projects/{rig.nid}/studio/prompts",
                            headers={"x-session-token": "author-a"},
                            json=_body("req-3", text="另一个家族").model_dump()).json()
    # The asset exists and the caller may read it, but it is not in the named family.
    response = rig.client.get(
        f"/api/projects/{rig.nid}/studio/prompts/{other['family_id']}"
        f"/revisions/{second['asset_id']}/body",
        headers={"x-session-token": "author-a"})
    assert response.status_code in (404, 422), response.text
    assert "另一个家族" not in response.text


def test_a_deleted_revision_would_be_a_tombstone_but_deletion_is_currently_blocked(rig):
    """Real finding, recorded rather than skipped.

    The route correctly returns a tombstone (`DELETED`, no bytes) for a revision whose
    `deleted_at` is set. But an author **cannot currently delete their own private prompt
    revision**: `AssetLibraryService.delete()` takes no `actor_id`, so a private
    `owner_actor_id` asset is invisible to it and the call raises `FileNotFoundError`.

    That is a genuine gap in the owner, out of scope for this read-only sub-phase, and it is
    asserted here so it cannot be mistaken for "deletion works". The tombstone branch of the
    new route therefore stays `NOT_RUN` against a real deleted revision.
    """
    first, second = _two_revisions(rig)
    with rig.workspace._asset_scope(rig.nid, rig.scope):
        with pytest.raises(FileNotFoundError):
            rig.assets.delete(second["asset_id"], branch_id=None)
    # Still fully readable, because it could not be deleted.
    response = rig.client.get(
        f"/api/projects/{rig.nid}/studio/prompts/{first['family_id']}"
        f"/revisions/{second['asset_id']}/body",
        headers={"x-session-token": "author-a"})
    assert response.status_code == 200
    assert response.json()["state"] == "COMPLETE"
    assert TEXT_2 not in response.text


def test_the_generic_download_route_was_not_widened(rig):
    """The narrow route must not have changed the long-standing download contract."""
    first, _ = _two_revisions(rig)
    response = rig.client.get(
        f"/api/projects/{rig.nid}/studio/assets/{first['asset_id']}/download",
        headers={"x-session-token": "author-a"})
    # Whatever it answers, the answer must not be the private prompt cleartext smuggled
    # through the generic route.
    assert TEXT_1.encode("utf-8") not in response.content
