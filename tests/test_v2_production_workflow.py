"""Phase7 unified production workflow projection over real original owners.

Run with ``scripts/run_v2_checks.py`` and an owned ``--basetemp`` under
``.runtime``. PostgreSQL cases require a real dedicated
``TEST_POSTGRES_DATABASE_URL`` and are skipped otherwise; no Session
replacement, model download or fabricated media result is used.
"""
from __future__ import annotations

import base64
import os
from pathlib import Path
import struct
from types import SimpleNamespace
from uuid import uuid4
import zlib

import pytest

TEST_URL = os.getenv("TEST_POSTGRES_DATABASE_URL", "")
FLAGS = "narrative_production_v2,asset_lineage_v2"
MODULE_ORDER = ("director", "storyboard", "image", "video", "audio", "timeline", "asset")


def png_bytes(color=b"\x11\x22\x33"):
    """A complete CRC-correct 2 x 2 RGB PNG, decoded by the real validator."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress((b"\x00" + color * 2) * 2))
            + chunk(b"IEND", b""))


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


@pytest.fixture(params=[
    pytest.param("file", marks=pytest.mark.file_backend_only),
    pytest.param("postgres", marks=pytest.mark.postgres_backend_only),
])
def rig(request, tmp_path, monkeypatch):
    from app.config import Settings
    from app.repositories.factory import create_repository_bundle
    from app.services import NovelService, ChapterService
    root = Path(__file__).resolve().parents[1]
    assert Path(os.environ["PROJECT_ROOT"]).resolve() == root
    for key in ("LOCALAPPDATA", "NOVEL_DATA_PATH"):
        assert Path(os.environ[key]).resolve().is_relative_to(root / ".runtime")
    assert tmp_path.resolve().is_relative_to(root / ".runtime")
    backend = request.param
    url = TEST_URL if backend == "postgres" else ""
    if backend == "postgres" and not url:
        pytest.fail("Phase7 PostgreSQL cases require a real TEST_POSTGRES_DATABASE_URL")
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", FLAGS)
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    bundle = create_repository_bundle(
        Settings(storage_backend=backend, database_url=url, novel_data=tmp_path,
                 enable_cloud=False, mock_provider=True), data_root=tmp_path)
    novels, chapters = NovelService(bundle.novels, bundle.chapters), ChapterService(bundle.chapters)
    nid = "phase7-workflow-" + uuid4().hex
    novels.create({"id": nid, "title": "Phase7 unified production workflow"})
    workspace = services(tmp_path, backend, url, novels, chapters)
    from app.creative.production_workflow import ProductionWorkflowService
    workflow = ProductionWorkflowService(workspace, workspace.creative)
    yield SimpleNamespace(nid=nid, scope={"mode": "local", "novel_id": nid}, actor="phase7-author",
                          workflow=workflow, workspace=workspace, novels=novels, chapters=chapters,
                          backend=backend, bundle=bundle)
    if backend == "postgres":
        try:
            workspace.store._connect().close()
        except Exception:  # pragma: no cover - cleanup must not mask the result
            pass


def _import_image(rig, name="external.png"):
    payload = base64.b64encode(png_bytes()).decode("ascii")
    return rig.workspace.import_asset(rig.nid, rig.scope, rig.actor, {
        "filename": name, "kind": "image", "content_base64": payload,
        "idempotency_key": "phase7-" + uuid4().hex})


# ------------------------------------------------------------------ reads --
def test_projection_is_advisory_and_lists_the_seven_modules(rig):
    view = rig.workflow.projection(rig.nid, rig.scope)
    assert view["schema_version"] == 1 and view["contract"] == "studio-production-workflow/1"
    assert view["project_id"] == rig.nid
    assert view["advisory_only"] is True and view["execution_authority"] is False
    assert view["scope"]["mode"] == "local" and view["scope"]["novel_id"] == rig.nid
    assert [row["id"] for row in view["modules"]] == list(MODULE_ORDER)
    for row in view["modules"]:
        assert row["status"] == "NOT_STARTED"
        assert row["document_count"] == 0 and row["asset_count"] == 0 and row["job_count"] == 0
        assert row["blocked_reasons"] == [] and row["owner"]
    assert view["project_start"]["state"] == "NOT_STARTED"
    assert view["project_start"]["has_creative_documents"] is False
    assert view["project_start"]["start_action"]["path"] == "/api/experimental/projects"
    assert view["project_start"]["start_action"]["requires_original_host_session"] is True
    assert view["asset_overview"] == {"total": 0, "by_kind": {"image": 0, "audio": 0, "video": 0, "text": 0, "other": 0},
                                      "private_pending_review": 0, "reviewed": 0}
    assert view["dashboard"] == {"stages_total": 7, "stages_started": 0, "stages_reviewed": 0,
                                 "open_reviews": 0, "blocked_stages": []}
    assert view["creative_intent"]["version"] == 0
    assert view["creative_intent"]["preset"] == "BLANK"
    assert [entry["intent_id"] for entry in view["creative_intent"]["values"]] == [
        "novel_writing", "novel_adaptation", "ai_short_film", "commercial_cg", "advertisement",
        "music_video", "game_previs", "image_design", "podcast_voice", "blank", "custom"]
    assert all(entry["selected"] is False for entry in view["creative_intent"]["values"])


def test_projection_neutral_activation_is_reported_without_claiming_start(rig):
    assert rig.workflow.projection(rig.nid, rig.scope)["project_start"]["state"] == "NOT_STARTED"
    rig.workspace.activate(rig.nid, rig.scope, rig.actor)
    start = rig.workflow.projection(rig.nid, rig.scope)["project_start"]
    assert start["state"] == "STARTED" and start["entry_kind"] == "NEUTRAL_STUDIO"
    assert start["incarnation"]


# --------------------------------------------------------------- mutation --
def test_intent_update_reuses_the_versioned_preference_row(rig):
    first = rig.workflow.update_intent(rig.nid, rig.scope, rig.actor, {
        "expected_version": None,
        "values": [{"intent_id": "ai_short_film", "label": "短片", "selected": True},
                   {"intent_id": "custom", "label": "自编舞台剧", "selected": True}],
        "preset": "video"})
    assert first["version"] == 1 and first["editable"] is True and first["history_retained"] is True
    selected = {entry["intent_id"] for entry in first["values"] if entry["selected"]}
    assert selected == {"ai_short_film", "custom"}
    assert next(entry["label"] for entry in first["values"] if entry["intent_id"] == "custom") == "自编舞台剧"
    assert first["preset"] == "VIDEO"

    # The saved row is the original owner's, not a second store.
    from app.creative.workspace import PREFERENCES
    document = rig.workspace.store.read(rig.nid, rig.scope)
    rows = list(document["collections"][PREFERENCES].values())
    assert len(rows) == 1 and rows[0]["version"] == 1

    second = rig.workflow.update_intent(rig.nid, rig.scope, rig.actor, {
        "expected_version": 1, "values": [{"intent_id": "blank", "label": "空白创作", "selected": True}],
        "preset": None})
    assert second["version"] == 2 and second["preset"] == "VIDEO"
    assert {entry["intent_id"] for entry in second["values"] if entry["selected"]} == {"blank"}
    rows = list(rig.workspace.store.read(rig.nid, rig.scope)["collections"][PREFERENCES].values())
    assert len(rows[0]["history"]) == 1
    assert rig.workflow.projection(rig.nid, rig.scope)["creative_intent"]["version"] == 2


def test_intent_update_fails_closed_on_stale_or_unread_state(rig):
    from fastapi import HTTPException
    rig.workflow.update_intent(rig.nid, rig.scope, rig.actor, {
        "expected_version": None, "values": [], "preset": None})
    with pytest.raises(HTTPException) as unread:
        rig.workflow.update_intent(rig.nid, rig.scope, rig.actor, {
            "expected_version": None, "values": [], "preset": None})
    assert unread.value.status_code == 409
    assert unread.value.detail["code"] == "PRODUCTION_WORKFLOW_INTENT_CONFLICT"
    with pytest.raises(HTTPException) as stale:
        rig.workflow.update_intent(rig.nid, rig.scope, rig.actor, {
            "expected_version": 99, "values": [], "preset": None})
    assert stale.value.status_code == 409
    assert stale.value.detail["code"] == "PRODUCTION_WORKFLOW_INTENT_CONFLICT"
    # The conflict never partially wrote a second revision.
    assert rig.workflow.projection(rig.nid, rig.scope)["creative_intent"]["version"] == 1


def test_intent_update_rejects_values_outside_the_owner_vocabulary(rig):
    from fastapi import HTTPException
    for body in ({"expected_version": None, "values": [{"intent_id": "not_an_intent", "label": "x",
                                                        "selected": True}], "preset": None},
                 {"expected_version": None, "values": [{"intent_id": "blank", "label": "空白创作",
                                                        "selected": True}], "preset": "not_a_preset"}):
        with pytest.raises(HTTPException) as invalid:
            rig.workflow.update_intent(rig.nid, rig.scope, rig.actor, body)
        assert invalid.value.status_code == 422
        assert invalid.value.detail["code"] == "PRODUCTION_WORKFLOW_INTENT_INVALID"
    assert rig.workflow.projection(rig.nid, rig.scope)["creative_intent"]["version"] == 0


# ---------------------------------------------------------------- assets --
def test_real_image_asset_moves_only_the_image_module(rig):
    row = _import_image(rig)
    assert row["kind"] == "image" and row["version"] == 1
    view = rig.workflow.projection(rig.nid, rig.scope)
    modules = {entry["id"]: entry for entry in view["modules"]}
    assert modules["image"]["asset_count"] == 1 and modules["image"]["status"] == "IN_PRODUCTION"
    assert modules["image"]["job_count"] == 0
    # The asset module is the library aggregate, so it reports the same asset and
    # no other modality module may claim it.
    assert modules["asset"]["asset_count"] == 1 and modules["asset"]["status"] == "IN_PRODUCTION"
    for identifier in MODULE_ORDER:
        if identifier not in {"image", "asset"}:
            assert modules[identifier]["status"] == "NOT_STARTED", identifier
    assert view["asset_overview"]["total"] == 1
    assert view["asset_overview"]["by_kind"]["image"] == 1
    assert view["asset_overview"]["by_kind"]["video"] == 0
    # A manual upload carries no owner review marker, so it is neither pending
    # nor reviewed; the projection must not invent either.
    assert view["asset_overview"]["private_pending_review"] == 0
    assert view["asset_overview"]["reviewed"] == 0
    # image and the library aggregate are the two started stages.
    assert view["dashboard"]["stages_started"] == 2 and view["dashboard"]["open_reviews"] == 0
    assert view["dashboard"]["blocked_stages"] == []


def test_deleted_assets_leave_the_projection(rig):
    row = _import_image(rig)
    assert rig.workflow.projection(rig.nid, rig.scope)["asset_overview"]["total"] == 1
    rig.workspace.lifecycle(rig.nid, rig.scope, row["id"], row["version"])
    assert rig.workflow.projection(rig.nid, rig.scope)["asset_overview"]["total"] == 0
    modules = {entry["id"]: entry for entry in rig.workflow.projection(rig.nid, rig.scope)["modules"]}
    assert modules["image"]["status"] == "NOT_STARTED"


def test_projection_never_reads_asset_bytes_or_lineage(rig):
    """The aggregate index must stay metadata-only: no sha256, lineage or parameters."""
    row = _import_image(rig)
    index = rig.workspace.asset_index(rig.nid, rig.scope)
    assert len(index) == 1
    assert set(index[0]) == {"id", "kind", "version", "review_status", "source_job_id", "deleted", "created_at"}
    assert index[0]["id"] == row["id"]
