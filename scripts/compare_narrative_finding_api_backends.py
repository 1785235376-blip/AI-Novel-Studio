import json
import os
import tempfile
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
os.environ["STORAGE_BACKEND"] = "postgres"

from fastapi.testclient import TestClient

from app.dependencies import narrative_finding_service, narrative_state_service, repositories
from app.main import app
from app.repositories.file.narrative import FileNarrativeRepository
from app.repositories.postgres.narrative import PostgresNarrativeRepository


client = TestClient(app)
run_id = uuid.uuid4().hex


def request(method, path, **kwargs):
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    return response.json()


def execute(project_id):
    thread_id = f"thread-{run_id}"
    shadow_id = f"shadow-{run_id}"
    thread_expectation_id = f"thread-expectation-{run_id}"
    shadow_expectation_id = f"shadow-expectation-{run_id}"
    base = f"/api/projects/{project_id}/narrative"

    request("POST", f"{base}/threads", json={"id": thread_id, "title": "Thread"})
    request("POST", f"{base}/foreshadowing", json={"id": shadow_id, "title": "Shadow"})
    expectations = [
        request("POST", f"{base}/expectations", json={
            "id": thread_expectation_id,
            "subject_type": "THREAD",
            "subject_id": thread_id,
            "expectation_type": "THREAD_PROGRESS_BY",
            "deadline_chapter": 2,
            "evidence_ids": ["thread-evidence"],
            "source_chapter_version_id": "chapter:1",
        }),
        request("POST", f"{base}/expectations", json={
            "id": shadow_expectation_id,
            "subject_type": "FORESHADOWING",
            "subject_id": shadow_id,
            "expectation_type": "FORESHADOWING_PAYOFF_BY",
            "deadline_chapter": 2,
            "evidence_ids": ["shadow-evidence"],
            "source_chapter_version_id": "chapter:1",
        }),
    ]
    check_body = {"current_chapter": 3}
    checks = request("POST", f"{base}/checks", json=check_body)
    repeated = request("POST", f"{base}/checks", json=check_body)
    findings = request("GET", f"{base}/findings")
    finding_id = findings[0]["id"]
    detail = request("GET", f"{base}/findings/{finding_id}")
    resolved = request("POST", f"{base}/findings/{finding_id}/resolve")
    request("POST", f"{base}/checks", json=check_body)
    reopened = request("GET", f"{base}/findings/{finding_id}")
    isolated_project = f"isolated-{project_id}"
    isolation = {
        "list": request("GET", f"/api/projects/{isolated_project}/narrative/findings"),
        "detail_status": client.get(f"/api/projects/{isolated_project}/narrative/findings/{finding_id}").status_code,
        "resolve_status": client.post(f"/api/projects/{isolated_project}/narrative/findings/{finding_id}/resolve").status_code,
    }
    return {
        "expectations": expectations,
        "checks": checks,
        "repeated": repeated,
        "findings": findings,
        "detail": detail,
        "resolved": resolved,
        "reopened": reopened,
        "isolation": isolation,
    }


assert isinstance(repositories.narrative, PostgresNarrativeRepository)
project = f"narrative-finding-api-{run_id}"
postgres_result = execute(project)

file_repository = FileNarrativeRepository(Path(tempfile.mkdtemp()))
narrative_state_service.repository = file_repository
narrative_finding_service.repository = file_repository
file_result = execute(project)

sections = {
    "Expectation": file_result["expectations"] == postgres_result["expectations"],
    "Checks": file_result["checks"] == postgres_result["checks"] and file_result["repeated"] == postgres_result["repeated"],
    "Finding List": file_result["findings"] == postgres_result["findings"],
    "Finding Detail": file_result["detail"] == postgres_result["detail"],
    "Resolve": file_result["resolved"] == postgres_result["resolved"],
    "Lifecycle": file_result["reopened"] == postgres_result["reopened"],
    "Project Isolation": file_result["isolation"] == postgres_result["isolation"] == {"list": [], "detail_status": 404, "resolve_status": 404},
}
for name, matched in sections.items():
    print(f"{name} API Backend Parity: {'MATCH' if matched else 'MISMATCH'}")
print(f"PostgreSQL Runtime: {'REAL VERIFIED' if isinstance(repositories.narrative, PostgresNarrativeRepository) else 'NOT VERIFIED'}")
print(f"File Runtime: {'REAL VERIFIED' if isinstance(file_repository, FileNarrativeRepository) else 'NOT VERIFIED'}")
print(f"Overall Narrative Finding API Backend Parity: {'MATCH' if all(sections.values()) else 'MISMATCH'}")
if not all(sections.values()):
    print(json.dumps({"file": file_result, "postgres": postgres_result}, indent=2, sort_keys=True))
    raise SystemExit(1)
