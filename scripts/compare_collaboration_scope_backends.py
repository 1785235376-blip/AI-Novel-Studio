import json,os,tempfile,uuid
from pathlib import Path
import psycopg
from dotenv import load_dotenv
from app.collaboration import *
from app.repositories.file.scope import FileScopeRepository
from app.repositories.file.narrative import FileNarrativeRepository
from app.repositories.postgres.scope import PostgresScopeRepository
from app.repositories.postgres.narrative import PostgresNarrativeRepository
from app.repositories.scoped_narrative import ScopedNarrativeRepository
from app.services.collaboration_scope_service import CollaborationScopeService

load_dotenv();url=os.environ["DATABASE_URL"].replace("postgresql+psycopg://","postgresql://");run=uuid.uuid4().hex;project=f"scope-{run}";stamp="2026-08-09T00:00:00+00:00"
class Novels:
 def get(self,p):
  if p!=project:raise FileNotFoundError(p)
  return {"id":p}
with psycopg.connect(url) as c:c.execute("INSERT INTO novels(slug,title,metadata,created_at,updated_at) VALUES (%s,%s,'{}',now(),now())",(project,"Scope Verification"));c.commit()
def execute(scope_repo,narrative_repo):
 s=CollaborationScopeService(scope_repo,Novels());w=Workspace(f"w-{run}","W",stamp,stamp);s.create_workspace(w);s.link_project(w.id,project);story=Storyline(f"s-{run}",w.id,project,"S","",stamp,stamp);s.create_storyline(story);b1=Branch(f"b1-{run}",w.id,project,story.id,"B1",None,stamp,stamp);b2=Branch(f"b2-{run}",w.id,project,story.id,"B2",None,stamp,stamp);s.create_branch(b1);s.create_branch(b2);scope=CollaborationScope(w.id,project,story.id,b1.id);s.validate_scope(scope);view=s.scoped_narrative(scope,narrative_repo);view.create(project,"events",{"id":f"e-{run}","project_id":project,"subject_id":"x","chapter_version_id":f"{project}:1:v1","fingerprint":f"f-{run}","created_at":stamp});other=s.scoped_narrative(CollaborationScope(w.id,project,story.id,b2.id),narrative_repo)
 return {"workspace":s.get_workspace(w.id),"storylines":s.list_storylines(w.id,project),"branches":s.list_branches(w.id,project,story.id),"event":view.list(project,"events"),"other_branch":other.list(project,"events")}
pg_scope=PostgresScopeRepository(lambda:psycopg.connect(url));pg_narrative=PostgresNarrativeRepository(lambda:psycopg.connect(url));postgres=execute(pg_scope,pg_narrative);local=execute(FileScopeRepository(Path(tempfile.mkdtemp())),FileNarrativeRepository(Path(tempfile.mkdtemp())));results={k:postgres[k]==local[k] for k in postgres}
with psycopg.connect(url) as c:typed=c.execute("SELECT storyline_id,branch_id FROM narrative_events WHERE id=%s",(f"e-{run}",)).fetchone()==(f"s-{run}",f"b1-{run}")
artifact={"workspace":"MATCH" if results["workspace"] else "MISMATCH","storyline":"MATCH" if results["storylines"] else "MISMATCH","branch":"MATCH" if results["branches"] else "MISMATCH","narrative_event_scope":"MATCH" if results["event"] and typed else "MISMATCH","typed_scope_columns":"PASS" if typed else "FAIL","cross_branch_isolation":"PASS" if not postgres["other_branch"] and not local["other_branch"] else "FAIL","overall_backend_parity":"MATCH" if all(results.values()) and typed else "MISMATCH","results":results};print(json.dumps(artifact,sort_keys=True))
if not all(results.values()) or not typed:raise SystemExit(1)
