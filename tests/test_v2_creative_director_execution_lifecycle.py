"""Internal independent Director execution on the original owners, File only.

Run only with scripts/run_v2_checks.py and an owned --basetemp after source freeze.
These are protocol/authority tests, not live-model quality or public availability.
"""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from threading import Event
import json

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.jobs import JobManager, generation_content_available, require_whole_generation_acceptance
from app.model_center.discovery_authority import DiscoveryAuthority
from app.model_runtime import GenerationEvent
from creative_director_execution_fixture import (
    CONTRACT, FLAGS, TEXT, ForbiddenOwner, lifecycle, preview, dispatch, result, raw_proposal, run, wait,
)

pytestmark = pytest.mark.file_backend_only
DENIALS = (ValueError, HTTPException, PermissionError, FileNotFoundError, KeyError)


def ledger(e):
    return e.broker.ledger(e.nid, e.scope, e.actor)


def assert_hidden(e, job):
    assert not generation_content_available(job)
    assert list(e.manager.events(job.id)) == []
    for action in (lambda: require_whole_generation_acceptance(job), lambda: e.manager.accept(job.id),
                   lambda: e.manager.reject(job.id), lambda: e.manager.diff(job.id)):
        with pytest.raises(HTTPException):
            action()


def capture_start(e, monkeypatch, mutate):
    original = e.manager._start_creative_director_job
    captured = []
    def start(job, capability):
        captured.append(job)
        mutate(job)
        return original(job, capability)
    monkeypatch.setattr(e.manager, "_start_creative_director_job", start)
    return captured


def test_original_file_worker_exact_request_single_accounting_and_internal_result(lifecycle, monkeypatch):
    e = lifecycle
    calls = []
    for name in ("reserve", "guard_dispatch", "finalize"):
        original = getattr(e.broker, name)
        def observed(*args, _name=name, _original=original, **kwargs):
            calls.append(_name)
            return _original(*args, **kwargs)
        monkeypatch.setattr(e.broker, name, observed)
    before = deepcopy(e.source)
    prepared, receipt, job = run(e)
    assert job.operation == "creative_director_text" and job.experimental_origin == "creative_director_source_model"
    assert job.chapter_id is None and job.graph_binding is None and job.adaptation_binding is None
    assert job.context_snapshot_id is None and job.base_chapter_version is None
    assert job.status == "COMPLETED" and job.terminal_hook_status == "COMPLETED"
    assert job.output == TEXT and job.execution_outcome == "COMPLETED"
    assert job.usage == {"input_tokens": 3, "output_tokens": 4, "total_tokens": 7}
    assert len(e.requests) == 1 and len(job.route_decisions) == 1
    request = e.requests[0]
    assert request["model"] == "explicit-fixture-model" and request["stream"] is False
    assert request["max_tokens"] == 512 and request["temperature"] == 0.0
    assert request["messages"][-1] == {"role": "user", "content": prepared["model_preview"]["prompt"]}
    assert "The visitor turns." in request["messages"][-1]["content"]
    assert calls == ["reserve", "guard_dispatch", "finalize"]
    accounting = ledger(e)
    assert len(accounting) == 1 and accounting[0]["job_id"] == job.id
    assert accounting[0]["status"] == "SETTLED" and accounting[0]["actual_microusd"] == 0
    assert accounting[0]["version"] == 3
    saved = e.persistence.get(job.id)
    assert saved["status"] == "COMPLETED" and saved["terminal_hook_status"] == "COMPLETED"
    assert saved["creative_director_binding"] == job.creative_director_binding
    assert "prepared_text_invocation" not in saved and "request_authorization" not in saved
    assert prepared["model_preview"]["prompt"] not in json.dumps(saved)
    internal = result(e)
    assert internal["text"] == TEXT and internal["job_id"] == job.id
    assert internal["request_digest"] == job.expected_request_digest
    assert internal["preview_digest"] == prepared["model_preview"]["preview_digest"]
    internal["text"] = "Detached replacement"
    assert result(e)["text"] == TEXT
    assert e.documents.get(e.nid, e.scope, e.source["id"]) == before
    assert_hidden(e, job)
    with pytest.raises(DENIALS): e.manager.start_prepared(job)
    with pytest.raises(DENIALS): dispatch(e, prepared)
    assert len(e.requests) == 1 and len(ledger(e)) == 1
    current = raw_proposal(e)
    assert current["status"] != "NEEDS_REVIEW" and current["document_id"] is None
    assert current["director_notes"] == []


@pytest.mark.parametrize("authority", [None, False, "principal", {},
    DiscoveryAuthority("", lambda: None), DiscoveryAuthority("a" * 64, None)])
def test_actual_discovery_authority_and_live_principal_are_mandatory(lifecycle, authority):
    e = lifecycle
    e.authority = authority
    with pytest.raises((TypeError, AttributeError) + DENIALS): preview(e)
    assert not e.requests and not e.manager.jobs and not ledger(e)


@pytest.mark.parametrize("change", ["host_revoke", "host_aba", "scope_revoke", "actor", "scope", "flags", "acceptance"])
def test_authority_changes_after_preview_deny_before_reservation(lifecycle, monkeypatch, change):
    e = lifecycle; prepared = preview(e)
    if change == "host_revoke": e.sessions.revoke(e.token)
    elif change == "host_aba":
        e.sessions.revoke(e.token); e.sessions.register(e.token, e.session)
    elif change == "scope_revoke": e.active = False
    elif change == "actor": e.ctx.actor = "different-actor"
    elif change == "scope": e.ctx.scope = {"mode": "local", "novel_id": "different-project"}
    elif change == "flags": monkeypatch.setenv("EXPERIMENTAL_FEATURES", "")
    else: monkeypatch.setenv("V1_ACCEPTANCE_MODE", "true")
    with pytest.raises(DENIALS): dispatch(e, prepared)
    assert not e.requests and not e.manager.jobs and not ledger(e)


@pytest.mark.parametrize("change", ["license", "managed", "locality", "model_evidence", "enabled_receipt", "price", "budget", "source", "proposal"])
def test_current_source_route_price_budget_license_rechecked_before_admission(lifecycle, change):
    e = lifecycle; prepared = preview(e)
    if change == "license": e.candidate["license_confirmed"] = False
    elif change == "managed": e.candidate["runtime_config"]["management"] = "MANAGED"
    elif change == "locality": e.candidate["source_locality"] = "REMOTE"
    elif change == "model_evidence": e.candidate["model_evidence_fingerprint"] = "changed"
    elif change == "enabled_receipt": e.candidate["enabled_at"] = "replacement"
    elif change == "budget":
        e.broker.configure_budget(e.nid, e.scope, e.actor, {"expected_version": 0, "max_inflight": 2})
    else:
        with e.raw.transaction(e.nid, e.scope) as state:
            if change == "price": state["collections"][e.broker.PRICES][e.route["route_id"]]["reserve_microusd"] = 1
            elif change == "source": state["collections"][e.documents.COLLECTION][e.source["id"]]["title"] = "Changed current source"
            else: state["collections"][e.documents.proposals.COLLECTION][e.row["id"]]["source_digest"] = "f" * 64
    with pytest.raises(DENIALS): dispatch(e, prepared)
    assert not e.requests and not e.manager.jobs and not ledger(e)


@pytest.mark.parametrize("change", ["managed", "license", "locality", "synthetic", "cloud"])
def test_unapproved_routes_never_reach_original_worker(lifecycle, monkeypatch, change):
    e = lifecycle
    if change == "managed": e.candidate["runtime_config"]["management"] = "MANAGED"
    elif change == "license": e.candidate["license_confirmed"] = False
    elif change == "locality": e.candidate["source_locality"] = "REMOTE"
    elif change == "cloud":
        original = e.runtime.is_remote_text_provider
        monkeypatch.setattr(e.runtime, "is_remote_text_provider", lambda provider: provider == e.candidate["provider_id"] or original(provider))
    else: e.route = next(row for row in e.broker.candidates(local_text_only=True) if row["provider_id"] == "mock")
    with pytest.raises(DENIALS): preview(e)
    assert not e.requests and not e.manager.jobs and not ledger(e)


@pytest.mark.parametrize("field,value", [("expected_version", True), ("allow_synthetic", "false"),
    ("max_output_tokens", True), ("max_output_tokens", 0), ("temperature", float("nan")),
    ("endpoint", "http://127.0.0.1:8999"), ("max_output_bytes", 10)])
def test_internal_preview_input_is_strict_and_cannot_add_route_or_bounds(lifecycle, field, value):
    with pytest.raises(DENIALS): preview(lifecycle, **{field: value})
    assert not lifecycle.requests and not lifecycle.manager.jobs and not ledger(lifecycle)


@pytest.mark.parametrize("mutation", ["binding", "actor", "scope", "job_id", "provider", "model", "prompt", "parameters",
    "output_bound", "deadline", "cancellation", "origin", "graph", "adaptation"])
def test_prepared_identity_and_request_tamper_denied_before_worker(lifecycle, monkeypatch, mutation):
    e = lifecycle; prepared = preview(e)
    def mutate(job):
        if mutation == "binding": job.creative_director_binding["source_version"] += 1
        elif mutation == "actor": job.actor_id = "other"
        elif mutation == "scope": job.scope["novel_id"] = "other"
        elif mutation == "job_id": job.id = "00000000-0000-4000-8000-000000000000"
        elif mutation == "provider": job.requested_provider = "mock"
        elif mutation == "model": job.requested_model = "other"
        elif mutation in {"prompt", "parameters"}:
            invocation = job.prepared_text_invocation
            request = invocation.request
            request = replace(request, prompt="different") if mutation == "prompt" else replace(request,
                parameters=replace(request.parameters, max_output_tokens=256))
            job.prepared_text_invocation = replace(invocation, request=request)
        elif mutation == "output_bound": job.generation_max_output_bytes += 1
        elif mutation == "deadline": job.generation_deadline = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        elif mutation == "cancellation": job.cancelled = Event()
        elif mutation == "origin": job.experimental_origin = "creative_graph_model"
        elif mutation == "graph": job.graph_binding = {}
        else: job.adaptation_binding = {}
    capture_start(e, monkeypatch, mutate)
    with pytest.raises(DENIALS): dispatch(e, prepared)
    assert not e.requests
    current = raw_proposal(e)["model_execution"]
    assert current["status"] == "UNKNOWN" and current["receipt_state"] == "UNKNOWN_NO_AUTOMATIC_REPLAY"
    assert len(ledger(e)) == 1 and ledger(e)[0]["status"] == "RESERVED"


@pytest.mark.parametrize("kind", ["event_job", "response_provider", "response_model", "no_delta", "mismatch", "blank", "truncated", "no_completion"])
def test_every_event_and_complete_response_is_exact(lifecycle, monkeypatch, kind):
    e = lifecycle
    original = e.adapter.stream_text
    def stream(request):
        for event in original(request):
            if event.event_type == "generation.delta":
                if kind == "no_delta": continue
                if kind == "event_job": event = replace(event, job_id="wrong-job")
            if event.event_type == "generation.completed":
                if kind == "no_completion": continue
                response = event.response
                if kind == "response_provider": response = replace(response, provider_id="other")
                elif kind == "response_model": response = replace(response, model_id="other")
                elif kind == "mismatch": response = replace(response, text="different output")
                elif kind == "blank": response = replace(response, text=" ")
                elif kind == "truncated": response = replace(response, finish_reason="length")
                event = replace(event, response=response)
            yield event
    monkeypatch.setattr(e.adapter, "stream_text", stream)
    _, _, job = run(e)
    assert job.status == "FAILED" and not job.output
    assert len(e.requests) == 1 and len(ledger(e)) == 1
    with pytest.raises(DENIALS): result(e)
    assert_hidden(e, job)


@pytest.mark.parametrize("change", ["host_revoke", "host_aba", "scope_revoke", "flags", "source", "cancel", "cancel_identity"])
def test_changes_during_wire_suppress_late_chunks_and_success(lifecycle, monkeypatch, change):
    e = lifecycle; entered, release = Event(), Event()
    def block():
        entered.set(); assert release.wait(5)
    e.wire_hook = block
    prepared = preview(e)
    receipt = dispatch(e, prepared)
    job = e.manager.get(receipt["model_execution"]["job_id"])
    try:
        assert entered.wait(3)
        if change == "host_revoke": e.sessions.revoke(e.token)
        elif change == "host_aba":
            e.sessions.revoke(e.token); e.sessions.register(e.token, e.session)
        elif change == "scope_revoke": e.active = False
        elif change == "flags": monkeypatch.setenv("EXPERIMENTAL_FEATURES", "")
        elif change == "cancel": e.manager.cancel(job.id)
        elif change == "cancel_identity": job.cancelled = Event()
        else:
            with e.raw.transaction(e.nid, e.scope) as state:
                state["collections"][e.documents.COLLECTION][e.source["id"]]["title"] = "Changed while provider waited"
    finally:
        release.set()
    wait(e, job)
    assert job.status in {"FAILED", "CANCELLED"} and not job.output
    assert len(e.requests) == 1 and len(ledger(e)) == 1
    with pytest.raises(DENIALS): result(e)
    assert_hidden(e, job)


@pytest.mark.parametrize("change", ["host_revoke", "scope_revoke", "cancel", "cancel_identity", "bounds"])
def test_changes_after_real_broker_settlement_cannot_publish_success(lifecycle, monkeypatch, change):
    e = lifecycle; original = e.broker.finalize; calls = []
    def finalize(*args, **kwargs):
        calls.append(1)
        accounting = original(*args, **kwargs)
        job = next(iter(e.manager.jobs.values()))
        if change == "host_revoke": e.sessions.revoke(e.token)
        elif change == "scope_revoke": e.active = False
        elif change == "cancel": job.cancelled.set()
        elif change == "cancel_identity": job.cancelled = Event()
        else: job.generation_max_output_bytes += 1
        return accounting
    monkeypatch.setattr(e.broker, "finalize", finalize)
    _, _, job = run(e)
    assert calls == [1] and job.status in {"FAILED", "CANCELLED"} and not job.output
    assert len(e.requests) == 1 and ledger(e)[0]["status"] == "SETTLED"
    with pytest.raises(DENIALS): result(e)
    assert_hidden(e, job)


@pytest.mark.parametrize("boundary", ["reserve_before", "reserve_after", "start"])
def test_ambiguous_admission_keeps_unknown_and_never_releases_or_replays(lifecycle, monkeypatch, boundary):
    e = lifecycle; prepared = preview(e); calls = []
    original = e.broker.reserve
    def reserve(*args, **kwargs):
        calls.append("reserve")
        if boundary == "reserve_before": raise OSError("injected reserve failure")
        receipt = original(*args, **kwargs)
        if boundary == "reserve_after": raise OSError("injected lost reserve response")
        return receipt
    monkeypatch.setattr(e.broker, "reserve", reserve)
    monkeypatch.setattr(e.broker, "finalize", lambda *a, **k: pytest.fail("Ambiguous admission released hold"))
    if boundary == "start":
        monkeypatch.setattr(e.manager, "_start_creative_director_job", lambda *a: (_ for _ in ()).throw(OSError("injected start failure")))
    with pytest.raises(OSError): dispatch(e, prepared)
    execution = raw_proposal(e)["model_execution"]
    assert execution["status"] == "UNKNOWN" and execution["receipt_state"] == "UNKNOWN_NO_AUTOMATIC_REPLAY"
    assert not e.requests
    with pytest.raises(DENIALS): dispatch(e, prepared)
    with pytest.raises(DENIALS): result(e)
    assert calls == ["reserve"]
    assert len(ledger(e)) == (0 if boundary == "reserve_before" else 1)
    assert all(item["status"] == "RESERVED" for item in ledger(e))


@pytest.mark.parametrize("boundary", ["settling", "finalize", "final_write"])
def test_terminal_persistence_or_accounting_failure_hides_text_without_replay(lifecycle, monkeypatch, boundary):
    e = lifecycle; saved = e.persistence.save; finalize = e.broker.finalize; failures = []; accounting = []
    def save(value):
        status = value.get("status")
        if not failures and ((boundary == "settling" and status == "SETTLING") or
                             (boundary == "final_write" and status == "COMPLETED")):
            failures.append(status); raise OSError("injected terminal write failure")
        return saved(value)
    def settle(*args, **kwargs):
        accounting.append(1)
        if boundary == "finalize": raise OSError("injected settlement failure")
        return finalize(*args, **kwargs)
    monkeypatch.setattr(e.persistence, "save", save)
    monkeypatch.setattr(e.broker, "finalize", settle)
    prepared, _, job = run(e)
    assert job.status == "FAILED" and not job.output and len(e.requests) == 1
    assert len(accounting) <= 1
    if boundary != "finalize": assert failures
    with pytest.raises(DENIALS): result(e)
    with pytest.raises(DENIALS): dispatch(e, prepared)
    assert len(e.requests) == 1 and len(ledger(e)) == 1
    assert_hidden(e, job)


@pytest.mark.parametrize("status", ["PREPARED", "QUEUED", "GENERATING", "SETTLING", "COMPLETED"])
def test_restart_strips_authority_without_replay_or_ledger_mutation(lifecycle, monkeypatch, status):
    e = lifecycle; _, _, job = run(e)
    item = e.persistence.get(job.id)
    item["status"] = status
    e.persistence.save(item)
    before = deepcopy(ledger(e)); calls = len(e.requests)
    monkeypatch.setattr(e.broker, "finalize", lambda *a, **k: pytest.fail("Restart released ledger"))
    owner = ForbiddenOwner()
    restored = JobManager(e.persistence, owner, owner, owner, memory_extractor=owner)
    loaded = restored.get(job.id)
    for name in ("creative_execution_authority", "request_authorization", "prepared_text_invocation", "author_preparation_guard", "before_dispatch", "on_terminal"):
        assert getattr(loaded, name) is None
    assert loaded.status == ("COMPLETED" if status == "COMPLETED" else "FAILED")
    assert not generation_content_available(loaded)
    with pytest.raises(DENIALS): restored.start_prepared(loaded)
    assert ledger(e) == before and len(e.requests) == calls


def public_client(e, prefix):
    from app.creative.api import create_creative_router
    from app.experimental.flags import require_flag
    app = FastAPI()
    def authorize(nid, token, branch, permission):
        assert nid == e.nid and token == e.token and branch is None
        e.guard(); e.authority.guard()
        return e.actor, deepcopy(e.scope)
    app.include_router(create_creative_router(e.documents, authorize, require_flag,
        require_host_session=lambda token: e.authority.guard(), model_host_authority=lambda request, token: e.authority),
        prefix=prefix)
    return TestClient(app), prefix + "/novels/" + e.nid + "/experimental/creative/director-proposals"


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
@pytest.mark.parametrize("placement", ["live", "history", "nested_preview", "nested_execution"])
def test_internal_model_records_never_leak_through_public_reads_or_stale_conflicts(lifecycle, prefix, placement):
    e = lifecycle; prepared = preview(e)
    secret = prepared["model_preview"]["prompt"]
    history_secret = "PRIVATE_INTERNAL_HISTORY_SENTINEL"
    with e.raw.transaction(e.nid, e.scope) as state:
        row = state["collections"][e.documents.proposals.COLLECTION][e.row["id"]]
        marker = {"contract": CONTRACT, "prompt": secret, "output": TEXT, "request": history_secret}
        if placement == "live": row["model_preview"] = marker
        else:
            row["model_preview"] = row["model_execution"] = None
            row["history"] = []
            if placement == "history": row["history"] = [{"model_preview": marker, "private": history_secret}]
            else: row["model_preview" if placement == "nested_preview" else "model_execution"] = {"nested": marker}
    client, base = public_client(e, prefix)
    headers = {"X-Session-Token": e.token}
    responses = [client.get(base, headers=headers), client.get(base + "/" + e.row["id"], headers=headers)]
    bodies = {
        "preview": {"expected_version": 1, "route_id": e.route["route_id"]},
        "dispatch": {"expected_version": 1, "reviewed_preview_digest": "b" * 64},
        "refresh": {"expected_version": 1}, "cancel": {"expected_version": 1},
        "review": {"expected_version": 1, "reviewed_output_digest": e.row["output_digest"],
                   "title": e.row["title"], "director_notes": e.row["director_notes"]},
        "storyboard-preview": {"expected_version": 1, "route_id": e.route["route_id"], "source_contract": "STORYBOARD_SHOT_CONTEXT_V1"},
        "storyboard-dispatch": {"expected_version": 1, "reviewed_preview_digest": "b" * 64, "source_contract": "STORYBOARD_SHOT_CONTEXT_V1"},
    }
    before = e.raw.read(e.nid, e.scope)
    for action, body in bodies.items():
        response = client.post(base + "/" + e.row["id"] + "/" + action, headers=headers, json=body)
        assert response.status_code in {400, 403, 404, 409, 422}, (action, response.text)
        responses.append(response)
    for response in responses:
        encoded = json.dumps(response.json(), ensure_ascii=False)
        assert secret not in encoded and TEXT not in encoded and history_secret not in encoded
        assert CONTRACT not in encoded and '"history"' not in encoded
        assert response.headers["cache-control"] == "no-store"
        if response.status_code == 409 and isinstance(response.json().get("current"), dict):
            assert set(response.json()["current"]) <= {"version", "status"}
    assert e.raw.read(e.nid, e.scope) == before
    assert not e.requests and not e.manager.jobs and not ledger(e)


@pytest.mark.parametrize("shape", ["overdepth", "malformed_history", "malformed_snapshot", "oversized_history"])
def test_malformed_or_overdepth_history_fails_closed(lifecycle, shape):
    from app.creative.director_binding import _has_internal_director_record
    row = deepcopy(lifecycle.row)
    if shape == "malformed_history": row["history"] = {"not": "a list"}
    elif shape == "malformed_snapshot": row["history"] = ["not a snapshot"]
    elif shape == "oversized_history": row["history"] = [{} for _ in range(101)]
    else:
        current = row
        for _ in range(34):
            current["history"] = [{}]; current = current["history"][0]
        current["model_execution"] = {"contract": CONTRACT}
    assert _has_internal_director_record(row)


def test_authored_marker_looking_text_does_not_reclassify_legacy_rule_assisted_proposal(lifecycle):
    from app.creative.director_binding import _has_internal_director_record
    e = lifecycle
    with e.raw.transaction(e.nid, e.scope) as state:
        row = state["collections"][e.documents.proposals.COLLECTION][e.row["id"]]
        row["title"] = CONTRACT
        row["director_notes"][0]["note"] = CONTRACT
    public = e.documents.proposals.get(e.nid, e.scope, e.actor, e.row["id"])
    assert not _has_internal_director_record(public)
    assert public["title"] == CONTRACT and public["status"] == "NEEDS_REVIEW"


def source_binding(e):
    return {"contract": "CREATIVE_DIRECTOR_SOURCE_V1", "source_kind": "STORYBOARD", "project_id": e.nid,
        "project_incarnation": e.source["project_incarnation"], "actor_id": e.actor, "scope": deepcopy(e.scope),
        "source_document_id": e.source["id"], "source_version": e.source["version"],
        "source_digest": e.documents.document_digest(e.source), "reviewed_preview_digest": "b" * 64}


def test_locked_validator_requires_actual_scope_and_matching_owner(lifecycle):
    from app.creative.director_binding import _validate_creative_director_source_locked as validate
    e = lifecycle; binding = source_binding(e)
    with pytest.raises(ValueError): validate(e.documents, binding, actor_id=e.actor, scope=e.scope)
    with e.raw.transaction(e.nid, e.scope):
        with pytest.raises(ValueError): validate(e.documents, binding, actor_id=e.actor, scope=e.scope)
    with e.documents.store.owner_lease(e.nid):
        with pytest.raises(ValueError): validate(e.documents, binding, actor_id=e.actor, scope=e.scope)


def test_locked_validation_composes_with_original_broker_transaction_writes(lifecycle):
    from app.creative.director_binding import (_validate_creative_director_source_locked as validate,
                                             _creative_director_owner_lease)
    e = lifecycle; binding = source_binding(e)
    with e.broker._owned_transaction(e.nid, e.scope,
            lambda: _creative_director_owner_lease(e.documents, binding)) as state:
        state["collections"].setdefault("fixture_ledger_boundary", {})["before"] = {"value": 1}
        assert validate(e.documents, binding, actor_id=e.actor, scope=e.scope) == e.source
        state["collections"]["fixture_ledger_boundary"]["after"] = {"value": 2}
    assert set(e.raw.read(e.nid, e.scope)["collections"]["fixture_ledger_boundary"]) == {"before", "after"}


@pytest.mark.parametrize("change", ["raw_scope", "owner", "creative_view", "source_mutation"])
def test_locked_validation_rejects_mismatched_or_mutated_active_snapshot(lifecycle, monkeypatch, change):
    from app.creative.director_binding import (_validate_creative_director_source_locked as validate,
                                             _creative_director_owner_lease)
    e = lifecycle; binding = source_binding(e); before = e.raw.read(e.nid, e.scope)
    with pytest.raises(ValueError):
        with e.raw.transaction(e.nid, e.scope) as state:
            with _creative_director_owner_lease(e.documents, binding):
                key = e.raw.key(e.nid, e.scope)
                if change == "raw_scope": state["scope"] = {"mode": "local", "novel_id": "wrong"}
                elif change == "owner": e.documents.store._local.owners[e.nid] = "file:00000000-0000-4000-8000-000000000000"
                elif change == "creative_view":
                    view = deepcopy(state)
                    view["collections"][e.documents.COLLECTION][e.source["id"]]["title"] = "Detached view"
                    e.documents.store._local.active = {key: view}
                else:
                    original = e.documents.get
                    def changed(*args, **kwargs):
                        output = original(*args, **kwargs)
                        state["collections"][e.documents.COLLECTION][e.source["id"]]["title"] = "Mutation during validation"
                        return output
                    monkeypatch.setattr(e.documents, "get", changed)
                try: validate(e.documents, binding, actor_id=e.actor, scope=e.scope)
                finally:
                    if change == "creative_view": e.documents.store._local.active = {}
    assert e.raw.read(e.nid, e.scope) == before


@pytest.mark.parametrize("boundary", ["preview", "reserve", "guard_dispatch", "finalize"])
def test_missing_marker_at_each_broker_boundary_is_not_provisioned(lifecycle, monkeypatch, boundary):
    e = lifecycle
    marker = e.root / "novels" / e.nid / "creative_project_v2.json"
    original = getattr(e.broker, boundary)
    def remove(*args, **kwargs):
        marker.unlink()
        return original(*args, **kwargs)
    monkeypatch.setattr(e.broker, boundary, remove)
    if boundary == "preview":
        with pytest.raises(DENIALS): preview(e)
    elif boundary == "reserve":
        prepared = preview(e)
        with pytest.raises(DENIALS): dispatch(e, prepared)
    else:
        prepared = preview(e)
        try:
            receipt = dispatch(e, prepared)
        except DENIALS:
            receipt = None
        jobs = list(e.manager.jobs.values())
        if receipt is not None:
            assert jobs and jobs[0].id == receipt["model_execution"]["job_id"]
        for job in jobs:
            wait(e, job)
            assert job.status == "FAILED" and not job.output
    assert not marker.exists()
    assert len(e.requests) == (1 if boundary == "finalize" else 0)


@pytest.mark.parametrize("hook", ["before_dispatch", "on_terminal"])
def test_replaced_accounting_hooks_cannot_publish_success(lifecycle, monkeypatch, hook):
    e = lifecycle; prepared = preview(e); calls = []
    capture_start(e, monkeypatch, lambda job: setattr(job, hook, lambda: calls.append("forged hook")))
    with pytest.raises(DENIALS): dispatch(e, prepared)
    assert not e.requests and not calls
    assert len(ledger(e)) == 1 and ledger(e)[0]["status"] == "RESERVED"


@pytest.mark.parametrize("field,value", [("contract", "OTHER"), ("source_kind", "SCREENPLAY"),
    ("project_id", "other"), ("project_incarnation", "file:00000000-0000-4000-8000-000000000000"),
    ("actor_id", "other"), ("scope", {"mode": "local", "novel_id": "other"}),
    ("source_document_id", "other"), ("source_version", 2), ("source_digest", "c" * 64),
    ("reviewed_preview_digest", "d" * 64)])
def test_each_source_binding_field_is_fenced_before_start(lifecycle, monkeypatch, field, value):
    e = lifecycle; prepared = preview(e)
    capture_start(e, monkeypatch, lambda job: job.creative_director_binding.update({field: value}))
    with pytest.raises(DENIALS): dispatch(e, prepared)
    assert not e.requests
    assert raw_proposal(e)["model_execution"]["status"] == "UNKNOWN"


@pytest.mark.parametrize("boundary", ["before_broker", "after_broker"])
@pytest.mark.parametrize("change", ["host", "scope", "bounds", "cancellation"])
def test_dispatch_revalidates_before_and_after_broker_io(lifecycle, monkeypatch, boundary, change):
    e = lifecycle; original = e.broker.guard_dispatch; counts = []
    def mutate():
        job = next(iter(e.manager.jobs.values()))
        if change == "host": e.sessions.revoke(e.token)
        elif change == "scope": e.active = False
        elif change == "bounds": job.generation_max_output_bytes += 1
        else: job.cancelled = Event()
    def guard_dispatch(*args, **kwargs):
        counts.append(1)
        if boundary == "before_broker": mutate()
        receipt = original(*args, **kwargs)
        if boundary == "after_broker": mutate()
        return receipt
    monkeypatch.setattr(e.broker, "guard_dispatch", guard_dispatch)
    _, _, job = run(e)
    assert counts == [1] and not e.requests and job.status == "FAILED" and not job.output
    assert len(ledger(e)) == 1
    with pytest.raises(DENIALS): result(e)


@pytest.mark.parametrize("boundary", ["pending_write", "queued_write"])
def test_admission_write_uncertainty_never_releases_or_replays(lifecycle, monkeypatch, boundary):
    from contextlib import contextmanager
    e = lifecycle; prepared = preview(e); original = e.raw.transaction; failed = []
    @contextmanager
    def transaction(*args, **kwargs):
        with original(*args, **kwargs) as state:
            yield state
            row = state["collections"].get(e.documents.proposals.COLLECTION, {}).get(e.row["id"], {})
            status = (row.get("model_execution") or {}).get("status")
            target = "ADMISSION_PENDING" if boundary == "pending_write" else "QUEUED"
            if status == target and not failed:
                failed.append(status)
                raise OSError("injected original Creative admission write failure")
    monkeypatch.setattr(e.raw, "transaction", transaction)
    monkeypatch.setattr(e.broker, "finalize", lambda *a, **k: pytest.fail("Admission uncertainty released hold"))
    with pytest.raises(OSError): dispatch(e, prepared)
    assert failed and not e.requests
    current = raw_proposal(e)
    assert current["model_execution"]["status"] == "UNKNOWN"
    assert current["model_execution"]["receipt_state"] == "UNKNOWN_NO_AUTOMATIC_REPLAY"
    with pytest.raises(DENIALS): dispatch(e, prepared)
    assert len(ledger(e)) == (0 if boundary == "pending_write" else 1)
    assert all(row["status"] == "RESERVED" for row in ledger(e))


@pytest.mark.parametrize("change", ["deleted", "recreated", "missing_marker"])
def test_preview_cannot_transfer_to_deleted_or_recreated_project_owner(lifecycle, change):
    e = lifecycle; prepared = preview(e)
    marker = e.root / "novels" / e.nid / "creative_project_v2.json"
    if change == "missing_marker": marker.unlink()
    else:
        e.novels.delete(e.nid)
        if change == "recreated":
            e.novels.create({"id": e.nid, "title": "Replacement owner"})
            assert e.documents.store.incarnation(e.nid) != e.source["project_incarnation"]
    with pytest.raises(DENIALS): dispatch(e, prepared)
    assert not e.requests and not e.manager.jobs
    if change == "missing_marker": assert not marker.exists()
    elif change == "deleted": assert not (e.root / "novels" / e.nid).exists()


def test_complete_output_larger_than_bound_is_discarded(lifecycle):
    e = lifecycle; prepared = preview(e)
    e.wire_text = "x" * (prepared["model_preview"]["max_output_bytes"] + 1)
    receipt = dispatch(e, prepared)
    job = wait(e, e.manager.get(receipt["model_execution"]["job_id"]))
    assert job.status == "FAILED" and not job.output and len(e.requests) == 1
    with pytest.raises(DENIALS): result(e)


@pytest.mark.parametrize("event_type", ["generation.started", "generation.delta", "generation.completed"])
def test_job_identity_is_checked_on_every_event_type(lifecycle, monkeypatch, event_type):
    e = lifecycle; original = e.adapter.stream_text
    def stream(request):
        for event in original(request):
            yield replace(event, job_id="other-job") if event.event_type == event_type else event
    monkeypatch.setattr(e.adapter, "stream_text", stream)
    _, _, job = run(e)
    assert job.status == "FAILED" and not job.output
    assert len(e.requests) == (0 if event_type == "generation.started" else 1)
    with pytest.raises(DENIALS): result(e)


@pytest.mark.parametrize("event_type", ["generation.delta", "generation.completed"])
def test_revocation_after_a_yielded_event_discards_previous_output(lifecycle, monkeypatch, event_type):
    e = lifecycle; original = e.adapter.stream_text
    def stream(request):
        for event in original(request):
            yield event
            if event.event_type == event_type:
                e.active = False
    monkeypatch.setattr(e.adapter, "stream_text", stream)
    _, _, job = run(e)
    assert job.status == "FAILED" and not job.output and len(e.requests) == 1
    with pytest.raises(DENIALS): result(e)
    assert_hidden(e, job)


def test_preexisting_cancel_is_not_replaced_by_a_fresh_request(lifecycle, monkeypatch):
    e = lifecycle; prepared = preview(e)
    capture_start(e, monkeypatch, lambda job: job.cancelled.set())
    with pytest.raises(DENIALS): dispatch(e, prepared)
    assert not e.requests and len(ledger(e)) == 1
    assert raw_proposal(e)["model_execution"]["status"] == "UNKNOWN"


@pytest.mark.parametrize("shape", ["contract_list", "contract_dict", "nested_list", "deep_model"])
def test_structurally_malformed_model_payloads_redact_without_recursive_copy(lifecycle, shape):
    from app.creative.director_binding import _has_internal_director_record
    e = lifecycle; row = deepcopy(e.row)
    if shape == "contract_list": row["model_preview"] = {"contract": [CONTRACT], "prompt": TEXT}
    elif shape == "contract_dict": row["model_execution"] = {"contract": {"unexpected": CONTRACT}, "text": TEXT}
    elif shape == "nested_list": row["model_preview"] = {"nested": [[{"contract": CONTRACT, "text": TEXT}]]}
    else:
        row["model_preview"] = {}; current = row["model_preview"]
        for _ in range(1500):
            current["nested"] = {}; current = current["nested"]
        current["contract"] = CONTRACT
        current["text"] = TEXT
    assert _has_internal_director_record(row)
    public = e.documents.proposals._public(row)
    assert public["status"] == "MODEL_UNAVAILABLE"
    assert public["model_preview"] is None and public["model_execution"] is None
    assert TEXT not in json.dumps(public)


@pytest.mark.parametrize("change", ["durable_output", "durable_status", "ledger_job", "ledger_actor", "ledger_digest", "ledger_status", "ledger_cost"])
def test_private_result_requires_exact_durable_job_and_settled_ledger(lifecycle, change):
    e = lifecycle; _, _, job = run(e)
    if change.startswith("durable_"):
        saved = e.persistence.get(job.id)
        if change == "durable_output": saved["output"] = "different durable output"
        else: saved["status"] = "FAILED"
        e.persistence.save(saved)
    else:
        with e.raw.transaction(e.nid, e.scope) as state:
            accounting = next(iter(state["collections"][e.broker.LEDGER].values()))
            key, value = {"ledger_job": ("job_id", "different-job"), "ledger_actor": ("created_by", "other"),
                "ledger_digest": ("authorization_digest", "f" * 64), "ledger_status": ("status", "UNKNOWN_UPSTREAM"),
                "ledger_cost": ("actual_microusd", 1)}[change]
            accounting[key] = value
    with pytest.raises(DENIALS): result(e)
    assert len(e.requests) == 1
    assert_hidden(e, job)


def test_successful_internal_result_remains_unavailable_to_public_proposal_review(lifecycle):
    e = lifecycle; prepared, _, job = run(e)
    client, base = public_client(e, "/api")
    headers = {"X-Session-Token": e.token}
    current = raw_proposal(e)
    for suffix in ("", "/" + e.row["id"]):
        response = client.get(base + suffix, headers=headers)
        assert response.status_code == 200
        encoded = json.dumps(response.json(), ensure_ascii=False)
        assert TEXT not in encoded and prepared["model_preview"]["prompt"] not in encoded
        assert CONTRACT not in encoded
    response = client.post(base + "/" + e.row["id"] + "/review", headers=headers, json={
        "expected_version": current["version"], "reviewed_output_digest": e.row["output_digest"],
        "title": e.row["title"], "director_notes": e.row["director_notes"]})
    assert response.status_code in {400, 403, 404, 409, 422}
    assert len(e.documents.list(e.nid, e.scope)) == 1
    assert raw_proposal(e)["document_id"] is None
    assert job.status == "COMPLETED" and result(e)["text"] == TEXT


def test_real_deadline_elapsed_during_wire_discards_late_completion(lifecycle, monkeypatch):
    from app.creative import generation
    e = lifecycle
    monkeypatch.setattr(generation, "TIMEOUT_SECONDS", 1)
    entered = []
    def expire():
        entered.append(1)
        Event().wait(1.05)  # Actual elapsed time, no clock/deadline rewrite.
    e.wire_hook = expire
    _, _, job = run(e)
    assert entered == [1] and len(e.requests) == 1
    assert job.status == "FAILED" and not job.output
    assert job.error_code == "GENERATION_DEADLINE_EXCEEDED"
    with pytest.raises(DENIALS): result(e)


def test_utf8_byte_limit_cannot_be_replaced_by_character_count(lifecycle):
    e = lifecycle; prepared = preview(e)
    bound = prepared["model_preview"]["max_output_bytes"]
    e.wire_text = "界" * (bound // 2)
    assert len(e.wire_text) < bound < len(e.wire_text.encode("utf-8"))
    receipt = dispatch(e, prepared)
    job = wait(e, e.manager.get(receipt["model_execution"]["job_id"]))
    assert job.status == "FAILED" and not job.output and len(e.requests) == 1
    assert job.error_code == "GENERATION_OUTPUT_LIMIT"
    with pytest.raises(DENIALS): result(e)


@pytest.mark.parametrize("when", ["before_dispatch", "during_wire"])
def test_same_fingerprint_registered_adapter_replacement_is_detected(lifecycle, monkeypatch, when):
    from app.model_center.discovery_bridge import LocalTextAdapter
    e = lifecycle; prepared = preview(e); previous = deepcopy(e.route); changed = []
    def replace_adapter():
        replacement = LocalTextAdapter(e.adapter.bridge, e.candidate)
        replacement.client = e.adapter.client
        monkeypatch.setattr(replacement, "health_check", ForbiddenOwner())
        descriptor = next(item for item in e.runtime.provider_registry.descriptors()
                          if item.provider_id == e.candidate["provider_id"])
        e.runtime.provider_registry.register(descriptor, replacement, replace=True)
        current = e.broker.current_route(previous["route_id"], local_text_only=True)
        assert current["fingerprint"] == previous["fingerprint"]
        assert current["binding_hash"] != previous["binding_hash"]
        changed.append(1)
    if when == "before_dispatch":
        replace_adapter()
        with pytest.raises(DENIALS): dispatch(e, prepared)
        assert not e.requests and not e.manager.jobs
    else:
        e.wire_hook = replace_adapter
        try: receipt = dispatch(e, prepared)
        except DENIALS:
            assert len(e.manager.jobs) == 1
            receipt = raw_proposal(e)
        job = wait(e, e.manager.get(receipt["model_execution"]["job_id"]))
        assert job.status == "FAILED" and not job.output and len(e.requests) == 1
        with pytest.raises(DENIALS): result(e)
    assert changed == [1]


def test_new_invocation_adapter_cannot_ride_identical_route_and_binding_hash(lifecycle, monkeypatch):
    from app.model_execution import LocalModelInvocation
    e = lifecycle; prepared = preview(e); previous = deepcopy(e.route)
    def replace_adapter(job):
        adapter = LocalModelInvocation(e.runtime, e.candidate["provider_id"], e.candidate["id"], synthetic_allowed=False)
        assert adapter is not job.prepared_text_invocation.adapter
        current = e.broker.current_route(previous["route_id"], local_text_only=True)
        assert current["fingerprint"] == previous["fingerprint"]
        assert current["binding_hash"] == previous["binding_hash"]
        job.prepared_text_invocation = replace(job.prepared_text_invocation, adapter=adapter)
    capture_start(e, monkeypatch, replace_adapter)
    with pytest.raises(DENIALS): dispatch(e, prepared)
    assert not e.requests and len(ledger(e)) == 1
    assert raw_proposal(e)["model_execution"]["status"] == "UNKNOWN"


@pytest.mark.parametrize("field,value", [("reservation_id", "wrong-reservation"), ("receipt_state", "UNKNOWN_NO_AUTOMATIC_REPLAY"),
    ("request_digest", "f" * 64), ("job_id", "wrong-job"), ("version", 100)])
def test_queued_receipt_mutation_during_wire_suppresses_worker_output(lifecycle, field, value):
    e = lifecycle
    def mutate():
        with e.raw.transaction(e.nid, e.scope) as state:
            row = state["collections"][e.documents.proposals.COLLECTION][e.row["id"]]
            if field == "version": row["version"] = value
            else: row["model_execution"][field] = value
    e.wire_hook = mutate
    # Return-response authorization may also reject the mutated receipt; the
    # registered original job remains the worker being awaited.
    prepared = preview(e)
    try: dispatch(e, prepared)
    except DENIALS: pass
    assert len(e.manager.jobs) == 1
    job = wait(e, next(iter(e.manager.jobs.values())))
    assert job.status == "FAILED" and not job.output and len(e.requests) == 1
    assert len(ledger(e)) == 1
    with pytest.raises(DENIALS): result(e)


@pytest.mark.parametrize("boundary", ["wire", "after_settlement"])
@pytest.mark.parametrize("recreate", [False, True])
def test_owner_loss_after_admission_never_publishes_or_adopts_replacement(lifecycle, monkeypatch, boundary, recreate):
    e = lifecycle; original = e.broker.finalize; changes = []
    def remove_owner():
        e.novels.delete(e.nid)
        if recreate:
            e.novels.create({"id": e.nid, "title": "New owner under same public slug"})
            assert e.documents.store.incarnation(e.nid) != e.source["project_incarnation"]
        changes.append(1)
    if boundary == "wire": e.wire_hook = remove_owner
    else:
        def finalize(*args, **kwargs):
            accounting = original(*args, **kwargs)
            remove_owner()
            return accounting
        monkeypatch.setattr(e.broker, "finalize", finalize)
    prepared = preview(e)
    try: dispatch(e, prepared)
    except DENIALS: pass
    assert len(e.manager.jobs) == 1
    job = wait(e, next(iter(e.manager.jobs.values())))
    assert changes == [1] and len(e.requests) == 1
    assert job.status == "FAILED" and not job.output
    with pytest.raises(DENIALS): result(e)
    assert not generation_content_available(job)
    assert job.id not in {row["id"] for row in e.persistence.load_all()}
    if not recreate: assert not (e.root / "novels" / e.nid).exists()


def test_actual_deadline_elapsed_during_settlement_blocks_terminal_publication(lifecycle, monkeypatch):
    from app.creative import generation
    e = lifecycle; original = e.broker.finalize; settled = []
    monkeypatch.setattr(generation, "TIMEOUT_SECONDS", 1)
    def finalize(*args, **kwargs):
        job = next(iter(e.manager.jobs.values()))
        assert datetime.now(timezone.utc) < datetime.fromisoformat(job.generation_deadline)
        assert job.execution_outcome == "COMPLETED" and job.output == TEXT and len(e.requests) == 1
        accounting = original(*args, **kwargs)
        assert accounting["status"] == "SETTLED" and accounting["job_status"] == "COMPLETED"
        settled.append(1)
        Event().wait(1.05)  # Broker completed, but the original deadline expires.
        return accounting
    monkeypatch.setattr(e.broker, "finalize", finalize)
    _, _, job = run(e)
    assert settled == [1] and len(e.requests) == 1
    assert job.status == "FAILED" and not job.output
    assert ledger(e)[0]["status"] == "SETTLED"
    assert e.persistence.get(job.id)["status"] != "COMPLETED"
    with pytest.raises(DENIALS): result(e)


@pytest.mark.filterwarnings("error::pytest.PytestUnhandledThreadExceptionWarning")
def test_continuous_storage_failure_after_dispatch_suppresses_output_and_settles_once(lifecycle, monkeypatch):
    e = lifecycle; original_save = e.persistence.save; original_finalize = e.broker.finalize
    failing, failures, settled = [], [], []
    def save(value):
        if failing:
            failures.append(value["status"])
            raise OSError("continuous original generation storage failure")
        return original_save(value)
    def finalize(*args, **kwargs):
        settled.append(1)
        return original_finalize(*args, **kwargs)
    monkeypatch.setattr(e.persistence, "save", save)
    monkeypatch.setattr(e.broker, "finalize", finalize)
    e.wire_hook = lambda: failing.append(True)
    _, _, job = run(e)
    assert failures and len(failures) >= 2
    assert len(e.requests) == 1 and settled == [1]
    assert job.status in {"FAILED", "CANCELLED"} and not job.output
    assert "RECONCILIATION_REQUIRED" in job.terminal_hook_status
    assert e.persistence.get(job.id)["status"] != "COMPLETED"
    with pytest.raises(DENIALS): result(e)
    assert_hidden(e, job)
