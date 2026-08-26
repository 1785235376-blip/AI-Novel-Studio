from app.narrative_detection import *

def test_no_expectation_means_no_finding():assert registry.evaluate(NarrativeRuleContext("p",20))==[]
def test_thread_stale_uses_explicit_deadline_and_stable_identity():
 e=NarrativeExpectation("x","p","THREAD","t","THREAD_PROGRESS_BY",5,("ev",),"chapter:1")
 a=registry.evaluate(NarrativeRuleContext("p",6,[e],{"t":2}));b=registry.evaluate(NarrativeRuleContext("p",6,[e],{"t":2}))
 assert a[0].finding_type=="THREAD_STALE" and a[0].id==b[0].id and a[0].evidence_ids==["ev"]
def test_foreshadowing_overdue_respects_payoff():
 e=NarrativeExpectation("x","p","FORESHADOWING","f","FORESHADOWING_PAYOFF_BY",5)
 assert registry.evaluate(NarrativeRuleContext("p",6,[e],foreshadowing_payoff_chapter={"f":5}))==[]
 assert registry.evaluate(NarrativeRuleContext("p",6,[e]))[0].finding_type=="FORESHADOWING_OVERDUE"
