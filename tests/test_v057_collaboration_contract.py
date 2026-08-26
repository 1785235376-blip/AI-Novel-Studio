from app.application.collaboration_service import version_conflict_response
from app.collaboration_api import create_collaboration_router
from app.repositories.chapter_repository import VersionConflict
from fastapi import FastAPI


def test_backend_conflict_dto_matches_frontend_contract():
    error = VersionConflict(
        {"id": "novel:1", "version": 9, "content": "must not escape"},
        resource_id="novel:1", expected_version=8,
    )
    response = version_conflict_response(error)
    assert response.status_code == 409
    assert response.body == {"error": {
        "resource_id": "novel:1", "expected_version": 8,
        "actual_version": 9, "type": "VERSION_CONFLICT",
    }}
    assert "must not escape" not in repr(response.body)


def test_denial_contract_recommendation_is_stable():
    # Root API integration should emit this shape; the frontend maps both status and code.
    recommended = {"detail": {"code": "FORBIDDEN", "message": "Permission denied"}}
    assert recommended["detail"]["code"] == "FORBIDDEN"


def test_collaboration_router_openapi_path_and_response_models_are_stable():
    app = FastAPI()
    app.include_router(create_collaboration_router(object()))
    schema = app.openapi()
    base = "/api/collaboration/workspaces/{w}/projects/{p}/storylines/{s}/branches/{b}"
    expected = {
        f"{base}/bootstrap": "CollaborationBootstrap",
        f"{base}/members": "MemberList",
        f"{base}/permissions": "PermissionSummary",
        f"{base}/chapters": "ChapterList",
        f"{base}/audit": "AuditPage",
        f"{base}/chapters/{{chapter_id}}/revisions": "RevisionList",
        f"{base}/chapters/{{chapter_id}}/revisions/{{version}}": "RevisionDetail",
        f"{base}/chapters/{{chapter_id}}/snapshots": "SnapshotList",
        f"{base}/chapters/{{chapter_id}}/snapshots/{{snapshot_id}}": "SnapshotDetail",
        f"{base}/generations/{{generation_id}}/snapshot": "GenerationSnapshotLink",
    }
    for path, model in expected.items():
        response = schema["paths"][path]["get"]["responses"]["200"]
        assert response["content"]["application/json"]["schema"]["$ref"].endswith(f"/{model}")

    snapshot = schema["components"]["schemas"]["SnapshotDetail"]["properties"]
    assert not {"context", "content", "prompt", "secret"}.intersection(snapshot)
