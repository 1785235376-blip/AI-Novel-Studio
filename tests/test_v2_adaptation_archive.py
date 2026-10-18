"""Original adaptation execution plus private Asset owner crash boundaries."""
import copy
import json
import threading
import time
from contextlib import contextmanager
from hashlib import sha256

import pytest

from test_v2_source_adaptation import (mounted, prefix, broker_app, creative_model, checked, create,
    ready, dispatch, settle, review, action, output)


def archived(e, row):
    with e.studio._asset_scope(e.nid, row["scope"]):
        return [item for item in e.assets.list(e.nid, branch_id=row["scope"].get("branch_id"),
            actor_id=row["created_by"], include_deleted=True)
            if (item.get("_text_result_origin") or {}).get("proposal_id") == row["id"]]


def raw(e, row, asset):
    with e.studio._asset_scope(e.nid, row["scope"]):
        return e.assets.content(asset["id"], branch_id=row["scope"].get("branch_id"), actor_id=row["created_by"])


def read(e, row):
    return checked(e.client.get(e.creative_base + f'/adaptation-proposals/{row["id"]}', headers=e.headers))


def completed_without_refresh(e, monkeypatch, text=None):
    from app.runtime import runtime
    calls, threads = [], []
    row, _ = ready(e, monkeypatch)
    def stream(prompt, model, **kwargs):
        calls.append(prompt); threads.append(threading.current_thread())
        yield text if text is not None else json.dumps(output(e))
    monkeypatch.setattr(runtime.providers["mock"], "stream", stream)
    running = dispatch(e, row)
    job = e.manager.get(running["model_execution"]["job_id"])
    limit = time.monotonic() + 20
    with job.condition:
        while job.status not in e.manager.terminal or job.terminal_hook_status is None:
            remaining = limit - time.monotonic(); assert remaining > 0
            job.condition.wait(min(.05, remaining))
    assert threads
    threads[0].join(max(0, limit - time.monotonic()))
    assert not threads[0].is_alive() and job.status == "COMPLETED", job.public()
    return running, job, calls


def reopen(e, monkeypatch):
    from app.jobs import JobManager
    original = e.manager
    reopened = JobManager(generations=original.persistence, chapters=e.chapters, contexts=original.contexts,
        canon=e.canon, memory_extractor=original.memory_extractor, snapshot_required=False,
        collaboration_updates=original.collaboration_updates)
    monkeypatch.setattr(e.creative.adaptations.generation, "manager", reopened)
    def forbidden(*args, **kwargs): raise AssertionError("recovery must not replay or rebuild a request")
    monkeypatch.setattr(reopened, "start_prepared", forbidden)
    monkeypatch.setattr(reopened, "prepare_author_request", forbidden)
    monkeypatch.setattr(e.creative.adaptations.generation.preparer, "prepare_author", forbidden)
    return reopened


def test_automatic_archive_then_edited_adoption_preserves_original_bytes(creative_model, monkeypatch):
    e = creative_model
    chapter = copy.deepcopy(e.chapters.get(e.chapter["id"]))
    row, calls = ready(e, monkeypatch)
    result = settle(e, dispatch(e, row))
    assert result["status"] == "NEEDS_REVIEW", result
    item, = archived(e, result)
    job = e.manager.get(result["model_execution"]["job_id"])
    assert raw(e, result, item) == job.output.encode()
    assert item["version"] == 1 and item["_text_result_review"]["status"] == "DRAFT"
    assert result["asset_output"]["asset_id"] == item["id"]
    receipt = item["_text_execution_receipt"]
    assert receipt["request"] == row["model_preview"]["request"]
    assert receipt["terminal"]["final_publication"] == job.adaptation_publication
    assert receipt["request"]["parameters"] == {"temperature": None, "max_output_tokens": None, "stop_sequences": []}
    edited = copy.deepcopy(result["output"]); edited["scenes"][0]["action"] = "Human-reviewed changed action."
    adopted = checked(review(e, result, output=edited))
    approved, = archived(e, result)
    assert approved["id"] == item["id"] and approved["version"] == 2
    assert approved["_text_result_review"]["status"] == "APPROVED"
    assert raw(e, result, approved) == job.output.encode()
    assert approved["_text_result_review"]["receipt"]["generated_output_digest"] != approved["_text_result_review"]["receipt"]["reviewed_output_digest"]
    assert adopted["proposal"]["asset_output"]["state"] == "APPROVED"
    assert e.chapters.get(e.chapter["id"]) == chapter and len(calls) == 1
    assert read(e, result)["asset_output"]["version"] == 2
    assert len(e.creative.list(e.nid, result["scope"])) == 1
    with e.studio._asset_scope(e.nid, result["scope"]):
        assert not e.assets.list(e.nid)
        with pytest.raises(FileNotFoundError): e.assets.get(item["id"])
    public = e.assets.public(approved)
    assert "_text_execution_receipt" not in public and "_text_result_origin" not in public


@pytest.mark.parametrize("after", [False, True], ids=["before-meta", "after-meta"])
def test_archive_write_fault_recovers_one_asset_without_model_replay(creative_model, monkeypatch, after):
    e = creative_model
    running, job, calls = completed_without_refresh(e, monkeypatch)
    original, writes = e.assets._write_meta, []
    def fault(meta):
        if (meta.get("_text_result_origin") or {}).get("proposal_id") == running["id"]:
            writes.append(meta["id"])
            if after: original(meta)
            raise OSError("synthetic archive write fault")
        return original(meta)
    monkeypatch.setattr(e.assets, "_write_meta", fault)
    before = copy.deepcopy(e.manager.persistence.get(job.id))
    failed = read(e, running)
    assert failed["asset_output"]["state"] == "INCOMPLETE" and failed["output"] is None
    count = len(writes)
    for _ in range(3): assert read(e, running)["output"] is None
    assert len(writes) == count == 1
    monkeypatch.setattr(e.assets, "_write_meta", original)
    recovered = action(e, running, "refresh")
    assert recovered["status"] == "NEEDS_REVIEW", recovered
    assert len(archived(e, running)) == 1 and len(calls) == 1
    if after: assert recovered["asset_output"]["asset_id"] == writes[0]
    assert e.manager.persistence.get(job.id) == before


def test_archive_committed_then_proposal_transaction_fault_recovers(creative_model, monkeypatch):
    e = creative_model
    running, job, calls = completed_without_refresh(e, monkeypatch)
    original = e.creative.store.transaction
    @contextmanager
    def fault(nid, scope):
        with original(nid, scope) as state:
            yield state
            row = state["collections"].get(e.creative.adaptations.COLLECTION, {}).get(running["id"])
            if row and row["status"] == "NEEDS_REVIEW": raise OSError("synthetic phase B commit fault")
    monkeypatch.setattr(e.creative.store, "transaction", fault)
    failed = action(e, running, "refresh")
    assert failed["asset_output"]["state"] == "INCOMPLETE"
    item, = archived(e, running)
    assert e.creative.adaptations._owned(e.nid, running["scope"], running["created_by"], running["id"])["status"] == "GENERATING"
    monkeypatch.setattr(e.creative.store, "transaction", original)
    reopened = reopen(e, monkeypatch)
    loaded = reopened.get(job.id)
    assert loaded.request_authorization is None and loaded.author_preparation_guard is None
    result = action(e, running, "refresh")
    assert result["status"] == "NEEDS_REVIEW" and result["asset_output"]["asset_id"] == item["id"]
    assert len(archived(e, running)) == len(calls) == 1


@pytest.mark.parametrize("archive_first", [False, True])
def test_real_original_manager_restart_recovers_passive_result(creative_model, monkeypatch, archive_first):
    e = creative_model
    row, job, calls = completed_without_refresh(e, monkeypatch)
    if archive_first: row = action(e, row, "refresh")
    reopened = reopen(e, monkeypatch)
    loaded = reopened.get(job.id)
    for field in ("request_authorization", "author_preparation_guard", "author_context_resolver", "before_dispatch", "on_terminal", "prepared_text_invocation"):
        assert getattr(loaded, field) is None
    result = read(e, row)
    assert result["status"] == "NEEDS_REVIEW", result
    assert len(archived(e, row)) == 1 and len(calls) == 1
    accepted = checked(review(e, result))
    assert accepted["proposal"]["asset_output"]["version"] == 2
    assert len(calls) == 1


@pytest.mark.parametrize("after", [False, True])
def test_human_decision_survives_failed_asset_review_projection(creative_model, monkeypatch, after):
    e = creative_model
    row, calls = ready(e, monkeypatch)
    row = settle(e, dispatch(e, row))
    original = e.assets._write_meta
    def fault(meta):
        if meta.get("version") == 2 and (meta.get("_text_result_origin") or {}).get("proposal_id") == row["id"]:
            if after: original(meta)
            raise OSError("synthetic review projection fault")
        return original(meta)
    monkeypatch.setattr(e.assets, "_write_meta", fault)
    accepted = checked(review(e, row))
    assert accepted["proposal"]["status"] == "APPROVED"
    assert accepted["proposal"]["asset_output"]["state"] == "INCOMPLETE"
    document = accepted["document"]["id"]
    monkeypatch.setattr(e.assets, "_write_meta", original)
    recovered = action(e, accepted["proposal"], "refresh")
    assert recovered["document_id"] == document and recovered["asset_output"]["version"] == 2
    assert len(e.creative.list(e.nid, row["scope"])) == 1 and len(archived(e, row)) == len(calls) == 1


@pytest.mark.parametrize("field", ["adaptation_publication", "output", "expected_request_digest", "generation_deadline",
    "generation_max_output_bytes", "execution_mode", "provider", "model", "base_chapter_digest", "source", "instruction"])
def test_changed_durable_execution_never_archives(creative_model, monkeypatch, field):
    e = creative_model
    row, job, calls = completed_without_refresh(e, monkeypatch)
    original = e.manager.persistence.get
    def changed(jid):
        value = original(jid)
        if jid == job.id: value[field] = None if field == "adaptation_publication" else "changed"
        return value
    monkeypatch.setattr(e.manager.persistence, "get", changed)
    result = action(e, row, "refresh")
    assert result["output"] is None and result["asset_output"]["state"] == "INCOMPLETE"
    assert not archived(e, row) and len(calls) == 1


def test_invalid_json_still_archives_completed_raw_evidence_privately(creative_model, monkeypatch):
    e = creative_model
    row, calls = ready(e, monkeypatch, "not valid JSON")
    result = settle(e, dispatch(e, row))
    assert result["model_execution"]["status"] == "DISCARDED" and result["output"] is None
    item, = archived(e, result)
    assert raw(e, result, item) == b"not valid JSON" and item["version"] == 1
    assert review(e, result).status_code in {409, 422}
    assert not e.creative.list(e.nid, row["scope"]) and len(calls) == 1


def test_receipt_budget_rejects_before_prepare_reservation_or_inference(creative_model, monkeypatch):
    e = creative_model
    row, calls = ready(e, monkeypatch)
    assets = e.creative.adaptations.assets
    original = assets.assets._text_initial
    def reject(initial, data): raise ValueError("ADAPTATION_TEXT_METADATA_LIMIT")
    monkeypatch.setattr(assets.assets, "_text_initial", reject)
    def forbidden(*args, **kwargs): raise AssertionError("preflight must precede execution preparation")
    monkeypatch.setattr(e.creative.adaptations.generation.preparer, "prepare_author", forbidden)
    before = e.creative.store.read(e.nid, row["scope"])
    response = e.client.post(e.creative_base + f'/adaptation-proposals/{row["id"]}/dispatch', headers=e.headers,
        json={"expected_version": row["version"], "reviewed_preview_digest": row["model_preview"]["preview_digest"]})
    assert response.status_code == 422 and "ADAPTATION_TEXT_METADATA_LIMIT" in response.text
    assert not e.manager.jobs and not calls and not archived(e, row)
    assert e.creative.store.read(e.nid, row["scope"]) == before

@pytest.mark.parametrize("field", ["_owner_actor_id", "_required_features", "version", "_text_result_review", "asset_archive", "model_asset_intent", "selection_digest"])
def test_archive_and_proposal_tampering_masks_all_generated_projections(creative_model, monkeypatch, field):
    e = creative_model
    row, calls = ready(e, monkeypatch)
    result = settle(e, dispatch(e, row))
    item, = archived(e, result)
    if field.startswith("_") or field == "version":
        path = e.assets._meta_path(item["id"])
        meta = json.loads(path.read_text(encoding='utf-8'))
        if field == "version": meta[field] = True
        elif field == "_text_result_review": meta[field] = {"status": "APPROVED", "receipt": {}, "history": []}
        else: meta.pop(field)
        path.write_text(json.dumps(meta), encoding='utf-8')
    else:
        with e.creative.store.transaction(e.nid, result["scope"]) as state:
            current = state["collections"][e.creative.adaptations.COLLECTION][result["id"]]
            if field == "selection_digest": current[field] = "f" * 64
            else: current.pop(field)
    view = read(e, result)
    assert view["output"] is None and view["model_preview"] is None and view["provenance"] is None
    assert view["asset_output"]["state"] == "INCOMPLETE"
    assert review(e, result).status_code in {409, 422}
    assert len(calls) == 1 and not e.creative.list(e.nid, result["scope"])


def test_completed_first_save_restart_cannot_invent_final_publication(creative_model, monkeypatch):
    e = creative_model
    from app.runtime import runtime
    row, calls = ready(e, monkeypatch)
    provider_stream = runtime.providers["mock"].stream
    threads = []
    def stream(*args, **kwargs):
        threads.append(threading.current_thread())
        yield from provider_stream(*args, **kwargs)
    monkeypatch.setattr(runtime.providers["mock"], "stream", stream)
    original = e.manager._persist
    entered, release = threading.Event(), threading.Event()
    def block_after_first_completed_save(job):
        result = original(job)
        if job.status == "COMPLETED" and job.terminal_hook_status == "COMPLETED" and job.adaptation_publication is None:
            entered.set(); assert release.wait(15), "original publication gate was not released"
        return result
    monkeypatch.setattr(e.manager, "_persist", block_after_first_completed_save)
    running = dispatch(e, row)
    try:
        assert entered.wait(10)
        first = e.manager.persistence.get(running["model_execution"]["job_id"])
        assert first["status"] == "COMPLETED" and first.get("adaptation_publication") is None
        reopened = reopen(e, monkeypatch)
        result = action(e, running, "refresh")
        assert result["output"] is None and result["asset_output"]["state"] == "INCOMPLETE"
        assert not archived(e, running)
        assert reopened.get(first["id"]).request_authorization is None
    finally:
        release.set()
        if threads: threads[0].join(20)
        assert threads and not threads[0].is_alive()
    final = e.manager.persistence.get(first["id"])
    assert final["adaptation_publication"]["output_digest"] == sha256(final["output"].encode()).hexdigest()
    reopen(e, monkeypatch)
    recovered = action(e, running, "refresh")
    assert recovered["status"] == "NEEDS_REVIEW" and len(archived(e, running)) == len(calls) == 1


def test_list_archives_later_result_without_starvation_or_extra_user_action(creative_model, monkeypatch):
    e = creative_model
    first, _ = ready(e, monkeypatch)
    first = settle(e, dispatch(e, first))
    checked(review(e, first))
    second, job, calls = completed_without_refresh(e, monkeypatch)
    assert not archived(e, second)
    rows = checked(e.client.get(e.creative_base + '/adaptation-proposals', headers=e.headers))["items"]
    recovered = next(item for item in rows if item["id"] == second["id"])
    assert recovered["status"] == "NEEDS_REVIEW" and recovered["asset_output"]["version"] == 1
    assert len(calls) == 1 and len(archived(e, second)) == 1

@pytest.mark.parametrize("price,usage,expected", [
    ({"actual_known_zero": True}, None, "KNOWN_SYNTHETIC_ZERO"),
    ({"input_per_million_microusd": 0, "output_per_million_microusd": 0}, {"input_tokens": 10, "output_tokens": 8}, "CALCULATED_FROM_REPORTED_USAGE"),
    ({"input_per_million_microusd": 0, "output_per_million_microusd": 0}, None, None),
    ({"input_per_million_microusd": 1, "output_per_million_microusd": 0}, {"input_tokens": 0, "output_tokens": 8}, None),
    ({"actual_known_zero": 1}, None, None),
    ({"input_per_million_microusd": False, "output_per_million_microusd": 0}, {"input_tokens": 10, "output_tokens": 8}, None),
    ({"input_per_million_microusd": 0, "output_per_million_microusd": 0}, {"input_tokens": True, "output_tokens": 8}, None),
])
def test_passive_zero_settlement_matches_original_broker_branches(price, usage, expected):
    from app.creative.adaptation_assets import zero_settlement_state
    if expected is None:
        with pytest.raises(ValueError): zero_settlement_state(price, usage)
    else: assert zero_settlement_state(price, usage) == expected


@pytest.mark.parametrize("state", ["FAILED", "CANCELLED", "QUEUED"])
def test_changed_original_job_state_cannot_disclose_archived_result(creative_model, monkeypatch, state):
    e = creative_model
    row, calls = ready(e, monkeypatch)
    result = settle(e, dispatch(e, row))
    monkeypatch.setattr(e.manager.get(result["model_execution"]["job_id"]), "status", state)
    view = read(e, result)
    assert view["output"] is None and view["model_preview"] is None and view["provenance"] is None
    assert view["status"] != "NEEDS_REVIEW" and len(calls) == 1


def test_pending_publication_lock_masks_an_already_archived_result(creative_model, monkeypatch):
    e = creative_model
    row, calls = ready(e, monkeypatch)
    result = settle(e, dispatch(e, row))
    job = e.manager.get(result["model_execution"]["job_id"])
    entered, release = threading.Event(), threading.Event()
    def hold():
        with job.condition:
            entered.set(); assert release.wait(10)
    thread = threading.Thread(target=hold); thread.start()
    try:
        assert entered.wait(5)
        view = read(e, result)
        assert view["output"] is None and view["model_preview"] is None and view["provenance"] is None
        assert view["asset_output"]["state"] == "PENDING" and view["status"] != "NEEDS_REVIEW"
    finally:
        release.set(); thread.join(10); assert not thread.is_alive()
    assert len(calls) == 1

@pytest.mark.parametrize("change", ["cancel", "source", "revoke"])
def test_authority_change_after_archive_commit_never_publishes_or_replays(creative_model, monkeypatch, change):
    e = creative_model
    row, job, calls = completed_without_refresh(e, monkeypatch)
    original = e.assets._write_meta
    def after_commit(meta):
        original(meta)
        if (meta.get("_text_result_origin") or {}).get("proposal_id") == row["id"]:
            raise OSError("synthetic lost archive acknowledgement")
    monkeypatch.setattr(e.assets, "_write_meta", after_commit)
    assert action(e, row, "refresh")["asset_output"]["state"] == "INCOMPLETE"
    item, = archived(e, row)
    monkeypatch.setattr(e.assets, "_write_meta", original)
    if change == "cancel":
        cancelled = action(e, row, "cancel")
        assert cancelled["status"] == "CANCELLED"
        value = read(e, row)
        assert value["status"] == "CANCELLED" and value["output"] is None and value["model_preview"] is None
        response = e.client.post(e.creative_base + f'/adaptation-proposals/{row["id"]}/refresh', headers=e.headers,
            json={"expected_version": cancelled["version"]})
        assert response.status_code == 422
    elif change == "source":
        checked(e.client.put(e.prefix + f'/chapters/{e.chapter["id"]}', json={"version": e.chapter["version"], "content": "Changed saved source"}))
        assert e.client.get(e.creative_base + f'/adaptation-proposals/{row["id"]}', headers=e.headers).status_code == 409
    else:
        e.main.trusted_session_resolver.revoke(e.headers["X-Session-Token"])
        assert e.client.get(e.creative_base + f'/adaptation-proposals/{row["id"]}', headers=e.headers).status_code == 401
    assert len(calls) == 1 and len(archived(e, row)) == 1
    assert not e.creative.list(e.nid, row["scope"])

@pytest.mark.parametrize("field,value", [
    ("instruction", "different instruction"), ("requested_model", "different-model"),
    ("required_experimental_features", ["narrative_production_v2"]), ("dispatch_hooks_required", False),
    ("adaptation_publication", None),
])
def test_genuine_restart_rejects_changed_passive_original_job_fields(creative_model, monkeypatch, field, value):
    e = creative_model
    row, job, calls = completed_without_refresh(e, monkeypatch)
    saved = e.manager.persistence.get(job.id)
    saved[field] = value
    e.manager.persistence.save(saved)
    reopened = reopen(e, monkeypatch)
    assert getattr(reopened.get(job.id), field) == value
    result = action(e, row, "refresh")
    assert result["output"] is None and result["asset_output"]["state"] == "INCOMPLETE"
    assert not archived(e, row) and len(calls) == 1


def test_completed_archive_recovers_after_same_durable_adapter_is_rebound(creative_model, monkeypatch):
    e = creative_model
    from app.runtime import runtime
    from app.model_runtime import LegacyTextProviderAdapter
    row, job, calls = completed_without_refresh(e, monkeypatch)
    before = e.creative.store.read(e.nid, row["scope"])["collections"][e.creative.adaptations.COLLECTION][row["id"]]["model_preview"]["broker"]["chosen"]
    replacement = LegacyTextProviderAdapter("mock", runtime.providers["mock"])
    monkeypatch.setitem(runtime.provider_registry._providers, "mock", replacement)
    after = e.broker.current_route(before["route_id"], local_text_only=True)
    assert after["fingerprint"] == before["fingerprint"]
    assert after["binding_hash"] != before["binding_hash"]
    reopen(e, monkeypatch)
    result = action(e, row, "refresh")
    assert result["status"] == "NEEDS_REVIEW", result
    assert len(calls) == 1 and len(archived(e, row)) == 1
