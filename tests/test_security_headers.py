"""Local-host response security headers.

The packaged/development runtime is a loopback HTTP server. Every response,
including the early fail-closed denials that never reach a route, must carry the
content-sniffing, referrer and framing boundaries. Routes are allowed to set a
stricter value of their own (asset downloads already set nosniff).
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

REQUIRED = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}


def _assert_headers(response):
    for name, value in REQUIRED.items():
        assert response.headers.get(name) == value, (name, response.headers.get(name))


def test_successful_health_response_carries_security_headers():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    _assert_headers(response)


def test_route_level_error_carries_security_headers():
    with TestClient(app) as client:
        response = client.get("/api/novels/does-not-exist")
    assert response.status_code == 404
    _assert_headers(response)


def test_early_runtime_denial_carries_security_headers():
    """The loopback gate returns before routing; headers must still be present."""
    with TestClient(app, client=("192.168.1.44", 50000)) as client:
        response = client.get("/novels")
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "LOCAL_RUNTIME_LOOPBACK_REQUIRED"
    _assert_headers(response)
