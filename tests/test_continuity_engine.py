from app.lore.continuity import Certainty, CharacterLocationState, LocationState, RelationshipState
from app.lore.continuity_engine import ContinuityRuleContext, registry


def test_registry_is_unique_and_stably_ordered():
    assert len(registry.rule_ids)==len(set(registry.rule_ids))
    assert registry.rule_ids==tuple(sorted(registry.rule_ids))


def test_impossible_travel_requires_explicit_confirmed_boundary():
    base=dict(project_id="p",character_id="c",state=LocationState.PRESENT,certainty=Certainty.CONFIRMED)
    states=[CharacterLocationState(location_id="a",valid_from_event_id="e1",valid_to_event_id="e2",evidence_ids=["a"],**base),CharacterLocationState(location_id="b",valid_from_event_id="e2",evidence_ids=["b"],**base)]
    found=registry.evaluate(ContinuityRuleContext(project_id="p",locations=states,travel_times={("a","b"):10}))
    assert [x for x in found if x.finding_type=="IMPOSSIBLE_TRAVEL"]
    assert not [x for x in registry.evaluate(ContinuityRuleContext(project_id="p",locations=states)) if x.finding_type=="IMPOSSIBLE_TRAVEL"]


def test_relationship_conflict_is_directed_and_temporal():
    base=dict(project_id="p",source_character_id="a",target_character_id="b",valid_from_event_id="e",certainty=Certainty.CONFIRMED)
    states=[RelationshipState(relationship_type="ALLY",evidence_ids=["x"],**base),RelationshipState(relationship_type="ENEMY",evidence_ids=["y"],**base)]
    found=registry.evaluate(ContinuityRuleContext(project_id="p",relationships=states))
    assert [x for x in found if x.finding_type=="RELATIONSHIP_STATE_CONFLICT"]
    reverse=states[1].model_copy(update={"source_character_id":"b","target_character_id":"a"})
    assert not [x for x in registry.evaluate(ContinuityRuleContext(project_id="p",relationships=[states[0],reverse])) if x.finding_type=="RELATIONSHIP_STATE_CONFLICT"]
