from fastapi.testclient import TestClient

from app.dependencies import narrative_state_service
from app.main import app
from app.repositories.file.narrative import FileNarrativeRepository
import pytest


class Chapters:
    def get(self,chapter_id):
        if chapter_id!="p:1":raise FileNotFoundError(chapter_id)
        return {"id":chapter_id,"novel_id":"p","version":2}
class Novels:
    def get_data_set(self,project,kind):return [{"id":"char"}] if project=="p" else []
class Lore:
    def get_evidence(self,evidence_id):return {"id":evidence_id,"novel_id":"other" if evidence_id=="cross" else "p"}


@pytest.mark.file_backend_only
def test_narrative_progress_api_and_project_isolation(tmp_path):
    original=(narrative_state_service.repository,narrative_state_service.chapters,narrative_state_service.novels,narrative_state_service.lore)
    narrative_state_service.repository=FileNarrativeRepository(tmp_path);narrative_state_service.chapters=Chapters();narrative_state_service.novels=Novels();narrative_state_service.lore=Lore();client=TestClient(app)
    try:
        assert client.post("/api/projects/p/narrative/mysteries",json={"id":"m","title":"Who?"}).status_code==201
        assert client.post("/api/projects/p/narrative/character-goals",json={"id":"g","character_id":"char","title":"Escape"}).status_code==201
        assert client.get("/api/projects/p/narrative/mysteries/m").status_code==200
        assert client.get("/api/projects/other/narrative/mysteries/m").status_code==404
        assert client.post("/api/projects/other/narrative/mysteries/m/transition",json={"status":"ANSWERED"}).status_code==404
        payload={"id":"link","chapter_id":"p:1","chapter_version":2,"entity_type":"MYSTERY","entity_id":"m","progress_type":"ANSWERED","summary":"Answer","evidence_ids":["evidence"],"event_id":"event"}
        assert client.post("/api/projects/p/narrative/chapter-progress",json=payload).status_code==201
        assert client.get("/api/projects/p/narrative/mysteries/m").json()["status"]=="ANSWERED"
        assert client.post("/api/projects/p/narrative/chapter-progress",json=payload).status_code==201
        assert len(client.get("/api/projects/p/narrative/chapter-progress").json())==1
        assert client.post("/api/projects/p/narrative/mysteries/m/transition",json={"status":"OPEN"}).status_code==400
        assert client.post("/api/projects/p/narrative/chapter-progress",json={**payload,"id":"bad-version","event_id":"bad-version","chapter_version":1}).status_code==400
        assert client.post("/api/projects/p/narrative/chapter-progress",json={**payload,"id":"bad-evidence","event_id":"bad-evidence","evidence_ids":["cross"]}).status_code==400
        state=client.get("/api/projects/p/narrative/state").json();assert state["mysteries"][0]["status"]=="ANSWERED" and state["character_goals"][0]["status"]=="ACTIVE"
    finally:
        narrative_state_service.repository,narrative_state_service.chapters,narrative_state_service.novels,narrative_state_service.lore=original
