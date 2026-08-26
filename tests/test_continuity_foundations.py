from app.lore.continuity import (
    CanonDependency, CanonDependencyType, CharacterKnowledge, Certainty,
    ContinuityFinding, ContinuitySeverity, FindingStatus, KnowledgeState,
    RelationshipState, TimelineEvent,
)


def test_typed_foundations_preserve_provenance_and_story_time():
    event = TimelineEvent(project_id="p", event_type="DISCOVERY", title="Discovery", start_time="day-3")
    assert event.start_time == "day-3"
    assert event.certainty is Certainty.UNKNOWN
    assert event.evidence_ids == []


def test_relationship_is_directed_and_dependency_is_typed():
    relation = RelationshipState(project_id="p", source_character_id="a", target_character_id="b", relationship_type="TRUSTS")
    dependency = CanonDependency(project_id="p", source_canon_id="a", target_canon_id="b", dependency_type=CanonDependencyType.REQUIRES)
    assert (relation.source_character_id, relation.target_character_id) == ("a", "b")
    assert dependency.dependency_type is CanonDependencyType.REQUIRES


def test_unknown_knowledge_is_not_false_and_findings_are_advisory():
    knowledge = CharacterKnowledge(project_id="p", character_id="a", subject_type="FACT", subject_id="f")
    finding = ContinuityFinding(project_id="p", finding_type="CHARACTER_KNOWLEDGE_LEAK", severity=ContinuitySeverity.LOW, description="possible leak")
    assert knowledge.knowledge_state is KnowledgeState.UNKNOWN
    assert finding.status is FindingStatus.OPEN
    assert finding.evidence_ids == []
