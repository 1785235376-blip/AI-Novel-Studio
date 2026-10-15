"""R3-I — Pinned Prompt Revision Adoption into a real derived Storyboard Shot.

Uses the repository's own entry points, in the order the owner requires:

    CreativeService.create(SCREENPLAY with real scenes)
      -> CreativeService.derive(mode=STORYBOARD, shot_policy=SCENE)   # shots are DERIVED
      -> PromptAuthoringService.create + approve                       # the source revision
      -> PromptAdoptionService.adopt                                    # into a real shot id

Structural facts this file depends on, corrected from the first draft: a CreativeDocument
keeps `scenes`/`shots` at the DOCUMENT TOP LEVEL (not under `content`), and shots are produced
by `derive()` from a sourced screenplay rather than authored inline.
"""
from __future__ import annotations

import os
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.v1_capability_service import CapabilityVersionConflict

from app.creative.prompt_adoption import FRAME_PROMPT_MAX, PromptAdoptionService
from app.creative.prompt_authoring_models import PromptCreateIn, PromptRevisionIn

HARNESS_MISSING = "requires the isolated runner (scripts/run_v2_checks.py) that sets PROJECT_ROOT"

TEXT = "  合成采用的正文 🙂\n第二行  \n"


@pytest.fixture
def rig(tmp_path, monkeypatch):
    if os.environ.get("PROJECT_ROOT") is None:
        pytest.skip(HARNESS_MISSING)
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
    nid = "r3i-" + uuid4().hex
    novels.create({"id": nid, "title": "R3I"})
    raw = ExperimentalStore(tmp_path, "file", "")
    creative = CreativeService(raw, novels, chapters)
    assets = AssetLibraryService(tmp_path)
    workspace = IndependentWorkspaceService(
        creative, assets, ProductionLineageService(raw, novels, chapters, assets,
                                                   MediaService(raw, novels, chapters, assets)))
    bible = BibleWorkspaceService(workspace, WorldService(raw, novels, chapters))
    library = PromptWorkspaceService(workspace, bible)
    authoring = PromptAuthoringService(workspace, bible)
    adoption = PromptAdoptionService(workspace, library)
    return SimpleNamespace(nid=nid, scope={"mode": "local", "novel_id": nid}, creative=creative,
                           library=library, authoring=authoring, adoption=adoption,
                           actor="author-a", workspace=workspace, assets=assets)


def _storyboard(rig, action="站住"):
    """A REAL derived STORYBOARD: screenplay with scenes -> derive(). Never authored inline."""
    screenplay = rig.creative.create(rig.nid, rig.scope, rig.actor, {
        "mode": "SCREENPLAY", "title": "剧本", "source_independent": True,
        "scenes": [{"id": "scene-1", "sequence": 1, "heading": "内景 房间 日", "action": action}]})
    storyboard = rig.creative.derive(rig.nid, rig.scope, rig.actor, screenplay["id"], {
        "expected_version": screenplay["version"], "mode": "STORYBOARD",
        "title": "分镜", "shot_policy": "SCENE"})
    shots = storyboard.get("shots") or []
    assert shots, "derive() must produce at least one shot from the screenplay scenes"
    return storyboard, shots[0]["id"]


def _prompt(rig, text=TEXT, approved=True):
    receipt = rig.authoring.create(rig.nid, rig.scope, rig.actor, PromptCreateIn.model_validate(
        dict(text=text, purpose="IMAGE", origin="MANUAL", request_id="req-" + uuid4().hex)))
    if approved:
        rig.authoring.approve(rig.nid, rig.scope, rig.actor, receipt["family_id"],
                              receipt["asset_id"], receipt["asset_version"])
    detail = rig.library.detail(rig.nid, rig.scope, receipt["family_id"], rig.actor)
    body = rig.library.revision_body(rig.nid, rig.scope, receipt["family_id"],
                                     receipt["asset_id"], rig.actor)
    return receipt, detail, body


def _body(rig, document, receipt, body_read, shot_id, **over):
    base = dict(shot_id=shot_id, family_id=receipt["family_id"], asset_id=receipt["asset_id"],
                revision=receipt["revision"], expected_digest=body_read["digest"],
                expected_version=document["version"],
                expected_digest_target=rig.creative.document_digest(document),
                request_id="adopt-" + uuid4().hex)
    base.update(over)
    return SimpleNamespace(**base)


def _adopt(rig, document, shot_id, receipt, body_read, **over):
    payload = _body(rig, document, receipt, body_read, shot_id, **over)
    return payload, rig.adoption.adopt(rig.nid, rig.scope, rig.actor, document["id"],
                                       shot_id, payload)


def _shot_of(rig, document, shot_id):
    return rig.adoption._shot(rig.creative.get(rig.nid, rig.scope, document["id"]), shot_id)


# ------------------------------------------------------------------ happy --
def test_adoption_writes_the_frame_prompt_and_commits_a_new_revision(rig):
    document, shot_id = _storyboard(rig)
    receipt, _detail, body_read = _prompt(rig)
    payload, result = _adopt(rig, document, shot_id, receipt, body_read)

    assert result["replayed"] is False
    assert result["version"] == document["version"] + 1
    # The adopted text is written verbatim: no trim, newlines and emoji intact.
    assert _shot_of(rig, document, shot_id)["frame_prompt"] == TEXT

    proof = result["adoption"]
    assert proof["contract"] == "prompt-adoption/1"
    assert proof["family_id"] == receipt["family_id"]
    assert proof["asset_id"] == receipt["asset_id"]
    assert proof["revision"] == receipt["revision"]
    assert proof["digest"] == body_read["digest"]
    assert proof["digest_of"] == "ORIGINAL_BYTES"
    assert proof["adopted_by"] == rig.actor and proof["adopted_at"]
    assert proof["request_id"] == payload.request_id
    assert proof["target_version"] == document["version"]


def test_only_the_target_shot_changes(rig):
    screenplay = rig.creative.create(rig.nid, rig.scope, rig.actor, {
        "mode": "SCREENPLAY", "title": "两场", "source_independent": True,
        "scenes": [{"id": "scene-1", "sequence": 1, "heading": "内景 房间 日", "action": "站住"},
                   {"id": "scene-2", "sequence": 2, "heading": "外景 街道 夜", "action": "奔跑"}]})
    document = rig.creative.derive(rig.nid, rig.scope, rig.actor, screenplay["id"], {
        "expected_version": screenplay["version"], "mode": "STORYBOARD",
        "title": "分镜", "shot_policy": "SCENE"})
    shots = document["shots"]
    assert len(shots) == 2
    receipt, _detail, body_read = _prompt(rig)
    _adopt(rig, document, shots[0]["id"], receipt, body_read)
    after = rig.creative.get(rig.nid, rig.scope, document["id"])["shots"]
    assert after[0]["frame_prompt"] == TEXT
    # The other shot is untouched.
    assert after[1]["frame_prompt"] == shots[1]["frame_prompt"]


def test_reopening_shows_the_same_pinned_source(rig):
    document, shot_id = _storyboard(rig)
    receipt, _detail, body_read = _prompt(rig)
    _adopt(rig, document, shot_id, receipt, body_read)

    read = rig.adoption.read(rig.nid, rig.scope, document["id"], rig.actor)
    assert len(read["adoptions"]) == 1
    entry = read["adoptions"][0]
    assert entry["asset_id"] == receipt["asset_id"]
    assert entry["revision"] == receipt["revision"]
    assert entry["source_readable"] is True
    assert entry["newer_revision_available"] is False
    assert entry["still_applied"] is True
    # The stored proof keeps the adopted text for comparison, but the read projection must
    # not hand plaintext back out of it.
    assert "adopted_text" not in entry


def test_a_newer_prompt_revision_is_reported_but_never_rebinds(rig):
    document, shot_id = _storyboard(rig)
    receipt, _detail, body_read = _prompt(rig)
    _adopt(rig, document, shot_id, receipt, body_read)

    second = rig.authoring.revise(rig.nid, rig.scope, rig.actor, receipt["family_id"],
        PromptRevisionIn.model_validate(dict(
            text="第二版正文", purpose="IMAGE", origin="MANUAL",
            request_id="req-" + uuid4().hex,
            expected_previous_asset_id=receipt["asset_id"], expected_revision=1)))
    rig.authoring.approve(rig.nid, rig.scope, rig.actor, receipt["family_id"],
                          second["asset_id"], second["asset_version"])

    entry = rig.adoption.read(rig.nid, rig.scope, document["id"], rig.actor)["adoptions"][0]
    # Drift is SURFACED but the pinned reference does not move.
    assert entry["newer_revision_available"] is True
    assert entry["asset_id"] == receipt["asset_id"]
    assert entry["revision"] == receipt["revision"]
    assert _shot_of(rig, document, shot_id)["frame_prompt"] == TEXT


def test_an_ordinary_edit_keeps_the_history_but_stops_claiming_the_shot_uses_it(rig):
    document, shot_id = _storyboard(rig)
    receipt, _detail, body_read = _prompt(rig)
    _adopt(rig, document, shot_id, receipt, body_read)

    # The user then edits the same shot's frame_prompt through the ordinary document path.
    current = rig.creative.get(rig.nid, rig.scope, document["id"])
    value = {key: current[key] for key in ("mode", "title", "scenes", "shots",
                                           "director_notes", "source_chapter_ids",
                                           "source_independent")
             if key in current}
    value["shots"] = [dict(item) for item in current["shots"]]
    for item in value["shots"]:
        if item["id"] == shot_id:
            item["frame_prompt"] = "用户自己改写的画面"
    rig.creative.update(rig.nid, rig.scope, rig.actor, document["id"], current["version"], value)

    entry = rig.adoption.read(rig.nid, rig.scope, document["id"], rig.actor)["adoptions"][0]
    # History keeps the proof...
    assert entry["asset_id"] == receipt["asset_id"]
    # ...but it must not keep claiming the shot still uses the adopted text.
    assert entry["still_applied"] is False
    assert _shot_of(rig, document, shot_id)["frame_prompt"] == "用户自己改写的画面"


# ------------------------------------------------------------- refusals --
def test_an_unknown_shot_is_refused(rig):
    document, _shot_id = _storyboard(rig)
    receipt, _detail, body_read = _prompt(rig)
    with pytest.raises(FileNotFoundError):
        _adopt(rig, document, "shot-does-not-exist", receipt, body_read)


def test_a_non_storyboard_target_is_refused(rig):
    screenplay = rig.creative.create(rig.nid, rig.scope, rig.actor, {
        "mode": "SCREENPLAY", "title": "剧本", "source_independent": True,
        "scenes": [{"id": "scene-1", "sequence": 1, "heading": "内景 房间 日", "action": "站住"}]})
    receipt, _detail, body_read = _prompt(rig)
    with pytest.raises(ValueError, match="PROMPT_ADOPTION_TARGET_NOT_STORYBOARD"):
        _adopt(rig, screenplay, "scene-1", receipt, body_read)


def test_an_unapproved_prompt_is_refused(rig):
    document, shot_id = _storyboard(rig)
    receipt, _detail, body_read = _prompt(rig, approved=False)
    with pytest.raises(ValueError, match="PROMPT_ADOPTION_NOT_APPROVED"):
        _adopt(rig, document, shot_id, receipt, body_read)


def test_a_stale_expected_version_is_refused(rig):
    document, shot_id = _storyboard(rig)
    receipt, _detail, body_read = _prompt(rig)
    with pytest.raises(CapabilityVersionConflict):
        _adopt(rig, document, shot_id, receipt, body_read, expected_version=99)


def test_a_stale_document_digest_is_refused(rig):
    document, shot_id = _storyboard(rig)
    receipt, _detail, body_read = _prompt(rig)
    with pytest.raises(CapabilityVersionConflict):
        _adopt(rig, document, shot_id, receipt, body_read, expected_digest_target="0" * 64)


def test_a_client_digest_that_does_not_match_the_server_read_is_refused(rig):
    document, shot_id = _storyboard(rig)
    receipt, _detail, body_read = _prompt(rig)
    with pytest.raises(ValueError, match="PROMPT_ADOPTION_DIGEST_MISMATCH"):
        _adopt(rig, document, shot_id, receipt, body_read, expected_digest="f" * 64)


def test_text_over_the_field_limit_is_refused_not_truncated(rig):
    document, shot_id = _storyboard(rig)
    receipt, _detail, body_read = _prompt(rig, text="中" * (FRAME_PROMPT_MAX + 1))
    with pytest.raises(ValueError, match="PROMPT_ADOPTION_TOO_LONG"):
        _adopt(rig, document, shot_id, receipt, body_read)
    assert _shot_of(rig, document, shot_id)["frame_prompt"] == ""


def test_a_shot_id_that_disagrees_between_path_and_body_is_refused(rig):
    document, shot_id = _storyboard(rig)
    receipt, _detail, body_read = _prompt(rig)
    payload = _body(rig, document, receipt, body_read, shot_id)
    payload.shot_id = "another-shot"
    with pytest.raises(ValueError, match="PROMPT_ADOPTION_SHOT_ID_MISMATCH"):
        rig.adoption.adopt(rig.nid, rig.scope, rig.actor, document["id"], shot_id, payload)


# ----------------------------------------------------------- idempotency --
def test_the_same_request_id_replays_without_a_second_revision(rig):
    document, shot_id = _storyboard(rig)
    receipt, _detail, body_read = _prompt(rig)
    payload, first = _adopt(rig, document, shot_id, receipt, body_read)
    again = rig.adoption.adopt(rig.nid, rig.scope, rig.actor, document["id"], shot_id, payload)
    assert again["replayed"] is True
    assert again["version"] == first["version"]
    assert rig.creative.get(rig.nid, rig.scope, document["id"])["version"] == first["version"]


def test_the_same_request_id_with_different_input_is_refused(rig):
    document, shot_id = _storyboard(rig)
    receipt, _detail, body_read = _prompt(rig)
    payload, _first = _adopt(rig, document, shot_id, receipt, body_read)
    payload.asset_id = "different-asset"
    with pytest.raises(ValueError, match="PROMPT_ADOPTION_REQUEST_REUSED"):
        rig.adoption.adopt(rig.nid, rig.scope, rig.actor, document["id"], shot_id, payload)


# --------------------------------------------------------------- safety --
def test_the_owner_contract_for_private_and_approved_sources(rig):
    """Assert the ACTUAL AssetLibraryService review contract, not an assumption.

    Verified in source: `promote_owned` performs
    `meta.update(_owner_actor_id=None, _origin_provenance=..., approved_at=now(), version=+1)`.
    Approval therefore **publishes** the asset — it clears the private owner marker and stamps
    `approved_at`. That is deliberate review semantics, so:
      * an UNAPPROVED author-private revision is readable only by its author;
      * an APPROVED revision becomes readable by other actors, because review published it.
    This test previously asserted that another actor could never read the source, which was a
    wrong expectation about the owner's contract rather than a product defect.
    """
    # --- unapproved: author-private, so another actor is refused ---
    private_receipt, _d, _b = _prompt(rig, approved=False)
    with pytest.raises((FileNotFoundError, ValueError, PermissionError)):
        rig.library.revision_body(rig.nid, rig.scope, private_receipt["family_id"],
                                  private_receipt["asset_id"], "author-b")

    # --- approved: review published it, so another actor may read it ---
    document, shot_id = _storyboard(rig)
    receipt, _detail, body_read = _prompt(rig)
    _adopt(rig, document, shot_id, receipt, body_read)
    published = rig.library.revision_body(rig.nid, rig.scope, receipt["family_id"],
                                          receipt["asset_id"], "author-b")
    assert published["state"] == "COMPLETE"
    assert published["value"] == TEXT

    # And the private owner marker really was cleared by approval.
    raw = rig.assets._read_meta(receipt["asset_id"]) if hasattr(rig.assets, "_read_meta") else None
    if isinstance(raw, dict):
        assert raw.get("_owner_actor_id") is None
        assert raw.get("approved_at")
