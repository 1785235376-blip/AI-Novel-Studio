"""Candidate-only lifecycle checks over original File owners.

No public transport, provider network or independent acceptance is implied.
"""
from copy import deepcopy
import json
from threading import Event

import pytest

from creative_director_execution_fixture import lifecycle, raw_proposal, wait
from test_director_durable_pending_review import publish, prepare, review, restart, fresh_host, DENIALS
from test_v2_independent_director_adoption import board, review_body, raw_bytes, output, preview

pytestmark = pytest.mark.file_backend_only


def status(e):
    return e.coordinator._read_independent_status(
        e.ctx, e.row["id"], e.guard, host_authority=e.authority)


def adopted(e):
    return e.coordinator._read_independent_adopted(
        e.ctx, e.row["id"], e.guard, host_authority=e.authority)


def reconcile(e, body):
    return e.coordinator._reconcile_independent_review(
        e.ctx, e.row["id"], body, e.guard, host_authority=e.authority)


def test_preview_observation_does_not_admit_a_job_or_reservation(lifecycle):
    e = board(lifecycle)
    prepared = preview(e)
    before = raw_bytes(e)
    receipt = status(e)
    assert receipt["phase"] == "PREVIEW"
    assert receipt["reviewed_preview_digest"] == prepared["model_preview"]["preview_digest"]
    assert receipt["job_id"] is None and receipt["adoption"] is None
    assert receipt["dispatch_state"] == "NOT_DISPATCHED"
    assert receipt["settlement_state"] == "NOT_APPLICABLE"
    assert raw_bytes(e) == before
    assert e.persistence.load_all() == [] and e.requests == []
    assert e.broker.ledger(e.nid, e.scope, e.actor) == []


def test_status_and_exact_adoption_receipt_survive_fresh_host_restart(lifecycle):
    e = board(lifecycle)
    job, body = publish(e)
    before = raw_bytes(e)
    completed = status(e)
    assert completed["phase"] == "COMPLETED"
    assert completed["terminal_evidence_digest"] == body["terminal_evidence_digest"]
    assert completed["automatic_retry"] is False
    assert e.wire_text not in json.dumps(completed)
    assert raw_bytes(e) == before
    candidate = prepare(e, body)
    assert status(e)["phase"] == "PENDING_REVIEW"
    human = review_body(candidate)
    human["director_notes"][0]["note"] = "Explicit reviewed direction for receipt validation."
    result = review(e, human)
    assert result["proposal"]["status"] == "MODEL_UNAVAILABLE"
    assert raw_proposal(e)["status"] == "APPROVED"
    receipt = adopted(e)
    assert receipt["document"]["document_id"] == result["document"]["id"]
    assert receipt["document"]["status"] == "DRAFT"
    assert receipt["document"]["digest"] == e.documents.document_digest(result["document"])
    assert status(e)["adoption"] == receipt
    before = raw_bytes(e)
    assert reconcile(e, human) == receipt
    assert raw_bytes(e) == before
    restart(e)
    fresh_host(e)
    before = raw_bytes(e)
    assert adopted(e) == reconcile(e, human) == receipt
    assert status(e)["phase"] == "ADOPTED_DRAFT"
    assert raw_bytes(e) == before
    assert len(e.requests) == 1
    assert len(e.persistence.load_all()) == 1
    assert e.persistence.get(job.id)["id"] == job.id


@pytest.mark.parametrize("field", ["title", "note", "version", "digest"])
def test_reconciliation_requires_exact_submitted_review_without_mutation(lifecycle, field):
    e = board(lifecycle)
    _, body = publish(e)
    candidate = prepare(e, body)
    human = review_body(candidate)
    review(e, human)
    changed = deepcopy(human)
    if field == "title":
        changed["title"] += " different"
    elif field == "note":
        changed["director_notes"][0]["note"] += " different"
    elif field == "version":
        changed["expected_version"] += 1
    else:
        changed["reviewed_output_digest"] = "0" * 64
    before = raw_bytes(e)
    with pytest.raises(DENIALS):
        reconcile(e, changed)
    assert raw_bytes(e) == before
    assert len(e.requests) == 1


@pytest.mark.parametrize("operation", ["status", "adopted", "reconcile"])
def test_current_authority_is_required_for_every_passive_receipt(lifecycle, operation):
    e = board(lifecycle)
    _, body = publish(e)
    candidate = prepare(e, body)
    human = review_body(candidate)
    review(e, human)
    e.active = False
    before = raw_bytes(e)
    with pytest.raises(DENIALS):
        if operation == "status":
            status(e)
        elif operation == "adopted":
            adopted(e)
        else:
            reconcile(e, human)
    assert raw_bytes(e) == before


def test_completed_passive_job_cannot_be_cancelled(lifecycle):
    e = board(lifecycle)
    job, _ = publish(e)
    restart(e)
    fresh_host(e)
    row = raw_proposal(e)
    before = raw_bytes(e)
    with pytest.raises(DENIALS):
        e.coordinator._cancel_independent(e.ctx, e.row["id"], {
            "expected_version": row["version"], "job_id": job.id,
            "request_digest": row["model_execution"]["request_digest"],
            "reviewed_preview_digest": row["model_preview"]["preview_digest"],
        }, e.guard, host_authority=e.authority)
    assert raw_bytes(e) == before
    assert e.persistence.get(job.id)["status"] == "COMPLETED"


def test_live_cancellation_only_signals_then_original_worker_settles(lifecycle):
    e = board(lifecycle)
    entered, release = Event(), Event()
    e.wire_text = json.dumps(output(e))

    def hold_wire():
        entered.set()
        assert release.wait(10), "test must release the original adapter wire"

    e.wire_hook = hold_wire
    prepared = preview(e)
    try:
        e.coordinator._dispatch_independent(e.ctx, e.row["id"], {
            "expected_version": prepared["version"],
            "reviewed_preview_digest": prepared["model_preview"]["preview_digest"],
        }, e.guard, host_authority=e.authority, terminal_evidence=True)
        assert entered.wait(5)
        row = raw_proposal(e)
        job = e.manager.get(row["model_execution"]["job_id"])
        body = {"expected_version": row["version"], "job_id": job.id,
            "request_digest": row["model_execution"]["request_digest"],
            "reviewed_preview_digest": row["model_preview"]["preview_digest"]}
        before = raw_bytes(e)
        with pytest.raises(DENIALS):
            e.coordinator._cancel_independent(e.ctx, e.row["id"], {
                **body, "job_id": "not-the-owned-job",
            }, e.guard, host_authority=e.authority)
        assert not job.cancelled.is_set()
        result = e.coordinator._cancel_independent(
            e.ctx, e.row["id"], body, e.guard, host_authority=e.authority)
        assert result["cancellation_requested"] is True
        assert result["cancellation_confirmed"] is False
        assert job.cancelled.is_set()
        assert e.persistence.get(job.id)["status"] not in {"CANCELLED", "COMPLETED"}
        assert raw_bytes(e) == before
        repeated = e.coordinator._cancel_independent(
            e.ctx, e.row["id"], body, e.guard, host_authority=e.authority)
        assert repeated["cancellation_requested"] is True
        assert raw_bytes(e) == before
    finally:
        release.set()
    assert wait(e, job).status == "CANCELLED"
    final = status(e)
    assert final["phase"] == "CANCELLED"
    # The original broker cannot prove the interrupted upstream usage. Do not
    # turn a local cooperative stop into a fabricated settlement guarantee.
    assert final["cancellation_confirmed"] is False
    assert final["settlement_state"] == "UNKNOWN_UPSTREAM"
    assert final["dispatch_state"] == "DISPATCHED"
    assert final["upstream_cancellation_guaranteed"] is False
    ledger = e.broker.ledger(e.nid, e.scope, e.actor)
    assert len(ledger) == 1 and ledger[0]["actual_microusd"] is None
    assert not job.output
    assert len(e.requests) == 1


def test_explicit_queued_cancel_releases_original_reservation_without_dispatch(lifecycle, monkeypatch):
    e = board(lifecycle)
    entered, release = Event(), Event()
    original = e.manager._run

    def delayed_original_worker(job):
        entered.set()
        assert release.wait(10)
        original(job)

    monkeypatch.setattr(e.manager, "_run", delayed_original_worker)
    prepared = preview(e)
    try:
        e.coordinator._dispatch_independent(e.ctx, e.row["id"], {
            "expected_version": prepared["version"],
            "reviewed_preview_digest": prepared["model_preview"]["preview_digest"],
        }, e.guard, host_authority=e.authority, terminal_evidence=True)
        assert entered.wait(5)
        row = raw_proposal(e)
        job = e.manager.get(row["model_execution"]["job_id"])
        admitted = status(e)
        assert admitted["phase"] == "ADMITTED"
        assert admitted["dispatch_state"] == "NOT_DISPATCHED"
        body = {"expected_version": row["version"], "job_id": job.id,
            "request_digest": row["model_execution"]["request_digest"],
            "reviewed_preview_digest": row["model_preview"]["preview_digest"]}
        e.active = False
        with pytest.raises(DENIALS):
            e.coordinator._cancel_independent(e.ctx, e.row["id"], body, e.guard, host_authority=e.authority)
        assert not job.cancelled.is_set()
        e.active = True
        receipt = e.coordinator._cancel_independent(
            e.ctx, e.row["id"], body, e.guard, host_authority=e.authority)
        assert receipt["cancellation_requested"] is True
        assert receipt["cancellation_confirmed"] is False
    finally:
        release.set()
    assert wait(e, job).status == "CANCELLED"
    final = status(e)
    assert final["cancellation_confirmed"] is True
    assert final["settlement_state"] == "RELEASED"
    assert final["dispatch_state"] == "NOT_DISPATCHED"
    assert final["upstream_cancellation_guaranteed"] is False
    assert e.requests == []
    ledger = e.broker.ledger(e.nid, e.scope, e.actor)
    assert len(ledger) == 1 and ledger[0]["actual_microusd"] == 0


@pytest.mark.parametrize("operation", ["status", "adopted", "reconcile"])
def test_late_job_change_is_rejected_before_passive_receipt_returns(lifecycle, monkeypatch, operation):
    e = board(lifecycle)
    job, body = publish(e)
    candidate = prepare(e, body)
    human = review_body(candidate)
    review(e, human)
    original = e.coordinator._pending_current
    calls = 0

    def change_after_final_guard(*args, **kwargs):
        nonlocal calls
        result = original(*args, **kwargs)
        if args[1]["status"] == "APPROVED":
            calls += 1
            if calls == 2:
                saved = e.persistence.get(job.id)
                saved.update(status="FAILED", output="")
                e.persistence.save(saved)
        return result

    monkeypatch.setattr(e.coordinator, "_pending_current", change_after_final_guard)
    before = raw_bytes(e)
    with pytest.raises(ValueError, match="CREATIVE_DIRECTOR_LIFECYCLE_OBSERVATION_CHANGED"):
        if operation == "status":
            status(e)
        elif operation == "adopted":
            adopted(e)
        else:
            reconcile(e, human)
    assert calls >= 2
    assert raw_bytes(e) == before


def test_late_job_change_rolls_back_review_without_creating_a_second_draft(lifecycle, monkeypatch):
    e = board(lifecycle)
    job, body = publish(e)
    candidate = prepare(e, body)
    original = e.coordinator._pending_current
    calls = 0

    def change_after_final_guard(*args, **kwargs):
        nonlocal calls
        result = original(*args, **kwargs)
        if args[1]["status"] == "APPROVED":
            calls += 1
            if calls == 2:
                saved = e.persistence.get(job.id)
                saved.update(status="FAILED", output="")
                e.persistence.save(saved)
        return result

    monkeypatch.setattr(e.coordinator, "_pending_current", change_after_final_guard)
    before = raw_bytes(e)
    with pytest.raises(ValueError, match="CREATIVE_DIRECTOR_PENDING_OUTPUT_CHANGED"):
        review(e, review_body(candidate))
    assert calls == 2
    assert raw_bytes(e) == before
    assert raw_proposal(e)["document_id"] is None


@pytest.mark.parametrize("after_replace", [False, True])
def test_uncertain_review_is_reconciled_exactly_without_repeating_adoption(lifecycle, monkeypatch, after_replace):
    import app.experimental.store as store
    e = board(lifecycle)
    _, body = publish(e)
    candidate = prepare(e, body)
    human = review_body(candidate)
    before = raw_bytes(e)
    old_documents = set(e.raw.read(e.nid, e.scope)["collections"][e.documents.COLLECTION])
    original = store.atomic_write

    def broken(*args, **kwargs):
        if after_replace:
            original(*args, **kwargs)
        raise OSError("injected review publication uncertainty")

    monkeypatch.setattr(store, "atomic_write", broken)
    with pytest.raises(OSError):
        review(e, human)
    monkeypatch.setattr(store, "atomic_write", original)
    if after_replace:
        committed = raw_bytes(e)
        receipt = reconcile(e, human)
        assert reconcile(e, human) == receipt
        assert raw_bytes(e) == committed
        assert receipt["approved_version"] == candidate["expected_version"] + 1
        documents = set(e.raw.read(e.nid, e.scope)["collections"][e.documents.COLLECTION])
        assert documents - old_documents == {receipt["document"]["document_id"]}
        assert raw_proposal(e)["document_id"] == receipt["document"]["document_id"]
    else:
        assert raw_bytes(e) == before
        with pytest.raises(DENIALS):
            reconcile(e, human)
        assert raw_bytes(e) == before
        assert raw_proposal(e)["document_id"] is None
    assert len(e.requests) == 1


def test_persisted_signal_flag_does_not_restore_cancellation_authority(lifecycle):
    e = board(lifecycle)
    job, _ = publish(e)
    path = e.persistence.repository._job_path(job.id)
    saved = json.loads(path.read_text())
    saved["creative_director_cancel_requested"] = True
    path.write_text(json.dumps(saved))  # Unsupported hostile persisted data.
    restart(e)
    fresh_host(e)
    restored = e.manager.get(job.id)
    assert restored.creative_director_cancel_requested is False
    assert restored.creative_execution_authority is None
    before = path.read_bytes()
    with pytest.raises(ValueError, match="CREATIVE_DIRECTOR_CANCEL_LIVE_OWNER_REQUIRED"):
        e.manager._request_creative_director_cancellation(restored)
    assert path.read_bytes() == before
    assert status(e)["cancellation_requested"] is False


def test_cooperative_cancel_arriving_inside_bounds_check_keeps_cancel_classification(lifecycle, monkeypatch):
    import app.jobs as jobs
    from app.model_runtime import ModelRuntimeError, RuntimeErrorCode
    e = board(lifecycle)
    entered, release = Event(), Event()
    original_worker = e.manager._run
    original_current = jobs._creative_execution_current

    def delayed_original_worker(job):
        entered.set()
        assert release.wait(10)
        original_worker(job)

    monkeypatch.setattr(e.manager, "_run", delayed_original_worker)
    prepared = preview(e)
    try:
        e.coordinator._dispatch_independent(e.ctx, e.row["id"], {
            "expected_version": prepared["version"],
            "reviewed_preview_digest": prepared["model_preview"]["preview_digest"],
        }, e.guard, host_authority=e.authority, terminal_evidence=True)
        assert entered.wait(5)
        row = raw_proposal(e)
        job = e.manager.get(row["model_execution"]["job_id"])
        body = {"expected_version": row["version"], "job_id": job.id,
            "request_digest": row["model_execution"]["request_digest"],
            "reviewed_preview_digest": row["model_preview"]["preview_digest"]}
        calls = []

        def cancel_at_current_boundary(current):
            assert current is job
            calls.append(current.id)
            e.coordinator._cancel_independent(
                e.ctx, e.row["id"], body, e.guard, host_authority=e.authority)
            return original_current(current)

        monkeypatch.setattr(jobs, "_creative_execution_current", cancel_at_current_boundary)
        with pytest.raises(ModelRuntimeError) as caught:
            jobs.check_generation_bounds(job)
        assert caught.value.code == RuntimeErrorCode.CANCELLED
        assert calls == [job.id]
        assert job.generation_bound_failure is None
        monkeypatch.setattr(jobs, "_creative_execution_current", original_current)
    finally:
        release.set()
    assert wait(e, job).status == "CANCELLED"
    assert status(e)["cancellation_confirmed"] is True
    assert e.requests == []
