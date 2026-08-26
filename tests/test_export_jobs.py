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


def test_export_download_route_returns_attachment(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import app.api as api

    fake = type("FakeExportService", (), {
        "download": lambda self, _job_id: {
            "content": b"fixture",
            "filename": "章节.md",
            "media_type": "text/markdown",
            "format": "markdown",
        },
    })()
    monkeypatch.setattr(api, "export_job_service", fake)
    local_app = FastAPI()
    local_app.include_router(api.router, prefix="/api")

    response = TestClient(local_app).get("/api/exports/job-1/download")
    assert response.status_code == 200
    assert response.content == b"fixture"
    assert response.headers["content-type"] == "text/markdown; charset=utf-8"
    assert response.headers["content-disposition"].startswith('attachment; filename="export.md";')


def test_export_download_route_reports_not_ready(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import app.api as api

    def unavailable(_self, _job_id):
        raise ExportJobUnavailable("running")

    fake = type("FakeExportService", (), {"download": unavailable})()
    monkeypatch.setattr(api, "export_job_service", fake)
    local_app = FastAPI()
    local_app.include_router(api.router, prefix="/api")

    response = TestClient(local_app).get("/api/exports/job-1/download")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "EXPORT_NOT_READY"
    assert response.json()["detail"]["details"]["status"] == "running"


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
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import app.api as api

    class FakeExportService:
        def cancel(self, job_id):
            return {"id": job_id, "status": "cancelled", "progress": 20}

        def retry(self, job_id):
            return {"id": "retry-1", "retry_of": job_id, "status": "queued", "progress": 0}

    monkeypatch.setattr(api, "export_job_service", FakeExportService())
    local_app = FastAPI()
    local_app.include_router(api.router, prefix="/api")
    client = TestClient(local_app)
    cancelled = client.post("/api/exports/job-1/cancel")
    retried = client.post("/api/exports/job-1/retry")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert retried.status_code == 202
    assert retried.json()["retry_of"] == "job-1"


class _ScopedExportService:
    def __init__(self):
        self.created_permission_context = None
        self.job = {
            "id": "job-1",
            "novel_id": "project-b",
            "status": "succeeded",
            "permission_context": {"branch_id": "branch-b"},
        }

    def create(self, novel_id, format, idempotency_key=None, *, permission_context=None):
        self.created_permission_context = permission_context
        return {**self.job, "novel_id": novel_id, "format": format, "permission_context": permission_context}

    def get(self, job_id):
        if job_id != self.job["id"]:
            raise FileNotFoundError(job_id)
        return self.job

    def download(self, job_id):
        return {"content": b"fixture", "filename": "export.txt", "media_type": "text/plain"}

    def cancel(self, job_id):
        return {**self.job, "status": "cancelled"}

    def retry(self, job_id):
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

        workspaces = {"session-a": "workspace-a", "session-b": "workspace-b"}
        if token not in workspaces:
            raise KeyError(token)
        return SimpleNamespace(actor_id=token, workspace_id=workspaces[token])


class _ExportMembership:
    def __init__(self, *, writable=True):
        self.writable = writable
        self.calls = []

    def require(self, actor, permission, domain, scope):
        self.calls.append((actor, permission, domain, scope))
        if permission == "domain.write" and not self.writable:
            raise PermissionError("read-only membership")


def _collaboration_export_client(monkeypatch, *, writable=True):
    from types import SimpleNamespace
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import app.api as api

    membership = _ExportMembership(writable=writable)
    monkeypatch.setattr(api, "settings", SimpleNamespace(enable_collaboration_runtime=True))
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
    client, membership, _ = _collaboration_export_client(monkeypatch)

    response = getattr(client, method)(path, headers={"X-Session-Token": "session-a"})

    assert response.status_code == 404
    assert response.json()["detail"] == "export job not found"
    assert membership.calls == []


def test_export_job_routes_apply_read_and_write_membership(monkeypatch):
    client, membership, _ = _collaboration_export_client(monkeypatch, writable=False)
    headers = {"X-Session-Token": "session-b"}

    downloaded = client.get("/api/exports/job-1/download", headers=headers)
    cancelled = client.post("/api/exports/job-1/cancel", headers=headers)

    assert downloaded.status_code == 200
    assert downloaded.content == b"fixture"
    assert cancelled.status_code == 404
    assert [call[1] for call in membership.calls] == ["domain.read", "domain.write"]
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
