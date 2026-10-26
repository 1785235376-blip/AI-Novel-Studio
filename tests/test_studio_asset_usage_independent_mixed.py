"""Independent mixed-owner, lifecycle, resource and collaboration counterexamples."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from studio_asset_usage_fixture import usage_rig, audio_history, rig, graph_create, create_timeline, snapshot
from test_studio_asset_usage_independent import query, page, refused

pytestmark = pytest.mark.file_backend_only


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_independent_mixed_twenty_six_consumers_and_221_positions(usage_rig, prefix):
    e = usage_rig
    expected = set()
    for index in range(13):
        graph = graph_create(e, 16, f"mixed-{index}")
        expected.update(("CREATIVE_GRAPH", graph["id"], f"ref-{node:04d}") for node in range(16))
        timeline = create_timeline(e)
        expected.add(("STUDIO_TIMELINE", timeline["id"], "dialogue/clip-one"))
    before = snapshot(e.rig.root)
    found, cursor = [], None
    for _ in range(100):
        params = {"limit": 19, "sources": "graph,timeline"}
        if cursor:
            params["cursor"] = cursor
        result = page(query(e, params, owner="asset", prefix=prefix))
        assert result["owner"] == "STUDIO_SAVED_ASSET_REFERENCES"
        for item in result["items"]:
            position = item["node_id"] if item["owner"] == "CREATIVE_GRAPH" else item["track_id"] + "/" + item["clip_id"]
            found.append((item["owner"], item["id"], position))
        if not result["has_more"]:
            assert result["total"] == 221
            break
        cursor = result["next_cursor"]
    else:
        pytest.fail("mixed query failed to terminate")
    assert len(found) == len(set(found)) == 221 and set(found) == expected
    assert snapshot(e.rig.root) == before


def test_independent_mixed_equal_ids_preserve_both_owners(usage_rig, monkeypatch):
    from app.experimental import common
    e = usage_rig
    graph = graph_create(e, 1)
    with monkeypatch.context() as patch:
        patch.setattr(common, "new_id", lambda: graph["id"])
        create_timeline(e)
    first = page(query(e, {"limit": 1}, owner="asset"))
    second = page(query(e, {"limit": 1, "cursor": first["next_cursor"]}, owner="asset"))
    items = first["items"] + second["items"]
    assert {item["owner"] for item in items} == {"CREATIVE_GRAPH", "STUDIO_TIMELINE"}
    assert {item["id"] for item in items} == {graph["id"]}
    assert second["total"] == 2


def test_independent_timeline_selection_ignores_graph_edits_and_binds_sources(usage_rig):
    e = usage_rig
    graph = graph_create(e, 1)
    create_timeline(e)
    create_timeline(e)
    first = page(query(e, {"limit": 1, "sources": "timeline"}, owner="asset"))
    definition = deepcopy(graph["definition"])
    definition["title"] = "Not a selected source"
    response = e.client.put(e.graph_url + "/" + graph["id"], headers=e.headers,
        json={"expected_version": graph["version"], "definition": definition})
    assert response.status_code == 200, response.text
    params = {"limit": 1, "sources": "timeline", "cursor": first["next_cursor"]}
    assert page(query(e, params, owner="asset"))["total"] == 2
    for selected in ("graph", "graph,timeline"):
        refused(query(e, {**params, "sources": selected}, owner="asset"), e)


@pytest.mark.parametrize("stage", ["after_consumer", "before_return"])
def test_independent_mixed_read_rechecks_real_host(usage_rig, monkeypatch, stage):
    from app.creative import asset_usage_paging
    e = usage_rig
    graph_create(e, 1)
    create_timeline(e)
    reached = []
    def hook(value):
        if value == stage and not reached:
            reached.append(value)
            e.rig.sessions.revoke(e.headers["X-Session-Token"])
    monkeypatch.setattr(asset_usage_paging, "_checkpoint", hook)
    response = query(e, {"limit": 2}, owner="asset")
    assert reached == [stage]
    assert response.status_code == 401, response.text
    assert "items" not in response.json() and e.asset["id"] not in response.text


def test_independent_mixed_host_rejection_precedes_invalid_selection(usage_rig):
    e = usage_rig
    for params in ({"limit": 0}, {"limit": 1, "sources": "unknown"}):
        response = query(e, params, owner="asset", headers={})
        assert response.status_code == 401, response.text


def test_independent_unactivated_project_is_not_provisioned_by_read(usage_rig):
    e = usage_rig
    nid = e.rig.project()
    marker = e.rig.root / "novels" / nid / "creative_project_v2.json"
    assert not marker.exists()
    before = snapshot(e.rig.root)
    url = e.usage_base.replace(e.rig.nid, nid)
    for owner in ("graph", "timeline", "asset"):
        response = e.client.get(url + f"/studio-{owner}-usages", headers=e.headers, params={"limit": 1})
        assert response.status_code == 409, response.text
        assert not marker.exists()
    assert snapshot(e.rig.root) == before


@pytest.mark.parametrize("mode", ["expiry", "capacity", "response", "read_bytes", "read_count"])
def test_independent_resource_refusal_is_closed_and_read_only(usage_rig, monkeypatch, mode):
    from app.creative import asset_usage_paging as paging
    from app.creative.asset_usage_budget import UsageReadBudget
    e = usage_rig
    graph_create(e, 3)
    monkeypatch.setattr(paging, "_tokens", {})
    first = page(query(e, {"limit": 1}))
    params = {"limit": 1}
    if mode == "expiry":
        now = paging.time.monotonic()
        monkeypatch.setattr(paging, "time", SimpleNamespace(monotonic=lambda: now + paging.TOKEN_TTL + 1))
        params["cursor"] = first["next_cursor"]
    elif mode == "capacity":
        monkeypatch.setattr(paging, "MAX_TOKENS", 1)
    elif mode == "response":
        monkeypatch.setattr(paging, "MAX_RESPONSE_BYTES", 64)
    elif mode == "read_bytes":
        monkeypatch.setattr(UsageReadBudget, "MAX_READ_BYTES", 1)
    else:
        monkeypatch.setattr(UsageReadBudget, "MAX_READS", 0)
    before = snapshot(e.rig.root)
    refused(query(e, params), e)
    assert snapshot(e.rig.root) == before


def test_independent_scope_over_four_mib_refused_before_payload_read(usage_rig, monkeypatch):
    from pathlib import Path
    e = usage_rig
    graph_create(e, 1)
    path = e.graph.store.path(e.rig.nid, e.rig.scope)
    # Synthetic hostile resource fixture: retain the valid JSON then append
    # whitespace beyond the hard encoded-file limit. This changes no schema.
    path.write_bytes(path.read_bytes() + b" " * (4 * 1024 * 1024))
    original = Path.open
    opened = []
    def checked_open(self, *args, **kwargs):
        if self == path:
            opened.append(True)
        return original(self, *args, **kwargs)
    before = snapshot(e.rig.root)
    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", checked_open)
        refused(query(e, {"limit": 1}), e)
    assert opened == [], "oversized payload was opened before its stat bound"
    assert snapshot(e.rig.root) == before


@pytest.mark.parametrize("change", ["actor", "branch"])
def test_independent_continuation_cannot_cross_real_collaboration_authority(usage_rig, change):
    from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
    from test_studio_asset_query import shared_scope
    e = usage_rig
    scope, headers = shared_scope(e.rig)
    grant_scope = AuthorizationScope(ScopeKind.PROJECT, "query-workspace", e.rig.nid)
    for user, permission in (("reader", "domain.write"), ("no-grants", "domain.read")):
        e.rig.grants.assign_permission(PermissionAssignment("independent-" + user, user, permission,
            ModalityDomain.NOVEL, grant_scope, "synthetic independent fixture"))
    e.headers = headers
    activated = e.client.post(e.base + "/activate", headers=headers)
    assert activated.status_code == 200, activated.text
    asset = e.rig.seed("collaboration.wav", "audio", scope_value=scope)
    e.usage_base = e.usage_base.replace(e.asset["id"], asset["id"])
    e.asset = asset
    graph_create(e, 3)
    first = page(query(e, {"limit": 1}, owner="asset"))
    if change == "actor":
        changed = {**headers, "X-Session-Token": "token-no-grants"}
        # Another authorized actor sees no private consumers, rather than being
        # rejected merely because they are different from the first reader.
        assert page(query(e, {"limit": 1}, owner="asset", headers=changed))["total"] == 0
    else:
        changed = {**headers, "X-Branch-Id": "query-branch-b"}
        response = e.client.post(e.base + "/activate", headers=changed)
        assert response.status_code == 200, response.text
    before = snapshot(e.rig.root)
    refused(query(e, {"limit": 1, "cursor": first["next_cursor"]}, owner="asset", headers=changed), e)
    assert snapshot(e.rig.root) == before


def test_independent_scan_ceiling_yields_progress_for_empty_filtered_pages(usage_rig):
    e = usage_rig
    for index in range(17):
        graph_create(e, 16, f"scan-{index}")
    first = page(query(e, {"limit": 200, "state": "STALE"}))
    assert first["items"] == [] and first["has_more"] is True
    assert first["scanned_references"] == 256 and first["scanned_consumers"] == 16
    assert first["total"] is None
    second = page(query(e, {"limit": 200, "state": "STALE", "cursor": first["next_cursor"]}))
    assert second["items"] == [] and second["has_more"] is False and second["total"] == 0
    assert second["scanned_references"] == 16
