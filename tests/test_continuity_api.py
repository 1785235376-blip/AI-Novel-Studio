from fastapi.testclient import TestClient

from app.config import settings
from app.dependencies import continuity_finding_service
from app.main import app
from app.repositories.file.continuity import FileContinuityRepository
import pytest


def _enable(tmp_path):
    object.__setattr__(settings, "enable_continuity_rules", True)
    continuity_finding_service.enabled = True
    continuity_finding_service.repository = FileContinuityRepository(tmp_path)


@pytest.mark.file_backend_only
def test_continuity_api_disabled(tmp_path):
    object.__setattr__(settings, "enable_continuity_rules", False)
    response = TestClient(app).post("/api/projects/p/continuity/checks", json={})
    assert response.status_code == 200
    assert response.json() == {"status": "DISABLED", "findings": []}


@pytest.mark.file_backend_only
def test_continuity_api_enabled_filters_detail_and_isolation(tmp_path):
    _enable(tmp_path); client=TestClient(app)
    body={"events":[{"id":"e","project_id":"p","event_type":"X","title":"X","start_time":"day-2","end_time":"day-1","certainty":"CONFIRMED","evidence_ids":["ev"]}]}
    first=client.post("/api/projects/p/continuity/checks",json=body).json(); second=client.post("/api/projects/p/continuity/checks",json=body).json()
    assert first["findings"][0]["id"]==second["findings"][0]["id"]
    fid=first["findings"][0]["id"]
    assert len(client.get("/api/projects/p/continuity/findings?finding_type=TIMELINE_ORDER_VIOLATION").json())==1
    assert client.get(f"/api/projects/p/continuity/findings/{fid}").status_code==200
    assert client.get(f"/api/projects/other/continuity/findings/{fid}").status_code==404
    assert client.post(f"/api/projects/p/continuity/findings/{fid}/resolve").json()["status"]=="RESOLVED"
    assert client.post(f"/api/projects/other/continuity/findings/{fid}/resolve").status_code==404


@pytest.mark.file_backend_only
def test_continuity_repository_failure_is_advisory(tmp_path):
    _enable(tmp_path)
    class Broken:
        def create(self,*args,**kwargs): raise RuntimeError("failure")
    continuity_finding_service.repository=Broken()
    response=TestClient(app).post("/api/projects/p/continuity/checks",json={"events":[{"project_id":"p","event_type":"X","title":"X","start_time":"z","end_time":"a"}]})
    assert response.status_code==200
    assert response.json()=={"status":"COMPLETED","findings":[]}


@pytest.mark.file_backend_only
def test_continuity_api_reports_world_rule_violation(tmp_path):
    _enable(tmp_path)
    client = TestClient(app)
    response = client.post(
        "/api/projects/novel-1/continuity/checks",
        json={
            "events": [{"id": "e1", "project_id": "novel-1", "event_type": "SCENE", "title": "永生仪式"}],
            "world_rules": [{
                "id": "rule-1",
                "payload": {"statement": "角色不能永生", "forbidden_terms": ["永生"]},
            }],
        },
    )
    assert response.status_code == 200
    findings = response.json()["findings"]
    assert any(item["finding_type"] == "WORLD_RULE_VIOLATION" for item in findings)
    finding = next(item for item in findings if item["finding_type"] == "WORLD_RULE_VIOLATION")
    assert finding["rule_id"] == "rule-1"
    assert "永生" in finding["evidence_ids"]
