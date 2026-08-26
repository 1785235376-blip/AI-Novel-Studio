from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.actor_context import ActorContext
from app.collaboration_api import CollaborationReadService
from app.packaging.bootstrap_api import PackagedBootstrapRegistry, create_packaged_bootstrap_router
from app.packaging.local_session_bootstrap import (
    BootstrapDenied,
    BootstrapState,
    LocalSessionBootstrap,
    TrustedLocalIdentity,
)
from app.packaging.runtime_identity import RuntimeIdentity
from app.trusted_sessions import TrustedSessionResolver
from app.trusted_sessions import create_runtime_session_resolver


ORIGIN = "http://127.0.0.1:41831"


def build(*, clock=lambda: 100.0, events=None):
    runtime = RuntimeIdentity.create()
    sessions = TrustedSessionResolver()
    manager = LocalSessionBootstrap(
        runtime=runtime,
        sessions=sessions,
        trusted_identity=TrustedLocalIdentity("local-author", "workspace-a"),
        expected_origin=ORIGIN,
        ttl_seconds=30,
        clock=clock,
        event_sink=(events if events is not None else []).append,
    )
    return runtime, sessions, manager, manager.take_launcher_secret()


def exchange(manager, runtime, secret):
    return manager.exchange(
        bootstrap_secret=secret,
        runtime_instance_id=runtime.runtime_instance_id,
        origin=ORIGIN,
        remote_host="127.0.0.1",
    )


def test_single_use_exchange_registers_server_owned_actor_context():
    runtime, sessions, manager, secret = build()
    receipt = exchange(manager, runtime, secret)
    actor = sessions.resolve(receipt.session_token)
    assert (actor.actor_id, actor.workspace_id) == ("local-author", "workspace-a")
    assert actor.session.client_id == f"windows-runtime:{runtime.runtime_instance_id}"
    assert manager.state is BootstrapState.USED
    with pytest.raises(BootstrapDenied):
        exchange(manager, runtime, secret)
    with pytest.raises(ValueError):
        ActorContext("local-author", "workspace-b", actor.session)


def test_bootstrap_secret_is_high_entropy_per_launch_and_transferred_once():
    _, _, first, first_secret = build()
    _, _, second, second_secret = build()
    assert first_secret != second_secret
    assert len(first_secret) >= 64
    assert len(second_secret) >= 64
    with pytest.raises(RuntimeError):
        first.take_launcher_secret()


def test_packaged_runtime_has_no_development_session_fallback():
    with pytest.raises(RuntimeError, match="cannot load development sessions"):
        create_runtime_session_resolver(packaged_runtime=True, dev_sessions_json='[{"token":"dev"}]')
    resolver = create_runtime_session_resolver(packaged_runtime=True, dev_sessions_json="")
    with pytest.raises(KeyError):
        resolver.resolve("dev-token")
    with pytest.raises(RuntimeError, match="trusted collaboration"):
        create_runtime_session_resolver(
            packaged_runtime=True, dev_sessions_json="", collaboration_runtime=False
        )


def test_issued_session_crosses_real_authorization_boundary_without_workspace_leak():
    runtime, sessions, manager, secret = build()
    token = exchange(manager, runtime, secret).session_token

    class Scopes:
        def validate_scope(self, _scope): return None

    class MembershipAuthorization:
        def require(self, actor, _permission, _domain, scope):
            if actor.workspace_id != scope.workspace_id:
                raise PermissionError("workspace isolation")

    service = CollaborationReadService(
        sessions=sessions,
        membership_authorization=MembershipAuthorization(),
        identity=None,
        authorization=None,
        scopes=Scopes(),
        chapters=None,
        generations=None,
        lore_repository=None,
    )
    actor, scope = service.context(token, "workspace-a", "project", "story", "branch")
    assert actor.actor_id == "local-author"
    assert scope.workspace_id == "workspace-a"
    with pytest.raises(Exception) as denied:
        service.context(token, "workspace-b", "project", "story", "branch")
    assert getattr(denied.value, "status_code", None) == 403


@pytest.mark.parametrize(
    ("override", "code"),
    [
        ({"bootstrap_secret": "wrong"}, "BOOTSTRAP_DENIED"),
        ({"runtime_instance_id": "wrong-runtime"}, "BOOTSTRAP_DENIED"),
        ({"origin": "http://127.0.0.1:41832"}, "BOOTSTRAP_ORIGIN_DENIED"),
        ({"remote_host": "127.0.0.2"}, "BOOTSTRAP_LOOPBACK_REQUIRED"),
    ],
)
def test_invalid_exchange_fails_closed_without_consuming_valid_secret(override, code):
    runtime, sessions, manager, secret = build()
    values = {
        "bootstrap_secret": secret,
        "runtime_instance_id": runtime.runtime_instance_id,
        "origin": ORIGIN,
        "remote_host": "127.0.0.1",
    }
    values.update(override)
    with pytest.raises(BootstrapDenied) as error:
        manager.exchange(**values)
    assert error.value.code == code
    assert manager.state is BootstrapState.ACTIVE
    assert exchange(manager, runtime, secret).session_token


def test_request_origin_comparison_is_exact():
    runtime, _, manager, secret = build()
    with pytest.raises(BootstrapDenied) as error:
        manager.exchange(
            bootstrap_secret=secret,
            runtime_instance_id=runtime.runtime_instance_id,
            origin=ORIGIN + "/",
            remote_host="127.0.0.1",
        )
    assert error.value.code == "BOOTSTRAP_ORIGIN_DENIED"


def test_expiry_runtime_invalidation_and_restart_are_fail_closed():
    now = [10.0]
    runtime, sessions, manager, secret = build(clock=lambda: now[0])
    now[0] = 41.0
    with pytest.raises(BootstrapDenied):
        exchange(manager, runtime, secret)
    assert manager.state is BootstrapState.EXPIRED

    runtime2, sessions2, manager2, secret2 = build()
    token = exchange(manager2, runtime2, secret2).session_token
    manager2.invalidate()
    with pytest.raises(KeyError):
        sessions2.resolve(token)
    assert manager2.state is BootstrapState.INVALIDATED
    runtime3, _, manager3, _ = build()
    with pytest.raises(BootstrapDenied):
        manager3.exchange(
            bootstrap_secret=secret2,
            runtime_instance_id=runtime2.runtime_instance_id,
            origin=ORIGIN,
            remote_host="127.0.0.1",
        )
    assert runtime3.runtime_instance_id != runtime2.runtime_instance_id
    with pytest.raises(BootstrapDenied):
        manager3.exchange(
            bootstrap_secret=secret2,
            runtime_instance_id=runtime3.runtime_instance_id,
            origin=ORIGIN,
            remote_host="127.0.0.1",
        )


def test_concurrent_replay_has_exactly_one_winner():
    runtime, _, manager, secret = build()
    barrier = threading.Barrier(3)
    outcomes: list[str] = []

    def worker():
        barrier.wait()
        try:
            exchange(manager, runtime, secret)
            outcomes.append("accepted")
        except BootstrapDenied:
            outcomes.append("denied")

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()
    assert sorted(outcomes) == ["accepted", "denied"]


def test_origin_contract_rejects_paths_credentials_and_non_loopback():
    runtime = RuntimeIdentity.create()
    sessions = TrustedSessionResolver()
    for origin in (
        "http://localhost:41831",
        "https://127.0.0.1:41831",
        "http://user@127.0.0.1:41831",
        "http://127.0.0.1:41831/path",
        "http://127.0.0.1:41831?x=1",
    ):
        with pytest.raises(ValueError):
            LocalSessionBootstrap(
                runtime=runtime,
                sessions=sessions,
                trusted_identity=TrustedLocalIdentity("actor", "workspace"),
                expected_origin=origin,
            )


def test_http_contract_is_post_only_body_only_no_store_and_disabled_by_default():
    runtime, sessions, manager, secret = build()
    registry = PackagedBootstrapRegistry()
    registry.configure(manager)
    enabled = [True]
    app = FastAPI()
    app.include_router(create_packaged_bootstrap_router(registry, enabled=lambda: enabled[0]))
    client = TestClient(app, client=("127.0.0.1", 50000))

    assert client.get("/api/packaged/bootstrap").status_code == 405
    rejected = client.post(
        "/api/packaged/bootstrap",
        headers={"Origin": ORIGIN},
        json={
            "bootstrap_secret": secret,
            "runtime_instance_id": runtime.runtime_instance_id,
            "actor_id": "spoofed",
        },
    )
    assert rejected.status_code == 422
    response = client.post(
        "/api/packaged/bootstrap",
        headers={"Origin": ORIGIN},
        json={"bootstrap_secret": secret, "runtime_instance_id": runtime.runtime_instance_id},
    )
    assert response.status_code == 200
    assert set(response.json()) == {"session_token"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert sessions.resolve(response.json()["session_token"]).workspace_id == "workspace-a"

    enabled[0] = False
    assert client.post(
        "/api/packaged/bootstrap",
        headers={"Origin": ORIGIN},
        json={"bootstrap_secret": "anything", "runtime_instance_id": runtime.runtime_instance_id},
    ).status_code == 404


def test_registry_rejects_origin_that_would_not_pass_production_cors():
    runtime, _, manager, _ = build()
    registry = PackagedBootstrapRegistry(expected_origin="http://127.0.0.1:49999")
    with pytest.raises(ValueError, match="configured frontend origin"):
        registry.configure(manager)


def test_packaged_origin_can_be_used_as_the_exact_cors_allow_origin():
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[ORIGIN],
        allow_methods=["POST"],
        allow_headers=["content-type"],
    )
    app.include_router(create_packaged_bootstrap_router(PackagedBootstrapRegistry()))
    client = TestClient(app, client=("127.0.0.1", 50002))
    preflight = client.options(
        "/api/packaged/bootstrap",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == ORIGIN


def test_production_fail_closed_middleware_allows_only_enabled_packaged_posts():
    import app.main as main_module
    from app.config import settings
    from app.dependencies import packaged_bootstrap_registry

    runtime, _, manager, secret = build()
    original_packaged = settings.enable_packaged_runtime
    original_collaboration = settings.enable_collaboration_runtime
    original_origin = settings.frontend_origin
    object.__setattr__(settings, "enable_packaged_runtime", True)
    object.__setattr__(settings, "enable_collaboration_runtime", True)
    object.__setattr__(settings, "frontend_origin", ORIGIN)
    packaged_bootstrap_registry.configure(manager)
    try:
        client = TestClient(main_module.app, client=("127.0.0.1", 50001))
        response = client.post(
            "/api/packaged/bootstrap",
            headers={"Origin": ORIGIN},
            json={"bootstrap_secret": secret, "runtime_instance_id": runtime.runtime_instance_id},
        )
        assert response.status_code == 200
        token = response.json()["session_token"]
        assert client.get("/api/asset-providers", headers={"X-Session-Token": token}).status_code == 200
        assert client.get("/api/asset-providers").status_code == 401
        assert client.get("/api/asset-providers", headers={"X-Session-Token": "invalid"}).status_code == 401
        assert client.get("/novels", headers={"X-Session-Token": token}).status_code == 200
        assert client.get("/api/packaged/bootstrap").status_code == 501
        assert client.post("/api/packaged/initial-workspace", json={}).status_code == 401
        assert client.post("/api/packaged/not-bootstrap", json={}).status_code == 501

        object.__setattr__(settings, "enable_collaboration_runtime", False)
        assert client.get("/novels").status_code == 501
    finally:
        packaged_bootstrap_registry.clear()
        object.__setattr__(settings, "enable_packaged_runtime", original_packaged)
        object.__setattr__(settings, "enable_collaboration_runtime", original_collaboration)
        object.__setattr__(settings, "frontend_origin", original_origin)


def test_runtime_metadata_logs_and_files_remain_secret_free(tmp_path: Path):
    events: list[str] = []
    before = set(tmp_path.rglob("*"))
    runtime, sessions, manager, secret = build(events=events)
    token = exchange(manager, runtime, secret).session_token
    after = set(tmp_path.rglob("*"))
    serialized = json.dumps(manager.safe_metadata, sort_keys=True)
    assert secret not in serialized
    assert token not in serialized
    assert runtime.ownership_nonce not in serialized
    assert before == after
    assert events == ["bootstrap.created", "bootstrap.accepted", "session.issued"]
    assert all(secret not in event and token not in event for event in events)
    assert sessions.resolve(token).session.session_id.startswith("packaged:")


def test_frontend_does_not_persist_or_transport_packaged_bootstrap_material():
    frontend = Path(__file__).resolve().parents[1] / "frontend" / "src"
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in frontend.rglob("*")
        if path.is_file() and path.suffix in {".ts", ".tsx", ".js", ".jsx"}
    )
    assert "/api/packaged/bootstrap" not in source
    assert "bootstrap_secret" not in source
    assert "runtime_instance_id" not in source
