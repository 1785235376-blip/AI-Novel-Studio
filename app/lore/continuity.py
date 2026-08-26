from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Certainty(StrEnum):
    CONFIRMED = "CONFIRMED"
    ESTIMATED = "ESTIMATED"
    UNKNOWN = "UNKNOWN"


class LocationState(StrEnum):
    PRESENT = "PRESENT"
    IN_TRANSIT = "IN_TRANSIT"
    DEPARTED = "DEPARTED"
    UNKNOWN = "UNKNOWN"


class KnowledgeState(StrEnum):
    KNOWN = "KNOWN"
    BELIEVED = "BELIEVED"
    SUSPECTED = "SUSPECTED"
    FALSE_BELIEF = "FALSE_BELIEF"
    UNKNOWN = "UNKNOWN"


class CanonDependencyType(StrEnum):
    DEPENDS_ON = "DEPENDS_ON"
    REQUIRES = "REQUIRES"
    CONFLICTS_WITH = "CONFLICTS_WITH"
    EXCLUDES = "EXCLUDES"


class ContinuitySeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class FindingStatus(StrEnum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    DISMISSED = "DISMISSED"
    RESOLVED = "RESOLVED"


class TimelineEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    event_type: str
    title: str
    description: str = ""
    start_time: str | None = None
    end_time: str | None = None
    sequence_index: int | None = None
    location_id: str | None = None
    certainty: Certainty = Certainty.UNKNOWN
    status: str = "ACTIVE"
    source_chapter_version_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class CharacterLocationState(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    character_id: str
    location_id: str | None = None
    valid_from_event_id: str | None = None
    valid_to_event_id: str | None = None
    state: LocationState = LocationState.UNKNOWN
    certainty: Certainty = Certainty.UNKNOWN
    evidence_ids: list[str] = Field(default_factory=list)
    source_chapter_version_id: str | None = None


class RelationshipState(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    source_character_id: str
    target_character_id: str
    relationship_type: str
    status: str = "ACTIVE"
    valid_from_event_id: str | None = None
    valid_to_event_id: str | None = None
    description: str = ""
    certainty: Certainty = Certainty.UNKNOWN
    evidence_ids: list[str] = Field(default_factory=list)
    source_chapter_version_id: str | None = None
    created_at: datetime = Field(default_factory=_now)


class CanonDependency(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    source_canon_id: str
    target_canon_id: str
    dependency_type: CanonDependencyType
    description: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)


class CharacterKnowledge(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    character_id: str
    subject_type: str
    subject_id: str
    knowledge_state: KnowledgeState = KnowledgeState.UNKNOWN
    learned_at_event_id: str | None = None
    source_character_id: str | None = None
    source_chapter_version_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    certainty: Certainty = Certainty.UNKNOWN
    created_at: datetime = Field(default_factory=_now)


class ContinuityFinding(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    finding_type: str
    severity: ContinuitySeverity
    status: FindingStatus = FindingStatus.OPEN
    description: str
    rule_id: str | None = None
    subject_type: str | None = None
    subject_id: str | None = None
    source_chapter_version_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)
    resolved_at: datetime | None = None

