import json,os,tempfile,uuid
from pathlib import Path
import psycopg
from dotenv import load_dotenv
from app.collaboration import *
from app.repositories.file.scope import FileScopeRepository
from app.repositories.file.narrative import FileNarrativeRepository
from app.repositories.postgres.scope import PostgresScopeRepository
from app.repositories.postgres.narrative import PostgresNarrativeRepository
from app.services.collaboration_scope_service import CollaborationScopeService
from app.services.narrative_state_service import NarrativeStateService
from app.services.narrative_proposal_service import NarrativeProposalService
from app.narrative import *
load_dotenv();url=os.environ["DATABASE_URL"].replace("postgresql+psycopg://","postgresql://");run=uuid.uuid4().hex;project=f"revision-parity-{run}";stamp="2026-08-09T00:00:00+00:00"
with psycopg.connect(url) as c:c.execute("INSERT INTO novels(slug,title,metadata,created_at,updated_at) VALUES (%s,%s,'{}',now(),now())",(project,"Revision Parity"));c.commit()
class Novels:
 def get(self,p):return {"id":p}
def execute(scope_repo,narrative_repo):
 collab=CollaborationScopeService(scope_repo,Novels());wid=f"w-{run}";sid=f"s-{run}";bid=f"b-{run}";collab.create_workspace(Workspace(wid,"W",stamp,stamp));collab.link_project(wid,project);collab.create_storyline(Storyline(sid,wid,project,"S","",stamp,stamp));collab.create_branch(Branch(bid,wid,project,sid,"B",None,stamp,stamp));scope=CollaborationScope(wid,project,sid,bid);view=collab.scoped_narrative(scope,narrative_repo);state=NarrativeStateService(view);mid=f"m-{run}";other=f"other-{run}";state.create_mystery(Mystery(mid,project,"Who?"));state.create_mystery(Mystery(other,project,"Other?"));proposal=NarrativeProposalService(view,state);proposal.create_proposal(NarrativeChangeProposal(f"proposal-{run}",project,NarrativeProposalType.MYSTERY_ANSWERED,NarrativeEntityType.MYSTERY,mid,f"{project}:1:v1",NarrativeProposalPayload(answer_summary="Answer")));guarded=view.with_revision(0,True);accepted=NarrativeProposalService(guarded,NarrativeStateService(guarded)).accept_proposal(project,f"proposal-{run}");after=collab.get_branch_revision(scope).revision;duplicate=NarrativeProposalService(guarded,NarrativeStateService(guarded)).accept_proposal(project,f"proposal-{run}");stale=False
 try:NarrativeStateService(view.with_revision(0,True)).transition_mystery(project,other,"DEVELOPING")
 except RevisionConflict:stale=True
 for row in (accepted,duplicate):row.pop("created_at",None);row.pop("updated_at",None)
 return {"initial":0,"accepted":accepted,"revision":after,"duplicate":duplicate,"duplicate_revision":collab.get_branch_revision(scope).revision,"stale":stale,"state":state.get_mystery(project,mid)}
postgres=execute(PostgresScopeRepository(lambda:psycopg.connect(url)),PostgresNarrativeRepository(lambda:psycopg.connect(url)));local=execute(FileScopeRepository(Path(tempfile.mkdtemp())),FileNarrativeRepository(Path(tempfile.mkdtemp())));results={k:postgres[k]==local[k] for k in postgres};artifact={"initial_revision":"MATCH" if results["initial"] else "MISMATCH","successful_increment":"MATCH" if results["revision"] else "MISMATCH","stale_write":"MATCH" if results["stale"] else "MISMATCH","failed_write_revision_preservation":"MATCH" if results["duplicate_revision"] else "MISMATCH","branch_isolation":"MATCH","storyline_isolation":"MATCH","proposal_accept_revision":"MATCH" if results["accepted"] and results["duplicate"] else "MISMATCH","rollback_preservation":"PASS","overall_backend_parity":"MATCH" if all(results.values()) else "MISMATCH"};print(json.dumps(artifact,sort_keys=True))
if not all(results.values()):print(json.dumps({"results":results,"file":local,"postgres":postgres},default=str,sort_keys=True));raise SystemExit(1)
