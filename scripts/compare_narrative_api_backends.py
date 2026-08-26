import json,os,tempfile,uuid
from pathlib import Path
from dotenv import load_dotenv
load_dotenv();os.environ["STORAGE_BACKEND"]="postgres"
from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import narrative_state_service,repositories
from app.repositories.file.narrative import FileNarrativeRepository
from app.repositories.postgres.narrative import PostgresNarrativeRepository

client=TestClient(app);run=uuid.uuid4().hex
def execute(project):
 client.post(f"/api/projects/{project}/narrative/threads",json={"id":f"t-{run}","title":"Thread"}).raise_for_status()
 client.post(f"/api/projects/{project}/narrative/foreshadowing",json={"id":f"f-{run}","title":"Door","thread_id":f"t-{run}"}).raise_for_status()
 event={"status":"RESOLVED","event_id":f"e-{run}","event_type":"THREAD_PROGRESS","chapter_version_id":"chapter:1","evidence_ids":[f"ev-{run}"]}
 client.post(f"/api/projects/{project}/narrative/threads/t-{run}/transition",json=event).raise_for_status()
 return client.get(f"/api/projects/{project}/narrative/state").json()

assert isinstance(repositories.narrative,PostgresNarrativeRepository)
project=str(uuid.uuid4());pg=execute(project)
narrative_state_service.repository=FileNarrativeRepository(Path(tempfile.mkdtemp()));file=execute(project)
for state in (pg,file):
 for event in state["events"]: event.pop("created_at",None)
print(json.dumps({"postgres_routing":"PASS","api_visible":"MATCH" if file==pg else "MISMATCH","project_isolation":"PASS" if client.get(f"/api/projects/{uuid.uuid4()}/narrative/state").json()["threads"]==[] else "FAIL"},sort_keys=True))
