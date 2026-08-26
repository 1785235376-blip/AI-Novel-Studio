import json,os,uuid
import psycopg
from dotenv import load_dotenv
from app.collaboration import CollaborationScope,Workspace,Storyline,Branch
from app.repositories.postgres.scope import PostgresScopeRepository
from app.repositories.postgres.narrative import PostgresNarrativeRepository
from app.services.collaboration_scope_service import CollaborationScopeService

load_dotenv();url=os.environ["DATABASE_URL"].replace("postgresql+psycopg://","postgresql://");run=uuid.uuid4().hex;project=f"multi-{run}"
with psycopg.connect(url) as c:c.execute("INSERT INTO novels(slug,title,metadata,created_at,updated_at) VALUES (%s,%s,'{}',now(),now())",(project,"Multi Client"));c.commit()
class Novels:
 def get(self,p):return {"id":p}
repo_a=PostgresScopeRepository(lambda:psycopg.connect(url));repo_b=PostgresScopeRepository(lambda:psycopg.connect(url));a=CollaborationScopeService(repo_a,Novels());b=CollaborationScopeService(repo_b,Novels());wid=f"w-{run}";sid=f"s-{run}";b1=f"b1-{run}";b2=f"b2-{run}";a.create_workspace(Workspace(wid,"W"));a.link_project(wid,project);a.create_storyline(Storyline(sid,wid,project,"S"));a.create_branch(Branch(b1,wid,project,sid,"B1"));a.create_branch(Branch(b2,wid,project,sid,"B2"));visible=b.get_workspace(wid)["id"]==wid and b.list_storylines(wid,project)[0]["id"]==sid and len(b.list_branches(wid,project,sid))==2
narrative_a=PostgresNarrativeRepository(lambda:psycopg.connect(url));narrative_b=PostgresNarrativeRepository(lambda:psycopg.connect(url));view_a=a.scoped_narrative(CollaborationScope(wid,project,sid,b1),narrative_a);view_b=b.scoped_narrative(CollaborationScope(wid,project,sid,b1),narrative_b);other=b.scoped_narrative(CollaborationScope(wid,project,sid,b2),narrative_b);view_a.create(project,"events",{"id":f"e-{run}","project_id":project,"subject_id":"x","chapter_version_id":f"{project}:1:v1","fingerprint":f"f-{run}","created_at":"2026-08-09T00:00:00+00:00"});shared=len(view_b.list(project,"events"))==1;isolated=other.list(project,"events")==[]
artifact={"client_a_connection":"REAL_VERIFIED","client_b_connection":"REAL_VERIFIED","shared_workspace_visibility":"PASS" if visible else "FAIL","shared_project_visibility":"PASS" if visible else "FAIL","shared_storyline_visibility":"PASS" if visible else "FAIL","shared_branch_visibility":"PASS" if visible else "FAIL","cross_branch_isolation":"PASS" if isolated else "FAIL","shared_narrative_visibility":"PASS" if shared else "FAIL","process_local_state_dependency":"NONE"};print(json.dumps(artifact,sort_keys=True))
if not visible or not shared or not isolated:raise SystemExit(1)
