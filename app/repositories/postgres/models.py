from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


privacy_level = Enum(
    "LOCAL_ONLY", "CLOUD_ALLOWED", "REDACT_BEFORE_CLOUD",
    name="privacy_level", create_type=False,
)
approval_status = Enum(
    "PENDING", "APPROVED", "REJECTED",
    name="approval_status", create_type=False,
)


class Base(DeclarativeBase):
    pass


class NovelModel(Base):
    __tablename__ = "novels"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class LocationModel(Base):
    __tablename__ = "locations"
    __table_args__ = (UniqueConstraint("novel_id", "slug"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    facts: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    privacy: Mapped[str] = mapped_column(privacy_level, nullable=False, default="CLOUD_ALLOWED")


class CharacterModel(Base):
    __tablename__ = "characters"
    __table_args__ = (UniqueConstraint("novel_id", "slug"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    age: Mapped[int | None] = mapped_column(Integer)
    life_status: Mapped[str] = mapped_column(Text, nullable=False, default="ALIVE")
    current_location_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"))
    facts: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    privacy: Mapped[str] = mapped_column(privacy_level, nullable=False, default="CLOUD_ALLOWED")


class RelationshipStateModel(Base):
    __tablename__ = "relationship_states"
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_character_id: Mapped[str] = mapped_column(Text, nullable=False)
    target_character_id: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class CanonModel(Base):
    __tablename__ = "canon_entries"
    __table_args__ = (UniqueConstraint("novel_id", "entity_type", "entity_id", "fact_key"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    fact_key: Mapped[str] = mapped_column(Text, nullable=False)
    fact_value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    privacy: Mapped[str] = mapped_column(privacy_level, nullable=False, default="CLOUD_ALLOWED")
    source: Mapped[str] = mapped_column(Text, nullable=False)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class StoryStateModel(Base):
    __tablename__ = "story_states"
    __table_args__ = (UniqueConstraint("novel_id", "chapter_number"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class TimelineModel(Base):
    __tablename__ = "timeline_events"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    event_time: Mapped[str] = mapped_column(Text, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    location_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    privacy: Mapped[str] = mapped_column(privacy_level, nullable=False, default="CLOUD_ALLOWED")


class ForeshadowingModel(Base):
    __tablename__ = "foreshadowing"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    planted_chapter: Mapped[int | None] = mapped_column(Integer)
    target_chapter: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="OPEN")
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class SecretModel(Base):
    __tablename__ = "secrets"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    earliest_reveal_chapter: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="ACTIVE")
    privacy: Mapped[str] = mapped_column(privacy_level, nullable=False, default="LOCAL_ONLY")


class ChapterModel(Base):
    __tablename__ = "chapters"
    __table_args__ = (UniqueConstraint("novel_id", "chapter_number"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    markdown_path: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str | None] = mapped_column(Text)
    workflow_status: Mapped[str] = mapped_column(Text, nullable=False, default="DRAFT")
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    document: Mapped[dict | None] = mapped_column(JSONB)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class ChapterSummaryModel(Base):
    __tablename__ = "chapter_summaries"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chapter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    structured_summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class PendingCanonModel(Base):
    __tablename__ = "pending_canon"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chapters.id", ondelete="SET NULL"))
    proposal: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(approval_status, nullable=False, default="PENDING")
    reviewed_by: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class DocumentVersionModel(Base):
    __tablename__ = "chapter_versions"
    __table_args__ = (UniqueConstraint("chapter_id", "version"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chapter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    document: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    operator: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    # Migration 015 owns the FK. Users are persisted by a lightweight SQL
    # repository rather than this ORM metadata, so keep the ORM mapping scalar.
    actor_id: Mapped[str | None] = mapped_column(Text)
    session_id: Mapped[str | None] = mapped_column(Text)
    scope_type: Mapped[str | None] = mapped_column(Text)
    scope_id: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="MANUAL_SAVE")


class GenerationJobModel(Base):
    __tablename__ = "generation_jobs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("novels.id", ondelete="CASCADE"))
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chapters.id", ondelete="SET NULL"))
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    request: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    draft_path: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(Text)
    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_code: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    result: Mapped[dict | None] = mapped_column(JSONB)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    # The table-level FK is owned by Migration 015.  Context snapshots use a
    # repository-local SQL table rather than an ORM model, so map the UUID
    # without duplicating that table in SQLAlchemy metadata.
    context_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
