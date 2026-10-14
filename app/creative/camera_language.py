"""Authoritative camera language for the existing Director/Storyboard owners.

Why this module exists
----------------------
`DirectorNote` (`app/creative/models.py:62`) already carries the professional
fields — `shot_size`, `camera_angle`, `camera_motion`, `composition`, `lens`,
`lighting`, `color_palette`, `emotion`, `performance`, `blocking`,
`character_state` — but every camera field is a bounded **free-text string**
(`max_length` only). Anything could be stored: "WIDE", "wide shot", "ultra wide",
"很宽的镜头". That is not structured data, and nothing could be checked, compared or
projected from it.

This module adds the vocabulary **on top of those existing fields**. It does not
introduce a second shot, scene, project or asset model, and it never rewrites a
stored value.

Backward compatibility is the hard constraint
---------------------------------------------
Existing projects hold free text, and those rows must stay readable. So a value is
classified rather than coerced:

* `CANONICAL`          — matches a vocabulary member or a documented alias
* `LEGACY_PASSTHROUGH` — non-empty but unrecognised: preserved **verbatim**, never
                         guessed at, and explicitly reported as non-canonical
* `EMPTY`              — not authored

`normalise` therefore never invents a meaning. `require_canonical` is the strict
gate, and it is for *new* professional writes only — it is deliberately not wired
into the legacy shot-update path, so old clients keep working.

Continuity is checked only from **authored** continuity
-------------------------------------------------------
`ShotContinuity` (`models.py:111`) states its own rule: authored constraints, never
inferred identity guarantees. `continuity_warnings` obeys that — it compares two
adjacent shots only where **both** authored a value, and it never treats a camera
change as a break, because changing the camera between shots is legitimate
direction rather than a continuity error.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

#: Shot sizes, ordered widest to tightest.
SHOT_SIZES: tuple[str, ...] = ("EXTREME_WIDE", "WIDE", "MEDIUM", "CLOSE_UP", "EXTREME_CLOSE_UP")

#: Camera movements.
CAMERA_MOTIONS: tuple[str, ...] = ("STATIC", "PAN", "TILT", "DOLLY", "TRACKING", "CRANE", "HANDHELD")

#: Lens classes.
LENSES: tuple[str, ...] = ("WIDE", "NORMAL", "TELEPHOTO", "MACRO")

#: Compositions.
COMPOSITIONS: tuple[str, ...] = ("RULE_OF_THIRDS", "CENTER", "SYMMETRY", "LEADING_LINES")

#: One authoritative vocabulary per existing owner field.
VOCABULARIES: dict[str, tuple[str, ...]] = {
    "shot_size": SHOT_SIZES,
    "camera_motion": CAMERA_MOTIONS,
    "lens": LENSES,
    "composition": COMPOSITIONS,
}

#: Documented spellings that map onto a canonical member. Lower-case, and compared
#: after the same folding `normalise` applies to input.
ALIASES: dict[str, dict[str, str]] = {
    "shot_size": {
        "EXTREME WIDE SHOT": "EXTREME_WIDE", "XW": "EXTREME_WIDE", "EWS": "EXTREME_WIDE",
        "WIDE SHOT": "WIDE", "WS": "WIDE", "LONG SHOT": "WIDE",
        "MEDIUM SHOT": "MEDIUM", "MS": "MEDIUM", "MID SHOT": "MEDIUM",
        "CLOSEUP": "CLOSE_UP", "CLOSE UP": "CLOSE_UP", "CLOSE": "CLOSE_UP", "CU": "CLOSE_UP",
        "EXTREME CLOSEUP": "EXTREME_CLOSE_UP", "EXTREME CLOSE UP": "EXTREME_CLOSE_UP",
        "ECU": "EXTREME_CLOSE_UP",
    },
    "camera_motion": {
        "STILL": "STATIC", "FIXED": "STATIC", "LOCKED": "STATIC",
        "PAN LEFT": "PAN", "PAN RIGHT": "PAN", "PANNING": "PAN",
        "TILT UP": "TILT", "TILT DOWN": "TILT", "TILTING": "TILT",
        "DOLLY IN": "DOLLY", "DOLLY OUT": "DOLLY", "PUSH IN": "DOLLY",
        "TRACK": "TRACKING", "TRACKING SHOT": "TRACKING", "FOLLOW": "TRACKING",
        "CRANE UP": "CRANE", "JIB": "CRANE",
        "HAND HELD": "HANDHELD", "HAND-HELD": "HANDHELD", "SHAKY": "HANDHELD",
    },
    "lens": {
        "WIDE ANGLE": "WIDE", "WIDEANGLE": "WIDE",
        "STANDARD": "NORMAL", "NORMAL LENS": "NORMAL",
        "TELE": "TELEPHOTO", "TELEPHOTO LENS": "TELEPHOTO", "LONG LENS": "TELEPHOTO",
        "MACRO LENS": "MACRO",
    },
    "composition": {
        "RULE OF THIRDS": "RULE_OF_THIRDS", "THIRDS": "RULE_OF_THIRDS",
        "CENTRE": "CENTER", "CENTERED": "CENTER", "CENTRAL": "CENTER",
        "SYMMETRIC": "SYMMETRY", "SYMMETRICAL": "SYMMETRY",
        "LEADING LINE": "LEADING_LINES", "LEADING LINES": "LEADING_LINES",
    },
}

CANONICAL = "CANONICAL"
LEGACY_PASSTHROUGH = "LEGACY_PASSTHROUGH"
EMPTY = "EMPTY"


def _fold(value: Any) -> str:
    """Case/space/separator-insensitive form used for matching only."""
    text = str(value or "").strip().upper()
    for separator in ("_", "-", "\t", "\n"):
        text = text.replace(separator, " ")
    return " ".join(text.split())


@dataclass(frozen=True)
class CameraField:
    """One classified camera field. `value` is canonical only when `code` says so."""

    field: str
    raw: str
    value: str
    code: str

    @property
    def canonical(self) -> bool:
        return self.code == CANONICAL

    @property
    def legacy(self) -> bool:
        return self.code == LEGACY_PASSTHROUGH

    def as_dict(self) -> dict[str, Any]:
        return {"field": self.field, "value": self.value, "code": self.code,
                "canonical": self.canonical}


def normalise(field: str, raw: Any) -> CameraField:
    """Classify one camera field without ever changing a user's meaning.

    Unrecognised non-empty text is returned **verbatim** as `LEGACY_PASSTHROUGH`:
    the old value stays readable and is honestly reported as not canonical.
    """
    vocabulary = VOCABULARIES.get(field)
    if vocabulary is None:
        raise ValueError("CREATIVE_CAMERA_FIELD_UNKNOWN")
    original = str(raw or "")
    folded = _fold(original)
    if not folded:
        return CameraField(field, original, "", EMPTY)
    spaceless = folded.replace(" ", "_")
    if spaceless in vocabulary:
        return CameraField(field, original, spaceless, CANONICAL)
    alias = ALIASES.get(field, {}).get(folded)
    if alias:
        return CameraField(field, original, alias, CANONICAL)
    return CameraField(field, original, original, LEGACY_PASSTHROUGH)


def require_canonical(field: str, raw: Any) -> str:
    """Strict gate for **new** professional writes. Never used on legacy paths."""
    result = normalise(field, raw)
    if result.code != CANONICAL:
        raise ValueError("CREATIVE_CAMERA_VOCABULARY_INVALID")
    return result.value


def project_camera(source: Mapping[str, Any]) -> dict[str, Any]:
    """Read-only structured projection of the camera fields on a shot or note.

    The input mapping is never mutated and no field is invented: an unauthored
    field is reported as `EMPTY`, and legacy text is echoed unchanged beneath a
    non-canonical code.
    """
    if not isinstance(source, Mapping):
        raise ValueError("CREATIVE_CAMERA_SOURCE_INVALID")
    fields = {field: normalise(field, source.get(field, "")) for field in VOCABULARIES}
    camera = {field: item.value for field, item in fields.items()}
    camera["angle"] = str(source.get("camera_angle", "") or "")
    return {
        "camera": camera,
        "classification": {field: item.code for field, item in fields.items()},
        "canonical_ratio": (sum(1 for item in fields.values() if item.canonical)
                            / len(fields)),
    }


# --- continuity over authored constraints only ------------------------------

#: Compared fields, taken from the existing `ShotContinuity` owner.
#: `camera` is deliberately excluded: changing the camera between shots is
#: direction, not a continuity break.
CONTINUITY_FIELDS: tuple[str, ...] = ("characters", "outfit", "environment")

CONTINUITY_CODES: dict[str, str] = {
    "characters": "CONTINUITY_CHARACTERS_CHANGED",
    "outfit": "CONTINUITY_OUTFIT_CHANGED",
    "environment": "CONTINUITY_ENVIRONMENT_CHANGED",
}


@dataclass(frozen=True)
class ContinuityWarning:
    """A difference between two *authored* continuity blocks. Never an inference."""

    code: str
    field: str
    previous_shot_id: str
    next_shot_id: str
    previous_value: str
    next_value: str

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "field": self.field, "previous_shot_id": self.previous_shot_id,
                "next_shot_id": self.next_shot_id, "previous": self.previous_value,
                "next": self.next_value}


def _authored(shot: Mapping[str, Any]) -> Mapping[str, Any]:
    value = shot.get("continuity")
    return value if isinstance(value, Mapping) else {}


def continuity_warnings(shots: Iterable[Mapping[str, Any]]) -> list[ContinuityWarning]:
    """Warn where two adjacent shots **both** authored a differing constraint.

    Reported as a warning only — nothing is changed, corrected or inferred, which
    is what `ShotContinuity`'s own docstring requires.

    Comparison ignores case and surrounding whitespace but **not** internal
    spacing, so `红 色 外套` and `红色外套` are reported rather than silently
    equated. That asymmetry is deliberate: a spurious warning is dismissible,
    whereas a silently swallowed continuity break is not.
    """
    ordered = [shot for shot in shots if isinstance(shot, Mapping)]
    warnings: list[ContinuityWarning] = []
    for previous, following in zip(ordered, ordered[1:]):
        before, after = _authored(previous), _authored(following)
        for field in CONTINUITY_FIELDS:
            left, right = str(before.get(field, "") or "").strip(), str(after.get(field, "") or "").strip()
            # Only two authored values can disagree; a missing one is unknown, not a break.
            if not left or not right or _fold(left) == _fold(right):
                continue
            warnings.append(ContinuityWarning(
                code=CONTINUITY_CODES[field], field=field,
                previous_shot_id=str(previous.get("id", "") or ""),
                next_shot_id=str(following.get("id", "") or ""),
                previous_value=left, next_value=right,
            ))
    return warnings
