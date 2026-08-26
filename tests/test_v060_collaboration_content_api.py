from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.actor_context import ActorContext, SessionContext
from app.collaboration_api import CollaborationReadService, create_collaboration_router
from app.application.audit_service import AuditService
from app.application.collaboration_service import CollaborationApplicationService


def test_production_fail_closed_middleware_allows_scoped_chapter_create_to_reach_trusted_boundary(monkeypatch):
    import app.main as main_module
    monkeypatch.setattr(main_module, "settings", SimpleNamespace(enable_collaboration_runtime=True))
    response = TestClient(main_module.app).post(
        "/api/collaboration/workspaces/w/projects/project/storylines/story/branches/branch/chapters",
        json={"title": "First"},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "SESSION_REQUIRED"


def test_production_fail_closed_middleware_allows_only_exact_lifecycle_posts(monkeypatch):
    import app.main as main_module
    import app.api as api_module
    collaboration_settings = SimpleNamespace(enable_collaboration_runtime=True)
    monkeypatch.setattr(main_module, "settings", collaboration_settings)
    monkeypatch.setattr(api_module, "settings", collaboration_settings)
    client = TestClient(main_module.app)

    for suffix in ("archive", "restore-archive"):
        response = client.post(f"/api/chapters/project:1/{suffix}?expected_version=1")
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "SESSION_REQUIRED"
        assert client.put(f"/api/chapters/project:1/{suffix}").status_code == 501
        assert client.delete(f"/api/chapters/project:1/{suffix}").status_code == 501
        assert client.patch(f"/api/chapters/project:1/{suffix}").status_code == 501
        assert client.post(f"/api/chapters/project:1/{suffix}/extra").status_code == 501

    response = client.delete("/api/chapters/project:1")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "SESSION_REQUIRED"
    assert client.post("/api/chapters/project:1/unsupported").status_code == 501


def test_production_fail_closed_middleware_allows_only_exact_archived_list_get(monkeypatch):
    import app.main as main_module
    monkeypatch.setattr(main_module, "settings", SimpleNamespace(enable_collaboration_runtime=True))
    client = TestClient(main_module.app, raise_server_exceptions=False)
    path = "/api/novels/project/chapters/archived"

    assert client.get(path).status_code != 501
    assert client.post(path).status_code == 501
    assert client.delete(path).status_code == 501
    assert client.get(path + "/extra").status_code == 501
    assert client.get("/api/novels/chapters/archived").status_code == 501
    assert client.get("/api/novels/project/archived").status_code == 501
    assert client.post("/api/chapters/project:1/unsupported").status_code == 501


def test_sensitive_collaboration_routes_require_session(monkeypatch):
    import app.main as main_module
    monkeypatch.setattr(main_module, "settings", SimpleNamespace(enable_collaboration_runtime=True,enable_packaged_runtime=False))
    client = TestClient(main_module.app, raise_server_exceptions=False)
    requests = [
        ("put", "/api/chapters/project:1"),
        ("post", "/api/generate/continue"),
        ("post", "/api/agent/chat"),
        ("post", "/api/exports"),
        ("get", "/api/exports/job/download"),
        ("post", "/api/harness/process/start"),
        ("get", "/api/collaboration/admin/workspaces"),
        ("get", "/api/assets/asset/download?novel_id=project"),
    ]
    for method,path in requests:
        response=getattr(client,method)(path)
        assert response.status_code==401,(method,path,response.status_code,response.text)
        assert response.json()["detail"]["code"]=="SESSION_REQUIRED"


class Sessions:
    def resolve(self, token):
        if token != "trusted":
            raise KeyError(token)
        return ActorContext("alice", "w", SessionContext("session", "client", "alice", "w"))


class MembershipAuthorization:
    def __init__(self, writable=True): self.writable = writable
    def require(self, actor, permission, domain, scope):
        if permission == "domain.write" and not self.writable:
            raise PermissionError("read only")
    def is_allowed(self, actor, permission, domain, scope): return permission != "domain.write" or self.writable


class Scopes:
    def validate_scope(self, scope):
        if scope.project_id != "project": raise KeyError(scope.project_id)
        return scope


class Chapters:
    def __init__(self): self.rows = []; self.deleted = []
    def create(self, project_id, payload):
        row = {"id": f"{project_id}:1", "novel_id": project_id, "number": 1, "volume": 1,
               "title": payload["title"], "word_count": 0, "status": "Draft", "content": f"# {payload['title']}",
               "version": 1, "document": {"type": "doc", "content": []}, "updated_at": "2026-01-01T00:00:00+00:00"}
        self.rows.append(row); return row
    def delete(self, chapter_id): self.deleted.append(chapter_id)
    def list(self, project_id): return self.rows


class AuthorizationRepository:
    def __init__(self, fail=False): self.events = []; self.fail = fail
    def append_audit_event(self, event):
        if self.fail: raise RuntimeError("audit unavailable")
        self.events.append(event); return event
    def list_audit_events(self, scope=None): return self.events


class Novels:
    def get_data_set(self, project_id, resource): return [{"id": f"{resource}-1", "project": project_id}]
    def get_public_secrets(self, project_id): return [{"id": "safe-secret", "privacy_level": "PUBLIC"}]


class AtomicCreate:
    def __init__(self, chapters, audit, fail=False): self.chapters, self.audit, self.fail = chapters, audit, fail
    def create_chapter_with_audit(self, project_id, title, operator, event_factory):
        created = self.chapters.create(project_id, {"title": title})
        if self.fail: raise RuntimeError("atomic transaction rolled back")
        self.audit.append_audit_event(event_factory(created)); return created


def make_client(*, writable=True, audit_fail=False):
    chapters, audit = Chapters(), AuthorizationRepository(audit_fail)
    membership = MembershipAuthorization(writable)
    application = CollaborationApplicationService(membership, AtomicCreate(chapters, audit, audit_fail), AuditService(audit))
    service = CollaborationReadService(
        sessions=Sessions(), membership_authorization=membership,
        identity=SimpleNamespace(repository=SimpleNamespace()),
        authorization=SimpleNamespace(repository=audit), scopes=Scopes(), chapters=chapters,
        generations=SimpleNamespace(), lore_repository=SimpleNamespace(), novels=Novels(),
        collaboration_application=application,
    )
    app = FastAPI(); app.include_router(create_collaboration_router(service))
    return TestClient(app, raise_server_exceptions=not audit_fail), chapters, audit


BASE = "/api/collaboration/workspaces/w/projects/project/storylines/story/branches/branch"
HEADERS = {"X-Session-Token": "trusted"}


def test_scoped_chapter_create_requires_write_and_emits_content_free_audit():
    api, chapters, audit = make_client()
    response = api.post(f"{BASE}/chapters", headers=HEADERS, json={"title": "Opening"})
    assert response.status_code == 201
    assert response.json()["id"] == "project:1" and response.json()["title"] == "Opening"
    assert chapters.rows and audit.events[0]["action"] == "CHAPTER_CREATED"
    assert "content" not in audit.events[0]["metadata"] and "document" not in audit.events[0]["metadata"]


def test_scoped_chapter_create_denies_read_only_actor_before_mutation():
    api, chapters, audit = make_client(writable=False)
    response = api.post(f"{BASE}/chapters", headers=HEADERS, json={"title": "Opening"})
    assert response.status_code == 403
    assert chapters.rows == [] and audit.events == []


def test_scoped_chapter_create_fails_when_atomic_port_fails():
    api, chapters, _ = make_client(audit_fail=True)
    response = api.post(f"{BASE}/chapters", headers=HEADERS, json={"title": "Opening"})
    assert response.status_code == 500
    assert response.status_code == 500


def test_story_database_resources_require_read_scope_and_return_public_secrets():
    api, _, _ = make_client()
    for resource in ("characters", "locations", "canon", "foreshadowing", "timeline"):
        response = api.get(f"{BASE}/story-database/{resource}", headers=HEADERS)
        assert response.status_code == 200 and response.json()["resource"] == resource
    secrets = api.get(f"{BASE}/story-database/secrets", headers=HEADERS)
    assert secrets.json()["items"] == [{"id": "safe-secret", "privacy_level": "PUBLIC"}]
    assert api.get(f"{BASE}/story-database/unknown", headers=HEADERS).status_code == 404
    assert api.get(f"{BASE}/story-database/characters").status_code == 401
