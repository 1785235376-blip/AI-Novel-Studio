from __future__ import annotations

import json
import uuid
from typing import Any

from pydantic import BaseModel, Field

from .context_intelligence import (
    ContextIntent,
    ContextIntentAnalyzer,
    ContextValidationReport,
    MemoryRetrievalReason,
    detect_conflicts,
    priority_score,
)
from ..narrative_context import NarrativeContextView
from ..context_policy import ContextPolicyResult


class LoreMemoryView(BaseModel):
    short_memory: list[dict[str, Any]] = Field(default_factory=list)
    medium_memory: list[dict[str, Any]] = Field(default_factory=list)
    long_memory: list[dict[str, Any]] = Field(default_factory=list)
    evidence_summary: list[dict[str, Any]] = Field(default_factory=list)
    memory_version: dict[str, Any] = Field(default_factory=dict)


class ContextEnvelope(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    base_context: dict[str, Any]
    lore_memory: LoreMemoryView
    intent: ContextIntent
    retrieval_reason: list[MemoryRetrievalReason] = Field(default_factory=list)
    privacy_decisions: list[dict[str, Any]] = Field(default_factory=list)
    validation_report: ContextValidationReport | None = None
    token_budget: int = 2000
    narrative_context: NarrativeContextView | None = None
    context_policy: ContextPolicyResult | None = None


class LoreContextBuilder:
    def __init__(self, lore_service, token_budget: int = 2000):
        self.lore = lore_service
        self.repository = lore_service.repository
        self.token_budget = token_budget

    def build(
        self,
        base_context: dict,
        chapter: int,
        cloud: bool = False,
        instruction: str = "",
        operation: str = "",
    ) -> ContextEnvelope:
        intent = ContextIntentAnalyzer().analyze(
            base_context["novel_id"], instruction, base_context, operation
        )
        character_ids = intent.characters or [
            item.get("id") for item in base_context.get("characters", []) if item.get("id")
        ]
        candidates: dict[str, tuple[dict, float, list[dict]]] = {}
        for memory in self.repository.list_memories(base_context["novel_id"], "ACTIVE"):
            if memory.get("character_id") not in character_ids:
                continue
            start, end = memory.get("valid_from_chapter"), memory.get("valid_to_chapter")
            if (start is not None and start > chapter) or (end is not None and end < chapter):
                continue
            proposal = self.repository.get_proposal(memory["proposal_id"])
            relations = self.repository.list_proposal_evidence(memory["proposal_id"])
            evidence = [self.repository.get_evidence(item["evidence_id"]) for item in relations]
            score = priority_score(memory, intent, chapter, proposal.get("confidence"))
            candidates[memory["id"]] = (memory, score, evidence)

        ordered = sorted(candidates.values(), key=lambda item: (-item[1], item[0]["id"]))
        short: list[dict] = []
        medium: list[dict] = []
        evidence_summary: list[dict] = []
        reasons: list[MemoryRetrievalReason] = []
        privacy: list[dict] = []
        used = 0
        for memory, score, evidence in ordered:
            if cloud and any(item["privacy"] == "LOCAL_ONLY" for item in evidence):
                privacy.append({"memory_id": memory["id"], "decision": "OMITTED_LOCAL_ONLY"})
                continue
            cost = max(1, len(json.dumps(memory, ensure_ascii=False)) // 4)
            if used + cost > self.token_budget:
                privacy.append({"memory_id": memory["id"], "decision": "OMITTED_TOKEN_BUDGET"})
                continue
            used += cost
            source_ids = []
            for item in evidence:
                summary = {
                    "evidence_id": item["id"],
                    "source_type": item["source_type"],
                    "chapter_id": item.get("chapter_id"),
                    "chapter_version": item.get("chapter_version"),
                    "privacy": item["privacy"],
                }
                if not cloud and item.get("excerpt"):
                    summary["excerpt"] = item["excerpt"]
                elif item["privacy"] == "REDACT_BEFORE_CLOUD":
                    summary["redacted"] = True
                evidence_summary.append(summary)
                source_ids.append(item["id"])
            target = short if memory.get("valid_from_chapter") is not None and memory["valid_from_chapter"] >= max(1, chapter - 2) else medium
            target.append(memory)
            reasons.append(MemoryRetrievalReason(
                memory_id=memory["id"],
                reason_type="DIRECT_CHARACTER",
                explanation=f"Character {memory['character_id']} is relevant to the current writing intent.",
                confidence=score,
                related_entities=[memory["character_id"], *intent.locations],
                source_ids=source_ids,
                priority_score=score,
            ))

        novel_id = base_context["novel_id"]
        volume = base_context.get("volume", 1)
        volume_snapshot = self.repository.get_latest_snapshot(novel_id, "VOLUME", f"volume:{volume}")
        novel_snapshot = self.repository.get_latest_snapshot(novel_id, "NOVEL", "novel")
        long: list[dict] = []
        if not cloud:
            if volume_snapshot:
                medium.append(volume_snapshot["memory"])
            if novel_snapshot:
                long.append(novel_snapshot["memory"])
        elif volume_snapshot or novel_snapshot:
            privacy.append({"scope": "snapshots", "decision": "OMITTED_UNCLASSIFIED_DERIVED_MEMORY"})
        memory_version = {
            "active_memory_ids": [item["id"] for item in [*short, *medium] if "id" in item],
            "volume_snapshot": volume_snapshot["version"] if volume_snapshot else None,
            "novel_snapshot": novel_snapshot["version"] if novel_snapshot else None,
        }
        view = LoreMemoryView(
            short_memory=short,
            medium_memory=medium,
            long_memory=long,
            evidence_summary=evidence_summary,
            memory_version=memory_version,
        )
        envelope = ContextEnvelope(
            base_context=base_context,
            lore_memory=view,
            intent=intent,
            retrieval_reason=reasons,
            privacy_decisions=privacy,
            token_budget=self.token_budget,
        )
        envelope.validation_report = detect_conflicts(
            envelope.id, base_context.get("canon", []), [*short, *medium]
        )
        return envelope
