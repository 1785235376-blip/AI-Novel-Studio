"""Explicit private historical result → original pending proposal → reviewed DRAFT.

Original File owners, mocked adapter wire, no provider/network or public activation.
Run only via the original V2 runner after parent grants a serialized test slot.
"""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
import json

import pytest
from fastapi import HTTPException

from creative_director_execution_fixture import lifecycle, raw_proposal, wait
from test_v2_independent_director_adoption import board, output, preview, review_body, raw_bytes
from app.creative.director_terminal_evidence import FIELD, PENDING_FIELD, digest
from app.services.v1_capability_service import CapabilityVersionConflict

pytestmark = pytest.mark.file_backend_only
DENIALS = (ValueError, HTTPException, PermissionError, FileNotFoundError, KeyError, CapabilityVersionConflict)


def publish(e, *, schema=True, evidence=True):
    from creative_director_execution_fixture import preview as old_preview
    e.wire_text = json.dumps(output(e))
    prepared = preview(e) if schema else old_preview(e)
    receipt = e.coordinator._dispatch_independent(e.ctx, e.row["id"], {
        "expected_version": prepared["version"], "reviewed_preview_digest": prepared["model_preview"]["preview_digest"]},
        e.guard, host_authority=e.authority, terminal_evidence=evidence)
    job = wait(e, e.manager.get(receipt["model_execution"]["job_id"]))
    assert job.status == "COMPLETED"
    body = {"expected_version": raw_proposal(e)["version"],
        "terminal_evidence_digest": digest(e.persistence.get(job.id).get(FIELD))}
    return job, body


def prepare(e, body):
    return e.coordinator._prepare_independent_pending_review(e.ctx, e.row["id"], body, e.guard, host_authority=e.authority)


def read(e):
    return e.coordinator._read_independent_pending_review(e.ctx, e.row["id"], e.guard, host_authority=e.authority)


def review(e, body):
    return e.coordinator._review_independent_pending(e.ctx, e.row["id"], body, e.guard, host_authority=e.authority)


def restart(e):
    from app.jobs import JobManager
    from app.creative.service import CreativeService
    from app.creative.generation import DirectorModelCoordinator
    from app.experimental.store import ExperimentalStore
    e.raw = ExperimentalStore(e.root, "file", "")
    e.documents = CreativeService(e.raw, e.novels, e.forbidden)
    e.broker.store = e.raw
    e.manager = JobManager(e.persistence, e.forbidden, e.forbidden, e.forbidden,
        memory_extractor=e.forbidden, snapshot_required=True, collaboration_updates=e.forbidden)
    e.coordinator = DirectorModelCoordinator(e.documents.proposals, e.broker, e.forbidden, e.manager)
    e.documents.proposals.generation = e.coordinator


def fresh_host(e):
    from starlette.requests import Request
    from app.model_center.discovery_authority import resolve_discovery_authority
    e.sessions.revoke(e.token); e.sessions.register(e.token, e.session)
    request = Request({"type": "http", "method": "POST", "scheme": "http", "path": "/private",
        "headers": [], "client": ("127.0.0.1", 41000), "server": ("127.0.0.1", 8000), "query_string": b""})
    old = e.authority
    e.authority = resolve_discovery_authority(request, e.token, settings_getter=lambda: e.host_settings,
        resolver_getter=lambda: e.sessions, bootstrap_getter=lambda: None)
    assert e.authority.principal != old.principal
    with pytest.raises(HTTPException): old.guard()


def test_expired_restart_fresh_host_pending_clear_review_draft_reopen(lifecycle, monkeypatch):
    import app.jobs as jobs
    import app.creative.generation as generation
    e = board(lifecycle); job, body = publish(e)
    class Expired(datetime):
        @classmethod
        def now(cls, tz=None): return datetime.fromisoformat(job.generation_deadline) + timedelta(seconds=1)
    monkeypatch.setattr(jobs, "datetime", Expired)
    monkeypatch.setattr(generation, "datetime", Expired)
    with pytest.raises(DENIALS):
        e.coordinator._read_independent_candidates(e.ctx, e.row["id"], e.guard, host_authority=e.authority)
    restart(e); fresh_host(e)
    before = e.raw.read(e.nid, e.scope)
    candidate = prepare(e, body)
    pending_row = raw_proposal(e)
    assert pending_row["version"] == body["expected_version"] + 1
    assert datetime.fromisoformat(pending_row[PENDING_FIELD]["published_at"]) > datetime.fromisoformat(job.generation_deadline)
    assert len(pending_row["history"]) == len(before["collections"][e.documents.proposals.COLLECTION][e.row["id"]]["history"]) + 1
    assert pending_row["status"] == "INTERNAL_MODEL_PENDING_REVIEW" and pending_row["document_id"] is None
    assert pending_row[PENDING_FIELD]["terminal_evidence_digest"] == body["terminal_evidence_digest"]
    assert "output" not in pending_row[PENDING_FIELD] and e.wire_text not in json.dumps(pending_row[PENDING_FIELD])
    saved = e.persistence.get(job.id); saved.update(status="FAILED", output="")
    e.persistence.save(saved)
    restart(e); fresh_host(e)
    assert read(e) == candidate
    snapshot = raw_bytes(e)
    assert prepare(e, body) == candidate and raw_bytes(e) == snapshot
    human = review_body(candidate); human["director_notes"][0]["note"] = "Human edit after restart"
    adopted = review(e, human)
    assert adopted["document"]["status"] == "DRAFT"
    assert adopted["document"]["director_notes"][0]["note"] == human["director_notes"][0]["note"]
    assert adopted["document"]["provenance"]["terminal_evidence_digest"] == body["terminal_evidence_digest"]
    assert adopted["document"]["source_documents"] == {e.source["id"]: {
        "version": e.source["version"], "digest": e.documents.document_digest(e.source)}}
    draft = deepcopy(adopted["document"]); restart(e)
    assert e.documents.get(e.nid, e.scope, draft["id"]) == draft
    assert len(e.requests) == len(e.broker.ledger(e.nid, e.scope, e.actor)) == 1


@pytest.mark.parametrize("fault", ["evidence", "schema", "digest", "output", "bytes", "status", "hook", "request", "checkpoint", "ledger", "preview", "parameters"])
def test_prepare_requires_exact_historical_completion(lifecycle, fault):
    e = board(lifecycle); job, body = publish(e, schema=fault != "schema", evidence=fault != "evidence")
    saved = e.persistence.get(job.id)
    if fault == "digest": body["terminal_evidence_digest"] = "0" * 64
    elif fault in {"output", "bytes", "status", "hook", "request", "checkpoint"}:
        if fault == "output": saved["output"] = ""
        elif fault == "bytes": saved["output"] += "é"
        elif fault == "status": saved["status"] = "FAILED"
        elif fault == "hook": saved["terminal_hook_status"] = "UNKNOWN"
        elif fault == "checkpoint":
            saved[FIELD]["checkpoint_at"] = saved[FIELD]["generation_deadline"]
            body["terminal_evidence_digest"] = digest(saved[FIELD])
        else: saved["expected_request_digest"] = "f" * 64
        # Direct hostile fixture corruption is never a supported writer.
        e.persistence.repository._job_path(job.id).write_text(json.dumps(saved), encoding="utf-8")
    elif fault in {"ledger", "preview", "parameters"}:
        with e.raw.transaction(e.nid, e.scope) as state:
            row = state["collections"][e.documents.proposals.COLLECTION][e.row["id"]]
            if fault == "ledger": state["collections"][e.broker.LEDGER][row["model_execution"]["reservation_id"]]["actual_microusd"] = False
            elif fault == "preview": row["model_preview"]["prompt"] += "tampered"
            else: row["model_preview"]["parameters"]["temperature"] = 0
    before = raw_bytes(e)
    with pytest.raises(DENIALS): prepare(e, body)
    assert raw_bytes(e) == before and PENDING_FIELD not in raw_proposal(e)


@pytest.mark.parametrize("operation", ["prepare", "read", "review"])
@pytest.mark.parametrize("fault", ["host", "actor", "scope", "features", "source", "source_version", "source_archive", "source_delete", "incarnation", "owner_missing", "owner_replaced", "route", "license", "price", "budget"])
def test_fresh_authority_source_and_current_policy_at_every_action(lifecycle, monkeypatch, operation, fault):
    e = board(lifecycle); _, body = publish(e)
    candidate = prepare(e, body) if operation != "prepare" else None
    if fault == "host": e.sessions.revoke(e.token)
    elif fault == "actor": e.ctx.actor = "different-author"
    elif fault == "scope": e.active = False
    elif fault == "features": monkeypatch.setenv("EXPERIMENTAL_FEATURES", "")
    elif fault == "owner_missing": (e.root / "novels" / e.nid / "creative_project_v2.json").unlink()
    elif fault == "owner_replaced":
        import uuid
        marker = e.root / "novels" / e.nid / "creative_project_v2.json"
        value = json.loads(marker.read_text()); value["project_incarnation"] = str(uuid.uuid4())
        marker.write_text(json.dumps(value))
    elif fault == "route": e.candidate["model_evidence_fingerprint"] = "changed"
    elif fault == "license": e.candidate["license_confirmed"] = False
    elif fault == "budget": e.broker.configure_budget(e.nid, e.scope, e.actor, {"expected_version": 0, "max_inflight": 2})
    else:
        with e.raw.transaction(e.nid, e.scope) as state:
            collections = state["collections"]
            if fault == "source": collections[e.documents.COLLECTION][e.source["id"]]["title"] = "Changed"
            elif fault == "source_version": collections[e.documents.COLLECTION][e.source["id"]]["version"] += 1
            elif fault == "source_archive": collections[e.documents.COLLECTION][e.source["id"]]["status"] = "ARCHIVED"
            elif fault == "source_delete": collections[e.documents.COLLECTION].pop(e.source["id"])
            elif fault == "incarnation": collections[e.documents.proposals.COLLECTION][e.row["id"]]["project_incarnation"] = "changed"
            else: collections[e.broker.PRICES][e.route["route_id"]]["reserve_microusd"] = 1
    before = raw_bytes(e)
    with pytest.raises(DENIALS):
        prepare(e, body) if operation == "prepare" else read(e) if operation == "read" else review(e, review_body(candidate))
    assert raw_bytes(e) == before


@pytest.mark.parametrize("fault", ["extra", "notes", "digest", "mapping", "provenance", "version", "null"])
def test_saved_pending_schema_digest_and_provenance_are_revalidated(lifecycle, fault):
    e = board(lifecycle); _, body = publish(e); prepare(e, body)
    with e.raw.transaction(e.nid, e.scope) as state:
        row = state["collections"][e.documents.proposals.COLLECTION][e.row["id"]]
        if fault == "extra": row[PENDING_FIELD]["extra"] = "secret"
        elif fault == "notes": row["director_notes"][0]["note"] = "changed"
        elif fault == "digest": row[PENDING_FIELD]["output_digest"] = "0" * 64
        elif fault == "mapping": row["director_notes"][0]["scene_id"] = "scene-b"
        elif fault == "provenance": row[PENDING_FIELD]["provenance"]["prompt"] = "secret"
        elif fault == "version": row["version"] += 1
        else: row[PENDING_FIELD] = None
    before = raw_bytes(e)
    with pytest.raises(DENIALS): read(e)
    assert raw_bytes(e) == before


def test_concurrent_prepare_reconciles_one_version_and_concurrent_review_one_draft(lifecycle):
    e = board(lifecycle); _, body = publish(e)
    before = raw_proposal(e)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: prepare(e, deepcopy(body)), range(2)))
    assert results[0] == results[1]
    assert raw_proposal(e)["version"] == before["version"] + 1
    def adopt():
        try: return review(e, review_body(results[0]))
        except DENIALS: return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: adopt(), range(2)))
    assert len([value for value in results if value]) == 1
    assert len(e.raw.read(e.nid, e.scope)["collections"][e.documents.COLLECTION]) == 3


@pytest.mark.parametrize("operation", ["prepare", "review"])
def test_private_cas_conflict_contains_only_version_and_status(lifecycle, operation):
    e = board(lifecycle); _, body = publish(e)
    if operation == "review": body = review_body(prepare(e, body))
    body["expected_version"] += 5
    with pytest.raises(CapabilityVersionConflict) as caught:
        prepare(e, body) if operation == "prepare" else review(e, body)
    assert set(caught.value.current) == {"version", "status"}


@pytest.mark.parametrize("placement", ["pending", "null", "malformed", "history", "nested_history"])
def test_new_marker_and_copied_provenance_stay_publicly_closed(lifecycle, placement):
    from test_v2_creative_director_execution_lifecycle import public_client
    e = board(lifecycle); _, body = publish(e); candidate = prepare(e, body)
    with e.raw.transaction(e.nid, e.scope) as state:
        row = state["collections"][e.documents.proposals.COLLECTION][e.row["id"]]
        pending = deepcopy(row[PENDING_FIELD]); row["model_preview"] = row["model_execution"] = None
        row["history"] = []
        row["provenance"]["private_copy"] = deepcopy(pending)
        if placement == "null": row[PENDING_FIELD] = None
        elif placement == "malformed": row[PENDING_FIELD] = "secret marker"
        elif placement in {"history", "nested_history"}:
            row.pop(PENDING_FIELD)
            historical = {PENDING_FIELD: pending}
            row["history"] = [historical if placement == "history" else {"history": [historical]}]
    for prefix in ("/api", "/api/v1"):
        client, base = public_client(e, prefix); headers = {"X-Session-Token": e.token}
        response = client.get(base + "/" + e.row["id"], headers=headers)
        assert response.status_code == 200
        value = response.json()
        assert value["director_notes"] == [] and value["status"] == "MODEL_UNAVAILABLE"
        assert PENDING_FIELD not in value and "provenance" not in value
        assert candidate["provenance"]["terminal_evidence_digest"] not in response.text
        for action, action_body in {"review": review_body(candidate), "refresh": {"expected_version": candidate["expected_version"]},
                "cancel": {"expected_version": candidate["expected_version"]}}.items():
            denied = client.post(base + "/" + e.row["id"] + "/" + action, headers=headers, json=action_body)
            assert denied.status_code in {400, 403, 404, 409, 422}
            assert "private_copy" not in denied.text


@pytest.mark.parametrize("after_replace", [False, True])
def test_uncertain_prepare_commit_never_replays_or_duplicates(lifecycle, monkeypatch, after_replace):
    import app.experimental.store as store
    e = board(lifecycle); _, body = publish(e)
    original = store.atomic_write; before = raw_bytes(e)
    def broken(*args, **kwargs):
        if after_replace: original(*args, **kwargs)
        raise OSError("injected scope replacement uncertainty")
    monkeypatch.setattr(store, "atomic_write", broken)
    with pytest.raises(OSError): prepare(e, body)
    monkeypatch.setattr(store, "atomic_write", original)
    if after_replace:
        committed = raw_bytes(e); candidate = prepare(e, body)
        assert raw_bytes(e) == committed and candidate == read(e)
    else:
        assert raw_bytes(e) == before and PENDING_FIELD not in raw_proposal(e)
    assert len(e.requests) == 1


@pytest.mark.parametrize("lock", ["raw", "creative", "owner"])
def test_preheld_lock_rejected_before_job_lookup(lifecycle, monkeypatch, lock):
    e = board(lifecycle); _, body = publish(e)
    monkeypatch.setattr(e.manager, "get", lambda *args: pytest.fail("lookup under caller lock"))
    context = e.raw.transaction(e.nid, e.scope) if lock == "raw" else (
        e.documents.store.transaction(e.nid, e.scope) if lock == "creative" else e.documents.store.owner_lease(e.nid))
    with context:
        with pytest.raises(ValueError, match="LOCK_ORDER_INVALID"): prepare(e, body)


@pytest.mark.parametrize("fault", ["scope", "host", "source", "notes", "capacity"])
def test_prepare_final_callbacks_fail_without_partial_publication(lifecycle, monkeypatch, fault):
    e = board(lifecycle); _, body = publish(e)
    original = e.documents.proposals._capacity
    def capacity(state):
        original(state)
        if fault == "scope": e.active = False
        elif fault == "host": e.sessions.revoke(e.token)
        elif fault == "capacity": raise ValueError("capacity fault")
        else:
            raw = e.raw._local.active[e.raw.key(e.nid, e.scope)]
            if fault == "source": raw["collections"][e.documents.COLLECTION][e.source["id"]]["title"] = "changed"
            else: raw["collections"][e.documents.proposals.COLLECTION][e.row["id"]]["director_notes"][0]["note"] = "changed"
    monkeypatch.setattr(e.documents.proposals, "_capacity", capacity)
    before = raw_bytes(e)
    with pytest.raises(DENIALS): prepare(e, body)
    assert raw_bytes(e) == before


def test_output_clear_at_last_leaf_boundary_rolls_back_pending(lifecycle, monkeypatch):
    e = board(lifecycle); job, body = publish(e)
    repository = e.persistence.repository; original = repository._director_snapshot_leaf
    @contextmanager
    def clear_then_lock(jid):
        saved = repository.get(jid); saved.update(output="", status="FAILED")
        repository.save(saved)
        with original(jid) as locked: yield locked
    monkeypatch.setattr(repository, "_director_snapshot_leaf", clear_then_lock)
    before = raw_bytes(e)
    with pytest.raises(ValueError, match="OUTPUT_CHANGED"): prepare(e, body)
    assert raw_bytes(e) == before and e.persistence.get(job.id)["output"] == ""


def test_callbacks_finish_before_leaf_and_leaf_spans_original_scope_commit(lifecycle, monkeypatch):
    import app.experimental.store as store
    import app.repositories.file.mutation_coordinator as coordinator
    import app.creative.director_binding as binding_module
    e = board(lifecycle); job, body = publish(e)
    repository = e.persistence.repository
    leaf = repository._write_key(repository._job_path(job.id))
    def held(): return any(key[1] == leaf for key in getattr(coordinator._thread_state, "depths", {}))
    callbacks, commits = [], []
    original_guard, original_write = e.guard, store.atomic_write
    def guard():
        assert not held(), "authority callback acquired under leaf"
        callbacks.append(True); original_guard()
    def write(path, value, *args, **kwargs):
        assert held(), "generation leaf released before scope replacement"
        assert getattr(e.documents.store._local, "owners", {}).get(e.nid) == raw_proposal(e)["project_incarnation"]
        commits.append(True)
        return original_write(path, value, *args, **kwargs)
    def checked(name, callback):
        def wrapped(*args, **kwargs):
            assert not held(), name + " callback acquired under leaf"
            callbacks.append(name)
            return callback(*args, **kwargs)
        return wrapped
    monkeypatch.setattr(e.coordinator, "_independent_host", checked("Host", e.coordinator._independent_host))
    monkeypatch.setattr(e.coordinator, "_independent_policy", checked("policy", e.coordinator._independent_policy))
    monkeypatch.setattr(binding_module, "_validate_creative_director_source_locked",
        checked("source", binding_module._validate_creative_director_source_locked))
    e.guard = guard; monkeypatch.setattr(store, "atomic_write", write)
    prepare(e, body)
    assert callbacks and commits == [True] and not held()


@pytest.mark.parametrize("boundary", ["owner_unwind", "leaf_unwind"])
def test_postcommit_unwind_uncertainty_reconciles_exact_original_pending(lifecycle, monkeypatch, boundary):
    import app.creative.director_binding as binding
    e = board(lifecycle); _, body = publish(e)
    if boundary == "owner_unwind":
        target, name = binding, "_creative_director_owner_lease"
    else: target, name = e.persistence.repository, "_director_snapshot_leaf"
    original = getattr(target, name)
    @contextmanager
    def broken(*args, **kwargs):
        with original(*args, **kwargs) as value: yield value
        raise OSError("injected lock unwind uncertainty")
    monkeypatch.setattr(target, name, broken)
    with pytest.raises(OSError): prepare(e, body)
    monkeypatch.setattr(target, name, original)
    before = raw_bytes(e)
    assert PENDING_FIELD in raw_proposal(e)
    assert prepare(e, body) == read(e) and raw_bytes(e) == before


@pytest.mark.parametrize("boundary", ["policy", "final_guard"])
def test_ai_execution_feature_rechecked_after_policy_and_final_guard(lifecycle, monkeypatch, boundary):
    from creative_director_execution_fixture import FLAGS
    e = board(lifecycle); _, body = publish(e)
    original_policy, original_guard = e.coordinator._independent_policy, e.guard
    policy_returned = []
    def revoke(): monkeypatch.setenv("EXPERIMENTAL_FEATURES", FLAGS.replace("ai_execution_v2,", ""))
    def policy(*args, **kwargs):
        value = original_policy(*args, **kwargs)
        policy_returned.append(True)
        if boundary == "policy": revoke()
        return value
    def guard():
        original_guard()
        if boundary == "final_guard" and policy_returned: revoke()
    monkeypatch.setattr(e.coordinator, "_independent_policy", policy)
    e.guard = guard
    before = raw_bytes(e)
    with pytest.raises(DENIALS): prepare(e, body)
    assert policy_returned and raw_bytes(e) == before


@pytest.mark.parametrize("operation", ["read", "review"])
@pytest.mark.parametrize("target", ["source", "ledger", "active_mapping", "active_row"])
def test_final_guard_cannot_mutate_any_scope_row_during_pending_read_or_review(lifecycle, monkeypatch, operation, target):
    e = board(lifecycle); _, body = publish(e); candidate = prepare(e, body)
    original_policy, original_guard = e.coordinator._independent_policy, e.guard
    armed = []
    def policy(*args, **kwargs):
        value = original_policy(*args, **kwargs); armed.append(True); return value
    def guard():
        original_guard()
        if armed:
            state = e.raw._local.active[e.raw.key(e.nid, e.scope)]
            if target == "source": state["collections"][e.documents.COLLECTION][e.source["id"]]["title"] = "changed at final guard"
            elif target == "ledger":
                reservation = state["collections"][e.documents.proposals.COLLECTION][e.row["id"]]["model_execution"]["reservation_id"]
                state["collections"][e.broker.LEDGER][reservation]["status"] = "RESERVED"
            elif target == "active_mapping": e.raw._local.active = dict(e.raw._local.active)
            else: e.raw._local.active[e.raw.key(e.nid, e.scope)] = deepcopy(state)
    monkeypatch.setattr(e.coordinator, "_independent_policy", policy); e.guard = guard
    before = raw_bytes(e)
    with pytest.raises(DENIALS): read(e) if operation == "read" else review(e, review_body(candidate))
    assert armed and raw_bytes(e) == before
