"""Ordered creative assets and explicitly reviewed direction, File/real PostgreSQL.

Run with scripts/run_v2_checks.py and owned basetemp; model transport tests use
captured synthetic output through the real author, broker, JobManager and API.
"""
import copy
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
import time

import pytest

from test_v2_creative_foundation import rig, client, payload, public
from test_r3_mounted_contracts import mounted, prefix, checked, scoped
from test_r4_broker_mounted import broker_app, route, wait_ledger


def note(scene_id="scene-1", **extra):
    return {"id": "direction-1", "number": 1, "scene_id": scene_id, "note": "Start with a held frame",
            "shot_size": "CLOSE_UP", "camera_angle": "EYE_LEVEL", "camera_motion": "STATIC",
            "duration_seconds": 6, "emotion": "Hesitant", "pacing": "Pause after dialogue",
            "performance": "Hold eye contact", "blocking": "Confirm positions in rehearsal", **extra}


def proposal(rig):
    source = rig.service.create(rig.nid, rig.scope, rig.actor, payload(rig))
    row = rig.service.proposals.create(rig.nid, rig.scope, rig.actor,
        {"source_document_id": source["id"], "expected_source_version": source["version"]})
    return source, row


def review_body(row, **extra):
    return {"expected_version": row["version"], "reviewed_output_digest": row["output_digest"],
            "title": row["title"], "director_notes": row["director_notes"], **extra}


@pytest.mark.parametrize("mode", ["DIRECTOR", "PRODUCTION", "VIDEO_PLANNING"])
def test_modes_ordered_typed_assets_persist_and_are_editable(rig, mode):
    value = payload(rig)
    value["mode"] = mode
    value["scenes"].append({"id": "scene-2", "sequence": 2, "heading": "INT. ROOM"})
    value["scenes"].reverse()
    value["director_notes"] = [note("scene-2", id="d2", number=2), note()]
    if mode != "DIRECTOR":
        value["shots"] = [{"id": "shot-2", "number": 2, "scene_id": "scene-2", "lens": "50mm",
            "lighting": "Window light", "environment": "Dusty room", "action": "Visitor sits", "sound": "Clock ticks"},
            {"id": "shot-1", "number": 1, "scene_id": "scene-1", "sound_effect": "Legacy sound"}]
        value["video_plan"] = {"segments": [{"shot_id": "shot-2"}, {"shot_id": "shot-1"}]}
    row = rig.service.create(rig.nid, rig.scope, rig.actor, value)
    assert [s["id"] for s in row["scenes"]] == ["scene-1", "scene-2"]
    assert [n["id"] for n in row["director_notes"]] == ["direction-1", "d2"]
    assert rig.service.get(rig.nid, rig.scope, row["id"]) == row
    if mode != "DIRECTOR":
        assert row["shots"][1]["lens"] == "50mm" and row["shots"][1]["sound"] == "Clock ticks"
        assert row["shots"][0]["sound_effect"] == "Legacy sound"
        # Timeline ordering is intentional and remains separate from shot order.
        assert row["video_plan"]["segments"][0]["shot_id"] == "shot-2"
    value = public(row)
    value["director_notes"][0]["number"], value["director_notes"][1]["number"] = 2, 1
    edited = rig.service.update(rig.nid, rig.scope, rig.actor, row["id"], 1, value)
    assert [n["id"] for n in edited["director_notes"]] == ["d2", "direction-1"]


@pytest.mark.parametrize("change", [
    lambda x: x.update(director_notes=[note(), note()]),
    lambda x: x.update(director_notes=[note("unknown")]),
    lambda x: x.update(shots=[{"number": 1, "scene_id": "scene-1"}]),
    lambda x: x.update(video_plan={}),
    lambda x: x["director_notes"][0].update(blocking="x" * 4001),
])
def test_director_structure_rejects_unknown_duplicate_or_incompatible_assets(rig, change):
    value = {**payload(rig), "mode": "DIRECTOR", "director_notes": [note()]}
    change(value)
    with pytest.raises(ValueError):
        rig.service.create(rig.nid, rig.scope, rig.actor, value)
    assert not rig.service.list(rig.nid, rig.scope)


def test_existing_v1_creative_snapshot_missing_new_optional_fields_stays_readable(rig):
    row = rig.service.create(rig.nid, rig.scope, rig.actor, payload(rig))
    with rig.store.transaction(rig.nid, rig.scope) as state:
        saved = state["collections"][rig.service.COLLECTION][row["id"]]
        saved.pop("director_notes")
    reopened = rig.service.get(rig.nid, rig.scope, row["id"])
    assert reopened["version"] == 1 and "director_notes" not in reopened
    assert rig.service.export(rig.nid, rig.scope, row["id"])["document"]["title"] == row["title"]


def test_restore_is_a_new_cas_revision_and_can_restore_archived_document(rig):
    from app.services.v1_capability_service import CapabilityVersionConflict
    row = rig.service.create(rig.nid, rig.scope, rig.actor, payload(rig))
    modified = public(row); modified["title"] = "Changed"
    rig.service.update(rig.nid, rig.scope, "editor", row["id"], 1, modified)
    rig.service.archive(rig.nid, rig.scope, "editor", row["id"], 2)
    restored = rig.service.restore(rig.nid, rig.scope, "editor", row["id"], 3, 1)
    assert restored["title"] == row["title"] and restored["version"] == 4 and restored["status"] == "DRAFT"
    assert restored["created_by"] == rig.actor and restored["restored_from_version"] == 1
    assert [h["version"] for h in restored["history"]] == [1, 2, 3]
    with pytest.raises(CapabilityVersionConflict):
        rig.service.restore(rig.nid, rig.scope, "editor", row["id"], 3, 1)


def test_restore_never_rebinds_a_stale_chapter(rig):
    from app.experimental.common import StaleSourceError
    row = rig.service.create(rig.nid, rig.scope, rig.actor, payload(rig))
    rig.chapters.save(rig.chapter["id"], {"version": rig.chapter["version"], "content": "New source"})
    with pytest.raises(StaleSourceError):
        rig.service.restore(rig.nid, rig.scope, rig.actor, row["id"], 1, 1)


def test_rule_assisted_proposal_requires_human_review_and_preserves_manuscript(rig):
    before = rig.chapters.get(rig.chapter["id"])
    source, row = proposal(rig)
    assert row["status"] == "NEEDS_REVIEW" and row["provenance"]["model_called"] is False
    assert row["provenance"]["method"] == "RULE_ASSISTED"
    assert row["director_notes"][0]["blocking"] and row["director_notes"][0]["pacing"]
    assert rig.service.list(rig.nid, rig.scope) == [source]
    notes = copy.deepcopy(row["director_notes"]); notes[0]["performance"] = "Human-reviewed choice"
    result = rig.service.proposals.review(rig.nid, rig.scope, rig.actor, row["id"], review_body(row, director_notes=notes))
    document = result["document"]
    assert document["id"] != source["id"] and document["mode"] == "DIRECTOR"
    assert document["director_notes"][0]["performance"] == "Human-reviewed choice"
    assert document["source_documents"][source["id"]]["version"] == 1
    assert document["provenance"]["reviewed_by"] == rig.actor
    assert document["provenance"]["reviewed_output_digest"] != row["output_digest"]
    assert rig.chapters.get(rig.chapter["id"]) == before
    assert rig.service.get(rig.nid, rig.scope, source["id"]) == source
    assert result["proposal"]["status"] == "APPROVED"


def test_proposal_review_owner_scope_cas_digest_and_cancel_fences(rig):
    from app.services.v1_capability_service import CapabilityVersionConflict
    _, row = proposal(rig)
    with pytest.raises(FileNotFoundError):
        rig.service.proposals.get(rig.nid, rig.scope, "other", row["id"])
    with pytest.raises(FileNotFoundError):
        rig.service.proposals.review(rig.nid, rig.scope, "other", row["id"], review_body(row))
    with pytest.raises(ValueError, match="EXACT_REVIEW"):
        rig.service.proposals.review(rig.nid, rig.scope, rig.actor, row["id"], review_body(row, reviewed_output_digest="0" * 64))
    with pytest.raises(CapabilityVersionConflict):
        rig.service.proposals.review(rig.nid, rig.scope, rig.actor, row["id"], review_body(row, expected_version=2))
    cancelled = rig.service.proposals.cancel(rig.nid, rig.scope, rig.actor, row["id"], {"expected_version": 1})
    with pytest.raises(ValueError, match="NOT_REVIEWABLE"):
        rig.service.proposals.review(rig.nid, rig.scope, rig.actor, row["id"], review_body(cancelled, director_notes=row["director_notes"]))
    assert len(rig.service.list(rig.nid, rig.scope)) == 1


def test_proposal_and_derived_document_fence_source_edits_and_restart(rig):
    from app.creative.service import CreativeService
    from app.experimental.store import ExperimentalStore
    from app.experimental.common import StaleSourceError
    source, row = proposal(rig)
    reopened = CreativeService(ExperimentalStore(rig.root, rig.backend, rig.url), rig.novels, rig.chapters)
    assert reopened.proposals.get(rig.nid, rig.scope, rig.actor, row["id"]) == row
    result = reopened.proposals.review(rig.nid, rig.scope, rig.actor, row["id"], review_body(row))
    rig.service.update(rig.nid, rig.scope, rig.actor, source["id"], 1, public(source))
    with pytest.raises(StaleSourceError):
        reopened.proposals.get(rig.nid, rig.scope, rig.actor, row["id"])
    with pytest.raises(StaleSourceError):
        reopened.get(rig.nid, rig.scope, result["document"]["id"])
    assert not reopened.proposals.list(rig.nid, rig.scope, rig.actor)


def test_revocation_rolls_back_proposal_and_document_together(rig):
    source, row = proposal(rig)
    before = rig.store.read(rig.nid, rig.scope)
    calls = []
    def guard():
        calls.append(1)
        if len(calls) == 2:
            raise PermissionError("revoked")
    with pytest.raises(PermissionError):
        rig.service.proposals.review(rig.nid, rig.scope, rig.actor, row["id"], review_body(row), guard=guard)
    assert rig.store.read(rig.nid, rig.scope) == before


def test_simultaneous_reviews_commit_one_derived_document(rig):
    from app.creative.service import CreativeService
    from app.experimental.store import ExperimentalStore
    from app.services.v1_capability_service import CapabilityVersionConflict
    _, row = proposal(rig)
    barrier = Barrier(2)
    def review(_):
        service = CreativeService(ExperimentalStore(rig.root, rig.backend, rig.url), rig.novels, rig.chapters)
        barrier.wait(timeout=10)
        try:
            return service.proposals.review(rig.nid, rig.scope, rig.actor, row["id"], review_body(row))
        except CapabilityVersionConflict:
            return "CONFLICT"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(review, range(2)))
    assert sum(result == "CONFLICT" for result in results) == 1
    assert len(rig.service.list(rig.nid, rig.scope)) == 2


def test_proposal_api_authority_private_response_and_restore(rig, client):
    base = f"/api/novels/{rig.nid}/experimental/creative"
    headers = {"X-Session-Token": "owner"}
    source = checked(client.post(base + "/documents", headers=headers, json=payload(rig)), 201)
    body = {"source_document_id": source["id"], "expected_source_version": 1}
    assert client.post(base + "/director-proposals", headers={"X-Session-Token": "reader"}, json=body).status_code == 403
    row = checked(client.post(base + "/director-proposals", headers=headers, json=body), 201)
    response = client.get(base + "/director-proposals/" + row["id"], headers=headers)
    assert response.headers["cache-control"] == "no-store"
    assert checked(response)["output_digest"] == row["output_digest"]
    assert checked(client.get(base + "/capabilities", headers=headers))["user_modes"] == ["NOVEL", "SCREENPLAY", "DIRECTOR", "STORYBOARD", "PRODUCTION"]
    result = checked(client.post(base + "/director-proposals/" + row["id"] + "/review", headers=headers, json=review_body(row)))
    assert result["document"]["mode"] == "DIRECTOR"
    restored = checked(client.post(base + "/documents/" + result["document"]["id"] + "/restore", headers=headers,
        json={"expected_version": 1, "restore_version": 1}))
    assert restored["version"] == 2


@pytest.fixture
def creative_model(broker_app, monkeypatch):
    e = broker_app
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2,model_broker_v2,author_context_inspector_v2")
    service = e.experimental.creative_service
    for name, value in (("store", e.store), ("novels", e.novels), ("chapters", e.chapters)):
        monkeypatch.setattr(service, name, value)
    e.creative = service
    e.creative_base = e.base + "/creative"
    return e


def model_ready(e, monkeypatch, output=None):
    from app.runtime import runtime
    calls = []
    def stream(prompt, model, **kwargs):
        calls.append({"prompt": prompt, "model": model})
        yield output if output is not None else json.dumps({"director_notes": [note()]})
    monkeypatch.setattr(runtime.providers["mock"], "stream", stream)
    source = checked(e.client.post(e.creative_base + "/documents", headers=e.headers, json={
        "mode": "SCREENPLAY", "title": "Current screenplay", "source_chapter_ids": [e.chapter["id"]],
        "scenes": [{"id": "scene-1", "sequence": 1, "heading": "EXT. COURTYARD", "action": "The visitor waits."}]}), 201)
    row = checked(e.client.post(e.creative_base + "/director-proposals", headers=e.headers,
        json={"source_document_id": source["id"], "expected_source_version": 1}), 201)
    row = model_action(e, row, "preview", route_id=route(e)["route_id"])
    return source, row, calls


def model_action(e, row, action, **extra):
    return checked(e.client.post(e.creative_base + f'/director-proposals/{row["id"]}/{action}',
        headers=e.headers, json={"expected_version": row["version"], **extra}))


def model_dispatch(e, row):
    return model_action(e, row, "dispatch", reviewed_preview_digest=row["model_preview"]["preview_digest"])


def model_settle(e, running):
    wait_ledger(e, running["model_execution"]["reservation_id"])
    return model_action(e, running, "refresh")


def test_original_model_executor_trace_review_and_no_manuscript_acceptance(creative_model, monkeypatch):
    e = creative_model
    before = copy.deepcopy(e.chapters.get(e.chapter["id"]))
    source, row, calls = model_ready(e, monkeypatch)
    preview = row["model_preview"]
    assert not calls and not e.manager.jobs
    assert preview["author"]["request_scope"]["source_mode"] == "NONE"
    assert e.chapter["content"] not in json.dumps(preview["request"])
    assert preview["execution_available"] and preview["broker"]["chosen"]["synthetic"]
    running = model_dispatch(e, row)
    assert model_dispatch(e, row)["model_execution"]["job_id"] == running["model_execution"]["job_id"]
    result = model_settle(e, running)
    assert result["status"] == "NEEDS_REVIEW" and result["model_execution"]["status"] == "CANDIDATES"
    assert result["provenance"]["model_id"] == "mock-writer"
    assert result["provenance"]["model_version"] and result["provenance"]["parameters"]
    assert result["provenance"]["synthetic"] and len(calls) == 1
    job = e.manager.get(running["model_execution"]["job_id"])
    assert job.experimental_origin == "creative_director_model"
    assert e.client.post(e.prefix + "/generation/" + job.id + "/accept", headers=e.headers, json={}).status_code == 409
    accepted = checked(e.client.post(e.creative_base + f'/director-proposals/{row["id"]}/review', headers=e.headers,
        json=review_body(result)))
    assert accepted["document"]["provenance"]["job_id"] == job.id
    assert accepted["document"]["mode"] == "DIRECTOR"
    assert e.chapters.get(e.chapter["id"]) == before
    assert e.creative.get(e.nid, source["scope"], source["id"]) == source


@pytest.mark.parametrize("output", ["not json", '{"director_notes":[],"director_notes":[]}',
    json.dumps({"director_notes": [note(scene_id="unknown")]}),
    json.dumps({"director_notes": [note(), note()]}),
    json.dumps({"director_notes": [note(tool="execute")]}),
    json.dumps({"director_notes": [note(number=True)]}),
    json.dumps({"director_notes": [{k: v for k, v in note().items() if k != "id"}]}),
])
def test_untrusted_model_json_is_discarded_without_derived_write(creative_model, monkeypatch, output):
    e = creative_model
    _, row, calls = model_ready(e, monkeypatch, output)
    result = model_settle(e, model_dispatch(e, row))
    assert result["status"] == "MODEL_UNAVAILABLE"
    assert result["model_execution"]["status"] == "DISCARDED"
    assert result["director_notes"] == [] and len(calls) == 1
    assert len(checked(e.client.get(e.creative_base + "/documents", headers=e.headers))["items"]) == 1


def test_model_restart_loses_execution_authority_and_never_replays(creative_model, monkeypatch):
    e = creative_model
    _, row, calls = model_ready(e, monkeypatch)
    running = model_dispatch(e, row)
    result = model_settle(e, running)
    monkeypatch.setattr(e.manager, "jobs", {})
    view = checked(e.client.get(e.creative_base + f'/director-proposals/{row["id"]}', headers=e.headers))
    assert view["status"] == "MODEL_UNAVAILABLE" and not view["director_notes"] and view["model_preview"] is None
    response = e.client.post(e.creative_base + f'/director-proposals/{row["id"]}/review', headers=e.headers, json=review_body(result))
    assert response.status_code == 409
    repeated = model_dispatch(e, row)
    assert repeated["model_execution"]["job_id"] == running["model_execution"]["job_id"]
    assert not e.manager.jobs and len(calls) == 1


def test_model_source_update_blocks_review_and_reused_preview(creative_model, monkeypatch):
    e = creative_model
    source, row, calls = model_ready(e, monkeypatch)
    result = model_settle(e, model_dispatch(e, row))
    e.creative.update(e.nid, source["scope"], source["created_by"], source["id"], 1, public(source))
    response = e.client.post(e.creative_base + f'/director-proposals/{row["id"]}/review', headers=e.headers, json=review_body(result))
    assert response.status_code == 409 and "SOURCE" in response.text
    assert e.client.get(e.creative_base + f'/director-proposals/{row["id"]}', headers=e.headers).status_code == 409
    assert len(calls) == 1


def test_model_cancel_drops_late_callback_and_feature_off_hides_generation(creative_model, monkeypatch):
    e = creative_model
    _, row, _ = model_ready(e, monkeypatch)
    from app.runtime import runtime
    entered, release = Event(), Event()
    def delayed(prompt, model, **kwargs):
        entered.set()
        assert release.wait(10)
        yield json.dumps({"director_notes": [note()]})
    monkeypatch.setattr(runtime.providers["mock"], "stream", delayed)
    try:
        running = model_dispatch(e, row)
        assert entered.wait(5)
        cancelled = model_action(e, running, "cancel")
        assert cancelled["status"] == "CANCELLED"
    finally:
        release.set()
    wait_ledger(e, running["model_execution"]["reservation_id"])
    assert not checked(e.client.get(e.creative_base + f'/director-proposals/{row["id"]}', headers=e.headers))["director_notes"]
    assert e.client.post(e.creative_base + f'/director-proposals/{row["id"]}/refresh', headers=e.headers,
        json={"expected_version": cancelled["version"]}).status_code == 422
    job_id = running["model_execution"]["job_id"]
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "model_broker_v2,author_context_inspector_v2")
    assert e.client.get(e.creative_base + f'/director-proposals/{row["id"]}', headers=e.headers).status_code == 404
    response = e.client.get(e.prefix + "/generation/" + job_id, headers=e.headers)
    assert response.status_code == 404 and "director_notes" not in response.text


def test_model_budget_change_blocks_dispatch_without_paid_fallback(creative_model, monkeypatch):
    e = creative_model
    _, row, calls = model_ready(e, monkeypatch)
    checked(e.client.put(e.base + "/model-broker/budget", headers=e.headers, json={
        "expected_version": 0, "limit_microusd": 0, "max_inflight": 1, "require_known_estimate": True}))
    response = e.client.post(e.creative_base + f'/director-proposals/{row["id"]}/dispatch', headers=e.headers,
        json={"expected_version": row["version"], "reviewed_preview_digest": row["model_preview"]["preview_digest"]})
    assert response.status_code == 409
    assert not calls and not e.manager.jobs


def test_parallel_model_admission_only_creates_one_job(creative_model, monkeypatch):
    e = creative_model
    _, row, calls = model_ready(e, monkeypatch)
    body = {"expected_version": row["version"], "reviewed_preview_digest": row["model_preview"]["preview_digest"]}
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: e.client.post(e.creative_base + f'/director-proposals/{row["id"]}/dispatch',
            headers=e.headers, json=body), range(2)))
    assert all(response.status_code in {200, 409} for response in responses)
    assert any(response.status_code == 200 for response in responses)
    assert len(e.manager.jobs) == 1
    running = next(response.json() for response in responses if response.status_code == 200)
    wait_ledger(e, running["model_execution"]["reservation_id"])
    assert len(calls) == 1


def test_unknown_admission_stays_durable_and_does_not_replay(creative_model, monkeypatch):
    e = creative_model
    _, row, calls = model_ready(e, monkeypatch)
    def failed_admission(job):
        raise ValueError("SYNTHETIC_LOST_ADMISSION")
    monkeypatch.setattr(e.manager, "start_prepared", failed_admission)
    response = e.client.post(e.creative_base + f'/director-proposals/{row["id"]}/dispatch', headers=e.headers,
        json={"expected_version": row["version"], "reviewed_preview_digest": row["model_preview"]["preview_digest"]})
    assert response.status_code == 422
    unknown = checked(e.client.get(e.creative_base + f'/director-proposals/{row["id"]}', headers=e.headers))
    assert unknown["model_execution"]["status"] == "UNKNOWN" and not unknown["director_notes"]
    again = model_dispatch(e, row)
    assert again["model_execution"]["job_id"] == unknown["model_execution"]["job_id"]
    assert not e.manager.jobs and not calls
    assert len(e.broker.ledger(e.nid, e.scope, "local-author")) == 1


def test_real_generation_restart_cannot_import_saved_model_output(creative_model, monkeypatch):
    from app.jobs import JobManager
    e = creative_model
    _, row, calls = model_ready(e, monkeypatch)
    running = model_dispatch(e, row)
    wait_ledger(e, running["model_execution"]["reservation_id"])
    restarted = JobManager(generations=e.manager.persistence, chapters=e.chapters,
        contexts=e.manager.contexts, canon=e.canon, snapshot_required=False)
    monkeypatch.setattr(e.creative.proposals.generation, "manager", restarted)
    result = model_action(e, running, "refresh")
    assert result["model_execution"]["status"] == "UNKNOWN"
    assert result["status"] == "MODEL_UNAVAILABLE" and not result["director_notes"]
    assert len(calls) == 1


def test_original_token_revocation_drops_model_output_and_stream(creative_model, monkeypatch):
    from app.runtime import runtime
    e = creative_model
    _, row, _ = model_ready(e, monkeypatch)
    entered, release = Event(), Event()
    def delayed(prompt, model, **kwargs):
        entered.set()
        assert release.wait(10)
        yield json.dumps({"director_notes": [note(note="PRIVATE_REVOKED_SENTINEL")]})
    monkeypatch.setattr(runtime.providers["mock"], "stream", delayed)
    try:
        running = model_dispatch(e, row)
        assert entered.wait(5)
        e.sessions.revoke("broker-host")
    finally:
        release.set()
    job = e.manager.get(running["model_execution"]["job_id"])
    deadline = time.monotonic() + 5
    while job.status not in e.manager.terminal and time.monotonic() < deadline:
        time.sleep(.01)
    assert job.status in e.manager.terminal and job.output == ""
    projection = checked(e.client.get(e.creative_base + f'/director-proposals/{row["id"]}', headers=e.headers))
    assert projection["status"] == "MODEL_UNAVAILABLE" and not projection["director_notes"]
    assert projection["model_preview"] is None
    response = e.client.post(e.creative_base + f'/director-proposals/{row["id"]}/refresh', headers=e.headers,
        json={"expected_version": running["version"]})
    assert response.status_code == 401 and "PRIVATE_REVOKED_SENTINEL" not in response.text
    for path in (e.prefix + "/generation/" + job.id, e.prefix + "/generation/" + job.id + "/events"):
        response = e.client.get(path, headers=e.headers)
        assert response.status_code in {401, 403, 404} and "PRIVATE_REVOKED_SENTINEL" not in response.text


def test_model_output_byte_bound_is_enforced_by_original_executor(creative_model, monkeypatch):
    e = creative_model
    _, row, calls = model_ready(e, monkeypatch, "X" * 128001)
    result = model_settle(e, model_dispatch(e, row))
    job = e.manager.get(result["model_execution"]["job_id"])
    assert job.error_code == "GENERATION_OUTPUT_LIMIT" and job.output == ""
    assert result["model_execution"]["status"] == "DISCARDED" and not result["director_notes"]
    assert len(calls) == 1


def test_derived_stage_progression_is_bound_ordered_and_never_writes_sources(rig):
    from app.experimental.common import StaleSourceError
    source, row = proposal(rig)
    director = rig.service.proposals.review(rig.nid, rig.scope, rig.actor, row["id"], review_body(row))["document"]
    storyboard = rig.service.derive(rig.nid, rig.scope, rig.actor, director["id"], {"expected_version": 1, "mode": "STORYBOARD"})
    assert storyboard["mode"] == "STORYBOARD" and storyboard["shots"][0]["scene_id"] == "scene-1"
    assert storyboard["shots"][0]["director_notes"][0]["blocking"] == director["director_notes"][0]["blocking"]
    assert storyboard["shots"][0]["lens"] == storyboard["shots"][0]["lighting"] == ""
    assert storyboard["provenance"]["method"] == "STRUCTURED_DERIVATION"
    production = rig.service.derive(rig.nid, rig.scope, rig.actor, storyboard["id"], {"expected_version": 1, "mode": "PRODUCTION"})
    assert production["video_plan"]["segments"][0]["shot_id"] == storyboard["shots"][0]["id"]
    assert production["source_documents"][storyboard["id"]]["version"] == 1
    assert rig.service.get(rig.nid, rig.scope, source["id"]) == source
    assert rig.chapters.get(rig.chapter["id"]) == rig.chapter
    rig.service.update(rig.nid, rig.scope, rig.actor, director["id"], 1, public(director))
    for item in (storyboard, production):
        with pytest.raises(StaleSourceError):
            rig.service.get(rig.nid, rig.scope, item["id"])


def test_stage_derivation_rejects_wrong_mode_cas_and_revocation(rig):
    from app.services.v1_capability_service import CapabilityVersionConflict
    source, _ = proposal(rig)
    before = rig.store.read(rig.nid, rig.scope)
    with pytest.raises(ValueError, match="STAGE_INVALID"):
        rig.service.derive(rig.nid, rig.scope, rig.actor, source["id"], {"expected_version": 1, "mode": "PRODUCTION"})
    with pytest.raises(CapabilityVersionConflict):
        rig.service.derive(rig.nid, rig.scope, rig.actor, source["id"], {"expected_version": 2, "mode": "STORYBOARD"})
    calls = []
    def revoked():
        calls.append(1)
        if len(calls) == 2:
            raise PermissionError("revoked")
    with pytest.raises(PermissionError):
        rig.service.derive(rig.nid, rig.scope, rig.actor, source["id"], {"expected_version": 1, "mode": "STORYBOARD"}, reauthorize=revoked)
    assert rig.store.read(rig.nid, rig.scope) == before


def test_stage_derivation_http_contract(rig, client):
    base = f"/api/novels/{rig.nid}/experimental/creative"
    headers = {"X-Session-Token": "owner"}
    source = checked(client.post(base + "/documents", headers=headers, json=payload(rig)), 201)
    storyboard = checked(client.post(base + "/documents/" + source["id"] + "/derive", headers=headers,
        json={"expected_version": 1, "mode": "STORYBOARD"}), 201)
    production = checked(client.post(base + "/documents/" + storyboard["id"] + "/derive", headers=headers,
        json={"expected_version": 1, "mode": "PRODUCTION", "title": "Production plan"}), 201)
    assert production["title"] == "Production plan" and production["mode"] == "PRODUCTION"


@pytest.mark.parametrize("disabled", ["narrative", "all", "v1-acceptance"])
def test_broker_recovery_cancel_stops_creative_job_after_feature_off(creative_model, monkeypatch, disabled):
    """Feature OFF hides content while the original owner can still stop work."""
    from app.runtime import runtime
    e = creative_model
    _, row, _ = model_ready(e, monkeypatch)
    entered, release = Event(), Event()
    def delayed(prompt, model, **kwargs):
        entered.set()
        assert release.wait(15)
        yield json.dumps({"director_notes": [note(note="PRIVATE_RECOVERY_OUTPUT")]})
    monkeypatch.setattr(runtime.providers["mock"], "stream", delayed)
    try:
        running = model_dispatch(e, row)
        assert entered.wait(5)
        if disabled == "v1-acceptance":
            monkeypatch.setenv("V1_ACCEPTANCE_MODE", "true")
        else:
            monkeypatch.setenv("EXPERIMENTAL_FEATURES", "model_broker_v2,author_context_inspector_v2" if disabled == "narrative" else "")
        creative_url = e.creative_base + f'/director-proposals/{row["id"]}'
        assert e.client.get(creative_url, headers=e.headers).status_code == 404
        assert e.client.post(creative_url + "/cancel", headers=e.headers,
            json={"expected_version": running["version"]}).status_code == 404
        job = e.manager.get(running["model_execution"]["job_id"])
        recovery_url = e.base + "/model-broker/jobs/" + running["model_execution"]["reservation_id"]
        receipt = checked(e.client.get(recovery_url, headers=e.headers))
        assert receipt["recovery"] == "FEATURE_DISABLED_CONTENT_HIDDEN"
        assert receipt["job"] == {"id": job.id, "status": job.public()["status"], "content_available": False}
        allowed_ledger = {"id", "job_id", "version", "status", "dispatched", "currency", "cost_state", "accounted_microusd", "actual_microusd"}
        assert set(receipt["ledger"]) == allowed_ledger
        body = {"expected_version": receipt["ledger"]["version"]}
        assert e.client.post(recovery_url + "/cancel", json=body).status_code == 401
        assert not job.cancelled.is_set()
        denied = e.client.post(recovery_url + "/cancel", headers=e.headers, json={"expected_version": 999})
        assert denied.status_code == 409 and "current" not in denied.json()["detail"]
        cancelled = checked(e.client.post(recovery_url + "/cancel", headers=e.headers, json=body))
        assert cancelled["job"] == {"id": job.id, "status": "CANCELLED", "content_available": False}
        assert cancelled["recovery"] == "FEATURE_DISABLED_CONTENT_HIDDEN"
        assert set(cancelled["ledger"]) == allowed_ledger
        assert all(marker not in json.dumps(cancelled) for marker in ("PRIVATE_RECOVERY_OUTPUT", "The visitor waits", "director_notes", "prompt"))
        assert job.cancelled.is_set()
    finally:
        release.set()
    terminal = wait_ledger(e, running["model_execution"]["reservation_id"])
    assert terminal["job"]["content_available"] is False and job.status == "CANCELLED" and job.output == ""
    assert e.client.get(creative_url, headers=e.headers).status_code == 404
