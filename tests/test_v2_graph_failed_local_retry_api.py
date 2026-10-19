"""Mounted route admission and original collaboration guards, using File storage."""
from uuid import uuid4

from test_v2_creative_graph_api import graph_client, scoped_graph_client, create, admit, definition
from test_v2_independent_workspace_api import client
from test_r3_mounted_contracts import checked, mounted, prefix


def prepare(e, headers=None):
    value = definition("line\n" * 101)
    value["nodes"][1]["definition_id"] = "draft_prepare"
    value["nodes"][1]["parameters"] = {}
    graph = create(e, headers=headers, value=value)
    source = admit(e, graph, headers=headers)
    path = e.studio_base + "/graph-runs/" + source["id"]
    source = checked(e.client.post(path + "/execute", headers=headers, json={"expected_version": source["version"]}))
    assert source["status"] == "FAILED"
    flight = checked(e.client.post(e.graph_base + "/" + graph["id"] + "/preflight", headers=headers,
        json={"expected_version": graph["version"], "target_node_ids": sorted(source["node_states"])}))
    body = {"expected_version": source["version"], "expected_graph_version": graph["version"],
        "reviewed_preflight_digest": flight["preflight_digest"], "request_id": "retry-" + uuid4().hex}
    return graph, source, path, body


def test_mounted_file_retry_is_private_idempotent_and_has_closed_input(graph_client):
    e = graph_client
    graph, source, path, body = prepare(e)
    response = e.client.post(path + "/retry-local", json=body)
    new = checked(response, 201)
    assert response.headers["cache-control"] == "no-store"
    assert new["retry_of"] == source["id"] and new["attempt"] == 2 and new["status"] == "QUEUED"
    assert checked(e.client.post(path + "/retry-local", json=body), 201) == new
    assert checked(e.client.get(path)) == source
    for field, value in (("target_node_ids", []), ("input", {"text": "edited"}), ("attempt", 99), ("retry_of", "other")):
        assert e.client.post(path + "/retry-local", json={**body, field: value}).status_code == 422
    assert e.client.post(path + "/retry-local", json={**body, "expected_version": source["version"] + 1}).status_code == 409
    assert len(checked(e.client.get(e.graph_base + "/" + graph["id"] + "/runs"))["items"]) == 2


def test_collaboration_route_reuses_actor_scope_and_revoked_write_guard(scoped_graph_client):
    e = scoped_graph_client
    graph, source, path, body = prepare(e, e.headers)
    assert e.client.post(path + "/retry-local", json=body).status_code == 401
    assert e.client.post(path + "/retry-local", headers=e.viewer_headers, json=body).status_code in {403, 404}
    admitted = checked(e.client.post(path + "/retry-local", headers=e.headers, json=body), 201)
    assert admitted["status"] == "QUEUED"
    before = e.graphs.store.read(e.nid, source["scope"])
    e.authorization.revoke_role(e.role, e.lead)
    assert e.client.post(path + "/retry-local", headers=e.headers, json=body).status_code == 403
    assert e.graphs.store.read(e.nid, source["scope"]) == before
