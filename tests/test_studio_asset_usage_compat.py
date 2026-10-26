"""Additive compatibility checks; no old untracked suites are imported."""
import pytest
from studio_asset_usage_fixture import usage_rig, audio_history, rig, graph_create, create_timeline, snapshot

pytestmark = pytest.mark.file_backend_only


def test_original_graph_and_timeline_usage_routes_are_read_only(usage_rig):
    e = usage_rig
    graph = graph_create(e, 2)
    timeline = create_timeline(e)
    before = snapshot(e.rig.root)
    for suffix, owner, expected in (("studio-graph-usages", "CREATIVE_GRAPH", 2),
                                    ("studio-timeline-usages", "STUDIO_TIMELINE", 1)):
        response = e.client.get(e.usage_base + "/" + suffix, headers=e.headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert set(body) == {"owner", "source", "items", "coverage", "truncated", "limit",
                             "read_only", "automatic_regeneration", "other_dependencies"}
        assert body["owner"] == owner and len(body["items"]) == expected
        assert body["source"] == e.source
        assert body["coverage"] == "EXACT_SAVED_DIRECT_ASSET_REFERENCES"
        assert body["other_dependencies"] == "UNKNOWN"
        assert body["read_only"] and not body["automatic_regeneration"] and not body["truncated"]
        assert all(item["state"] == "CURRENT" for item in body["items"])
    assert snapshot(e.rig.root) == before


def test_original_usage_host_denial_precedes_source_lookup(usage_rig):
    e = usage_rig
    before = snapshot(e.rig.root)
    for suffix in ("studio-graph-usages", "studio-timeline-usages"):
        for base in (e.usage_base, e.usage_base.replace(e.asset["id"], "missing-asset")):
            response = e.client.get(base + "/" + suffix)
            assert response.status_code == 401, response.text
    assert snapshot(e.rig.root) == before



def test_original_single_graph_node_capacity_is_not_expanded(usage_rig):
    e = usage_rig
    before = snapshot(e.rig.root)
    pin = {'asset_id': e.asset['id'], 'version': e.asset['version'],
           'digest': e.asset['sha256'], 'kind': 'audio'}
    body = {'request_id': 'oversized-graph', 'definition': {'title': 'Oversized synthetic graph',
        'nodes': [{'id': f'ref-{i:04d}', 'definition_id': 'asset_reference', 'parameters': pin}
                  for i in range(201)]}}
    response = e.client.post(e.graph_url, headers=e.headers, json=body)
    assert response.status_code == 422, response.text
    assert snapshot(e.rig.root) == before
