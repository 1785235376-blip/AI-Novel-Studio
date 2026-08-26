from app.lore.continuity import Certainty, CharacterKnowledge, CharacterLocationState, KnowledgeState, LocationState, TimelineEvent
from app.lore.continuity_rules import knowledge_leaks, location_conflicts, timeline_order


def test_timeline_order_rule_is_deterministic():
    event = TimelineEvent(id="e", project_id="p", event_type="x", title="x", start_time="day-5", end_time="day-3", certainty=Certainty.CONFIRMED, evidence_ids=["ev"])
    first = timeline_order([event]); second = timeline_order([event])
    assert first[0].finding_type == "TIMELINE_ORDER_VIOLATION"
    assert first[0].id == second[0].id


def test_location_conflict_requires_confirmed_same_event():
    base = dict(project_id="p", character_id="c", valid_from_event_id="e", certainty=Certainty.CONFIRMED, state=LocationState.PRESENT)
    assert location_conflicts([CharacterLocationState(location_id="a", **base), CharacterLocationState(location_id="b", **base)])
    estimated = dict(base, certainty=Certainty.ESTIMATED)
    assert not location_conflicts([CharacterLocationState(location_id="a", **base), CharacterLocationState(location_id="b", **estimated)])


def test_unknown_knowledge_only_reports_explicit_use_without_evidence():
    item = CharacterKnowledge(project_id="p", character_id="c", subject_type="FACT", subject_id="f", knowledge_state=KnowledgeState.UNKNOWN)
    assert knowledge_leaks([item], {"f"})[0].severity.value == "LOW"
    assert knowledge_leaks([item], set()) == []
