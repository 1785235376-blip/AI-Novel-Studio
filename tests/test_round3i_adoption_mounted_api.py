"""Mounted-app route registration + fail-closed regression (P0/P1 deliverable).

This is the guard against the false "source is wired but actually unreachable" conclusion.
It asserts against the REAL ASGI app with real requests, because starlette 1.6.0 represents an
include as a `_IncludedRouter` node rather than flattened APIRoutes, so scanning route paths
cannot decide reachability.

Discrimination this file relies on, verified in the same app:
  * declared route, resource missing -> {"detail": "Not found: <id>", "code": "HTTP_404"}
  * undeclared path                  -> {"detail": "Not Found"}   (framework default)
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("fastapi")

HARNESS_MISSING = "requires the isolated runner (scripts/run_v2_checks.py) that sets PROJECT_ROOT"


@pytest.fixture(scope="module")
def client():
    if os.environ.get("PROJECT_ROOT") is None:
        pytest.skip(HARNESS_MISSING)
    os.environ.setdefault("EXPERIMENTAL_FEATURES", "narrative_production_v2,asset_lineage_v2")
    from fastapi.testclient import TestClient

    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


MISSING = "/api/projects/does-not-exist/studio/documents/d1"


def test_the_real_app_serves_the_studio_api_at_all(client):
    """Control: the app object under test really does serve /api routes."""
    assert client.get("/api/health").status_code == 200


def test_an_undeclared_path_is_the_frameworks_own_404(client):
    """Calibration: this is what 'route not registered' looks like in this app."""
    resp = client.get(f"{MISSING}/nope-not-declared")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Not Found"


def test_the_adoption_get_route_is_mounted_and_reaches_the_handler(client):
    """A handler-executed 404, NOT the framework's route-not-found."""
    for prefix in ("/api", "/api/v1"):
        resp = client.get(f"{prefix}/projects/does-not-exist/studio/documents/d1/prompt-adoption")
        assert resp.status_code == 404, f"{prefix} adoption GET not reachable"
        body = resp.json()
        # The handler ran and looked the project up: it is NOT the framework default.
        assert body["detail"] != "Not Found", f"{prefix} adoption GET looks unregistered"
        assert body.get("code") == "HTTP_404"


def test_the_adoption_post_route_is_mounted_and_validates_its_dto(client):
    """A 422 naming a DTO field proves the route matched AND the body was validated."""
    resp = client.post(f"{MISSING}/shots/s1/prompt-adoption", json={})
    assert resp.status_code == 422, "adoption POST not reachable"
    fields = {tuple(item["loc"]) for item in resp.json()["detail"]}
    assert ("body", "shot_id") in fields


def test_the_adoption_post_is_fail_closed_until_write_time_verification_is_proven(client):
    """POST must refuse rather than perform an unverified cross-owner write."""
    from app.creative.prompt_adoption_api import PROMPT_ADOPTION_WRITE_ENABLED
    assert PROMPT_ADOPTION_WRITE_ENABLED is False, "write must stay closed until P3 is proven"
    resp = client.post(f"{MISSING}/shots/s1/prompt-adoption", json={
        "shot_id": "s1", "family_id": "f1", "asset_id": "a1", "revision": 1,
        "expected_digest": "d" * 64, "expected_version": 1,
        "expected_digest_target": "e" * 64, "request_id": "r1"})
    assert resp.status_code == 503, "a fully valid body must still be refused while closed"
    assert resp.json()["detail"]["code"] == "PROMPT_ADOPTION_WRITE_TIME_UNVERIFIED"


def test_wrong_methods_are_refused(client):
    assert client.put(f"{MISSING}/shots/s1/prompt-adoption", json={}).status_code in {404, 405}
    assert client.delete(f"{MISSING}/prompt-adoption").status_code in {404, 405}
