from fastapi.testclient import TestClient

from app.main import app


def test_versioned_core_api_alias_matches_legacy_contract():
    client = TestClient(app)
    for path in ("health", "providers", "asset-providers"):
        legacy = client.get(f"/api/{path}")
        versioned = client.get(f"/api/v1/{path}")
        assert versioned.status_code == legacy.status_code == 200
        assert versioned.json() == legacy.json()


def test_versioned_routes_are_published_in_openapi():
    paths = app.openapi()["paths"]
    assert "/api/v1/health" in paths
    assert "/api/v1/collaboration/admin/workspaces" in paths
    assert "/api/v1/packaged/bootstrap" in paths
    assert "/api/v1/exports/{job_id}/download" in paths
    assert "/api/v1/exports/{job_id}/cancel" in paths
    assert "/api/v1/exports/{job_id}/retry" in paths
    # Keep the existing desktop/frontend contract available during migration.
    assert "/api/health" in paths
