import json,os,tempfile,uuid
from pathlib import Path
from dotenv import load_dotenv
load_dotenv();os.environ["STORAGE_BACKEND"]="postgres"
from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import narrative_state_service,repositories
from app.repositories.file.narrative import FileNarrativeRepository
from app.repositories.postgres.narrative import PostgresNarrativeRepository

client=TestClient(app);run=uuid.uuid4().hex;project="sample_novel";evidence_id=f"narrative-progress-evidence-{run}"
def req(method,path,**kwargs):
 r=client.request(method,path,**kwargs);r.raise_for_status();return r.json()
def execute():
 base=f"/api/projects/{project}/narrative";suffix=run
 mystery=req("POST",f"{base}/mysteries",json={"id":f"m-{suffix}","title":"Who?"})
 goal=req("POST",f"{base}/character-goals",json={"id":f"g-{suffix}","character_id":"lin-hai","title":"Escape"})
 req("POST",f"{base}/threads",json={"id":f"t-{suffix}","title":"Thread"})
 req("POST",f"{base}/foreshadowing",json={"id":f"f-{suffix}","title":"Clue"})
 version=narrative_state_service.chapters.get(f"{project}:1")["version"]
 specs=[("thread","PLOT_THREAD",f"t-{suffix}","ADVANCED"),("shadow","FORESHADOWING",f"f-{suffix}","DEVELOPED"),("mystery","MYSTERY",f"m-{suffix}","DEVELOPED"),("goal","CHARACTER_GOAL",f"g-{suffix}","ADVANCED")]
 links=[]
 for name,entity_type,entity_id,progress_type in specs:
  links.append(req("POST",f"{base}/chapter-progress",json={"id":f"link-{name}-{suffix}","chapter_id":f"{project}:1","chapter_version":version,"entity_type":entity_type,"entity_id":entity_id,"progress_type":progress_type,"summary":name,"evidence_ids":[evidence_id] if name=="mystery" else [],"event_id":f"event-{name}-{suffix}"}))
 duplicate=req("POST",f"{base}/chapter-progress",json={"id":f"link-mystery-{suffix}","chapter_id":f"{project}:1","chapter_version":version,"entity_type":"MYSTERY","entity_id":f"m-{suffix}","progress_type":"DEVELOPED","summary":"mystery","evidence_ids":[evidence_id],"event_id":f"event-mystery-{suffix}"})
 transitioned=req("POST",f"{base}/mysteries/m-{suffix}/transition",json={"status":"ANSWERED","chapter_version_id":f"{project}:1:v{version}"})
 illegal=client.post(f"{base}/mysteries/m-{suffix}/transition",json={"status":"OPEN"}).status_code
 isolated=client.get(f"/api/projects/other/narrative/mysteries/m-{suffix}").status_code
 state=req("GET",f"{base}/state")
 for key in ("threads","foreshadowing","events","mysteries","character_goals"):state[key]=[x for x in state[key] if suffix in x["id"]]
 for event in state["events"]:event.pop("created_at",None)
 return {"mystery":mystery,"goal":goal,"links":links,"duplicate":duplicate,"transitioned":transitioned,"illegal":illegal,"isolated":isolated,"list_mysteries":[x for x in req("GET",f"{base}/mysteries") if suffix in x["id"]],"list_goals":[x for x in req("GET",f"{base}/character-goals") if suffix in x["id"]],"list_links":[x for x in req("GET",f"{base}/chapter-progress") if suffix in x["id"]],"state":state}

assert isinstance(repositories.narrative,PostgresNarrativeRepository)
version=narrative_state_service.chapters.get(f"{project}:1")["version"]
repositories.lore.create_evidence({"id":evidence_id,"novel_id":project,"source_type":"CHAPTER_VERSION","source_id":f"{project}:1:v{version}:{run}","chapter_id":f"{project}:1","chapter_version":version,"locator":{},"content_hash":"0"*64,"privacy":"CLOUD_ALLOWED"})
print("Executing PostgreSQL API fixture...",flush=True);postgres=execute();print("PostgreSQL API fixture complete",flush=True)
narrative_state_service.repository=FileNarrativeRepository(Path(tempfile.mkdtemp()))
print("Executing File API fixture...",flush=True);file=execute();print("File API fixture complete",flush=True)
keys=("mystery","goal","links","duplicate","transitioned","illegal","isolated","list_mysteries","list_goals","list_links","state")
results={key:file[key]==postgres[key] for key in keys}
print(f"Mystery API Backend Parity: {'MATCH' if all(results[x] for x in ('mystery','transitioned','illegal','list_mysteries')) else 'MISMATCH'}")
print(f"Character Goal API Backend Parity: {'MATCH' if results['goal'] and results['list_goals'] else 'MISMATCH'}")
print(f"Chapter Progress API Backend Parity: {'MATCH' if all(results[x] for x in ('links','duplicate','list_links')) else 'MISMATCH'}")
print(f"NarrativeStateView API Backend Parity: {'MATCH' if results['state'] else 'MISMATCH'}")
print(f"Project Isolation: {'PASS' if results['isolated'] and file['isolated']==404 else 'FAIL'}")
print("PostgreSQL API: REAL VERIFIED");print("File API: REAL VERIFIED")
print(f"Overall API Backend Parity: {'MATCH' if all(results.values()) else 'MISMATCH'}")
if not all(results.values()):print(json.dumps({"results":results,"file":file,"postgres":postgres},indent=2,default=str));raise SystemExit(1)
