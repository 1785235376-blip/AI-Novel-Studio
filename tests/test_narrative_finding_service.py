from app.narrative_detection import *
from app.repositories.file.narrative import FileNarrativeRepository
from app.services.narrative_finding_service import NarrativeFindingService

def test_narrative_finding_lifecycle_and_identity(tmp_path):
 service=NarrativeFindingService(FileNarrativeRepository(tmp_path));e=NarrativeExpectation("e","p","THREAD","t","THREAD_PROGRESS_BY",2)
 service.create_expectation(e);ctx=NarrativeRuleContext("p",3,[e])
 first=service.run_checks(ctx)[0];assert service.resolve("p",first.id)["status"]=="RESOLVED"
 second=service.run_checks(ctx)[0];assert second.id==first.id and service.list_findings("p")[0]["status"]=="OPEN"

def test_no_expectation_persists_no_finding(tmp_path):
 service=NarrativeFindingService(FileNarrativeRepository(tmp_path));assert service.run_checks(NarrativeRuleContext("p",20))==[];assert service.list_findings("p")==[]
