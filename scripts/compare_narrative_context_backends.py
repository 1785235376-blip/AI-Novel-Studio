import json,os,tempfile,uuid
from pathlib import Path
import psycopg
from dotenv import load_dotenv
from app.narrative_context import NarrativeContextBuilder
from app.repositories.file.narrative import FileNarrativeRepository
from app.repositories.postgres.narrative import PostgresNarrativeRepository

load_dotenv();url=os.environ["DATABASE_URL"].replace("postgresql+psycopg://","postgresql://");run=uuid.uuid4().hex;project=f"context-{run}"
def populate(repository):
 t=f"t-{run}";f=f"f-{run}";m=f"m-{run}";g=f"g-{run}";event=f"et-{run}";rows={"threads":[{"id":t,"project_id":project,"title":"Thread","status":"OPEN","event_ids":[event]}],"foreshadowing":[{"id":f,"project_id":project,"title":"Clue","status":"DEVELOPING"}],"mysteries":[{"id":m,"project_id":project,"title":"Who?","status":"OPEN"}],"character_goals":[{"id":g,"project_id":project,"character_id":"hero","title":"Escape","status":"ACTIVE"}],"events":[{"id":event,"project_id":project,"subject_id":t,"event_type":"PLOT_THREAD:ADVANCED","chapter_version_id":f"{project}:1:v1","evidence_ids":["ev"],"payload":{"summary":"Advanced"},"created_at":"2026-01-01T00:00:00+00:00","fingerprint":f"fp-{run}"}],"chapter_links":[{"id":f"link-{run}","project_id":project,"chapter_id":f"{project}:1","chapter_version":1,"entity_type":"MYSTERY","entity_id":m,"progress_type":"DEVELOPED","event_id":f"other-{run}","summary":"","evidence_ids":[]}],"expectations":[{"id":f"expect-{run}","project_id":project,"subject_type":"MYSTERY","subject_id":m,"expectation_type":"MYSTERY_ANSWER_BY","deadline_chapter":2,"active":True,"source_chapter_version_id":f"{project}:1:v1","evidence_ids":["ev"]}],"findings":[{"id":f"finding-{run}","project_id":project,"finding_type":"MYSTERY_OVERDUE","subject_id":m,"description":"Overdue","severity":"MEDIUM","status":"OPEN","evidence_ids":["ev"],"source_chapter_version_id":f"{project}:1:v1"},{"id":f"old-{run}","project_id":project,"finding_type":"THREAD_STALE","subject_id":t,"description":"Old","severity":"MEDIUM","status":"RESOLVED","evidence_ids":[]}]}
 for kind,items in rows.items():
  for item in items:repository.create(project,kind,item)
def execute(repository):
 before={kind:repository.list(project,kind) for kind in ("threads","foreshadowing","events","mysteries","character_goals","chapter_links","expectations","findings")};builder=NarrativeContextBuilder(repository,320);views=[builder.build(project,f"{project}:1",1,["hero"]).model_dump(mode="json") for _ in range(3)];after={kind:repository.list(project,kind) for kind in before};return {"view":views[0],"deterministic":views[0]==views[1]==views[2],"read_only":before==after,"serialized":json.dumps(views[0],ensure_ascii=False,sort_keys=True,separators=(",",":"))}
file_root=Path(tempfile.mkdtemp());file_repository=FileNarrativeRepository(file_root);postgres_repository=PostgresNarrativeRepository(lambda:psycopg.connect(url));populate(file_repository);populate(postgres_repository);file=execute(file_repository);postgres=execute(postgres_repository)
file_restart=execute(FileNarrativeRepository(file_root));postgres_restart=execute(PostgresNarrativeRepository(lambda:psycopg.connect(url)));matched=file==postgres==file_restart==postgres_restart
print("File Narrative Context: REAL VERIFIED");print("PostgreSQL Narrative Context: REAL VERIFIED");print(f"NarrativeContextView Backend Parity: {'MATCH' if matched else 'MISMATCH'}");print(f"Narrative Context Serialized Parity: {'MATCH' if matched else 'MISMATCH'}");print(f"Determinism: {'PASS' if file['deterministic'] and postgres['deterministic'] else 'FAIL'}");print(f"Authoritative Mutation: {'NONE' if file['read_only'] and postgres['read_only'] else 'FOUND'}")
if not matched:raise SystemExit(1)
