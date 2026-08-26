import pytest
from app.collaboration import *
from app.repositories.file.scope import FileScopeRepository
from app.repositories.file.narrative import FileNarrativeRepository
from app.services.collaboration_scope_service import CollaborationScopeService
from app.services.narrative_state_service import NarrativeStateService
from app.narrative import Mystery
from app.narrative import NarrativeChangeProposal,NarrativeEntityType,NarrativeProposalPayload,NarrativeProposalType
from app.services.narrative_proposal_service import NarrativeProposalService

class Novels:
 def get(self,p):return {"id":p}
def setup(tmp_path):
 scope_repo=FileScopeRepository(tmp_path);collab=CollaborationScopeService(scope_repo,Novels());collab.create_workspace(Workspace("w","W"));collab.link_project("w","p");collab.create_storyline(Storyline("s","w","p","S"));collab.create_branch(Branch("b","w","p","s","B"));scope=CollaborationScope("w","p","s","b");base=FileNarrativeRepository(tmp_path/"n");return collab,scope,base
def test_revision_initial_increment_stale_and_missing_guard(tmp_path):
 collab,scope,base=setup(tmp_path);assert collab.get_branch_revision(scope).revision==0
 initial=collab.scoped_narrative(scope,base);NarrativeStateService(initial).create_mystery(Mystery("m","p","Who?"))
 guarded=NarrativeStateService(initial.with_revision(0,True));guarded.transition_mystery("p","m","DEVELOPING");assert collab.get_branch_revision(scope).revision==1
 with pytest.raises(RevisionConflict) as exc:NarrativeStateService(initial.with_revision(0,True)).transition_mystery("p","m","ANSWERED")
 assert exc.value.current_revision==1 and base.list(initial.project_key,"mysteries")[0]["status"]=="DEVELOPING"
 with pytest.raises(ValueError,match="expected_revision"):NarrativeStateService(initial.with_revision(None,True)).transition_mystery("p","m","ANSWERED")
 assert collab.get_branch_revision(scope).revision==1
def test_tracking_disabled_enforcement_and_failed_domain_preserves_revision(tmp_path):
 collab,scope,base=setup(tmp_path);view=collab.scoped_narrative(scope,base);state=NarrativeStateService(view);state.create_mystery(Mystery("m","p","Who?"));NarrativeStateService(view.with_revision(None,False)).transition_mystery("p","m","DEVELOPING");assert collab.get_branch_revision(scope).revision==1
 with pytest.raises(ValueError):NarrativeStateService(view.with_revision(1,True)).transition_mystery("p","m","OPEN")
 assert collab.get_branch_revision(scope).revision==1
def test_branch_revisions_are_isolated_and_snapshot_binds_revision(tmp_path):
 collab,scope,_=setup(tmp_path);collab.create_branch(Branch("other","w","p","s","Other"));other=CollaborationScope("w","p","s","other");collab.compare_and_increment(scope,0,True);assert collab.get_branch_revision(scope).revision==1 and collab.get_branch_revision(other).revision==0
 current=collab.get_branch_revision(scope);assert collab.context_snapshot_ref(scope,"snapshot").revision==current and collab.get_branch_revision(scope).revision==1
def test_default_flag_is_disabled():
 from app.config import Settings
 assert Settings().enable_optimistic_concurrency is False
def test_proposal_accept_revision_guard_and_duplicate_idempotency(tmp_path):
 collab,scope,base=setup(tmp_path);view=collab.scoped_narrative(scope,base);state=NarrativeStateService(view);state.create_mystery(Mystery("m","p","Who?"));service=NarrativeProposalService(view,state);service.create_proposal(NarrativeChangeProposal("proposal","p",NarrativeProposalType.MYSTERY_ANSWERED,NarrativeEntityType.MYSTERY,"m","p:1:v1",NarrativeProposalPayload(answer_summary="Answer")))
 guarded_view=view.with_revision(0,True);accepted=NarrativeProposalService(guarded_view,NarrativeStateService(guarded_view)).accept_proposal("p","proposal");assert accepted["status"]=="ACCEPTED" and collab.get_branch_revision(scope).revision==1
 assert NarrativeProposalService(guarded_view,NarrativeStateService(guarded_view)).accept_proposal("p","proposal")["status"]=="ACCEPTED" and collab.get_branch_revision(scope).revision==1
def test_stale_proposal_accept_preserves_pending_and_state(tmp_path):
 collab,scope,base=setup(tmp_path);view=collab.scoped_narrative(scope,base);state=NarrativeStateService(view);state.create_mystery(Mystery("m","p","Who?"));service=NarrativeProposalService(view,state);service.create_proposal(NarrativeChangeProposal("proposal","p",NarrativeProposalType.MYSTERY_ANSWERED,NarrativeEntityType.MYSTERY,"m","p:1:v1",NarrativeProposalPayload(answer_summary="Answer")));collab.compare_and_increment(scope,0,True)
 stale=view.with_revision(0,True)
 with pytest.raises(RevisionConflict):NarrativeProposalService(stale,NarrativeStateService(stale)).accept_proposal("p","proposal")
 assert service.get_proposal("p","proposal")["status"]=="PENDING" and state.get_mystery("p","m")["status"]=="OPEN" and collab.get_branch_revision(scope).revision==1
def test_file_revision_failure_restores_narrative_snapshot(tmp_path,monkeypatch):
 collab,scope,base=setup(tmp_path);view=collab.scoped_narrative(scope,base);state=NarrativeStateService(view);state.create_mystery(Mystery("m","p","Who?"));before=base._read(view.project_key);monkeypatch.setattr(collab.repository,"compare_and_increment",lambda *_args,**_kwargs: (_ for _ in ()).throw(OSError("revision write failed")))
 with pytest.raises(OSError):NarrativeStateService(view.with_revision(0,True)).transition_mystery("p","m","DEVELOPING")
 assert base._read(view.project_key)==before and collab.get_branch_revision(scope).revision==0
