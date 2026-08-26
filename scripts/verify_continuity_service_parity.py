import json, os, tempfile, uuid
from pathlib import Path
import psycopg
from dotenv import load_dotenv
from app.lore.continuity import Certainty, CharacterKnowledge, CharacterLocationState, KnowledgeState, LocationState, RelationshipState, TimelineEvent
from app.repositories.file.continuity import FileContinuityRepository
from app.repositories.postgres.continuity import PostgresContinuityRepository
from app.services.continuity_finding_service import ContinuityFindingService

load_dotenv(); url=os.environ["DATABASE_URL"].replace("postgresql+psycopg://","postgresql://"); project=f"service-parity-{uuid.uuid4().hex}"
file=ContinuityFindingService(FileContinuityRepository(Path(tempfile.mkdtemp())),enabled=True)
pg=ContinuityFindingService(PostgresContinuityRepository(lambda:psycopg.connect(url)),enabled=True)
events=[TimelineEvent(id=f"event-{project}",project_id=project,event_type="X",title="X",start_time="day-2",end_time="day-1",certainty=Certainty.CONFIRMED,evidence_ids=[f"ev-t-{project}"])]
locations=[CharacterLocationState(id=f"la-{project}",project_id=project,character_id="c",location_id="a",valid_from_event_id="e",state=LocationState.PRESENT,certainty=Certainty.CONFIRMED,evidence_ids=[f"ev-la-{project}"]),CharacterLocationState(id=f"lb-{project}",project_id=project,character_id="c",location_id="b",valid_from_event_id="e",state=LocationState.PRESENT,certainty=Certainty.CONFIRMED,evidence_ids=[f"ev-lb-{project}"])]
travel=[CharacterLocationState(id=f"ta-{project}",project_id=project,character_id="traveler",location_id="port",valid_from_event_id="t1",valid_to_event_id="t2",state=LocationState.PRESENT,certainty=Certainty.CONFIRMED,evidence_ids=[f"ev-ta-{project}"]),CharacterLocationState(id=f"tb-{project}",project_id=project,character_id="traveler",location_id="mountain",valid_from_event_id="t2",state=LocationState.PRESENT,certainty=Certainty.CONFIRMED,evidence_ids=[f"ev-tb-{project}"])]
relationships=[RelationshipState(id=f"ra-{project}",project_id=project,source_character_id="a",target_character_id="b",relationship_type="ALLY",valid_from_event_id="r1",certainty=Certainty.CONFIRMED,evidence_ids=[f"ev-ra-{project}"]),RelationshipState(id=f"rb-{project}",project_id=project,source_character_id="a",target_character_id="b",relationship_type="ENEMY",valid_from_event_id="r1",certainty=Certainty.CONFIRMED,evidence_ids=[f"ev-rb-{project}"])]
knowledge=[CharacterKnowledge(id=f"k-{project}",project_id=project,character_id="c",subject_type="FACT",subject_id="secret",knowledge_state=KnowledgeState.UNKNOWN),CharacterKnowledge(id=f"false-{project}",project_id=project,character_id="c",subject_type="FACT",subject_id="belief",knowledge_state=KnowledgeState.FALSE_BELIEF,evidence_ids=[f"ev-false-{project}"])]
def run(service):
 rows=[x.model_dump(mode="json") for x in service.run_checks(project,events=events,locations=locations+travel,relationships=relationships,knowledge=knowledge,used_subject_ids={"secret"},travel_times={("port","mountain"):5},canon_facts={"canon":True},asserted_facts={"canon":False,"belief":True},evidence_required_subjects={"required"})]
 for row in rows: row.pop("created_at",None); row.pop("resolved_at",None)
 return rows
a=run(file); b=run(pg); target=a[0]["id"]; file.resolve(project,target); pg.resolve(project,target); resolved=file.get_finding(target)["status"]==pg.get_finding(target)["status"]=="RESOLVED"; run(file); run(pg); reopened=file.get_finding(target)["status"]==pg.get_finding(target)["status"]=="OPEN"
print(json.dumps({"service":"MATCH" if a==b else "MISMATCH","rules":[x["finding_type"] for x in a],"idempotent":len(run(pg))==len(a),"lifecycle":"MATCH" if resolved and reopened else "MISMATCH"},sort_keys=True))
