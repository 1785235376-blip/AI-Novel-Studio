"""Private live review on original File owners; no public/model-quality claim.

Run with the original V2 runner and an owned basetemp after source freeze.
Only the separate adopted DRAFT survives restart; no pending review authority does.
"""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event
import hashlib
import json
import time

import pytest
from fastapi import HTTPException

from creative_director_execution_fixture import lifecycle, dispatch, wait, raw_proposal, ForbiddenOwner

pytestmark = pytest.mark.file_backend_only
DENIALS = (ValueError, HTTPException, PermissionError, FileNotFoundError, KeyError)


def board(e):
    """A second real source distinguishes ordering, scene and shot identity."""
    e.source = e.documents.create(e.nid, e.scope, e.actor, {
        "mode": "STORYBOARD", "source_independent": True, "title": "Two authored shots",
        "scenes": [{"id": "scene-a", "sequence": 1, "heading": "ROOM", "action": "A visitor waits."},
                   {"id": "scene-b", "sequence": 2, "heading": "HALL", "action": "A door opens."}],
        "shots": [{"id": "shot-a", "number": 1, "scene_id": "scene-a", "action": "The visitor turns."},
                  {"id": "shot-b", "number": 2, "scene_id": "scene-b", "action": "The handle moves."}]})
    e.row = e.documents.proposals.create(e.nid, e.scope, e.actor,
        {"source_document_id": e.source["id"], "expected_source_version": e.source["version"]})
    return e


def output(e):
    notes = []
    for association, scene in zip(e.row["provenance"]["source_shots"], e.source["scenes"]):
        notes.append({"id": association["note_id"], "number": association["source_number"],
            "scene_id": association["scene_id"], "source_shot_id": association["source_shot_id"],
            "note": "Candidate interpretation", "shot_size": "MEDIUM", "duration_seconds": 5,
            "planning": {"rationale": "Consider a reaction beat", "sequence_reason": "Follow the authored order",
                "duration_reason": "Tentative timing", "uncertainty": "Physical geography remains unverified",
                "evidence": [{"scene_id": scene["id"], "field": "action", "excerpt": scene["action"]}],
                "assumptions": ["Camera placement needs human review"],
                "alternatives": [{"choice": "Hold wider", "tradeoff": "Less facial detail"}]}})
    return {"source_contract": "STORYBOARD_SHOT_CONTEXT_V1", "source_document_id": e.source["id"],
        "source_version": e.source["version"], "source_digest": e.documents.document_digest(e.source),
        "director_notes": notes}


def preview(e):
    return e.coordinator._preview_independent_review(e.ctx, e.row["id"], {
        "expected_version": e.row["version"], "route_id": e.route["route_id"],
        "allow_synthetic": False, "max_output_tokens": 512, "temperature": 0.0},
        e.guard, host_authority=e.authority)


def execute(e, candidate=None):
    e.wire_text = json.dumps(output(e) if candidate is None else candidate)
    prepared = preview(e)
    receipt = dispatch(e, prepared)
    job = wait(e, e.manager.get(receipt["model_execution"]["job_id"]))
    assert job.status == "COMPLETED" and job.terminal_hook_status == "COMPLETED"
    return prepared, job


def candidates(e):
    return e.coordinator._read_independent_candidates(e.ctx, e.row["id"], e.guard, host_authority=e.authority)


def review_body(candidate):
    return {"expected_version": candidate["expected_version"], "reviewed_output_digest": candidate["output_digest"],
        "title": "Explicit human-reviewed direction", "director_notes": deepcopy(candidate["director_notes"])}


def adopt(e, body):
    return e.coordinator._review_independent(e.ctx, e.row["id"], body, e.guard, host_authority=e.authority)


def files(e):
    return {str(p.relative_to(e.root)): p.read_bytes() for p in e.root.rglob("*") if p.is_file()}


def snapshot(e):
    return files(e), tuple(e.manager.jobs), deepcopy(e.broker.ledger(e.nid, e.scope, e.actor))


def raw_bytes(e):
    return e.raw.path(e.nid, e.scope).read_bytes()


def test_schema_opt_in_readonly_candidate_edited_adoption_and_file_reopen(lifecycle):
    from app.creative.proposals import director_output_digest
    from app.creative.service import CreativeService
    from app.creative.storyboard_model import DirectorStoryboardModelOutput, source_mapping
    from app.experimental.store import ExperimentalStore, canonical
    e = board(lifecycle)
    source = deepcopy(e.source)
    mapping = source_mapping(e.row, source)
    prepared, job = execute(e)
    prompt = prepared["model_preview"]["prompt"]
    assert prepared["model_preview"]["output_contract"] == "STORYBOARD_SHOT_CONTEXT_V1"
    assert "output_schema" in prompt and "source_mapping" in prompt
    data = json.loads(prompt.split("\n", 1)[1])
    assert data["output_schema"] == DirectorStoryboardModelOutput.model_json_schema()
    assert data["source_mapping"] == mapping
    before = snapshot(e)
    candidate = candidates(e)
    assert snapshot(e) == before
    assert candidate["proposal_id"] == e.row["id"]
    assert candidate["output_digest"] == director_output_digest(candidate["director_notes"], candidate.get("visual_target"))
    candidate["director_notes"][0]["note"] = "Detached caller mutation"
    assert candidates(e)["director_notes"][0]["note"] != "Detached caller mutation"
    body = review_body(candidates(e))
    body["director_notes"][0]["note"] = "Human edit: hold before turning"
    before_state = e.raw.read(e.nid, e.scope)
    accepted = adopt(e, body)
    draft = accepted["document"]
    assert draft["mode"] == "DIRECTOR" and draft["status"] == "DRAFT" and draft["id"] != source["id"]
    assert draft["director_notes"] == body["director_notes"]
    assert draft["shots"] == []
    assert draft["source_documents"] == {source["id"]: {"version": source["version"], "digest": e.documents.document_digest(source)}}
    provenance = draft["provenance"]
    assert provenance["source_mapping"] == mapping and "source_shots" not in provenance
    assert provenance["model_called"] is True and provenance["synthetic"] is False
    assert provenance["provider_id"] == e.route["provider_id"] and provenance["model_id"] == e.route["model_id"]
    assert provenance["parameters"] == {"max_output_tokens": 512, "temperature": 0.0}
    assert provenance["model_version"] == e.route.get("identity", {}).get("model_version")
    assert provenance["route_fingerprint"] == e.route["fingerprint"]
    assert provenance["job_id"] == job.id and provenance["request_digest"] == job.expected_request_digest
    assert provenance["preview_digest"] == prepared["model_preview"]["preview_digest"]
    assert provenance["raw_output_digest"] == hashlib.sha256(e.wire_text.encode()).hexdigest()
    assert provenance["reviewed_output_digest"] == director_output_digest(draft["director_notes"], draft.get("visual_target"))
    assert provenance["reviewed_by"] == e.actor
    encoded = canonical(draft)
    assert prompt not in encoded and e.token not in encoded
    assert not any(word in provenance for word in ("prompt", "seal", "capability", "host_principal", "request_authorization"))
    stored = raw_proposal(e)
    assert stored["status"] == "APPROVED" and stored["document_id"] == draft["id"]
    assert stored["provenance"]["source_shots"] == e.row["provenance"]["source_shots"]
    assert e.documents.get(e.nid, e.scope, source["id"]) == source
    after_state = e.raw.read(e.nid, e.scope)
    for name in set(before_state["collections"]) | set(after_state["collections"]):
        if name not in {e.documents.COLLECTION, e.documents.proposals.COLLECTION}:
            assert before_state["collections"].get(name) == after_state["collections"].get(name)
    assert len(e.manager.jobs) == len(e.requests) == len(e.broker.ledger(e.nid, e.scope, e.actor)) == 1
    reopened = CreativeService(ExperimentalStore(e.root, "file", ""), e.novels, e.forbidden)
    assert reopened.get(e.nid, e.scope, draft["id"]) == draft
    assert reopened.get(e.nid, e.scope, source["id"]) == source
    # Approval intentionally invalidates the old capability: do not invoke it here.


@pytest.mark.parametrize("fault", ["duplicate_key", "extra", "order", "missing", "duplicate", "cross_shot", "scene",
    "source_id", "source_version", "source_digest", "contract", "forged_excerpt", "shot_field", "uncertainty", "planning", "oversize"])
def test_strict_schema_and_source_evidence_never_create_partial_candidates(lifecycle, fault):
    e = board(lifecycle); payload = output(e)
    note = payload["director_notes"][0]
    if fault == "extra": payload["extra"] = True
    elif fault == "order": payload["director_notes"].reverse()
    elif fault == "missing": payload["director_notes"].pop()
    elif fault == "duplicate": payload["director_notes"][1] = deepcopy(note)
    elif fault == "cross_shot": note["source_shot_id"] = "shot-b"
    elif fault == "scene": note["scene_id"] = "scene-b"
    elif fault == "source_id": payload["source_document_id"] = "forged-source"
    elif fault == "source_version": payload["source_version"] += 1
    elif fault == "source_digest": payload["source_digest"] = "0" * 64
    elif fault == "contract": payload["source_contract"] = "UNKNOWN"
    elif fault == "forged_excerpt": note["planning"]["evidence"][0]["excerpt"] = "A dragon lands."
    elif fault == "shot_field": note["planning"]["evidence"][0].update(field="composition", excerpt="centered")
    elif fault == "uncertainty": note["planning"].pop("uncertainty")
    elif fault == "planning": note.pop("planning")
    elif fault == "oversize": note["note"] = "x" * 8001
    if fault == "duplicate_key":
        e.wire_text = json.dumps(payload).replace('"source_version":', '"source_version": 1, "source_version":', 1)
        prepared = preview(e); receipt = dispatch(e, prepared)
        wait(e, e.manager.get(receipt["model_execution"]["job_id"]))
    else: execute(e, payload)
    before = snapshot(e)
    with pytest.raises(DENIALS): candidates(e)
    assert snapshot(e) == before
    assert raw_proposal(e)["document_id"] is None


@pytest.mark.parametrize("operation", ["read", "adopt"])
@pytest.mark.parametrize("fault", ["deadline", "restart", "hook", "durable", "ledger", "actor", "scope", "host", "host_aba",
    "source", "incarnation", "owner_missing", "license", "route", "price", "budget", "visual_target", "cancel"])
def test_live_authority_required_at_read_and_adoption(lifecycle, monkeypatch, operation, fault):
    from app.jobs import JobManager
    e = board(lifecycle); _, job = execute(e); body = review_body(candidates(e))
    if fault == "deadline":
        import app.jobs as jobs
        class Expired(datetime):
            @classmethod
            def now(cls, tz=None): return datetime.fromisoformat(job.generation_deadline) + timedelta(seconds=1)
        monkeypatch.setattr(jobs, "datetime", Expired)
    elif fault == "restart":
        e.coordinator.manager = JobManager(e.persistence, e.forbidden, e.forbidden, e.forbidden, memory_extractor=e.forbidden)
    elif fault == "hook": job.terminal_hook_status = "UNKNOWN"
    elif fault == "durable":
        saved = e.persistence.get(job.id); saved["output"] = "different"; e.persistence.save(saved)
    elif fault == "actor": e.ctx.actor = "another-owner"
    elif fault == "scope": e.ctx.scope = {"mode": "local", "novel_id": "another-project"}
    elif fault == "host": e.sessions.revoke(e.token)
    elif fault == "host_aba": e.sessions.revoke(e.token); e.sessions.register(e.token, e.session)
    elif fault == "owner_missing": (e.root / "novels" / e.nid / "creative_project_v2.json").unlink()
    elif fault == "license": e.candidate["license_confirmed"] = False
    elif fault == "route": e.candidate["model_evidence_fingerprint"] = "changed"
    elif fault == "budget": e.broker.configure_budget(e.nid, e.scope, e.actor, {"expected_version": 0, "max_inflight": 2})
    elif fault == "cancel": job.cancelled.set()
    else:
        with e.raw.transaction(e.nid, e.scope) as state:
            collections = state["collections"]
            if fault == "ledger": collections[e.broker.LEDGER][raw_proposal(e)["model_execution"]["reservation_id"]]["status"] = "RESERVED"
            elif fault == "price": collections[e.broker.PRICES][e.route["route_id"]]["reserve_microusd"] = 1
            elif fault == "source": collections[e.documents.COLLECTION][e.source["id"]]["title"] = "Changed"
            elif fault == "incarnation": collections[e.documents.proposals.COLLECTION][e.row["id"]]["project_incarnation"] = "changed"
            else: collections[e.documents.proposals.COLLECTION][e.row["id"]]["visual_target"] = {"style": "Changed"}
    before = snapshot(e)
    with pytest.raises(DENIALS): candidates(e) if operation == "read" else adopt(e, body)
    assert snapshot(e) == before


@pytest.mark.parametrize("fault", ["version", "digest", "association", "order", "duplicate", "capacity", "commit"])
def test_review_cas_mapping_capacity_and_commit_are_atomic(lifecycle, monkeypatch, fault):
    import app.experimental.store as store_module
    from app.services.v1_capability_service import CapabilityVersionConflict
    e = board(lifecycle); execute(e); body = review_body(candidates(e))
    if fault == "version": body["expected_version"] += 1
    elif fault == "digest": body["reviewed_output_digest"] = "0" * 64
    elif fault == "association": body["director_notes"][0]["id"] = "replacement"
    elif fault == "order": body["director_notes"].reverse()
    elif fault == "duplicate": body["director_notes"][1] = deepcopy(body["director_notes"][0])
    elif fault == "capacity": monkeypatch.setattr(e.documents, "assert_capacity", lambda *a: (_ for _ in ()).throw(ValueError("capacity fault")))
    elif fault == "commit": monkeypatch.setattr(store_module, "atomic_write", lambda *a: (_ for _ in ()).throw(OSError("commit fault")))
    before = snapshot(e)
    with pytest.raises(DENIALS + (OSError, CapabilityVersionConflict)): adopt(e, body)
    assert snapshot(e) == before


@pytest.mark.parametrize("fault", ["host", "scope", "cancel", "output", "durable", "ledger"])
def test_final_guard_after_payload_preparation_prevents_partial_adoption(lifecycle, monkeypatch, fault):
    e = board(lifecycle); _, job = execute(e); body = review_body(candidates(e)); original = e.documents.prepare_content
    def prepare(*args, **kwargs):
        payload = original(*args, **kwargs)
        if fault == "host": e.sessions.revoke(e.token)
        elif fault == "scope": e.active = False
        elif fault == "cancel": job.cancelled.set()
        elif fault == "output": job.output = "changed output"
        elif fault == "durable":
            monkeypatch.setattr(e.persistence, "get", lambda *a: {"status": "UNKNOWN"})
        else:
            state = e.raw._local.active[e.raw.key(e.nid, e.scope)]
            state["collections"][e.broker.LEDGER][raw_proposal(e)["model_execution"]["reservation_id"]]["status"] = "RESERVED"
        return payload
    monkeypatch.setattr(e.documents, "prepare_content", prepare)
    before = raw_bytes(e)
    with pytest.raises(DENIALS): adopt(e, body)
    assert raw_bytes(e) == before and raw_proposal(e)["document_id"] is None


def test_duplicate_concurrent_review_creates_exactly_one_draft(lifecycle):
    e = board(lifecycle); execute(e); body = review_body(candidates(e)); before = e.raw.read(e.nid, e.scope)
    def submit():
        try: return adopt(e, deepcopy(body))
        except DENIALS: return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: submit(), range(2)))
    success = [item for item in outcomes if item]
    assert len(success) == 1
    after = e.raw.read(e.nid, e.scope)
    assert len(after["collections"][e.documents.COLLECTION]) == len(before["collections"][e.documents.COLLECTION]) + 1
    assert raw_proposal(e)["document_id"] == success[0]["document"]["id"]


@pytest.mark.parametrize("lock", ["raw", "creative", "owner"])
@pytest.mark.parametrize("operation", ["read", "adopt"])
def test_caller_preheld_scope_or_owner_is_rejected_before_job_lookup(lifecycle, monkeypatch, lock, operation):
    e = board(lifecycle); execute(e); body = review_body(candidates(e))
    monkeypatch.setattr(e.manager, "get", lambda *a: pytest.fail("job lookup occurred under caller-owned lock"))
    context = e.raw.transaction(e.nid, e.scope) if lock == "raw" else (
        e.documents.store.transaction(e.nid, e.scope) if lock == "creative" else e.documents.store.owner_lease(e.nid))
    before = raw_bytes(e)
    with context:
        with pytest.raises(DENIALS): candidates(e) if operation == "read" else adopt(e, body)
    assert raw_bytes(e) == before


def test_review_waits_for_original_worker_final_publication_guard(lifecycle, monkeypatch):
    e = board(lifecycle); e.wire_text = json.dumps(output(e))
    original = e.persistence.save; published, release = Event(), Event()
    def save(value):
        result = original(value)
        if value.get("status") == "COMPLETED" and value.get("terminal_hook_status") == "COMPLETED":
            published.set()
            assert release.wait(5)
        return result
    monkeypatch.setattr(e.persistence, "save", save)
    prepared = preview(e); receipt = dispatch(e, prepared)
    job = e.manager.get(receipt["model_execution"]["job_id"])
    try:
        assert published.wait(3)
        before = raw_bytes(e)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(candidates, e)
            time.sleep(.05)
            assert not future.done() and raw_bytes(e) == before
            release.set()
            candidate = future.result(timeout=5)
        wait(e, job)
        assert candidate["director_notes"] and job.status == "COMPLETED"
    finally:
        release.set()


@pytest.mark.parametrize("operation", ["read", "adopt"])
def test_condition_wait_is_bounded_by_original_deadline(lifecycle, monkeypatch, operation):
    import app.creative.generation as generation
    monkeypatch.setattr(generation, "TIMEOUT_SECONDS", 1)
    e = board(lifecycle); _, job = execute(e); body = review_body(candidates(e))
    locked, release = Event(), Event()
    def hold():
        with job.condition:
            locked.set(); assert release.wait(5)
    with ThreadPoolExecutor(max_workers=2) as pool:
        holder = pool.submit(hold)
        assert locked.wait(2)
        before = raw_bytes(e)
        started = time.monotonic()
        future = pool.submit(candidates, e) if operation == "read" else pool.submit(adopt, e, body)
        try:
            with pytest.raises(DENIALS): future.result(timeout=2)
            assert time.monotonic() - started < 2
            assert raw_bytes(e) == before
        finally:
            release.set(); holder.result(timeout=2)


@pytest.mark.parametrize("placement", ["current", "history"])
def test_private_candidate_and_adopted_history_never_open_public_proposal_fences(lifecycle, placement):
    from test_v2_creative_director_execution_lifecycle import public_client, assert_hidden
    e = board(lifecycle); prepared, job = execute(e); candidate = candidates(e)
    if placement == "history":
        with e.raw.transaction(e.nid, e.scope) as state:
            row = state["collections"][e.documents.proposals.COLLECTION][e.row["id"]]
            row["history"].append({"model_preview": deepcopy(row["model_preview"])})
            row["model_preview"] = row["model_execution"] = None
    before = snapshot(e)
    for prefix in ("/api", "/api/v1"):
        client, base = public_client(e, prefix); headers = {"X-Session-Token": e.token}
        response = client.get(base + "/" + e.row["id"], headers=headers)
        assert response.status_code == 200
        public = response.json()
        assert public["status"] == "MODEL_UNAVAILABLE" and public["director_notes"] == []
        for action, body in {
            "review": review_body(candidate),
            "preview": {"expected_version": candidate["expected_version"], "route_id": e.route["route_id"]},
            "dispatch": {"expected_version": candidate["expected_version"], "reviewed_preview_digest": prepared["model_preview"]["preview_digest"]},
            "refresh": {"expected_version": candidate["expected_version"]},
            "cancel": {"expected_version": candidate["expected_version"]},
        }.items():
            denied = client.post(base + "/" + e.row["id"] + "/" + action, headers=headers, json=body)
            assert denied.status_code in {400, 403, 404, 409, 422}
            assert prepared["model_preview"]["prompt"] not in denied.text and e.token not in denied.text
        assert e.wire_text not in response.text and "output_schema" not in response.text
    assert snapshot(e) == before
    # History tampering deliberately invalidates the old authority; generic
    # public generation content remains hidden without invoking its capability.
    from app.jobs import generation_content_available
    assert not generation_content_available(job)


def test_retained_old_incarnation_rows_do_not_consume_current_document_quota(lifecycle, monkeypatch):
    import app.creative.service as service
    e = board(lifecycle); execute(e); body = review_body(candidates(e))
    with e.raw.transaction(e.nid, e.scope) as state:
        documents = state["collections"][e.documents.COLLECTION]
        retained = deepcopy(e.source); retained.update(id="retained-other-owner", project_incarnation="old-owner")
        documents[retained["id"]] = retained
    monkeypatch.setattr(service, "MAX_DOCUMENTS", 3)
    accepted = adopt(e, body)
    state = e.raw.read(e.nid, e.scope)
    assert state["collections"][e.documents.COLLECTION][retained["id"]] == retained
    assert accepted["document"]["status"] == "DRAFT"


def test_default_internal_preview_cannot_grant_review_even_for_valid_storyboard_json(lifecycle):
    from creative_director_execution_fixture import preview as default_preview
    e = board(lifecycle); e.wire_text = json.dumps(output(e))
    prepared = default_preview(e)
    assert "output_contract" not in prepared["model_preview"]
    receipt = dispatch(e, prepared)
    wait(e, e.manager.get(receipt["model_execution"]["job_id"]))
    body = {"expected_version": raw_proposal(e)["version"], "reviewed_output_digest": "0" * 64,
        "title": "No implicit review opt-in", "director_notes": deepcopy(e.row["director_notes"])}
    before = snapshot(e)
    with pytest.raises(ValueError, match="REVIEW_OUTPUT_CONTRACT_REQUIRED"): candidates(e)
    with pytest.raises(ValueError, match="REVIEW_OUTPUT_CONTRACT_REQUIRED"): adopt(e, body)
    assert snapshot(e) == before and raw_proposal(e)["document_id"] is None


def test_adopted_draft_is_readable_but_public_proposal_and_job_fences_stay_closed(lifecycle):
    from test_v2_creative_director_execution_lifecycle import public_client
    from app.jobs import generation_content_available
    e = board(lifecycle); prepared, job = execute(e); candidate = candidates(e)
    body = review_body(candidate); accepted = adopt(e, body); draft = accepted["document"]
    before = snapshot(e)
    assert not generation_content_available(job)
    assert e.documents.get(e.nid, e.scope, draft["id"]) == draft
    assert raw_proposal(e)["model_preview"]["output_contract"] == "STORYBOARD_SHOT_CONTEXT_V1"
    assert raw_proposal(e)["model_execution"]["job_id"] == job.id
    for prefix in ("/api", "/api/v1"):
        client, base = public_client(e, prefix); headers = {"X-Session-Token": e.token}
        responses = [client.get(base, headers=headers), client.get(base + "/" + e.row["id"], headers=headers)]
        assert all(response.status_code == 200 for response in responses)
        public = responses[-1].json()
        assert public["status"] == "MODEL_UNAVAILABLE"
        assert public["model_preview"] is None and public["model_execution"] is None and public["director_notes"] == []
        for action, request in {
            "review": body,
            "dispatch": {"expected_version": raw_proposal(e)["version"],
                "reviewed_preview_digest": prepared["model_preview"]["preview_digest"]},
            "refresh": {"expected_version": raw_proposal(e)["version"]},
        }.items():
            response = client.post(base + "/" + e.row["id"] + "/" + action, headers=headers, json=request)
            assert response.status_code in {400, 403, 404, 409, 422}
            responses.append(response)
        capabilities = client.get(base + "/model-capabilities", headers=headers)
        assert capabilities.status_code == 200
        responses.append(capabilities)
        for response in responses:
            assert prepared["model_preview"]["prompt"] not in response.text
            assert e.wire_text not in response.text and e.token not in response.text
    assert snapshot(e) == before
    # No old execution capability is invoked after the approval that revoked it.
