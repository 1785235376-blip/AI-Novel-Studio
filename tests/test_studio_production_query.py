"""Production job queries over the original mounted File/API owner chain.

No task-center changes, media reads, provider calls, or execution occur here.
"""
from uuid import uuid4

import pytest

from test_cloud_canvas_node_resume import resume_source
from test_cloud_formal_canvas_node import formal_node, create_target, command, queue
from test_studio_asset_query import rig, shared_scope
from test_studio_asset_query_authority import source_snapshot


pytestmark = pytest.mark.file_backend_only


def get(e, params=None, *, headers=None, nid=None, prefix="/api"):
    return e.client.get(f"{prefix}/projects/{nid or e.nid}/studio/production/jobs",
                        params=params, headers=e.headers if headers is None else headers)


def items(response):
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()["items"]


@pytest.fixture
def queued(resume_source):
    e = resume_source
    target = create_target(e)
    e.queued = [queue(e, command(e, target, request_id=f"query-job-{i}"))[0] for i in range(5)]
    # Deterministic same-time tie ordering, using the original queue writer.
    owner = e.production._image(e.actor)
    def stamp(rows):
        for row in rows:
            row["created_at"] = "2026-10-25T00:00:00+00:00"
        return rows[0]
    owner._mutate(e.nid, None, stamp)
    return e


def test_legacy_envelope_and_exact_owner_operation_filters(queued):
    e = queued
    old = get(e).json()
    assert set(old) == {"items", "product_acceptance"}
    assert len(old["items"]) == 5
    assert get(e, {"owner": "image", "operation_id": "m5.image.t2i"}).json() == old
    for query in ({"owner": "audio"}, {"operation_id": "m5.image.i2i"},
                  {"owner": "image", "operation_id": "m8.audio.speech"}):
        assert get(e, query).json() == {"items": [], "product_acceptance": "LOCAL_REQUIRED"}


def test_exact_total_and_descending_ties_across_pages(queued):
    e = queued
    expected = sorted((row["id"] for row in e.queued), reverse=True)
    before = source_snapshot(e.rig.root)
    observed = []
    for offset in (0, 2, 4):
        response = get(e, {"owner": "image", "limit": 2, "offset": offset})
        page = items(response)
        body = response.json()
        assert set(body) == {"items", "total", "limit", "offset", "has_more", "product_acceptance"}
        assert (body["total"], body["limit"], body["offset"]) == (5, 2, offset)
        assert body["has_more"] is (offset < 4)
        observed.extend(row["id"] for row in page)
    assert observed == expected
    for offset in (5, 6, 1_000_000):
        body = get(e, {"limit": 100, "offset": offset}).json()
        assert body == {"items": [], "total": 5, "limit": 100, "offset": offset,
                        "has_more": False, "product_acceptance": "LOCAL_REQUIRED"}
    only_offset = get(e, {"offset": 0}).json()
    assert (only_offset["limit"], only_offset["offset"], only_offset["total"]) == (50, 0, 5)
    assert get(e, {"limit": 1}).json()["offset"] == 0
    assert get(e, {"owner": "audio", "limit": 3}).json() == {
        "items": [], "total": 0, "limit": 3, "offset": 0, "has_more": False,
        "product_acceptance": "LOCAL_REQUIRED"}
    assert source_snapshot(e.rig.root) == before


@pytest.mark.parametrize("params", [
    {"owner": "unknown"}, {"owner": "IMAGE"}, {"owner": ""}, {"owner": " image "},
    {"operation_id": "unknown"}, {"operation_id": ""}, {"operation_id": "m8.audio.speech\n"},
    {"limit": 0}, {"limit": -1}, {"limit": 101}, {"limit": "1.5"}, {"limit": ""},
    {"offset": -1}, {"offset": 1_000_001}, {"offset": "1.5"}, {"offset": ""},
])
def test_invalid_query_has_fixed_error_after_authority(resume_source, params):
    e = resume_source
    before = source_snapshot(e.rig.root)
    response = get(e, params)
    assert response.status_code == 422, response.text
    assert response.json()["detail"] == {
        "code": "EXPERIMENTAL_INVALID", "message": "STUDIO_PRODUCTION_QUERY_INVALID"}
    assert response.headers["cache-control"] == "no-store"
    assert "input" not in response.text and str(e.rig.root) not in response.text
    assert source_snapshot(e.rig.root) == before


def test_existing_internal_list_is_not_implicitly_paginated(queued):
    e = queued
    expected = get(e).json()
    assert e.production.list(e.nid, e.scope, e.actor, lambda: None) == expected


def media_context(e, operation, request_id, *, nid=None, scope=None, actor=None):
    nid, scope, actor = nid or e.nid, scope or e.scope, actor or e.actor
    return {**e.production._base(nid, scope, actor, lambda: None),
            "operation_id": operation, "request_id": request_id, "request_digest": "c" * 64,
            "sources": [], "rights": {}, "provider_binding": None}


def seed_video(e, request_id, *, kind="STUDIO_VIDEO", context=None, nid=None, scope=None, actor=None):
    """Persist synthetic QUEUED metadata through the original receipt owner.

    No timeline admission/execution is claimed by this read-only query fixture.
    The original writer and reader still enforce scope, identity and receipt hash.
    """
    nid, scope, actor = nid or e.nid, scope or e.scope, actor or e.actor
    operation = "m9.timeline.multitrack" if kind == "STUDIO_TIMELINE" else "m7.video.t2v"
    context = context or media_context(e, operation, request_id, nid=nid, scope=scope, actor=actor)
    return e.production.video_owner._studio_write(nid, scope.get("branch_id"), actor,
        {"id": "query-" + uuid4().hex, "kind": kind, "context": context,
         "status": "QUEUED", "created_at": "2026-10-24T00:00:00+00:00"}, context=context)


def seed_audio(e, request_id, operation="m8.audio.speech"):
    context = media_context(e, operation, request_id)
    context["provider_binding"] = {"provider_id": "synthetic-audio", "model_id": "no-model",
        "endpoint": "http://127.0.0.1:9", "local": True,
        "capability": "TTS" if operation == "m8.audio.speech" else "MUSIC", "route_digest": "a" * 64}
    return e.production._audio(e.scope, e.actor).queue(e.nid,
        {"operation_id": operation, "provider_id": "synthetic-audio", "model_id": "no-model",
         "prompt": "Synthetic metadata only", "parameters": {}, "source_snapshots": []},
        context, lambda: None, lambda _source: pytest.fail("No sources may be read"))


def test_all_original_owners_and_operation_intersection(queued):
    e = queued
    audio = seed_audio(e, "audio-query")
    music = seed_audio(e, "music-query", "m8.audio.music")
    video = seed_video(e, "video-query")
    timeline = seed_video(e, "timeline-query", kind="STUDIO_TIMELINE")
    expected = {"image": {row["id"] for row in e.queued}, "audio": {audio["id"], music["id"]},
                "video": {video["id"]}, "timeline": {timeline["id"]}}
    full = items(get(e))
    assert len(full) == 9
    assert full == sorted(full, key=lambda row: (row["created_at"] or "", row["id"]), reverse=True)
    before = source_snapshot(e.rig.root)
    for owner, wanted in expected.items():
        response = get(e, {"owner": owner, "limit": 100})
        assert {row["id"] for row in items(response)} == wanted
        assert response.json()["total"] == len(wanted)
    response = get(e, {"owner": "audio", "operation_id": "m8.audio.speech", "offset": 0})
    assert [row["id"] for row in items(response)] == [audio["id"]]
    assert response.json()["total"] == 1
    response = get(e, {"operation_id": "m9.timeline.multitrack", "limit": 1})
    assert [row["id"] for row in items(response)] == [timeline["id"]]
    assert source_snapshot(e.rig.root) == before


def test_same_id_project_recreation_excludes_old_queue_and_total(queued):
    e = queued
    old_ids = {row["id"] for row in e.queued}
    e.rig.novels.delete(e.nid)
    e.rig.project(e.nid)
    e.workspace.activate(e.nid, e.scope, e.actor)
    response = get(e, {"limit": 1})
    assert items(response) == [] and response.json()["total"] == 0
    assert not any(jid in response.text for jid in old_ids)


def test_actor_project_scope_and_incarnation_precede_total(resume_source):
    from app.creative.production_execution_models import StudioProductionQuery
    e = resume_source
    visible = seed_video(e, "visible")
    seed_video(e, "foreign-actor", actor="other-actor")
    other = e.rig.project()
    other_scope = {"mode": "local", "novel_id": other}
    e.workspace.activate(other, other_scope, e.actor)
    seed_video(e, "foreign-project", nid=other, scope=other_scope)
    stale = media_context(e, "m7.video.t2v", "old-incarnation")
    stale["incarnation"] = "file:" + str(uuid4())
    seed_video(e, "old-incarnation", context=stale)
    response = get(e, {"limit": 1})
    assert [row["id"] for row in items(response)] == [visible["id"]]
    assert response.json()["total"] == 1
    scope, _headers = shared_scope(e.rig)
    second = {**scope, "branch_id": "query-branch-b"}
    for current in (scope, second):
        e.workspace.activate(e.nid, current, "reader")
    a = seed_video(e, "branch-a", scope=scope, actor="reader")
    b = seed_video(e, "branch-b", scope=second, actor="reader")
    # Real File isolation; HTTP authentication is tested separately below.
    for current, row in ((scope, a), (second, b)):
        result = e.production.list(e.nid, current, "reader", lambda: None,
                                   query=StudioProductionQuery(limit=1))
        assert result["total"] == 1 and [job["id"] for job in result["items"]] == [row["id"]]


@pytest.mark.parametrize("case,expected", [
    ("missing_session", 401), ("invalid_session", 401), ("revoked_session", 401),
    ("forwarded_host", 403), ("host_origin", 403), ("feature_disabled", 404),
    ("missing_project", 404), ("missing_branch", 400), ("no_read", 403),
    ("revoked_member", 403), ("collaboration_without_host", 403),
])
def test_original_refusal_precedes_invalid_query(resume_source, monkeypatch, case, expected):
    from app.identity import IdentityStatus
    e = resume_source
    headers, nid = dict(e.headers), e.nid
    if case == "missing_session": headers = {}
    elif case == "invalid_session": headers["X-Session-Token"] = "not-a-session"
    elif case == "revoked_session": e.rig.sessions.revoke(headers["X-Session-Token"])
    elif case == "forwarded_host": headers["X-Forwarded-For"] = "127.0.0.1"
    elif case == "host_origin": headers["Origin"] = "https://not-the-host.invalid"
    elif case == "feature_disabled": monkeypatch.setenv("EXPERIMENTAL_FEATURES", "")
    elif case == "missing_project": nid = "missing-project"
    else:
        _scope, headers = shared_scope(e.rig)
        if case == "missing_branch": headers.pop("X-Branch-Id")
        elif case == "no_read": headers["X-Session-Token"] = "token-no-grants"
        elif case == "revoked_member":
            e.rig.identities.set_membership_status("reader", "query-workspace", IdentityStatus.INACTIVE)
    before = source_snapshot(e.rig.root)
    for query in ({}, {"owner": "private-invalid"}, {"operation_id": "private-invalid"}, {"limit": "0"}):
        response = get(e, query, headers=headers, nid=nid)
        assert response.status_code == expected, response.text
        assert response.headers["cache-control"] == "no-store"
        assert "items" not in response.json() and "total" not in response.json()
        assert "private-invalid" not in response.text and str(e.rig.root) not in response.text
    assert source_snapshot(e.rig.root) == before


def test_neutral_activation_refusal_precedes_bad_query(resume_source):
    e = resume_source
    nid = e.rig.project()
    # Warm the pre-existing project marker, then compare refusal before/after.
    response = get(e, nid=nid)
    assert response.status_code == 422
    assert response.json()["message"] == "STUDIO_NEUTRAL_PROJECT_ACTIVATION_REQUIRED"
    before = source_snapshot(e.rig.root)
    invalid = get(e, {"limit": 0}, nid=nid)
    assert invalid.status_code == response.status_code
    assert invalid.json()["detail"] == response.json()["detail"]
    assert source_snapshot(e.rig.root) == before


def test_wire_scalar_convention_and_versioned_alias(queued):
    e = queued
    response = get(e, [("owner", "unknown"), ("owner", "image"),
        ("operation_id", "unknown"), ("operation_id", "m5.image.t2i"),
        ("limit", "0"), ("limit", "1.0"), ("offset", "0.0")])
    assert len(items(response)) == 1
    assert response.json()["limit"] == 1 and response.json()["offset"] == 0
    assert get(e, {"limit": 1}, prefix="/api/v1").json() == response.json()


def test_corrupt_tail_is_not_hidden_by_filter_or_pagination(queued):
    e = queued
    owner = e.production._image(e.actor)
    def corrupt(rows):
        rows[-1]["binding_digest"] = "0" * 64
        return rows[-1]
    owner._mutate(e.nid, None, corrupt)
    before = source_snapshot(e.rig.root)
    for query in ({}, {"owner": "audio", "limit": 1}, {"limit": 1, "offset": 1_000_000}):
        response = get(e, query)
        assert response.status_code == 422
        assert response.json()["message"] == "STUDIO_IMAGE_JOB_BINDING_CHANGED"
        assert "items" not in response.json() and "total" not in response.json()
    assert source_snapshot(e.rig.root) == before


def test_video_owner_capacity_refusal_is_not_partial_total(resume_source):
    e = resume_source
    context = media_context(e, "m7.video.t2v", "over-capacity")
    directory = e.production.video_owner._studio_dir(e.nid, None, e.actor, context)
    directory.mkdir(parents=True)
    for index in range(101):
        (directory / f"receipt-{index}.json").write_text("{}", encoding="utf-8")
    before = source_snapshot(e.rig.root)
    for query in ({}, {"owner": "image", "limit": 1}, {"offset": 1_000_000}):
        response = get(e, query)
        assert response.status_code == 422
        assert response.json()["message"] == "STUDIO_TIMELINE_JOB_LIMIT"
        assert "items" not in response.json() and "total" not in response.json()
    assert source_snapshot(e.rig.root) == before


def test_private_graph_benchmark_batch_admission_precedes_total(resume_source):
    from app.creative.graph_media_binding import make_graph_binding_digest
    from app.creative.production_execution_models import StudioProductionQuery
    e = resume_source
    visible = seed_video(e, "standalone")
    graph = media_context(e, "m7.video.t2v", "graph-private")
    binding = {"contract": "creative-graph-media-binding/1", "run_id": "run-private",
        "node_id": "node-private", "graph_id": "graph-private", "graph_version": 1,
        "graph_digest": "a" * 64, "run_request_digest": "b" * 64,
        "input_digest": "c" * 64, "preview_run_version": 1,
        "command_digest": "d" * 64, "attempt_digest": "e" * 64}
    binding["attempt_digest"] = make_graph_binding_digest(binding, graph)
    graph["graph_binding"] = binding
    graph_row = seed_video(e, "graph-private", context=graph)
    benchmark = media_context(e, "m7.video.t2v", "benchmark-private")
    benchmark["benchmark_binding"] = {"contract": "studio-video-benchmark/1", "run_id": "f" * 64,
        "index": 0, **{key: benchmark[key] for key in ("actor", "scope_key", "incarnation")},
        "set_hash": "a" * 64, "route_fingerprint": "b" * 64}
    benchmark_row = seed_video(e, "benchmark-private", context=benchmark)
    batch = media_context(e, "m5.image.cutout", "batch-private")
    batch["batch_binding"] = {"contract": "studio-image-safe-batch/1", "batch_id": "batch-private",
        "item_index": 0, **{key: batch[key] for key in ("actor", "scope_key", "incarnation", "request_id")},
        "snapshot_digest": "a" * 64}
    batch_row = seed_video(e, "batch-private", context=batch)
    before = source_snapshot(e.rig.root)
    response = get(e, {"owner": "video", "limit": 1})
    assert [row["id"] for row in items(response)] == [visible["id"]]
    assert response.json()["total"] == 1
    assert all(row["id"] not in response.text for row in (graph_row, benchmark_row, batch_row))
    for name, value, row in (("graph_binding", binding, graph_row),
                              ("benchmark_binding", benchmark["benchmark_binding"], benchmark_row)):
        result = e.production.list(e.nid, e.scope, e.actor, lambda: None,
            **{name: value}, query=StudioProductionQuery(limit=1))
        assert result["total"] == 1 and [job["id"] for job in result["items"]] == [row["id"]]
    # Matching a private batch binding still requires the original batch owner;
    # pagination cannot downgrade this to a successful empty list.
    with pytest.raises(ValueError, match="BATCH_STUDIO_IMAGE_OWNER_REQUIRED"):
        e.production.list(e.nid, e.scope, e.actor, lambda: None,
            batch_binding=batch["batch_binding"], query=StudioProductionQuery(limit=1))
    assert source_snapshot(e.rig.root) == before


def test_internal_list_keeps_more_than_default_page_size(resume_source):
    e = resume_source
    for index in range(51):
        seed_video(e, f"complete-history-{index}")
    result = e.production.list(e.nid, e.scope, e.actor, lambda: None)
    assert set(result) == {"items", "product_acceptance"} and len(result["items"]) == 51
    paged = get(e, {"offset": 0}).json()
    assert paged["total"] == 51 and len(paged["items"]) == 50 and paged["has_more"] is True


def test_host_revocation_during_owner_read_returns_no_page(queued, monkeypatch):
    e = queued
    original = e.production.video_owner.list_studio
    def revoke_after_read(*args, **kwargs):
        result = original(*args, **kwargs)
        e.rig.sessions.revoke(e.headers["X-Session-Token"])
        return result
    monkeypatch.setattr(e.production.video_owner, "list_studio", revoke_after_read)
    before = source_snapshot(e.rig.root)
    response = get(e, {"owner": "image", "limit": 1})
    assert response.status_code == 401, response.text
    assert "items" not in response.json() and "total" not in response.json()
    assert not any(row["id"] in response.text for row in e.queued)
    assert source_snapshot(e.rig.root) == before


def test_query_openapi_matches_exact_public_fields():
    from app.creative.production_execution_models import StudioProductionQuery
    parameters = {item["name"]: item for item in StudioProductionQuery.openapi_parameters()}
    assert set(parameters) == {"owner", "operation_id", "limit", "offset"}
    assert parameters["owner"]["schema"]["anyOf"][0]["enum"] == ["image", "audio", "video", "timeline"]
    assert "m9.timeline.multitrack" in parameters["operation_id"]["schema"]["anyOf"][0]["enum"]
    assert all(item["in"] == "query" and item["required"] is False for item in parameters.values())
