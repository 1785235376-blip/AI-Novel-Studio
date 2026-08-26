import os,tempfile,uuid
from pathlib import Path
import psycopg
from dotenv import load_dotenv
from app.narrative_detection import NarrativeExpectation,NarrativeRuleContext,registry
from app.repositories.file.narrative import FileNarrativeRepository
from app.repositories.postgres.narrative import PostgresNarrativeRepository
from app.services.narrative_finding_service import NarrativeFindingService

load_dotenv();url=os.environ["DATABASE_URL"].replace("postgresql+psycopg://","postgresql://");run=uuid.uuid4().hex;project=f"phase2c-{run}"
def execute(repository):
 m=f"m-{run}";g=f"g-{run}";repository.create(project,"mysteries",{"id":m,"project_id":project,"title":"Who?","description":"","status":"OPEN","opened_chapter_version_id":None,"answered_chapter_version_id":None});repository.create(project,"character_goals",{"id":g,"project_id":project,"character_id":"c","title":"Escape","description":"","status":"ACTIVE","started_chapter_version_id":None,"completed_chapter_version_id":None})
 expectations=[NarrativeExpectation(f"me-{run}",project,"MYSTERY",m,"MYSTERY_ANSWER_BY",2,("ev-m",),"chapter:1"),NarrativeExpectation(f"ge-{run}",project,"CHARACTER_GOAL",g,"CHARACTER_GOAL_PROGRESS_BY",2,("ev-g",),"chapter:1")];service=NarrativeFindingService(repository)
 for item in expectations:service.create_expectation(item)
 ctx=lambda:NarrativeRuleContext(project,3,[NarrativeExpectation(**x) for x in repository.list(project,"expectations")],mysteries=repository.list(project,"mysteries"),character_goals=repository.list(project,"character_goals"),narrative_events=repository.list(project,"events"))
 first=[vars(x) for x in service.run_checks(ctx())];service.run_checks(ctx());stable=len(service.list_findings(project))==2
 repository.create(project,"chapter_links",{"id":f"orphan-{run}","project_id":project,"chapter_id":"x:1","chapter_version":1,"entity_type":"CHARACTER_GOAL","entity_id":g,"progress_type":"ADVANCED","event_id":"missing","summary":"","evidence_ids":[]});service.run_checks(ctx());link_only=next(x for x in service.list_findings(project) if x["finding_type"]=="CHARACTER_GOAL_STALE")["status"]=="OPEN"
 event={"id":f"event-{run}","project_id":project,"event_type":"CHARACTER_GOAL:ADVANCED","subject_id":g,"chapter_version_id":"x:1:v1","evidence_ids":[],"payload":{},"created_at":"2026-01-01T00:00:00+00:00","fingerprint":f"fp-{run}"};repository.create(project,"events",event);repository.update(project,"mysteries",m,{**repository.get(project,"mysteries",m),"status":"ANSWERED","answered_chapter_version_id":"x:1:v1"});service.run_checks(ctx());resolved=service.list_findings(project)
 return {"expectations":repository.list(project,"expectations"),"first":first,"stable":stable,"link_only":link_only,"resolved":resolved}
file=execute(FileNarrativeRepository(Path(tempfile.mkdtemp())));postgres=execute(PostgresNarrativeRepository(lambda:psycopg.connect(url)));matched=file==postgres
print(f"Registered Narrative Rules: {len(registry.rules)}");print(f"Rule Order: {'STABLE' if list(registry.rules)==['THREAD_STALE','FORESHADOWING_OVERDUE','MYSTERY_OVERDUE','CHARACTER_GOAL_STALE'] else 'UNSTABLE'}")
print(f"MYSTERY_OVERDUE Backend Parity: {'MATCH' if matched else 'MISMATCH'}");print(f"CHARACTER_GOAL_STALE Backend Parity: {'MATCH' if matched else 'MISMATCH'}");print(f"NarrativeEvent Progress Source: {'PASS' if file['link_only'] and postgres['link_only'] else 'FAIL'}");print(f"Overall Backend Parity: {'MATCH' if matched else 'MISMATCH'}")
if not matched:raise SystemExit(1)
