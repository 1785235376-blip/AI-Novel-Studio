import json, os, uuid
import psycopg
from dotenv import load_dotenv
from app.repositories.postgres.narrative import PostgresNarrativeRepository

load_dotenv();url=os.environ["DATABASE_URL"].replace("postgresql+psycopg://","postgresql://");project=str(uuid.uuid4());repo=PostgresNarrativeRepository(lambda:psycopg.connect(url))
thread={"id":f"thread-{project}","project_id":project,"title":"Investigation","status":"OPEN","event_ids":[]}
foreshadow={"id":f"foreshadow-{project}","project_id":project,"title":"Locked door","status":"PLANTED"}
repo.create(project,"threads",thread);repo.create(project,"foreshadowing",foreshadow)
event={"id":f"event-{project}","project_id":project,"event_type":"THREAD_PROGRESS","subject_id":thread["id"],"chapter_version_id":"chapter:1","fingerprint":f"fp-{project}","evidence_ids":[f"ev-{project}"],"payload":{"progress":"clue"}}
updated=repo.transition(project,"threads",thread["id"],"RESOLVED",event)
before=repo.get(project,"threads",thread["id"]);event_count=len(repo.list(project,"events")) if False else None
rollback=False
try: repo.transition(project,"threads",thread["id"],"BROKEN",{"id":f"bad-{project}","chapter_version_id":"chapter:1","fingerprint":f"bad-{project}"})
except Exception: rollback=True
after=repo.get(project,"threads",thread["id"])
with psycopg.connect(url) as c: count=c.execute("select count(*) from narrative_events where project_id=%s",(project,)).fetchone()[0]
print(json.dumps({"project":project,"crud":updated["status"]=="RESOLVED","event_count":count,"rollback_exception":rollback,"rollback_preserved":after==before},sort_keys=True))
