"""Explicit local T2V samples on original owners, with synthetic wire only.

Use scripts/run_v2_checks.py with an owned --basetemp and select the File
backend unless a dedicated real PostgreSQL fixture has been authorized. The
WEBM is generated and decoded by the real CPU tools; no server, model, network
transport, GPU inference, runtime download, or performance claim is involved.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import os
from types import SimpleNamespace

import pytest

from app.creative.production_execution import ProductionExecutionService
from app.creative.production_execution_models import MediaCommand, MediaJobAction
from app.experimental.common import StaleSourceError
from app.experimental.model_benchmark import ModelBenchmarkService
from app.experimental.model_broker import ModelBrokerService
from app.media_files import inspect_media
from app.runtime import Runtime
from app.services.image_job_service import ImageJobService
from app.services.video_assembly_service import VideoAssemblyService
from app.services.v1_capability_service import CapabilityVersionConflict
from app.stable_identity import StableIdentityStore
from test_v2_independent_workspace import reopened, rig
from test_v2_video_runtime_foundation import configured


PROMPT = "SYNTHETIC PRIVATE BENCHMARK VIDEO"


@pytest.fixture
def video_benchmark(rig, tmp_path, monkeypatch):
    r = rig
    discovery, production, adapter, wire, command = configured(r, tmp_path, monkeypatch)
    flags = set(os.environ["EXPERIMENTAL_FEATURES"].split(","))
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", ",".join(sorted(flags | {"model_benchmark_v2"})))
    runtime = Runtime(StableIdentityStore(r.root / "video-benchmark-identities.json"))
    broker = ModelBrokerService(r.store, r.novels, r.chapters, runtime=runtime,
        video_registry=production.video_providers)
    bench = ModelBenchmarkService(r.store, r.novels, r.chapters, broker=broker)
    bench.configure_video(production)
    broker.evidence_reader = bench.evidence
    route = next(row for row in broker.candidates()
        if row["capability"] == "VIDEO" and row["model_id"] == command["model_id"])
    stamp = datetime.now(timezone.utc)
    price = broker.configure_price(r.nid, r.scope, r.actor, {
        "route_id": route["route_id"], "route_fingerprint": route["fingerprint"],
        "reserve_microusd": 0, "source": "Explicit synthetic test estimate, not an invoice or host-compute measurement",
        "as_of": stamp.isoformat(), "expires_at": (stamp + timedelta(days=1)).isoformat(),
        "expected_version": 0})
    return SimpleNamespace(r=r, discovery=discovery, production=production,
        adapter=adapter, wire=wire, command=command, runtime=runtime,
        broker=broker, bench=bench, route=route, price=price)


def test_set(e, **values):
    return e.bench.create_set(e.r.nid, e.r.scope, e.r.actor, {
        "title": "One explicit synthetic video sample", "cases": [
            {"title": "Synthetic blue fixture", "kind": "VIDEO_WORKFLOW", "prompt": PROMPT}],
        **values})


# This helper is not a pytest test even though it creates a test set.
test_set.__test__ = False


def start(e, saved=None, request_id="explicit-video-sample"):
    saved = saved or test_set(e)
    return e.bench.start(e.r.nid, e.r.scope, e.r.actor, {
        "set_id": saved["id"], "expected_set_version": saved["version"],
        "route_id": e.route["route_id"], "request_id": request_id})


def preview(e, run):
    return e.bench.video.preview(e.r.nid, e.r.scope, e.r.actor,
        run["id"], run["version"], lambda: None)


def execute(e, run, reviewed_digest=None):
    receipt = run["video_sample"]["preview"]
    return e.bench.video.execute(e.r.nid, e.r.scope, e.r.actor,
        run["id"], run["version"], reviewed_digest or receipt["preview_digest"], lambda: None)


def refresh(e, run):
    return e.bench.video.refresh(e.r.nid, e.r.scope, e.r.actor,
        run["id"], run["version"], lambda: None)


def current(e, run):
    return e.bench.get(e.r.nid, e.r.scope, e.bench.RUNS, run["id"])


def prompt_count(e):
    return sum(url.endswith("/prompt") for url, _ in e.wire.calls)


def changed_set(e, saved):
    value = {key: deepcopy(saved[key]) for key in (
        "title", "cases", "repetitions", "max_output_tokens", "timeout_seconds", "max_cost_microusd")}
    value["cases"][0]["prompt"] = "A changed synthetic video prompt"
    return e.bench.update_set(e.r.nid, e.r.scope, e.r.actor,
        saved["id"], saved["version"], value)


def reopen_owners(e):
    r = e.r
    workspace = reopened(r)
    production = ProductionExecutionService(workspace, ImageJobService(r.root),
        e.production.image_registry, VideoAssemblyService(r.root, workspace.assets),
        e.production.video_providers, {}, SimpleNamespace(), SimpleNamespace(), SimpleNamespace())
    broker = ModelBrokerService(workspace.store, r.novels, r.chapters,
        runtime=e.runtime, video_registry=production.video_providers)
    bench = ModelBenchmarkService(workspace.store, r.novels, r.chapters, broker=broker)
    bench.configure_video(production)
    broker.evidence_reader = bench.evidence
    return workspace, production, broker, bench


def test_video_start_and_preview_never_send_and_same_request_is_idempotent(video_benchmark):
    e = video_benchmark
    saved = test_set(e)
    metadata_calls = deepcopy(e.discovery.client.calls)
    run = start(e, saved)
    again = start(e, saved)
    assert run == again and run["status"] == "READY" and run["capability"] == "VIDEO"
    assert run["total"] == 1 and run["completed"] == 0 and run["results"] == []
    assert run["automatic_replay"] is False
    reviewed = preview(e, run)
    receipt = reviewed["video_sample"]["preview"]
    production_preview = receipt["production_preview"]
    assert production_preview["command"]["operation_id"] == "m7.video.t2v"
    assert production_preview["command"]["prompt"] == PROMPT
    assert production_preview["command"]["source_snapshots"] == []
    assert production_preview["execution_recipe"]["adapter"] == "COMFYUI_BUILTIN_VIDEO"
    assert len(receipt["preview_digest"]) == 64
    assert e.wire.calls == [] and e.discovery.client.calls == metadata_calls
    assert e.broker.ledger(e.r.nid, e.r.scope, e.r.actor) == []
    assert len(e.bench.runs(e.r.nid, e.r.scope, e.r.actor)) == 1
    assert e.discovery.center.lifecycle.start.call_count == 0


def test_local_video_zero_estimate_never_claims_actual_cost_or_free_compute(video_benchmark):
    e = video_benchmark
    assert e.broker._price(e.route, {}) is None
    decision = e.broker.preview(e.r.nid, e.r.scope, e.r.actor, {
        "capability": "VIDEO", "policy": "CUSTOM", "profile": "LOCAL_ONLY",
        "preferred_route": e.route["route_id"], "max_cost_microusd": 0})
    chosen = decision["chosen"]
    assert chosen["route_id"] == e.route["route_id"] and not chosen["cloud"]
    assert chosen["price"]["reserve_microusd"] == 0
    assert chosen["price"]["source"] == e.price["source"]
    assert chosen["price"].get("actual_known_zero") is not True
    assert chosen["price"].get("zero_kind") is None
    assert chosen["cost_state"] == "ESTIMATE"
    assert decision["execution_authorized"] is False and not e.wire.calls


def test_one_video_sample_decodes_private_original_bytes_and_reopens(video_benchmark):
    e = video_benchmark
    reviewed = preview(e, start(e))
    running = execute(e, reviewed)
    job = running["video_sample"]["job"]
    assert running["status"] == "RUNNING" and running["completed"] == 0
    assert running["results"] == [] and job["owner"] == "video"
    assert job["status"] == "REMOTE_RUNNING" and job["output_candidate"] is None
    assert prompt_count(e) == 1
    assert not any(url.endswith("/view") for url, _ in e.wire.calls)
    assert e.broker.budget(e.r.nid, e.r.scope)["inflight"] == 1
    completed = refresh(e, running)
    assert completed["status"] == "COMPLETED" and completed["completed"] == 1
    assert len(completed["results"]) == 1
    result = completed["results"][0]
    receipt = result["media_receipt"]
    assert receipt["owner"] == "video" and receipt["task_id"] == job["id"]
    assert receipt["status"] == "AWAITING_REVIEW"
    candidate = receipt["output_candidate"]
    assert candidate == completed["video_sample"]["job"]["output_candidate"]
    assert completed["video_sample"]["job"]["approved_asset_version"] is None
    assert candidate["kind"] == "video" and candidate["version"] == 1
    assert result["passed"] is True and result["error_code"] is None
    assert result["latency_ms"] is None and result["observed_task_latency_ms"] >= 0
    assert prompt_count(e) == 1 and e.discovery.center.lifecycle.start.call_count == 0
    with pytest.raises(FileNotFoundError):
        e.r.service.asset(e.r.nid, e.r.scope, candidate["id"])
    with pytest.raises(FileNotFoundError):
        e.r.assets.content(candidate["id"])
    with pytest.raises(FileNotFoundError):
        e.r.assets.content(candidate["id"], actor_id="another-author")
    with pytest.raises(FileNotFoundError):
        e.r.assets.content(candidate["id"], actor_id=e.r.actor)
    meta, data = e.production.candidate(e.r.nid, e.r.scope, e.r.actor,
        "video", job["id"], lambda: None,
        benchmark_binding=completed["video_sample"]["binding"])
    assert meta["id"] == candidate["id"] and meta["sha256"] == candidate["digest"]
    assert data == e.wire.data and hashlib.sha256(data).hexdigest() == candidate["digest"]
    measured = inspect_media(data, "video")
    assert measured["media_type"] == "video/webm"
    assert measured["validation"] == "DECODED" and measured["codec"] == "vp9"
    assert measured["duration_ms"] > 0
    calls = deepcopy(e.wire.calls)
    workspace, production, broker, bench = reopen_owners(e)
    persisted = bench.get(e.r.nid, e.r.scope, bench.RUNS, completed["id"])
    assert persisted == completed
    reopened_meta, reopened_data = production.candidate(e.r.nid, e.r.scope,
        e.r.actor, "video", job["id"], lambda: None,
        benchmark_binding=persisted["video_sample"]["binding"])
    assert reopened_meta == meta and reopened_data == data
    with pytest.raises(FileNotFoundError):
        workspace.assets.content(candidate["id"], actor_id=e.r.actor)
    with pytest.raises(FileNotFoundError):
        workspace.asset(e.r.nid, e.r.scope, candidate["id"])
    # Even a successful sample cannot manufacture an upstream invoice from a
    # local endpoint and an estimate. Original accounting keeps its hold.
    assert broker.budget(e.r.nid, e.r.scope)["inflight"] == 1
    ledger = broker.ledger(e.r.nid, e.r.scope, e.r.actor)
    assert len(ledger) == 1 and ledger[0]["status"] == "UNKNOWN_UPSTREAM"
    assert ledger[0]["actual_microusd"] is None and ledger[0]["dispatched"] is True
    assert e.wire.calls == calls


def test_observed_video_task_time_never_becomes_speed_or_inference_evidence(video_benchmark):
    e = video_benchmark
    completed = refresh(e, execute(e, preview(e, start(e))))
    evidence = next(row for row in e.bench.evidence(e.r.nid, e.r.scope)
        if row["run_id"] == completed["id"])
    assert evidence["capability"] == "VIDEO" and evidence["evidence_state"] == "CURRENT"
    assert evidence["routing_eligible"] is False
    assert evidence["metrics"]["sample_count"] == 1
    assert evidence["metrics"]["latency_ms"] is None
    assert evidence["gpu_memory_bytes"] is None and evidence["tokens_per_second"] is None
    assert evidence["quality_score"] is None and evidence["cold_start_state"] == "NOT_MEASURED"
    assert evidence.get("inference_verified") is not True
    assert e.adapter.studio_configuration()["video_recipe"]["inference_verified"] is False
    decision = e.broker.preview(e.r.nid, e.r.scope, e.r.actor, {
        "capability": "VIDEO", "policy": "SPEED", "profile": "LOCAL_ONLY",
        "preferred_route": e.route["route_id"], "max_latency_ms": 3600000})
    candidate = next(row for row in decision["candidates"] if row["route_id"] == e.route["route_id"])
    assert candidate["latency_ms"] is None and candidate["evidence_ids"] == []
    assert "LATENCY_EVIDENCE_UNKNOWN_OR_OVER_LIMIT" in candidate["reasons"]
    assert decision["chosen"] is None and prompt_count(e) == 1


def test_duplicate_video_execute_never_submits_a_second_prompt(video_benchmark):
    e = video_benchmark
    reviewed = preview(e, start(e))
    running = execute(e, reviewed)
    for duplicate in (reviewed, running):
        with pytest.raises((ValueError, CapabilityVersionConflict)):
            execute(e, duplicate)
    assert prompt_count(e) == 1
    assert len(e.broker.ledger(e.r.nid, e.r.scope, e.r.actor)) == 1
    assert current(e, running)["video_sample"]["job"]["id"] == running["video_sample"]["job"]["id"]


def test_video_execute_requires_the_exact_reviewed_preview(video_benchmark):
    e = video_benchmark
    reviewed = preview(e, start(e))
    with pytest.raises((ValueError, StaleSourceError)):
        execute(e, reviewed, "0" * 64)
    assert e.wire.calls == []
    assert not any(row["dispatched"] for row in e.broker.ledger(e.r.nid, e.r.scope, e.r.actor))


def test_unknown_video_submission_retains_hold_and_reconcile_never_replays(video_benchmark, monkeypatch):
    e = video_benchmark
    reviewed = preview(e, start(e))
    post = e.wire.post
    def lost_reply(url, **kwargs):
        response = post(url, **kwargs)
        if url.endswith("/prompt"):
            raise RuntimeError("Synthetic response lost after accepted submit")
        return response
    monkeypatch.setattr(e.wire, "post", lost_reply)
    with pytest.raises(RuntimeError, match="Synthetic response lost"):
        execute(e, reviewed)
    unknown = current(e, reviewed)
    assert unknown["status"] == "RUNNING"
    job = unknown["video_sample"]["job"]
    assert job["status"] == "UNKNOWN" and job["output_candidate"] is None
    assert job["automatic_replay"] is False and unknown["automatic_replay"] is False
    assert prompt_count(e) == 1 and e.broker.budget(e.r.nid, e.r.scope)["inflight"] == 1
    with pytest.raises((ValueError, CapabilityVersionConflict)):
        execute(e, unknown)
    calls = deepcopy(e.wire.calls)
    reconciled = e.bench.video.reconcile(e.r.nid, e.r.scope, e.r.actor,
        unknown["id"], unknown["version"], lambda: None)
    assert reconciled["video_sample"]["job"]["status"] == "UNKNOWN"
    assert reconciled["results"] == [] and e.wire.calls == calls
    assert e.broker.budget(e.r.nid, e.r.scope)["inflight"] == 1


def test_local_video_cancel_preserves_dispatched_inflight_hold(video_benchmark):
    e = video_benchmark
    running = execute(e, preview(e, start(e)))
    calls = deepcopy(e.wire.calls)
    cancelled = e.bench.cancel(e.r.nid, e.r.scope, e.r.actor, running["id"], running["version"])
    assert cancelled["status"] == "CANCELLED" and cancelled["results"] == []
    job = cancelled["video_sample"]["job"]
    assert job["status"] == "CANCELLED" and job["output_candidate"] is None
    assert job["remote_compute_may_continue"] is True and job["automatic_replay"] is False
    assert e.broker.budget(e.r.nid, e.r.scope)["inflight"] == 1
    ledger = e.broker.ledger(e.r.nid, e.r.scope, e.r.actor)
    assert len(ledger) == 1 and ledger[0]["dispatched"] is True
    assert ledger[0]["status"] in {"DISPATCHED", "UNKNOWN_UPSTREAM"}
    with pytest.raises((ValueError, CapabilityVersionConflict)):
        refresh(e, cancelled)
    with pytest.raises((ValueError, CapabilityVersionConflict)):
        execute(e, cancelled)
    assert e.wire.calls == calls and prompt_count(e) == 1
    assert e.bench.evidence(e.r.nid, e.r.scope) == []


@pytest.mark.parametrize("stage", ["before_submit", "before_refresh"])
def test_disabled_original_video_route_cannot_submit_or_download(video_benchmark, stage):
    e = video_benchmark
    run = preview(e, start(e))
    if stage == "before_refresh":
        run = execute(e, run)
    calls = deepcopy(e.wire.calls)
    e.discovery.disable(e.adapter.candidate["id"])
    with pytest.raises((ValueError, FileNotFoundError)):
        (execute if stage == "before_submit" else refresh)(e, run)
    assert e.wire.calls == calls
    assert not any(url.endswith("/view") for url, _ in e.wire.calls)
    assert e.discovery.center.lifecycle.start.call_count == 0


@pytest.mark.parametrize("endpoint", ["http://192.0.2.2:8188", "http://example.invalid:8188"])
def test_nominal_local_video_adapter_rejects_a_consistently_rebound_remote_endpoint(video_benchmark, endpoint):
    e = video_benchmark
    reviewed = preview(e, start(e))
    candidate = e.discovery.registrations[e.adapter.candidate["id"]]
    candidate["runtime_config"]["endpoint"] = endpoint
    e.adapter.candidate = deepcopy(candidate)
    e.adapter._studio_identity = deepcopy({key: candidate.get(key)
        for key in e.adapter._STUDIO_IDENTITY_FIELDS})
    e.adapter.endpoint = e.adapter.delegate.endpoint = endpoint
    calls = deepcopy(e.wire.calls)
    metadata_calls = deepcopy(e.discovery.client.calls)
    with pytest.raises(ValueError, match="STUDIO_DISCOVERED_VIDEO_REGISTRATION_CHANGED"):
        e.adapter.studio_configuration()
    assert not any(row["route_id"] == e.route["route_id"] for row in e.broker.candidates())
    with pytest.raises((ValueError, FileNotFoundError)):
        execute(e, reviewed)
    assert e.wire.calls == calls and e.discovery.client.calls == metadata_calls
    assert prompt_count(e) == 0 and e.discovery.center.lifecycle.start.call_count == 0


def test_bound_video_job_is_unavailable_to_standalone_production_commands(video_benchmark):
    e = video_benchmark
    running = execute(e, preview(e, start(e)))
    job = running["video_sample"]["job"]
    calls = deepcopy(e.wire.calls)
    action = MediaJobAction(expected_version=job["version"], expected_request_digest=job["request_digest"])
    with pytest.raises(FileNotFoundError):
        e.production.get(e.r.nid, e.r.scope, e.r.actor, "video", job["id"], lambda: None)
    with pytest.raises(FileNotFoundError):
        e.production.execute(e.r.nid, e.r.scope, e.r.actor, "video", job["id"], action, lambda: None)
    with pytest.raises(FileNotFoundError):
        e.production.refresh_video(e.r.nid, e.r.scope, e.r.actor, job["id"], action, lambda: None)
    with pytest.raises(ValueError):
        MediaCommand.model_validate({**e.command, "benchmark_binding": {"run_id": running["id"]}})
    assert e.wire.calls == calls and prompt_count(e) == 1


@pytest.mark.parametrize("stage", ["before_submit", "during_history"])
def test_changed_video_set_invalidates_preview_and_last_mile_download(video_benchmark, stage):
    e = video_benchmark
    saved = test_set(e)
    reviewed = preview(e, start(e, saved))
    if stage == "before_submit":
        changed_set(e, saved)
        with pytest.raises((ValueError, StaleSourceError)):
            execute(e, reviewed)
        assert prompt_count(e) == 0
    else:
        running = execute(e, reviewed)
        e.wire.after_history = lambda: changed_set(e, saved)
        with pytest.raises((ValueError, StaleSourceError)):
            refresh(e, running)
        assert prompt_count(e) == 1
    assert not any(url.endswith("/view") for url, _ in e.wire.calls)
    assert e.bench.evidence(e.r.nid, e.r.scope) == []


def test_recreated_project_cannot_reuse_old_video_run_request_identity(video_benchmark):
    e = video_benchmark
    old = start(e, request_id="same-user-request")
    incarnation = e.r.store.incarnation(e.r.nid)
    e.r.novels.delete(e.r.nid)
    e.r.create_project("Recreated independent video studio", nid=e.r.nid)
    e.r.service.activate(e.r.nid, e.r.scope, e.r.actor)
    assert e.r.store.incarnation(e.r.nid) != incarnation
    fresh = start(e, request_id="same-user-request")
    assert fresh["id"] != old["id"] and fresh["status"] == "READY"
    with pytest.raises((ValueError, FileNotFoundError)):
        preview(e, old)
    assert not e.wire.calls and e.discovery.center.lifecycle.start.call_count == 0


def test_two_video_samples_wait_for_reported_bill_and_ignore_late_first_sample(video_benchmark):
    e = video_benchmark
    saved = test_set(e, cases=[
        {"title": "First fixture", "kind": "VIDEO_WORKFLOW", "prompt": PROMPT},
        {"title": "Second fixture", "kind": "VIDEO_WORKFLOW", "prompt": "SECOND SYNTHETIC PRIVATE VIDEO"},
    ])
    first_running = execute(e, preview(e, start(e, saved)))
    late_first_sample = deepcopy(first_running["video_sample"])
    first = refresh(e, first_running)
    first_job = first["video_sample"]["job"]
    assert first["status"] == "READY" and first["completed"] == 1
    assert first["total"] == 2 and len(first["results"]) == 1 and prompt_count(e) == 1
    entries = e.broker.ledger(e.r.nid, e.r.scope, e.r.actor)
    assert len(entries) == 1 and entries[0]["status"] == "UNKNOWN_UPSTREAM"
    assert entries[0]["actual_microusd"] is None and entries[0]["dispatched"] is True
    assert e.broker.budget(e.r.nid, e.r.scope)["inflight"] == 1
    second_preview = preview(e, first)
    calls = deepcopy(e.wire.calls)
    with pytest.raises(ValueError, match="BROKER_CONCURRENCY_LIMIT"):
        execute(e, second_preview)
    blocked = current(e, first)
    assert blocked["status"] == "READY" and blocked["completed"] == 1
    assert blocked["video_samples"]["0"]["status"] == "COMPLETED"
    assert e.wire.calls == calls and prompt_count(e) == 1
    assert len(e.broker.ledger(e.r.nid, e.r.scope, e.r.actor)) == 1

    # This is an explicit report about the synthetic test, through the original
    # reconciliation API. It must not become automatic zero-fee evidence.
    entry = e.broker.ledger(e.r.nid, e.r.scope, e.r.actor)[0]
    reconciled = e.broker.reconcile(e.r.nid, e.r.scope, e.r.actor, entry["id"], {
        "expected_version": entry["version"], "actual_microusd": 0,
        "upstream_terminal_confirmed": True, "original_executor_stopped_confirmed": True,
        "evidence_note": "Manual synthetic fixture bill report: first injected task completed; reported total 0 USD, no live provider used.",
    })
    assert reconciled["status"] == "RECONCILED"
    assert reconciled["cost_state"] == "USER_REPORTED_UPSTREAM_BILL"
    assert reconciled["actual_microusd"] == 0 and reconciled["upstream_terminal_confirmed"] is True
    assert e.broker.budget(e.r.nid, e.r.scope)["inflight"] == 0
    assert e.wire.calls == calls
    second_preview = preview(e, current(e, first))
    second = execute(e, second_preview)
    second_job = second["video_sample"]["job"]
    assert second["status"] == "RUNNING" and second["video_sample"]["index"] == 1
    assert second_job["status"] == "REMOTE_RUNNING" and second_job["id"] != first_job["id"]
    assert second_job["request_digest"] != first_job["request_digest"]
    assert prompt_count(e) == 2
    with pytest.raises((ValueError, CapabilityVersionConflict)):
        execute(e, second)
    before_late = current(e, second)
    calls = deepcopy(e.wire.calls)
    after_late = e.bench.video._save_sample(e.r.nid, e.r.scope, e.r.actor,
        second["id"], late_first_sample, lambda: None)
    assert after_late == before_late and current(e, second) == before_late
    assert after_late["video_sample"]["job"]["id"] == second_job["id"]
    assert after_late["video_samples"]["0"]["status"] == "COMPLETED"
    assert e.wire.calls == calls
    completed = refresh(e, second)
    assert completed["status"] == "COMPLETED" and completed["completed"] == 2
    assert [row["index"] for row in completed["results"]] == [0, 1]
    assert len({row["media_receipt"]["task_id"] for row in completed["results"]}) == 2
    assert all(row["latency_ms"] is None for row in completed["results"])
    assert prompt_count(e) == 2
    entries = e.broker.ledger(e.r.nid, e.r.scope, e.r.actor)
    assert len(entries) == 2
    assert {row["status"] for row in entries} == {"RECONCILED", "UNKNOWN_UPSTREAM"}
    assert next(row for row in entries if row["job_id"] == second_job["id"])["actual_microusd"] is None


def test_reconstructed_video_adapter_refreshes_same_original_job_without_resubmission(video_benchmark):
    from app.model_center.discovery_bridge import LocalVideoAdapter
    e = video_benchmark
    running = execute(e, preview(e, start(e)))
    sample = deepcopy(running["video_sample"])
    job = sample["job"]
    assert job["status"] == "REMOTE_RUNNING" and prompt_count(e) == 1
    original_config = deepcopy(e.adapter.studio_configuration())
    original_route = e.broker.current_route(e.route["route_id"])
    saved_registration = deepcopy(e.discovery.registrations[e.adapter.candidate["id"]])
    rebuilt = LocalVideoAdapter(e.adapter.bridge, saved_registration)
    rebuilt.delegate.transport = e.wire
    e.adapter.bridge.video_registry[saved_registration["provider_id"]] = rebuilt
    assert rebuilt is not e.adapter and rebuilt.delegate is not e.adapter.delegate
    assert rebuilt.studio_configuration() == original_config
    assert e.discovery.registrations[saved_registration["id"]] == saved_registration
    _, production, broker, bench = reopen_owners(e)
    reopened_route = broker.current_route(original_route["route_id"])
    assert reopened_route["identity"] == original_route["identity"]
    assert reopened_route["fingerprint"] == original_route["fingerprint"]
    assert reopened_route["binding_hash"] == original_route["binding_hash"]
    restored = bench.get(e.r.nid, e.r.scope, bench.RUNS, running["id"])
    assert restored == running
    completed = bench.video.refresh(e.r.nid, e.r.scope, e.r.actor,
        restored["id"], restored["version"], lambda: None)
    assert completed["status"] == "COMPLETED" and completed["completed"] == 1
    assert completed["video_sample"]["job"]["id"] == job["id"]
    assert completed["video_sample"]["binding"] == sample["binding"]
    assert completed["video_sample"]["job"]["request_digest"] == job["request_digest"]
    assert completed["results"][0]["media_receipt"]["task_id"] == job["id"]
    _, data = production.candidate(e.r.nid, e.r.scope, e.r.actor, "video", job["id"],
        lambda: None, benchmark_binding=sample["binding"])
    assert data == e.wire.data and prompt_count(e) == 1
    assert e.discovery.center.lifecycle.start.call_count == 0


def test_cancel_after_video_history_fences_download_and_private_publication(video_benchmark):
    e = video_benchmark
    running = execute(e, preview(e, start(e)))
    cancellations = []

    def cancel_after_history():
        live = current(e, running)
        cancellations.append(e.bench.cancel(e.r.nid, e.r.scope, e.r.actor,
            live["id"], live["version"]))

    e.wire.after_history = cancel_after_history
    with pytest.raises(ValueError):
        refresh(e, running)
    cancelled = current(e, running)
    assert len(cancellations) == 1 and cancelled["status"] == "CANCELLED"
    assert cancelled["video_sample"]["job"]["status"] == "CANCELLED"
    assert cancelled["video_sample"]["job"]["output_candidate"] is None
    assert cancelled["video_sample"]["job"]["remote_compute_may_continue"] is True
    assert cancelled["results"] == [] and cancelled["completed"] == 0
    assert prompt_count(e) == 1
    assert not any(url.endswith("/view") for url, _ in e.wire.calls)
    assert e.r.service.list_assets(e.r.nid, e.r.scope) == {"items": []}
    assert e.bench.evidence(e.r.nid, e.r.scope) == []
    assert e.broker.budget(e.r.nid, e.r.scope)["inflight"] == 1
    ledger = e.broker.ledger(e.r.nid, e.r.scope, e.r.actor)
    assert len(ledger) == 1 and ledger[0]["dispatched"] is True
    assert ledger[0]["actual_microusd"] is None
