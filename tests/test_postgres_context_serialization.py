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
                                         "title": "Meeting", "note": "extra", "privacy_level": "CLOUD_ALLOWED"}
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
                                             "hint": "door", "privacy_level": "LOCAL_ONLY", "privacy_status": "UNKNOWN"}
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


def test_migrated_missing_privacy_shape_never_hides_restrictive_policy():
    for serializer, values in (
        (serialize_character, {"age": 31, "life_status": "ALIVE"}),
        (serialize_location, {}),
    ):
        item = model(slug="legacy", name="Legacy", privacy="CLOUD_ALLOWED",
                     facts={"_source_privacy_present": False}, **values)
        assert serializer(item)["privacy_level"] == "LOCAL_ONLY"
        assert serializer(item)["privacy_status"] == "UNKNOWN"
        assert "_source_privacy_present" not in serializer(item)
        for privacy in ("LOCAL_ONLY", "REDACT_BEFORE_CLOUD"):
            item.privacy = privacy
            assert serializer(item)["privacy_level"] == "LOCAL_ONLY"
        item.facts = {"_source_privacy_present": True, "privacy_level": "CLOUD_ALLOWED"}
        assert serializer(item)["privacy_level"] == "REDACT_BEFORE_CLOUD"


def test_location_status_survives_without_unmasking_reserved_fields():
    item = model(slug="port", name="Port", privacy="LOCAL_ONLY",
                 facts={"status": "INACCESSIBLE", "id": "forged", "name": "forged",
                        "privacy_level": "CLOUD_ALLOWED", "_source_id": "forged"})
    assert serialize_location(item) == {
        "id": "port", "name": "Port", "status": "INACCESSIBLE", "privacy_level": "LOCAL_ONLY"}


def test_migrated_secret_preserves_type_and_absent_title_without_overriding_columns():
    item = model(id=uuid.uuid4(), title="legacy", content="secret", earliest_reveal_chapter=99,
                 status="ACTIVE", privacy="LOCAL_ONLY")
    mapping = {str(item.id): {"id": "legacy", "order": 0, "title_present": False,
        "extensions": {"type": "secret", "id": "forged", "content": "forged",
                       "privacy_level": "CLOUD_ALLOWED", "status": "CORRUPT"}}}
    assert serialize_secret(item, mapping) == {
        "id": "legacy", "type": "secret", "content": "secret", "earliest_reveal_chapter": 99,
        "status": "ACTIVE", "privacy_level": "LOCAL_ONLY"}
    public = serialize_secret(item, mapping, public=True)
    assert public["content"] is None and public["visibility"] == "LOCAL_ONLY"


def test_writing_goal_update_and_read_keep_only_allowed_metadata(monkeypatch):
    from contextlib import contextmanager
    from datetime import datetime, timezone
    from app.repositories.postgres import novel as repository_module

    stamp = datetime.now(timezone.utc)
    record = model(slug="novel", title="Novel", created_at=stamp, updated_at=stamp,
                   metadata_json={"genre": "Mystery", "style_profile": {"pov": "first"}})
    class Session:
        def flush(self):
            pass
    class Database:
        @contextmanager
        def session(self):
            yield Session()
    monkeypatch.setattr(repository_module, "novel_or_raise", lambda session, nid: record)
    repository = repository_module.PostgresNovelRepository(Database())
    goal = {"target_words": 1000, "target_chapters": 10, "deadline": "2027-01-01"}
    updated = repository.update("novel", {"writing_goal": goal, "id": "forged", "owner_id": "forged"})
    assert updated["writing_goal"] == goal
    assert repository.get("novel")["writing_goal"] == goal
    assert updated["id"] == "novel" and "owner_id" not in updated
    assert record.metadata_json == {"genre": "Mystery", "style_profile": {"pov": "first"}, "writing_goal": goal}


def test_sample_migration_preserves_raw_context_shape(tmp_path):
    from app.migrate_file_to_postgres import _sync_novel, _sync_characters, _sync_locations, _sync_secrets
    from app.repository import FileRepository, read_json
    from app.repositories.postgres.models import CharacterModel, LocationModel, SecretModel
    from sample_novel_fixture import install_sample_novel

    root = install_sample_novel(tmp_path)
    class Session:
        def __init__(self):
            self.rows = []
        def scalar(self, query):
            return None
        def get(self, kind, key):
            return None
        def add(self, item):
            if item.id is None:
                item.id = uuid.uuid4()
            self.rows.append(item)
        def flush(self):
            pass
    session = Session()
    report = {key: [] for key in ("imported", "updated", "skipped", "conflicts", "failed")}
    novel = _sync_novel(session, FileRepository(tmp_path), {"id": "sample_novel"}, report)
    locations = _sync_locations(session, root, novel, report)
    _sync_characters(session, root, novel, locations, report)
    _sync_secrets(session, root, novel, report)
    mapping = novel.metadata_json["context_source_ids"]["secrets"]
    for kind, serializer, source in (
        (CharacterModel, serialize_character, "characters/characters.json"),
        (LocationModel, serialize_location, "locations/locations.json"),
        (SecretModel, lambda row: serialize_secret(row, mapping), "secrets.json"),
    ):
        assert [serializer(row) for row in session.rows if isinstance(row, kind)] == [
            {**item, "privacy_level": item.get("privacy_level", "LOCAL_ONLY"),
             **({"privacy_status": "UNKNOWN"} if "privacy_level" not in item else {})}
            for item in read_json(root / source, [])
        ]
    assert not report["conflicts"] and not report["failed"]
