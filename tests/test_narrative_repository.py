from app.narrative import *
from app.repositories.file.narrative import FileNarrativeRepository
from app.services.narrative_state_service import NarrativeStateService


def test_file_narrative_lifecycle_is_atomic_and_idempotent(tmp_path):
    service=NarrativeStateService(FileNarrativeRepository(tmp_path))
    service.create_thread(PlotThread("t","p","Thread")); event=NarrativeEvent("e","p","THREAD_PROGRESS","t","chapter:1",("ev",))
    service.transition_thread("p","t","RESOLVED",event)
    state=service.state("p");assert state["threads"][0]["status"]=="RESOLVED";assert len(state["events"])==1


def test_file_narrative_project_isolation(tmp_path):
    service=NarrativeStateService(FileNarrativeRepository(tmp_path));service.create_thread(PlotThread("t","a","A"))
    assert service.state("b")["threads"]==[]
