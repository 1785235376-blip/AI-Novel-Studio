from __future__ import annotations

import hashlib
import json
from typing import Iterable

from .continuity import (
    Certainty, CharacterKnowledge, CharacterLocationState, ContinuityFinding,
    ContinuitySeverity, FindingStatus, KnowledgeState, TimelineEvent,
)


def _id(project: str, rule: str, subject: str, evidence: Iterable[str]) -> str:
    raw = json.dumps([project, rule, subject, sorted(evidence)], separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def timeline_order(events: list[TimelineEvent]) -> list[ContinuityFinding]:
    findings = []
    for event in events:
        if event.start_time and event.end_time and event.start_time > event.end_time:
            evidence = event.evidence_ids
            findings.append(ContinuityFinding(
                id=_id(event.project_id, "TIMELINE_ORDER_VIOLATION", event.id, evidence),
                project_id=event.project_id, finding_type="TIMELINE_ORDER_VIOLATION",
                severity=ContinuitySeverity.HIGH if event.certainty is Certainty.CONFIRMED else ContinuitySeverity.LOW,
                description=f"Event {event.id} has an end before its start.", rule_id="TIMELINE_ORDER_VIOLATION",
                subject_type="TIMELINE_EVENT", subject_id=event.id,
                source_chapter_version_id=event.source_chapter_version_id, evidence_ids=evidence,
            ))
    return findings


def location_conflicts(states: list[CharacterLocationState]) -> list[ContinuityFinding]:
    findings = []
    confirmed = [s for s in states if s.certainty is Certainty.CONFIRMED and s.state.value == "PRESENT" and s.location_id]
    for i, left in enumerate(confirmed):
        for right in confirmed[i + 1:]:
            if left.character_id == right.character_id and left.location_id != right.location_id and left.valid_from_event_id == right.valid_from_event_id:
                evidence = [*left.evidence_ids, *right.evidence_ids]
                findings.append(ContinuityFinding(id=_id(left.project_id, "CHARACTER_LOCATION_CONFLICT", left.character_id, evidence), project_id=left.project_id, finding_type="CHARACTER_LOCATION_CONFLICT", severity=ContinuitySeverity.HIGH, description=f"Character {left.character_id} has mutually exclusive confirmed locations.", rule_id="CHARACTER_LOCATION_CONFLICT", subject_type="CHARACTER", subject_id=left.character_id, evidence_ids=evidence))
    return findings


def knowledge_leaks(knowledge: list[CharacterKnowledge], used_subject_ids: set[str]) -> list[ContinuityFinding]:
    findings = []
    for item in knowledge:
        if item.subject_id in used_subject_ids and item.knowledge_state is KnowledgeState.UNKNOWN and not item.evidence_ids:
            findings.append(ContinuityFinding(id=_id(item.project_id, "CHARACTER_KNOWLEDGE_LEAK", item.id, []), project_id=item.project_id, finding_type="CHARACTER_KNOWLEDGE_LEAK", severity=ContinuitySeverity.LOW, description=f"Character {item.character_id} uses knowledge without acquisition evidence.", rule_id="CHARACTER_KNOWLEDGE_LEAK", subject_type="CHARACTER", subject_id=item.character_id))
    return findings
