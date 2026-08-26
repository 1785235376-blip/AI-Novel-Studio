from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any, Iterable

from pydantic import BaseModel, Field


class ContextPackCandidate(BaseModel):
    source_id: str
    source_type: str
    content: Any
    locality: str = "CLOUD_ALLOWED"
    character_ids: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    chapter_number: int | None = None
    source_priority: int | None = None


class ContextPackChunk(BaseModel):
    chunk_id: str
    source_id: str
    source_type: str
    content: Any
    estimated_tokens: int
    score: int
    selection_reasons: list[str] = Field(default_factory=list)


class ContextPackV2Result(BaseModel):
    enabled: bool
    chunks: list[ContextPackChunk] = Field(default_factory=list)
    estimated_tokens: int = 0
    token_budget: int = 0
    omitted_local_only: list[str] = Field(default_factory=list)
    deduplicated_count: int = 0
    truncated_sources: list[str] = Field(default_factory=list)


class ContextPackV2Builder:
    """Deterministic, persistence-free long-context selection.

    The caller owns the feature flag.  Passing ``enabled=False`` is a strict
    no-op and deliberately does not inspect candidate content.
    """

    SOURCE_PRIORITY = {
        "RECENT_CHAPTER": 0,
        "CHARACTER": 1,
        "TIMELINE": 2,
        "LORE": 3,
        "NARRATIVE": 4,
        "OTHER": 5,
    }
    SOURCE_ALLOCATION = {
        "RECENT_CHAPTER": 35,
        "CHARACTER": 25,
        "TIMELINE": 20,
        "LORE": 15,
        "NARRATIVE": 5,
        "OTHER": 5,
    }

    def __init__(self, token_budget: int = 2400, chunk_token_limit: int = 320):
        self.token_budget = max(0, int(token_budget))
        self.chunk_token_limit = max(1, int(chunk_token_limit))

    @staticmethod
    def _canonical(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

    @classmethod
    def estimate_tokens(cls, value: Any) -> int:
        return max(1, (len(cls._canonical(value)) + 3) // 4)

    @staticmethod
    def _terms(values: Iterable[str]) -> set[str]:
        terms: set[str] = set()
        for value in values:
            terms.update(x.casefold() for x in re.findall(r"[\w\-]+", str(value), re.UNICODE) if x)
        return terms

    @classmethod
    def extract_candidates(
        cls,
        *,
        characters: Iterable[dict[str, Any]] = (),
        lore: Iterable[dict[str, Any]] = (),
        timeline: Iterable[dict[str, Any]] = (),
        recent_chapters: Iterable[dict[str, Any]] = (),
    ) -> list[ContextPackCandidate]:
        candidates: list[ContextPackCandidate] = []
        for source_type, entries in (
            ("CHARACTER", characters), ("LORE", lore), ("TIMELINE", timeline),
            ("RECENT_CHAPTER", recent_chapters),
        ):
            for index, item in enumerate(entries):
                data = dict(item)
                source_id = str(data.get("id", data.get("source_id", f"{source_type.lower()}:{index}")))
                content = data.get("content", data.get("text", data))
                character_ids = data.get("character_ids", [])
                if data.get("character_id") is not None:
                    character_ids = [*character_ids, data["character_id"]]
                candidates.append(ContextPackCandidate(
                    source_id=source_id, source_type=source_type, content=content,
                    locality=str(data.get("locality", data.get("privacy_level", data.get("privacy", "CLOUD_ALLOWED")))),
                    character_ids=sorted({str(x) for x in character_ids}),
                    keywords=sorted({str(x) for x in data.get("keywords", [])}),
                    chapter_number=data.get("chapter_number", data.get("chapter")),
                ))
        return candidates

    def _chunks(self, candidate: ContextPackCandidate) -> list[tuple[str, Any]]:
        if not isinstance(candidate.content, str) or self.estimate_tokens(candidate.content) <= self.chunk_token_limit:
            return [(f"{candidate.source_type.upper()}:{candidate.source_id}:0", candidate.content)]
        # Character slicing is deterministic and Unicode-safe.  Whitespace is
        # retained so joining chunks reconstructs the exact admitted source.
        width = self.chunk_token_limit * 4
        return [(f"{candidate.source_type.upper()}:{candidate.source_id}:{i // width}", candidate.content[i:i + width])
                for i in range(0, len(candidate.content), width)]

    def build(
        self,
        candidates: Iterable[ContextPackCandidate | dict[str, Any]],
        *,
        enabled: bool,
        cloud: bool = False,
        query: str = "",
        character_ids: Iterable[str] = (),
        current_chapter: int | None = None,
    ) -> ContextPackV2Result:
        if not enabled:
            return ContextPackV2Result(enabled=False, token_budget=self.token_budget)

        parsed = [x if isinstance(x, ContextPackCandidate) else ContextPackCandidate.model_validate(x)
                  for x in candidates]
        # Privacy admission is intentionally the first content-sensitive pass.
        omitted = sorted({x.source_id for x in parsed if cloud and x.locality == "LOCAL_ONLY"})
        admitted = [x for x in parsed if not (cloud and x.locality == "LOCAL_ONLY")]
        query_terms = self._terms([query]); requested_characters = {str(x) for x in character_ids}
        ranked: list[tuple[tuple[Any, ...], ContextPackChunk]] = []
        seen: set[str] = set(); duplicate_count = 0
        for candidate in sorted(admitted, key=lambda x: (x.source_id, x.source_type, self._canonical(x.content))):
            source_type = candidate.source_type.upper()
            priority = candidate.source_priority if candidate.source_priority is not None else self.SOURCE_PRIORITY.get(source_type, self.SOURCE_PRIORITY["OTHER"])
            content_terms = self._terms([self._canonical(candidate.content), *candidate.keywords])
            overlap = len(query_terms & content_terms)
            character_match = bool(requested_characters & set(candidate.character_ids))
            recency = max(0, 100 - abs(current_chapter - candidate.chapter_number)) if current_chapter is not None and candidate.chapter_number is not None else 0
            score = 10_000 - priority * 1_000 + overlap * 100 + (500 if character_match else 0) + recency
            reasons = [f"SOURCE_PRIORITY:{source_type}"]
            if overlap: reasons.append("QUERY_RELEVANCE")
            if character_match: reasons.append("CHARACTER_RELEVANCE")
            if recency: reasons.append("CHAPTER_RECENCY")
            for chunk_id, content in self._chunks(candidate):
                canonical = self._canonical(content)
                if canonical in seen:
                    duplicate_count += 1; continue
                seen.add(canonical)
                chunk = ContextPackChunk(chunk_id=chunk_id, source_id=candidate.source_id,
                                         source_type=source_type, content=content,
                                         estimated_tokens=self.estimate_tokens(content), score=score,
                                         selection_reasons=reasons)
                ranked.append(((-score, priority, candidate.source_id, chunk_id, canonical), chunk))

        ranked.sort(key=lambda x: x[0])
        # First pass preserves source diversity; unused category capacity is
        # then pooled so small or absent categories cannot waste budget.
        caps = {kind: self.token_budget * percent // 100 for kind, percent in self.SOURCE_ALLOCATION.items()}
        used_by: dict[str, int] = defaultdict(int); selected: list[ContextPackChunk] = []; deferred = []
        total = 0
        for key, chunk in ranked:
            category = chunk.source_type if chunk.source_type in caps else "OTHER"
            if total + chunk.estimated_tokens <= self.token_budget and used_by[category] + chunk.estimated_tokens <= caps[category]:
                selected.append(chunk); total += chunk.estimated_tokens; used_by[category] += chunk.estimated_tokens
            else:
                deferred.append((key, chunk))
        for _, chunk in deferred:
            if total + chunk.estimated_tokens <= self.token_budget:
                selected.append(chunk); total += chunk.estimated_tokens
        selected_ids = {x.chunk_id for x in selected}
        truncated = sorted({chunk.source_id for _, chunk in ranked if chunk.chunk_id not in selected_ids})
        selected.sort(key=lambda x: next(key for key, chunk in ranked if chunk.chunk_id == x.chunk_id))
        return ContextPackV2Result(enabled=True, chunks=selected, estimated_tokens=total,
                                   token_budget=self.token_budget, omitted_local_only=omitted,
                                   deduplicated_count=duplicate_count, truncated_sources=truncated)
