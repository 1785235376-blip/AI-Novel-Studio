import json,os,uuid
import psycopg
from dotenv import load_dotenv
from app.repositories.postgres.narrative import PostgresNarrativeRepository

load_dotenv();url=os.environ["DATABASE_URL"].replace("postgresql+psycopg://","postgresql://");repository=PostgresNarrativeRepository(lambda:psycopg.connect(url));run=uuid.uuid4().hex;project=f"atomic-{run}"
mystery={"id":f"m-{run}","project_id":project,"title":"Who?","description":"","status":"OPEN","opened_chapter_version_id":None,"answered_chapter_version_id":None}
repository.create(project,"mysteries",mystery)
event={"id":f"event-{run}","project_id":project,"event_type":"TEST","subject_id":"other","chapter_version_id":"x:1:v1","evidence_ids":[],"payload":{},"created_at":"2026-01-01T00:00:00+00:00","fingerprint":f"fingerprint-{run}"}
repository.create(project,"events",event)
updated={**mystery,"status":"DEVELOPING"};conflicting={**event,"subject_id":mystery["id"],"fingerprint":f"different-{run}"};link={"id":f"link-{run}","project_id":project,"chapter_id":"x:1","chapter_version":1,"entity_type":"MYSTERY","entity_id":mystery["id"],"progress_type":"DEVELOPED","summary":"","evidence_ids":[],"event_id":event["id"]}
failed=False
try:repository.record_progress(project,"mysteries",mystery["id"],updated,conflicting,link)
except psycopg.errors.UniqueViolation:failed=True
preserved=repository.get(project,"mysteries",mystery["id"])["status"]=="OPEN" and repository.list(project,"chapter_links")==[]
print(json.dumps({"forced_failure":"PASS" if failed else "FAIL","transaction_atomicity":"PASS" if failed and preserved else "FAIL","rollback_preservation":"PASS" if preserved else "FAIL","postgres_persistence":"REAL_VERIFIED"},sort_keys=True))
if not failed or not preserved:raise SystemExit(1)
