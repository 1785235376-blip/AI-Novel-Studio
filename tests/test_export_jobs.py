from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Lock
import time
from datetime import datetime, timedelta, timezone
import json

import pytest

from app.services.export_job_service import ExportJobResultInvalid, ExportJobService, ExportJobUnavailable


def test_export_job_is_durable_idempotent_and_completes():
    with TemporaryDirectory() as root:
        service = ExportJobService(Path(root), lambda novel_id, fmt: {
            "format": fmt, "filename": f"{novel_id}.{fmt}", "content": "fixture"
        })
        try:
            first = service.create("novel-a", "markdown", "same-key")
            second = service.create("novel-a", "markdown", "same-key")
            assert first["id"] == second["id"]
            for _ in range(100):
                current = service.get(first["id"])
                if current["status"] == "succeeded":
                    break
                time.sleep(0.01)
            assert current["result"]["content"] == "fixture"
            assert service.path.is_file()
        finally:
            service._pool.shutdown(wait=True)


def test_export_job_rejects_unknown_format():
    with TemporaryDirectory() as root:
        service = ExportJobService(Path(root), lambda *_: {})
        try:
            with pytest.raises(ValueError, match="unsupported"):
                service.create("novel-a", "unsupported-format")
        finally:
            service._pool.shutdown(wait=True)


def test_export_idempotency_key_expires_after_24_hours():
    with TemporaryDirectory() as root:
        service = ExportJobService(Path(root), lambda *_: {
            "format": "txt", "filename": "novel.txt", "content": "fresh"
        })
        try:
            old = {
                "id": "old-job", "novel_id": "novel-a", "format": "txt",
                "status": "succeeded", "created_at": (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat(),
                "updated_at": (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat(),
                "idempotency_key": "same-key", "result": {"content": "old"}, "error": None,
            }
            service._write({"old-job": old})
            fresh = service.create("novel-a", "txt", "same-key")
            assert fresh["id"] != "old-job"
        finally:
            service._pool.shutdown(wait=True)


def test_export_job_download_returns_bytes_and_safe_headers_metadata():
    with TemporaryDirectory() as root:
        service = ExportJobService(Path(root), lambda *_: {
            "format": "markdown",
            "filename": "../章节\r\n稿.md",
            "media_type": "text/markdown; charset=utf-8",
            "content": "正文",
        })
        try:
            job = service.create("novel-a", "markdown")
            for _ in range(100):
                if service.get(job["id"])["status"] == "succeeded":
                    break
                time.sleep(0.01)
            payload = service.download(job["id"])
            assert payload["content"] == "正文".encode("utf-8")
            assert payload["filename"] == "章节稿.md"
            assert payload["media_type"] == "text/markdown"
            assert "/" not in payload["filename"] and "\r" not in payload["filename"]
        finally:
            service._pool.shutdown(wait=True)


def test_export_job_persists_binary_result_as_bounded_base64_payload():
    with TemporaryDirectory() as root:
        service = ExportJobService(Path(root), lambda *_: {
            "format": "txt", "filename": "binary.bin", "content": b"\x00\xfffixture",
        })
        try:
            job = service.create("novel-a", "txt")
            completed = _wait_for_status(service, job["id"], "succeeded")
            assert completed["result"]["content_encoding"] == "base64"
            assert service.download(job["id"])["content"] == b"\x00\xfffixture"
        finally:
            service._pool.shutdown(wait=True)


def test_export_job_download_rejects_non_terminal_and_corrupt_states():
    started = Event()
    release = Event()

    def blocked_export(*_):
        started.set()
        release.wait(timeout=2)
        return {"filename": "ok.txt", "content": "ok"}

    with TemporaryDirectory() as root:
        service = ExportJobService(Path(root), blocked_export)
        try:
            job = service.create("novel-a", "txt")
            assert started.wait(timeout=1)
            with pytest.raises(ExportJobUnavailable) as not_ready:
                service.download(job["id"])
            assert not_ready.value.status == "running"

            service._write({"corrupt": {"status": "unknown", "format": "txt", "result": {}}})
            with pytest.raises(ExportJobResultInvalid):
                service.download("corrupt")
        finally:
            release.set()
            service._pool.shutdown(wait=True)


class _LocalExportRouteService:
    """Every route authorizes the stored record before calling its operation."""
    def __init__(self, status="succeeded"):
        self.job = {
            "id": "job-1", "novel_id": "novel-a", "status": status,
            "permission_context": {"mode": "local", "novel_id": "novel-a"},
        }
        self.reads = []

    def get(self, job_id):
        self.reads.append(job_id)
        if job_id != self.job["id"]:
            raise FileNotFoundError(job_id)
        return self.job


def _local_export_client(monkeypatch, service):
    from types import SimpleNamespace
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import app.api as api

    monkeypatch.setattr(api, "settings", SimpleNamespace(enable_collaboration_runtime=False))
    monkeypatch.setattr(api, "export_job_service", service)
    local_app = FastAPI()
    local_app.include_router(api.router, prefix="/api")
    return TestClient(local_app)


def test_export_download_route_returns_attachment(monkeypatch):
    class FakeExportService(_LocalExportRouteService):
        def download(self, job_id):
            assert self.reads == [job_id]
            return {
                "content": b"fixture", "filename": "章节.md",
                "media_type": "text/markdown", "format": "markdown",
            }

    fake = FakeExportService()
    response = _local_export_client(monkeypatch, fake).get("/api/exports/job-1/download")
    assert response.status_code == 200
    assert response.content == b"fixture"
    assert response.headers["content-type"] == "text/markdown; charset=utf-8"
    assert response.headers["content-disposition"].startswith('attachment; filename="export.md";')
    assert fake.reads == ["job-1"]


def test_export_download_route_reports_not_ready(monkeypatch):
    class FakeExportService(_LocalExportRouteService):
        def download(self, job_id):
            assert self.reads == [job_id]
            raise ExportJobUnavailable("running")

    fake = FakeExportService(status="running")
    response = _local_export_client(monkeypatch, fake).get("/api/exports/job-1/download")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "EXPORT_NOT_READY"
    assert response.json()["detail"]["details"]["status"] == "running"
    assert fake.reads == ["job-1"]


def _wait_for_status(service, job_id, expected, timeout=2):
    deadline = time.monotonic() + timeout
    current = service.get(job_id)
    while time.monotonic() < deadline:
        current = service.get(job_id)
        if current["status"] == expected:
            return current
        time.sleep(0.01)
    return current


def test_export_job_cancel_is_durable_and_cooperative():
    started = Event()
    release = Event()

    def blocked_export(*_, progress_callback=None):
        started.set()
        while not release.wait(0.01):
            # A real exporter can report progress and observe cancellation at
            # the next callback boundary.  Legacy two-argument exporters still
            # receive the same call shape through the compatibility adapter.
            if progress_callback:
                progress_callback(40, "正在写入")
        return {"format": "txt", "filename": "cancel.txt", "content": "late"}

    with TemporaryDirectory() as root:
        service = ExportJobService(Path(root), blocked_export)
        try:
            job = service.create("novel-a", "txt")
            assert started.wait(timeout=1)
            cancelled = service.cancel(job["id"])
            assert cancelled["status"] == "cancelled"
            assert cancelled["error"]["code"] == "EXPORT_CANCELLED"
            release.set()
            final = _wait_for_status(service, job["id"], "cancelled")
            assert final["status"] == "cancelled"
            assert final["progress_message"] == "已取消"
        finally:
            release.set()
            service._pool.shutdown(wait=True)


def test_export_job_retry_creates_new_attempt_after_failure():
    calls = {"count": 0}
    lock = Lock()

    def flaky_export(*_):
        with lock:
            calls["count"] += 1
            attempt = calls["count"]
        if attempt == 1:
            raise RuntimeError("fixture failure")
        return {"format": "txt", "filename": "retry.txt", "content": "ok"}

    with TemporaryDirectory() as root:
        service = ExportJobService(Path(root), flaky_export)
        try:
            first = service.create("novel-a", "txt")
            failed = _wait_for_status(service, first["id"], "failed")
            assert failed["error"]["code"] == "EXPORT_FAILED"
            retried = service.retry(first["id"])
            assert retried["id"] != first["id"]
            assert retried["retry_of"] == first["id"]
            assert retried["attempt"] == 2
            completed = _wait_for_status(service, retried["id"], "succeeded")
            assert completed["progress"] == 100
        finally:
            service._pool.shutdown(wait=True)


def test_export_job_startup_recovery_requeues_interrupted_work():
    started = Event()
    release = Event()
    now = datetime.now(timezone.utc).isoformat()

    def recovered_export(*_):
        started.set()
        release.wait(timeout=2)
        return {"format": "txt", "filename": "recovered.txt", "content": "ok"}

    with TemporaryDirectory() as root:
        path = Path(root) / "export_jobs.json"
        path.write_text(json.dumps({
            "old-running": {
                "id": "old-running", "novel_id": "novel-a", "format": "txt",
                "status": "running", "created_at": now, "updated_at": now,
                "idempotency_key": None, "result": None, "error": None,
            }
        }), encoding="utf-8")
        service = ExportJobService(Path(root), recovered_export)
        try:
            assert started.wait(timeout=1)
            running = service.get("old-running")
            assert running["status"] == "running"
            assert running["recovery_count"] == 1
            release.set()
            completed = _wait_for_status(service, "old-running", "succeeded")
            assert completed["progress"] == 100
        finally:
            release.set()
            service._pool.shutdown(wait=True)


def test_export_lifecycle_routes_cancel_and_retry(monkeypatch):
    class FakeExportService(_LocalExportRouteService):
        def cancel(self, job_id):
            assert self.reads == [job_id]
            self.job = {**self.job, "status": "cancelled", "progress": 20}
            return self.job

        def retry(self, job_id):
            assert self.reads == [job_id, job_id]
            assert self.job["status"] == "cancelled"
            return {**self.job, "id": "retry-1", "retry_of": job_id, "status": "queued", "progress": 0}

    fake = FakeExportService(status="queued")
    client = _local_export_client(monkeypatch, fake)
    cancelled = client.post("/api/exports/job-1/cancel")
    retried = client.post("/api/exports/job-1/retry")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert retried.status_code == 202
    assert retried.json()["retry_of"] == "job-1"
    assert fake.reads == ["job-1", "job-1"]


class _ScopedExportService:
    def __init__(self):
        self.created_permission_context = None
        self.operations = []
        self.job = {
            "id": "job-1",
            "novel_id": "project-b",
            "status": "succeeded",
            "permission_context": {
                "mode": "collaboration", "novel_id": "project-b",
                "workspace_id": "workspace-b", "storyline_id": "story-b",
                "branch_id": "branch-b", "actor_id": "session-b", "permission": "domain.read",
            },
        }

    def create(self, novel_id, format, idempotency_key=None, *, permission_context=None):
        self.created_permission_context = permission_context
        return {**self.job, "novel_id": novel_id, "format": format, "permission_context": permission_context}

    def get(self, job_id):
        if job_id != self.job["id"]:
            raise FileNotFoundError(job_id)
        return self.job

    def download(self, job_id):
        self.operations.append(("download", job_id))
        return {"content": b"fixture", "filename": "export.txt", "media_type": "text/plain"}

    def cancel(self, job_id):
        self.operations.append(("cancel", job_id))
        return {**self.job, "status": "cancelled"}

    def retry(self, job_id):
        self.operations.append(("retry", job_id))
        return {**self.job, "id": "job-2", "retry_of": job_id, "status": "queued"}


class _ExportScopes:
    def __init__(self):
        self.repository = self

    def project_workspace(self, project_id):
        return {"project-a": "workspace-a", "project-b": "workspace-b"}.get(project_id)

    def get(self, collection, item_id):
        assert collection == "branches"
        if item_id != "branch-b":
            raise KeyError(item_id)
        return {
            "id": "branch-b",
            "workspace_id": "workspace-b",
            "project_id": "project-b",
            "storyline_id": "story-b",
        }

    def validate_scope(self, scope):
        return scope


class _ExportSessions:
    def resolve(self, token):
        from types import SimpleNamespace

        workspaces = {"session-a": "workspace-a", "session-b": "workspace-b", "other-owner": "workspace-b"}
        if token not in workspaces:
            raise KeyError(token)
        return SimpleNamespace(actor_id=token, workspace_id=workspaces[token])


class _ExportMembership:
    def __init__(self, *, writable=True, readable=True):
        self.writable = writable
        self.readable = readable
        self.calls = []

    def require(self, actor, permission, domain, scope):
        self.calls.append((actor, permission, domain, scope))
        if permission == "domain.read" and not self.readable:
            raise PermissionError("membership revoked")
        if permission == "domain.write" and not self.writable:
            raise PermissionError("read-only membership")


def _collaboration_export_client(monkeypatch, *, writable=True, readable=True, collaboration=True):
    from types import SimpleNamespace
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import app.api as api

    membership = _ExportMembership(writable=writable, readable=readable)
    monkeypatch.setattr(api, "settings", SimpleNamespace(enable_collaboration_runtime=collaboration))
    export_service = _ScopedExportService()
    monkeypatch.setattr(api, "export_job_service", export_service)
    monkeypatch.setattr(api, "novel_service", SimpleNamespace(get=lambda novel_id: {"id": novel_id}))
    monkeypatch.setattr(api, "collaboration_scope_service", _ExportScopes())
    monkeypatch.setattr(api, "trusted_session_resolver", _ExportSessions())
    monkeypatch.setattr(api, "membership_authorization_service", membership)
    local_app = FastAPI()
    local_app.include_router(api.router, prefix="/api")
    return TestClient(local_app), membership, export_service


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/exports/job-1"),
        ("get", "/api/exports/job-1/download"),
        ("post", "/api/exports/job-1/cancel"),
        ("post", "/api/exports/job-1/retry"),
    ],
)
def test_export_job_routes_hide_cross_project_jobs(monkeypatch, method, path):
    client, membership, export_service = _collaboration_export_client(monkeypatch)

    response = getattr(client, method)(path, headers={"X-Session-Token": "session-a"})

    assert response.status_code == 404
    assert response.json()["detail"] == "export job not found"
    assert membership.calls == []
    assert export_service.operations == []


def test_export_job_routes_apply_read_and_write_membership(monkeypatch):
    client, membership, export_service = _collaboration_export_client(monkeypatch, writable=False)
    headers = {"X-Session-Token": "session-b"}

    downloaded = client.get("/api/exports/job-1/download", headers=headers)
    cancelled = client.post("/api/exports/job-1/cancel", headers=headers)
    retried = client.post("/api/exports/job-1/retry", headers=headers)

    assert downloaded.status_code == 200
    assert downloaded.content == b"fixture"
    assert cancelled.status_code == retried.status_code == 404
    assert export_service.operations == [("download", "job-1")]
    assert [call[1] for call in membership.calls] == ["domain.read", "domain.write", "domain.write"]
    assert all(call[3].project_id == "project-b" for call in membership.calls)
    assert all(call[3].branch_id == "branch-b" for call in membership.calls)


def test_create_export_requires_the_session_project_even_without_branch(monkeypatch):
    client, membership, export_service = _collaboration_export_client(monkeypatch)

    forbidden = client.post(
        "/api/exports?novel_id=project-b",
        headers={"X-Session-Token": "session-a"},
        json={"format": "txt"},
    )
    allowed = client.post(
        "/api/exports?novel_id=project-b",
        headers={"X-Session-Token": "session-b"},
        json={"format": "txt"},
    )

    assert forbidden.status_code == 403
    assert forbidden.json()["detail"]["code"] == "EXPORT_SCOPE_FORBIDDEN"
    assert allowed.status_code == 202
    assert export_service.created_permission_context["mode"] == "collaboration"
    assert export_service.created_permission_context["workspace_id"] == "workspace-b"
    assert export_service.created_permission_context["branch_id"] is None
    assert [call[1] for call in membership.calls] == ["domain.read"]


_EXPORT_JOB_ROUTES = [
    ("get", "/api/exports/job-1"), ("get", "/api/exports/job-1/download"),
    ("post", "/api/exports/job-1/cancel"), ("post", "/api/exports/job-1/retry"),
]


@pytest.mark.parametrize(("method", "path"), _EXPORT_JOB_ROUTES)
@pytest.mark.parametrize("collaboration", [True, False], ids=["collaboration-runtime", "local-runtime"])
def test_export_persisted_owner_is_enforced_even_after_runtime_mode_change(monkeypatch, method, path, collaboration):
    client, membership, service = _collaboration_export_client(monkeypatch, collaboration=collaboration)

    response = getattr(client, method)(path, headers={"X-Session-Token": "other-owner"})

    assert response.status_code == 404
    assert response.json()["detail"] == "export job not found"
    assert membership.calls[0][0].actor_id == "other-owner"
    assert service.operations == []


@pytest.mark.parametrize(("method", "path"), _EXPORT_JOB_ROUTES)
@pytest.mark.parametrize("context_patch", [
    None, {"mode": "local"}, {"actor_id": "another-owner"},
    {"workspace_id": "workspace-a"}, {"novel_id": "project-a"},
    {"storyline_id": "story-a"}, {"branch_id": "missing-branch"},
], ids=["legacy-branch-only", "wrong-mode", "wrong-actor", "wrong-workspace", "wrong-project", "wrong-storyline", "wrong-branch"])
def test_export_routes_conceal_incomplete_or_mismatched_persisted_scope(monkeypatch, method, path, context_patch):
    client, _, service = _collaboration_export_client(monkeypatch)
    if context_patch is None:
        service.job["permission_context"] = {"branch_id": "branch-b"}
    else:
        service.job["permission_context"].update(context_patch)

    response = getattr(client, method)(path, headers={"X-Session-Token": "session-b"})

    assert response.status_code == 404
    assert response.json()["detail"] == "export job not found"
    assert service.operations == []


@pytest.mark.parametrize(("method", "path"), _EXPORT_JOB_ROUTES)
def test_export_routes_reject_request_branch_mismatch(monkeypatch, method, path):
    client, _, service = _collaboration_export_client(monkeypatch)
    response = getattr(client, method)(path, headers={"X-Session-Token": "session-b", "X-Branch-Id": "branch-a"})
    assert response.status_code == 404
    assert service.operations == []


@pytest.mark.parametrize("token", [None, "invalid"])
@pytest.mark.parametrize("collaboration", [True, False], ids=["collaboration-runtime", "local-runtime"])
def test_collaboration_export_download_requires_valid_session_in_either_runtime(monkeypatch, token, collaboration):
    client, membership, service = _collaboration_export_client(monkeypatch, collaboration=collaboration)
    response = client.get("/api/exports/job-1/download", headers={"X-Session-Token": token} if token else {})
    assert response.status_code == 401
    assert membership.calls == []
    assert service.operations == []


def test_export_download_revalidates_current_read_membership(monkeypatch):
    client, membership, service = _collaboration_export_client(monkeypatch)
    headers = {"X-Session-Token": "session-b"}
    assert client.get("/api/exports/job-1/download", headers=headers).status_code == 200
    membership.readable = False
    service.operations.clear()

    response = client.get("/api/exports/job-1/download", headers=headers)

    assert response.status_code == 404
    assert [call[1] for call in membership.calls] == ["domain.read", "domain.read"]
    assert service.operations == []


def test_export_owner_with_write_membership_can_cancel_and_retry(monkeypatch):
    client, membership, service = _collaboration_export_client(monkeypatch)
    service.job["status"] = "queued"
    headers = {"X-Session-Token": "session-b"}
    cancelled = client.post("/api/exports/job-1/cancel", headers=headers)
    service.job["status"] = "cancelled"
    retried = client.post("/api/exports/job-1/retry", headers=headers)
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    assert retried.status_code == 202 and retried.json()["retry_of"] == "job-1"
    assert [call[1] for call in membership.calls] == ["domain.write", "domain.write"]
    assert service.operations == [("cancel", "job-1"), ("retry", "job-1")]


def test_export_permission_context_survives_restart_retry_and_scopes_idempotency(tmp_path):
    context = dict(_ScopedExportService().job["permission_context"])

    def failed_export(*_):
        raise RuntimeError("local fixture failure")

    service = ExportJobService(tmp_path, failed_export)
    try:
        original = service.create("project-b", "txt", "same-key", permission_context=context)
        assert _wait_for_status(service, original["id"], "failed")["status"] == "failed"
        assert json.loads(service.path.read_text())[original["id"]]["permission_context"] == context
        same = service.create("project-b", "txt", "same-key", permission_context=context)
        other = service.create("project-b", "txt", "same-key", permission_context={**context, "actor_id": "other-owner"})
        assert same["id"] == original["id"]
        assert other["id"] != original["id"]
        assert _wait_for_status(service, other["id"], "failed")["status"] == "failed"
    finally:
        service._pool.shutdown(wait=True)

    restarted = ExportJobService(tmp_path, failed_export)
    try:
        assert restarted.get(original["id"])["permission_context"] == context
        retried = restarted.retry(original["id"])
        assert retried["id"] != original["id"]
        assert retried["retry_of"] == original["id"]
        assert retried["permission_context"] == context
        assert _wait_for_status(restarted, retried["id"], "failed")["status"] == "failed"
        assert json.loads(restarted.path.read_text())[retried["id"]]["permission_context"] == context
    finally:
        restarted._pool.shutdown(wait=True)


@pytest.fixture
def real_branch_export(monkeypatch, tmp_path):
    """File/HTTP integration through the actual branch snapshot authority."""
    from types import SimpleNamespace
    from fastapi.testclient import TestClient
    import app.api as api
    import app.main as main_module
    from app.actor_context import SessionContext
    from app.authorization import AuthorizationScope, DomainRole, DomainRoleAssignment, ModalityDomain, ScopeKind
    from app.collaboration import Branch, Storyline, Workspace
    from app.experimental.store import ExperimentalStore
    from app.identity import User, WorkspaceMembership
    from app.repositories.factory import create_repository_bundle
    from app.services.authorization_service import AuthorizationService
    from app.services.branch_manuscript_service import BranchManuscriptService
    from app.services.chapter_service import ChapterService
    from app.services.collaboration_scope_service import CollaborationScopeService
    from app.services.identity_service import IdentityService
    from app.services.membership_authorization_service import MembershipAuthorizationService
    from app.services.novel_service import NovelService
    from app.trusted_sessions import TrustedSessionResolver

    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "branch_manuscript_v1")
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    bundle = create_repository_bundle(config=SimpleNamespace(storage_backend="file"), data_root=tmp_path)
    novels = NovelService(bundle.novels, bundle.chapters)
    chapters = ChapterService(bundle.chapters)
    novels.create({"id": "project-b", "title": "Branch export fixture"})
    chapters.create("project-b", {"title": "Mainline", "content": "PROJECT_ONLY_SECRET"})
    scopes = CollaborationScopeService(bundle.scope, bundle.novels)
    scopes.create_workspace(Workspace("workspace-b", "Workspace B"))
    scopes.link_project("workspace-b", "project-b")
    scopes.create_storyline(Storyline("story-b", "workspace-b", "project-b", "Story B"))
    scopes.create_branch(Branch("branch-b", "workspace-b", "project-b", "story-b", "Branch B"))
    identity = IdentityService(bundle.identity, scopes)
    identity.create_user(User("branch-owner", "Branch Owner"))
    identity.add_membership(WorkspaceMembership("branch-member", "branch-owner", "workspace-b"))
    authorization = AuthorizationService(bundle.authorization, scopes)
    branch_scope = AuthorizationScope(ScopeKind.BRANCH, "workspace-b", "project-b", "story-b", "branch-b")
    authorization.assign_role(DomainRoleAssignment(
        "branch-role", "branch-owner", DomainRole.DOMAIN_LEAD, ModalityDomain.NOVEL, branch_scope, "fixture-admin",
    ))
    membership = MembershipAuthorizationService(identity, authorization)
    resolver = TrustedSessionResolver()
    resolver.register("opaque-branch-session", SessionContext("session-b", "client-b", "branch-owner", "workspace-b"))
    scope = {
        "mode": "collaboration", "novel_id": "project-b", "workspace_id": "workspace-b",
        "storyline_id": "story-b", "branch_id": "branch-b",
    }
    branch_manuscripts = BranchManuscriptService(ExperimentalStore(tmp_path, "file"), novels, chapters, scopes)
    novels.branch_authority = branch_manuscripts.for_scope
    branch_manuscripts.for_scope(scope).create("project-b", {"title": "Branch", "content": "BRANCH_ONLY_TEXT"})
    service = ExportJobService(tmp_path, novels.export, snapshotter=novels.export_snapshot)
    settings = SimpleNamespace(enable_collaboration_runtime=True, enable_packaged_runtime=False)
    monkeypatch.setattr(api, "settings", settings)
    monkeypatch.setattr(main_module, "settings", settings)
    monkeypatch.setattr(api, "novel_service", novels)
    monkeypatch.setattr(api, "export_job_service", service)
    monkeypatch.setattr(api, "collaboration_scope_service", scopes)
    monkeypatch.setattr(api, "membership_authorization_service", membership)
    monkeypatch.setattr(api, "trusted_session_resolver", resolver)
    monkeypatch.setattr(main_module, "trusted_session_resolver", resolver)
    client = TestClient(main_module.app)
    client.headers.update({"X-Session-Token": "opaque-branch-session", "X-Branch-Id": "branch-b"})
    try:
        created = client.post("/api/exports?novel_id=project-b", json={"format": "txt"})
        assert created.status_code == 202
        job = _wait_for_status(service, created.json()["id"], "succeeded")
        assert job["status"] == "succeeded"
        # This actor has only BRANCH rights; the project fallback must fail.
        actor = resolver.resolve("opaque-branch-session")
        project_scope = AuthorizationScope(ScopeKind.PROJECT, "workspace-b", "project-b")
        assert membership.is_allowed(actor, "domain.read", ModalityDomain.NOVEL, branch_scope)
        assert not membership.is_allowed(actor, "domain.read", ModalityDomain.NOVEL, project_scope)
        yield SimpleNamespace(
            client=client, service=service, job=job, scope=scope,
            authorization=authorization, project_scope=project_scope, identity=identity,
        )
    finally:
        service._pool.shutdown(wait=True)


def test_real_branch_export_snapshot_allows_branch_only_reader_and_respects_flag(real_branch_export, monkeypatch):
    from app.services.export_snapshot_authority import branch_snapshot_owned

    fixture = real_branch_export
    job = fixture.service.get(fixture.job["id"])
    assert job["permission_context"]["actor_id"] == "branch-owner"
    assert branch_snapshot_owned(job["snapshot"], fixture.scope)
    url = f"/api/exports/{job['id']}/download"
    downloaded = fixture.client.get(url)
    assert downloaded.status_code == 200
    assert "BRANCH_ONLY_TEXT" in downloaded.text
    assert "PROJECT_ONLY_SECRET" not in downloaded.text
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "")
    disabled = fixture.client.get(url)
    assert disabled.status_code == 404
    assert disabled.json()["detail"]["code"] == "EXPERIMENTAL_FEATURE_DISABLED"


@pytest.mark.parametrize("damage", ["missing-snapshot", "wrong-authority", "wrong-digest", "project-dataset"])
def test_real_branch_export_without_valid_snapshot_requires_independent_project_rights(real_branch_export, damage):
    from app.authorization import DomainRole, DomainRoleAssignment, ModalityDomain
    from app.services.export_snapshot_authority import branch_snapshot_owned

    fixture = real_branch_export
    rows = fixture.service._read()
    job = rows[fixture.job["id"]]
    if damage == "missing-snapshot":
        job["snapshot"] = None
    elif damage == "wrong-authority":
        job["snapshot"]["manuscript_authority"] = "PROJECT_MANUSCRIPT_V1"
    elif damage == "wrong-digest":
        job["snapshot"]["source"]["chapters"][0]["document_digest"] = "0" * 64
    else:
        job["snapshot"]["source"]["datasets"]["characters"] = [{"name": "Project-owned character"}]
    assert not branch_snapshot_owned(job["snapshot"], fixture.scope)
    fixture.service._write(rows)

    for method, suffix in (("get", ""), ("get", "/download"), ("post", "/cancel"), ("post", "/retry")):
        response = getattr(fixture.client, method)(f"/api/exports/{job['id']}{suffix}")
        assert response.status_code == 404
        assert response.json()["detail"] == "export job not found"
    assert fixture.service.get(job["id"]) == job

    # Historical artifacts remain available to this exact owner if the real
    # permission service independently grants PROJECT access. No gate is stubbed.
    fixture.authorization.assign_role(DomainRoleAssignment(
        "project-role", "branch-owner", DomainRole.DOMAIN_LEAD, ModalityDomain.NOVEL,
        fixture.project_scope, "fixture-admin",
    ))
    downloaded = fixture.client.get(f"/api/exports/{job['id']}/download")
    assert downloaded.status_code == 200
    assert "BRANCH_ONLY_TEXT" in downloaded.text


def test_real_branch_export_rejects_membership_revoked_after_completion(real_branch_export):
    from app.identity import IdentityStatus

    fixture = real_branch_export
    url = f"/api/exports/{fixture.job['id']}/download"
    assert fixture.client.get(url).status_code == 200
    fixture.identity.set_membership_status("branch-owner", "workspace-b", IdentityStatus.INACTIVE)
    denied = fixture.client.get(url)
    assert denied.status_code == 404
    assert denied.json()["detail"] == "export job not found"
