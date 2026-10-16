"""Camera language vocabulary and authored-continuity warnings.

Two properties matter beyond the individual cases:

* **old projects stay readable** — unrecognised free text is preserved verbatim and
  reported as non-canonical rather than coerced or rejected;
* **nothing is inferred** — continuity warnings only compare two *authored* values,
  and a camera change is never treated as a continuity break.
"""
from __future__ import annotations

import inspect

import pytest

from app.creative import camera_language as camera


# --- the vocabulary is the one the phase asked for --------------------------

def test_shot_sizes_are_the_five_required():
    assert camera.SHOT_SIZES == ("EXTREME_WIDE", "WIDE", "MEDIUM", "CLOSE_UP", "EXTREME_CLOSE_UP")


def test_camera_motions_are_the_seven_required():
    assert camera.CAMERA_MOTIONS == ("STATIC", "PAN", "TILT", "DOLLY", "TRACKING", "CRANE", "HANDHELD")


def test_lenses_are_the_four_required():
    assert camera.LENSES == ("WIDE", "NORMAL", "TELEPHOTO", "MACRO")


def test_compositions_are_the_four_required():
    assert camera.COMPOSITIONS == ("RULE_OF_THIRDS", "CENTER", "SYMMETRY", "LEADING_LINES")


def test_every_vocabulary_field_is_an_existing_owner_field():
    """The vocabulary must sit on the existing shot/note fields, not a new model."""
    from app.creative.models import DirectorNote

    for field in camera.VOCABULARIES:
        assert field in DirectorNote.model_fields, field


# --- canonical, aliases, legacy passthrough, empty --------------------------

@pytest.mark.parametrize("raw,expected", [
    ("CLOSE_UP", "CLOSE_UP"), ("close up", "CLOSE_UP"), ("closeup", "CLOSE_UP"),
    ("CU", "CLOSE_UP"), ("close", "CLOSE_UP"), ("  Close-Up  ", "CLOSE_UP"),
    ("medium shot", "MEDIUM"), ("MS", "MEDIUM"), ("wide", "WIDE"),
    ("extreme wide shot", "EXTREME_WIDE"), ("EWS", "EXTREME_WIDE"), ("ECU", "EXTREME_CLOSE_UP"),
])
def test_shot_size_aliases_resolve_to_canonical(raw, expected):
    result = camera.normalise("shot_size", raw)
    assert (result.value, result.code) == (expected, camera.CANONICAL)
    assert result.canonical and not result.legacy


@pytest.mark.parametrize("raw,expected", [
    ("STATIC", "STATIC"), ("still", "STATIC"), ("tilt up", "TILT"), ("dolly in", "DOLLY"),
    ("hand-held", "HANDHELD"), ("tracking shot", "TRACKING"), ("jib", "CRANE"), ("panning", "PAN"),
])
def test_camera_motion_aliases_resolve_to_canonical(raw, expected):
    assert camera.normalise("camera_motion", raw).value == expected


@pytest.mark.parametrize("field,raw,expected", [
    ("lens", "wide angle", "WIDE"), ("lens", "standard", "NORMAL"), ("lens", "tele", "TELEPHOTO"),
    ("composition", "rule of thirds", "RULE_OF_THIRDS"), ("composition", "centre", "CENTER"),
    ("composition", "symmetrical", "SYMMETRY"), ("composition", "leading lines", "LEADING_LINES"),
])
def test_lens_and_composition_aliases(field, raw, expected):
    assert camera.normalise(field, raw).value == expected


def test_old_free_text_is_preserved_verbatim_not_guessed():
    """The compatibility rule: never invent a meaning for unrecognised text."""
    for raw in ("ultra wide", "很宽的镜头", "??"):
        result = camera.normalise("shot_size", raw)
        assert result.code == camera.LEGACY_PASSTHROUGH
        assert result.value == raw and result.legacy and not result.canonical


def test_empty_is_reported_as_empty_not_legacy():
    for raw in ("", "   ", None):
        result = camera.normalise("shot_size", raw)
        assert result.code == camera.EMPTY and result.value == ""


def test_unknown_field_is_refused():
    with pytest.raises(ValueError, match="CREATIVE_CAMERA_FIELD_UNKNOWN"):
        camera.normalise("not_a_camera_field", "WIDE")


def test_strict_gate_accepts_canonical_and_refuses_legacy():
    assert camera.require_canonical("shot_size", "close up") == "CLOSE_UP"
    for raw in ("", "ultra wide", "很宽的镜头"):
        with pytest.raises(ValueError, match="CREATIVE_CAMERA_VOCABULARY_INVALID"):
            camera.require_canonical("shot_size", raw)


# --- projection is read-only and invents nothing ----------------------------

def test_projection_does_not_mutate_the_source():
    source = {"shot_size": "close up", "camera_motion": "dolly in",
              "lens": "42mm", "composition": "rule of thirds", "camera_angle": "EYE_LEVEL"}
    before = dict(source)
    projected = camera.project_camera(source)
    assert source == before
    assert projected["camera"] == {"shot_size": "CLOSE_UP", "camera_motion": "DOLLY",
                                   "lens": "42mm", "composition": "RULE_OF_THIRDS",
                                   "angle": "EYE_LEVEL"}
    assert projected["classification"] == {"shot_size": "CANONICAL", "camera_motion": "CANONICAL",
                                           "lens": "LEGACY_PASSTHROUGH", "composition": "CANONICAL"}
    assert projected["canonical_ratio"] == 0.75


def test_projection_reports_unset_fields_as_empty():
    projected = camera.project_camera({})
    assert set(projected["camera"].values()) == {""}
    assert projected["canonical_ratio"] == 0


def test_projection_refuses_a_non_mapping():
    with pytest.raises(ValueError, match="CREATIVE_CAMERA_SOURCE_INVALID"):
        camera.project_camera(["not", "a", "mapping"])  # type: ignore[arg-type]


# --- continuity: authored only, warning only --------------------------------

def shot(identifier, **continuity):
    return {"id": identifier, "continuity": continuity}


def test_authored_outfit_change_raises_the_expected_warning():
    """The phase's own example: shot 01 red, shot 02 blue."""
    warnings = camera.continuity_warnings([
        shot("shot-01", outfit="红色外套", characters="林向晚", environment="旧城公寓"),
        shot("shot-02", outfit="蓝色外套", characters="林向晚", environment="旧城公寓"),
    ])
    assert len(warnings) == 1
    warning = warnings[0]
    assert warning.code == "CONTINUITY_OUTFIT_CHANGED" and warning.field == "outfit"
    assert warning.previous_shot_id == "shot-01" and warning.next_shot_id == "shot-02"
    assert (warning.previous_value, warning.next_value) == ("红色外套", "蓝色外套")


def test_identical_authored_values_warn_nothing():
    assert camera.continuity_warnings([
        shot("a", outfit="红色外套"), shot("b", outfit="红色外套"),
    ]) == []


def test_case_and_surrounding_whitespace_are_not_a_change():
    assert camera.continuity_warnings([
        shot("a", outfit="Red Coat"), shot("b", outfit="  RED   COAT  "),
    ]) == []


def test_internal_spacing_difference_warns_conservatively():
    """Deliberate asymmetry: a spurious warning is dismissible, a missed break is silent.

    `红 色 外套` and `红色外套` are therefore NOT silently equated - the checker
    reports the difference and leaves the judgement to the author.
    """
    warnings = camera.continuity_warnings([shot("a", outfit="红色外套"), shot("b", outfit="红 色 外套")])
    assert [warning.code for warning in warnings] == ["CONTINUITY_OUTFIT_CHANGED"]


def test_a_missing_authored_value_is_unknown_not_a_break():
    """One side unauthored means unknown; it must not be reported as a change."""
    assert camera.continuity_warnings([shot("a", outfit="红色外套"), shot("b")]) == []
    assert camera.continuity_warnings([shot("a"), shot("b", outfit="蓝色外套")]) == []


def test_a_camera_change_is_direction_not_a_continuity_break():
    """Deliberate: moving the camera between shots is normal filmmaking."""
    assert camera.continuity_warnings([
        shot("a", camera="WIDE"), shot("b", camera="CLOSE_UP"),
    ]) == []


def test_all_authored_fields_can_warn():
    warnings = camera.continuity_warnings([
        shot("a", characters="A", outfit="红", environment="室内"),
        shot("b", characters="B", outfit="蓝", environment="室外"),
    ])
    assert {warning.code for warning in warnings} == {
        "CONTINUITY_CHARACTERS_CHANGED", "CONTINUITY_OUTFIT_CHANGED",
        "CONTINUITY_ENVIRONMENT_CHANGED"}


def test_continuity_checking_does_not_mutate_the_shots():
    shots = [shot("a", outfit="红"), shot("b", outfit="蓝")]
    snapshot = [dict(item, continuity=dict(item["continuity"])) for item in shots]
    camera.continuity_warnings(shots)
    assert shots == snapshot


def test_shots_without_a_continuity_block_are_ignored():
    assert camera.continuity_warnings([{"id": "a"}, {"id": "b"}]) == []


def test_warnings_are_json_shaped():
    warning = camera.continuity_warnings([shot("a", outfit="红"), shot("b", outfit="蓝")])[0]
    assert set(warning.as_dict()) == {"code", "field", "previous_shot_id", "next_shot_id",
                                      "previous", "next"}


# --- reuse, not a second system ---------------------------------------------

def test_module_reuses_existing_owners_and_defines_no_second_model():
    source = inspect.getsource(camera)
    for forbidden in ("from app", "import app", "class Shot(", "class Scene(", "class Project(",
                      "class Asset(", "class Task("):
        assert forbidden not in source, f"camera language must reuse owners, not {forbidden}"
