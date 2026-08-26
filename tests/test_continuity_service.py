from pathlib import Path

from app.lore.continuity import Certainty, TimelineEvent
from app.repositories.file.continuity import FileContinuityRepository
from app.services.continuity_finding_service import ContinuityFindingService


def test_disabled_service_preserves_legacy_behavior(tmp_path: Path):
    service = ContinuityFindingService(FileContinuityRepository(tmp_path), enabled=False)
    event = TimelineEvent(project_id="p", event_type="x", title="x", start_time="b", end_time="a")
    assert service.run_checks("p", events=[event]) == []


def test_enabled_service_persists_advisory_finding(tmp_path: Path):
    service = ContinuityFindingService(FileContinuityRepository(tmp_path), enabled=True)
    event = TimelineEvent(project_id="p", event_type="x", title="x", start_time="day-2", end_time="day-1", certainty=Certainty.CONFIRMED)
    findings = service.run_checks("p", events=[event])
    assert findings[0].finding_type == "TIMELINE_ORDER_VIOLATION"
    assert service.list_findings("p")[0]["status"] == "OPEN"
