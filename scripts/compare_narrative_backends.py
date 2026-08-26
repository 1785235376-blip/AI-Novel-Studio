import json,os,tempfile,uuid
from pathlib import Path
import psycopg
from dotenv import load_dotenv
from app.narrative import Foreshadowing,NarrativeEvent,PlotThread
from app.repositories.file.narrative import FileNarrativeRepository
from app.repositories.postgres.narrative import PostgresNarrativeRepository
from app.services.narrative_state_service import NarrativeStateService

load_dotenv();url=os.environ["DATABASE_URL"].replace("postgresql+psycopg://","postgresql://");project=str(uuid.uuid4())
file=NarrativeStateService(FileNarrativeRepository(Path(tempfile.mkdtemp())));pg=NarrativeStateService(PostgresNarrativeRepository(lambda:psycopg.connect(url)))
thread=PlotThread(f"thread-{project}",project,"Investigation");foreshadow=Foreshadowing(f"shadow-{project}",project,"Locked door")
event1=NarrativeEvent(f"event1-{project}",project,"THREAD_PROGRESS",thread.id,"chapter:1",(f"ev1-{project}",),{"progress":"clue"})
event2=NarrativeEvent(f"event2-{project}",project,"FORESHADOWING_PROGRESS",foreshadow.id,"chapter:2",(f"ev2-{project}",),{"progress":"developed"})
for service in (file,pg):
 service.create_thread(thread);service.create_foreshadowing(foreshadow)
 service.transition_thread(project,thread.id,"RESOLVED",event1)
 service.transition_foreshadowing(project,foreshadow.id,"DEVELOPING",event2)
a=file.state(project);b=pg.state(project)
result={kind:"MATCH" if a[kind]==b[kind] else "MISMATCH" for kind in a};result["overall"]="MATCH" if all(x=="MATCH" for x in result.values()) else "MISMATCH"
print(json.dumps(result,sort_keys=True))
