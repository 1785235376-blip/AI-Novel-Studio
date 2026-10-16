"""Director checkpoints reuse original leases, but never cache live authority.

These checks exercise original File and real PostgreSQL owners. Synthetic
transport tests retain the original broker's five-second settlement assertion.
"""
import copy
import json
from threading import Event, get_ident
from types import SimpleNamespace

import pytest

from test_v2_creative_foundation import rig, payload, public
from test_r3_mounted_contracts import mounted, prefix, checked, scoped
from test_v2_creative_workflows import (
    broker_app, creative_model, model_ready, model_dispatch, model_settle, model_action, route, review_body,
)
from test_v2_director_storyboard_production import target, rich_note


def coordinator(rig):
    from app.creative.generation import DirectorModelCoordinator
    return DirectorModelCoordinator(rig.service.proposals, None, None, None)


def context(rig):
    return SimpleNamespace(novel_id=rig.nid, scope=rig.scope, actor=rig.actor)


def test_checkpoint_coalesces_real_reads_but_next_checkpoint_observes_edits(rig, monkeypatch):
    source = rig.service.create(rig.nid, rig.scope, rig.actor, payload(rig))
    proposal = rig.service.proposals.create(rig.nid, rig.scope, rig.actor,
        {"source_document_id": source["id"], "expected_source_version": 1})
    before = rig.store.read(rig.nid, rig.scope)
    real_connect, calls = rig.store._connect, []
    def counted():
        calls.append(get_ident())
        return real_connect()
    monkeypatch.setattr(rig.store, "_connect", counted)
    owner = coordinator(rig)
    with owner._authority_read(context(rig)):
        for _ in range(8):
            assert rig.service.get(rig.nid, rig.scope, source["id"]) == source
            assert rig.service.proposals._current(rig.nid, rig.scope, proposal) == source
            detached = rig.service.store.read(rig.nid, rig.scope)
            detached["collections"][rig.service.COLLECTION][source["id"]]["title"] = "Detached reader edit"
            assert rig.store.read(rig.nid, rig.scope) == before
    # Raw source snapshot, brief incarnation probe, and held original owner.
    # Additional nested reads never create additional PostgreSQL connections.
    assert len(calls) == (3 if rig.backend == "postgres" else 0)
    assert rig.store.read(rig.nid, rig.scope) == before
    rig.service.update(rig.nid, rig.scope, rig.actor, source["id"], 1, public(source))
    from app.experimental.common import StaleSourceError
    with owner._authority_read(context(rig)):
        with pytest.raises(StaleSourceError, match="PROPOSAL_SOURCE_CHANGED"):
            rig.service.proposals._current(rig.nid, rig.scope, proposal)


@pytest.mark.parametrize("kind", ["raw", "creative"])
def test_checkpoint_reuses_explicit_original_transactions_without_nested_lease(rig, monkeypatch, kind):
    source = rig.service.create(rig.nid, rig.scope, rig.actor, payload(rig))
    owner = coordinator(rig)
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Do not open a nested raw source lease")
    monkeypatch.setattr(rig.service.store, "source_lease", forbidden)
    transaction = rig.store.transaction if kind == "raw" else rig.service.store.transaction
    with transaction(rig.nid, rig.scope):
        with owner._authority_read(context(rig)):
            assert rig.service.get(rig.nid, rig.scope, source["id"]) == source
    assert rig.service.get(rig.nid, rig.scope, source["id"]) == source


def test_checkpoint_rejects_project_before_scope_lock_order(rig):
    owner = coordinator(rig)
    with rig.service.store.owner_lease(rig.nid):
        with pytest.raises(ValueError, match="SOURCE_LEASE_NESTED_OR_ORDER_INVALID"):
            with owner._authority_read(context(rig)):
                pytest.fail("Scope must not be acquired beneath a project owner")


def test_read_checkpoint_cannot_commit_source_mutation(rig):
    source = rig.service.create(rig.nid, rig.scope, rig.actor, payload(rig))
    before = rig.store.read(rig.nid, rig.scope)
    key = rig.store.key(rig.nid, rig.scope)
    with pytest.raises(ValueError, match="SOURCE_LEASE_MUTATION_DENIED"):
        with coordinator(rig)._authority_read(context(rig)):
            # A programming error inside a trusted callback must still rollback.
            rig.store._local.active[key]["collections"][rig.service.COLLECTION][source["id"]]["title"] = "Invalid write"
    assert rig.store.read(rig.nid, rig.scope) == before


def test_live_original_guard_uses_bounded_reads_and_observes_revocation(creative_model, monkeypatch):
    from fastapi import HTTPException
    from app.runtime import runtime
    e = creative_model
    source, preview, _ = model_ready(e, monkeypatch)
    entered, release = Event(), Event()
    def delayed(_prompt, _model, **_kwargs):
        entered.set()
        assert release.wait(10)
        yield '{"director_notes": []}'
    monkeypatch.setattr(runtime.providers["mock"], "stream", delayed)
    try:
        running = model_dispatch(e, preview)
        assert entered.wait(5)
        job = e.manager.get(running["model_execution"]["job_id"])
        raw = e.creative.store.store
        original, calls, caller = raw._connect, [], get_ident()
        def counted():
            if get_ident() == caller:
                calls.append(1)
            return original()
        monkeypatch.setattr(raw, "_connect", counted)
        job.request_authorization()
        assert len(calls) == (3 if e.config.storage_backend == "postgres" else 0)
        assert e.creative.get(e.nid, source["scope"], source["id"]) == source
        before = copy.deepcopy(e.chapters.get(e.chapter["id"]))
        e.sessions.revoke("broker-host")
        calls.clear()
        with pytest.raises(HTTPException) as denied:
            # Exact original Host/session authorizer is re-run; it cannot use
            # the previous checkpoint's permission or source snapshot.
            job.request_authorization()
        assert denied.value.status_code == 401
        assert not calls
        assert e.chapters.get(e.chapter["id"]) == before
    finally:
        release.set()


def test_original_visual_goal_settles_within_unchanged_deadline(creative_model, monkeypatch, tmp_path):
    """Regression for the two previous PostgreSQL alias failures, with timing."""
    from app.runtime import runtime
    e = creative_model
    calls = []
    def stream(_prompt, _model, **_kwargs):
        calls.append(1)
        yield json.dumps({"director_notes": [rich_note()]})
    monkeypatch.setattr(runtime.providers["mock"], "stream", stream)
    source = checked(e.client.post(e.creative_base + "/documents", headers=e.headers, json={
        "mode": "SCREENPLAY", "title": "Synthetic timing source", "source_chapter_ids": [e.chapter["id"]],
        "scenes": [{"id": "scene-1", "sequence": 1, "heading": "ROOM", "action": "Visitor pauses."}]}), 201)
    row = checked(e.client.post(e.creative_base + "/director-proposals", headers=e.headers, json={
        "source_document_id": source["id"], "expected_source_version": 1, "visual_target": target()}), 201)
    preview = model_action(e, row, "preview", route_id=route(e)["route_id"])
    running = model_dispatch(e, preview)
    result = model_settle(e, running)  # Original five-second wait_ledger unchanged.
    job = e.manager.get(running["model_execution"]["job_id"])
    proof = {"prefix": e.prefix, "backend": e.config.storage_backend,
             "author_latency_ms": job.latency_ms, "original_ledger_deadline_ms": 5000,
             "job_status": job.status, "terminal_hook_status": job.terminal_hook_status,
             "proposal_status": result["status"], "synthetic_transport_calls": len(calls)}
    (tmp_path / "settlement-timing.private.json").write_text(json.dumps(proof, indent=2), encoding="utf-8")
    assert job.status == "COMPLETED" and job.terminal_hook_status == "COMPLETED"
    assert job.latency_ms < 5000 and calls == [1]
    assert result["status"] == "NEEDS_REVIEW"
    adopted = checked(e.client.post(e.creative_base + f'/director-proposals/{row["id"]}/review',
        headers=e.headers, json=review_body(result)))["document"]
    assert adopted["visual_target"] == target()
