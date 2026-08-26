from app.context_policy import ContextAuthorityLevel,ContextPolicy,ContextPolicyItem,ContextSourceType
from app.agents import AgentRunner


def item(policy,source_type,source_id,value,**kwargs):return ContextPolicyItem(metadata=policy.metadata(source_type,source_id,"p",**kwargs),value=value)


def test_context_authority_mapping_and_stable_precedence():
    policy=ContextPolicy(4000)
    assert policy.AUTHORITY[ContextSourceType.CANON]==ContextAuthorityLevel.AUTHORITATIVE
    assert policy.AUTHORITY[ContextSourceType.ACCEPTED_CHAPTER]==ContextAuthorityLevel.AUTHORITATIVE
    assert policy.AUTHORITY[ContextSourceType.TIMELINE]==ContextAuthorityLevel.CONSTRAINING
    assert policy.AUTHORITY[ContextSourceType.CHARACTER_KNOWLEDGE]==ContextAuthorityLevel.CONSTRAINING
    assert policy.AUTHORITY[ContextSourceType.LORE_MEMORY]==ContextAuthorityLevel.SUPPORTING
    assert policy.AUTHORITY[ContextSourceType.NARRATIVE_STATE]==ContextAuthorityLevel.SUPPORTING
    assert policy.AUTHORITY[ContextSourceType.NARRATIVE_FINDING]==ContextAuthorityLevel.ADVISORY
    values=[item(policy,"NARRATIVE_FINDING","z",{}),item(policy,"CANON","a",{}),item(policy,"LORE_MEMORY","m",{})]
    first=policy.apply(values).model_dump(mode="json");second=policy.apply(list(reversed(values))).model_dump(mode="json");assert first==second


def test_exact_duplicate_merges_reasons_stably():
    policy=ContextPolicy(4000);a=item(policy,"LORE_MEMORY","m",{"fact":1},selection_reasons=["CURRENT_CHARACTER"]);b=item(policy,"LORE_MEMORY","m",{"fact":1},selection_reasons=["CURRENT_CHAPTER"])
    result=policy.apply([a,b]);assert result.duplicate_count==1 and len(result.supporting)==1
    assert result.supporting[0].metadata.selection_reasons==["CURRENT_CHAPTER","CURRENT_CHARACTER"]


def test_higher_authority_wins_and_advisory_cannot_override():
    policy=ContextPolicy(4000);canon=item(policy,"CANON","canon",{"value":"A"},fact_key="character:c:location");lore=item(policy,"LORE_MEMORY","lore",{"value":"B"},fact_key="character:c:location");advisory=item(policy,"NARRATIVE_FINDING","finding",{"value":"C"},fact_key="character:c:location")
    result=policy.apply([advisory,lore,canon]);assert [x.metadata.source_id for x in result.authoritative]==["canon"]
    assert result.supporting==[] and result.advisory==[] and result.conflicts[0].resolution_policy=="HIGHER_AUTHORITY_WINS"


def test_same_authority_conflict_is_explicit_and_false_conflicts_are_ignored():
    policy=ContextPolicy(4000);a=item(policy,"CANON","a",1,fact_key="x");b=item(policy,"CANON","b",2,fact_key="x");other=item(policy,"CANON","c",3,fact_key="y")
    result=policy.apply([a,b,other]);assert len(result.authoritative)==3
    assert result.conflicts[0].resolution_policy=="UNRESOLVED_HIGH_AUTHORITY_CONFLICT" and result.conflicts[0].writer_visibility=="VISIBLE"
    assert len(result.conflicts)==1


def test_same_source_different_values_are_not_silently_deduplicated():
    policy=ContextPolicy(4000);a=item(policy,"CANON","same",1,fact_key="x");b=item(policy,"CANON","same",2,fact_key="x")
    first=policy.apply([a,b]).model_dump(mode="json");second=policy.apply([b,a]).model_dump(mode="json")
    assert first==second and first["duplicate_count"]==0
    assert first["conflicts"][0]["resolution_policy"]=="UNRESOLVED_HIGH_AUTHORITY_CONFLICT"


def test_budget_and_locality_are_independent_from_authority():
    policy=ContextPolicy(600);local=item(policy,"CANON","local",{"secret":"x"},locality="LOCAL_ONLY");public=item(policy,"CANON","public",{"fact":"x"});warnings=[item(policy,"NARRATIVE_FINDING",f"w{i}",{"warning":"x"*100}) for i in range(10)]
    cloud=policy.apply([local,public,*warnings],cloud=True);assert [x.metadata.source_id for x in cloud.authoritative]==["public"]
    assert cloud.truncated_sources and cloud.budget_usage["AUTHORITATIVE"]>0
    tiny=ContextPolicy(8).apply([public]);assert tiny.authoritative_context_truncated is True and tiny.truncated_sources==["public"]


def test_writer_contract_and_other_agent_isolation():
    class Registry:
        def prompt(self,name):return name
    policy=ContextPolicy(4000).apply([item(ContextPolicy(4000),"CANON","a",1)]).model_dump(mode="json");runner=AgentRunner(Registry());context={"context_policy":policy}
    assert "Higher-authority context" in runner.build_prompt("writer",context,"write")
    assert "context_policy" not in runner.build_prompt("reviewer",context,"review")
