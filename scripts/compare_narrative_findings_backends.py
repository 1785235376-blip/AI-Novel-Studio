import json,os,tempfile,uuid
from pathlib import Path
import psycopg
from dotenv import load_dotenv
from app.narrative_detection import NarrativeExpectation,NarrativeRuleContext
from app.repositories.file.narrative import FileNarrativeRepository
from app.repositories.postgres.narrative import PostgresNarrativeRepository
from app.services.narrative_finding_service import NarrativeFindingService
load_dotenv();url=os.environ["DATABASE_URL"].replace("postgresql+psycopg://","postgresql://");project=str(uuid.uuid4())
file=NarrativeFindingService(FileNarrativeRepository(Path(tempfile.mkdtemp())));pg=NarrativeFindingService(PostgresNarrativeRepository(lambda:psycopg.connect(url)))
expectations=[NarrativeExpectation(f"thread-{project}",project,"THREAD","t","THREAD_PROGRESS_BY",2,("ev-t",),"chapter:1"),NarrativeExpectation(f"shadow-{project}",project,"FORESHADOWING","f","FORESHADOWING_PAYOFF_BY",2,("ev-f",),"chapter:1")]
for service in (file,pg):
 for e in expectations:service.create_expectation(e)
ctx=NarrativeRuleContext(project,3,expectations)
a=[vars(x) for x in file.run_checks(ctx)];b=[vars(x) for x in pg.run_checks(ctx)];target=a[0]["id"]
file.resolve(project,target);pg.resolve(project,target);resolved=file.list_findings(project)==pg.list_findings(project);file.run_checks(ctx);pg.run_checks(ctx);reopened=file.list_findings(project)==pg.list_findings(project)
print(json.dumps({"rules":"MATCH" if a==b else "MISMATCH","resolved":"MATCH" if resolved else "MISMATCH","reopened":"MATCH" if reopened else "MISMATCH"},sort_keys=True,default=str))
