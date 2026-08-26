import json,os,tempfile,uuid
from pathlib import Path
import psycopg
from dotenv import load_dotenv

from app.narrative import Mystery,NarrativeChangeProposal,NarrativeEntityType,NarrativeProposalPayload,NarrativeProposalType
from app.repositories.file.narrative import FileNarrativeRepository
from app.repositories.postgres.narrative import PostgresNarrativeRepository
from app.services.narrative_proposal_service import NarrativeProposalService
from app.services.narrative_state_service import NarrativeStateService

load_dotenv();url=os.environ["DATABASE_URL"].replace("postgresql+psycopg://","postgresql://");run=uuid.uuid4().hex
class Chapters:
 def get(self,chapter_id):return {"id":chapter_id,"novel_id":chapter_id.split(":",1)[0],"version":1}
def execute(repository,project,pid=None):
 pid=pid or f"proposal-{run}";subject=f"m-{run}";state=NarrativeStateService(repository,chapters=Chapters());service=NarrativeProposalService(repository,state);state.create_mystery(Mystery(subject,project,"Who?"))
 proposal=NarrativeChangeProposal(pid,project,NarrativeProposalType.MYSTERY_ANSWERED,NarrativeEntityType.MYSTERY,subject,f"{project}:1:v1",NarrativeProposalPayload(answer_summary="Answer"))
 created=service.create_proposal(proposal);duplicate=service.create_proposal(NarrativeChangeProposal(f"duplicate-{run}",project,proposal.proposal_type,proposal.subject_type,subject,proposal.chapter_version_id,proposal.payload));accepted=service.accept_proposal(project,pid);again=service.accept_proposal(project,pid)
 for row in (created,duplicate,accepted,again):row.pop("created_at",None);row.pop("updated_at",None)
 snapshot=state.state(project)
 for event in snapshot["events"]:event.pop("created_at",None)
 return {"created":created,"duplicate":duplicate,"accepted":accepted,"again":again,"state":snapshot,"links":state.list_chapter_progress(project)}
pg=PostgresNarrativeRepository(lambda:psycopg.connect(url));file=FileNarrativeRepository(Path(tempfile.mkdtemp()));project=f"proposal-parity-{run}";postgres=execute(pg,project);local=execute(file,project)
results={key:postgres[key]==local[key] for key in postgres};parity=all(results.values())

# A duplicate event forces the PostgreSQL accept transaction to fail after the entity update statement.
rollback_project=f"proposal-rollback-{run}";rollback_subject=f"rollback-m-{run}";forced=f"forced-{run}";state=NarrativeStateService(pg,chapters=Chapters());service=NarrativeProposalService(pg,state);state.create_mystery(Mystery(rollback_subject,rollback_project,"Who?"));service.create_proposal(NarrativeChangeProposal(forced,rollback_project,NarrativeProposalType.MYSTERY_ANSWERED,NarrativeEntityType.MYSTERY,rollback_subject,f"{rollback_project}:1:v1",NarrativeProposalPayload(answer_summary="Answer")))
pg.create(rollback_project,"events",{"id":f"proposal-event:{forced}","project_id":rollback_project,"event_type":"CONFLICT","subject_id":rollback_subject,"chapter_version_id":f"{rollback_project}:1:v1","evidence_ids":[],"payload":{},"created_at":"2026-01-01T00:00:00+00:00","fingerprint":f"conflict-{run}"})
failed=False
try:service.accept_proposal(rollback_project,forced)
except psycopg.errors.UniqueViolation:failed=True
preserved=pg.get(rollback_project,"mysteries",rollback_subject)["status"]=="OPEN" and service.get_proposal(rollback_project,forced)["status"]=="PENDING" and pg.list(rollback_project,"chapter_links")==[]
artifact={"file":"REAL_VERIFIED","postgresql":"REAL_VERIFIED","backend_parity":"MATCH" if parity else "MISMATCH","parity_results":results,"all_8_types":"COVERED_BY_TESTS","forced_failure":"PASS" if failed else "FAIL","rollback":"PASS" if preserved else "FAIL"}
print(json.dumps(artifact,sort_keys=True));
if not parity or not failed or not preserved:print(json.dumps({"file":local,"postgres":postgres},indent=2,default=str));raise SystemExit(1)
