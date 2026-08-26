from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ContextIntentType(StrEnum):
    CHAPTER_WRITE = "CHAPTER_WRITE"
    CHAPTER_REWRITE = "CHAPTER_REWRITE"
    CHAPTER_REVIEW = "CHAPTER_REVIEW"
    CONTINUATION = "CONTINUATION"
    WORLD_BUILDING = "WORLD_BUILDING"
    CHARACTER_DEVELOPMENT = "CHARACTER_DEVELOPMENT"


class ContextIntent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    intent_type: ContextIntentType
    characters: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    factions: list[str] = Field(default_factory=list)
    required_memory_types: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)


class MemoryRetrievalReason(BaseModel):
    memory_id: str
    reason_type: str
    explanation: str
    confidence: float = Field(ge=0, le=1)
    related_entities: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    priority_score: float = Field(ge=0, le=1)


class ContextConflict(BaseModel):
    severity: str
    conflict_type: str
    description: str
    evidence_ids: list[str] = Field(default_factory=list)


class ContextValidationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    context_id: str
    conflicts: list[ContextConflict] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)


class ContextSnapshot(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chapter_version_id: str
    context_pack_hash: str
    canon_version: str
    memory_version: dict[str, Any]
    character_state_version: str
    timeline_version: str
    prompt_version: str
    model: str
    actor_id: str | None = None
    session_id: str | None = None
    scope_type: Literal["WORKSPACE", "PROJECT", "STORYLINE", "BRANCH"] | None = None
    scope_id: str | None = None
    context_mode: Literal["V1", "V2"] = "V1"
    ordering: list[str] = Field(default_factory=list)
    budget: dict[str, Any] = Field(default_factory=dict)
    generation_id: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ContextIntentAnalyzer:
    OPERATION_MAP = {
        "rewrite": ContextIntentType.CHAPTER_REWRITE,
        "review": ContextIntentType.CHAPTER_REVIEW,
        "continue": ContextIntentType.CONTINUATION,
        "world_building": ContextIntentType.WORLD_BUILDING,
        "character_development": ContextIntentType.CHARACTER_DEVELOPMENT,
    }

    def analyze(self, project_id: str, instruction: str, sources: dict, operation: str = "") -> ContextIntent:
        intent_type = self.OPERATION_MAP.get(operation, ContextIntentType.CHAPTER_WRITE)
        if not operation:
            lowered = instruction.lower()
            if any(word in lowered for word in ("rewrite", "改写", "重写")):
                intent_type = ContextIntentType.CHAPTER_REWRITE
            elif any(word in lowered for word in ("review", "检查", "审阅")):
                intent_type = ContextIntentType.CHAPTER_REVIEW
            elif any(word in lowered for word in ("continue", "续写", "继续")):
                intent_type = ContextIntentType.CONTINUATION
            elif any(word in lowered for word in ("world", "世界观", "设定")):
                intent_type = ContextIntentType.WORLD_BUILDING
            elif any(word in lowered for word in ("character", "人物成长", "角色发展")):
                intent_type = ContextIntentType.CHARACTER_DEVELOPMENT

        def resolve(items: list[dict]) -> list[str]:
            found = []
            folded = instruction.casefold()
            for item in items:
                names = [str(item.get("id", "")), str(item.get("name", ""))]
                if any(name and name.casefold() in folded for name in names):
                    found.append(str(item.get("id") or item.get("name")))
            return found

        characters = resolve(sources.get("characters", []))
        locations = resolve(sources.get("locations", []))
        active = sources.get("story_state", {}).get("active_characters", [])
        characters = list(dict.fromkeys([*characters, *active]))
        required = ["CHARACTER_MEMORY"] if characters else []
        if locations:
            required.append("LOCATION_CONTEXT")
        if intent_type in {ContextIntentType.CHAPTER_WRITE, ContextIntentType.CONTINUATION}:
            required.extend(["TIMELINE", "CANON", "SECRET"])
        return ContextIntent(
            project_id=project_id,
            intent_type=intent_type,
            characters=characters,
            locations=locations,
            required_memory_types=list(dict.fromkeys(required)),
        )


def priority_score(memory: dict, intent: ContextIntent, chapter: int, confidence: float | None) -> float:
    entity = 1.0 if memory.get("character_id") in intent.characters else 0.35
    start = memory.get("valid_from_chapter")
    distance = abs(chapter - start) if isinstance(start, int) else 10
    timeline = max(0.0, 1.0 - min(distance, 20) / 20)
    plot = 1.0 if memory.get("memory_type") in {"EXPERIENCE", "STATE_CHANGE", "RELATIONSHIP_CHANGE"} else 0.5
    certainty = 0.5 if confidence is None else float(confidence)
    recency = max(0.0, 1.0 - min(distance, 50) / 50)
    return round(entity * .35 + timeline * .25 + plot * .20 + certainty * .10 + recency * .10, 6)


def detect_conflicts(context_id: str, canon: list[dict], memories: list[dict]) -> ContextValidationReport:
    conflicts: list[ContextConflict] = []
    canon_text = json.dumps(canon, ensure_ascii=False).casefold()
    opposites = [
        (("dead", "死亡", "已死"), ("alive", "存活", "活着"), "CHARACTER_STATE"),
        (("broken leg", "腿骨折", "无法行走"), ("running", "奔跑", "跑步"), "CHARACTER_STATE"),
    ]
    for memory in memories:
        memory_text = json.dumps(memory.get("content", {}), ensure_ascii=False).casefold()
        for left, right, conflict_type in opposites:
            if (any(x in canon_text for x in left) and any(x in memory_text for x in right)) or (
                any(x in canon_text for x in right) and any(x in memory_text for x in left)
            ):
                conflicts.append(ContextConflict(
                    severity="HIGH",
                    conflict_type=conflict_type,
                    description=f"Memory {memory['id']} may contradict approved canon.",
                    evidence_ids=[memory["id"]],
                ))
    return ContextValidationReport(context_id=context_id, conflicts=conflicts)
