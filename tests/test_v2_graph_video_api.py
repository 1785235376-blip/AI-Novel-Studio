"""Mounted original Host/API boundary; no model runtime invocation."""
import json
import os
from pathlib import Path

import pytest
from test_r3_mounted_contracts import checked, mounted, prefix
from test_v2_independent_workspace_api import client
from test_v2_discovered_image_production_api import image_client
from test_v2_graph_image_api import image_graph_client


def test_video_catalog_is_explicit_and_original_image_catalog_stays_unchanged(image_graph_client):
    e = image_graph_client
    old = checked(e.client.get(e.graph_base + "/catalog?include_image=true&include_production=true", headers=e.headers))
    result = checked(e.client.get(e.graph_base + "/catalog?include_video=true", headers=e.headers))
    assert result["capabilities"]["video_graph_schema_version"] == 5
    assert result["capabilities"]["storyboard_video_approval_required"] is True
    assert not result["capabilities"]["automatic_video_dispatch"] and not e.calls
    assert not {"video_generate", "storyboard_shot"} & {item["id"] for item in old["definitions"]}
    capture = os.getenv("PHASE4_CATALOG_CAPTURE")
    if capture:
        path = Path(capture).resolve()
        assert path.is_relative_to(Path(__file__).resolve().parents[1] / ".runtime")
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@pytest.mark.parametrize("change,status", [("missing", 401), ("forged", 401), ("origin", 403), ("forwarded", 403)])
def test_video_catalog_retains_trusted_host_protection(image_graph_client, change, status):
    e = image_graph_client
    headers = {} if change == "missing" else {"X-Session-Token": "forged"} if change == "forged" else (
        {**e.headers, "Origin": "https://untrusted.invalid"} if change == "origin" else {**e.headers, "Forwarded": "for=127.0.0.1"})
    response = e.client.get(e.graph_base + "/catalog?include_video=true", headers=headers)
    assert response.status_code == status and not e.calls
