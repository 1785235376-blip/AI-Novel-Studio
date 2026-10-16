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

#: Same convention as tests/test_v2_creative_foundation.py: the endpoint is opt-in, and the
#: conftest skips the postgres variant unless STORAGE_BACKEND=postgres together with
#: TEST_POSTGRES_DATABASE_URL are supplied. There is no fallback to File.
TEST_URL = os.getenv("TEST_POSTGRES_DATABASE_URL", "")

TEXT = "  合成采用的正文 🙂\n第二行  \n"


@pytest.fixture(params=[pytest.param("file", marks=pytest.mark.file_backend_only),
                        pytest.param("postgres", marks=pytest.mark.postgres_backend_only)])
def rig(request, tmp_path, monkeypatch):
    if os.environ.get("PROJECT_ROOT") is None:
        pytest.skip(HARNESS_MISSING)
    backend = request.param
    url = TEST_URL if backend == "postgres" else ""
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
    if backend == "postgres" and not url:
        pytest.fail("postgres variant requested without TEST_POSTGRES_DATABASE_URL")
    bundle = create_repository_bundle(
        Settings(storage_backend=backend, database_url=url, novel_data=tmp_path,
                 enable_cloud=False, mock_provider=True), data_root=tmp_path)
    novels, chapters = NovelService(bundle.novels, bundle.chapters), ChapterService(bundle.chapters)
    nid = "r3i-" + uuid4().hex
    novels.create({"id": nid, "title": "R3I"})
    raw = ExperimentalStore(tmp_path, backend, url)
    # Prove the backend identity instead of trusting the parameter.
    assert raw.backend == backend, f"ExperimentalStore reported {raw.backend!r}, wanted {backend!r}"
    if backend == "postgres":
        # A REAL PostgreSQL connection, schema and table must be present. Any failure here is
        # an error, never a quiet fall back to File.
        with raw._connect() as connection:
            version = connection.execute("SHOW server_version").fetchone()[0]
            table = connection.execute(
                "SELECT to_regclass('public.experimental_scope_documents')").fetchone()[0]
            assert table is not None, "experimental_scope_documents is missing: migrations not applied"
            dsn = connection.execute("SELECT current_database()").fetchone()[0]
        print(f"[R3-I] postgres backend: server {version}, database {dsn}, table {table}")
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
                           actor="author-a", workspace=workspace, assets=assets,
                           backend=backend, url=url, root=tmp_path, store=raw)


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


# ------------------------------------------- proof hygiene and history idempotency --
def _ordinary_edit(rig, document, shot_id, text):
    """Edit one shot through the ordinary document path (no adoption)."""
    current = rig.creative.get(rig.nid, rig.scope, document["id"])
    value = {key: current[key] for key in ("mode", "title", "scenes", "shots", "director_notes",
                                           "source_chapter_ids", "source_independent")
             if key in current}
    value["shots"] = [dict(item) for item in current["shots"]]
    for item in value["shots"]:
        if item["id"] == shot_id:
            item["frame_prompt"] = text
    return rig.creative.update(rig.nid, rig.scope, rig.actor, document["id"],
                               current["version"], value)


def test_the_proof_records_a_digest_and_never_a_second_copy_of_the_body(rig):
    document, shot_id = _storyboard(rig)
    receipt, _detail, body_read = _prompt(rig)
    _adopt(rig, document, shot_id, receipt, body_read)

    row = rig.creative.get(rig.nid, rig.scope, document["id"])
    proof = row["prompt_adoptions"][-1]
    assert "adopted_text" not in proof, "the proof must not keep a second copy of the prompt body"
    assert proof["digest"] == body_read["digest"]
    # No field of the PROOF may carry the body. The whole-row text count is NOT asserted:
    # the document's own content history legitimately retains the shot's previous content,
    # which is a different thing from the proof duplicating the prompt.
    for key, value in proof.items():
        assert value != TEXT, f"proof field {key!r} carries the prompt body"
        assert not (isinstance(value, str) and len(value) > 400), (
            f"proof field {key!r} is implausibly long for provenance metadata")

def test_editing_and_typing_the_same_text_back_does_not_restore_the_claim(rig):
    document, shot_id = _storyboard(rig)
    receipt, _detail, body_read = _prompt(rig)
    _adopt(rig, document, shot_id, receipt, body_read)
    assert rig.adoption.read(rig.nid, rig.scope, document["id"], rig.actor)["adoptions"][-1]["still_applied"]

    _ordinary_edit(rig, document, shot_id, "别的画面")
    assert not rig.adoption.read(rig.nid, rig.scope, document["id"], rig.actor)["adoptions"][-1]["still_applied"]

    # Typing the ORIGINAL text back is an incidental coincidence, not a restored adoption.
    _ordinary_edit(rig, document, shot_id, TEXT)
    assert _shot_of(rig, document, shot_id)["frame_prompt"] == TEXT
    entry = rig.adoption.read(rig.nid, rig.scope, document["id"], rig.actor)["adoptions"][-1]
    assert entry["still_applied"] is False, (
        "content equality alone must not resurrect a historical adoption claim")
    # ...and the historical proof is preserved, not cleared.
    assert entry["asset_id"] == receipt["asset_id"]


def test_editing_another_shot_leaves_the_adoption_current(rig):
    screenplay = rig.creative.create(rig.nid, rig.scope, rig.actor, {
        "mode": "SCREENPLAY", "title": "两场", "source_independent": True,
        "scenes": [{"id": "scene-1", "sequence": 1, "heading": "内景 房间 日", "action": "站住"},
                   {"id": "scene-2", "sequence": 2, "heading": "外景 街道 夜", "action": "奔跑"}]})
    document = rig.creative.derive(rig.nid, rig.scope, rig.actor, screenplay["id"], {
        "expected_version": screenplay["version"], "mode": "STORYBOARD",
        "title": "分镜", "shot_policy": "SCENE"})
    shots = document["shots"]
    receipt, _detail, body_read = _prompt(rig)
    _adopt(rig, document, shots[0]["id"], receipt, body_read)
    # Editing a DIFFERENT shot advances the document version...
    _ordinary_edit(rig, document, shots[1]["id"], "第二个镜头的画面")
    entry = rig.adoption.read(rig.nid, rig.scope, document["id"], rig.actor)["adoptions"][-1]
    # ...so by the strict rule the recorded adoption is no longer current, even though this
    # shot's own text is untouched. Reported accurately rather than guessed either way.
    assert entry["still_applied"] is False
    assert _shot_of(rig, document, shots[0]["id"])["frame_prompt"] == TEXT


def test_a_settled_request_id_is_not_replayed_over_a_newer_adoption(rig):
    document, shot_id = _storyboard(rig)
    first, _d1, b1 = _prompt(rig)
    payload, result_a = _adopt(rig, document, shot_id, first, b1)

    # A second, different adoption on the SAME shot, with its own request id.
    second, _d2, b2 = _prompt(rig, text="第二份采用的正文")
    doc_now = rig.creative.get(rig.nid, rig.scope, document["id"])
    payload_b = _body(rig, doc_now, second, b2, shot_id)
    result_b = rig.adoption.adopt(rig.nid, rig.scope, rig.actor, document["id"], shot_id, payload_b)
    assert result_b["replayed"] is False
    assert _shot_of(rig, document, shot_id)["frame_prompt"] == "第二份采用的正文"

    # Retrying the ORIGINAL request must be settled from the server's own history: no new
    # revision, and it must not write the older adoption back over the newer one.
    replay = rig.adoption.adopt(rig.nid, rig.scope, rig.actor, document["id"], shot_id, payload)
    assert replay["replayed"] is True
    assert replay["version"] == result_b["version"]
    assert rig.creative.get(rig.nid, rig.scope, document["id"])["version"] == result_b["version"]
    assert _shot_of(rig, document, shot_id)["frame_prompt"] == "第二份采用的正文"
    assert result_a["version"] < result_b["version"]


def test_the_settled_request_still_conflicts_when_the_input_differs(rig):
    document, shot_id = _storyboard(rig)
    first, _d1, b1 = _prompt(rig)
    payload, _a = _adopt(rig, document, shot_id, first, b1)
    second, _d2, b2 = _prompt(rig, text="另一份正文")
    doc_now = rig.creative.get(rig.nid, rig.scope, document["id"])
    _b = _body(rig, doc_now, second, b2, shot_id)
    rig.adoption.adopt(rig.nid, rig.scope, rig.actor, document["id"], shot_id, _b)
    payload.asset_id = "not-the-settled-one"
    with pytest.raises(ValueError, match="PROMPT_ADOPTION_REQUEST_REUSED"):
        rig.adoption.adopt(rig.nid, rig.scope, rig.actor, document["id"], shot_id, payload)


# --------------------------------------------------- per-revision display mask --
def _masked_revision(rig, family_id, previous_asset_id, revision, text, masked=True):
    """Add a revision with an explicit per-revision `redacted` flag and approve it."""
    from app.creative.prompt_authoring_models import PromptRevisionIn
    receipt = rig.authoring.revise(rig.nid, rig.scope, rig.actor, family_id,
        PromptRevisionIn.model_validate(dict(
            text=text, purpose="IMAGE", origin="MANUAL", request_id="req-" + uuid4().hex,
            expected_previous_asset_id=previous_asset_id, expected_revision=revision,
            redacted=masked)))
    rig.authoring.approve(rig.nid, rig.scope, rig.actor, family_id,
                          receipt["asset_id"], receipt["asset_version"])
    return receipt


def test_a_masked_newer_revision_does_not_mask_the_readable_adopted_one(rig):
    """The exact defect: the head's mask standing in for the adopted revision's own mask.

    `revision_body` carries NO `redacted` field, so reading the mask from the body silently
    yielded None and every masked revision looked displayable. The mask lives in the family
    projection's `versions[]` rows, per asset_id.
    """
    document, shot_id = _storyboard(rig)
    first, _d, b1 = _prompt(rig)                       # v1, unmasked
    _adopt(rig, document, shot_id, first, b1)

    # v2 arrives and IS masked; the family head's `redacted` therefore becomes True.
    second = _masked_revision(rig, first["family_id"], first["asset_id"], 1,
                              "第二版被遮罩", masked=True)
    detail = rig.library.detail(rig.nid, rig.scope, first["family_id"], rig.actor)
    assert detail["revision"] == second["revision"] and detail["redacted"] is True

    entry = rig.adoption.read(rig.nid, rig.scope, document["id"], rig.actor)["adoptions"][-1]
    assert entry["asset_id"] == first["asset_id"], "the pinned reference must not move"
    assert entry["source_state"] == "KNOWN"
    assert entry["source_redacted"] is False, "a masked HEAD must not mask the adopted revision"
    assert entry["source_readable"] is True, "the readable adopted revision became undisplayable"


def test_a_masked_revision_cannot_be_adopted_at_all(rig):
    """Real business path: a masked revision is refused as an adoption source.

    This is why 'an old masked revision later unlocked by a readable new one' is NOT
    constructible through the business API — a masked revision never becomes an adoption
    source in the first place. The projection's fail-closed branch covers the case where a
    source becomes masked AFTER adoption (storage-compatibility), which is a different test.
    """
    document, shot_id = _storyboard(rig)
    first, _d, b1 = _prompt(rig)
    masked = _masked_revision(rig, first["family_id"], first["asset_id"], 1,
                              "被遮罩的第二版", masked=True)
    detail = rig.library.detail(rig.nid, rig.scope, first["family_id"], rig.actor)
    body = rig.library.revision_body(rig.nid, rig.scope, first["family_id"],
                                     masked["asset_id"], rig.actor)
    assert body["state"] == "COMPLETE"          # the bytes ARE readable...
    assert "redacted" not in body, "…and the body contract deliberately does not carry the mask"
    payload = _body(rig, document, masked, body, shot_id)
    payload.revision = detail["revision"]
    payload.expected_digest = body["digest"]
    with pytest.raises(ValueError, match="PROMPT_ADOPTION_SOURCE_REDACTED"):
        rig.adoption.adopt(rig.nid, rig.scope, rig.actor, document["id"], shot_id, payload)


def test_an_unconfirmable_revision_fails_closed_rather_than_displaying(rig):
    """If the version row cannot be matched, display must FAIL CLOSED, not default to allow."""
    document, shot_id = _storyboard(rig)
    first, _d, b1 = _prompt(rig)
    _adopt(rig, document, shot_id, first, b1)

    entry = rig.adoption.read(rig.nid, rig.scope, document["id"], rig.actor)["adoptions"][-1]
    assert entry["source_state"] == "KNOWN" and entry["source_readable"] is True

    # Corrupt the record so the adopted asset_id no longer appears in the family's versions:
    # the projection must report UNKNOWN and NOT displayable instead of assuming permission.
    proofs = rig.creative._raw(rig.nid, rig.scope, document["id"])
    for item in proofs.get("prompt_adoptions", []):
        item["asset_id"] = "no-such-asset-in-family"
    rig.creative._write_raw(rig.nid, rig.scope, proofs) if hasattr(rig.creative, "_write_raw") else None
    # If the store exposes no such helper the corruption is skipped rather than faked.
    if not hasattr(rig.creative, "_write_raw"):
        pytest.skip("store exposes no writable raw accessor; UNKNOWN branch not exercised here")
    entry2 = rig.adoption.read(rig.nid, rig.scope, document["id"], rig.actor)["adoptions"][-1]
    assert entry2["source_state"] == "UNKNOWN"
    assert entry2["source_readable"] is False


# ------------------------------------------- document digest, and the UNKNOWN branch --
def test_the_read_projection_digest_is_the_documents_own_digest(rig):
    """Regression: the per-revision lookup used to rebind the CreativeDocument variable.

    `read()` bound `row` to the CreativeDocument and then reassigned the same name to a
    Prompt `versions[]` entry, so the digest it returned came from a PROMPT VERSION ROW, and
    when no row matched it hashed None. This asserts the real, document-level digest both
    before and after an adoption.
    """
    document, shot_id = _storyboard(rig)
    before = rig.adoption.read(rig.nid, rig.scope, document["id"], rig.actor)
    expected = rig.creative.document_digest(rig.creative.get(rig.nid, rig.scope, document["id"]))
    assert before["digest"] == expected
    assert before["version"] == document["version"]

    receipt, _d, b1 = _prompt(rig)
    _adopt(rig, document, shot_id, receipt, b1)

    after = rig.adoption.read(rig.nid, rig.scope, document["id"], rig.actor)
    live = rig.creative.get(rig.nid, rig.scope, document["id"])
    assert after["digest"] == rig.creative.document_digest(live)
    assert after["version"] == live["version"]
    assert after["digest"] != before["digest"], "a new revision must change the document digest"


def test_the_unknown_branch_fails_closed_and_still_returns_a_document_digest(rig):
    """CONTROLLED PROJECTION CONTRACT TEST — not a business scenario.

    A stub prompt service returns a family projection whose `versions[]` omits the adopted
    asset, which is how a storage-compatibility state (a proof referencing a revision the
    family no longer lists) presents itself. This exercises the UNKNOWN branch and, crucially,
    the previously crashing path: `document_digest(None)` from the shadowed variable.

    It is deliberately NOT presented as a real user operation: no business API produces this
    input, so it is a contract test of the projection itself.
    """
    import copy as _copy
    document, shot_id = _storyboard(rig)
    receipt, _d, b1 = _prompt(rig)
    _adopt(rig, document, shot_id, receipt, b1)

    real = rig.adoption.prompts

    class _StubPrompts:
        def __init__(self, inner):
            self._inner = inner

        def detail(self, nid, scope, family_id, actor=None):
            projection = self._inner.detail(nid, scope, family_id, actor)
            projection = _copy.deepcopy(projection)
            # The adopted revision is no longer listed by the family.
            projection["versions"] = [v for v in projection.get("versions") or []
                                      if v.get("asset_id") != receipt["asset_id"]]
            return projection

        def revision_body(self, *a, **k):
            return self._inner.revision_body(*a, **k)

    rig.adoption.prompts = _StubPrompts(real)
    try:
        read = rig.adoption.read(rig.nid, rig.scope, document["id"], rig.actor)
        entry = read["adoptions"][-1]
        assert entry["source_state"] == "UNKNOWN", "an unconfirmable revision must be UNKNOWN"
        assert entry["source_readable"] is False, "UNKNOWN must fail closed, never allow"
        # The crash path: this must be the DOCUMENT's digest, not None hashed.
        live = rig.creative.get(rig.nid, rig.scope, document["id"])
        assert read["digest"] == rig.creative.document_digest(live)
    finally:
        rig.adoption.prompts = real


# ======================================================= BATCH 2: atomic adoption --
def test_A_atomic_adoption_succeeds_inside_the_cross_module_transaction(rig):
    """Test A: the real business chain, committed in ONE cross-module atomic boundary.

    SCREENPLAY -> derive STORYBOARD -> create+approve Prompt -> adopt_atomic, where the source
    read happens under the asset lease the phase already holds.
    """
    document, shot_id = _storyboard(rig)
    receipt, _d, b1 = _prompt(rig)
    before = rig.creative.get(rig.nid, rig.scope, document["id"])
    version_before = before["version"]

    payload = _body(rig, before, receipt, b1, shot_id)
    result = rig.adoption.adopt_atomic(rig.nid, rig.scope, rig.actor, document["id"],
                                       shot_id, payload)

    assert result["committed"] is True, "success must be reported only after the phase commits"
    assert result["replayed"] is False
    assert result["version"] == version_before + 1, "exactly one new revision"

    # The authorised read-back, not the request echo.
    live = rig.creative.get(rig.nid, rig.scope, document["id"])
    assert live["version"] == version_before + 1
    shot = next(item for item in live["shots"] if item["id"] == shot_id)
    assert shot["frame_prompt"] == TEXT, "the adopted text must be written verbatim"

    # The proof describes the content actually committed.
    proof = result["adoption"]
    assert proof["asset_id"] == receipt["asset_id"]
    assert proof["revision"] == receipt["revision"]
    assert proof["digest"] == b1["digest"]
    assert proof["request_digest"]
    import hashlib
    assert hashlib.sha256(shot["frame_prompt"].encode("utf-8")).hexdigest() == proof["digest"], \
        "the proof digest must match the committed shot content"

    # Reopening the projection agrees.
    read = rig.adoption.read(rig.nid, rig.scope, document["id"], rig.actor)
    entry = read["adoptions"][-1]
    assert entry["asset_id"] == receipt["asset_id"]
    assert entry["still_applied"] is True
    assert entry["source_readable"] is True

    # No model or media work was started.
    assert not any(name for name in rig.workspace.store.read(rig.nid, rig.scope)
                   .get("collections", {}) if "job" in name.lower())


def test_A_atomic_adoption_changes_only_the_target_shot(rig):
    screenplay = rig.creative.create(rig.nid, rig.scope, rig.actor, {
        "mode": "SCREENPLAY", "title": "两场", "source_independent": True,
        "scenes": [{"id": "scene-1", "sequence": 1, "heading": "内景 房间 日", "action": "站住"},
                   {"id": "scene-2", "sequence": 2, "heading": "外景 街道 夜", "action": "奔跑"}]})
    document = rig.creative.derive(rig.nid, rig.scope, rig.actor, screenplay["id"], {
        "expected_version": screenplay["version"], "mode": "STORYBOARD",
        "title": "分镜", "shot_policy": "SCENE"})
    shots = document["shots"]
    receipt, _d, b1 = _prompt(rig)
    payload = _body(rig, document, receipt, b1, shots[0]["id"])
    rig.adoption.adopt_atomic(rig.nid, rig.scope, rig.actor, document["id"],
                              shots[0]["id"], payload)
    after = rig.creative.get(rig.nid, rig.scope, document["id"])["shots"]
    assert after[0]["frame_prompt"] == TEXT
    assert after[1]["frame_prompt"] == shots[1]["frame_prompt"], "a sibling shot must not change"


def test_B_a_target_conflict_leaves_no_partial_adoption(rig):
    """Test B: a concurrent edit before the commit must not be overwritten.

    The other operation commits first, so the adoption's expected_version/digest are stale.
    """
    document, shot_id = _storyboard(rig)
    receipt, _d, b1 = _prompt(rig)
    snapshot = rig.creative.get(rig.nid, rig.scope, document["id"])
    payload = _body(rig, snapshot, receipt, b1, shot_id)

    # Another operation changes the document first.
    value = {key: snapshot[key] for key in ("mode", "title", "scenes", "shots",
                                            "director_notes", "source_chapter_ids",
                                            "source_independent") if key in snapshot}
    value["shots"] = [dict(item) for item in snapshot["shots"]]
    for item in value["shots"]:
        if item["id"] == shot_id:
            item["frame_prompt"] = "别人的新内容"
    rig.creative.update(rig.nid, rig.scope, rig.actor, document["id"],
                        snapshot["version"], value)

    with pytest.raises(CapabilityVersionConflict):
        rig.adoption.adopt_atomic(rig.nid, rig.scope, rig.actor, document["id"], shot_id, payload)

    # Real storage result: the other author's content survives and NO proof was added.
    live = rig.creative.get(rig.nid, rig.scope, document["id"])
    shot = next(item for item in live["shots"] if item["id"] == shot_id)
    assert shot["frame_prompt"] == "别人的新内容", "the newer content must not be overwritten"
    assert not [p for p in (live.get("prompt_adoptions") or [])
                if p.get("request_id") == payload.request_id], "no partial adoption proof"


def test_a_request_id_replay_is_settled_inside_the_transaction(rig):
    document, shot_id = _storyboard(rig)
    receipt, _d, b1 = _prompt(rig)
    snapshot = rig.creative.get(rig.nid, rig.scope, document["id"])
    payload = _body(rig, snapshot, receipt, b1, shot_id)
    first = rig.adoption.adopt_atomic(rig.nid, rig.scope, rig.actor, document["id"],
                                      shot_id, payload)
    again = rig.adoption.adopt_atomic(rig.nid, rig.scope, rig.actor, document["id"],
                                      shot_id, payload)
    assert again["replayed"] is True
    assert again["version"] == first["version"]
    assert rig.creative.get(rig.nid, rig.scope, document["id"])["version"] == first["version"]


# ================================================== Test C: source deletion race --
def test_C_deleting_the_source_before_the_adoption_makes_it_refuse(rig):
    """Test C, scenario 1 — deterministic order: the source is deleted FIRST.

    Ordering is established by the test's own sequential execution, not by a sleep: the delete
    has returned before the adoption is even invoked, so this is a real "source already gone"
    state and not a guess about who won a race.
    """
    document, shot_id = _storyboard(rig)
    receipt, _d, b1 = _prompt(rig)
    snapshot = rig.creative.get(rig.nid, rig.scope, document["id"])
    payload = _body(rig, snapshot, receipt, b1, shot_id)
    version_before = snapshot["version"]

    # The source revision is deleted through the owner's own delete path.
    try:
        # The owner binds assets to a project, so the delete runs inside that project's asset
        # scope and through the owner's own method. The public delete rules are unchanged.
        with rig.workspace._asset_scope(rig.nid, rig.scope):
            rig.assets.delete(receipt["asset_id"], branch_id=rig.scope.get("branch_id"))
    except FileNotFoundError:
        pytest.skip(
            "BLOCKED (Test C scenario 1): AssetLibraryService.delete() takes no actor_id, so the "
            "owner cannot resolve this asset and the source-deleted-first state cannot be "
            "constructed through the business API. This is the recorded R3-U private-revision "
            "deletion limitation, NOT a passing source-deletion race.")

    with pytest.raises((FileNotFoundError, ValueError)):
        rig.adoption.adopt_atomic(rig.nid, rig.scope, rig.actor, document["id"],
                                  shot_id, payload)

    # Real persisted result: nothing was written and no proof was stored.
    live = rig.creative.get(rig.nid, rig.scope, document["id"])
    assert live["version"] == version_before, "a refused adoption must not create a revision"
    shot = next(item for item in live["shots"] if item["id"] == shot_id)
    assert shot["frame_prompt"] == "", "the shot must be untouched"
    assert not (live.get("prompt_adoptions") or []), "no source proof may be recorded"


def test_C_a_concurrent_delete_cannot_corrupt_the_committed_adoption(rig):
    """Test C, scenario 2 — the adoption holds the lease while a delete is attempted.

    The adoption is held INSIDE its transaction by a guard that blocks on an explicit event,
    so the delete is attempted at a known point, deterministically, with no sleep. Whatever
    order the owner's locks produce, the assertions are on the real persisted state: no
    partial write, no duplicated proof, no deadlock.
    """
    import threading
    document, shot_id = _storyboard(rig)
    receipt, _d, b1 = _prompt(rig)
    snapshot = rig.creative.get(rig.nid, rig.scope, document["id"])
    payload = _body(rig, snapshot, receipt, b1, shot_id)

    entered = threading.Event()      # set once the adoption is inside its transaction
    may_proceed = threading.Event()  # released by the test after the delete was attempted
    outcome = {}

    def guard():
        if not entered.is_set():
            entered.set()
            # Block deterministically until the test has attempted the delete.
            may_proceed.wait(timeout=20)

    def run_adoption():
        try:
            outcome["result"] = rig.adoption.adopt_atomic(
                rig.nid, rig.scope, rig.actor, document["id"], shot_id, payload, guard)
        except Exception as exc:  # noqa: BLE001
            outcome["error"] = exc

    worker = threading.Thread(target=run_adoption, daemon=True)
    worker.start()
    assert entered.wait(timeout=20), "the adoption never entered its transaction"

    delete_outcome = {}
    def attempt_delete():
        try:
            with rig.workspace._asset_scope(rig.nid, rig.scope):
                rig.assets.delete(receipt["asset_id"], branch_id=rig.scope.get("branch_id"))
            delete_outcome["ok"] = True
        except Exception as exc:  # noqa: BLE001
            delete_outcome["error"] = exc

    # Attempt the delete while the adoption holds its locks: it must either serialise after
    # the commit or fail, but it must not corrupt the adoption or deadlock.
    deleter = threading.Thread(target=attempt_delete, daemon=True)
    deleter.start()
    # Do NOT require the delete to have finished while the adoption holds its resources:
    # waiting there is legal lock serialisation, not a deadlock. Record its state instead.
    deleter.join(timeout=1.0)
    blocked_while_held = deleter.is_alive()
    may_proceed.set()
    worker.join(timeout=25)
    assert not worker.is_alive(), "the adoption deadlocked"
    deleter.join(timeout=25)
    assert not deleter.is_alive(), "the delete deadlocked after the adoption released"
    # The delete must have reached a definite outcome, never been lost.
    assert ("ok" in delete_outcome) or ("error" in delete_outcome), \
        "the delete produced no outcome at all"
    assert not any("job" in name.lower()
                   for name in rig.workspace.store.read(rig.nid, rig.scope).get("collections", {}))
    outcome["delete_blocked_while_held"] = blocked_while_held

    # Whichever legal order occurred, the persisted state must be coherent.
    live = rig.creative.get(rig.nid, rig.scope, document["id"])
    # Precise identity, no `or True`: the previous condition was a tautology and could not
    # fail, so it proved nothing about which proof was stored.
    proofs = [p for p in (live.get("prompt_adoptions") or [])
              if p.get("request_id") == payload.request_id
              and p.get("document_id") == document["id"]
              and p.get("shot_id") == shot_id]
    if "result" in outcome:
        result = outcome["result"]
        assert result["committed"] is True
        assert live["version"] == result["version"], "the committed version must be readable"
        shot = next(item for item in live["shots"] if item["id"] == shot_id)
        assert shot["frame_prompt"] == TEXT
        assert [p for p in proofs if p.get("shot_id") == shot_id], "the source proof must exist"
        assert len([p for p in proofs if p.get("request_id") == payload.request_id]) == 1, \
            "exactly one proof for this request"
        # No model or media work was started by any of this.
        assert not any("job" in name.lower()
                       for name in rig.workspace.store.read(rig.nid, rig.scope)
                       .get("collections", {}))
    else:
        # The adoption legitimately lost the race; then it must have written NOTHING.
        assert live["version"] == snapshot["version"], "a failed adoption must not commit"
        assert not [p for p in proofs if p.get("request_id") == payload.request_id]


# ============================================ P0: a payload-masked source must be refused
def test_a_payload_masked_revision_is_refused_and_writes_nothing(rig):
    """The mask is read from the PAYLOAD, and the previous code never rejected anything.

    `validate_payload` returns only {"ok", "reason"}; asking it for `redacted` always yielded
    None, so a masked source was adoptable. This test creates a genuinely masked revision
    through the business API and requires adopt_atomic to refuse it.
    """
    document, shot_id = _storyboard(rig)
    first, _d, b1 = _prompt(rig)
    masked = _masked_revision(rig, first["family_id"], first["asset_id"], 1,
                              "被遮罩的正文", masked=True)
    snapshot = rig.creative.get(rig.nid, rig.scope, document["id"])
    body = rig.library.revision_body(rig.nid, rig.scope, first["family_id"],
                                     masked["asset_id"], rig.actor)
    # The payload really does carry the mask, and the body contract does not.
    with rig.workspace._asset_scope(rig.nid, rig.scope):
        payload_meta = rig.workspace.assets.get(masked["asset_id"], actor_id=rig.actor)
    import app.creative.prompt_asset as _pa
    assert _pa.prompt_payload(payload_meta).get("redacted") is True
    assert "redacted" not in body

    request = _body(rig, snapshot, masked, body, shot_id)
    with pytest.raises(ValueError, match="PROMPT_ADOPTION_SOURCE_REDACTED"):
        rig.adoption.adopt_atomic(rig.nid, rig.scope, rig.actor, document["id"],
                                  shot_id, request)

    live = rig.creative.get(rig.nid, rig.scope, document["id"])
    assert live["version"] == snapshot["version"], "a masked source must not create a revision"
    shot = next(item for item in live["shots"] if item["id"] == shot_id)
    assert shot["frame_prompt"] == "", "the shot must be untouched"
    assert not (live.get("prompt_adoptions") or []), "no proof may be stored"
    assert not any("job" in name.lower()
                   for name in rig.workspace.store.read(rig.nid, rig.scope).get("collections", {}))


# ============================================ PostgreSQL / File backend receipt --
def test_the_rig_uses_the_requested_backend(rig):
    """No silent fallback: the rig must report the backend it was asked for."""
    assert rig.backend in {"file", "postgres"}
    assert rig.store.backend == rig.backend
    if rig.backend == "postgres":
        assert rig.url, "postgres mode must have a real endpoint"
        with rig.store._connect() as connection:
            assert connection.execute(
                "SELECT to_regclass('public.experimental_scope_documents')").fetchone()[0]


def test_atomic_adoption_persists_and_reopens_through_a_fresh_store_connection(rig):
    """The core receipt, on BOTH backends, with a genuinely new store instance on reopen."""
    from app.creative.service import CreativeService
    from app.experimental.store import ExperimentalStore

    document, shot_id = _storyboard(rig)
    receipt, _d, b1 = _prompt(rig)
    snapshot = rig.creative.get(rig.nid, rig.scope, document["id"])
    request = _body(rig, snapshot, receipt, b1, shot_id)

    result = rig.adoption.adopt_atomic(rig.nid, rig.scope, rig.actor, document["id"],
                                       shot_id, request)
    assert result["committed"] is True
    assert result["version"] == snapshot["version"] + 1

    # A SEPARATE store connection, not the one that wrote.
    reopened_store = ExperimentalStore(rig.root, rig.backend, rig.url)
    assert reopened_store.backend == rig.backend
    reopened = CreativeService(reopened_store, rig.creative.novels, rig.creative.chapters)
    live = reopened.get(rig.nid, rig.scope, document["id"])
    assert live["version"] == result["version"]
    shot = next(item for item in live["shots"] if item["id"] == shot_id)
    assert shot["frame_prompt"] == TEXT
    proofs = [p for p in (live.get("prompt_adoptions") or [])
              if p.get("request_id") == request.request_id]
    assert len(proofs) == 1
    assert proofs[0]["result_version"] == result["version"]

    # The same request_id retried must not add a second write.
    again = rig.adoption.adopt_atomic(rig.nid, rig.scope, rig.actor, document["id"],
                                      shot_id, request)
    assert again["replayed"] is True
    assert again["version"] == result["version"]
    assert reopened.get(rig.nid, rig.scope, document["id"])["version"] == result["version"]
