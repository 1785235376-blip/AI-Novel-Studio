import json, os, tempfile, uuid
from pathlib import Path
import psycopg
from dotenv import load_dotenv
from app.repositories.file.continuity import FileContinuityRepository
from app.repositories.postgres.continuity import PostgresContinuityRepository

load_dotenv(); url=os.environ["DATABASE_URL"].replace("postgresql+psycopg://","postgresql://")
run_id=uuid.uuid4().hex; novel_id=str(uuid.uuid4())
with psycopg.connect(url) as conn:
 conn.execute("INSERT INTO novels(id,slug,title) VALUES (%s,%s,%s)",(novel_id,f"continuity-parity-{run_id}","Continuity Parity")); conn.commit()
pg=PostgresContinuityRepository(lambda:psycopg.connect(url)); file=FileContinuityRepository(Path(tempfile.mkdtemp()))
project=novel_id
fixtures={
 "timeline":{"id":str(uuid.uuid4()),"project_id":project,"novel_id":project,"event_type":"PARITY","title":"Parity","start_time":"day-1","sequence_index":1,"evidence_ids":[f"ev-t-{run_id}"]},
 "locations":{"id":f"loc-{run_id}","project_id":project,"character_id":f"char-a-{run_id}","location_id":"harbor","evidence_ids":[f"ev-l-{run_id}"]},
 "relationships":{"id":f"rel-{run_id}","project_id":project,"source_character_id":f"char-a-{run_id}","target_character_id":f"char-b-{run_id}","relationship_type":"ALLY","evidence_ids":[f"ev-r-{run_id}"]},
 "canon_dependencies":{"id":f"canon-{run_id}","project_id":project,"source_canon_id":f"a-{run_id}","target_canon_id":f"b-{run_id}","dependency_type":"REQUIRES","evidence_ids":[f"ev-c-{run_id}"]},
 "knowledge":{"id":f"knowledge-{run_id}","project_id":project,"character_id":f"char-a-{run_id}","subject_type":"FACT","subject_id":f"fact-{run_id}","knowledge_state":"UNKNOWN","evidence_ids":[f"ev-k-{run_id}"]},
 "findings":{"id":f"finding-{run_id}","project_id":project,"finding_type":"CHARACTER_KNOWLEDGE_LEAK","severity":"LOW","status":"OPEN","description":"Parity","evidence_ids":[f"ev-f-{run_id}"]},
}
result={}
for kind,payload in fixtures.items():
 file.create(kind,payload); pg.create(kind,payload)
 result[kind]="MATCH" if file.get_by_id(kind,payload["id"])==pg.get_by_id(kind,payload["id"]) and file.list_by_evidence(kind,payload["evidence_ids"][0])==pg.list_by_evidence(kind,payload["evidence_ids"][0]) else "MISMATCH"
result["overall"]="MATCH" if all(v=="MATCH" for v in result.values()) else "MISMATCH"
print(json.dumps(result,sort_keys=True))
