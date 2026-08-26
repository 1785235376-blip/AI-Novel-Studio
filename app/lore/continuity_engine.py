from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .continuity import CharacterKnowledge, CharacterLocationState, ContinuityFinding, ContinuitySeverity, RelationshipState, TimelineEvent, Certainty
from .continuity_rules import _id, knowledge_leaks, location_conflicts, timeline_order


@dataclass
class ContinuityRuleContext:
    project_id: str
    events: list[TimelineEvent] = field(default_factory=list)
    locations: list[CharacterLocationState] = field(default_factory=list)
    relationships: list[RelationshipState] = field(default_factory=list)
    knowledge: list[CharacterKnowledge] = field(default_factory=list)
    used_subject_ids: set[str] = field(default_factory=set)
    travel_times: dict[tuple[str, str], int] = field(default_factory=dict)
    canon_facts: dict[str, object] = field(default_factory=dict)
    asserted_facts: dict[str, object] = field(default_factory=dict)
    evidence_required_subjects: set[str] = field(default_factory=set)
    evidence_present_subjects: set[str] = field(default_factory=set)


class RuleRegistry:
    def __init__(self): self._rules: dict[str, Callable[[ContinuityRuleContext], list[ContinuityFinding]]] = {}
    def register(self, rule_id, evaluator):
        if rule_id in self._rules: raise ValueError(f"Duplicate continuity rule: {rule_id}")
        self._rules[rule_id]=evaluator
    @property
    def rule_ids(self): return tuple(sorted(self._rules))
    def evaluate(self, context):
        findings=[]
        for rule_id in self.rule_ids: findings.extend(self._rules[rule_id](context))
        return findings


def impossible_travel(ctx):
    findings=[]; states=sorted([s for s in ctx.locations if s.certainty is Certainty.CONFIRMED and s.location_id and s.valid_from_event_id],key=lambda s:s.valid_from_event_id)
    for left,right in zip(states,states[1:]):
        key=(left.location_id,right.location_id); required=ctx.travel_times.get(key)
        if left.character_id==right.character_id and required is not None and left.valid_to_event_id and left.valid_to_event_id==right.valid_from_event_id and required>0:
            evidence=[*left.evidence_ids,*right.evidence_ids]
            findings.append(ContinuityFinding(id=_id(ctx.project_id,"IMPOSSIBLE_TRAVEL",left.character_id,evidence),project_id=ctx.project_id,finding_type="IMPOSSIBLE_TRAVEL",severity=ContinuitySeverity.HIGH,description=f"Character {left.character_id} has no available travel interval.",rule_id="IMPOSSIBLE_TRAVEL",subject_type="CHARACTER",subject_id=left.character_id,evidence_ids=evidence))
    return findings


def relationship_conflicts(ctx):
    findings=[]
    for i,left in enumerate(ctx.relationships):
        for right in ctx.relationships[i+1:]:
            if left.source_character_id==right.source_character_id and left.target_character_id==right.target_character_id and left.valid_from_event_id==right.valid_from_event_id and left.relationship_type!=right.relationship_type and left.certainty is Certainty.CONFIRMED and right.certainty is Certainty.CONFIRMED:
                evidence=[*left.evidence_ids,*right.evidence_ids]
                findings.append(ContinuityFinding(id=_id(ctx.project_id,"RELATIONSHIP_STATE_CONFLICT",left.source_character_id+":"+left.target_character_id,evidence),project_id=ctx.project_id,finding_type="RELATIONSHIP_STATE_CONFLICT",severity=ContinuitySeverity.HIGH,description="Directed relationship has conflicting confirmed states.",rule_id="RELATIONSHIP_STATE_CONFLICT",subject_type="RELATIONSHIP",subject_id=left.source_character_id+":"+left.target_character_id,evidence_ids=evidence))
    return findings


def canon_rule_conflicts(ctx):
    findings=[]
    for subject,value in ctx.asserted_facts.items():
        if subject in ctx.canon_facts and ctx.canon_facts[subject] != value:
            findings.append(ContinuityFinding(id=_id(ctx.project_id,"CANON_RULE_CONFLICT",subject,[]),project_id=ctx.project_id,finding_type="CANON_RULE_CONFLICT",severity=ContinuitySeverity.HIGH,description=f"Assertion for {subject} contradicts authoritative Canon.",rule_id="CANON_RULE_CONFLICT",subject_type="CANON_FACT",subject_id=subject))
    return findings


def false_belief_as_fact(ctx):
    findings=[]
    for item in ctx.knowledge:
        if item.knowledge_state.value=="FALSE_BELIEF" and item.subject_id in ctx.asserted_facts:
            findings.append(ContinuityFinding(id=_id(ctx.project_id,"FALSE_BELIEF_AS_FACT",item.id,item.evidence_ids),project_id=ctx.project_id,finding_type="FALSE_BELIEF_AS_FACT",severity=ContinuitySeverity.MEDIUM,description=f"Character {item.character_id}'s false belief is asserted as fact.",rule_id="FALSE_BELIEF_AS_FACT",subject_type="CHARACTER",subject_id=item.character_id,evidence_ids=item.evidence_ids))
    return findings


def missing_evidence(ctx):
    findings=[]
    for subject in sorted(ctx.evidence_required_subjects-ctx.evidence_present_subjects):
        findings.append(ContinuityFinding(id=_id(ctx.project_id,"MISSING_EVIDENCE",subject,[]),project_id=ctx.project_id,finding_type="MISSING_EVIDENCE",severity=ContinuitySeverity.LOW,description=f"Required evidence is unavailable for {subject}.",rule_id="MISSING_EVIDENCE",subject_type="FACT",subject_id=subject))
    return findings


registry=RuleRegistry()
registry.register("CANON_RULE_CONFLICT",canon_rule_conflicts)
registry.register("CHARACTER_KNOWLEDGE_LEAK",lambda c:knowledge_leaks(c.knowledge,c.used_subject_ids))
registry.register("CHARACTER_LOCATION_CONFLICT",lambda c:location_conflicts(c.locations))
registry.register("IMPOSSIBLE_TRAVEL",impossible_travel)
registry.register("FALSE_BELIEF_AS_FACT",false_belief_as_fact)
registry.register("MISSING_EVIDENCE",missing_evidence)
registry.register("RELATIONSHIP_STATE_CONFLICT",relationship_conflicts)
registry.register("TIMELINE_ORDER_VIOLATION",lambda c:timeline_order(c.events))
