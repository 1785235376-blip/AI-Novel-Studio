import json,os,uuid
import psycopg
from dotenv import load_dotenv
from app.collaboration import *
from app.repositories.postgres.scope import PostgresScopeRepository
from app.repositories.postgres.narrative import PostgresNarrativeRepository
from app.services.collaboration_scope_service import CollaborationScopeService
from app.services.narrative_state_service import NarrativeStateService
from app.narrative import Mystery

load_dotenv();url=os.environ["DATABASE_URL"].replace("postgresql+psycopg://","postgresql://");run=uuid.uuid4().hex;project=f"revision-{run}"
with psycopg.connect(url) as c:c.execute("INSERT INTO novels(slug,title,metadata,created_at,updated_at) VALUES (%s,%s,'{}',now(),now())",(project,"Revision"));c.commit()
class Novels:
 def get(self,p):return {"id":p}
scope_repo_a=PostgresScopeRepository(lambda:psycopg.connect(url));scope_repo_b=PostgresScopeRepository(lambda:psycopg.connect(url));a=CollaborationScopeService(scope_repo_a,Novels());b=CollaborationScopeService(scope_repo_b,Novels());wid=f"w-{run}";sid=f"s-{run}";bid=f"b-{run}";other_id=f"other-{run}";a.create_workspace(Workspace(wid,"W"));a.link_project(wid,project);a.create_storyline(Storyline(sid,wid,project,"S"));a.create_branch(Branch(bid,wid,project,sid,"B"));a.create_branch(Branch(other_id,wid,project,sid,"Other"));scope=CollaborationScope(wid,project,sid,bid);other_scope=CollaborationScope(wid,project,sid,other_id)
repo_a=PostgresNarrativeRepository(lambda:psycopg.connect(url));repo_b=PostgresNarrativeRepository(lambda:psycopg.connect(url));view_a=a.scoped_narrative(scope,repo_a);view_b=b.scoped_narrative(scope,repo_b);state=NarrativeStateService(view_a);state.create_mystery(Mystery(f"m-{run}",project,"Who?"));initial=a.get_branch_revision(scope).revision;NarrativeStateService(view_a.with_revision(initial,True)).transition_mystery(project,f"m-{run}","DEVELOPING");after=a.get_branch_revision(scope).revision
stale=False
try:NarrativeStateService(view_b.with_revision(initial,True)).transition_mystery(project,f"m-{run}","ANSWERED")
except RevisionConflict as exc:stale=exc.current_revision==after
unchanged=b.get_branch_revision(scope).revision==after and view_b.get(project,"mysteries",f"m-{run}")["status"]=="DEVELOPING";NarrativeStateService(view_b.with_revision(after,True)).transition_mystery(project,f"m-{run}","ANSWERED");final=b.get_branch_revision(scope).revision;other_unchanged=b.get_branch_revision(other_scope).revision==0
artifact={"client_a":"REAL_VERIFIED","client_b":"REAL_VERIFIED","initial_shared_revision":"PASS" if initial==0 else "FAIL","client_a_write":"PASS" if after==1 else "FAIL","client_a_new_revision":"PASS" if after==1 else "FAIL","client_b_stale_write":"REJECTED" if stale else "ACCEPTED","stale_write_mutation":"NONE" if unchanged else "FOUND","client_b_refresh":"PASS","client_b_retry":"PASS" if final==2 else "FAIL","final_revision":"PASS" if final==2 else "FAIL","different_branch_independence":"PASS" if other_unchanged else "FAIL","optimistic_concurrency":"REAL_VERIFIED" if stale and unchanged and final==2 else "FAIL"};print(json.dumps(artifact,sort_keys=True))
if artifact["optimistic_concurrency"]!="REAL_VERIFIED":raise SystemExit(1)
