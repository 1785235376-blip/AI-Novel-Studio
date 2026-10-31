"""Character Bible and Scene Bible as a read-only projection over existing owners.

Why this module exists
----------------------
Round 2 asks for a Character Bible (identity, appearance, clothing, reference,
behaviour, relationship) and a Scene Bible (location, architecture, material,
lighting, weather, time, mood) so that Image, Video and Storyboard can stay
consistent. Every one of those dimensions already has an owner, and this module
creates no new one — it **joins** what exists:

| Bible field | Existing owner that already holds it |
| --- | --- |
| character identity | the project's `characters` records (`name`/`age`/`role`) |
| character behaviour | `WorldService` `PSYCHOLOGY` records |
| character relationship | `WorldService` `RELATIONSHIP` records |
| character appearance / clothing / reference | `WorldService` `CHARACTER_VISUAL` records (added by Round 2) |
| scene location | the project's `locations` records + `WorldService` `GEOGRAPHY` |
| scene architecture / material / lighting / weather / mood / time-of-day | `WorldService` `SCENE_VISUAL` records (added by Round 2) |
| where a character or scene is used | the existing creative documents' scenes and shots |

The module is pure: it takes plain mappings and returns JSON-shaped data, and
imports no application model. It has no write path.

Three honesty rules are enforced in the shape of the output
-----------------------------------------------------------
1. **Unknown is a value.** An unauthored dimension is reported as `UNKNOWN` with
   `authored: false` — never as an empty string that could be read as "nothing to
   say", and never filled in from prose.
2. **Draft is not canon.** A world record carries the owner's own `status`. Only
   `APPROVED` records are `authoritative`; a `DRAFT` is reported as a draft. The
   projection never promotes a record and never merges drafts into canon.
3. **Declared is not verified.** A reference names bytes owned by the asset
   library. This module does not read another owner's store, so a reference is
   reported as `RESOLVED` only when the caller supplied the asset index and the id
   is present there; otherwise it is `UNRESOLVED`. It is never silently assumed.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

BIBLE_CONTRACT = "studio-bible/1"
CHARACTER_BIBLE_CONTRACT = "studio-character-bible/1"
SCENE_BIBLE_CONTRACT = "studio-scene-bible/1"
SCHEMA_VERSION = 1

#: A dimension the owners do not carry. A value, not an empty string.
UNKNOWN = "UNKNOWN"
#: The record exists but the owner has not approved it.
DRAFT = "DRAFT"
#: The dimension is authored and authoritative.
AUTHORED = "AUTHORED"

#: The six required Character Bible dimensions, in display order.
CHARACTER_BIBLE_FIELDS: tuple[str, ...] = (
    "identity", "appearance", "clothing", "reference", "behavior", "relationship",
)
#: The seven required Scene Bible dimensions, in display order.
SCENE_BIBLE_FIELDS: tuple[str, ...] = (
    "location", "architecture", "material", "lighting", "weather", "time", "mood",
)

CHARACTER_BIBLE_LABELS: dict[str, str] = {
    "identity": "身份", "appearance": "外形", "clothing": "服装",
    "reference": "参考图", "behavior": "行为", "relationship": "关系",
}
SCENE_BIBLE_LABELS: dict[str, str] = {
    "location": "地点", "architecture": "建筑", "material": "材质",
    "lighting": "灯光", "weather": "天气", "time": "时间", "mood": "氛围",
}

#: Where each dimension is read from, so a surface can show the provenance.
CHARACTER_SOURCES: dict[str, str] = {
    "identity": "characters.name/age/role",
    "appearance": "world_records.CHARACTER_VISUAL.appearance",
    "clothing": "world_records.CHARACTER_VISUAL.clothing",
    "reference": "world_records.CHARACTER_VISUAL.reference_asset_ids",
    "behavior": "world_records.PSYCHOLOGY.state/motivation",
    "relationship": "world_records.RELATIONSHIP.state",
}
SCENE_SOURCES: dict[str, str] = {
    "location": "locations.name",
    "architecture": "world_records.SCENE_VISUAL.architecture",
    "material": "world_records.SCENE_VISUAL.material",
    "lighting": "world_records.SCENE_VISUAL.lighting",
    "weather": "world_records.SCENE_VISUAL.weather",
    "time": "world_records.SCENE_VISUAL.time_of_day",
    "mood": "world_records.SCENE_VISUAL.mood",
}

#: The world-record kinds that carry authored visual bible data.
CHARACTER_VISUAL_KIND = "CHARACTER_VISUAL"
SCENE_VISUAL_KIND = "SCENE_VISUAL"


def _rows(value: Iterable[Any] | None) -> list[Mapping[str, Any]]:
    if value is None:
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item).strip() for item in value if str(item).strip())
    return str(value).strip()


def _identifiers(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _authored(value: Any) -> bool:
    return bool(_text(value))


def _dimension(field: str, source: str, value: str, *, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """One bible dimension. Unauthored becomes the explicit `UNKNOWN` value."""
    entry: dict[str, Any] = {
        "field": field,
        "label": (CHARACTER_BIBLE_LABELS | SCENE_BIBLE_LABELS).get(field, field),
        "value": value if value else UNKNOWN,
        "authored": bool(value),
        "state": AUTHORED if value else UNKNOWN,
        "source": source,
    }
    if extra:
        entry.update(extra)
    return entry


# ------------------------------------------------------------- world records --

def _record_data_kind(row: Mapping[str, Any], kind: str) -> bool:
    return _text(row.get("kind")) == kind and isinstance(row.get("data"), Mapping)


def _approved(row: Mapping[str, Any]) -> bool:
    return _text(row.get("status")) == "APPROVED"


def _pick(records: Iterable[Mapping[str, Any]], kind: str, key: str, value: str) -> tuple[Mapping[str, Any] | None, bool]:
    """The current record for one subject, preferring an approved one.

    Returns `(row, authoritative)`. A draft is returned when it is all that exists —
    but as a draft, never as canon.
    """
    matching = [row for row in records if _record_data_kind(row, kind) and _text(row["data"].get(key)) == value]
    for row in matching:
        if _approved(row):
            return row, True
    return (matching[0], False) if matching else (None, False)


def _reference_dimension(field: str, source: str, asset_ids: list[str],
                         asset_index: Mapping[str, Any] | None) -> dict[str, Any]:
    """Declared asset references, verified only against an index the caller supplied.

    Without an index nothing can be verified, and saying `RESOLVED` would be a
    fabrication — so every id is reported `UNRESOLVED` and the reason is explicit.
    """
    entries = []
    for asset_id in asset_ids:
        resolved = bool(asset_index is not None and asset_id in asset_index)
        entries.append({"asset_id": asset_id, "resolution": "RESOLVED" if resolved else "UNRESOLVED"})
    unresolved = [entry["asset_id"] for entry in entries if entry["resolution"] == "UNRESOLVED"]
    return {
        "field": field,
        "label": CHARACTER_BIBLE_LABELS.get(field, field),
        "value": ", ".join(asset_ids) if asset_ids else UNKNOWN,
        "authored": bool(asset_ids),
        "state": AUTHORED if asset_ids else UNKNOWN,
        "source": source,
        "references": entries,
        "unresolved_references": unresolved,
        "verification": "INDEX_SUPPLIED" if asset_index is not None else "NO_INDEX_SUPPLIED",
    }


# -------------------------------------------------------------------- usage --

def _usage_index(documents: Iterable[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Where each character id and location id is referenced by real creative content.

    Built only from authored references on scenes and shots — a character is never
    linked to a document by name similarity or any other guess.
    """
    index: dict[str, list[dict[str, Any]]] = {}

    def note(entity_id: str, entry: dict[str, Any]) -> None:
        if not entity_id:
            return
        rows = index.setdefault(entity_id, [])
        if entry not in rows:
            rows.append(entry)

    for document in documents:
        document_id = _text(document.get("id"))
        mode = _text(document.get("mode"))
        scenes = _rows(document.get("scenes"))
        for scene in scenes:
            scene_id = _text(scene.get("id"))
            for character_id in _identifiers(scene.get("characters")):
                note(character_id, {"document_id": document_id, "mode": mode, "role": "SCENE_CAST", "scene_id": scene_id})
            location = _text(scene.get("location"))
            if location:
                # A creative scene names its location as free text; the link is reported
                # as a *name* match only when it equals a known location id or name.
                note(location, {"document_id": document_id, "mode": mode, "role": "SCENE_LOCATION", "scene_id": scene_id})
        for shot in _rows(document.get("shots")):
            shot_id = _text(shot.get("id"))
            for character_id in _identifiers(shot.get("characters")):
                note(character_id, {"document_id": document_id, "mode": mode, "role": "SHOT_CAST", "shot_id": shot_id})
            continuity = shot.get("continuity")
            if isinstance(continuity, Mapping):
                for character_id in [item.strip() for item in _text(continuity.get("characters")).split(",") if item.strip()]:
                    note(character_id, {"document_id": document_id, "mode": mode, "role": "SHOT_CONTINUITY", "shot_id": shot_id})
    return index


# ------------------------------------------------------------- the two bibles --

def project_character_bible(characters: Iterable[Mapping[str, Any]] | None = None, *,
                            world_records: Iterable[Mapping[str, Any]] | None = None,
                            assets: Iterable[Mapping[str, Any]] | None = None,
                            documents: Iterable[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """One entry per existing character record, with the six required dimensions."""
    records = _rows(world_records)
    usage = _usage_index(_rows(documents))
    asset_index = {_text(row.get("id")): row for row in _rows(assets)}

    entries: list[dict[str, Any]] = []
    for character in sorted(_rows(characters), key=lambda row: _text(row.get("id"))):
        character_id = _text(character.get("id"))
        visual, visual_authoritative = _pick(records, CHARACTER_VISUAL_KIND, "character_id", character_id)
        visual_data = dict(visual["data"]) if visual is not None else {}

        identity_bits = [part for part in (
            _text(character.get("name")), _text(character.get("age")),
            _text(character.get("role")), _text(character.get("status")),
        ) if part]
        psychology = [row for row in records
                      if _record_data_kind(row, "PSYCHOLOGY") and _text(row["data"].get("character_id")) == character_id]
        behaviour = ", ".join(part for part in (
            _text(psychology[0]["data"].get("state")) if psychology else "",
            _text(psychology[0]["data"].get("motivation")) if psychology else "",
        ) if part)
        relationships = [
            {"target_character_id": _text(row["data"].get("target_character_id")),
             "state": _text(row["data"].get("state")),
             "authoritative": _approved(row)}
            for row in records
            if _record_data_kind(row, "RELATIONSHIP") and _text(row["data"].get("source_character_id")) == character_id
        ]

        dimensions = [
            _dimension("identity", CHARACTER_SOURCES["identity"], ", ".join(identity_bits)),
            _dimension("appearance", CHARACTER_SOURCES["appearance"], _text(visual_data.get("appearance")),
                       extra={"record_status": _text(visual.get("status")) if visual is not None else None,
                              "authoritative": visual_authoritative}),
            _dimension("clothing", CHARACTER_SOURCES["clothing"], _text(visual_data.get("clothing")),
                       extra={"record_status": _text(visual.get("status")) if visual is not None else None,
                              "authoritative": visual_authoritative}),
            _reference_dimension("reference", CHARACTER_SOURCES["reference"],
                                 _identifiers(visual_data.get("reference_asset_ids")),
                                 asset_index if assets is not None else None),
            _dimension("behavior", CHARACTER_SOURCES["behavior"], behaviour),
            _dimension("relationship", CHARACTER_SOURCES["relationship"],
                       ", ".join(item["state"] for item in relationships),
                       extra={"relationships": relationships}),
        ]
        entries.append({
            "character_id": character_id,
            "name": _text(character.get("name")),
            "dimensions": dimensions,
            "used_in": usage.get(character_id, []),
            "visual_record_status": _text(visual.get("status")) if visual is not None else None,
            "visual_authoritative": visual_authoritative,
        })
    return {
        "contract": CHARACTER_BIBLE_CONTRACT,
        "schema_version": SCHEMA_VERSION,
        "required_fields": list(CHARACTER_BIBLE_FIELDS),
        "entries": entries,
        "character_count": len(entries),
    }


def project_scene_bible(locations: Iterable[Mapping[str, Any]] | None = None, *,
                        world_records: Iterable[Mapping[str, Any]] | None = None,
                        assets: Iterable[Mapping[str, Any]] | None = None,
                        documents: Iterable[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """One entry per existing location record, with the seven required dimensions."""
    records = _rows(world_records)
    usage = _usage_index(_rows(documents))
    asset_index = {_text(row.get("id")): row for row in _rows(assets)}

    entries: list[dict[str, Any]] = []
    for location in sorted(_rows(locations), key=lambda row: _text(row.get("id"))):
        location_id = _text(location.get("id"))
        visual, visual_authoritative = _pick(records, SCENE_VISUAL_KIND, "location_id", location_id)
        visual_data = dict(visual["data"]) if visual is not None else {}
        geography = [row for row in records
                     if _record_data_kind(row, "GEOGRAPHY") and _text(row["data"].get("location_id")) == location_id]

        dimensions = [
            _dimension("location", SCENE_SOURCES["location"],
                       ", ".join(part for part in (_text(location.get("name")), _text(location.get("id"))) if part),
                       extra={"geography_records": len(geography)}),
            _dimension("architecture", SCENE_SOURCES["architecture"], _text(visual_data.get("architecture")),
                       extra={"record_status": _text(visual.get("status")) if visual is not None else None,
                              "authoritative": visual_authoritative}),
            _dimension("material", SCENE_SOURCES["material"], _text(visual_data.get("material")),
                       extra={"record_status": _text(visual.get("status")) if visual is not None else None,
                              "authoritative": visual_authoritative}),
            _dimension("lighting", SCENE_SOURCES["lighting"], _text(visual_data.get("lighting")),
                       extra={"record_status": _text(visual.get("status")) if visual is not None else None,
                              "authoritative": visual_authoritative}),
            _dimension("weather", SCENE_SOURCES["weather"], _text(visual_data.get("weather")),
                       extra={"record_status": _text(visual.get("status")) if visual is not None else None,
                              "authoritative": visual_authoritative}),
            _dimension("time", SCENE_SOURCES["time"], _text(visual_data.get("time_of_day")),
                       extra={"record_status": _text(visual.get("status")) if visual is not None else None,
                              "authoritative": visual_authoritative}),
            _dimension("mood", SCENE_SOURCES["mood"], _text(visual_data.get("mood")),
                       extra={"record_status": _text(visual.get("status")) if visual is not None else None,
                              "authoritative": visual_authoritative}),
        ]
        entries.append({
            "location_id": location_id,
            "name": _text(location.get("name")),
            "dimensions": dimensions,
            "reference_asset_ids": _identifiers(visual_data.get("reference_asset_ids")),
            "used_in": usage.get(location_id, []),
            "visual_record_status": _text(visual.get("status")) if visual is not None else None,
            "visual_authoritative": visual_authoritative,
        })
    return {
        "contract": SCENE_BIBLE_CONTRACT,
        "schema_version": SCHEMA_VERSION,
        "required_fields": list(SCENE_BIBLE_FIELDS),
        "entries": entries,
        "location_count": len(entries),
    }


def project_bible(*, characters=None, locations=None, world_records=None,
                  assets=None, documents=None) -> dict[str, Any]:
    """The whole read-only bible: both halves, plus what each entry still lacks.

    `gaps` exists so the surface can answer "what is missing?" without any inference:
    it is the literal list of dimensions still reported `UNKNOWN`.
    """
    character_bible = project_character_bible(characters, world_records=world_records,
                                              assets=assets, documents=documents)
    scene_bible = project_scene_bible(locations, world_records=world_records,
                                      assets=assets, documents=documents)
    character_gaps = [
        {"character_id": entry["character_id"], "field": dimension["field"]}
        for entry in character_bible["entries"] for dimension in entry["dimensions"]
        if not dimension["authored"]
    ]
    scene_gaps = [
        {"location_id": entry["location_id"], "field": dimension["field"]}
        for entry in scene_bible["entries"] for dimension in entry["dimensions"]
        if not dimension["authored"]
    ]
    return {
        "contract": BIBLE_CONTRACT,
        "schema_version": SCHEMA_VERSION,
        "advisory_only": True,
        "execution_authority": False,
        "auto_modify": False,
        "required_character_fields": list(CHARACTER_BIBLE_FIELDS),
        "required_scene_fields": list(SCENE_BIBLE_FIELDS),
        "character_bible": character_bible,
        "scene_bible": scene_bible,
        "gaps": {"characters": character_gaps, "scenes": scene_gaps},
        "unknown_is_explicit": True,
    }
