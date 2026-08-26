from app.lore.continuity import Certainty, TimelineEvent
from app.repositories.file.continuity import FileContinuityRepository
from app.services.continuity_finding_service import ContinuityFindingService


def test_resolve_and_redetection_reopens_same_finding(tmp_path):
    service=ContinuityFindingService(FileContinuityRepository(tmp_path),enabled=True)
    event=TimelineEvent(id="e",project_id="p",event_type="X",title="X",start_time="z",end_time="a",certainty=Certainty.CONFIRMED)
    first=service.run_checks("p",events=[event])[0]
    assert service.resolve("p",first.id)["status"]=="RESOLVED"
    second=service.run_checks("p",events=[event])[0]
    assert second.id==first.id
    assert service.get_finding(first.id)["status"]=="OPEN"


def test_lifecycle_project_isolation(tmp_path):
    service=ContinuityFindingService(FileContinuityRepository(tmp_path),enabled=True)
    event=TimelineEvent(id="e",project_id="p",event_type="X",title="X",start_time="z",end_time="a")
    finding=service.run_checks("p",events=[event])[0]
    try: service.resolve("other",finding.id)
    except KeyError: pass
    else: raise AssertionError("cross-project resolve must fail")
