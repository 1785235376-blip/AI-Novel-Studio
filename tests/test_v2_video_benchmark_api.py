"""Mounted benchmark API over original File/PG owners and synthetic video wire.

The host-authority fixture exercises router and continuation guards. It does
not pretend to be the application's session resolver or a live model host.
"""
from copy import deepcopy
import os
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.experimental.flags import require_flag
from app.experimental.model_benchmark_api import create_model_benchmark_router
from app.services.v1_capability_service import CapabilityVersionConflict
from test_v2_video_benchmark import (
    PROMPT, execute, preview, prompt_count, refresh, rig, start,
    test_set as create_test_set, video_benchmark,
)


def mounted(e, *, host=True):
    state = SimpleNamespace(active=True, principal="fixture-current-model-host", allowed=True, actor=e.r.actor)
    permissions, checks = [], []
    token = "synthetic-video-host-session"

    def require_session(value):
        if value != token:
            raise HTTPException(401, {"code": "FIXTURE_HOST_SESSION_REQUIRED"})

    def authorize(nid, value, branch, permission):
        permissions.append(permission)
        if not state.allowed or nid != e.r.nid or branch is not None:
            raise HTTPException(403, {"code": "FIXTURE_PROJECT_AUTHORITY_DENIED"})
        return state.actor, deepcopy(e.r.scope)

    def host_guard():
        checks.append("current")
        if not state.active:
            raise HTTPException(403, {"code": "FIXTURE_MODEL_HOST_REVOKED"})
        if state.principal != "fixture-current-model-host":
            raise HTTPException(403, {"code": "FIXTURE_MODEL_HOST_PRINCIPAL_INVALID"})

    def authority(request, value):
        require_session(value)
        return SimpleNamespace(principal=state.principal, guard=host_guard)

    app = FastAPI()
    app.include_router(create_model_benchmark_router(e.bench, authorize, require_flag,
        require_session, model_host_authority=authority if host else None))
    client = TestClient(app)
    return SimpleNamespace(client=client,
        url=f"/novels/{e.r.nid}/experimental/model-benchmarks",
        headers={"X-Session-Token": token}, state=state, permissions=permissions, checks=checks)


def prepared_request(e, stage):
    saved = create_test_set(e)
    if stage == "start":
        return "/runs", {"set_id": saved["id"], "expected_set_version": saved["version"],
            "route_id": e.route["route_id"], "request_id": "api-video-sample"}
    run = start(e, saved)
    if stage == "preview":
        return f"/runs/{run['id']}/preview", {"expected_version": run["version"]}
    run = preview(e, run)
    return f"/runs/{run['id']}/execute", {"expected_version": run["version"],
        "reviewed_preview_digest": run["video_sample"]["preview"]["preview_digest"]}


@pytest.mark.parametrize("stage", ["start", "preview", "execute"])
@pytest.mark.parametrize("denial", ["missing_host", "missing_principal", "invalid_principal", "revoked"])
def test_model_host_principal_and_current_authority_required_before_video_actions(video_benchmark, stage, denial):
    e = video_benchmark
    suffix, body = prepared_request(e, stage)
    m = mounted(e, host=denial != "missing_host")
    if denial == "missing_principal": m.state.principal = None
    elif denial == "invalid_principal": m.state.principal = "unrecognized-host-principal"
    elif denial == "revoked": m.state.active = False
    before = e.r.raw_store.read(e.r.nid, e.r.scope)
    response = m.client.post(m.url + suffix, headers=m.headers, json=body)
    assert response.status_code == 403, response.text
    assert e.r.raw_store.read(e.r.nid, e.r.scope) == before
    assert e.wire.calls == [] and e.broker.ledger(e.r.nid, e.r.scope, e.r.actor) == []
    assert e.discovery.center.lifecycle.start.call_count == 0


@pytest.mark.parametrize("token", [None, "invalid-session"])
def test_video_start_requires_an_authenticated_host_session(video_benchmark, token):
    e = video_benchmark
    suffix, body = prepared_request(e, "start")
    m = mounted(e)
    headers = {} if token is None else {"X-Session-Token": token}
    before = e.r.raw_store.read(e.r.nid, e.r.scope)
    response = m.client.post(m.url + suffix, headers=headers, json=body)
    assert response.status_code == 401, response.text
    assert e.r.raw_store.read(e.r.nid, e.r.scope) == before
    assert e.wire.calls == [] and m.checks == []


def test_explicit_video_api_actions_preserve_one_send_and_private_review(video_benchmark):
    e = video_benchmark
    m = mounted(e)
    created = m.client.post(m.url + "/sets", headers=m.headers, json={
        "title": "Explicit video API fixture", "cases": [
            {"title": "One decoded video", "kind": "VIDEO_WORKFLOW", "prompt": PROMPT}]})
    assert created.status_code == 201, created.text
    saved = created.json()
    response = m.client.post(m.url + "/runs", headers=m.headers, json={
        "set_id": saved["id"], "expected_set_version": saved["version"],
        "route_id": e.route["route_id"], "request_id": "api-one-video"})
    assert response.status_code == 201, response.text
    run = response.json()
    assert run["status"] == "READY" and run["capability"] == "VIDEO"
    assert response.headers["cache-control"] == "no-store"
    assert not {"history", "video_samples", "studio_incarnation"}.intersection(run)
    path = m.url + "/runs/" + run["id"]
    step = m.client.post(path + "/step", headers=m.headers, json={"expected_version": run["version"]})
    assert step.status_code == 422, step.text
    assert e.wire.calls == []
    no_digest = m.client.post(path + "/execute", headers=m.headers, json={"expected_version": run["version"]})
    assert no_digest.status_code == 422, no_digest.text
    response = m.client.post(path + "/preview", headers=m.headers, json={"expected_version": run["version"]})
    assert response.status_code == 200, response.text
    reviewed = response.json()
    assert "binding" not in reviewed["video_sample"]
    digest = reviewed["video_sample"]["preview"]["preview_digest"]
    wrong = m.client.post(path + "/execute", headers=m.headers, json={
        "expected_version": reviewed["version"], "reviewed_preview_digest": "0" * 64})
    assert wrong.status_code == 422, wrong.text
    forged = m.client.post(path + "/execute", headers=m.headers, json={
        "expected_version": reviewed["version"], "reviewed_preview_digest": digest,
        "benchmark_binding": {"run_id": "PRIVATE_FORGED_BINDING_SENTINEL"}})
    assert forged.status_code == 422 and "PRIVATE_FORGED_BINDING_SENTINEL" not in forged.text
    assert e.wire.calls == []
    payload = {"expected_version": reviewed["version"], "reviewed_preview_digest": digest}
    response = m.client.post(path + "/execute", headers=m.headers, json=payload)
    assert response.status_code == 200, response.text
    running = response.json()
    assert running["status"] == "RUNNING" and running["video_sample"]["job"]["status"] == "REMOTE_RUNNING"
    duplicate = m.client.post(path + "/execute", headers=m.headers, json=payload)
    assert duplicate.status_code == 409, duplicate.text
    assert prompt_count(e) == 1
    before = deepcopy(e.wire.calls)
    status = m.client.get(m.url + "/status", headers=m.headers)
    assert status.status_code == 200 and status.headers["cache-control"] == "no-store"
    assert status.json()["startup_runs"] is False
    assert status.json()["video_execution"] == "ONE_REGISTERED_LOCAL_T2V_THROUGH_ORIGINAL_STUDIO_REVIEW"
    assert "binding" not in status.json()["runs"][0]["video_sample"]
    assert "video_samples" not in status.json()["runs"][0]
    assert e.wire.calls == before
    response = m.client.post(path + "/reconcile", headers=m.headers, json={"expected_version": running["version"]})
    assert response.status_code == 200, response.text
    reconciled = response.json()
    assert reconciled["status"] == "RUNNING" and e.wire.calls == before
    response = m.client.post(path + "/refresh", headers=m.headers, json={"expected_version": reconciled["version"]})
    assert response.status_code == 200, response.text
    completed = response.json()
    assert completed["status"] == "COMPLETED" and len(completed["results"]) == 1
    receipt = completed["results"][0]["media_receipt"]
    assert receipt["owner"] == "video" and receipt["status"] == "AWAITING_REVIEW"
    assert completed["results"][0]["latency_ms"] is None
    with pytest.raises(FileNotFoundError):
        e.r.service.asset(e.r.nid, e.r.scope, receipt["output_candidate"]["id"])
    assert prompt_count(e) == 1 and m.checks


def test_authority_revoked_during_original_admission_prevents_video_wire(video_benchmark, monkeypatch):
    e = video_benchmark
    suffix, body = prepared_request(e, "execute")
    m = mounted(e)
    def revoke(_candidate):
        m.state.active = False
    monkeypatch.setattr(e.discovery, "check_model_dispatch", revoke)
    response = m.client.post(m.url + suffix, headers=m.headers, json=body)
    assert response.status_code == 403, response.text
    assert not m.state.active and m.checks
    assert e.wire.calls == [] and prompt_count(e) == 0
    assert e.bench.evidence(e.r.nid, e.r.scope) == []


def test_execution_feature_revocation_blocks_refresh_but_allows_local_cancel(video_benchmark, monkeypatch):
    e = video_benchmark
    running = execute(e, preview(e, start(e)))
    m = mounted(e)
    flags = set(os.environ["EXPERIMENTAL_FEATURES"].split(","))
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", ",".join(sorted(flags - {"ai_execution_v2"})))
    before = deepcopy(e.wire.calls)
    path = m.url + "/runs/" + running["id"]
    denied = m.client.post(path + "/refresh", headers=m.headers,
        json={"expected_version": running["version"]})
    assert denied.status_code == 404, denied.text
    response = m.client.post(path + "/cancel", headers=m.headers,
        json={"expected_version": running["version"]})
    assert response.status_code == 200, response.text
    cancelled = response.json()
    assert cancelled["status"] == "CANCELLED"
    assert cancelled["video_sample"]["job"]["status"] == "CANCELLED"
    assert cancelled["video_sample"]["job"]["remote_compute_may_continue"] is True
    assert cancelled["results"] == [] and e.wire.calls == before
    assert e.broker.budget(e.r.nid, e.r.scope)["inflight"] == 1
    assert prompt_count(e) == 1


def test_video_candidate_download_returns_exact_private_bytes_and_read_only_headers(video_benchmark):
    e = video_benchmark
    m = mounted(e)
    run = start(e)
    path = m.url + f"/runs/{run['id']}/video/0/candidate"
    missing = m.client.get(path, headers=m.headers)
    assert missing.status_code == 404, missing.text
    assert e.wire.calls == []
    running = execute(e, preview(e, run))
    calls = deepcopy(e.wire.calls)
    unfinished = m.client.get(path, headers=m.headers)
    assert unfinished.status_code == 404, unfinished.text
    assert e.wire.calls == calls
    completed = refresh(e, running)
    candidate = completed["results"][0]["media_receipt"]["output_candidate"]
    calls = deepcopy(e.wire.calls)
    ledger = deepcopy(e.broker.ledger(e.r.nid, e.r.scope, e.r.actor))
    response = m.client.get(path, headers=m.headers)
    assert response.status_code == 200, response.text
    assert response.content == e.wire.data
    assert response.headers["content-type"] == "video/webm"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-asset-sha256"] == candidate["digest"]
    assert response.headers["x-asset-version"] == str(candidate["version"])
    assert e.wire.calls == calls and e.broker.ledger(e.r.nid, e.r.scope, e.r.actor) == ledger
    assert set(m.permissions) == {"domain.read"}
    with pytest.raises(FileNotFoundError):
        e.r.service.asset(e.r.nid, e.r.scope, candidate["id"])
    with pytest.raises(FileNotFoundError):
        e.r.assets.content(candidate["id"], actor_id=e.r.actor)


@pytest.mark.parametrize("suffix, expected", [
    ("/video/candidate", 404),
    ("/video/-1/candidate", 404),
    ("/video/1/candidate", 404),
    ("/video/not-an-index/candidate", 422),
])
def test_video_candidate_missing_or_wrong_index_cannot_read_another_sample(video_benchmark, suffix, expected):
    e = video_benchmark
    completed = refresh(e, execute(e, preview(e, start(e))))
    m = mounted(e)
    calls = deepcopy(e.wire.calls)
    response = m.client.get(m.url + f"/runs/{completed['id']}" + suffix, headers=m.headers)
    assert response.status_code == expected, response.text
    assert response.content != e.wire.data and e.wire.calls == calls


@pytest.mark.parametrize("denial, expected", [("revoked_host", 403), ("other_actor", 404), ("recreated_owner", 404)])
def test_video_candidate_current_host_actor_and_incarnation_are_required(video_benchmark, denial, expected):
    e = video_benchmark
    completed = refresh(e, execute(e, preview(e, start(e))))
    m = mounted(e)
    calls = deepcopy(e.wire.calls)
    if denial == "revoked_host":
        m.state.active = False
    elif denial == "other_actor":
        m.state.actor = "different-project-author"
    else:
        old_identity = e.r.store.incarnation(e.r.nid)
        e.r.novels.delete(e.r.nid)
        e.r.create_project("Recreated owner cannot adopt private benchmark output", nid=e.r.nid)
        e.r.service.activate(e.r.nid, e.r.scope, e.r.actor)
        assert e.r.store.incarnation(e.r.nid) != old_identity
    response = m.client.get(m.url + f"/runs/{completed['id']}/video/0/candidate", headers=m.headers)
    assert response.status_code == expected, response.text
    assert response.content != e.wire.data and e.wire.calls == calls
    candidate = completed["results"][0]["media_receipt"]["output_candidate"]
    with pytest.raises(FileNotFoundError):
        e.r.service.asset(e.r.nid, e.r.scope, candidate["id"])


def private_owner_conflict():
    return {"version": 29, "prompt": "PRIVATE_OWNER_PROMPT_SENTINEL",
        "context": {"private_context": "PRIVATE_OWNER_CONTEXT_SENTINEL"},
        "execution_token": "SYNTHETIC_PRIVATE_EXECUTOR_TOKEN_SENTINEL",
        "result_uri": "https://example.invalid/PRIVATE_OWNER_URL_SENTINEL"}


@pytest.mark.parametrize("owner_version", [
    pytest.param(29, id="positive-integer"),
    pytest.param(2**53 - 1, id="maximum-safe-integer"),
    pytest.param(2**53, id="oversized-integer"),
    pytest.param(True, id="boolean"),
    pytest.param({"private": "PRIVATE_VERSION_OBJECT_SENTINEL"}, id="object"),
    pytest.param("PRIVATE_VERSION_STRING_SENTINEL", id="string"),
    pytest.param(0, id="zero"),
    pytest.param(-1, id="negative"),
    pytest.param(None, id="null"),
])
def test_video_preview_lower_owner_conflict_exposes_only_safe_current_version(video_benchmark, monkeypatch, owner_version):
    e = video_benchmark
    run = start(e)
    m = mounted(e)
    before = e.r.raw_store.read(e.r.nid, e.r.scope)
    calls = []

    def conflicting_preview(nid, scope, actor, rid, version, guard):
        assert (nid, scope, actor, rid, version) == (e.r.nid, e.r.scope, e.r.actor, run["id"], run["version"])
        calls.append(rid)
        raise CapabilityVersionConflict({**private_owner_conflict(), "version": owner_version})

    monkeypatch.setattr(e.bench.video, "preview", conflicting_preview)
    response = m.client.post(m.url + f"/runs/{run['id']}/preview", headers=m.headers,
        json={"expected_version": run["version"]})
    assert response.status_code == 409, response.text
    expected_version = owner_version if type(owner_version) is int and 1 <= owner_version <= 2**53 - 1 else None
    assert response.json() == {"detail": {"code": "BENCHMARK_VIDEO_VERSION_CONFLICT", "current_version": expected_version}}
    assert "current" not in response.json()["detail"]
    assert all(sentinel not in response.text for sentinel in (
        "PRIVATE_OWNER_PROMPT_SENTINEL", "PRIVATE_OWNER_CONTEXT_SENTINEL",
        "SYNTHETIC_PRIVATE_EXECUTOR_TOKEN_SENTINEL", "PRIVATE_OWNER_URL_SENTINEL",
        "PRIVATE_VERSION_OBJECT_SENTINEL", "PRIVATE_VERSION_STRING_SENTINEL"))
    assert calls == [run["id"]] and e.wire.calls == []
    assert e.r.raw_store.read(e.r.nid, e.r.scope) == before


@pytest.mark.parametrize("outcome", ["success", "conflict"])
def test_video_candidate_response_rechecks_host_after_lower_helper_success_or_conflict(video_benchmark, monkeypatch, outcome):
    e = video_benchmark
    run = start(e)
    m = mounted(e)
    before = e.r.raw_store.read(e.r.nid, e.r.scope)
    calls = []

    def revoke_at_candidate_boundary(nid, scope, actor, rid, index, guard):
        assert (nid, scope, actor, rid, index) == (e.r.nid, e.r.scope, e.r.actor, run["id"], 0)
        calls.append(outcome)
        m.state.active = False
        if outcome == "conflict":
            raise CapabilityVersionConflict(private_owner_conflict())
        return {"media_type": "video/webm", "sha256": "a" * 64, "version": 1}, e.wire.data

    monkeypatch.setattr(e.bench.video, "candidate", revoke_at_candidate_boundary)
    response = m.client.get(m.url + f"/runs/{run['id']}/video/0/candidate", headers=m.headers)
    assert response.status_code == 403, response.text
    assert response.json() == {"detail": {"code": "FIXTURE_MODEL_HOST_REVOKED"}}
    assert response.content != e.wire.data
    assert "current_version" not in response.text and "PRIVATE_OWNER" not in response.text
    assert "SYNTHETIC_PRIVATE_EXECUTOR_TOKEN_SENTINEL" not in response.text
    assert "x-asset-sha256" not in response.headers and "x-asset-version" not in response.headers
    assert calls == [outcome] and e.wire.calls == []
    assert e.r.raw_store.read(e.r.nid, e.r.scope) == before


@pytest.mark.parametrize("owner_change", ["recreated", "deleted_only"])
def test_video_candidate_recreated_owner_after_real_read_cannot_receive_old_bytes(video_benchmark, monkeypatch, owner_change):
    e = video_benchmark
    completed = refresh(e, execute(e, preview(e, start(e))))
    candidate = completed["results"][0]["media_receipt"]["output_candidate"]
    m = mounted(e)
    original_candidate = e.bench.video.candidate
    captured = []
    original_identity = e.r.store.incarnation(e.r.nid)

    def recreate_after_real_read(nid, scope, actor, rid, index, guard):
        result = original_candidate(nid, scope, actor, rid, index, guard)
        meta, data = result
        assert meta["id"] == candidate["id"] and data == e.wire.data
        captured.append((meta["sha256"], len(data)))
        e.r.novels.delete(e.r.nid)
        if owner_change == "recreated":
            e.r.create_project("Replacement owner during private candidate response", nid=e.r.nid)
            e.r.service.activate(e.r.nid, e.r.scope, e.r.actor)
            assert e.r.store.incarnation(e.r.nid) != original_identity
        elif e.r.backend == "file":
            assert not (e.r.root / "novels" / e.r.nid / "creative_project_v2.json").exists()
        return result

    monkeypatch.setattr(e.bench.video, "candidate", recreate_after_real_read)
    calls = deepcopy(e.wire.calls)
    response = m.client.get(m.url + f"/runs/{completed['id']}/video/0/candidate", headers=m.headers)
    assert response.status_code == 403, response.text
    assert response.json() == {"detail": {"code": "BENCHMARK_VIDEO_OWNER_CHANGED"}}
    assert captured == [(candidate["digest"], len(e.wire.data))]
    assert response.content != e.wire.data and candidate["digest"] not in response.text
    assert "x-asset-sha256" not in response.headers and "x-asset-version" not in response.headers
    assert e.wire.calls == calls and prompt_count(e) == 1
    if owner_change == "recreated":
        with pytest.raises(FileNotFoundError):
            e.r.service.asset(e.r.nid, e.r.scope, candidate["id"])
    else:
        with pytest.raises(FileNotFoundError):
            e.r.novels.get(e.r.nid)
        if e.r.backend == "file":
            assert not (e.r.root / "novels" / e.r.nid / "creative_project_v2.json").exists()


def test_new_project_incarnation_can_read_its_own_fresh_video_candidate(video_benchmark):
    e = video_benchmark
    old = start(e, request_id="same-request-after-recreate")
    old_identity = e.r.store.incarnation(e.r.nid)
    e.r.novels.delete(e.r.nid)
    e.r.create_project("Fresh owner with an explicitly submitted new sample", nid=e.r.nid)
    e.r.service.activate(e.r.nid, e.r.scope, e.r.actor)
    assert e.r.store.incarnation(e.r.nid) != old_identity
    fresh = start(e, request_id="same-request-after-recreate")
    assert fresh["id"] != old["id"]
    completed = refresh(e, execute(e, preview(e, fresh)))
    candidate = completed["results"][0]["media_receipt"]["output_candidate"]
    m = mounted(e)
    calls = deepcopy(e.wire.calls)
    response = m.client.get(m.url + f"/runs/{completed['id']}/video/0/candidate", headers=m.headers)
    assert response.status_code == 200, response.text
    assert response.content == e.wire.data
    assert response.headers["x-asset-sha256"] == candidate["digest"]
    assert response.headers["x-asset-version"] == str(candidate["version"])
    old_response = m.client.get(m.url + f"/runs/{old['id']}/video/0/candidate", headers=m.headers)
    assert old_response.status_code == 404, old_response.text
    assert e.wire.calls == calls and prompt_count(e) == 1


def test_video_status_rereads_runs_after_owner_changes_before_guard_capture(video_benchmark, monkeypatch):
    e = video_benchmark
    old = start(e)
    old_identity = e.r.store.incarnation(e.r.nid)
    m = mounted(e)
    original_runs = e.bench.runs
    projections = []

    def recreate_after_first_projection(nid, scope, actor):
        rows = original_runs(nid, scope, actor)
        projections.append([row["id"] for row in rows])
        if len(projections) == 1:
            assert old["id"] in projections[0]
            e.r.novels.delete(e.r.nid)
            e.r.create_project("Replacement owner before status guard capture", nid=e.r.nid)
            e.r.service.activate(e.r.nid, e.r.scope, e.r.actor)
            assert e.r.store.incarnation(e.r.nid) != old_identity
        return rows

    monkeypatch.setattr(e.bench, "runs", recreate_after_first_projection)
    response = m.client.get(m.url + "/status", headers=m.headers)
    assert response.status_code == 200, response.text
    assert response.json()["runs"] == [] and old["id"] not in response.text
    assert len(projections) >= 2 and old["id"] not in projections[-1]
    assert response.headers["cache-control"] == "no-store"
    assert e.wire.calls == [] and prompt_count(e) == 0
    assert m.checks and set(m.permissions) == {"domain.read"}
