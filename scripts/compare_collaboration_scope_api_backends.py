import json,os,tempfile,uuid
from pathlib import Path
import psycopg
from dotenv import load_dotenv
from fastapi.testclient import TestClient
load_dotenv()
from app.dependencies import collaboration_scope_service
from app.main import app
from app.repositories.file.scope import FileScopeRepository
from app.repositories.postgres.scope import PostgresScopeRepository

url=os.environ["DATABASE_URL"].replace("postgresql+psycopg://","postgresql://");run=uuid.uuid4().hex;project=f"scope-api-{run}";wid=f"w-{run}";sid=f"s-{run}";bid=f"b-{run}";client=TestClient(app)
class Novels:
 def get(self,p):
  if p!=project:raise FileNotFoundError(p)
  return {"id":p}
with psycopg.connect(url) as c:c.execute("INSERT INTO novels(slug,title,metadata,created_at,updated_at) VALUES (%s,%s,'{}',now(),now())",(project,"Scope API"));c.commit()
def execute(repository):
 collaboration_scope_service.repository=repository;collaboration_scope_service.novels=Novels();created=client.post("/api/workspaces",json={"id":wid,"name":"W"});story=client.post(f"/api/workspaces/{wid}/projects/{project}/storylines",json={"id":sid,"name":"S"});branch=client.post(f"/api/workspaces/{wid}/projects/{project}/storylines/{sid}/branches",json={"id":bid,"name":"B"});responses=(created,story,branch)
 if any(x.status_code!=201 for x in responses):raise RuntimeError([(x.status_code,x.text) for x in responses])
 result={"workspace":created.json(),"workspaces":[x for x in client.get("/api/workspaces").json() if x["id"]==wid],"storyline":story.json(),"storylines":client.get(f"/api/workspaces/{wid}/projects/{project}/storylines").json(),"branch":branch.json(),"branches":client.get(f"/api/workspaces/{wid}/projects/{project}/storylines/{sid}/branches").json(),"invalid":client.get(f"/api/workspaces/other/projects/{project}/storylines").status_code}
 for value in result.values():
  rows=value if isinstance(value,list) else [value] if isinstance(value,dict) else []
  for row in rows:row.pop("created_at",None);row.pop("updated_at",None)
 return result
postgres=execute(PostgresScopeRepository(lambda:psycopg.connect(url)));local=execute(FileScopeRepository(Path(tempfile.mkdtemp())));results={k:postgres[k]==local[k] for k in postgres};artifact={"file_api":"REAL_VERIFIED","postgres_api":"REAL_VERIFIED","workspace_api":"MATCH" if results["workspace"] and results["workspaces"] else "MISMATCH","storyline_api":"MATCH" if results["storyline"] and results["storylines"] else "MISMATCH","branch_api":"MATCH" if results["branch"] and results["branches"] else "MISMATCH","scope_validation":"MATCH" if results["invalid"] else "MISMATCH","overall_api_backend_parity":"MATCH" if all(results.values()) else "MISMATCH"};print(json.dumps(artifact,sort_keys=True))
if not all(results.values()):raise SystemExit(1)
