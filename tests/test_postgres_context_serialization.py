from __future__ import annotations

import uuid
from types import SimpleNamespace

from app.repositories.postgres.serialization import (
    character_order,
    foreshadowing_order,
    location_order,
    secret_order,
    serialize_canon,
    serialize_character,
    serialize_foreshadowing,
    serialize_location,
    serialize_secret,
    serialize_timeline,
    split_internal_fields,
    timeline_order,
)


def model(**values):
    return SimpleNamespace(**values)


def test_character_is_file_compatible_and_protects_reserved_fields():
    item = model(slug="lin-hai", name="Lin", age=24, life_status="ALIVE", privacy="CLOUD_ALLOWED",
                 facts={"role": "lead", "traits": ["careful"], "status": "CORRUPT",
                        "id": "uuid-leak", "facts": {"nested": True}, "_source_order": 3})
    assert serialize_character(item) == {"id": "lin-hai", "name": "Lin", "age": 24,
                                          "status": "ALIVE", "role": "lead",
                                          "traits": ["careful"], "privacy_level": "CLOUD_ALLOWED"}
    assert character_order(item) == 3


def test_location_expands_facts_and_sorts_by_source_order():
    item = model(slug="old-port", name="Old Port", privacy="CLOUD_ALLOWED",
                 facts={"travel_hours": {"lighthouse": 2}, "description": "wet",
                        "rules": ["no fire"], "name": "CORRUPT", "_source_order": 1})
    assert serialize_location(item) == {"id": "old-port", "name": "Old Port",
                                         "travel_hours": {"lighthouse": 2},
                                         "description": "wet", "rules": ["no fire"],
                                         "privacy_level": "CLOUD_ALLOWED"}
    assert location_order(item) == 1


def test_timeline_restores_source_id_time_and_removes_internal_fields():
    item = model(id=uuid.uuid4(), sequence=2, event_time="day two", title="Meeting",
                 privacy="CLOUD_ALLOWED", details={"_source_id": "meeting", "_source_order": 4,
                                                    "note": "extra", "id": "CORRUPT"})
    assert serialize_timeline(item) == {"id": "meeting", "sequence": 2, "time": "day two",
                                         "title": "Meeting", "note": "extra"}
    assert timeline_order(item) == (2, 4)


def test_secret_uses_metadata_mapping_and_keeps_public_policy_separate():
    internal_id = uuid.uuid4()
    item = model(id=internal_id, title="Identity", content="hidden", earliest_reveal_chapter=20,
                 status="ACTIVE", privacy="LOCAL_ONLY")
    mapping = {str(internal_id): {"id": "captain-identity", "order": 2}}
    assert serialize_secret(item, mapping) == {"id": "captain-identity", "title": "Identity",
                                                "content": "hidden", "earliest_reveal_chapter": 20,
                                                "status": "ACTIVE", "privacy_level": "LOCAL_ONLY"}
    assert serialize_secret(item, mapping, public=True)["content"] is None
    assert serialize_secret(item, mapping, public=True)["visibility"] == "LOCAL_ONLY"
    assert secret_order(item, mapping) == 2
    assert serialize_secret(item, {})["id"] == str(internal_id)


def test_foreshadowing_restores_id_removes_internal_fields_and_orders_source_first():
    item = model(id=uuid.uuid4(), title="Rust key", status="OPEN", planted_chapter=1,
                 target_chapter=None, details={"_source_id": "rust-key", "_source_order": 0,
                                               "hint": "door", "status": "CORRUPT"})
    assert serialize_foreshadowing(item) == {"id": "rust-key", "title": "Rust key",
                                             "status": "OPEN", "planted_chapter": 1,
                                             "hint": "door"}
    assert foreshadowing_order(item) == (0, 1)


def test_canon_preserves_business_id_and_falls_back_only_when_absent():
    internal_id = uuid.uuid4()
    item = model(id=internal_id, fact_value={"id": "business-fact", "fact": "A",
                                             "source": "file", "privacy_level": "LOCAL_ONLY"},
                 source="database", privacy="CLOUD_ALLOWED")
    assert serialize_canon(item) == {"id": "business-fact", "fact": "A",
                                     "source": "file", "privacy_level": "LOCAL_ONLY"}
    fallback = model(id=internal_id, fact_value={"fact": "B"}, source="migration", privacy="CLOUD_ALLOWED")
    assert serialize_canon(fallback)["id"] == str(internal_id)


def test_split_internal_fields_is_pure_and_handles_invalid_order():
    original = {"role": "lead", "_source_id": "source", "_source_order": "bad"}
    public, source_id, order = split_internal_fields(original)
    assert public == {"role": "lead"} and source_id == "source" and order > 1_000_000
    assert original == {"role": "lead", "_source_id": "source", "_source_order": "bad"}
