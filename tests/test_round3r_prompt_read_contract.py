"""R3-R — read-contract fixes for the Prompt system.

Every test in this file is written against the **correct** contract, so against the
`1bce019` baseline they fail. That failure is the reproduction evidence the task book
requires; the fixes follow in the same sub-phase.

Covered: R3-R-01 read limit / 200th item and family across the boundary,
R3-R-02 `history_complete` and chain anomalies, R3-R-03 body truncation and UTF-8,
R3-R-04 shot-context structure, R3-R-05 shot index independent of cast,
R3-R-06 actor passthrough for private drafts, R3-R-07 strict payload validation,
R3-R-08 redaction is not a single-field mask.
"""
from __future__ import annotations

import base64
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.creative import prompt_asset as prompt
from app.creative import prompt_workspace as workspace_module

HARNESS_MISSING = "requires the isolated runner (scripts/run_v2_checks.py) that sets PROJECT_ROOT"


def payload(**overrides):
    base = dict(family_id="fam-1", revision=1, purpose="IMAGE", origin="MANUAL",
                negative_prompt="low quality", model_reference="flux-1", parameters={"steps": 28},
                seed=7, reference_asset_ids=[], character_ids=[], scene_ids=[], shot_ids=[],
                change_note="初稿", change_reason="第一版")
    base.update(overrides)
    return prompt.build_payload(**base)


def asset(asset_id: str, body, *, version=2, kind="prompt", deleted=False):
    row = {"id": asset_id, "kind": kind, "version": version, "review_status": "DRAFT",
           "approved_at": None, "parameters": {"prompt": body}}
    if deleted:
        row["deleted_at"] = "2026-10-15T00:00:00Z"
    return row


# ============================================================ R3-R-07 =======
# Strict payload validation (pure — these fail on the baseline's partial check).

def test_payload_rejects_a_string_that_is_not_a_boolean():
    """`bool('false')` is True — a truthiness check would silently accept it."""
    strict = prompt.validate_payload({**payload(), "redacted": "false"})
    assert strict["ok"] is False
    assert strict["reason"] == "PROMPT_PAYLOAD_TYPE_INVALID"


def test_payload_rejects_a_bool_where_a_business_integer_is_required():
    """`True` is an `int` in Python; revision must be an exact integer."""
    assert prompt.validate_payload({**payload(), "revision": True})["ok"] is False
    assert prompt.validate_payload({**payload(), "seed": False})["ok"] is False


def test_payload_rejects_unknown_keys_and_bad_shapes():
    assert prompt.validate_payload({**payload(), "surprise": 1})["ok"] is False
    assert prompt.validate_payload({**payload(), "reference_asset_ids": "a1"})["ok"] is False
    assert prompt.validate_payload({**payload(), "character_ids": [1, 2]})["ok"] is False
    assert prompt.validate_payload({**payload(), "parameters": []})["ok"] is False
    assert prompt.validate_payload({**payload(), "purpose": "HOLOGRAM"})["ok"] is False
    assert prompt.validate_payload({**payload(), "change_note": "x" * 20001})["ok"] is False


def test_payload_validator_accepts_the_real_builder_output():
    strict = prompt.validate_payload(payload())
    assert strict["ok"] is True and strict["reason"] is None


def test_list_and_detail_agree_on_payload_validity_and_counting():
    """`revision_count` must have one documented meaning: valid revisions only."""
    rows = [asset("A1", payload(revision=1)), asset("BAD", {"contract": "other/1"})]
    projection = prompt.project_prompt_library(rows, bible=None)
    assert projection["prompt_count"] == 1
    assert projection["revision_count"] == 1
    assert projection["malformed_count"] == 1
    # Detail must apply the same validity gate, not bypass it.
    with pytest.raises(FileNotFoundError):
        prompt.project_prompt_detail("BAD", rows, bible=None)


# ============================================================ R3-R-03 =======
# Body truncation and UTF-8.

def test_full_body_is_exact_utf8_within_the_cap_and_states_it_is_complete():
    text = "中文字幕\n第二行 with spaces"
    body = prompt.read_prompt_body(text.encode("utf-8"), limit=4096)
    assert body["state"] == "COMPLETE"
    assert body["value"] == text
    assert body["truncated"] is False
    assert body["decodable"] is True
    assert body["original_length"] == len(text.encode("utf-8"))
    assert body["digest"] == prompt.digest(text.encode("utf-8"))
    assert body["digest_of"] == "ORIGINAL_BYTES"


def test_over_limit_body_is_marked_truncated_and_never_claims_completeness():
    raw = ("字" * 100).encode("utf-8")
    body = prompt.read_prompt_body(raw, limit=30)
    assert body["state"] == "TRUNCATED"
    assert body["truncated"] is True
    assert body["original_length"] == len(raw)
    assert body["digest"] == prompt.digest(raw)
    assert body["digest_of"] == "ORIGINAL_BYTES"
    # The preview is what it is — and it must not be presented as the full text.
    assert len(body["value"]) < len(raw)


def test_invalid_utf8_is_reported_not_silently_replaced():
    body = prompt.read_prompt_body(b"\xff\xfe bad bytes", limit=4096)
    assert body["state"] == "UNDECODABLE"
    assert body["decodable"] is False
    assert body["value"] is None
    assert body["digest"] == prompt.digest(b"\xff\xfe bad bytes")


def test_multibyte_boundary_never_produces_a_broken_character():
    raw = "日本語テキスト".encode("utf-8")
    for limit in range(1, len(raw) + 1):
        body = prompt.read_prompt_body(raw, limit=limit)
        if body["value"] is not None:
            # Any preview must still be valid UTF-8 — no half-character output.
            body["value"].encode("utf-8")


def test_zero_length_and_empty_text_are_handled():
    body = prompt.read_prompt_body(b"", limit=16)
    assert body["state"] == "COMPLETE"
    assert body["value"] == ""
    assert body["original_length"] == 0


def test_a_truncated_preview_hash_is_never_presented_as_the_asset_hash():
    raw = ("x" * 500).encode()
    body = prompt.read_prompt_body(raw, limit=10)
    assert body["digest"] != prompt.digest(body["value"])
    assert body["digest_of"] == "ORIGINAL_BYTES"


# ============================================================ R3-R-04 =======
# Shot context must adapt the REAL `project_shot_cards()` output.

def test_prompt_context_maps_real_shot_cards_without_losing_fields():
    """`project_shot_cards()` returns top-level fields, not a `dimensions` list."""
    from app.creative.director_intent import project_shot_cards

    document = {
        "id": "doc-1", "version": 3, "mode": "STORYBOARD", "title": "t", "status": "DRAFT",
        "visual_target": {"style": "冷峻写实", "atmosphere": "压抑"},
        "scenes": [{"id": "sc-1", "sequence": 1, "heading": "INT. 旧城公寓 - 夜", "characters": ["c1"]}],
        "shots": [{"number": 1, "scene_id": "sc-1", "shot_size": "WIDE", "camera_motion": "DOLLY",
                   "lens": "NORMAL", "composition": "CENTER", "lighting": "暖光", "characters": ["c1"],
                   "action": "推门", "emotion": "迟疑", "sound": "雨声", "duration_seconds": 6}],
    }
    cards = project_shot_cards(document)
    assert cards and "dimensions" not in cards[0], "the real producer must not be assumed to emit dimensions"

    context = prompt.project_prompt_context(shot_cards=cards, bible=None)
    shot = next(source for source in context["sources"] if source["kind"] == "SHOT_CARD")
    assert shot["dimensions"], "a real non-empty shot card must not map to zero dimensions"
    fields = {row["field"] for row in shot["dimensions"]}
    assert {"lighting", "action", "emotion"} <= fields
    authored = {row["field"]: row["authored"] for row in shot["dimensions"]}
    assert authored["lighting"] is True


def test_prompt_context_keeps_document_and_shot_identity():
    from app.creative.director_intent import project_shot_cards

    document = {"id": "doc-9", "version": 1, "mode": "STORYBOARD", "title": "t", "status": "DRAFT",
                "scenes": [{"id": "sc-1", "sequence": 1, "heading": "H"}],
                "shots": [{"number": 1, "scene_id": "sc-1", "action": "走"}]}
    context = prompt.project_prompt_context(shot_cards=project_shot_cards(document), bible=None,
                                            document_id="doc-9")
    shot = next(source for source in context["sources"] if source["kind"] == "SHOT_CARD")
    assert shot["id"], "shot identity must be carried"
    assert context.get("document_id") == "doc-9"


def test_prompt_context_does_not_treat_an_absent_field_as_a_valid_state():
    context = prompt.project_prompt_context(shot_cards=[{"shot_id": "s1", "dimensions": []}], bible=None)
    shot = next(source for source in context["sources"] if source["kind"] == "SHOT_CARD")
    assert shot["dimensions"] == []


# ==================================================== service-level rig =====

@pytest.fixture
def rig(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    if os.environ.get("PROJECT_ROOT") is None:
        pytest.skip(HARNESS_MISSING)
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.creative.bible_workspace import BibleWorkspaceService
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
    nid = "r3r-" + uuid4().hex
    novels.create({"id": nid, "title": "R3R"})
    raw = ExperimentalStore(tmp_path, "file", "")
    creative = CreativeService(raw, novels, chapters)
    assets = AssetLibraryService(tmp_path)
    workspace = IndependentWorkspaceService(
        creative, assets, ProductionLineageService(raw, novels, chapters, assets,
                                                   MediaService(raw, novels, chapters, assets)))
    bible = BibleWorkspaceService(workspace, WorldService(raw, novels, chapters))
    prompts = PromptWorkspaceService(workspace, bible)

    def authorize(project_id, token, branch, permission):
        if token not in {"author-a", "author-b"}:
            raise HTTPException(403, {"code": "CREATIVE_AUTHORITY_INVALID"})
        return token, {"mode": "local", "novel_id": project_id}

    from app.creative.workspace_api import create_independent_workspace_router
    app = FastAPI()
    app.include_router(create_independent_workspace_router(
        workspace, authorize, lambda flag: None,
        create_project=lambda body, token: (_ for _ in ()).throw(AssertionError("not used")),
        workspace_writer=lambda token: "author-a", bible_service=bible, prompt_service=prompts), prefix="/api")
    return SimpleNamespace(client=TestClient(app), nid=nid, assets=assets, workspace=workspace,
                           prompts=prompts, scope={"mode": "local", "novel_id": nid})


def _create(rig, body, text="prompt text", *, actor="author-a", private=False, family=None):
    with rig.workspace._asset_scope(rig.nid, rig.scope):
        created = rig.assets.create(rig.nid, "prompt.txt", base64.b64encode(text.encode()).decode(),
                                    media_type="text/plain", kind="prompt",
                                    required_features=("narrative_production_v2",),
                                    owner_actor_id=actor if private else None)
        # The owner's own read requires the actor: a private asset is invisible to an
        # anonymous read, which is exactly the filtering R3-R-06 must not bypass.
        rig.assets.update_metadata(created["id"], {"parameters": {"prompt": body}},
                                   branch_id=rig.scope.get("branch_id"), actor_id=actor)
    return created


# ============================================================ R3-R-01 =======
# Read limit: the 200th/201st item and a family across the boundary.

def test_read_limit_reports_truncation_and_never_loses_the_200th_body(rig, monkeypatch):
    monkeypatch.setattr(workspace_module, "MAX_PROMPTS", 3)
    for index in range(4):
        _create(rig, payload(family_id=f"fam-{index}", change_note=f"n{index}"),
                text=f"body-{index}", family=f"fam-{index}")
    projection = rig.prompts.library(rig.nid, rig.scope)
    assert projection["returned"] == 3
    assert projection["truncated"] is True
    assert projection["has_more"] is True
    assert projection["total_known"] is False
    # Every returned entry must have its body read — the boundary item included.
    for entry in projection["entries"]:
        text_field = next(row for row in entry["fields"] if row["field"] == "text")
        assert text_field["authored"] is True, "a returned entry lost its body at the read boundary"


def test_a_family_outside_the_first_page_still_resolves_in_detail(rig, monkeypatch):
    monkeypatch.setattr(workspace_module, "MAX_PROMPTS", 2)
    for index in range(4):
        _create(rig, payload(family_id=f"fam-{index}"), text=f"body-{index}")
    detail = rig.prompts.detail(rig.nid, rig.scope, "fam-3")
    assert detail["family_id"] == "fam-3"


def test_read_limit_is_the_declared_constant():
    assert workspace_module.MAX_PROMPTS == 200


# ============================================================ R3-R-02 =======

def test_history_complete_is_false_when_the_read_was_bounded(rig, monkeypatch):
    """Detail has its own scan bound; when it is hit, completeness must say so."""
    monkeypatch.setattr(workspace_module, "MAX_PROMPT_SCAN", 1)
    for index in range(3):
        _create(rig, payload(family_id=f"fam-{index}"), text=f"b{index}")
    detail = rig.prompts.detail(rig.nid, rig.scope, "fam-0")
    assert detail["read_complete"] is False
    assert detail["history_complete"] is False
    assert detail["scan_truncated"] is True


def test_chain_anomalies_are_reported_not_sorted_into_a_fake_history():
    rows = [asset("A1", payload(revision=2)), asset("A2", payload(revision=2))]
    detail = prompt.project_prompt_detail("fam-1", rows, bible=None)
    assert any(row["kind"] == "DUPLICATE_REVISION" for row in detail["anomalies"])


def test_a_broken_predecessor_is_reported():
    rows = [asset("A1", payload(revision=1)),
            asset("A2", payload(revision=2, previous_asset_id="missing"))]
    detail = prompt.project_prompt_detail("fam-1", rows, bible=None)
    assert any(row["kind"] == "BROKEN_PREDECESSOR" for row in detail["anomalies"])


def test_a_cross_family_predecessor_is_reported():
    rows = [asset("A1", payload(family_id="other", revision=1)),
            asset("A2", payload(revision=2, previous_asset_id="A1"))]
    detail = prompt.project_prompt_detail("fam-1", rows, bible=None)
    assert any(row["kind"] == "CROSS_FAMILY_LINK" for row in detail["anomalies"])


def test_an_unreadable_revision_is_reported_rather_than_assumed_readable():
    rows = [asset("A1", payload(revision=1)), asset("A2", payload(revision=2), deleted=True)]
    detail = prompt.project_prompt_detail("fam-1", rows, bible=None)
    assert detail["history_complete"] is False
    assert any(row["kind"] == "REVISION_UNAVAILABLE" for row in detail["anomalies"])


# ============================================================ R3-R-05 =======

def test_shot_index_does_not_depend_on_a_character_being_present(rig):
    """An empty establishing shot with no cast must still be a valid binding target."""
    from app.creative.director_intent import project_shot_cards

    document = {"id": "doc-empty", "version": 1, "mode": "STORYBOARD", "title": "t", "status": "DRAFT",
                "scenes": [{"id": "sc-1", "sequence": 1, "heading": "EXT. 天台 - 日"}],
                "shots": [{"number": 1, "scene_id": "sc-1", "action": "空镜"}]}
    cards = project_shot_cards(document)
    assert cards[0]["character"]["values"] == []
    index = prompt.shot_index([{"document_id": "doc-empty", "cards": cards}])
    assert "doc-empty:1" in index["entries"]
    assert index["entries"]["doc-empty:1"]["characters"] == []


def test_shot_identity_is_scoped_to_its_document(rig):
    from app.creative.director_intent import project_shot_cards

    def document(doc_id):
        return {"id": doc_id, "version": 1, "mode": "STORYBOARD", "title": doc_id, "status": "DRAFT",
                "scenes": [{"id": "sc-1", "sequence": 1, "heading": "H"}],
                "shots": [{"number": 1, "scene_id": "sc-1", "action": doc_id}]}

    index = prompt.shot_index([{"document_id": "doc-a", "cards": project_shot_cards(document("doc-a"))},
                               {"document_id": "doc-b", "cards": project_shot_cards(document("doc-b"))}])
    assert index["scope_aware"] is True
    assert index["entries"]["doc-a:1"]["document_id"] == "doc-a"
    assert index["entries"]["doc-b:1"]["document_id"] == "doc-b"


# ============================================================ R3-R-06 =======

def test_a_private_draft_is_readable_by_its_author_through_the_api(rig):
    _create(rig, payload(family_id="priv"), text="secret body", actor="author-a", private=True)
    response = rig.client.get(f"/api/projects/{rig.nid}/studio/prompts",
                              headers={"x-session-token": "author-a"})
    assert response.status_code == 200
    assert response.json()["prompt_count"] == 1


def test_a_private_draft_is_not_readable_by_another_author(rig):
    _create(rig, payload(family_id="priv"), text="secret body", actor="author-a", private=True)
    response = rig.client.get(f"/api/projects/{rig.nid}/studio/prompts",
                              headers={"x-session-token": "author-b"})
    assert response.status_code == 200
    body = response.json()
    assert body["prompt_count"] == 0
    assert "secret body" not in response.text


# ============================================================ R3-R-08 =======

def test_a_redacted_prompt_leaks_no_text_anywhere_in_the_projection(rig):
    body = payload(family_id="red", redacted=True, change_note="秘密原因", change_reason="秘密理由")
    _create(rig, body, text="highly secret prompt text")
    response = rig.client.get(f"/api/projects/{rig.nid}/studio/prompts",
                              headers={"x-session-token": "author-a"})
    assert "highly secret prompt text" not in response.text
    assert "秘密原因" not in response.text
    entry = response.json()["entries"][0]
    assert entry["redacted"] is True


def test_redaction_does_not_grant_permission(rig):
    """A redacted prompt is still subject to the owner's permission rules."""
    _create(rig, payload(family_id="red2", redacted=True), text="secret", actor="author-a", private=True)
    response = rig.client.get(f"/api/projects/{rig.nid}/studio/prompts",
                              headers={"x-session-token": "author-b"})
    assert response.json()["prompt_count"] == 0


def test_errors_never_echo_prompt_text(rig):
    response = rig.client.get(f"/api/projects/{rig.nid}/studio/prompts/nope",
                              headers={"x-session-token": "author-a"})
    assert response.status_code == 404
    assert "prompt text" not in response.text
