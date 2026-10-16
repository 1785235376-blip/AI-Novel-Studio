"""Phase14-A Professional Director System: intent, shot card and continuity.

Two properties matter beyond the individual cases, and they are the reason this
suite exists at all:

* **no second system** — the Director Workspace is a read-only view over the
  existing `DirectorVisualTarget`, `ShotCard`, `ShotContinuity` and
  `camera_language` owners; a test asserts the projection module defines no model
  and imports no application model, so that stays true by construction;
* **hint, never correction** — the continuity panel reports differences between
  *authored* values and has no write path, and a dimension authored on only one
  side of a cut is unknown rather than a break.

The pure projection tests run anywhere. The one route test needs the isolated
runner (`scripts/run_v2_checks.py`), which is what sets `PROJECT_ROOT`; without it
the route test skips rather than reporting a pass it did not earn.
"""
from __future__ import annotations

import inspect
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.creative import camera_language as camera
from app.creative import director_intent as director


# --------------------------------------------------------------- fixtures --

def shot(identifier: str, **fields):
    """A stored shot row, in the same plain shape the owner persists."""
    return {"id": identifier, "number": fields.pop("number", 1), "scene_id": fields.pop("scene_id", "scene-1"),
            **fields}


def document(**overrides):
    row = {
        "id": "doc-1", "version": 3, "mode": "STORYBOARD", "title": "旧城回声",
        "status": "DRAFT", "visual_target": None, "scenes": [], "shots": [], "director_notes": [],
    }
    row.update(overrides)
    return row


# ------------------------------------------------------ contract surfaces --

def test_the_seven_director_intent_dimensions_are_the_required_set():
    assert director.INTENT_FIELDS == (
        "visual_goal", "mood", "genre", "camera_language", "lighting",
        "color_direction", "performance_direction")


def test_the_eleven_shot_card_fields_are_the_required_set():
    assert director.SHOT_CARD_FIELDS == (
        "shot_id", "duration", "camera", "lens", "movement", "composition",
        "lighting", "character", "action", "emotion", "audio")


def test_the_five_continuity_dimensions_are_the_required_set():
    assert camera.CONTINUITY_FIELDS == ("characters", "outfit", "environment", "time", "lighting")


def test_every_intent_source_names_a_real_owner_field():
    """The projection may not read from a field the owners do not have."""
    from app.creative.models import DirectorNote, DirectorVisualTarget

    for field, (_, source, owner) in director.INTENT_SPECS.items():
        if source.startswith("visual_target."):
            assert source.split(".", 1)[1] in DirectorVisualTarget.model_fields, field
        else:
            for name in source.split("/"):
                assert name in DirectorNote.model_fields or name in ("shot_size", "lens", "composition"), (field, name)


def test_every_shot_card_field_is_backed_by_an_existing_owner_field():
    from app.creative.models import ShotCard

    for field in ("duration_seconds", "shot_size", "camera_angle", "camera_motion", "lens", "composition",
                  "lighting", "characters", "action", "emotion", "sound", "sound_effect", "dialogue"):
        assert field in ShotCard.model_fields, field


# ------------------------------------------------ the no-second-system rule --

def test_projection_module_defines_no_second_model_and_imports_no_app_model():
    source = inspect.getsource(director)
    for forbidden in ("from app", "import app", "class Shot(", "class Scene(", "class Project(",
                      "class Asset(", "class Task(", "class ShotCard(", "class DirectorNote("):
        assert forbidden not in source, f"the director projection must reuse owners, not {forbidden}"


def test_projection_defines_no_owner_and_never_writes():
    source = inspect.getsource(director)
    for forbidden in ("def create", "def update", "def write", "def save", "def commit", "def delete"):
        assert forbidden not in source, f"the director projection is read-only, not {forbidden}"


# --------------------------------------------------------- director intent --

def test_document_level_intent_reports_the_authored_value_and_its_source():
    projected = director.project_director_intent(document(visual_target={
        "style": "冷峻写实", "atmosphere": "压抑", "genre": "悬疑科幻",
        "color": "青蓝低饱和", "rhythm": "缓—急—缓", "reference_works": ["《银翼杀手》"],
    }))
    dimensions = projected["dimensions"]
    assert dimensions["visual_goal"]["value"] == "冷峻写实"
    assert dimensions["visual_goal"]["source"] == "visual_target.style"
    assert dimensions["visual_goal"]["authored"] is True
    assert dimensions["mood"]["value"] == "压抑"
    assert dimensions["genre"]["value"] == "悬疑科幻"
    assert dimensions["genre"]["authored"] is True
    assert dimensions["color_direction"]["value"] == "青蓝低饱和"
    assert projected["dimensions"]["visual_goal"]["detail"]["rhythm"] == "缓—急—缓"
    assert projected["dimensions"]["visual_goal"]["detail"]["reference_works"] == ["《银翼杀手》"]


def test_unauthored_document_intent_is_empty_not_invented():
    projected = director.project_director_intent(document(visual_target=None))
    genre = projected["dimensions"]["genre"]
    assert genre["value"] == "" and genre["authored"] is False
    assert genre["authored_scope"] == "DOCUMENT"


def test_per_shot_dimensions_are_measured_never_reported_as_document_decisions():
    """The distinction the surface depends on: measured is not authored."""
    projected = director.project_director_intent(document(shots=[
        shot("s1", number=1, shot_size="WIDE", lighting="暖光"),
        shot("s2", number=2, shot_size="ultra wide", lighting="暖光"),
    ]))
    for field in ("camera_language", "lighting", "performance_direction"):
        entry = projected["dimensions"][field]
        assert entry["kind"] == director.PER_SHOT_MEASURED
        assert entry["authored"] is False and entry["value"] == ""
        assert entry["authored_scope"] == "PER_SHOT"
        assert entry["usage"]["measured_over_rows"] == 2
    assert projected["measured_over"] == "SHOTS"


def test_camera_language_usage_separates_canonical_from_preserved_legacy_text():
    projected = director.project_director_intent(document(shots=[
        shot("s1", number=1, shot_size="wide shot", camera_motion="dolly in", lens="normal", composition="centre"),
        shot("s2", number=2, shot_size="很宽的镜头", camera_motion="STATIC", lens="", composition=""),
    ]))
    usage = projected["dimensions"]["camera_language"]["usage"]
    assert usage["measured_over_rows"] == 2
    # Shot 1 authors four canonical values; shot 2 authors one legacy (preserved
    # verbatim) and one canonical `STATIC`, and leaves lens/composition unauthored.
    assert usage["authored_values"] == 6
    assert usage["legacy_values_preserved"] == ["很宽的镜头"]
    assert 0 < usage["canonical_ratio"] < 1
    members = usage["vocabulary"]["camera_motion"]["members"]
    assert members == list(camera.CAMERA_MOTIONS)


def test_camera_language_usage_publishes_the_owner_vocabulary_verbatim():
    """The UI binds to this, so the backend is the only source of the word list."""
    usage = director.project_director_intent(document(shots=[]))["dimensions"]["camera_language"]["usage"]
    for field, members in camera.VOCABULARIES.items():
        assert usage["vocabulary"][field]["members"] == list(members)
        # Alias keys are published in the same folded form `normalise` matches
        # against, so a UI sending a raw user string still resolves identically.
        assert usage["vocabulary"][field]["alias_keys_are_folded"] is True
    assert usage["vocabulary"]["composition"]["aliases"]["RULE OF THIRDS"] == "RULE_OF_THIRDS"


def test_measurement_falls_back_to_director_notes_and_says_so():
    projected = director.project_director_intent(document(mode="DIRECTOR", shots=[], director_notes=[
        {"id": "n1", "number": 1, "scene_id": "sc1", "lighting": "逆光", "performance": "克制"},
        {"id": "n2", "number": 2, "scene_id": "sc1", "lighting": "逆光"},
    ]))
    assert projected["measured_over"] == "DIRECTOR_NOTES"
    lighting = projected["dimensions"]["lighting"]["usage"]
    assert lighting["measured_over_rows"] == 2 and lighting["authored_rows"] == 2
    performance = projected["dimensions"]["performance_direction"]["usage"]
    assert performance["dimensions"]["performance"]["authored_rows"] == 1
    assert performance["unauthored_rows"] == 1


def test_intent_projection_never_mutates_the_document():
    row = document(visual_target={"style": "写实"}, shots=[shot("s1", number=1, lighting="暖光")])
    before = repr(row)
    director.project_director_intent(row)
    assert repr(row) == before


# ------------------------------------------------------------- shot cards --

def test_shot_card_carries_every_required_field():
    card = director.project_shot_card({
        "id": "shot-01", "number": 1, "scene_id": "sc-1", "duration_seconds": 7,
        "shot_size": "close up", "camera_angle": "LOW", "camera_motion": "dolly in",
        "lens": "tele", "composition": "rule of thirds", "lighting": "冷光",
        "characters": ["林向晚"], "action": "推门", "emotion": "迟疑",
        "sound": "雨声", "sound_effect": "门轴", "dialogue": [{"speaker": "林向晚", "text": "有人吗"}],
    })
    for field in director.SHOT_CARD_FIELDS:
        assert field in card, field
    assert card["shot_id"] == "shot-01"
    assert card["duration"] == {"seconds": 7, "authored": True}
    assert card["camera"]["shot_size"] == "CLOSE_UP" and card["camera"]["angle"] == "LOW"
    assert card["lens"]["value"] == "TELEPHOTO" and card["lens"]["code"] == camera.CANONICAL
    assert card["movement"]["value"] == "DOLLY"
    assert card["composition"]["value"] == "RULE_OF_THIRDS"
    assert card["lighting"]["value"] == "冷光"
    assert card["character"]["values"] == ["林向晚"] and card["character"]["authored"] is True
    assert card["action"]["value"] == "推门"
    assert card["emotion"]["value"] == "迟疑"
    assert card["audio"]["sound"] == "雨声" and card["audio"]["sound_effect"] == "门轴"
    assert card["audio"]["dialogue"] == [{"speaker": "林向晚", "text": "有人吗", "delivery": ""}]
    assert card["audio"]["authored"] is True


def test_an_unset_shot_card_field_is_reported_empty_not_defaulted():
    card = director.project_shot_card({"id": "s1", "number": 1, "scene_id": "sc"})
    assert card["lens"]["value"] == "" and card["lens"]["code"] == camera.EMPTY
    assert card["lighting"]["authored"] is False
    assert card["emotion"]["authored"] is False
    assert card["audio"]["authored"] is False and card["audio"]["dialogue"] == []
    assert card["character"]["values"] == []


def test_legacy_free_text_on_a_shot_card_is_preserved_and_flagged():
    card = director.project_shot_card({"id": "s1", "number": 1, "scene_id": "sc", "shot_size": "很宽的镜头"})
    assert card["camera"]["shot_size"] == "很宽的镜头"
    assert card["camera_classification"]["shot_size"] == camera.LEGACY_PASSTHROUGH


def test_shot_card_projection_does_not_mutate_the_shot():
    row = {"id": "s1", "number": 1, "scene_id": "sc", "characters": ["A"], "dialogue": [{"speaker": "A", "text": "x"}]}
    before = repr(row)
    director.project_shot_card(row)
    assert repr(row) == before


def test_shot_cards_follow_the_owner_display_order():
    cards = director.project_shot_cards(document(shots=[
        shot("s2", number=2), shot("s1", number=1), shot("s3", number=3)]))
    assert [card["shot_id"] for card in cards] == ["s1", "s2", "s3"]


# ------------------------------------------------------------- continuity --

def test_continuity_panel_is_warning_only_and_declares_that():
    panel = director.project_continuity(document(shots=[shot("a", number=1), shot("b", number=2)]))
    assert panel["warning_only"] is True
    assert panel["auto_modify"] is False
    assert panel["required_dimensions"] == ["characters", "outfit", "environment", "time", "lighting"]


def test_time_and_lighting_changes_now_warn():
    panel = director.project_continuity(document(shots=[
        shot("a", number=1, lighting="暖光", continuity={"time": "夜", "lighting": "暖光"}),
        shot("b", number=2, lighting="冷光", continuity={"time": "日", "lighting": "冷光"}),
    ]))
    assert {warning["code"] for warning in panel["warnings"]} == {
        "CONTINUITY_TIME_CHANGED", "CONTINUITY_LIGHTING_CHANGED"}
    for warning in panel["warnings"]:
        assert warning["severity"] == "WARNING" and warning["label"]


def test_a_lighting_value_authored_on_the_card_is_compared_without_retyping():
    """The panel is a hint, not a form: one authored home is enough."""
    panel = director.project_continuity(document(shots=[
        shot("a", number=1, lighting="暖光"),
        shot("b", number=2, lighting="冷光"),
    ]))
    assert [warning["code"] for warning in panel["warnings"]] == ["CONTINUITY_LIGHTING_CHANGED"]


def test_a_dimension_authored_on_one_side_only_stays_unknown():
    panel = director.project_continuity(document(shots=[
        shot("a", number=1, continuity={"time": "夜"}),
        shot("b", number=2),
    ]))
    assert panel["warnings"] == []
    time_row = next(row for row in panel["dimensions"] if row["field"] == "time")
    assert time_row["compared_pairs"] == 0 and time_row["unknown_pairs"] == 1


def test_coverage_is_reported_so_silence_is_not_mistaken_for_agreement():
    panel = director.project_continuity(document(shots=[
        shot("a", number=1, continuity={"outfit": "红", "time": "夜"}),
        shot("b", number=2, continuity={"outfit": "红", "time": "夜"}),
    ]))
    assert panel["warnings"] == []
    outfit = next(row for row in panel["dimensions"] if row["field"] == "outfit")
    lighting = next(row for row in panel["dimensions"] if row["field"] == "lighting")
    assert outfit["compared_pairs"] == 1
    assert lighting["compared_pairs"] == 0 and lighting["unknown_pairs"] == 1


def test_a_camera_change_is_still_direction_not_a_break():
    panel = director.project_continuity(document(shots=[
        shot("a", number=1, continuity={"camera": "WIDE"}),
        shot("b", number=2, continuity={"camera": "CLOSE_UP"}),
    ]))
    assert panel["warnings"] == []
    assert panel["excluded"] == [{"field": "camera", "reason": "CAMERA_MOVE_IS_DIRECTION"}]


def test_continuity_does_not_mutate_the_shots():
    shots = [shot("a", number=1, continuity={"outfit": "红"}), shot("b", number=2, continuity={"outfit": "蓝"})]
    snapshot = repr(shots)
    director.project_continuity(document(shots=shots))
    assert repr(shots) == snapshot


# ------------------------------------------------------------- workspace ----

def test_workspace_projection_composes_the_three_surfaces_and_grants_nothing():
    projected = director.project_director_workspace(document(
        visual_target={"style": "写实"}, shots=[shot("s1", number=1, lighting="暖光")]))
    assert projected["contract"] == "studio-director-workspace/1"
    assert projected["advisory_only"] is True
    assert projected["execution_authority"] is False
    assert projected["auto_modify"] is False
    assert projected["document"] == {"id": "doc-1", "version": 3, "mode": "STORYBOARD",
                                     "title": "旧城回声", "status": "DRAFT"}
    assert set(projected) >= {"director_intent", "shot_cards", "continuity"}
    assert projected["required_shot_card_fields"] == list(director.SHOT_CARD_FIELDS)


def test_a_malformed_document_is_refused_rather_than_guessed():
    with pytest.raises(ValueError, match="CREATIVE_DIRECTOR_DOCUMENT_INVALID"):
        director.project_director_workspace(["not", "a", "document"])  # type: ignore[arg-type]


# ------------------------------------------------- optional owner extensions --

def test_shot_continuity_without_the_new_fields_keeps_its_exact_serialized_shape():
    """Backward compatibility: an unset opt-in field must not appear at all."""
    from app.creative.models import ShotContinuity

    legacy = ShotContinuity.model_validate({"characters": "林向晚", "outfit": "红"})
    assert legacy.model_dump() == {"characters": "林向晚", "outfit": "红", "environment": "", "camera": ""}


def test_shot_continuity_round_trips_the_new_dimensions_when_authored():
    from app.creative.models import ShotContinuity

    value = ShotContinuity.model_validate({"outfit": "红", "time": "夜", "lighting": "暖光"})
    assert value.time == "夜" and value.lighting == "暖光"
    assert value.model_dump() == {"characters": "", "outfit": "红", "environment": "", "camera": "",
                                  "time": "夜", "lighting": "暖光"}


def test_director_visual_target_without_genre_keeps_its_exact_serialized_shape():
    from app.creative.models import DirectorVisualTarget

    legacy = DirectorVisualTarget.model_validate({"style": "写实", "atmosphere": "压抑"})
    assert legacy.model_dump() == {"style": "写实", "atmosphere": "压抑", "reference_works": [],
                                   "color": "", "rhythm": ""}


def test_director_visual_target_carries_an_authored_genre_when_present():
    from app.creative.models import DirectorVisualTarget

    value = DirectorVisualTarget.model_validate({"style": "写实", "genre": "悬疑科幻"})
    assert value.genre == "悬疑科幻"
    assert value.model_dump()["genre"] == "悬疑科幻"


def test_an_unknown_extra_field_is_still_refused_on_both_extended_owners():
    from app.creative.models import DirectorVisualTarget, ShotContinuity

    for model in (DirectorVisualTarget, ShotContinuity):
        with pytest.raises(Exception):
            model.model_validate({"not_a_field": "x"})


# ------------------------------------------------------- route admission ----

def test_only_the_declared_methods_reach_the_director_workspace_path():
    from app.creative.workspace_api import is_independent_studio_route

    assert is_independent_studio_route("GET", "/api/projects/P1/studio/director/workspace/D1")
    for method, path in (("POST", "/api/projects/P1/studio/director/workspace/D1"),
                         ("PUT", "/api/projects/P1/studio/director/workspace/D1"),
                         ("DELETE", "/api/projects/P1/studio/director/workspace/D1"),
                         ("GET", "/api/projects/P1/studio/director/workspace"),
                         ("GET", "/api/projects/P1/studio/director/workspace/D1/extra")):
        assert not is_independent_studio_route(method, path), (method, path)


# ------------------------------------------------------ route integration ---

HARNESS_MISSING = "requires the isolated runner (scripts/run_v2_checks.py) that sets PROJECT_ROOT"


@pytest.fixture
def rig(tmp_path, monkeypatch):
    """A real studio router over the real File store, stub authority only.

    Mirrors `tests/test_v2_production_workflow_api.py`: the permission string, the
    scope admission and the error mapping are exercised end to end.
    """
    root = Path(__file__).resolve().parents[1]
    if os.environ.get("PROJECT_ROOT") is None:
        pytest.skip(HARNESS_MISSING)
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.creative.service import CreativeService
    from app.creative.workspace import IndependentWorkspaceService
    from app.experimental.media import MediaService
    from app.experimental.production_lineage import ProductionLineageService
    from app.experimental.store import ExperimentalStore
    from app.repositories.factory import create_repository_bundle
    from app.services import ChapterService, NovelService
    from app.services.asset_library_service import AssetLibraryService

    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2,asset_lineage_v2")
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    bundle = create_repository_bundle(
        Settings(storage_backend="file", database_url="", novel_data=tmp_path,
                 enable_cloud=False, mock_provider=True), data_root=tmp_path)
    novels, chapters = NovelService(bundle.novels, bundle.chapters), ChapterService(bundle.chapters)
    nid = "phase14a-director-" + uuid4().hex
    novels.create({"id": nid, "title": "Phase14-A director", "genre": "悬疑科幻"})
    raw = ExperimentalStore(tmp_path, "file", "")
    assets = AssetLibraryService(tmp_path)
    creative = CreativeService(raw, novels, chapters)
    lineage = ProductionLineageService(raw, novels, chapters, assets, MediaService(raw, novels, chapters, assets))
    workspace = IndependentWorkspaceService(creative, assets, lineage)

    def authorize(project_id, token, branch, permission):
        if token != "valid-session":
            raise HTTPException(403, {"code": "CREATIVE_AUTHORITY_INVALID"})
        return "phase14a-author", {"mode": "local", "novel_id": project_id}

    from app.creative.workspace_api import create_independent_workspace_router
    app = FastAPI()
    app.include_router(create_independent_workspace_router(
        workspace, authorize, lambda flag: None,
        create_project=lambda body, token: (_ for _ in ()).throw(AssertionError("not used")),
        workspace_writer=lambda token: "phase14a-author"), prefix="/api")
    return SimpleNamespace(client=TestClient(app), nid=nid, creative=creative,
                           scope={"mode": "local", "novel_id": nid})


#: Two adjacent shots that differ in exactly three authored dimensions: outfit and
#: time in the continuity block, and lighting between the card and the block.
_DIRECTOR_DOCUMENT = {
    "mode": "STORYBOARD", "title": "旧城回声 分镜", "source_independent": True,
    "visual_target": {"style": "冷峻写实", "atmosphere": "压抑", "genre": "悬疑科幻",
                      "color": "青蓝低饱和", "rhythm": "缓—急—缓", "reference_works": ["《银翼杀手》"]},
    "scenes": [
        {"id": "scene-1", "sequence": 1, "heading": "INT. 旧城公寓 - 夜", "time": "夜",
         "location": "旧城公寓", "characters": ["林向晚"]},
        {"id": "scene-2", "sequence": 2, "heading": "EXT. 天台 - 日", "time": "日",
         "location": "天台", "characters": ["林向晚"]},
    ],
    "shots": [
        {"number": 1, "scene_id": "scene-1", "shot_size": "WIDE", "camera_motion": "STATIC",
         "lens": "NORMAL", "composition": "CENTER", "lighting": "暖光", "characters": ["林向晚"],
         "action": "推门", "emotion": "迟疑", "sound": "雨声", "duration_seconds": 6,
         "continuity": {"outfit": "红色外套", "environment": "旧城公寓", "time": "夜"}},
        {"number": 2, "scene_id": "scene-2", "shot_size": "CLOSE_UP", "camera_motion": "DOLLY",
         "lens": "TELEPHOTO", "composition": "RULE_OF_THIRDS", "lighting": "冷光", "characters": ["林向晚"],
         "action": "回头", "emotion": "警觉", "sound_effect": "风声", "duration_seconds": 4,
         "continuity": {"outfit": "蓝色外套", "environment": "旧城公寓", "time": "日"}},
    ],
}


def _director_document(rig):
    """Create the phase's example director document through the existing owner."""
    return rig.creative.create(rig.nid, rig.scope, "phase14a-author", _DIRECTOR_DOCUMENT,
                               reauthorize=lambda: None)


def test_director_workspace_route_projects_the_original_document(rig):
    created = _director_document(rig)
    response = rig.client.get(f"/api/projects/{rig.nid}/studio/director/workspace/{created['id']}",
                              headers={"x-session-token": "valid-session"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["contract"] == "studio-director-workspace/1"
    assert body["advisory_only"] is True and body["execution_authority"] is False
    assert body["director_intent"]["dimensions"]["genre"]["value"] == "悬疑科幻"
    assert body["project_context"]["genre"] == "悬疑科幻"
    assert [card["shot_id"] for card in body["shot_cards"]] == [created["shots"][0]["id"], created["shots"][1]["id"]]
    codes = {warning["code"] for warning in body["continuity"]["warnings"]}
    assert codes == {"CONTINUITY_OUTFIT_CHANGED", "CONTINUITY_TIME_CHANGED", "CONTINUITY_LIGHTING_CHANGED"}
    assert body["continuity"]["auto_modify"] is False


def test_director_workspace_route_requires_authority_and_hides_unknown_documents(rig):
    created = _director_document(rig)
    path = f"/api/projects/{rig.nid}/studio/director/workspace/{created['id']}"
    assert rig.client.get(path, headers={"x-session-token": "nope"}).status_code == 403
    unknown = rig.client.get(f"/api/projects/{rig.nid}/studio/director/workspace/missing-doc",
                             headers={"x-session-token": "valid-session"})
    assert unknown.status_code == 404


def test_director_workspace_route_does_not_expose_a_write_binding(rig):
    """The projection route is GET-only; authoring stays on the existing owner.

    Read from the app's own OpenAPI contract rather than a hand-kept list, so this
    cannot drift from what the router actually publishes. Authoring a Director
    Intent continues to use the pre-existing creative document update owner, which
    this phase did not touch or re-route.
    """
    spec = rig.client.get("/openapi.json").json()
    path = "/api/projects/{nid}/studio/director/workspace/{rid}"
    assert path in spec["paths"], sorted(item for item in spec["paths"] if "director" in item)
    assert set(spec["paths"][path]) == {"get"}
