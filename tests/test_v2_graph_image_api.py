"""Mounted schema-4 API uses the original trusted Host and persistence owners."""
from copy import deepcopy
from uuid import uuid4

import pytest

from test_r3_mounted_contracts import checked, mounted, prefix
from test_v2_independent_workspace_api import client
from test_v2_discovered_image_production_api import image_client
from test_v2_graph_image_nodes import definition


@pytest.fixture
def image_graph_client(image_client, monkeypatch):
    e = image_client
    e.graphs = e.experimental.creative_graph_service
    for owner in (e.graphs, e.graphs.asset_inputs):
        monkeypatch.setattr(owner, "store", e.studio.store)
        monkeypatch.setattr(owner, "workspace", e.studio)
    e.graphs.configure_media(e.production)
    e.graph_base = e.studio_base + "/graphs"
    return e


def graph_body(e):
    return {"request_id": "graph-" + uuid4().hex, "definition": definition(operation="m5.image.t2i",
        provider=e.adapter.candidate["provider_id"], model=e.adapter.candidate["id"])}


def test_mounted_image_catalog_is_opt_in_and_passive(image_graph_client):
    e = image_graph_client
    original = checked(e.client.get(e.graph_base + "/catalog", headers=e.headers))
    expanded = checked(e.client.get(e.graph_base + "/catalog?include_image=true", headers=e.headers))
    assert "image_graph" not in original["capabilities"]
    assert {value["id"] for value in expanded["definitions"]} - {value["id"] for value in original["definitions"]} == {
        "image_reference", "image_prompt", "image_generate"}
    assert expanded["capabilities"]["image_graph"] is True
    assert expanded["capabilities"]["image_graph_schema_version"] == 4
    assert expanded["capabilities"]["image_reference_semantics"] == "WEIGHTED_PIXEL_INITIALIZATION"
    assert expanded["capabilities"]["image_upscale_execution"] is False
    assert e.calls == [] and e.discovery.center.lifecycle.start.call_count == 0


@pytest.mark.parametrize("change,status", [("missing", 401), ("forged", 401), ("origin", 403), ("forwarded", 403)])
def test_schema4_and_expanded_catalog_require_original_host(image_graph_client, change, status):
    e = image_graph_client
    headers = {} if change == "missing" else {"X-Session-Token": "forged"} if change == "forged" else (
        {**e.headers, "Origin": "https://untrusted.invalid"} if change == "origin" else
        {**e.headers, "Forwarded": "for=127.0.0.1"})
    for method, path, body in [("GET", e.graph_base + "/catalog?include_image=true", None),
        ("POST", e.graph_base, graph_body(e))]:
        response = e.client.request(method, path, headers=headers, json=body)
        assert response.status_code == status, response.text
        assert "SYNTHETIC authored image prompt" not in response.text
    assert not e.calls


def test_mounted_image_run_uses_original_media_preview_and_explicit_dispatch(image_graph_client):
    e = image_graph_client
    graph = checked(e.client.post(e.graph_base, headers=e.headers, json=graph_body(e)), 201)
    path = e.graph_base + "/" + graph["id"]
    flight = checked(e.client.post(path + "/preflight", headers=e.headers, json={"expected_version": graph["version"]}))
    assert flight["graph_schema_version"] == 4 and flight["executable"]
    row = checked(e.client.post(path + "/runs", headers=e.headers, json={"expected_graph_version": graph["version"],
        "reviewed_preflight_digest": flight["preflight_digest"], "target_node_ids": flight["target_node_ids"],
        "request_id": "run-" + uuid4().hex}), 201)
    run_path = e.studio_base + "/graph-runs/" + row["id"]
    row = checked(e.client.post(run_path + "/execute", headers=e.headers, json={"expected_version": row["version"]}))
    assert row["current_node_id"] == "generate" and not e.calls
    row = checked(e.client.post(run_path + "/media/preview", headers=e.headers,
        json={"expected_version": row["version"], "node_id": "generate"}))
    assert row["media_runtime"]["nodes"][0]["preview"]["command"]["operation_id"] == "m5.image.t2i"
    assert row["media_runtime"]["nodes"][0]["execution"] is None and not e.calls
    assert checked(e.client.get(run_path, headers=e.headers))["version"] == row["version"]
    assert checked(e.client.get(path + "/runs", headers=e.headers))["items"][0]["id"] == row["id"]
    e.sessions.revoke(e.host)
    response = e.client.get(run_path, headers=e.headers)
    assert response.status_code == 401 and "SYNTHETIC authored" not in response.text


def test_schema4_rejects_arbitrary_workflow_video_and_implicit_schema_upgrade(image_graph_client):
    e = image_graph_client
    body = graph_body(e)
    for change in ("schema", "video", "workflow"):
        value = deepcopy(body)
        value["request_id"] = change
        if change == "schema":
            value["definition"]["schema_version"] = 3
        elif change == "video":
            value["definition"]["nodes"][1]["parameters"]["operation_id"] = "m7.video.t2v"
        else:
            value["definition"]["nodes"][1]["parameters"]["parameters"]["arbitrary_workflow"] = {"load": "anything"}
        response = e.client.post(e.graph_base, headers=e.headers, json=value)
        assert response.status_code == 422, response.text
    assert not e.calls
