import pytest

from app.narrative import (CharacterGoal, Foreshadowing, Mystery, NarrativeChangeProposal,
    NarrativeEntityType, NarrativeProposalPayload, NarrativeProposalStatus, NarrativeProposalType, PlotThread)
from app.repositories.file.narrative import FileNarrativeRepository
from app.services.narrative_proposal_service import NarrativeProposalService
from app.services.narrative_state_service import NarrativeStateService


class Chapters:
    version=2
    def get(self,chapter_id):
        if chapter_id!="p:1":raise FileNotFoundError(chapter_id)
        return {"id":chapter_id,"novel_id":"p","version":self.version}

class Lore:
    def get_evidence(self,evidence_id):return {"id":evidence_id,"novel_id":"other" if evidence_id=="cross" else "p"}


def setup(tmp_path):
    repository=FileNarrativeRepository(tmp_path);chapters=Chapters();state=NarrativeStateService(repository,chapters=chapters,lore=Lore());service=NarrativeProposalService(repository,state)
    for kind,item in (("threads",PlotThread("t","p","Thread")),("foreshadowing",Foreshadowing("f","p","Clue")),("mysteries",Mystery("m","p","Who?")),("character_goals",CharacterGoal("g","p","c","Escape"))):repository.create("p",kind,item.__dict__)
    return repository,chapters,state,service


CASES = [
    (NarrativeProposalType.PLOT_THREAD_ADVANCED,NarrativeEntityType.PLOT_THREAD,"t",{"progress_summary":"Moved"},"OPEN"),
    (NarrativeProposalType.FORESHADOWING_DEVELOPED,NarrativeEntityType.FORESHADOWING,"f",{"progress_summary":"Deepened"},"DEVELOPING"),
    (NarrativeProposalType.MYSTERY_DEVELOPED,NarrativeEntityType.MYSTERY,"m",{"progress_summary":"Deepened"},"DEVELOPING"),
    (NarrativeProposalType.CHARACTER_GOAL_ADVANCED,NarrativeEntityType.CHARACTER_GOAL,"g",{"progress_summary":"Moved"},"ACTIVE"),
]


@pytest.mark.parametrize("proposal_type,subject_type,subject_id,payload,status",CASES)
def test_pending_has_no_mutation_and_accept_applies_once(tmp_path,proposal_type,subject_type,subject_id,payload,status):
    repository,_,_,service=setup(tmp_path);before=repository.get("p",{"PLOT_THREAD":"threads","FORESHADOWING":"foreshadowing","MYSTERY":"mysteries","CHARACTER_GOAL":"character_goals"}[subject_type],subject_id).copy()
    proposal=NarrativeChangeProposal("proposal", "p", proposal_type, subject_type, subject_id, "p:1:v2", NarrativeProposalPayload(**payload), ("ev",))
    created=service.create_proposal(proposal);assert created["status"]=="PENDING" and repository.list("p","events")==[]
    assert service.create_proposal(proposal)["id"]=="proposal" and len(service.list_proposals("p"))==1
    assert repository.get("p",{"PLOT_THREAD":"threads","FORESHADOWING":"foreshadowing","MYSTERY":"mysteries","CHARACTER_GOAL":"character_goals"}[subject_type],subject_id)==before
    accepted=service.accept_proposal("p","proposal");assert accepted["status"]=="ACCEPTED"
    assert repository.get("p",{"PLOT_THREAD":"threads","FORESHADOWING":"foreshadowing","MYSTERY":"mysteries","CHARACTER_GOAL":"character_goals"}[subject_type],subject_id)["status"]==status
    service.accept_proposal("p","proposal");assert len(repository.list("p","events"))==len(repository.list("p","chapter_links"))==1


@pytest.mark.parametrize("proposal_type,subject_type,subject_id,payload,status",[
    (NarrativeProposalType.FORESHADOWING_PAYOFF,NarrativeEntityType.FORESHADOWING,"f",{"payoff_summary":"Paid"},"PAYOFF"),
    (NarrativeProposalType.MYSTERY_ANSWERED,NarrativeEntityType.MYSTERY,"m",{"answer_summary":"Butler"},"ANSWERED"),
    (NarrativeProposalType.CHARACTER_GOAL_COMPLETED,NarrativeEntityType.CHARACTER_GOAL,"g",{"progress_summary":"Done"},"COMPLETED"),
    (NarrativeProposalType.CHARACTER_GOAL_FAILED,NarrativeEntityType.CHARACTER_GOAL,"g",{"progress_summary":"Failed"},"FAILED"),
])
def test_terminal_proposal_types_apply(tmp_path,proposal_type,subject_type,subject_id,payload,status):
    repository,_,state,service=setup(tmp_path)
    if proposal_type is NarrativeProposalType.FORESHADOWING_PAYOFF:state.record_chapter_narrative_progress(__import__('app.narrative',fromlist=['ChapterNarrativeLink']).ChapterNarrativeLink("prior","p","p:1",2,subject_type,subject_id,__import__('app.narrative',fromlist=['NarrativeProgressType']).NarrativeProgressType.DEVELOPED,event_id="prior-event"))
    service.create_proposal(NarrativeChangeProposal("proposal","p",proposal_type,subject_type,subject_id,"p:1:v2",NarrativeProposalPayload(**payload)))
    service.accept_proposal("p","proposal")
    kind={NarrativeEntityType.FORESHADOWING:"foreshadowing",NarrativeEntityType.MYSTERY:"mysteries",NarrativeEntityType.CHARACTER_GOAL:"character_goals"}[subject_type]
    assert repository.get("p",kind,subject_id)["status"]==status


def test_reject_stale_validation_and_atomic_failure_leave_state_unchanged(tmp_path,monkeypatch):
    repository,chapters,state,service=setup(tmp_path)
    def proposal(pid):return NarrativeChangeProposal(pid,"p",NarrativeProposalType.MYSTERY_ANSWERED,NarrativeEntityType.MYSTERY,"m","p:1:v2",NarrativeProposalPayload(answer_summary="Answer"))
    service.create_proposal(proposal("rejected"));service.reject_proposal("p","rejected")
    assert repository.list("p","events")==[]
    with pytest.raises(ValueError):service.accept_proposal("p","rejected")
    stale=proposal("stale");stale.payload=NarrativeProposalPayload(answer_summary="Different answer");service.create_proposal(stale);chapters.version=3
    with pytest.raises(ValueError):service.accept_proposal("p","stale")
    assert service.get_proposal("p","stale")["status"]=="PENDING" and repository.get("p","mysteries","m")["status"]=="OPEN"
    chapters.version=2;before=repository._read("p");monkeypatch.setattr(repository,"_write",lambda *_: (_ for _ in ()).throw(OSError("failure")))
    with pytest.raises(OSError):service.accept_proposal("p","stale")
    assert repository._read("p")==before


def test_structure_and_provenance_guards(tmp_path):
    _,_,_,service=setup(tmp_path)
    with pytest.raises(ValueError):service.create_proposal(NarrativeChangeProposal("bad","p",NarrativeProposalType.MYSTERY_ANSWERED,NarrativeEntityType.CHARACTER_GOAL,"g","p:1:v2",NarrativeProposalPayload(answer_summary="x")))
    with pytest.raises(ValueError):service.create_proposal(NarrativeChangeProposal("bad","p",NarrativeProposalType.MYSTERY_ANSWERED,NarrativeEntityType.MYSTERY,"m","p:1:v2",NarrativeProposalPayload(answer_summary="x"),("cross",)))
