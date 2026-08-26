from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class Scopes:
    def __init__(self):
        self.repository = self

    def project_workspace(self, project_id):
        return {"project-a": "workspace-a", "project-b": "workspace-b"}.get(project_id)

    def validate_scope(self, scope):
        return scope


class Sessions:
    def resolve(self, token):
        if token != "session-a":
            raise KeyError(token)
        return SimpleNamespace(actor_id="author-a", workspace_id="workspace-a")


class Membership:
    def __init__(self):
        self.calls = []

    def require(self, actor, permission, domain, scope):
        self.calls.append((actor, permission, domain, scope))


def client(monkeypatch):
    import app.api as api

    membership = Membership()
    monkeypatch.setattr(api, "settings", SimpleNamespace(enable_collaboration_runtime=True))
    monkeypatch.setattr(api, "collaboration_scope_service", Scopes())
    monkeypatch.setattr(api, "trusted_session_resolver", Sessions())
    monkeypatch.setattr(api, "membership_authorization_service", membership)
    application = FastAPI()
    application.include_router(api.router, prefix="/api")
    return TestClient(application), membership


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("put", "/api/novels/project-b/audio-production/settings", {"voice_bindings": [], "pronunciation_dictionary": []}),
        ("post", "/api/novels/project-b/audiobook/chapters/chapter-1/queue", {}),
        ("post", "/api/novels/project-b/audiobook/jobs/audio-1/cancel", None),
        ("post", "/api/speech/synthesize", {"novel_id": "project-b", "text": "hello"}),
        ("post", "/api/novels/project-b/speech-generations/import", {"audio_uri": "https://cdn.example/audio.mp3"}),
        ("post", "/api/novels/project-b/screenplays/sp-1/motion-tasks/task-1/execute", None),
        ("post", "/api/novels/project-b/screenplays/sp-1/motion-tasks/task-1/cancel", None),
        ("post", "/api/novels/project-b/screenplays/sp-1/motion-tasks/task-1/retry", None),
        ("put", "/api/novels/project-b/screenplays/sp-1/motion-tasks/task-1/frames", {}),
        ("put", "/api/novels/project-b/screenplays/sp-1/motion-tasks/task-1/provider", {"provider_id": "video", "model_id": "model"}),
        ("put", "/api/novels/project-b/screenplays/sp-1/motion-tasks/task-1/result", {"url": "https://cdn.example/video.mp4"}),
        ("put", "/api/novels/project-b/screenplays/sp-1/motion-tasks/task-1/remote-id", {"remote_task_id": "remote-1"}),
        ("post", "/api/novels/project-b/screenplays/sp-1/motion-tasks/task-1/sync", None),
        ("post", "/api/novels/project-b/screenplays/sp-1/motion-tasks/task-1/import-asset", None),
        ("post", "/api/novels/project-b/screenplays/sp-1/motion-tasks/task-1/import-asset/download", None),
    ],
)
def test_valid_session_cannot_mutate_media_in_another_project(monkeypatch, method, path, payload):
    api_client, membership = client(monkeypatch)

    response = getattr(api_client, method)(
        path,
        headers={"X-Session-Token": "session-a"},
        json=payload,
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "PROJECT_SCOPE_FORBIDDEN"
    assert membership.calls == []
