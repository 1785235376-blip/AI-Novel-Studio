from types import SimpleNamespace
import importlib
import pytest
from fastapi import HTTPException

from fastapi.testclient import TestClient

from app import api
from app.actor_context import SessionContext
from app.main import app
from app.trusted_sessions import TrustedSessionResolver
from app.repositories.chapter_repository import VersionConflict


class Chapters:
    def get(self, chapter_id):
        return {"id": chapter_id, "novel_id": "book", "version": 4,
                "content": "old", "document": {"type": "doc", "content": []}}


class ScopeRepository:
    def project_workspace(self, project_id): return "workspace"
    def get(self, kind, item_id):
        assert kind == "branches" and item_id == "branch"
        return {"id": "branch", "workspace_id": "workspace", "project_id": "book", "storyline_id": "story"}
    def list(self, kind, **filters):
        if kind == "storylines": return [{"id": "story"}]
        if kind == "branches": return [{"id": "branch"}]
        return []


class CollaborationUpdates:
    def __init__(self): self.calls = []
    def update_chapter(self, **kwargs):
        self.calls.append(kwargs)
        return {"id": kwargs["chapter_id"], "version": kwargs["expected_version"] + 1}

class AllowRead:
    def require(self,*args,**kwargs):return None


def test_http_resolves_opaque_session_server_side_and_never_trusts_actor_payload(monkeypatch):
    resolver = TrustedSessionResolver()
    resolver.register("opaque-a", SessionContext("session-a", "client-a", "user-a", "workspace"))
    updates = CollaborationUpdates()
    monkeypatch.setattr(api, "trusted_session_resolver", resolver)
    monkeypatch.setattr(api, "chapter_service", Chapters())
    monkeypatch.setattr(api, "collaboration_scope_service", SimpleNamespace(repository=ScopeRepository()))
    monkeypatch.setattr(api, "collaboration_application_service", updates)
    monkeypatch.setattr(api, "settings", SimpleNamespace(enable_collaboration_runtime=True))
    client = TestClient(app)

    assert client.put("/api/chapters/book:1", json={"content": "new", "version": 4}).status_code == 401
    assert client.put("/api/chapters/book:1", headers={"X-Session-Token": "bad"},
                      json={"content": "new", "version": 4}).status_code == 401
    response = client.put("/api/chapters/book:1", headers={"X-Session-Token": "opaque-a", "X-Branch-ID": "branch"},
                          json={"content": "new", "version": 4, "actor_id": "spoofed"})
    assert response.status_code == 200 and response.json()["version"] == 5
    assert updates.calls[0]["actor"].actor_id == "user-a"
    assert updates.calls[0]["actor"].session_id == "session-a"
    assert updates.calls[0]["scope"].branch_id == "branch"


def test_collaboration_mode_blocks_legacy_mutation_bypasses(monkeypatch):
    monkeypatch.setattr(api, "settings", SimpleNamespace(enable_collaboration_runtime=True))
    client = TestClient(app)
    assert client.delete("/api/chapters/book:1").status_code == 401
    assert client.post("/api/chapters/book:1/duplicate").status_code == 501
    assert client.post("/api/chapters/book:1/move", json={"direction": "up"}).status_code == 501


def test_multimodal_production_routes_reach_the_session_boundary(monkeypatch):
    import app.main as main_module
    collaboration_settings = SimpleNamespace(enable_collaboration_runtime=True, enable_packaged_runtime=False)
    monkeypatch.setattr(main_module,"settings",collaboration_settings)
    monkeypatch.setattr(api,"settings",collaboration_settings)
    client=TestClient(app)
    paths=(
        ("get","/api/novels/book/audio-production/settings"),
        ("post","/api/novels/book/audiobook/chapters/chapter/queue"),
        ("post","/api/novels/book/audiobook/jobs/job/cancel"),
        ("post","/api/novels/book/screenplays/screenplay/motion-tasks/task/execute"),
        ("post","/api/novels/book/screenplays/screenplay/motion-tasks/task/retry"),
    )
    for method,path in paths:
        response=getattr(client,method)(path)
        assert response.status_code==401
        assert response.json()["detail"]["code"]=="SESSION_REQUIRED"


def test_collaboration_mode_allows_authorized_project_delete(monkeypatch):
    import app.main as main_module
    resolver = TrustedSessionResolver()
    resolver.register("owner", SessionContext("session", "client", "user", "workspace"))
    deleted = []
    scope_service = SimpleNamespace(
        repository=SimpleNamespace(project_workspace=lambda project_id: "workspace"),
        validate_scope=lambda scope: None,
    )
    collaboration_settings = SimpleNamespace(enable_collaboration_runtime=True, enable_packaged_runtime=False)
    monkeypatch.setattr(main_module, "settings", collaboration_settings)
    monkeypatch.setattr(api, "settings", collaboration_settings)
    monkeypatch.setattr(main_module, "trusted_session_resolver", resolver)
    monkeypatch.setattr(api, "trusted_session_resolver", resolver)
    monkeypatch.setattr(api, "collaboration_scope_service", scope_service)
    monkeypatch.setattr(api, "membership_authorization_service", AllowRead())
    monkeypatch.setattr(api, "novel_service", SimpleNamespace(delete=lambda novel_id: deleted.append(novel_id)))

    response = TestClient(app).delete("/api/novels/book", headers={"X-Session-Token": "owner"})

    assert response.status_code == 204
    assert deleted == ["book"]


class GenerationJobs:
    def __init__(self, conflict=False):
        self.job = SimpleNamespace(
            id="job", actor_id="user-a", workspace_id="workspace", base_chapter_version=4,
            scope={"kind": "BRANCH", "workspace_id": "workspace", "project_id": "book",
                   "storyline_id": "story", "branch_id": "branch"},
        )
        self.calls=[];self.conflict=conflict
    def get(self, jid): return self.job
    def accept(self, *args):
        self.calls.append(args)
        if self.conflict:
            raise VersionConflict({"id":"book:1","version":5},resource_id="book:1",expected_version=4)
        return {"accepted":True}


def test_generation_accept_uses_current_trusted_actor_and_generation_base_version(monkeypatch):
    resolver=TrustedSessionResolver()
    resolver.register("owner-a",SessionContext("session-new","client-b","user-a","workspace"))
    resolver.register("other",SessionContext("session-x","client-x","user-b","workspace"))
    fake=GenerationJobs()
    monkeypatch.setattr(api,"trusted_session_resolver",resolver);monkeypatch.setattr(api,"jobs",fake)
    monkeypatch.setattr(api,"membership_authorization_service",AllowRead())
    monkeypatch.setattr(api,"settings",SimpleNamespace(enable_collaboration_runtime=True))
    client=TestClient(app)
    assert client.post("/api/generation/job/accept",headers={"X-Session-Token":"other"},json={"expected_version":4}).status_code==403
    assert client.post("/api/generation/job/accept",headers={"X-Session-Token":"owner-a"},json={"expected_version":5}).status_code==409
    response=client.post("/api/generation/job/accept",headers={"X-Session-Token":"owner-a"},json={"expected_version":4})
    assert response.status_code==200
    assert fake.calls[0][2].session_id=="session-new" and fake.calls[0][-1]==4


def test_generation_accept_after_chapter_advance_returns_version_conflict(monkeypatch):
    resolver=TrustedSessionResolver();resolver.register("owner",SessionContext("session","client","user-a","workspace"))
    fake=GenerationJobs(conflict=True)
    monkeypatch.setattr(api,"trusted_session_resolver",resolver);monkeypatch.setattr(api,"jobs",fake)
    monkeypatch.setattr(api,"membership_authorization_service",AllowRead())
    monkeypatch.setattr(api,"settings",SimpleNamespace(enable_collaboration_runtime=True))
    response=TestClient(app).post("/api/generation/job/accept",headers={"X-Session-Token":"owner"},json={"expected_version":4})
    assert response.status_code==409 and response.json()["detail"]["code"]=="VERSION_CONFLICT"


def test_generation_lifecycle_revalidates_current_membership(monkeypatch):
    class Revoked:
        def require(self,*args,**kwargs):raise PermissionError("membership inactive")
    resolver=TrustedSessionResolver();resolver.register("owner",SessionContext("session","client","user-a","workspace"))
    monkeypatch.setattr(api,"trusted_session_resolver",resolver);monkeypatch.setattr(api,"jobs",GenerationJobs())
    monkeypatch.setattr(api,"membership_authorization_service",Revoked())
    with pytest.raises(HTTPException) as caught:api._generation_context("job","owner")
    assert caught.value.status_code==403


def test_collaboration_middleware_blocks_legacy_context_routes(monkeypatch):
    main_module=importlib.import_module("app.main")
    monkeypatch.setattr(main_module,"settings",SimpleNamespace(enable_collaboration_runtime=True))
    client=TestClient(app)
    assert client.get("/novels").status_code==501
    assert client.post("/context-packs",json={"novel_id":"book","chapter":1}).status_code==501
