"""Bounded read-contract follow-up (§3 of the after-f83cadb directive).

Producer-to-consumer regressions for four specific observations, each reproduced against
the real module before being fixed:

* §3.1 `_decode_chunk` reported invalid UTF-8 as `COMPLETE` (a fully read body such as
  ``b"OK\\xff"`` decoded to ``"OK"``). Only a real preview boundary may drop an unfinished
  trailing codepoint.
* §3.2 library read completeness was not propagated into each family entry.
* §3.3 deleted revisions could never reach the detail projector.
* §3.4 a family's historical change notes followed the **head's** redaction flag.
"""
from __future__ import annotations

import base64
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.creative import prompt_asset as prompt

HARNESS_MISSING = "requires the isolated runner (scripts/run_v2_checks.py) that sets PROJECT_ROOT"


def payload(**overrides):
    base = dict(family_id="fam-1", revision=1, purpose="IMAGE", origin="MANUAL",
                negative_prompt="low quality", model_reference="flux-1", parameters={"steps": 28},
                seed=7, reference_asset_ids=[], character_ids=[], scene_ids=[], shot_ids=[],
                change_note="初稿", change_reason="第一版")
    base.update(overrides)
    return prompt.build_payload(**base)


def asset(asset_id: str, body, *, version=2, deleted=False):
    row = {"id": asset_id, "kind": "prompt", "version": version, "review_status": "DRAFT",
           "approved_at": None, "parameters": {"prompt": body}}
    if deleted:
        row["deleted_at"] = "2026-10-15T00:00:00Z"
    return row


# ============================================================== §3.1 ========

def test_a_fully_read_body_with_a_trailing_invalid_byte_is_undecodable():
    """The reproduced defect: `b"OK\\xff"` at full length reported COMPLETE "OK"."""
    body = prompt.read_prompt_body(b"OK\xff", limit=65536)
    assert body["state"] == prompt.BODY_UNDECODABLE
    assert body["value"] is None
    assert body["decodable"] is False
    assert body["body_validated"] is False


def test_a_fully_read_body_with_an_unfinished_multibyte_tail_is_undecodable():
    body = prompt.read_prompt_body(b"OK\xe4\xb8", limit=65536)
    assert body["state"] == prompt.BODY_UNDECODABLE
    assert body["value"] is None


def test_an_invalid_byte_inside_a_preview_is_not_hidden_by_the_cut():
    """`b"OK\\xffX"` at limit 3 previously returned TRUNCATED "OK" with the 0xff gone."""
    body = prompt.read_prompt_body(b"OK\xffX", limit=3)
    assert body["state"] == prompt.BODY_UNDECODABLE
    assert body["value"] is None


def test_a_preview_may_only_drop_an_unfinished_trailing_codepoint():
    body = prompt.read_prompt_body("OK中X".encode("utf-8"), limit=4)
    assert body["state"] == prompt.BODY_TRUNCATED
    assert body["value"] == "OK"
    assert body["decodable"] is True


def test_a_complete_valid_body_round_trips_exactly():
    for text in ("", "hello", "中文内容", "行1\n行2\n", "emoji 🙂 混排", "  spaced  "):
        raw = text.encode("utf-8")
        body = prompt.read_prompt_body(raw, limit=65536)
        assert body["state"] == prompt.BODY_COMPLETE
        assert body["value"] == text
        assert body["body_validated"] is True
        assert body["tail_unverified"] is False
        assert body["original_length"] == len(raw)
        assert body["digest"] == prompt.digest(raw)


def test_interior_invalid_bytes_are_reported():
    for raw in (b"OK\xff\xff more", b"\x80 leading", b"mid\xc3\x28dle"):
        body = prompt.read_prompt_body(raw, limit=65536)
        assert body["state"] == prompt.BODY_UNDECODABLE, raw
        assert body["value"] is None


def test_an_emoji_cut_at_the_boundary_is_a_preview_not_a_corruption():
    raw = "OK🙂X".encode("utf-8")
    body = prompt.read_prompt_body(raw, limit=5)
    assert body["state"] == prompt.BODY_TRUNCATED
    assert body["value"] == "OK"
    # The returned preview must itself be valid UTF-8.
    body["value"].encode("utf-8")


def test_zero_exact_and_over_limit_lengths():
    raw = "中".encode("utf-8")
    assert prompt.read_prompt_body(b"", limit=0)["state"] == prompt.BODY_COMPLETE
    assert prompt.read_prompt_body(raw, limit=len(raw))["state"] == prompt.BODY_COMPLETE
    over = prompt.read_prompt_body(raw, limit=len(raw) - 1)
    assert over["state"] == prompt.BODY_TRUNCATED
    assert over["truncated"] is True and over["tail_unverified"] is True


def test_a_preview_never_promises_its_unread_tail_is_valid():
    """A truncated read must not claim the whole body was validated."""
    raw = b"valid prefix" + b"\xff\xff\xff"
    body = prompt.read_prompt_body(raw, limit=4)
    assert body["truncated"] is True
    assert body["body_validated"] is False
    assert body["tail_unverified"] is True
    assert body["digest"] == prompt.digest(raw)


def test_the_digest_always_describes_the_original_bytes():
    raw = b"some bytes \xff"
    body = prompt.read_prompt_body(raw, limit=4)
    assert body["digest"] == prompt.digest(raw)
    assert body["digest_of"] == "ORIGINAL_BYTES"
    assert body["digest"] != prompt.digest(body["value"] or "")


# ============================================================== §3.2 ========

def test_an_incomplete_library_does_not_claim_authoritative_family_history():
    projection = prompt.project_prompt_library(
        [asset("A1", payload(revision=1))], bible=None,
        coverage={"returned": 1, "limit": 1, "truncated": True, "has_more": True,
                  "total_known": False})
    assert projection["truncated"] is True
    entry = projection["entries"][0]
    assert entry["read_complete"] is False
    assert entry["history_complete"] is False


def test_a_complete_library_still_reports_complete_family_history():
    projection = prompt.project_prompt_library(
        [asset("A1", payload(revision=1))], bible=None,
        coverage={"returned": 1, "limit": 200, "truncated": False, "has_more": False,
                  "total_known": False})
    entry = projection["entries"][0]
    assert entry["read_complete"] is True
    assert entry["history_complete"] is True


def test_scanned_assets_and_projected_families_are_distinct_labels():
    rows = [asset("A1", payload(revision=1)), asset("A2", payload(revision=2, previous_asset_id="A1"))]
    projection = prompt.project_prompt_library(
        rows, bible=None,
        coverage={"returned": 2, "limit": 200, "truncated": False, "has_more": False,
                  "total_known": False})
    assert projection["scanned_assets"] == 2
    assert projection["projected_families"] == 1
    assert projection["prompt_count"] == 1
    assert projection["revision_count"] == 2


# ============================================================== §3.4 ========

def test_a_masked_history_note_stays_masked_under_an_unmasked_head():
    rows = [asset("A1", payload(revision=1, redacted=True, change_note="秘密", change_reason="秘密理由")),
            asset("A2", payload(revision=2, redacted=False, change_note="公开", change_reason="公开理由",
                                previous_asset_id="A1"))]
    detail = prompt.project_prompt_detail("fam-1", rows, bible=None)
    versions = {row["revision"]: row for row in detail["versions"]}
    assert versions[1]["redacted"] is True
    assert versions[1]["change_note"] == prompt.digest("秘密")
    assert versions[1]["change_reason"] == prompt.digest("秘密理由")
    assert versions[2]["redacted"] is False
    assert versions[2]["change_note"] == "公开"
    assert versions[2]["change_reason"] == "公开理由"
    # The historical note must not appear in cleartext anywhere in the projection.
    assert "秘密" not in str(detail)


def test_a_cleartext_history_note_stays_cleartext_under_a_masked_head():
    rows = [asset("A1", payload(revision=1, redacted=False, change_note="旧说明")),
            asset("A2", payload(revision=2, redacted=True, change_note="新秘密",
                                previous_asset_id="A1"))]
    detail = prompt.project_prompt_detail("fam-1", rows, bible=None)
    versions = {row["revision"]: row for row in detail["versions"]}
    assert versions[1]["redacted"] is False
    assert versions[1]["change_note"] == "旧说明"
    assert versions[2]["redacted"] is True
    assert versions[2]["change_note"] == prompt.digest("新秘密")


# ============================================================== §3.3 ========

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
    nid = "r3s-" + uuid4().hex
    novels.create({"id": nid, "title": "R3S"})
    raw = ExperimentalStore(tmp_path, "file", "")
    creative = CreativeService(raw, novels, chapters)
    assets = AssetLibraryService(tmp_path)
    workspace = IndependentWorkspaceService(
        creative, assets, ProductionLineageService(raw, novels, chapters, assets,
                                                   MediaService(raw, novels, chapters, assets)))
    bible = BibleWorkspaceService(workspace, WorldService(raw, novels, chapters))
    prompts = PromptWorkspaceService(workspace, bible)

    def authorize(project_id, token, branch, permission):
        if token != "author-a":
            raise HTTPException(403, {"code": "CREATIVE_AUTHORITY_INVALID"})
        return token, {"mode": "local", "novel_id": project_id}

    from app.creative.workspace_api import create_independent_workspace_router
    app = FastAPI()
    app.include_router(create_independent_workspace_router(
        workspace, authorize, lambda flag: None,
        create_project=lambda body, token: (_ for _ in ()).throw(AssertionError("not used")),
        workspace_writer=lambda token: "author-a", bible_service=bible, prompt_service=prompts),
        prefix="/api")
    return SimpleNamespace(client=TestClient(app), nid=nid, assets=assets, workspace=workspace,
                           prompts=prompts, scope={"mode": "local", "novel_id": nid})


def _create(rig, body, text="prompt text"):
    with rig.workspace._asset_scope(rig.nid, rig.scope):
        created = rig.assets.create(rig.nid, "prompt.txt", base64.b64encode(text.encode()).decode(),
                                    media_type="text/plain", kind="prompt",
                                    required_features=("narrative_production_v2",))
        rig.assets.update_metadata(created["id"], {"parameters": {"prompt": body}},
                                   branch_id=rig.scope.get("branch_id"))
    return created


def test_a_deleted_newest_revision_is_visible_as_removed_in_detail(rig):
    first = _create(rig, payload(revision=1))
    second = _create(rig, payload(revision=2, previous_asset_id=first["id"],
                                  change_note="第二版", change_reason="修改"))
    with rig.workspace._asset_scope(rig.nid, rig.scope):
        rig.assets.delete(second["id"], branch_id=rig.scope.get("branch_id"))

    detail = rig.prompts.detail(rig.nid, rig.scope, "fam-1", "author-a")
    revisions = {row["revision"]: row for row in detail["versions"]}
    assert revisions[2]["available"] is False
    assert any(row["kind"] == "REVISION_UNAVAILABLE" for row in detail["anomalies"])
    assert detail["history_complete"] is False
    # A deleted body must never be exposed.
    assert detail["body"]["fetch"] in ("TOMBSTONE", "UNAVAILABLE")
    assert detail["body"]["value"] is None


def test_the_library_still_excludes_deleted_rows(rig):
    only = _create(rig, payload(revision=1))
    with rig.workspace._asset_scope(rig.nid, rig.scope):
        rig.assets.delete(only["id"], branch_id=rig.scope.get("branch_id"))
    library = rig.prompts.library(rig.nid, rig.scope, "author-a")
    assert library["prompt_count"] == 0
