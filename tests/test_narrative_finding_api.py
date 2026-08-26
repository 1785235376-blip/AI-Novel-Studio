from fastapi.testclient import TestClient

from app.dependencies import narrative_finding_service, narrative_state_service
from app.main import app
from app.repositories.file.narrative import FileNarrativeRepository
import pytest


@pytest.mark.file_backend_only
def test_narrative_finding_api_lifecycle_and_isolation(tmp_path):
    original_finding_repository = narrative_finding_service.repository
    original_state_repository = narrative_state_service.repository
    repository = FileNarrativeRepository(tmp_path)
    narrative_finding_service.repository = repository
    narrative_state_service.repository = repository
    client = TestClient(app)
    try:
        for project in ("a", "b"):
            response = client.post(
                f"/api/projects/{project}/narrative/threads",
                json={"id": f"thread-{project}", "title": "Thread"},
            )
            assert response.status_code == 201
            response = client.post(
                f"/api/projects/{project}/narrative/expectations",
                json={
                    "id": f"expectation-{project}",
                    "subject_type": "THREAD",
                    "subject_id": f"thread-{project}",
                    "expectation_type": "THREAD_PROGRESS_BY",
                    "deadline_chapter": 2,
                    "evidence_ids": [f"evidence-{project}"],
                    "source_chapter_version_id": "chapter:1",
                },
            )
            assert response.status_code == 201

        check_url = "/api/projects/a/narrative/checks"
        first = client.post(check_url, json={"current_chapter": 3})
        second = client.post(check_url, json={"current_chapter": 3})
        assert first.status_code == second.status_code == 200
        assert len(first.json()) == len(second.json()) == 1
        finding_id = first.json()[0]["id"]
        fingerprint = finding_id

        detail = client.get(f"/api/projects/a/narrative/findings/{finding_id}")
        assert detail.status_code == 200
        assert detail.json()["evidence_ids"] == ["evidence-a"]
        assert detail.json()["source_chapter_version_id"] == "chapter:1"
        assert len(client.get("/api/projects/a/narrative/findings").json()) == 1

        resolved = client.post(f"/api/projects/a/narrative/findings/{finding_id}/resolve")
        assert resolved.status_code == 200
        assert resolved.json()["status"] == "RESOLVED"
        reopened = client.post(check_url, json={"current_chapter": 3})
        assert reopened.status_code == 200
        reopened_detail = client.get(f"/api/projects/a/narrative/findings/{finding_id}").json()
        assert reopened_detail["id"] == finding_id == fingerprint
        assert reopened_detail["status"] == "OPEN"

        assert client.post(
            "/api/projects/a/narrative/expectations",
            json={
                "id": "cross-project",
                "subject_type": "THREAD",
                "subject_id": "thread-b",
                "expectation_type": "THREAD_PROGRESS_BY",
                "deadline_chapter": 2,
            },
        ).status_code == 404
        assert client.get(f"/api/projects/b/narrative/findings/{finding_id}").status_code == 404
        assert client.post(f"/api/projects/b/narrative/findings/{finding_id}/resolve").status_code == 404
        assert client.get("/api/projects/b/narrative/findings").json() == []
    finally:
        narrative_finding_service.repository = original_finding_repository
        narrative_state_service.repository = original_state_repository


@pytest.mark.file_backend_only
def test_narrative_checks_without_expectations_create_no_findings(tmp_path):
    original = narrative_finding_service.repository
    narrative_finding_service.repository = FileNarrativeRepository(tmp_path)
    try:
        client = TestClient(app)
        response = client.post("/api/projects/empty/narrative/checks", json={"current_chapter": 99})
        assert response.status_code == 200
        assert response.json() == []
        assert client.get("/api/projects/empty/narrative/findings").json() == []
    finally:
        narrative_finding_service.repository = original
