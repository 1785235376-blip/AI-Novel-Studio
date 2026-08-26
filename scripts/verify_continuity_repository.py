import json
import os
import uuid
import psycopg
from dotenv import load_dotenv
from app.repositories.postgres.continuity import PostgresContinuityRepository

load_dotenv()
url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
repo = PostgresContinuityRepository(lambda: psycopg.connect(url))
project = "codex-continuity-verification"
with psycopg.connect(url) as conn:
    row = conn.execute("SELECT id FROM novels ORDER BY id LIMIT 1").fetchone()
    if row is None:
        novel_id = str(uuid.uuid4())
        conn.execute("INSERT INTO novels(id,slug,title) VALUES (%s,%s,%s)",(novel_id,"continuity-verification","Continuity Verification"))
        conn.commit()
    else:
        novel_id = str(row[0])

fixtures = {
    "timeline": {"id": str(uuid.uuid4()), "project_id": novel_id, "novel_id": novel_id, "event_type": "VERIFY", "title": "Verification event", "start_time": "day-1", "sequence_index": 1, "evidence_ids": ["ev-t"]},
    "locations": {"id": str(uuid.uuid4()), "project_id": project, "character_id": "char-a", "location_id": "harbor", "evidence_ids": ["ev-a"]},
    "relationships": {"id": str(uuid.uuid4()), "project_id": project, "source_character_id": "char-a", "target_character_id": "char-b", "relationship_type": "ALLY", "evidence_ids": ["ev-b"]},
    "canon_dependencies": {"id": str(uuid.uuid4()), "project_id": project, "source_canon_id": "canon-a", "target_canon_id": "canon-b", "dependency_type": "REQUIRES", "evidence_ids": []},
    "knowledge": {"id": str(uuid.uuid4()), "project_id": project, "character_id": "char-a", "subject_type": "FACT", "subject_id": "fact-a", "knowledge_state": "UNKNOWN", "evidence_ids": ["ev-c"]},
    "findings": {"id": "fingerprint-verification", "project_id": project, "finding_type": "CHARACTER_KNOWLEDGE_LEAK", "severity": "LOW", "status": "OPEN", "description": "verification", "evidence_ids": ["ev-c"]},
}
results = {}
for kind, payload in fixtures.items():
    created = repo.create(kind, payload)
    repeated = repo.create(kind, payload)
    results[kind] = {
        "create": created == payload,
        "idempotent": repeated == payload,
        "get": repo.get_by_id(kind, payload["id"]) == payload,
        "project": payload in repo.list_by_project(kind, payload["project_id"]),
        "evidence": not payload.get("evidence_ids") or payload in repo.list_by_evidence(kind, payload["evidence_ids"][0]),
    }
print(json.dumps(results, ensure_ascii=False, sort_keys=True))
