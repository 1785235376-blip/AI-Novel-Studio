from app.lore.continuity import CharacterKnowledge, KnowledgeState
from app.lore.continuity_engine import ContinuityRuleContext, registry


def _types(ctx): return {x.finding_type:x for x in registry.evaluate(ctx)}


def test_canon_conflict_requires_explicit_authoritative_difference():
    found=_types(ContinuityRuleContext(project_id="p",canon_facts={"sun":"yellow"},asserted_facts={"sun":"blue"}))
    assert found["CANON_RULE_CONFLICT"].severity.value=="HIGH"
    assert "CANON_RULE_CONFLICT" not in _types(ContinuityRuleContext(project_id="p",asserted_facts={"sun":"blue"}))


def test_false_belief_is_separate_from_unknown_and_requires_fact_use():
    false=CharacterKnowledge(project_id="p",character_id="c",subject_type="FACT",subject_id="f",knowledge_state=KnowledgeState.FALSE_BELIEF,evidence_ids=["ev"])
    assert "FALSE_BELIEF_AS_FACT" in _types(ContinuityRuleContext(project_id="p",knowledge=[false],asserted_facts={"f":True}))
    unknown=false.model_copy(update={"knowledge_state":KnowledgeState.UNKNOWN})
    assert "FALSE_BELIEF_AS_FACT" not in _types(ContinuityRuleContext(project_id="p",knowledge=[unknown],asserted_facts={"f":True}))


def test_missing_evidence_uses_explicit_policy_and_invents_no_evidence():
    found=_types(ContinuityRuleContext(project_id="p",evidence_required_subjects={"f"}))
    assert found["MISSING_EVIDENCE"].evidence_ids==[]
    assert "MISSING_EVIDENCE" not in _types(ContinuityRuleContext(project_id="p",evidence_required_subjects={"f"},evidence_present_subjects={"f"}))
