from fastapi.testclient import TestClient
from app.dependencies import narrative_state_service
from app.main import app
from app.repositories.file.narrative import FileNarrativeRepository
import pytest


@pytest.mark.file_backend_only
def test_narrative_api_create_transition_and_state(tmp_path):
    narrative_state_service.repository=FileNarrativeRepository(tmp_path);client=TestClient(app)
    assert client.post("/api/projects/p/narrative/threads",json={"id":"t","title":"Thread"}).status_code==201
    body={"status":"RESOLVED","event_id":"e","event_type":"THREAD_PROGRESS","chapter_version_id":"chapter:1","evidence_ids":["ev"]}
    assert client.post("/api/projects/p/narrative/threads/t/transition",json=body).status_code==200
    state=client.get("/api/projects/p/narrative/state").json()
    assert state["threads"][0]["status"]=="RESOLVED" and state["events"][0]["chapter_version_id"]=="chapter:1"


@pytest.mark.file_backend_only
def test_narrative_api_project_isolation(tmp_path):
    narrative_state_service.repository=FileNarrativeRepository(tmp_path);client=TestClient(app)
    client.post("/api/projects/a/narrative/threads",json={"id":"t","title":"A"})
    assert client.get("/api/projects/b/narrative/state").json()["threads"]==[]
