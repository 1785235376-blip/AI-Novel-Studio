"""Mounted host-isolation regressions. Synthetic sessions and cached paths only."""
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.actor_context import SessionContext
from app.trusted_sessions import TrustedSessionResolver


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
@pytest.mark.parametrize("enabled", [True, False])
def test_collaboration_session_cannot_read_host_cache_when_v2_enabled_or_disabled(monkeypatch, prefix, enabled):
    import app.main as main
    monkeypatch.setattr(main, "settings", replace(main.settings,
        enable_collaboration_runtime=True, enable_packaged_runtime=False))
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2" if enabled else "")
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    sessions = TrustedSessionResolver()
    sessions.register("synthetic-workspace-administrator", SessionContext("s", "remote-client", "administrator", "workspace"))
    monkeypatch.setattr(main, "trusted_session_resolver", sessions)
    calls = []
    def private_snapshot():
        calls.append("read")
        return {"settings": {"scan_roots": ["/synthetic-host-private/models"]},
                "scan": {"environment_schema_version": 2, "model_files": [{"path": "/synthetic-host-private/model.gguf"}]}}
    monkeypatch.setattr(main.local_ai_discovery, "snapshot", private_snapshot)
    response = TestClient(main.app).get(prefix + "/model-center/local-ai",
        headers={"X-Session-Token": "synthetic-workspace-administrator"})
    assert response.status_code == 403
    assert response.json()["code"] == "LOCAL_AI_HOST_AUTHORITY_UNAVAILABLE"
    assert "synthetic-host-private" not in response.text
    assert calls == []


@pytest.fixture
def host(monkeypatch):
    import app.main as main
    monkeypatch.setattr(main, "settings", replace(main.settings,
        enable_collaboration_runtime=False, enable_packaged_runtime=False,
        frontend_origin="http://127.0.0.1:5173"))
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2")
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    sessions = TrustedSessionResolver()
    session = SessionContext("host-session", "host-client", "host-actor", "host-workspace")
    sessions.register("synthetic-current-host", session)
    monkeypatch.setattr(main, "trusted_session_resolver", sessions)
    calls = []
    def snapshot():
        calls.append("snapshot")
        return {"settings": {"scan_roots": ["/synthetic-host-private/models"]},
                "scan": {"environment_schema_version": 2, "model_files": []}}
    monkeypatch.setattr(main.local_ai_discovery, "snapshot", snapshot)
    return main, sessions, session, calls


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_only_existing_local_session_reads_private_uncached_snapshot(host, prefix):
    main, _, _, calls = host
    response = TestClient(main.app).get(prefix + "/model-center/local-ai",
        headers={"X-Session-Token": "synthetic-current-host", "Origin": main.settings.frontend_origin})
    assert response.status_code == 200
    assert calls == ["snapshot"]
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "synthetic-current-host" not in response.text


@pytest.mark.parametrize("token", [None, "forged-unregistered-host"])
def test_loopback_and_host_actor_headers_never_replace_a_registered_session(host, token):
    main, _, _, calls = host
    headers = {"X-Actor-ID": "host-actor", "X-Workspace-Role": "ADMIN"}
    if token:
        headers["X-Session-Token"] = token
    response = TestClient(main.app).get("/api/model-center/local-ai", headers=headers)
    assert response.status_code == 401
    assert response.headers["Cache-Control"] == "no-store"
    assert "synthetic-host-private" not in response.text and calls == []


@pytest.mark.parametrize("header,value", [("Forwarded", "for=127.0.0.1"),
    ("X-Forwarded-For", "127.0.0.1"), ("X-Real-IP", "127.0.0.1"),
    ("X-Forwarded-Host", "localhost"), ("X-Forwarded-Proto", "http"),
    ("Origin", "https://untrusted.example")])
def test_forwarded_identity_and_wrong_origin_are_not_host_provenance(host, header, value):
    main, _, _, calls = host
    response = TestClient(main.app).get("/api/model-center/local-ai",
        headers={"X-Session-Token": "synthetic-current-host", header: value})
    assert response.status_code == 403
    assert response.headers["Cache-Control"] == "no-store"
    assert "synthetic-host-private" not in response.text and calls == []


def test_remote_peer_with_valid_token_and_forged_forwarding_cannot_read_host(host):
    main, _, _, calls = host
    client = TestClient(main.app, client=("203.0.113.10", 41000))
    response = client.get("/api/model-center/local-ai", headers={
        "X-Session-Token": "synthetic-current-host", "X-Forwarded-For": "127.0.0.1"})
    assert response.status_code == 403
    assert "synthetic-host-private" not in response.text and calls == []


@pytest.mark.parametrize("change", ["revoke", "same_binding_aba", "replace_actor", "switch_runtime_mode"])
def test_late_authority_change_redacts_a_captured_host_snapshot(host, monkeypatch, change):
    main, sessions, session, _ = host
    def late_snapshot():
        if change == "switch_runtime_mode":
            monkeypatch.setattr(main, "settings", replace(main.settings, enable_collaboration_runtime=True))
        else:
            sessions.revoke("synthetic-current-host")
            if change == "same_binding_aba":
                sessions.register("synthetic-current-host", session)
            elif change == "replace_actor":
                sessions.register("synthetic-current-host", SessionContext("different", "remote", "different", "w"))
        return {"secret": "/synthetic-host-private/late-response"}
    monkeypatch.setattr(main.local_ai_discovery, "snapshot", late_snapshot)
    response = TestClient(main.app).get("/api/model-center/local-ai", headers={"X-Session-Token": "synthetic-current-host"})
    assert response.status_code in {401, 403}
    assert response.headers["Cache-Control"] == "no-store"
    assert "synthetic-host-private" not in response.text


def test_turning_v2_off_does_not_declassify_previous_host_inventory(host, monkeypatch):
    main, _, _, calls = host
    client = TestClient(main.app)
    headers = {"X-Session-Token": "synthetic-current-host"}
    assert client.get("/api/model-center/local-ai", headers=headers).status_code == 200
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "")
    monkeypatch.setattr(main, "settings", replace(main.settings, enable_collaboration_runtime=True))
    response = client.get("/api/model-center/local-ai", headers=headers)
    assert response.status_code == 403
    assert "synthetic-host-private" not in response.text
    assert calls == ["snapshot"]


DISCOVERY_ROUTES = [
    ("GET", "", None), ("GET", "/environment", None),
    ("GET", "/onboarding/scan-scope", None),
    ("POST", "/onboarding/scan", {"scope_digest": "a" * 64, "confirmed": True}),
    ("POST", "/scan", None), ("GET", "/scan/old-cached-id", None),
    ("POST", "/scan/old-cached-id/cancel", None),
    ("PUT", "/settings", {"scan_roots": []}),
    ("POST", "/runtimes", {"name": "synthetic", "type": "OLLAMA", "endpoint": "http://127.0.0.1:11434"}),
    ("PUT", "/runtimes/old", {"name": "synthetic", "type": "OLLAMA", "endpoint": "http://127.0.0.1:11434"}),
    ("POST", "/candidates/old/validate", None), ("POST", "/candidates/old/register", None),
    ("PUT", "/registrations/old", {}), ("POST", "/registrations/old/enable", {"confirmed": True}),
    ("POST", "/registrations/old/disable", None), ("DELETE", "/registrations/old", None),
]


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
@pytest.mark.parametrize("method,path,body", DISCOVERY_ROUTES)
def test_every_production_discovery_surface_denies_nonpackaged_collaboration(host, monkeypatch, prefix, method, path, body):
    main, _, _, calls = host
    monkeypatch.setattr(main, "settings", replace(main.settings, enable_collaboration_runtime=True))
    response = TestClient(main.app).request(method, prefix + "/model-center/local-ai" + path,
        json=body, headers={"X-Session-Token": "synthetic-current-host"})
    assert response.status_code == 403
    assert response.json()["code"] == "LOCAL_AI_HOST_AUTHORITY_UNAVAILABLE"
    assert response.headers["Cache-Control"] == "no-store"
    assert "synthetic-host-private" not in response.text and calls == []


@pytest.fixture
def packaged(host, monkeypatch):
    from app.packaging.bootstrap_api import PackagedBootstrapRegistry
    from app.packaging.local_session_bootstrap import LocalSessionBootstrap, TrustedLocalIdentity
    from app.packaging.runtime_identity import RuntimeIdentity
    main, sessions, _, calls = host
    monkeypatch.setattr(main, "settings", replace(main.settings,
        enable_collaboration_runtime=True, enable_packaged_runtime=True))
    registry = PackagedBootstrapRegistry(expected_origin=main.settings.frontend_origin)
    manager = LocalSessionBootstrap(runtime=RuntimeIdentity("synthetic-runtime", "synthetic-owned-nonce"),
        sessions=sessions, trusted_identity=TrustedLocalIdentity("host-actor", "host-workspace"),
        expected_origin=main.settings.frontend_origin, bootstrap_secret="synthetic-one-shot-secret")
    registry.configure(manager)
    token = manager.exchange(bootstrap_secret=manager.take_launcher_secret(),
        runtime_instance_id="synthetic-runtime", origin=main.settings.frontend_origin,
        remote_host="127.0.0.1").session_token
    monkeypatch.setattr(main, "packaged_bootstrap_registry", registry)
    return main, sessions, registry, manager, token, calls


def test_current_bootstrap_provenance_is_required_even_for_an_existing_registered_token(packaged):
    main, _, _, _, token, calls = packaged
    client = TestClient(main.app)
    assert client.get("/api/model-center/local-ai", headers={"X-Session-Token": "synthetic-current-host"}).status_code == 401
    response = client.get("/api/model-center/local-ai", headers={"X-Session-Token": token})
    assert response.status_code == 200
    assert calls == ["snapshot"] and token not in response.text


@pytest.mark.parametrize("when", ["before", "during"])
@pytest.mark.parametrize("change", ["invalidate", "clear_registry", "revoke_session"])
def test_bootstrap_or_issued_session_revocation_cannot_return_cached_host_paths(packaged, monkeypatch, when, change):
    main, sessions, registry, manager, token, calls = packaged
    def revoke():
        if change == "invalidate": manager.invalidate()
        elif change == "clear_registry": registry.clear()
        else: sessions.revoke(token)
    if when == "before":
        revoke()
    else:
        def late_snapshot():
            revoke()
            return {"private": "/synthetic-host-private/late-bootstrap"}
        monkeypatch.setattr(main.local_ai_discovery, "snapshot", late_snapshot)
    response = TestClient(main.app).get("/api/model-center/local-ai", headers={"X-Session-Token": token})
    assert response.status_code == 401
    assert response.headers["Cache-Control"] == "no-store"
    assert "synthetic-host-private" not in response.text and calls == []
