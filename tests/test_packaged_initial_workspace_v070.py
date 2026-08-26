from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.actor_context import SessionContext
from app.packaging.bootstrap_api import PackagedBootstrapRegistry, create_packaged_bootstrap_router
from app.packaging.initial_workspace import PackagedInitialWorkspaceProvisioner
from app.packaging.local_session_bootstrap import BootstrapDenied, LocalSessionBootstrap, TrustedLocalIdentity
from app.packaging.runtime_identity import RuntimeIdentity
from app.repositories.file.identity import FileIdentityRepository
from app.repositories.file.scope import FileAuthorizationRepository, FileScopeRepository
from app.trusted_sessions import TrustedSessionResolver


ORIGIN = "http://127.0.0.1:41831"


def packaged_client(tmp_path):
    runtime = RuntimeIdentity.create()
    sessions = TrustedSessionResolver()
    manager = LocalSessionBootstrap(
        runtime=runtime,
        sessions=sessions,
        trusted_identity=TrustedLocalIdentity("local-author", "workspace-a"),
        expected_origin=ORIGIN,
    )
    secret = manager.take_launcher_secret()
    token = manager.exchange(
        bootstrap_secret=secret,
        runtime_instance_id=runtime.runtime_instance_id,
        origin=ORIGIN,
        remote_host="127.0.0.1",
    ).session_token
    registry = PackagedBootstrapRegistry()
    registry.configure(manager)
    app = FastAPI()
    app.include_router(create_packaged_bootstrap_router(
        registry,
        enabled=lambda: True,
        initial_workspace_provisioner=PackagedInitialWorkspaceProvisioner(FileScopeRepository(tmp_path)),
    ))
    return TestClient(app, client=("127.0.0.1", 50000)), token, manager, sessions


def headers(token):
    return {"X-Session-Token": token}


def test_clean_packaged_session_provisions_complete_state_and_is_idempotent(tmp_path):
    client, token, _, _ = packaged_client(tmp_path)
    first = client.post("/api/packaged/initial-workspace", headers=headers(token), json={})
    second = client.post("/api/packaged/initial-workspace", headers=headers(token), json={})
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json() == {"id": "workspace-a", "name": "我的创作空间"}
    identity = FileIdentityRepository(tmp_path)
    assert identity.get_user("local-author")["status"] == "ACTIVE"
    assert identity.list_memberships(user_id="local-author") == [identity.get_membership("local-author", "workspace-a")]
    assert identity.get_membership("local-author", "workspace-a")["status"] == "ACTIVE"
    roles = FileAuthorizationRepository(tmp_path).list_role_assignments("local-author")
    assert [(row["role"], row["domain"], row["scope"]["workspace_id"]) for row in roles] == [("ADMIN", "NOVEL", "workspace-a")]
    events = FileAuthorizationRepository(tmp_path).list_audit_events()
    assert len(events) == 1 and events[0]["action"] == "WORKSPACE_CREATED"
    assert all(secret not in str(events) for secret in (token, "bootstrap_secret", "ownership_nonce"))


def test_request_accepts_no_authoritative_identity_fields(tmp_path):
    client, token, _, _ = packaged_client(tmp_path)
    for field in ("actor_id", "user_id", "workspace_id", "role", "permission", "domain", "scope"):
        response = client.post("/api/packaged/initial-workspace", headers=headers(token), json={field: "spoofed"})
        assert response.status_code == 422
    assert FileScopeRepository(tmp_path).list("workspaces") == []


def test_foreign_development_expired_and_old_runtime_sessions_are_rejected(tmp_path):
    client, token, manager, sessions = packaged_client(tmp_path)
    sessions.register("development", SessionContext("dev", "browser", "local-author", "workspace-a"))
    assert client.post("/api/packaged/initial-workspace", headers=headers("development"), json={}).status_code == 401
    assert client.post("/api/packaged/initial-workspace", headers=headers("foreign"), json={}).status_code == 401
    manager.invalidate()
    assert client.post("/api/packaged/initial-workspace", headers=headers(token), json={}).status_code == 401
    with pytest.raises(BootstrapDenied):
        manager.resolve_issued_session(token)


@pytest.mark.parametrize("status", ["ACTIVE", "INACTIVE"])
def test_any_unrelated_membership_rejects_provisioning(tmp_path, status):
    client, token, _, _ = packaged_client(tmp_path)
    scope = FileScopeRepository(tmp_path)
    identity = FileIdentityRepository(tmp_path)
    now = datetime.now(timezone.utc).isoformat()
    identity.save_user({"id": "local-author", "display_name": "本机作者", "status": "ACTIVE", "created_at": now, "updated_at": now, "metadata": None})
    scope.create("workspaces", {"id": "other", "name": "Other"})
    identity.save_membership({"id": "membership:other:local-author", "user_id": "local-author", "workspace_id": "other", "status": status, "created_at": now, "updated_at": now, "metadata": None})
    assert client.post("/api/packaged/initial-workspace", headers=headers(token), json={}).status_code == 409
    assert [row["id"] for row in scope.list("workspaces")] == ["other"]


def test_existing_target_with_partial_state_fails_closed(tmp_path):
    client, token, _, _ = packaged_client(tmp_path)
    scope = FileScopeRepository(tmp_path)
    scope.create("workspaces", {"id": "workspace-a", "name": "Unexpected"})
    assert client.post("/api/packaged/initial-workspace", headers=headers(token), json={}).status_code == 409
    assert FileIdentityRepository(tmp_path).list_memberships(user_id="local-author") == []


def test_file_provisioning_rolls_back_every_file_on_assignment_failure(tmp_path, monkeypatch):
    repository = FileScopeRepository(tmp_path)
    monkeypatch.setattr(
        FileAuthorizationRepository,
        "save_role_assignment_with_audit",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("injected audit failure")),
    )
    with pytest.raises(RuntimeError, match="injected audit failure"):
        repository.provision_initial_workspace("local-author", "workspace-a", "我的创作空间", "本机作者")
    assert repository.list("workspaces") == []
    assert FileIdentityRepository(tmp_path).list_users() == []
    assert FileIdentityRepository(tmp_path).list_memberships() == []
    assert FileAuthorizationRepository(tmp_path).list_role_assignments() == []


def test_concurrent_file_calls_return_one_workspace_and_one_audit(tmp_path):
    def provision():
        return FileScopeRepository(tmp_path).provision_initial_workspace("local-author", "workspace-a", "我的创作空间", "本机作者")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [future.result(timeout=10) for future in (pool.submit(provision), pool.submit(provision))]
    assert results[0] == results[1]
    assert len(FileScopeRepository(tmp_path).list("workspaces")) == 1
    assert len(FileIdentityRepository(tmp_path).list_memberships(user_id="local-author")) == 1
    assert len(FileAuthorizationRepository(tmp_path).list_audit_events()) == 1
