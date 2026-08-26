import pytest

from app.narrative import (CharacterGoal,CharacterGoalStatus,ChapterNarrativeLink,Foreshadowing,Mystery,MysteryStatus,NarrativeEntityType,NarrativeProgressType,PlotThread,transition_character_goal,transition_mystery)
from app.repositories.file.narrative import FileNarrativeRepository
from app.services.narrative_state_service import NarrativeStateService


def test_mystery_and_character_goal_lifecycle_guards():
    mystery=Mystery("m","p","Who?");transition_mystery(mystery,MysteryStatus.DEVELOPING);transition_mystery(mystery,MysteryStatus.ANSWERED,"p:1:v1")
    with pytest.raises(ValueError):transition_mystery(mystery,MysteryStatus.OPEN)
    goal=CharacterGoal("g","p","c","Escape");transition_character_goal(goal,CharacterGoalStatus.SUSPENDED);transition_character_goal(goal,CharacterGoalStatus.ACTIVE);transition_character_goal(goal,CharacterGoalStatus.COMPLETED,"p:1:v1")
    with pytest.raises(ValueError):transition_character_goal(goal,CharacterGoalStatus.ACTIVE)


def test_explicit_chapter_progress_is_atomic_idempotent_and_typed(tmp_path,monkeypatch):
    repository=FileNarrativeRepository(tmp_path);service=NarrativeStateService(repository)
    for kind,item in (("threads",PlotThread("t","p","Thread")),("foreshadowing",Foreshadowing("f","p","Clue")),("mysteries",Mystery("m","p","Who?")),("character_goals",CharacterGoal("g","p","c","Escape"))):repository.create("p",kind,item.__dict__)
    links=[
        ChapterNarrativeLink("l1","p","p:1",1,NarrativeEntityType.PLOT_THREAD,"t",NarrativeProgressType.ADVANCED,event_id="e1"),
        ChapterNarrativeLink("l2","p","p:1",1,NarrativeEntityType.FORESHADOWING,"f",NarrativeProgressType.DEVELOPED,event_id="e2"),
        ChapterNarrativeLink("l3","p","p:1",1,NarrativeEntityType.MYSTERY,"m",NarrativeProgressType.DEVELOPED,("note"),(),"e3"),
        ChapterNarrativeLink("l4","p","p:1",1,NarrativeEntityType.CHARACTER_GOAL,"g",NarrativeProgressType.ADVANCED,event_id="e4"),
    ]
    for link in links:service.record_chapter_narrative_progress(link)
    service.record_chapter_narrative_progress(links[0])
    assert len(service.list_chapter_progress("p"))==4
    assert len(repository.list("p","events"))==4
    assert service.state("p")["mysteries"][0]["status"]=="DEVELOPING"
    invalid=ChapterNarrativeLink("bad","p","p:1",1,NarrativeEntityType.MYSTERY,"m",NarrativeProgressType.PAYOFF,event_id="bad-event")
    with pytest.raises(ValueError):service.record_chapter_narrative_progress(invalid)
    before=repository._read("p")
    monkeypatch.setattr(repository,"_write",lambda *_: (_ for _ in ()).throw(OSError("failure")))
    with pytest.raises(OSError):service.record_chapter_narrative_progress(ChapterNarrativeLink("fail","p","p:1",1,NarrativeEntityType.MYSTERY,"m",NarrativeProgressType.ANSWERED,event_id="fail-event"))
    assert repository._read("p")==before
