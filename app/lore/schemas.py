from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import (EvidenceSourceType, EvidenceStatus, PrivacyLevel,
                    ProposalStatus, ProposalType, RelationRelevance,MemoryType,MemoryStatus,SnapshotScope)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LoreModel(BaseModel):
    model_config = ConfigDict(extra="allow", use_enum_values=True)
    schema_version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def known_schema(self):
        if self.schema_version != 1:
            raise ValueError(f"unsupported lore schema_version: {self.schema_version}")
        return self


class Evidence(LoreModel):
    id: str = Field(min_length=1)
    novel_id: str = Field(min_length=1)
    source_type: EvidenceSourceType
    source_id: str = Field(min_length=1)
    chapter_id: str | None = None
    chapter_version: int | None = Field(default=None, ge=1)
    generation_job_id: str | None = None
    excerpt: str | None = None
    locator: dict[str, Any]
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    privacy: PrivacyLevel
    status: EvidenceStatus = EvidenceStatus.ACTIVE
    invalidation_reason: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    @model_validator(mode="after")
    def source_contract(self):
        if self.source_type == EvidenceSourceType.CHAPTER_VERSION and (not self.chapter_id or self.chapter_version is None):
            raise ValueError("CHAPTER_VERSION evidence requires chapter_id and chapter_version")
        if self.source_type == EvidenceSourceType.GENERATION_JOB and not self.generation_job_id:
            raise ValueError("GENERATION_JOB evidence requires generation_job_id")
        if self.status == EvidenceStatus.INVALIDATED and not self.invalidation_reason:
            raise ValueError("INVALIDATED evidence requires invalidation_reason")
        return self


class LoreProposal(LoreModel):
    id: str = Field(min_length=1)
    novel_id: str = Field(min_length=1)
    proposal_type: ProposalType
    payload: dict[str, Any]
    approved_payload: dict[str, Any] | None = None
    status: ProposalStatus = ProposalStatus.PENDING
    source_chapter_id: str | None = None
    source_version: int | None = Field(default=None, ge=1)
    agent_name: str | None = None
    generation_job_id: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    @model_validator(mode="after")
    def state_contract(self):
        if self.status == ProposalStatus.PENDING:
            if self.approved_payload is not None or self.reviewed_by or self.reviewed_at:
                raise ValueError("PENDING proposal cannot contain review data")
        elif not self.reviewed_by or self.reviewed_at is None:
            raise ValueError("reviewed proposal requires reviewed_by and reviewed_at")
        if self.status == ProposalStatus.APPROVED and self.approved_payload is None:
            raise ValueError("APPROVED proposal requires approved_payload")
        if self.status == ProposalStatus.REJECTED and self.approved_payload is not None:
            raise ValueError("REJECTED proposal cannot contain approved_payload")
        if self.generation_job_id and not self.agent_name:
            raise ValueError("AI proposal requires agent_name")
        return self


class ProposalEvidenceRelation(LoreModel):
    proposal_id: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    relevance: RelationRelevance
    note: str | None = None
    created_at: datetime = Field(default_factory=utcnow)

class CharacterMemory(LoreModel):
    id:str=Field(min_length=1);novel_id:str=Field(min_length=1);character_id:str=Field(min_length=1);business_id:str=Field(min_length=1)
    memory_type:MemoryType;content:dict[str,Any];status:MemoryStatus=MemoryStatus.ACTIVE
    valid_from_chapter:int|None=Field(default=None,ge=1);valid_to_chapter:int|None=Field(default=None,ge=1)
    proposal_id:str=Field(min_length=1);supersedes_id:str|None=None;retraction_reason:str|None=None
    created_at:datetime=Field(default_factory=utcnow);updated_at:datetime=Field(default_factory=utcnow)
    @model_validator(mode="after")
    def memory_contract(self):
        if self.valid_from_chapter and self.valid_to_chapter and self.valid_to_chapter<self.valid_from_chapter:raise ValueError("valid_to_chapter must not precede valid_from_chapter")
        if self.status==MemoryStatus.RETRACTED and not self.retraction_reason:raise ValueError("RETRACTED memory requires retraction_reason")
        return self

class MemorySnapshot(LoreModel):
    id:str=Field(min_length=1);novel_id:str=Field(min_length=1);scope:SnapshotScope;scope_key:str=Field(min_length=1)
    range_start:int|None=Field(default=None,ge=1);range_end:int|None=Field(default=None,ge=1);memory:dict[str,Any]
    version:int=Field(ge=1);source_watermark:dict[str,Any];content_hash:str=Field(pattern=r"^[0-9a-f]{64}$")
    supersedes_id:str|None=None;created_by:str=Field(min_length=1);created_at:datetime=Field(default_factory=utcnow)
    @model_validator(mode="after")
    def snapshot_contract(self):
        if not self.source_watermark:raise ValueError("source_watermark is required")
        if self.range_start and self.range_end and self.range_end<self.range_start:raise ValueError("range_end must not precede range_start")
        return self
