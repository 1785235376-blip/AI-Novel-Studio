"""Read-only Director Intent / Shot Card / Continuity projection.

Why this module exists
----------------------
Phase14-A asks for a *director decision workbench*: a Director Workspace, a Shot
Card, a Continuity Panel, structured Director Intent output and a Camera Language
UI binding. Every one of those is a **view over data the existing owners already
hold**, so this module adds no owner, no store and no second model:

| Surface | Existing owner that already holds the value |
| --- | --- |
| Director Intent | `DirectorVisualTarget` (`style`/`atmosphere`/`genre`/`color`/`rhythm`/`reference_works`) and, per shot, `DirectorNote` |
| Shot Card | `ShotCard` — every one of the eleven required fields already exists on it |
| Continuity | `ShotContinuity` plus the shot's own authored fields, through `camera_language` |
| Camera Language | `camera_language.VOCABULARIES` / `ALIASES` — published here so the UI cannot drift from it |

The module is deliberately pure: it takes plain mappings (a stored creative
document row) and returns plain JSON-shaped data. It imports no application model,
so the "no second system" rule is a property of the code rather than a promise.

Two honesty rules are enforced in the shape of the output
--------------------------------------------------------
1. **Nothing is invented.** A field that the owner did not author is reported as
   unauthored with an empty value — never guessed, never defaulted into a
   plausible-looking decision.
2. **Measured is not authored.** Some dimensions (`camera_language`, `lighting`,
   `performance_direction`) have no document-level home; they live per shot. Those
   are reported as `PER_SHOT_MEASURED` with an explicit usage measurement, so the
   surface can never imply that a document-level decision was made when only
   per-shot values exist. Document-level values are `DOCUMENT_AUTHORED`.

Advisory only. This module has no write path, mutates nothing, and cannot grant
execution authority.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from . import camera_language

#: Contracts. The workspace contract wraps the three surface contracts.
DIRECTOR_WORKSPACE_CONTRACT = "studio-director-workspace/1"
DIRECTOR_INTENT_CONTRACT = "studio-director-intent/1"
SHOT_CARD_CONTRACT = "studio-shot-card/1"
CONTINUITY_PANEL_CONTRACT = "studio-continuity-panel/1"
SCHEMA_VERSION = 1

#: A value authored on the document itself.
DOCUMENT_AUTHORED = "DOCUMENT_AUTHORED"
#: A dimension authored per shot and summarised here; there is no document-level value.
PER_SHOT_MEASURED = "PER_SHOT_MEASURED"

INTENT_FIELDS: tuple[str, ...] = (
    "visual_goal", "mood", "genre", "camera_language", "lighting",
    "color_direction", "performance_direction",
)

INTENT_LABELS: dict[str, str] = {
    "visual_goal": "视觉目标",
    "mood": "情绪基调",
    "genre": "题材",
    "camera_language": "镜头语言",
    "lighting": "灯光",
    "color_direction": "色彩方向",
    "performance_direction": "表演方向",
}

#: field -> (kind, source path, authoritative owner field).
#: `source` is the exact owner location the value is read from, so every number on
#: a director surface can be traced back to the owner that actually stores it.
INTENT_SPECS: dict[str, tuple[str, str, str]] = {
    "visual_goal": (DOCUMENT_AUTHORED, "visual_target.style", "DirectorVisualTarget.style"),
    "mood": (DOCUMENT_AUTHORED, "visual_target.atmosphere", "DirectorVisualTarget.atmosphere"),
    "genre": (DOCUMENT_AUTHORED, "visual_target.genre", "DirectorVisualTarget.genre"),
    "color_direction": (DOCUMENT_AUTHORED, "visual_target.color", "DirectorVisualTarget.color"),
    "camera_language": (PER_SHOT_MEASURED, "shot_size/camera_motion/lens/composition", "ShotCard / DirectorNote"),
    "lighting": (PER_SHOT_MEASURED, "lighting", "ShotCard.lighting / DirectorNote.lighting"),
    "performance_direction": (PER_SHOT_MEASURED, "performance/blocking/character_state/emotion", "ShotCard / DirectorNote"),
}

#: The eleven fields the phase requires a Shot Card to show, in display order.
SHOT_CARD_FIELDS: tuple[str, ...] = (
    "shot_id", "duration", "camera", "lens", "movement", "composition",
    "lighting", "character", "action", "emotion", "audio",
)

#: The performance signals measured for `performance_direction`.
PERFORMANCE_KEYS: tuple[str, ...] = ("performance", "blocking", "character_state", "emotion")

#: Dimensions deliberately NOT compared, with the reason, so their absence is
#: visibly a decision rather than an oversight.
CONTINUITY_EXCLUDED: tuple[dict[str, str], ...] = (
    {"field": "camera", "reason": "CAMERA_MOVE_IS_DIRECTION"},
)


def _mapping(value: Any, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(code)
    return value


def _sequence(document: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    raw = document.get(key)
    if not isinstance(raw, (list, tuple)):
        return []
    return [item for item in raw if isinstance(item, Mapping)]


def _shots(document: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Shots in displayed order. `number` is the owner's own ordering field."""
    return sorted(_sequence(document, "shots"), key=lambda row: (row.get("number", 0), str(row.get("id", ""))))


def _notes(document: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return sorted(_sequence(document, "director_notes"), key=lambda row: (row.get("number", 0), str(row.get("id", ""))))


def _visual_target(document: Mapping[str, Any]) -> Mapping[str, Any]:
    value = document.get("visual_target")
    return value if isinstance(value, Mapping) else {}


def _text(value: Any) -> str:
    return camera_language.authored_text(value)


def _record(field: str, value: str, source: str, owner: str) -> dict[str, Any]:
    return {"field": field, "value": value, "authored": bool(value), "source": source, "owner": owner}


# --------------------------------------------------------------- shot cards --

def project_shot_card(shot: Mapping[str, Any]) -> dict[str, Any]:
    """One Shot Card carrying all eleven required fields, read from `ShotCard`.

    Read-only: the input mapping is never mutated. A field the owner left unset is
    reported as unauthored with an empty value instead of being filled in with
    something that merely looks reasonable.
    """
    source = _mapping(shot, "CREATIVE_DIRECTOR_SHOT_INVALID")
    projected_camera = camera_language.project_camera(source)
    dialogue = [{"speaker": _text(item.get("speaker")), "text": _text(item.get("text")),
                 "delivery": _text(item.get("delivery"))}
                for item in source.get("dialogue", []) if isinstance(item, Mapping)] if isinstance(source.get("dialogue"), (list, tuple)) else []
    characters = [str(item).strip() for item in source.get("characters", []) if str(item).strip()] \
        if isinstance(source.get("characters"), (list, tuple)) else []
    sound, sound_effect = _text(source.get("sound")), _text(source.get("sound_effect"))
    audio_authored = bool(sound or sound_effect or dialogue)
    duration = source.get("duration_seconds")
    return {
        "contract": SHOT_CARD_CONTRACT,
        "shot_id": _text(source.get("id")),
        "number": source.get("number"),
        "scene_id": _text(source.get("scene_id")),
        "duration": {"seconds": duration if isinstance(duration, int) else None,
                     "authored": isinstance(duration, int)},
        "camera": projected_camera["camera"],
        "camera_classification": projected_camera["classification"],
        "camera_canonical_ratio": projected_camera["canonical_ratio"],
        "lens": {**_record("lens", _text(projected_camera["camera"].get("lens")),
                           "ShotCard.lens", "ShotCard.lens"),
                 "code": projected_camera["classification"]["lens"]},
        "movement": {**_record("movement", _text(projected_camera["camera"].get("camera_motion")),
                               "ShotCard.camera_motion", "ShotCard.camera_motion"),
                     "code": projected_camera["classification"]["camera_motion"]},
        "composition": {**_record("composition", _text(projected_camera["camera"].get("composition")),
                                  "ShotCard.composition", "ShotCard.composition"),
                        "code": projected_camera["classification"]["composition"]},
        "lighting": _record("lighting", _text(source.get("lighting")), "ShotCard.lighting", "ShotCard.lighting"),
        "character": {"field": "character", "values": characters, "authored": bool(characters),
                      "source": "ShotCard.characters", "owner": "ShotCard.characters"},
        "action": _record("action", _text(source.get("action")), "ShotCard.action", "ShotCard.action"),
        "emotion": _record("emotion", _text(source.get("emotion")), "ShotCard.emotion", "ShotCard.emotion"),
        "audio": {"field": "audio", "sound": sound, "sound_effect": sound_effect, "dialogue": dialogue,
                  "authored": audio_authored, "source": "ShotCard.sound/sound_effect/dialogue",
                  "owner": "ShotCard"},
        "director_note_ids": [str(item) for item in source.get("director_note_ids", [])]
        if isinstance(source.get("director_note_ids"), (list, tuple)) else [],
    }


def project_shot_cards(document: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [project_shot_card(shot) for shot in _shots(_mapping(document, "CREATIVE_DIRECTOR_DOCUMENT_INVALID"))]


# ------------------------------------------------------------- intent usage --

def _measurement_rows(document: Mapping[str, Any]) -> tuple[str, list[Mapping[str, Any]]]:
    """Which authored rows a per-shot dimension is summarised over.

    A DIRECTOR document authors `director_notes`; a STORYBOARD document authors
    `shots`. Whichever the owner actually produced is the one measured, and the
    choice is reported rather than hidden.
    """
    shots = _shots(document)
    if shots:
        return "SHOTS", shots
    notes = _notes(document)
    if notes:
        return "DIRECTOR_NOTES", notes
    return "NONE", []


def _camera_usage(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = list(rows)
    dimensions: dict[str, Any] = {}
    canonical = legacy = authored = 0
    legacy_values: list[str] = []
    for field in camera_language.VOCABULARIES:
        counts: dict[tuple[str, str], int] = {}
        field_authored = 0
        for row in rows:
            classified = camera_language.normalise(field, row.get(field, ""))
            counts[(classified.value, classified.code)] = counts.get((classified.value, classified.code), 0) + 1
            if classified.code == camera_language.EMPTY:
                continue
            field_authored += 1
            authored += 1
            if classified.canonical:
                canonical += 1
            else:
                legacy += 1
                legacy_values.append(classified.value)
        values = [{"value": value, "code": code, "count": count}
                  for (value, code), count in sorted(counts.items(), key=lambda item: (-item[1], item[0][0]))]
        dimensions[field] = {"rows": len(rows), "authored_rows": field_authored, "values": values}
    total = len(rows) * len(camera_language.VOCABULARIES)
    return {
        "measured_over_rows": len(rows),
        "dimensions": dimensions,
        "authored_values": authored,
        "canonical_values": canonical,
        "legacy_values_preserved": sorted(set(legacy_values)),
        "canonical_ratio": (canonical / total) if total else 0.0,
        "vocabulary": {
            field: {"members": list(members), "aliases": dict(camera_language.ALIASES.get(field, {})),
                    # Alias keys are published exactly as `normalise` matches them —
                    # the folded (upper-case, separator-normalised) form — so a UI
                    # that sends a raw user string resolves identically here.
                    "alias_keys_are_folded": True}
            for field, members in camera_language.VOCABULARIES.items()
        },
    }


def _simple_usage(rows: Iterable[Mapping[str, Any]], keys: tuple[str, ...]) -> dict[str, Any]:
    """Authored-value coverage for dimensions that are plain authored text.

    Nested `director_notes` on a shot card are included, because a shot's
    performance direction is authored there by the existing derivation owner. Both
    locations are authored facts on existing owners; neither is inferred.
    """
    rows = list(rows)
    dimensions: dict[str, Any] = {}
    authored_rows = 0
    for row in rows:
        containers = [row, *[item for item in row.get("director_notes", []) if isinstance(item, Mapping)]] \
            if isinstance(row.get("director_notes"), (list, tuple)) else [row]
        if any(_text(container.get(key)) for container in containers for key in keys):
            authored_rows += 1
    for key in keys:
        values: dict[str, int] = {}
        key_rows = 0
        for row in rows:
            containers = [row, *[item for item in row.get("director_notes", []) if isinstance(item, Mapping)]] \
                if isinstance(row.get("director_notes"), (list, tuple)) else [row]
            seen = {_text(container.get(key)) for container in containers}
            seen.discard("")
            if seen:
                key_rows += 1
            for value in seen:
                values[value] = values.get(value, 0) + 1
        dimensions[key] = {
            "rows": len(rows), "authored_rows": key_rows,
            "values": [{"value": value, "count": count} for value, count in sorted(values.items(), key=lambda item: (-item[1], item[0]))],
        }
    return {"measured_over_rows": len(rows), "authored_rows": authored_rows,
            "unauthored_rows": len(rows) - authored_rows, "dimensions": dimensions}


# ---------------------------------------------------------- director intent --

def project_director_intent(document: Mapping[str, Any]) -> dict[str, Any]:
    """The seven Director Intent dimensions as structured, traceable output.

    Document-level dimensions report their authored value. Per-shot dimensions
    report a measurement instead — with `authored: false` and
    `authored_scope: PER_SHOT` — so a surface can never present a summary as
    though the director had authored a document-level decision.
    """
    source = _mapping(document, "CREATIVE_DIRECTOR_DOCUMENT_INVALID")
    target = _visual_target(source)
    measured_over, rows = _measurement_rows(source)
    fields: list[dict[str, Any]] = []
    dimensions: dict[str, Any] = {}
    for field in INTENT_FIELDS:
        kind, path, owner = INTENT_SPECS[field]
        if kind == DOCUMENT_AUTHORED:
            value = _text(target.get(path.split(".", 1)[1]))
            entry: dict[str, Any] = {**_record(field, value, path, owner),
                                     "label": INTENT_LABELS[field], "kind": kind,
                                     "authored_scope": "DOCUMENT", "usage": None}
            if field == "visual_goal":
                # Rhythm and reference works are additional authored context that
                # belongs to the visual goal; they stay visible without inflating
                # the required seven.
                entry["detail"] = {
                    "rhythm": _text(target.get("rhythm")),
                    "reference_works": [str(item) for item in target.get("reference_works", [])]
                    if isinstance(target.get("reference_works"), (list, tuple)) else [],
                }
        else:
            entry = {**_record(field, "", path, owner), "label": INTENT_LABELS[field], "kind": kind,
                     "authored_scope": "PER_SHOT",
                     "usage": _camera_usage(rows) if field == "camera_language"
                     else _simple_usage(rows, (("lighting",) if field == "lighting" else PERFORMANCE_KEYS))}
        fields.append(entry)
        dimensions[field] = entry
    return {
        "contract": DIRECTOR_INTENT_CONTRACT,
        "schema_version": SCHEMA_VERSION,
        "advisory_only": True,
        "auto_modify": False,
        "measured_over": measured_over,
        "required_fields": list(INTENT_FIELDS),
        "fields": fields,
        "dimensions": dimensions,
        "production_constraints": {
            "advisory_only": True, "execution_authority": False,
            "cost_status": "UNKNOWN", "feasibility_status": "UNKNOWN",
            "fields": [_record(field, _text(target.get(field)), f"visual_target.{field}",
                               f"DirectorVisualTarget.{field}") for field in
                       ("target_audience", "target_platform", "production_budget_constraints")],
        },
    }


# ------------------------------------------------------------ continuuity ----

def project_continuity(document: Mapping[str, Any]) -> dict[str, Any]:
    """The Continuity Panel: five dimensions, warning only, never a correction.

    `warning_only` and `auto_modify: false` are contract fields, not comments —
    the panel reports differences and the human decides. Coverage is reported per
    dimension so silence is never presented as agreement: a pair where either side
    left a dimension unauthored was *not* compared.
    """
    source = _mapping(document, "CREATIVE_DIRECTOR_DOCUMENT_INVALID")
    shots = _shots(source)
    warnings = camera_language.continuity_warnings(shots)
    coverage: dict[str, Any] = {}
    for field in camera_language.CONTINUITY_FIELDS:
        compared = unknown = 0
        for previous, following in zip(shots, shots[1:]):
            before = camera_language.authored_continuity_values(previous)[field]
            after = camera_language.authored_continuity_values(following)[field]
            if before and after:
                compared += 1
            else:
                unknown += 1
        coverage[field] = {"field": field, "label": camera_language.CONTINUITY_LABELS[field],
                           "code": camera_language.CONTINUITY_CODES[field],
                           "sources": [f"{container}.{key}" for container, key in camera_language.CONTINUITY_SOURCES[field]],
                           "compared_pairs": compared, "unknown_pairs": unknown}
    decorated = []
    for warning in warnings:
        row = warning.as_dict()
        row["label"] = camera_language.CONTINUITY_LABELS.get(warning.field, warning.field)
        row["severity"] = "WARNING"
        decorated.append(row)
    return {
        "contract": CONTINUITY_PANEL_CONTRACT,
        "schema_version": SCHEMA_VERSION,
        "warning_only": True,
        "auto_modify": False,
        "required_dimensions": list(camera_language.CONTINUITY_FIELDS),
        "dimensions": [coverage[field] for field in camera_language.CONTINUITY_FIELDS],
        "excluded": [dict(item) for item in CONTINUITY_EXCLUDED],
        "shot_count": len(shots),
        "compared_pairs": max(len(shots) - 1, 0),
        "warnings": decorated,
    }


# ---------------------------------------------------------------- workspace --

def project_director_workspace(document: Mapping[str, Any]) -> dict[str, Any]:
    """One bounded Director Workspace projection over a stored creative document."""
    source = _mapping(document, "CREATIVE_DIRECTOR_DOCUMENT_INVALID")
    return {
        "contract": DIRECTOR_WORKSPACE_CONTRACT,
        "schema_version": SCHEMA_VERSION,
        "advisory_only": True,
        "execution_authority": False,
        "auto_modify": False,
        "document": {
            "id": _text(source.get("id")),
            "version": source.get("version"),
            "mode": _text(source.get("mode")),
            "title": _text(source.get("title")),
            "status": _text(source.get("status")),
        },
        "required_shot_card_fields": list(SHOT_CARD_FIELDS),
        "director_intent": project_director_intent(source),
        "shot_cards": project_shot_cards(source),
        "continuity": project_continuity(source),
    }
