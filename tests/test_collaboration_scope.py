import pytest
from app.collaboration import *
from app.repositories.file.scope import FileScopeRepository
from app.repositories.file.narrative import FileNarrativeRepository
from app.services.collaboration_scope_service import CollaborationScopeService
from app.services.narrative_proposal_service import NarrativeProposalService
from app.services.narrative_state_service import NarrativeStateService
from app.narrative import Mystery,NarrativeChangeProposal,NarrativeEntityType,NarrativeProposalPayload,NarrativeProposalType
from app.narrative_detection import NarrativeExpectation,NarrativeRuleContext,_finding

class Novels:
 def get(self,project):
  if project not in {"p","q"}:raise FileNotFoundError(project)
  return {"id":project}

def service(tmp_path):return CollaborationScopeService(FileScopeRepository(tmp_path),Novels())
def test_default_scope_is_stable_idempotent_and_reloadable(tmp_path):
 first=service(tmp_path).ensure_default_scope("p");second=service(tmp_path).ensure_default_scope("p")
 assert first==second==CollaborationScope("default-workspace","p","default-storyline:p","main:default-storyline:p")
 assert len(service(tmp_path).list_workspaces())==1 and len(service(tmp_path).list_storylines("default-workspace","p"))==1
def test_ownership_and_scope_validation(tmp_path):
 s=service(tmp_path);s.create_workspace(Workspace("w","W"));s.link_project("w","p");s.create_storyline(Storyline("s","w","p","S"));s.create_branch(Branch("b","w","p","s","B"));assert s.validate_scope(CollaborationScope("w","p","s","b"))
 with pytest.raises(ValueError):s.validate_scope(CollaborationScope("w","q","s","b"))
 with pytest.raises(ValueError):s.create_storyline(Storyline("bad","w","q","Bad"))
def test_storyline_and_branch_narrative_isolation(tmp_path):
 s=service(tmp_path);s.create_workspace(Workspace("w","W"));s.link_project("w","p")
 for sid,bid in (("s1","b1"),("s1","b2"),("s2","b3")):
  if not any(x["id"]==sid for x in s.repository.list("storylines")):s.create_storyline(Storyline(sid,"w","p",sid))
  s.create_branch(Branch(bid,"w","p",sid,bid))
 base=FileNarrativeRepository(tmp_path/"narrative");views=[s.scoped_narrative(CollaborationScope("w","p",sid,bid),base) for sid,bid in (("s1","b1"),("s1","b2"),("s2","b3"))]
 views[0].create("p","events",{"id":"e1","project_id":"p","subject_id":"x","chapter_version_id":"p:1:v1","fingerprint":"f1","created_at":"2026-01-01T00:00:00+00:00"})
 assert len(views[0].list("p","events"))==1 and views[1].list("p","events")==[] and views[2].list("p","events")==[]
 with pytest.raises(KeyError):views[1].get("p","events","e1")
def test_revision_and_snapshot_are_reservations_only(tmp_path):
 scope=service(tmp_path).ensure_default_scope("p");revision=RevisionRef("r",scope);assert ContextSnapshotRef("c",scope,revision).revision==revision
def test_legacy_fingerprints_stable_and_new_branches_isolated(tmp_path):
 s=service(tmp_path);legacy=s.ensure_default_scope("p");s.create_workspace(Workspace("w","W"));
 # A second project provides a clean non-default workspace fixture.
 s.link_project("w","q");s.create_storyline(Storyline("s","w","q","S"));s.create_branch(Branch("b1","w","q","s","B1"));s.create_branch(Branch("b2","w","q","s","B2"))
 base=FileNarrativeRepository(tmp_path/"n");legacy_repo=s.scoped_narrative(legacy,base);assert legacy_repo.project_key=="p"
 fingerprints=[]
 for bid in ("b1","b2"):
  repo=s.scoped_narrative(CollaborationScope("w","q","s",bid),base);state=NarrativeStateService(repo);state.create_mystery(Mystery(f"m-{bid}","q","Who?"));proposal=NarrativeProposalService(repo,state).create_proposal(NarrativeChangeProposal(f"p-{bid}","q",NarrativeProposalType.MYSTERY_ANSWERED,NarrativeEntityType.MYSTERY,f"m-{bid}","q:1:v1",NarrativeProposalPayload(answer_summary="A")));fingerprints.append(proposal["fingerprint"])
 assert fingerprints[0]!=fingerprints[1]
 e=NarrativeExpectation("e","p","MYSTERY","m","MYSTERY_ANSWER_BY",1);legacy_id=_finding(NarrativeRuleContext("p",2),"MYSTERY_OVERDUE",e).id;assert legacy_id==_finding(NarrativeRuleContext("p",2),"MYSTERY_OVERDUE",e).id
 assert _finding(NarrativeRuleContext("p",2,storyline_id="s",branch_id="b1"),"MYSTERY_OVERDUE",e).id!=_finding(NarrativeRuleContext("p",2,storyline_id="s",branch_id="b2"),"MYSTERY_OVERDUE",e).id
