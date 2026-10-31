"""Independent security boundary for the opt-in Local Interop Host surface.

``/api/local-interop`` is the browser-to-Host bridge that carries a project
session, permission grants and handoff/approval flows. This repository had no
test file referencing that surface, so the transport, request, default-off and
capability boundaries are pinned here against the real router and the real
``LocalInteropHost`` (with a synthetic provider, no project data).

Covered: direct-127.0.0.1 transport only (both API aliases), query-string
credential/unknown-parameter refusal, bounded request bodies, fixed error shape,
feature-flag default-off refusal for mutations, and read-only status under the
flag-off state. NOT covered: full connect/event-stream/handoff flows, packaged
Host sessions, real browser peers.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.local_interop.api import create_local_interop_router
from app.local_interop.errors import InteropFailure
from app.local_interop.host import LocalInteropHost

LOOPBACK = ("127.0.0.1", 51234)
FOREIGN = ("192.168.1.50", 51234)
FLAG_ENV = "EXPERIMENTAL_FEATURES"
FLAG = "local_tutor_interop_v1"


class FakeProvider:
    """Minimal provider contract: a known token and a revoked/unknown token."""

    def actor(self, token):
        if token == "token-known":
            return SimpleNamespace(actor_id="actor-synthetic", session_id="session-synthetic",
                                   workspace_id="workspace-synthetic")
        raise InteropFailure("SESSION_REQUIRED", 401)


@pytest.fixture
def host(monkeypatch):
    monkeypatch.setenv(FLAG_ENV, "")
    return LocalInteropHost(FakeProvider())


@pytest.fixture
def api(host):
    application = FastAPI()
    application.include_router(create_local_interop_router(host))
    application.include_router(create_local_interop_router(host, prefix="/api/v1/local-interop"))
    return application


@pytest.mark.parametrize("alias", ["/api", "/api/v1"])
def test_transport_requires_direct_loopback_client(api, alias):
    with TestClient(api) as client:  # default transport peer is "testclient"
        response = client.get(f"{alias}/local-interop/status",
                              headers={"X-Session-Token": "token-known"})
    assert response.status_code == 403
    assert response.json()["code"] == "TRANSPORT_ERROR"
    with TestClient(api, client=LOOPBACK) as client:
        response = client.get(f"{alias}/local-interop/status",
                              headers={"X-Session-Token": "token-known"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"


def test_foreign_client_is_refused_before_any_host_call(api):
    with TestClient(api, client=FOREIGN) as client:
        response = client.post("/api/local-interop/settings", json={"enabled": True})
    assert response.status_code == 403
    assert response.json()["code"] == "TRANSPORT_ERROR"


@pytest.mark.parametrize("query", [
    "session_id=x&after=0",
    "session_id=x&x_session_token=token-known",
    "session_id=x&junk=1",
])
def test_query_string_parameter_allowlist(api, query, host):
    with TestClient(api, client=LOOPBACK) as client:
        response = client.get("/api/local-interop/events?" + query)
    if query == "session_id=x&after=0":
        # Query shape is admitted; the synthetic host then refuses the unknown
        # session (proves the allowlist is not a blanket rejection).
        assert response.status_code in (401, 403)
    else:
        assert response.status_code == 400
        assert response.json()["code"] == "INVALID_MESSAGE"


def test_oversized_request_body_is_refused(api):
    with TestClient(api, client=LOOPBACK) as client:
        response = client.post("/api/local-interop/ask", json={
            "session_id": "session", "preview_id": "preview", "confirmed": True,
            "question": "x" * (96 * 1024),
        })
    assert response.status_code == 413
    assert response.json()["code"] == "INVALID_MESSAGE"


def test_validation_error_shape_is_fixed(api):
    with TestClient(api, client=LOOPBACK) as client:
        response = client.post("/api/local-interop/settings", json={"unknown": True})
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_MESSAGE"
    assert "unknown" not in response.text


def test_no_generic_rpc_surface(api):
    with TestClient(api, client=LOOPBACK) as client:
        for path in ("/api/local-interop/rpc", "/api/local-interop/fetch?url=http://169.254.169.254/"):
            assert client.get(path).status_code == 404
        assert client.get("/api/local-interop/status?cmd=export").status_code == 400


def test_flag_off_status_is_read_only_and_mutations_refused(api, host):
    with TestClient(api, client=LOOPBACK) as client:
        status = client.get("/api/local-interop/status", headers={"X-Session-Token": "token-known"})
        assert status.status_code == 200
        body = status.json()
        assert body["feature_enabled"] is False and body["enabled"] is False
        assert body["disabled_capabilities"] == ["model.execute", "project.write"]
        enabled = client.post("/api/local-interop/settings", json={"enabled": True},
                              headers={"X-Session-Token": "token-known"})
        assert enabled.status_code == 403
        assert enabled.json()["code"] == "PERMISSION_DENIED"


def test_unknown_or_missing_token_is_refused(api):
    with TestClient(api, client=LOOPBACK) as client:
        missing = client.get("/api/local-interop/status")
        unknown = client.get("/api/local-interop/status", headers={"X-Session-Token": "token-unknown"})
    # Even the read-only status projection resolves the Host actor first.
    for response in (missing, unknown):
        assert response.status_code == 401
        assert response.json()["code"] == "SESSION_REQUIRED"


def test_host_requires_feature_flag_and_enabled_owner_for_operations(host, monkeypatch):
    with pytest.raises(InteropFailure) as refused:
        host._session("token-known", "session-synthetic")
    assert (refused.value.code, refused.value.status) == ("PERMISSION_DENIED", 403)
    with pytest.raises(InteropFailure):
        host.configure("token-known", True)

    monkeypatch.setenv(FLAG_ENV, FLAG)
    assert host.configure("token-known", True)["enabled"] is True
    with pytest.raises(InteropFailure) as missing:
        host._session("token-known", "session-missing")
    assert (missing.value.code, missing.value.status) == ("SESSION_REVOKED", 401)


def test_host_revokes_owner_when_flag_turns_off(host, monkeypatch):
    monkeypatch.setenv(FLAG_ENV, FLAG)
    host.configure("token-known", True)
    monkeypatch.setenv(FLAG_ENV, "")
    with pytest.raises(InteropFailure) as denied:
        host._session("token-known", "session-missing")
    assert (denied.value.code, denied.value.status) == ("PERMISSION_DENIED", 403)
