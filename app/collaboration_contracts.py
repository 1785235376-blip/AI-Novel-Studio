from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChapterCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class ChapterView(BaseModel):
    id: str
    novel_id: str
    number: int
    volume: int
    title: str
    word_count: int
    status: str
    content: str
    version: int
    document: dict[str, Any]
    updated_at: str


class StoryDatabaseView(BaseModel):
    resource: str
    items: list[dict[str, Any]]


class ScopeView(BaseModel):
    workspace_id: str
    project_id: str
    storyline_id: str
    branch_id: str


class ActorView(BaseModel):
    actor_id: str
    session_id: str
    client_id: str


class CollaborationBootstrap(BaseModel):
    actor: ActorView
    scope: ScopeView
    capabilities: dict[str, bool]


class MemberView(BaseModel):
    user_id: str
    display_name: str
    status: str
    membership_id: str


class MemberList(BaseModel):
    items: list[MemberView]


class PermissionSummary(BaseModel):
    actor_id: str
    domain: str
    capabilities: dict[str, bool]


class ChapterSummary(BaseModel):
    id: str
    novel_id: str
    number: int
    title: str
    version: int
    word_count: int
    status: str


class ChapterList(BaseModel):
    items: list[ChapterSummary]


class AuditView(BaseModel):
    id: str
    actor_id: str
    action: str
    target_type: str
    target_id: str
    timestamp: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditPage(BaseModel):
    items: list[AuditView]
    offset: int
    limit: int
    total: int


class RevisionSummary(BaseModel):
    version: int
    timestamp: str | None = None
    source: str
    operator: str
    reason: str | None = None
    actor_id: str | None = None
    session_id: str | None = None
    scope_type: str | None = None
    scope_id: str | None = None


class RevisionDetail(RevisionSummary):
    document: dict[str, Any]


class RevisionList(BaseModel):
    chapter_id: str
    current_version: int
    items: list[RevisionSummary]


class SnapshotSummary(BaseModel):
    id: str
    chapter_version_id: str
    context_pack_hash: str
    prompt_version: str
    model: str
    context_mode: str = "V1"
    generation_id: str | None = None
    created_at: str


class SnapshotDetail(SnapshotSummary):
    actor_id: str | None = None
    session_id: str | None = None
    scope_type: str | None = None
    scope_id: str | None = None
    ordering: list[str] = Field(default_factory=list)
    budget: dict[str, Any] = Field(default_factory=dict)


class SnapshotList(BaseModel):
    items: list[SnapshotSummary]


class GenerationSnapshotLink(BaseModel):
    generation_id: str
    context_snapshot_id: str | None = None


class ErrorBody(BaseModel):
    code: str
    detail: str | None = None
