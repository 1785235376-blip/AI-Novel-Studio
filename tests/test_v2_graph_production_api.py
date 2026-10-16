"""Mounted opt-in catalog and exact planning document picker Host boundary."""
import pytest
from test_r3_mounted_contracts import checked, mounted, prefix
from test_v2_independent_workspace_api import client
from test_v2_discovered_image_production_api import image_client
from test_v2_graph_image_api import image_graph_client


def test_production_catalog_is_opt_in_and_no_dispatch(image_graph_client):
    e = image_graph_client
    original = checked(e.client.get(e.graph_base + "/catalog?include_image=true", headers=e.headers))
    expanded = checked(e.client.get(e.graph_base + "/catalog?include_image=true&include_production=true", headers=e.headers))
    assert {row["id"] for row in expanded["definitions"]} - {row["id"] for row in original["definitions"]} == {
        "image_style", "image_upscale", "director_plan", "storyboard_plan", "storyboard_prompt"}
    assert original["capabilities"]["image_upscale_execution"] is False
    assert expanded["capabilities"]["image_upscale_execution"] is True
    assert expanded["capabilities"]["image_control_execution"] is False
    assert e.calls == []
    # Optional private fixture capture from the mounted server, not a fabricated
    # client contract. Normal test/CI execution has no artifact side effect.
    import os, json
    from pathlib import Path
    capture = os.getenv("PHASE3_CATALOG_CAPTURE")
    if capture:
        path = Path(capture).resolve()
        root = Path(__file__).resolve().parents[1]
        assert path.is_relative_to(root / ".runtime")
        path.write_text(json.dumps(expanded, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@pytest.mark.parametrize("change,status", [("missing", 401), ("forged", 401), ("origin", 403), ("forwarded", 403)])
def test_new_planning_projection_and_catalog_require_original_host(image_graph_client, change, status):
    e = image_graph_client
    headers = {} if change == "missing" else {"X-Session-Token": "forged"} if change == "forged" else (
        {**e.headers, "Origin": "https://untrusted.invalid"} if change == "origin" else {**e.headers, "Forwarded": "for=127.0.0.1"})
    for suffix in ("/catalog?include_production=true", "/planning-documents"):
        response = e.client.get(e.graph_base + suffix, headers=headers)
        assert response.status_code == status, response.text
    assert e.calls == []


def test_picker_returns_only_current_bounded_original_documents(image_graph_client):
    from app.creative.service import document_digest
    e = image_graph_client
    row = e.studio.creative.create(e.nid, e.scope, e.session.actor_id, {
        "mode": "DIRECTOR", "title": "SYNTHETIC standalone visual target", "source_independent": True,
        "visual_target": {"style": "ink"}})
    body = checked(e.client.get(e.graph_base + "/planning-documents", headers=e.headers))
    assert body == {"project_id": e.nid, "scope": e.scope, "documents": [{
        "id": row["id"], "title": row["title"], "mode": "DIRECTOR", "version": row["version"], "digest": document_digest(row)}]}
    assert "visual_target" not in body["documents"][0] and not e.calls
