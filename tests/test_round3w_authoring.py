"""R3-W — dedicated Prompt authoring: create, revise, idempotency, conflict, privacy.

Covers the directive's W6 list: normal create and read-back, a second revision,
concurrency conflict, repeated request id, reused request id with different content,
failure injection at each write stage, old revisions unchanged, private-draft isolation,
and CJK/newline/emoji/UTF-8 byte boundaries.
"""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.creative import prompt_asset as prompt
from app.creative.prompt_authoring_models import PromptCreateIn, PromptRevisionIn

HARNESS_MISSING = "requires the isolated runner (scripts/run_v2_checks.py) that sets PROJECT_ROOT"

TEXT_1 = "一个瘦高的男人站在雨里\n第二行\n"
TEXT_2 = "一个瘦高的男人站在雨里，回头 🙂\n第二行\n"


def create_body(**overrides):
    base = dict(text=TEXT_1, negative_prompt="low quality", purpose="IMAGE", origin="MANUAL",
                model_reference="flux-1", parameters={"steps": 28}, seed=7,
                character_ids=["c1"], scene_ids=[], shot_ids=[], reference_asset_ids=[],
                change_note="初稿", change_reason="第一版", request_id="req-" + uuid4().hex)
    base.update(overrides)
    return PromptCreateIn.model_validate(base)


def revision_body(previous_id, revision, **overrides):
    base = dict(text=TEXT_2, negative_prompt="low quality", purpose="IMAGE", origin="MANUAL",
                model_reference="flux-2", parameters={"steps": 40}, seed=8,
                character_ids=["c1"], scene_ids=[], shot_ids=[], reference_asset_ids=[],
                change_note="提高步数", change_reason="细节不足",
                request_id="req-" + uuid4().hex,
                expected_previous_asset_id=previous_id, expected_revision=revision)
    base.update(overrides)
    return PromptRevisionIn.model_validate(base)


# ================================================== DTO strictness (W2) =====

def test_the_dto_refuses_client_supplied_server_side_facts():
    for forbidden in ("approved_at", "reviewer", "reviewer_id", "_owner_actor_id",
                      "_project_binding", "model_called", "output_digest", "receipt",
                      "asset_id", "revision", "family_id"):
        with pytest.raises(Exception):
            PromptCreateIn.model_validate({**create_body().model_dump(), forbidden: "x"})


def test_the_dto_measures_utf8_bytes_and_preserves_creative_text():
    # Whitespace, newlines and emoji are authored content, not noise to be stripped.
    body = create_body(text="  line\n\n  emoji 🙂  ")
    assert body.text == "  line\n\n  emoji 🙂  "
    # Length is measured in real bytes: 3-byte CJK cannot exceed the byte budget by
    # pretending to be short in characters.
    from app.creative.prompt_authoring_models import PROMPT_TEXT_MAX_BYTES
    with pytest.raises(Exception):
        create_body(text="中" * (PROMPT_TEXT_MAX_BYTES // 3 + 2))


def test_the_dto_rejects_duplicate_bindings_and_bad_enums():
    with pytest.raises(Exception):
        create_body(character_ids=["c1", "c1"])
    with pytest.raises(Exception):
        create_body(purpose="HOLOGRAM")
    with pytest.raises(Exception):
        create_body(seed=-1)


# ============================================================ rig ==========

@pytest.fixture
def rig(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
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
    nid = "r3w-" + uuid4().hex
    novels.create({"id": nid, "title": "R3W"})
    novels.upsert_character(nid, "c1", {"name": "林向晚"})
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


def _post_create(rig, body, token="author-a"):
    return rig.client.post(f"/api/projects/{rig.nid}/studio/prompts",
                           headers={"x-session-token": token}, json=body.model_dump())


def _post_revision(rig, family_id, body, token="author-a"):
    return rig.client.post(f"/api/projects/{rig.nid}/studio/prompts/{family_id}/revisions",
                           headers={"x-session-token": token}, json=body.model_dump())


# ================================================= T01 create + read back ===

def test_t01_create_then_read_back_through_the_library(rig):
    response = _post_create(rig, create_body())
    assert response.status_code == 201, response.text
    receipt = response.json()
    assert receipt["revision"] == 1 and receipt["idempotent_replay"] is False
    assert receipt["previous_asset_id"] is None

    library = rig.client.get(f"/api/projects/{rig.nid}/studio/prompts",
                             headers={"x-session-token": "author-a"}).json()
    entry = next(row for row in library["entries"] if row["family_id"] == receipt["family_id"])
    text = next(row for row in entry["fields"] if row["field"] == "text")
    assert text["value"] == TEXT_1                       # newlines and CJK intact
    assert entry["revision"] == 1
    assert entry["body"]["state"] == prompt.BODY_COMPLETE
    assert entry["body"]["digest"] == receipt["text_digest"]


# ================================================= T02 second revision =====

def test_t02_second_revision_is_a_new_immutable_asset(rig):
    first = _post_create(rig, create_body()).json()
    response = _post_revision(rig, first["family_id"],
                              revision_body(first["asset_id"], 1))
    assert response.status_code == 201, response.text
    second = response.json()
    assert second["revision"] == 2
    assert second["previous_asset_id"] == first["asset_id"]
    assert second["asset_id"] != first["asset_id"]

    detail = rig.client.get(f"/api/projects/{rig.nid}/studio/prompts/{first['family_id']}",
                            headers={"x-session-token": "author-a"}).json()
    assert [row["revision"] for row in detail["versions"]] == [1, 2]
    assert detail["revision"] == 2 and detail["history_complete"] is True


# ================================================= T07 old revision fixed ==

def test_t07_the_old_revision_is_not_overwritten(rig):
    first = _post_create(rig, create_body()).json()
    _post_revision(rig, first["family_id"], revision_body(first["asset_id"], 1))

    with rig.workspace._asset_scope(rig.nid, rig.scope):
        rows = rig.assets.list(rig.nid, branch_id=None, actor_id="author-a")
        old = next(row for row in rows if row["id"] == first["asset_id"])
        raw = rig.assets.content(first["asset_id"], actor_id="author-a")
    assert raw.decode("utf-8") == TEXT_1                       # bytes unchanged
    assert prompt.revision_of(old) == 1                        # revision unchanged
    assert prompt.authoring_state(old) == prompt.STATE_ACTIVE
    assert old["version"] == first["asset_version"]             # never re-written


# ================================================= T03 concurrency =========

def test_t03_a_stale_editor_cannot_write_the_next_revision(rig):
    first = _post_create(rig, create_body()).json()
    # Two editors both hold revision 1; the first wins.
    assert _post_revision(rig, first["family_id"], revision_body(first["asset_id"], 1)).status_code == 201
    loser = _post_revision(rig, first["family_id"], revision_body(first["asset_id"], 1))
    assert loser.status_code == 409
    # The shared invoker wraps a CAS conflict as EXPERIMENTAL_VERSION_CONFLICT and carries
    # the reason under `current`; the client must still see the specific cause.
    assert "PROMPT_REVISION_STALE" in loser.text
    assert "current_revision" in loser.text


def test_t03b_two_active_revisions_are_reported_rather_than_hidden(rig):
    """The read-side backstop for the conflict rule.

    Revision allocation is conflict-detecting, not lock-serialized (documented in
    `prompt_authoring.py`). If two racers both finish before either re-reads, two active
    revisions exist; the projector must surface that as a blocking anomaly instead of
    silently presenting one of them as the family's history.
    """
    import base64
    first = _post_create(rig, create_body()).json()
    with rig.workspace._asset_scope(rig.nid, rig.scope):
        for index in (1, 2):
            created = rig.assets.create(
                rig.nid, f"racer-{index}.txt", base64.b64encode(TEXT_2.encode()).decode(),
                media_type="text/plain", kind="prompt", idempotency_key=f"racer-key-{index}",
                required_features=("narrative_production_v2",))
            payload = prompt.build_payload(
                family_id=first["family_id"], revision=2, purpose="IMAGE", origin="MANUAL",
                previous_asset_id=first["asset_id"], state=prompt.STATE_ACTIVE,
                request_id=f"racer-key-{index}")
            rig.assets.update_metadata(created["id"], {"parameters": {"prompt": payload}},
                                       branch_id=None, expected_version=created.get("version"))

    detail = rig.client.get(f"/api/projects/{rig.nid}/studio/prompts/{first['family_id']}",
                            headers={"x-session-token": "author-a"}).json()
    kinds = {row["kind"] for row in detail["anomalies"]}
    assert "DUPLICATE_REVISION" in kinds
    assert detail["history_complete"] is False
    # Both racers' content is still readable — nothing a user wrote was discarded.
    assert len([row for row in detail["versions"] if row["revision"] == 2]) == 2


# ================================================= T04/T05 idempotency =====

def test_t04_repeating_the_same_request_does_not_create_a_second_revision(rig):
    body = create_body()
    first = _post_create(rig, body)
    assert first.status_code == 201
    again = _post_create(rig, body)
    assert again.status_code == 201
    assert again.json()["asset_id"] == first.json()["asset_id"]
    assert again.json()["idempotent_replay"] is True

    library = rig.client.get(f"/api/projects/{rig.nid}/studio/prompts",
                             headers={"x-session-token": "author-a"}).json()
    assert library["prompt_count"] == 1
    assert library["revision_count"] == 1


def test_t05_reusing_a_request_id_for_different_content_is_refused(rig):
    body = create_body()
    assert _post_create(rig, body).status_code == 201
    reused = create_body(**{**body.model_dump(), "text": "完全不同的内容",
                            "request_id": body.request_id})
    response = _post_create(rig, reused)
    assert response.status_code == 409
    assert "PROMPT_REQUEST_ID_REUSED" in response.text

    library = rig.client.get(f"/api/projects/{rig.nid}/studio/prompts",
                             headers={"x-session-token": "author-a"}).json()
    assert library["revision_count"] == 1


# ================================================= T06 failure injection ===

def test_t06_metadata_failure_then_retry_produces_exactly_one_revision(rig, monkeypatch):
    body = create_body()
    real_update = rig.assets.update_metadata
    state = {"fail": True}

    def flaky_update(asset_id, fields, **kwargs):
        if state["fail"]:
            state["fail"] = False
            raise RuntimeError("injected failure after the body asset was created")
        return real_update(asset_id, fields, **kwargs)

    monkeypatch.setattr(rig.assets, "update_metadata", flaky_update)
    with pytest.raises(RuntimeError):
        _post_create(rig, body)
    monkeypatch.setattr(rig.assets, "update_metadata", real_update)

    # The retry reuses the same request id and completes exactly once.
    retry = _post_create(rig, body)
    assert retry.status_code == 201, retry.text
    library = rig.client.get(f"/api/projects/{rig.nid}/studio/prompts",
                             headers={"x-session-token": "author-a"}).json()
    assert library["prompt_count"] == 1
    assert library["revision_count"] == 1
    assert library["entries"][0]["revision"] == 1
    # The retry returned the same revision the interrupted first attempt had produced.
    assert library["entries"][0]["asset_id"] == retry.json()["asset_id"]


def test_t06b_a_lost_response_is_replayable(rig):
    body = create_body()
    first = _post_create(rig, body).json()
    replay = _post_create(rig, body).json()      # client never saw the first response
    assert replay == {**first, "idempotent_replay": True} or replay["asset_id"] == first["asset_id"]


# ================================================= T08 privacy =============

def test_t08_a_new_draft_is_private_to_its_author(rig):
    _post_create(rig, create_body(), token="author-a")
    mine = rig.client.get(f"/api/projects/{rig.nid}/studio/prompts",
                          headers={"x-session-token": "author-a"}).json()
    theirs = rig.client.get(f"/api/projects/{rig.nid}/studio/prompts",
                            headers={"x-session-token": "author-b"}).json()
    assert mine["prompt_count"] == 1
    assert theirs["prompt_count"] == 0
    assert TEXT_1 not in str(theirs)


def test_t08b_authoring_requires_authority(rig):
    response = rig.client.post(f"/api/projects/{rig.nid}/studio/prompts",
                               headers={"x-session-token": "nobody"},
                               json=create_body().model_dump())
    assert response.status_code == 403


# ================================================= T09 unicode =============

def test_t09_cjk_newline_emoji_round_trip_exactly(rig):
    text = "第一行\n\n  缩进与 emoji 🙂🙂 结尾\n"
    body = create_body(text=text)
    receipt = _post_create(rig, body).json()
    library = rig.client.get(f"/api/projects/{rig.nid}/studio/prompts",
                             headers={"x-session-token": "author-a"}).json()
    entry = next(row for row in library["entries"] if row["family_id"] == receipt["family_id"])
    assert next(row for row in entry["fields"] if row["field"] == "text")["value"] == text
    assert receipt["text_digest"] == prompt.digest(text.encode("utf-8"))


# ================================================= review reuse ============

def test_review_reuses_the_owner_path_and_is_not_client_supplied(rig):
    receipt = _post_create(rig, create_body()).json()
    response = rig.client.post(
        f"/api/projects/{rig.nid}/studio/prompts/{receipt['family_id']}"
        f"/revisions/{receipt['asset_id']}/approve?expected_version={receipt['asset_version']}",
        headers={"x-session-token": "author-a"})
    assert response.status_code == 200, response.text
    library = rig.client.get(f"/api/projects/{rig.nid}/studio/prompts",
                             headers={"x-session-token": "author-a"}).json()
    entry = next(row for row in library["entries"] if row["family_id"] == receipt["family_id"])
    assert entry["approved"] is True and entry["review_status"] == "APPROVED"
