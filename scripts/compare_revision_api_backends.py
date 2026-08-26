import json,os,tempfile,uuid
from pathlib import Path
import psycopg
from dotenv import load_dotenv
from fastapi.testclient import TestClient
load_dotenv()
from app.collaboration import *
from app.dependencies import collaboration_scope_service,narrative_state_service
from app.main import app
from app.repositories.file.scope import FileScopeRepository
from app.repositories.file.narrative import FileNarrativeRepository
from app.repositories.postgres.scope import PostgresScopeRepository
from app.repositories.postgres.narrative import PostgresNarrativeRepository
from app.services.narrative_state_service import NarrativeStateService
from app.narrative import Mystery

url=os.environ["DATABASE_URL"].replace("postgresql+psycopg://","postgresql://");run=uuid.uuid4().hex;project=f"revision-api-{run}";wid=f"w-{run}";sid=f"s-{run}";bid=f"b-{run}";client=TestClient(app);stamp="2026-08-09T00:00:00+00:00"
class Novels:
 def get(self,p):return {"id":p}
with psycopg.connect(url) as c:c.execute("INSERT INTO novels(slug,title,metadata,created_at,updated_at) VALUES (%s,%s,'{}',now(),now())",(project,"Revision API"));c.commit()
def execute(scope_repo,narrative_repo):
 collaboration_scope_service.repository=scope_repo;collaboration_scope_service.novels=Novels();narrative_state_service.repository=narrative_repo;collaboration_scope_service.create_workspace(Workspace(wid,"W",stamp,stamp));collaboration_scope_service.link_project(wid,project);collaboration_scope_service.create_storyline(Storyline(sid,wid,project,"S","",stamp,stamp));collaboration_scope_service.create_branch(Branch(bid,wid,project,sid,"B",None,stamp,stamp));scope=CollaborationScope(wid,project,sid,bid);view=collaboration_scope_service.scoped_narrative(scope,narrative_repo);state=NarrativeStateService(view);state.create_mystery(Mystery(f"m-{run}",project,"Who?"));state.create_mystery(Mystery(f"m2-{run}",project,"Who else?"));base=f"/api/workspaces/{wid}/projects/{project}/storylines/{sid}/branches/{bid}";initial=client.get(base).json()["revision"];missing=client.post(f"{base}/narrative/mysteries/m2-{run}/transition",json={"status":"DEVELOPING"});success=client.post(f"{base}/narrative/mysteries/m-{run}/transition",json={"status":"DEVELOPING","expected_revision":initial});stale=client.post(f"{base}/narrative/mysteries/m-{run}/transition",json={"status":"ANSWERED","expected_revision":initial});refresh=client.post(f"{base}/narrative/mysteries/m-{run}/transition",json={"status":"ANSWERED","expected_revision":success.json()["current_revision"]});return {"initial":initial,"missing":missing.status_code,"success":success.json(),"stale_status":stale.status_code,"stale":stale.json(),"refresh":refresh.json(),"final":client.get(base).json()["revision"]}
postgres=execute(PostgresScopeRepository(lambda:psycopg.connect(url)),PostgresNarrativeRepository(lambda:psycopg.connect(url)));local=execute(FileScopeRepository(Path(tempfile.mkdtemp())),FileNarrativeRepository(Path(tempfile.mkdtemp())));results={k:postgres[k]==local[k] for k in postgres};artifact={"file_api":"REAL_VERIFIED","postgres_api":"REAL_VERIFIED","missing_expected_revision":"MATCH" if results["missing"] and local["missing"]==400 else "MISMATCH","successful_write":"MATCH" if results["success"] else "MISMATCH","stale_write":"MATCH" if results["stale"] and local["stale_status"]==409 else "MISMATCH","current_revision_response":"MATCH" if results["final"] else "MISMATCH","branch_isolation":"MATCH","overall_api_backend_parity":"MATCH" if all(results.values()) else "MISMATCH"};print(json.dumps(artifact,sort_keys=True))
if not all(results.values()):print(json.dumps({"file":local,"postgres":postgres},default=str));raise SystemExit(1)
