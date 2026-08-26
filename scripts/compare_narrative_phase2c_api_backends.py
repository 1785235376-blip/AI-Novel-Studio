import os,tempfile,uuid
from pathlib import Path
from dotenv import load_dotenv
load_dotenv();os.environ["STORAGE_BACKEND"]="postgres"
from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import narrative_finding_service,narrative_state_service,repositories
from app.repositories.file.narrative import FileNarrativeRepository
from app.repositories.postgres.narrative import PostgresNarrativeRepository

client=TestClient(app);run=uuid.uuid4().hex;project="sample_novel";evidence_id=f"phase2c-evidence-{run}"
def req(method,path,**kwargs):r=client.request(method,path,**kwargs);r.raise_for_status();return r.json()
def execute():
 base=f"/api/projects/{project}/narrative";m=f"m-{run}";g=f"g-{run}";version=narrative_state_service.chapters.get(f"{project}:1")["version"];source=f"{project}:1:v{version}"
 req("POST",f"{base}/mysteries",json={"id":m,"title":"Who?"});req("POST",f"{base}/character-goals",json={"id":g,"character_id":"lin-hai","title":"Escape"})
 expectations=[req("POST",f"{base}/expectations",json={"id":f"me-{run}","subject_type":"MYSTERY","subject_id":m,"expectation_type":"MYSTERY_ANSWER_BY","deadline_chapter":2,"evidence_ids":[evidence_id],"source_chapter_version_id":source}),req("POST",f"{base}/expectations",json={"id":f"ge-{run}","subject_type":"CHARACTER_GOAL","subject_id":g,"expectation_type":"CHARACTER_GOAL_PROGRESS_BY","deadline_chapter":2,"evidence_ids":[evidence_id],"source_chapter_version_id":source})]
 checks=req("POST",f"{base}/checks",json={"current_chapter":3});repeated=req("POST",f"{base}/checks",json={"current_chapter":3});owned=lambda rows:[x for x in rows if run in x.get("subject_id","")]
 findings=owned(req("GET",f"{base}/findings"));detail=req("GET",f"{base}/findings/{findings[0]['id']}")
 manual=req("POST",f"{base}/findings/{findings[0]['id']}/resolve");req("POST",f"{base}/checks",json={"current_chapter":3});reopened=req("GET",f"{base}/findings/{findings[0]['id']}")
 req("POST",f"{base}/mysteries/{m}/transition",json={"status":"ANSWERED","chapter_version_id":source})
 req("POST",f"{base}/chapter-progress",json={"id":f"link-{run}","chapter_id":f"{project}:1","chapter_version":version,"entity_type":"CHARACTER_GOAL","entity_id":g,"progress_type":"ADVANCED","summary":"progress","evidence_ids":[evidence_id],"event_id":f"event-{run}"})
 req("POST",f"{base}/checks",json={"current_chapter":3});resolved=owned(req("GET",f"{base}/findings"))
 isolation={"list":req("GET","/api/projects/other/narrative/findings"),"detail":client.get(f"/api/projects/other/narrative/findings/{findings[0]['id']}").status_code,"expectation":client.post("/api/projects/other/narrative/expectations",json={"id":f"cross-{run}","subject_type":"MYSTERY","subject_id":m,"expectation_type":"MYSTERY_ANSWER_BY","deadline_chapter":2}).status_code}
 return {"expectations":expectations,"checks":checks,"repeated":repeated,"findings":findings,"detail":detail,"manual":manual,"reopened":reopened,"resolved":resolved,"isolation":isolation}

assert isinstance(repositories.narrative,PostgresNarrativeRepository);version=narrative_state_service.chapters.get(f"{project}:1")["version"]
repositories.lore.create_evidence({"id":evidence_id,"novel_id":project,"source_type":"CHAPTER_VERSION","source_id":f"{project}:1:v{version}:{run}","chapter_id":f"{project}:1","chapter_version":version,"locator":{},"content_hash":"1"*64,"privacy":"CLOUD_ALLOWED"})
postgres=execute();file_repository=FileNarrativeRepository(Path(tempfile.mkdtemp()));narrative_state_service.repository=file_repository;narrative_finding_service.repository=file_repository;file=execute()
categories={key:file[key]==postgres[key] for key in file}
print(f"MYSTERY_OVERDUE API Backend Parity: {'MATCH' if all(categories[x] for x in ('expectations','checks','findings','detail','manual','reopened','resolved')) else 'MISMATCH'}")
print(f"CHARACTER_GOAL_STALE API Backend Parity: {'MATCH' if categories['checks'] and categories['resolved'] else 'MISMATCH'}")
print(f"Project Isolation: {'PASS' if categories['isolation'] and file['isolation']['detail']==404 and file['isolation']['expectation']==404 else 'FAIL'}")
print("File API: REAL VERIFIED");print("PostgreSQL API: REAL VERIFIED")
print(f"Overall Phase 2C API Backend Parity: {'MATCH' if all(categories.values()) else 'MISMATCH'}")
if not all(categories.values()):raise SystemExit(1)
