"""CONTENT_POLICY_FRAMEWORK: RESERVED — the reservation must never break today.

Covers the four required behaviours: a legacy row without the field reads STANDARD,
a new project defaults to STANDARD, an unknown policy is refused, and the asset /
export read paths do not fail when the field is absent. One extra case proves that
an unrelated preference edit cannot reset an already-saved policy through the real
original owner (File backend; the PostgreSQL variant runs under the project runner).

This suite is intentionally small: the reservation adds no product behaviour.
"""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.creative.content_policy import (DEFAULT_CONTENT_POLICY, STATUS, POLICIES, asset_policy_for,
                                         effective_content_policy, export_notice, model_content_policy_support)
from app.creative.workspace import PREFERENCES, IndependentWorkspaceService
from app.creative.workspace_models import WorkspacePreferences, WorkspacePreferencesUpdate

TEST_URL = os.getenv("TEST_POSTGRES_DATABASE_URL", "")
FLAGS = "narrative_production_v2,asset_lineage_v2"
# A preference row written before the reservation existed: no content_policy key.
LEGACY_ROW = {"id": "pref-legacy", "novel_id": "project-legacy", "scope": {"mode": "local", "novel_id": "project-legacy"},
              "version": 1, "history": [], "intents": ["BLANK"], "preset": "BLANK", "custom_intent": "",
              "created_by": "author", "updated_by": "author", "created_at": "2026-01-01T00:00:00+00:00",
              "updated_at": "2026-01-01T00:00:00+00:00"}


def test_reserved_vocabulary_and_marker():
    assert STATUS == "RESERVED"
    assert DEFAULT_CONTENT_POLICY == "STANDARD" and "STANDARD" in POLICIES


def test_a_new_project_defaults_to_standard():
    fresh = WorkspacePreferences()
    assert fresh.content_policy is None
    assert effective_content_policy(fresh.model_dump()) == "STANDARD"
    # A brand-new project's wire view is the frozen projection, still without the field.
    view = IndependentWorkspaceService._preference_view(None)
    assert view == {"version": 0, "intents": [], "preset": "BLANK", "custom_intent": ""}
    assert effective_content_policy(view) == "STANDARD"


def test_a_legacy_row_without_the_field_still_reads_as_standard():
    document = {"novel_id": "project-legacy", "scope": {"mode": "local", "novel_id": "project-legacy"},
                "collections": {PREFERENCES: {"pref-legacy": LEGACY_ROW}}}
    # The original read path validates the row exactly as the service does.
    row = IndependentWorkspaceService._preferences(document)
    assert row is LEGACY_ROW
    validated = WorkspacePreferences.model_validate({key: row.get(key) for key in WorkspacePreferences.model_fields})
    assert validated.content_policy is None
    assert effective_content_policy(row) == "STANDARD"
    # The wire projection stays byte-identical: no client can see a new key, and no
    # missing key can raise.
    assert IndependentWorkspaceService._preference_view(row) == {
        "version": 1, "intents": ["BLANK"], "preset": "BLANK", "custom_intent": ""}


def test_an_unknown_policy_is_refused():
    base = {"intents": [], "preset": "BLANK", "custom_intent": ""}
    for value in ("NSFW", "STANDARD " , "standard", "", "CUSTOM_POLICY"):
        with pytest.raises(Exception):
            WorkspacePreferences.model_validate({**base, "content_policy": value})
    with pytest.raises(Exception):
        WorkspacePreferencesUpdate.model_validate({**base, "expected_version": 0, "content_policy": "NSFW"})
    # The reserved vocabulary itself is accepted.
    assert WorkspacePreferences.model_validate({**base, "content_policy": "MATURE"}).content_policy == "MATURE"
    # A value that the typed owner could never store still degrades to the default.
    assert effective_content_policy({"content_policy": "NSFW"}) == "STANDARD"


def test_asset_and_export_reads_survive_a_missing_field():
    legacy = {key: value for key, value in LEGACY_ROW.items() if key != "content_policy"}
    effective = effective_content_policy(legacy)
    assert asset_policy_for(effective) == "STANDARD"
    assert asset_policy_for(legacy.get("content_policy")) == "STANDARD"
    notice = export_notice(legacy.get("content_policy"))
    assert notice == {"kind": "CONTENT_POLICY_NOTICE", "policy": "STANDARD",
                      "rendered": False, "blocking": False, "status": "RESERVED"}
    # A model entry that declares nothing is reported as STANDARD and is never filtered.
    assert model_content_policy_support({"capabilities": ["IMAGE_GENERATION"]}) == ("STANDARD",)
    assert model_content_policy_support(None) == ("STANDARD",)
    assert model_content_policy_support({"content_policy_support": ["NOT_A_POLICY"]}) == ("STANDARD",)
    assert model_content_policy_support({"content_policy_support": ["STANDARD", "MATURE"]}) == ("STANDARD", "MATURE")


def test_the_phase8_mapping_declaration_shape_is_accepted():
    """Phase8 fixed the mapping form; the earlier list form stays supported."""
    mapping = {"content_policy_support": {"STANDARD": True, "MATURE": False}}
    assert model_content_policy_support(mapping) == ("STANDARD",)
    assert model_content_policy_support({"content_policy_support": {"MATURE": True, "STANDARD": True}}) == ("STANDARD", "MATURE")
    assert model_content_policy_support({"content_policy_support": {"MATURE": True}}) == ("MATURE",)
    # A mapping with nothing explicitly true, an unknown-only mapping, junk and a
    # non-boolean truthy value all fall back to the default instead of guessing.
    assert model_content_policy_support({"content_policy_support": {"STANDARD": False}}) == ("STANDARD",)
    assert model_content_policy_support({"content_policy_support": {"NSFW": True}}) == ("STANDARD",)
    assert model_content_policy_support({"content_policy_support": {"STANDARD": 1}}) == ("STANDARD",)
    assert model_content_policy_support({"content_policy_support": {}}) == ("STANDARD",)
    assert model_content_policy_support({"content_policy_support": "STANDARD"}) == ("STANDARD",)
    # Legacy list form still works, and neither shape filters anything.
    assert model_content_policy_support({"content_policy_support": ["MATURE"]}) == ("MATURE",)


def test_no_owner_outside_the_reservation_reads_the_reserved_field():
    """Asset and export reads cannot fail on a missing policy: nothing else reads it.

    Bounded walk over `app/` — the field is declared in `workspace_models.py` and its
    "null means unchanged" write rule lives in `workspace.py`; every other module,
    including the asset library and the export job service, must be untouched by it.
    """
    root = Path(__file__).resolve().parents[1]
    allowed = {
        # The declaration and the "null means unchanged" write rule.
        "app/creative/content_policy.py", "app/creative/workspace_models.py", "app/creative/workspace.py",
        # Pre-existing and unrelated: interactive_story.py:701 carries the string
        # 'content_policy': 'RETAIN_AUTHOR_TEXT_AS_UNREVIEWED_DRAFT_...' as an
        # interactive-story retention rule. It is not this project-level field and it
        # predates the reservation; it is listed here so the guard stays exact.
        "app/experimental/interactive_story.py",
    }
    offenders = []
    for path in (root / "app").rglob("*.py"):
        relative = path.relative_to(root).as_posix()
        if relative in allowed:
            continue
        text = path.read_text(encoding="utf-8")
        for needle in ("content_policy", "asset_policy"):
            if needle in text:
                offenders.append(f"{relative}:{needle}")
    assert offenders == []
    # The reserved helpers therefore accept every shape a legacy reader can hand them.
    for absent in (None, {}, {"content_policy": None}, {"intents": [], "preset": "BLANK", "custom_intent": ""}):
        assert effective_content_policy(absent) == "STANDARD"
        assert asset_policy_for(None) == "STANDARD"
        assert export_notice(None)["blocking"] is False


@pytest.fixture(params=[
    pytest.param("file", marks=pytest.mark.file_backend_only),
    pytest.param("postgres", marks=pytest.mark.postgres_backend_only),
])
def rig(request, tmp_path, monkeypatch):
    from app.config import Settings
    from app.repositories.factory import create_repository_bundle
    from app.services import NovelService, ChapterService
    from app.creative.service import CreativeService
    from app.experimental.store import ExperimentalStore
    from app.services.asset_library_service import AssetLibraryService
    root = Path(__file__).resolve().parents[1]
    assert Path(os.environ["PROJECT_ROOT"]).resolve() == root
    for key in ("LOCALAPPDATA", "NOVEL_DATA_PATH"):
        assert Path(os.environ[key]).resolve().is_relative_to(root / ".runtime")
    assert tmp_path.resolve().is_relative_to(root / ".runtime")
    backend = request.param
    url = TEST_URL if backend == "postgres" else ""
    if backend == "postgres" and not url:
        pytest.fail("content-policy PostgreSQL case requires a real TEST_POSTGRES_DATABASE_URL")
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", FLAGS)
    bundle = create_repository_bundle(
        Settings(storage_backend=backend, database_url=url, novel_data=tmp_path,
                 enable_cloud=False, mock_provider=True), data_root=tmp_path)
    novels, chapters = NovelService(bundle.novels, bundle.chapters), ChapterService(bundle.chapters)
    nid = "policy-" + uuid4().hex
    novels.create({"id": nid, "title": "Content policy reservation"})
    workspace = IndependentWorkspaceService(CreativeService(ExperimentalStore(tmp_path, backend, url), novels, chapters),
                                            AssetLibraryService(tmp_path), None)
    yield SimpleNamespace(nid=nid, scope={"mode": "local", "novel_id": nid}, actor="policy-author", workspace=workspace)


def test_an_unrelated_edit_never_resets_a_saved_policy(rig):
    scope, actor = rig.scope, rig.actor
    saved = rig.workspace.preferences(rig.nid, scope, actor, {
        "expected_version": 0, "intents": ["BLANK"], "preset": "BLANK", "custom_intent": "",
        "content_policy": "MATURE"})
    row = IndependentWorkspaceService._preferences(rig.workspace.store.read(rig.nid, scope))
    assert row["content_policy"] == "MATURE"
    # An unrelated preference edit that omits the policy must preserve it...
    rig.workspace.preferences(rig.nid, scope, actor, {
        "expected_version": saved["version"], "intents": ["CUSTOM"], "preset": "VIDEO", "custom_intent": "舞台剧"})
    row = IndependentWorkspaceService._preferences(rig.workspace.store.read(rig.nid, scope))
    assert row["content_policy"] == "MATURE" and row["preset"] == "VIDEO"
    assert effective_content_policy(row) == "MATURE"
    # ...and an explicit change still works through the same CAS row.
    current = IndependentWorkspaceService._preference_view(row)
    rig.workspace.preferences(rig.nid, scope, actor, {
        "expected_version": current["version"], "intents": ["CUSTOM"], "preset": "VIDEO", "custom_intent": "舞台剧",
        "content_policy": "STANDARD"})
    row = IndependentWorkspaceService._preferences(rig.workspace.store.read(rig.nid, scope))
    assert effective_content_policy(row) == "STANDARD"
    # The wire view never leaks the reserved field in either state.
    assert "content_policy" not in IndependentWorkspaceService._preference_view(row)
