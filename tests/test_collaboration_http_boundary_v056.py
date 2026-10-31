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


@pytest.fixture
def collaboration_project_delete(monkeypatch, tmp_path):
    """Use the real atomic retirement owner, not the pre-retirement delete stub."""
    import app.main as main_module
    from app.authorization import AuthorizationScope, DomainRole, DomainRoleAssignment, ModalityDomain, ScopeKind
    from app.collaboration import Branch, Storyline, Workspace
    from app.identity import User, WorkspaceMembership
    from app.repositories.factory import create_repository_bundle
    from app.services.authorization_service import AuthorizationService
    from app.services.collaboration_scope_service import CollaborationScopeService
    from app.services.identity_service import IdentityService
    from app.services.membership_authorization_service import MembershipAuthorizationService
    from app.services.novel_service import NovelService

    bundle = create_repository_bundle(config=SimpleNamespace(storage_backend="file"), data_root=tmp_path)
    novels = NovelService(bundle.novels, bundle.chapters)
    novels.create({"id": "book", "title": "Project deletion fixture"})
    scopes = CollaborationScopeService(bundle.scope, bundle.novels)
    scopes.create_workspace(Workspace("workspace", "Workspace"))
    scopes.create_workspace(Workspace("other-workspace", "Other workspace"))
    scopes.link_project("workspace", "book")
    scopes.create_storyline(Storyline("story", "workspace", "book", "Main"))
    scopes.create_branch(Branch("branch", "workspace", "book", "story", "main"))
    identity = IdentityService(bundle.identity, scopes)
    authorization = AuthorizationService(bundle.authorization, scopes)
    resolver = TrustedSessionResolver()
    for user, workspace in (("owner", "workspace"), ("member", "workspace"), ("outsider", "other-workspace")):
        identity.create_user(User(user, user.title()))
        identity.add_membership(WorkspaceMembership(f"membership:{user}", user, workspace))
        resolver.register(user, SessionContext(f"session:{user}", "client", user, workspace))
    scope = AuthorizationScope(ScopeKind.PROJECT, "workspace", "book")
    authorization.assign_role(DomainRoleAssignment(
        "owner-role", "owner", DomainRole.DOMAIN_LEAD, ModalityDomain.NOVEL, scope, "owner",
    ))
    settings = SimpleNamespace(enable_collaboration_runtime=True, enable_packaged_runtime=False)
    monkeypatch.setattr(main_module, "settings", settings)
    monkeypatch.setattr(api, "settings", settings)
    monkeypatch.setattr(main_module, "trusted_session_resolver", resolver)
    monkeypatch.setattr(api, "trusted_session_resolver", resolver)
    monkeypatch.setattr(api, "collaboration_scope_service", scopes)
    monkeypatch.setattr(api, "authorization_service", authorization)
    monkeypatch.setattr(api, "membership_authorization_service", MembershipAuthorizationService(identity, authorization))
    monkeypatch.setattr(api, "novel_service", novels)
    return SimpleNamespace(
        client=TestClient(app), bundle=bundle, identity=identity,
        audit_before=bundle.authorization.list_audit_events(),
    )


def test_collaboration_mode_allows_authorized_project_delete(collaboration_project_delete):
    fixture = collaboration_project_delete

    response = fixture.client.delete("/api/novels/book", headers={"X-Session-Token": "owner"})

    assert response.status_code == 204
    with pytest.raises(FileNotFoundError):
        fixture.bundle.novels.get("book")
    assert fixture.bundle.scope.project_workspace("book") is None
    assert fixture.bundle.scope.list("storylines", project_id="book") == []
    assert fixture.bundle.scope.list("branches", project_id="book") == []
    assert fixture.bundle.authorization.list_role_assignments("owner") == []
    events = fixture.bundle.authorization.list_audit_events()
    prior_ids = {event["id"] for event in fixture.audit_before}
    assert [event for event in events if event["id"] in prior_ids] == fixture.audit_before
    deleted = [event for event in events if event["id"] not in prior_ids]
    assert len(deleted) == 1
    assert deleted[0]["action"] == "PROJECT_DELETED"
    assert deleted[0]["actor_id"] == "owner"
    assert deleted[0]["target_id"] == "book"
    assert deleted[0]["scope"]["workspace_id"] == "workspace"


@pytest.mark.parametrize(("token", "status"), [(None, 401), ("invalid", 401), ("member", 403), ("outsider", 403)])
def test_collaboration_project_delete_rejects_unauthorized_actor_without_retiring(collaboration_project_delete, token, status):
    fixture = collaboration_project_delete
    before = fixture.bundle.novels.get("book")
    headers = {"X-Session-Token": token} if token else {}

    response = fixture.client.delete("/api/novels/book", headers=headers)

    assert response.status_code == status
    assert fixture.bundle.novels.get("book") == before
    assert fixture.bundle.scope.project_workspace("book") == "workspace"
    assert fixture.bundle.scope.get("branches", "branch")["project_id"] == "book"
    assert len(fixture.bundle.authorization.list_role_assignments("owner")) == 1
    assert fixture.bundle.authorization.list_audit_events() == fixture.audit_before


def test_collaboration_project_delete_revalidates_membership_at_commit(collaboration_project_delete, monkeypatch):
    from app.identity import IdentityStatus

    fixture = collaboration_project_delete
    original_delete = fixture.bundle.novels.delete

    def revoke_before_commit(novel_id, **lifecycle):
        fixture.identity.set_membership_status("owner", "workspace", IdentityStatus.INACTIVE)
        return original_delete(novel_id, **lifecycle)

    monkeypatch.setattr(fixture.bundle.novels, "delete", revoke_before_commit)
    response = fixture.client.delete("/api/novels/book", headers={"X-Session-Token": "owner"})

    assert response.status_code == 403
    assert fixture.bundle.novels.get("book")["id"] == "book"
    assert fixture.bundle.scope.project_workspace("book") == "workspace"
    assert fixture.bundle.scope.get("branches", "branch")["project_id"] == "book"
    assert len(fixture.bundle.authorization.list_role_assignments("owner")) == 1
    assert fixture.bundle.authorization.list_audit_events() == fixture.audit_before


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
