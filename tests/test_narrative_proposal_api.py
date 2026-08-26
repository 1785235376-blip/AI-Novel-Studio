from fastapi.testclient import TestClient

from app.dependencies import narrative_proposal_service,narrative_state_service
from app.main import app
from app.repositories.file.narrative import FileNarrativeRepository
import pytest


class Chapters:
    def get(self,chapter_id):
        if chapter_id!="p:1":raise FileNotFoundError(chapter_id)
        return {"id":chapter_id,"novel_id":"p","version":2}


@pytest.mark.file_backend_only
def test_proposal_api_lifecycle_and_project_isolation(tmp_path):
    original=(narrative_state_service.repository,narrative_state_service.chapters,narrative_proposal_service.repository)
    repository=FileNarrativeRepository(tmp_path);narrative_state_service.repository=repository;narrative_state_service.chapters=Chapters();narrative_proposal_service.repository=repository;client=TestClient(app)
    try:
        client.post("/api/projects/p/narrative/mysteries",json={"id":"m","title":"Who?"}).raise_for_status()
        body={"id":"proposal","proposal_type":"MYSTERY_ANSWERED","subject_type":"MYSTERY","subject_id":"m","chapter_version_id":"p:1:v2","payload":{"answer_summary":"The answer"},"evidence_ids":[]}
        created=client.post("/api/projects/p/narrative/proposals",json=body);assert created.status_code==201 and created.json()["status"]=="PENDING"
        assert client.post("/api/projects/p/narrative/proposals",json={**body,"id":"duplicate"}).json()["id"]=="proposal"
        assert client.get("/api/projects/other/narrative/proposals/proposal").status_code==404
        accepted=client.post("/api/projects/p/narrative/proposals/proposal/accept");assert accepted.status_code==200 and accepted.json()["status"]=="ACCEPTED"
        assert client.post("/api/projects/p/narrative/proposals/proposal/accept").status_code==200
        assert client.post("/api/projects/p/narrative/proposals/proposal/reject").status_code==400
        assert client.get("/api/projects/p/narrative/state").json()["mysteries"][0]["status"]=="ANSWERED"
    finally:narrative_state_service.repository,narrative_state_service.chapters,narrative_proposal_service.repository=original
