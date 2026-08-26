import pytest

from app.narrative_detection import NarrativeExpectation,NarrativeRuleContext,registry
from app.repositories.file.narrative import FileNarrativeRepository
from app.services.narrative_finding_service import NarrativeFindingService


def expectation(kind,subject,id="e",deadline=5,active=True):return NarrativeExpectation(id,"p",subject.split("_")[0] if subject else "",subject,kind,deadline,active=active)


@pytest.mark.parametrize("status,expected",[("OPEN",1),("DEVELOPING",1),("ANSWERED",0),("ABANDONED",0)])
def test_mystery_overdue_boundary_terminal_and_explicit_guard(status,expected):
    mystery={"id":"m","project_id":"p","status":status}
    assert not [x for x in registry.evaluate(NarrativeRuleContext("p",99,mysteries=[mystery])) if x.finding_type=="MYSTERY_OVERDUE"]
    e=NarrativeExpectation("e","p","MYSTERY","m","MYSTERY_ANSWER_BY",5)
    assert not [x for x in registry.evaluate(NarrativeRuleContext("p",5,[e],mysteries=[mystery])) if x.finding_type=="MYSTERY_OVERDUE"]
    found=[x for x in registry.evaluate(NarrativeRuleContext("p",6,[e],mysteries=[mystery])) if x.finding_type=="MYSTERY_OVERDUE"]
    assert len(found)==expected


@pytest.mark.parametrize("status,expected",[("ACTIVE",1),("SUSPENDED",0),("COMPLETED",0),("FAILED",0),("ABANDONED",0)])
def test_character_goal_stale_boundary_status_and_event_only(status,expected):
    goal={"id":"g","project_id":"p","status":status};e=NarrativeExpectation("e","p","CHARACTER_GOAL","g","CHARACTER_GOAL_PROGRESS_BY",5)
    assert not [x for x in registry.evaluate(NarrativeRuleContext("p",5,[e],character_goals=[goal])) if x.finding_type=="CHARACTER_GOAL_STALE"]
    found=[x for x in registry.evaluate(NarrativeRuleContext("p",6,[e],character_goals=[goal])) if x.finding_type=="CHARACTER_GOAL_STALE"]
    assert len(found)==expected
    event={"project_id":"p","subject_id":"g","event_type":"CHARACTER_GOAL:ADVANCED"}
    assert not [x for x in registry.evaluate(NarrativeRuleContext("p",6,[e],character_goals=[goal],narrative_events=[event])) if x.finding_type=="CHARACTER_GOAL_STALE"]
    unrelated={"project_id":"p","subject_id":"g","event_type":"CHARACTER_GOAL:MENTIONED"}
    assert len([x for x in registry.evaluate(NarrativeRuleContext("p",6,[e],character_goals=[{"id":"g","project_id":"p","status":"ACTIVE"}],narrative_events=[unrelated])) if x.finding_type=="CHARACTER_GOAL_STALE"])==1


def test_phase2c_registry_order_and_duplicate_guard():
    assert list(registry.rules)==["THREAD_STALE","FORESHADOWING_OVERDUE","MYSTERY_OVERDUE","CHARACTER_GOAL_STALE"]
    with pytest.raises(ValueError):registry.register("MYSTERY_OVERDUE",lambda _:[])


def test_phase2c_finding_resolution_identity_and_failure_isolation(tmp_path):
    service=NarrativeFindingService(FileNarrativeRepository(tmp_path));e=NarrativeExpectation("e","p","MYSTERY","m","MYSTERY_ANSWER_BY",2);service.create_expectation(e)
    open_ctx=NarrativeRuleContext("p",3,[e],mysteries=[{"id":"m","project_id":"p","status":"OPEN"}])
    first=service.run_checks(open_ctx)[0];service.run_checks(open_ctx);assert len(service.list_findings("p"))==1
    answered=NarrativeRuleContext("p",3,[e],mysteries=[{"id":"m","project_id":"p","status":"ANSWERED"}]);service.run_checks(answered)
    assert service.get_finding("p",first.id)["status"]=="RESOLVED"
    service.run_checks(open_ctx);assert service.get_finding("p",first.id)["status"]=="OPEN"
    original=registry.rules["MYSTERY_OVERDUE"];registry.rules["MYSTERY_OVERDUE"]=lambda _:(_ for _ in ()).throw(RuntimeError("rule failure"))
    try:service.run_checks(answered);assert service.get_finding("p",first.id)["status"]=="OPEN"
    finally:registry.rules["MYSTERY_OVERDUE"]=original
