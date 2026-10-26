"""Independently authored adversarial real File/main.app direct-pin queries.

Reuse setup only. Expected identities are constructed from source writes, never
from the paging implementation. One-shot checkpoints deterministically mutate
the original owner or revoke its real Host session, without timing sleeps.
"""
from copy import deepcopy

import pytest

from studio_asset_usage_fixture import usage_rig, audio_history, rig, graph_create, create_timeline, snapshot

pytestmark = pytest.mark.file_backend_only


def query(e, params=None, *, owner="graph", prefix="/api", headers=None, aid=None):
    url = e.usage_base.replace("/api/", prefix + "/", 1)
    if aid:
        url = url.replace(e.asset["id"], aid)
    return e.client.get(url + f"/studio-{owner}-usages", params=params,
                        headers=e.headers if headers is None else headers)


def page(response):
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["other_dependencies"] == "UNKNOWN"
    assert body["read_only"] and not body["automatic_regeneration"]
    assert not body["truncated"]
    return body


def refused(response, e):
    assert response.status_code == 409, response.text
    assert response.headers["cache-control"] == "no-store"
    assert "items" not in response.json() and "total" not in response.json()
    assert e.asset["id"] not in response.text and str(e.rig.root) not in response.text


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_independent_four_hundred_positions_are_neither_lost_nor_duplicated(usage_rig, prefix):
    e = usage_rig
    expected = set()
    for index in range(25):
        row = graph_create(e, 16, f"independent-{index}")
        expected.update((row["id"], f"ref-{node:04d}") for node in range(16))
    before = snapshot(e.rig.root)
    found, cursor, seen = [], None, set()
    for _ in range(100):
        params = {"limit": 17}
        if cursor:
            params["cursor"] = cursor
        body = page(query(e, params, prefix=prefix))
        found.extend((item["id"], item["node_id"]) for item in body["items"])
        assert len(body["items"]) <= 17
        if not body["has_more"]:
            assert body["total"] == 400
            break
        cursor = body["next_cursor"]
        assert cursor and cursor not in seen
        seen.add(cursor)
    else:
        pytest.fail("pagination did not terminate")
    assert len(found) == len(set(found)) == 400 and set(found) == expected
    assert snapshot(e.rig.root) == before


def test_independent_timeline_multitrack_positions_survive_page_boundaries(usage_rig):
    e = usage_rig
    expected = set()
    for index in range(8):
        body = {"expected_version": 0, "title": f"Independent timeline {index}",
            "timeline": {"schema_version": 3, "media_kind": "AUDIO", "duration_ms": 100,
                "tracks": [{"id": f"track-{track}", "kind": "AUDIO", "order": track,
                    "clips": [{"id": f"clip-{track}-{clip}", "source_snapshot": e.source,
                        "start_ms": 0, "in_ms": 0, "out_ms": 100} for clip in range(15)]}
                    for track in range(2)]}}
        response = e.client.post(e.base + "/production/timelines", headers=e.headers, json=body)
        assert response.status_code == 201, response.text
        tid = response.json()["id"]
        expected.update((tid, f"track-{track}", f"clip-{track}-{clip}")
                        for track in range(2) for clip in range(15))
    before = snapshot(e.rig.root)
    found, cursor = [], None
    for _ in range(100):
        params = {"limit": 13}
        if cursor:
            params["cursor"] = cursor
        body = page(query(e, params, owner="timeline"))
        found.extend((item["id"], item["track_id"], item["clip_id"]) for item in body["items"])
        if not body["has_more"]:
            assert body["total"] == 240
            break
        cursor = body["next_cursor"]
    else:
        pytest.fail("timeline pagination did not terminate")
    assert len(found) == len(set(found)) == 240 and set(found) == expected
    assert snapshot(e.rig.root) == before


@pytest.mark.parametrize("mutation", ["add", "move", "consumer_title", "asset_version", "recreate"])
def test_independent_continuation_rejects_changed_source_or_selected_consumer(usage_rig, mutation):
    e = usage_rig
    graph = graph_create(e, 3)
    first = page(query(e, {"limit": 1}))
    if mutation == "add":
        graph_create(e, 1, "added-after-page")
    elif mutation in {"move", "consumer_title"}:
        definition = deepcopy(graph["definition"])
        if mutation == "move":
            definition["nodes"][1]["position"] = {"x": 100.0, "y": 200.0}
        else:
            definition["title"] = "Changed selected consumer title"
        response = e.client.put(e.graph_url + "/" + graph["id"], headers=e.headers,
            json={"expected_version": graph["version"], "definition": definition})
        assert response.status_code == 200, response.text
    elif mutation == "asset_version":
        with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
            e.rig.assets.update_metadata(e.asset["id"], {"parameters": {"edit": True}}, expected_version=1)
    else:
        e.rig.novels.delete(e.rig.nid)
        e.rig.project(e.rig.nid)
        # Recreate through the original explicit activation owner.
        assert e.client.post(e.base + "/activate", headers=e.headers).status_code == 200
    before = snapshot(e.rig.root)
    refused(query(e, {"limit": 1, "cursor": first["next_cursor"]}), e)
    assert snapshot(e.rig.root) == before


def test_independent_unselected_timeline_changes_do_not_invalidate_graph_page(usage_rig):
    e = usage_rig
    graph_create(e, 3)
    first = page(query(e, {"limit": 1}))
    create_timeline(e)
    second = page(query(e, {"limit": 1, "cursor": first["next_cursor"]}))
    assert second["items"][0]["node_id"] != first["items"][0]["node_id"]


def test_independent_other_actor_graph_is_not_a_cursor_or_count_oracle(usage_rig):
    e = usage_rig
    graph_create(e, 3)
    first = page(query(e, {"limit": 1}))
    # Fixture data use the original owner create path; no permission method is
    # mocked. This row is deliberately owned by a different actor.
    private = e.graph.create(e.rig.nid, e.rig.scope, "another-actor", {
        "request_id": "private-create", "definition": {"title": "PRIVATE-TITLE-NOT-EXPOSED", "nodes": []}})
    second_response = query(e, {"limit": 1, "cursor": first["next_cursor"]})
    second = page(second_response)
    assert private["id"] not in second_response.text and "PRIVATE-TITLE" not in second_response.text
    last = page(query(e, {"limit": 1, "cursor": second["next_cursor"]}))
    assert last["total"] == 3


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_independent_no_host_denial_precedes_bad_query_or_missing_asset(usage_rig, prefix):
    e = usage_rig
    for aid in (e.asset["id"], "missing-asset"):
        response = query(e, {"limit": 0, "cursor": "x" * 10000}, headers={}, aid=aid, prefix=prefix)
        assert response.status_code == 401, response.text
        assert "items" not in response.json() and e.asset["id"] not in response.text


@pytest.mark.parametrize("params", [
    [("limit", "1"), ("limit", "2")], [("limit", "1"), ("state", "CURRENT"), ("state", "STALE")],
    {"limit": "0"}, {"limit": "201"}, {"limit": "1", "unknown": "x"},
    {"limit": "1", "cursor": "x" * 10000}, {"cursor": "x" * 43}, {"state": "CURRENT"},
])
def test_independent_ambiguous_or_unbounded_parameters_fail_without_source_writes(usage_rig, params):
    e = usage_rig
    graph_create(e, 2)
    before = snapshot(e.rig.root)
    refused(query(e, params), e)
    assert snapshot(e.rig.root) == before


@pytest.mark.parametrize("change", ["state", "owner", "asset", "token"])
def test_independent_cursor_is_bound_to_its_selection(usage_rig, change):
    e = usage_rig
    graph_create(e, 3)
    first = page(query(e, {"limit": 1}))
    params = {"limit": 1, "cursor": first["next_cursor"]}
    kwargs = {}
    if change == "state":
        params["state"] = "STALE"
    elif change == "owner":
        kwargs["owner"] = "timeline"
    elif change == "asset":
        kwargs["aid"] = e.rig.seed("different.wav", "audio")["id"]
    else:
        token = params["cursor"]
        params["cursor"] = ("A" if token[0] != "A" else "B") + token[1:]
    refused(query(e, params, **kwargs), e)


@pytest.mark.parametrize("stage", ["before_source", "after_source", "after_consumer", "before_issue", "before_return"])
def test_independent_real_host_revocation_at_each_checkpoint_denies(usage_rig, monkeypatch, stage):
    from app.creative import asset_usage_paging
    e = usage_rig
    graph_create(e, 3)
    reached = []
    def checkpoint(value):
        if value == stage and not reached:
            reached.append(value)
            e.rig.sessions.revoke(e.headers["X-Session-Token"])
    monkeypatch.setattr(asset_usage_paging, "_checkpoint", checkpoint)
    response = query(e, {"limit": 1})
    assert reached == [stage]
    assert response.status_code in {401, 403}, response.text
    assert "items" not in response.json() and e.asset["id"] not in response.text


@pytest.mark.parametrize("stage", ["after_source", "after_consumer", "before_issue", "before_return"])
def test_independent_source_change_during_observation_never_returns_mixed_page(usage_rig, monkeypatch, stage):
    from app.creative import asset_usage_paging
    e = usage_rig
    graph_create(e, 3)
    reached = []
    def checkpoint(value):
        if value == stage and not reached:
            reached.append(value)
            with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
                e.rig.assets.update_metadata(e.asset["id"], {"parameters": {"race": stage}}, expected_version=1)
    monkeypatch.setattr(asset_usage_paging, "_checkpoint", checkpoint)
    refused(query(e, {"limit": 1}), e)
    assert reached == [stage]
