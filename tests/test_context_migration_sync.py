from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from app.migrate_file_to_postgres import (
    FORESHADOWING_NAMESPACE, SECRET_NAMESPACE, TIMELINE_NAMESPACE,
    migrate, stable_source_uuid,
)
from app.repository import FileRepository
from app.repositories.postgres.models import (
    ChapterModel, ChapterSummaryModel, CharacterModel, ForeshadowingModel, LocationModel,
    NovelModel, SecretModel, StoryStateModel, TimelineModel,
)
from app.repositories.postgres.session import Database


DATABASE_URL = os.getenv("TEST_POSTGRES_DATABASE_URL", "")


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


@pytest.mark.skipif(not DATABASE_URL, reason="NOT VERIFIED: TEST_POSTGRES_DATABASE_URL is not configured")
def test_context_migration_sync_is_complete_updatable_and_idempotent(tmp_path):
    database = Database(DATABASE_URL)
    if not database.health_check(): pytest.skip("NOT VERIFIED: PostgreSQL is unavailable")
    repository = FileRepository(tmp_path)
    novel_id = f"phase2-{uuid.uuid4().hex[:10]}"
    repository.create_novel({"id": novel_id, "title": "Phase 2 Migration", "genre": "Test"})
    repository.create_chapter(novel_id, {"title": "One", "content": "Body"})
    root = repository.novels / novel_id
    write_json(root / "locations/locations.json", [{"id": "port", "name": "Port", "travel_hours": {"tower": 2}, "privacy_level": "CLOUD_ALLOWED"}])
    write_json(root / "characters/characters.json", [{"id": "hero", "name": "Hero", "age": 24, "status": "ALIVE", "role": "lead", "traits": ["careful"], "current_location": "port", "privacy_level": "CLOUD_ALLOWED"}])
    write_json(root / "timeline/events.json", [{"id": "arrival", "sequence": 1, "time": "day one", "title": "Arrival"}])
    write_json(root / "secrets.json", [{"id": "hidden-name", "title": "Identity", "content": "Secret", "earliest_reveal_chapter": 10, "status": "ACTIVE", "privacy_level": "LOCAL_ONLY"}])
    write_json(root / "foreshadowing.json", [{"id": "rust-key", "title": "Rust key", "status": "OPEN", "planted_chapter": 1}])
    write_json(root / "story_state.json", {"volume": 1, "chapter": 1, "active_characters": ["hero"], "current_location": "port"})
    write_json(root / "style/profile.json", {"pov": "third", "pace": "slow"})
    write_json(root / "summaries/index.json", [{"chapter": 1, "summary": "Hero arrived."}])
    first = migrate(tmp_path, DATABASE_URL, tmp_path / "first.json")
    assert not first["failed"] and not first["conflicts"]

    with database.session() as session:
        novel = session.scalar(select(NovelModel).where(NovelModel.slug == novel_id)); assert novel is not None
        assert novel.metadata_json["style_profile"] == {"pov": "third", "pace": "slow"}
        location = session.scalar(select(LocationModel).where(LocationModel.novel_id == novel.id)); assert location.facts["_source_order"] == 0
        character = session.scalar(select(CharacterModel).where(CharacterModel.novel_id == novel.id)); assert character.facts["role"] == "lead" and character.current_location_id == location.id
        assert session.get(TimelineModel, stable_source_uuid(TIMELINE_NAMESPACE, novel_id, "arrival")).details["_source_id"] == "arrival"
        secret_id = stable_source_uuid(SECRET_NAMESPACE, novel_id, "hidden-name"); assert session.get(SecretModel, secret_id).content == "Secret"
        assert novel.metadata_json["context_source_ids"]["secrets"][str(secret_id)] == {"id": "hidden-name", "order": 0}
        assert session.get(ForeshadowingModel, stable_source_uuid(FORESHADOWING_NAMESPACE, novel_id, "rust-key")).details["_source_id"] == "rust-key"
        assert session.scalar(select(StoryStateModel).where(StoryStateModel.novel_id == novel.id, StoryStateModel.chapter_number == 1)).state["current_location"] == "port"
        assert session.scalar(select(ChapterSummaryModel).join(ChapterModel).where(ChapterModel.novel_id == novel.id)).summary == "Hero arrived."

    second = migrate(tmp_path, DATABASE_URL, tmp_path / "second.json")
    assert all(not second[action] for action in ("imported", "updated", "conflicts", "failed"))
    assert second["skipped"]

    write_json(root / "characters/characters.json", [{"id": "hero", "name": "Hero", "age": 24, "status": "ALIVE", "role": "captain", "traits": ["careful"], "current_location": "port", "privacy_level": "CLOUD_ALLOWED"}])
    write_json(root / "story_state.json", {"volume": 1, "chapter": 1, "active_characters": ["hero"], "current_location": "tower"})
    write_json(root / "style/profile.json", {"pov": "third", "pace": "fast"})
    write_json(root / "summaries/index.json", [{"chapter": 1, "summary": "Hero became captain."}])
    third = migrate(tmp_path, DATABASE_URL, tmp_path / "third.json")
    updated_tables = {item["table"] for item in third["updated"]}
    assert {"novels", "characters", "story_states", "chapter_summaries"} <= updated_tables

    with database.session() as session:
        novel = session.scalar(select(NovelModel).where(NovelModel.slug == novel_id))
        session.delete(novel)
