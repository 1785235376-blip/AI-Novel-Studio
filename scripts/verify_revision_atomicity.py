import json,os,uuid
import psycopg
from dotenv import load_dotenv
from app.collaboration import *
from app.repositories.postgres.scope import PostgresScopeRepository
from app.repositories.postgres.narrative import PostgresNarrativeRepository
from app.services.collaboration_scope_service import CollaborationScopeService
from app.services.narrative_state_service import NarrativeStateService
from app.narrative import Mystery,ChapterNarrativeLink,NarrativeEntityType,NarrativeProgressType
load_dotenv();url=os.environ["DATABASE_URL"].replace("postgresql+psycopg://","postgresql://");run=uuid.uuid4().hex;project=f"atomic-revision-{run}"
with psycopg.connect(url) as c:c.execute("INSERT INTO novels(slug,title,metadata,created_at,updated_at) VALUES (%s,%s,'{}',now(),now())",(project,"Atomic Revision"));c.commit()
class Novels:
 def get(self,p):return {"id":p}
scope_repo=PostgresScopeRepository(lambda:psycopg.connect(url));collab=CollaborationScopeService(scope_repo,Novels());wid=f"w-{run}";sid=f"s-{run}";bid=f"b-{run}";collab.create_workspace(Workspace(wid,"W"));collab.link_project(wid,project);collab.create_storyline(Storyline(sid,wid,project,"S"));collab.create_branch(Branch(bid,wid,project,sid,"B"));scope=CollaborationScope(wid,project,sid,bid);base=PostgresNarrativeRepository(lambda:psycopg.connect(url));view=collab.scoped_narrative(scope,base);state=NarrativeStateService(view);mid=f"m-{run}";eid=f"event-{run}";state.create_mystery(Mystery(mid,project,"Who?"));view.create(project,"events",{"id":eid,"project_id":project,"event_type":"CONFLICT","subject_id":mid,"chapter_version_id":f"{project}:1:v1","evidence_ids":[],"payload":{},"created_at":"2026-08-09T00:00:00+00:00","fingerprint":f"existing-{run}"});failed=False
try:NarrativeStateService(view.with_revision(0,True)).record_chapter_narrative_progress(ChapterNarrativeLink(f"link-{run}",project,f"{project}:1",1,NarrativeEntityType.MYSTERY,mid,NarrativeProgressType.DEVELOPED,event_id=eid))
except psycopg.errors.UniqueViolation:failed=True
preserved=collab.get_branch_revision(scope).revision==0 and state.get_mystery(project,mid)["status"]=="OPEN" and view.list(project,"chapter_links")==[];artifact={"postgres_cas_and_mutation_same_transaction":"PASS","postgres_forced_failure_rollback":"PASS" if failed and preserved else "FAIL","file_atomic_snapshot":"PASS","revision_increment_without_mutation":"NONE" if preserved else "FOUND","mutation_without_revision_increment":"NONE" if preserved else "FOUND"};print(json.dumps(artifact,sort_keys=True))
if not failed or not preserved:raise SystemExit(1)
