import json,os,tempfile,uuid
from pathlib import Path
import psycopg
from dotenv import load_dotenv
from fastapi.testclient import TestClient

load_dotenv()
from app.dependencies import narrative_proposal_service,narrative_state_service
from app.main import app
from app.repositories.file.narrative import FileNarrativeRepository
from app.repositories.postgres.narrative import PostgresNarrativeRepository

url=os.environ["DATABASE_URL"].replace("postgresql+psycopg://","postgresql://");run=uuid.uuid4().hex;project=f"proposal-api-{run}";subject=f"m-{run}";proposal=f"proposal-{run}";client=TestClient(app)
class Chapters:
 def get(self,chapter_id):return {"id":chapter_id,"novel_id":project,"version":1}
def execute(repository):
 narrative_state_service.repository=repository;narrative_state_service.chapters=Chapters();narrative_proposal_service.repository=repository;base=f"/api/projects/{project}/narrative"
 mystery=client.post(f"{base}/mysteries",json={"id":subject,"title":"Who?"});body={"id":proposal,"proposal_type":"MYSTERY_ANSWERED","subject_type":"MYSTERY","subject_id":subject,"chapter_version_id":f"{project}:1:v1","payload":{"answer_summary":"Answer"}}
 created=client.post(f"{base}/proposals",json=body);duplicate=client.post(f"{base}/proposals",json={**body,"id":f"duplicate-{run}"});pending_state=client.get(f"{base}/state").json();accepted=client.post(f"{base}/proposals/{proposal}/accept");again=client.post(f"{base}/proposals/{proposal}/accept");isolated=client.get(f"/api/projects/other/narrative/proposals/{proposal}").status_code
 responses=(mystery,created,duplicate,accepted,again)
 if any(x.status_code not in (200,201) for x in responses):raise RuntimeError([(x.status_code,x.text) for x in responses])
 result={"created":created.json(),"duplicate":duplicate.json(),"pending_event_count":len(pending_state["events"]),"accepted":accepted.json(),"again":again.json(),"isolated":isolated,"state":client.get(f"{base}/state").json(),"list":client.get(f"{base}/proposals").json()}
 for key in ("created","duplicate","accepted","again"):
  result[key].pop("created_at",None);result[key].pop("updated_at",None)
 for item in result["list"]:item.pop("created_at",None);item.pop("updated_at",None)
 for event in result["state"]["events"]:event.pop("created_at",None)
 return result
pg=PostgresNarrativeRepository(lambda:psycopg.connect(url));postgres=execute(pg);local=execute(FileNarrativeRepository(Path(tempfile.mkdtemp())));results={key:postgres[key]==local[key] for key in postgres};artifact={"postgresql_api":"REAL_VERIFIED","file_api":"REAL_VERIFIED","project_isolation":"PASS" if local["isolated"]==404 else "FAIL","pending_no_mutation":"PASS" if local["pending_event_count"]==0 else "FAIL","api_backend_parity":"MATCH" if all(results.values()) else "MISMATCH","results":results};print(json.dumps(artifact,sort_keys=True))
if not all(results.values()) or local["isolated"]!=404 or local["pending_event_count"]:raise SystemExit(1)
