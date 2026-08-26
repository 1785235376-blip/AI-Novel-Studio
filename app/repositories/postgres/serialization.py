from __future__ import annotations

from collections.abc import Mapping
from typing import Any


MAX_SOURCE_ORDER = 2**31 - 1
RESERVED_FIELDS = frozenset({
    "id", "name", "age", "status", "privacy_level", "facts", "details",
})
INTERNAL_FIELDS = frozenset({"_source_id", "_source_order"})


def split_internal_fields(payload: Mapping[str, Any] | None) -> tuple[dict[str, Any], str | None, int]:
    """Return public extension fields, source id, and stable source order."""
    data = dict(payload or {})
    source_id = data.pop("_source_id", None)
    raw_order = data.pop("_source_order", MAX_SOURCE_ORDER)
    try:
        source_order = int(raw_order)
    except (TypeError, ValueError):
        source_order = MAX_SOURCE_ORDER
    public = {key: value for key, value in data.items() if key not in RESERVED_FIELDS and key not in INTERNAL_FIELDS}
    return public, str(source_id) if source_id is not None else None, source_order


def character_order(model: Any) -> int:
    return split_internal_fields(model.facts)[2]


def serialize_character(model: Any) -> dict[str, Any]:
    public, _, _ = split_internal_fields(model.facts)
    return {
        "id": model.slug,
        "name": model.name,
        "age": model.age,
        "status": model.life_status,
        **public,
        "privacy_level": model.privacy,
    }


def location_order(model: Any) -> int:
    return split_internal_fields(model.facts)[2]


def serialize_location(model: Any) -> dict[str, Any]:
    public, _, _ = split_internal_fields(model.facts)
    return {
        "id": model.slug,
        "name": model.name,
        **public,
        "privacy_level": model.privacy,
    }


def timeline_order(model: Any) -> tuple[int, int]:
    return int(model.sequence), split_internal_fields(model.details)[2]


def serialize_timeline(model: Any) -> dict[str, Any]:
    public, source_id, _ = split_internal_fields(model.details)
    output = {
        **public,
        "id": source_id or str(model.id),
        "sequence": model.sequence,
        "time": model.event_time,
        "title": model.title,
    }
    if "privacy_level" in (model.details or {}):
        output["privacy_level"] = model.privacy
    return output


def _secret_mapping(model: Any, id_mapping: Mapping[str, Any] | None) -> Mapping[str, Any]:
    candidate = (id_mapping or {}).get(str(model.id), {})
    return candidate if isinstance(candidate, Mapping) else {}


def secret_order(model: Any, id_mapping: Mapping[str, Any] | None) -> int:
    raw_order = _secret_mapping(model, id_mapping).get("order", MAX_SOURCE_ORDER)
    try:
        return int(raw_order)
    except (TypeError, ValueError):
        return MAX_SOURCE_ORDER


def serialize_secret(model: Any, id_mapping: Mapping[str, Any] | None, *, public: bool = False) -> dict[str, Any]:
    mapping = _secret_mapping(model, id_mapping)
    output = {
        "id": str(mapping.get("id") or model.id),
        "title": model.title,
        "content": None if public else model.content,
        "earliest_reveal_chapter": model.earliest_reveal_chapter,
        "status": model.status,
        "privacy_level": model.privacy,
    }
    if public:
        output["visibility"] = model.privacy
    return output


def foreshadowing_order(model: Any) -> tuple[int, int]:
    _, _, source_order = split_internal_fields(model.details)
    planted = model.planted_chapter if model.planted_chapter is not None else MAX_SOURCE_ORDER
    return source_order, int(planted)


def serialize_foreshadowing(model: Any) -> dict[str, Any]:
    public, source_id, _ = split_internal_fields(model.details)
    return {
        **public,
        "id": source_id or str(model.id),
        "title": model.title,
        "status": model.status,
        "planted_chapter": model.planted_chapter,
        **({"target_chapter": model.target_chapter} if model.target_chapter is not None else {}),
    }


def serialize_canon(model: Any) -> dict[str, Any]:
    output = dict(model.fact_value or {})
    output.setdefault("id", str(model.id))
    output.setdefault("source", model.source)
    output.setdefault("privacy_level", model.privacy)
    return output
