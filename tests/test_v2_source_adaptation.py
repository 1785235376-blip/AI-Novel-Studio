"""Actual Creative/Author/Broker/JobManager composition with synthetic transport."""
import copy
import json
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from test_r3_mounted_contracts import mounted, prefix, checked, scoped
from test_r4_broker_mounted import broker_app, route
from test_v2_creative_workflows import creative_model


def output(e):
    return {"scenes": [{"id": "scene-adapted-1", "sequence": 1, "heading": "INT. STUDY - NIGHT",
                        "action": "A visitor pauses at the doorway."}],
            "report": {"summary": "A synthetic adaptation requiring human review.", "changes": [
                {"id": "change-1", "kind": "VISUALIZATION", "source_quote": e.chapter["content"],
                 "scene_ids": ["scene-adapted-1"], "note": "Narration becomes visible action; verify the interpretation."}]}}


def create(e, **extra):
    return checked(e.client.post(e.creative_base + "/adaptation-proposals", headers=e.headers, json={
        "chapter_id": e.chapter["id"], "expected_source_version": e.chapter["version"],
        "title": "Selected chapter adaptation", **extra}), 201)


def action(e, row, name, **extra):
    return checked(e.client.post(e.creative_base + f'/adaptation-proposals/{row["id"]}/{name}',
        headers=e.headers, json={"expected_version": row["version"], **extra}))


def ready(e, monkeypatch, text=None):
    from app.runtime import runtime
    calls = []
    def stream(prompt, model, **kwargs):
        calls.append({"prompt": prompt, "model": model})
        yield text if text is not None else json.dumps(output(e))
    monkeypatch.setattr(runtime.providers["mock"], "stream", stream)
    row = create(e)
    return action(e, row, "preview", route_id=route(e)["route_id"], allow_synthetic=True), calls


def dispatch(e, row):
    return action(e, row, "dispatch", reviewed_preview_digest=row["model_preview"]["preview_digest"])


def settle(e, row):
    job = e.manager.get(row["model_execution"]["job_id"])
    deadline = time.monotonic() + 20
    with job.condition:
        while job.status not in e.manager.terminal or job.terminal_hook_status is None:
            remaining = deadline - time.monotonic()
            assert remaining > 0, (job.public()["status"], job.error_code)
            job.condition.wait(min(remaining, .05))
    return action(e, row, "refresh")


def review(e, row, **extra):
    return e.client.post(e.creative_base + f'/adaptation-proposals/{row["id"]}/review', headers=e.headers, json={
        "expected_version": row["version"], "reviewed_output_digest": row["output_digest"],
        "title": row["title"], "output": row["output"], **extra})


def test_exact_saved_source_original_execution_and_separate_reviewed_screenplay(creative_model, monkeypatch):
    e = creative_model
    before = copy.deepcopy(e.chapters.get(e.chapter["id"]))
    row, calls = ready(e, monkeypatch)
    preview = row["model_preview"]
    assert not calls and not e.manager.jobs
    assert preview["author"]["request_scope"]["source_mode"] == "SELECTION_ONLY"
    assert preview["author"]["source"] == before["content"]
    assert before["content"] in preview["request"]["prompt"]
    assert preview["request"]["context"] == {}
    running = dispatch(e, row)
    assert dispatch(e, row)["model_execution"]["job_id"] == running["model_execution"]["job_id"]
    result = settle(e, running)
    assert result["status"] == "NEEDS_REVIEW", result
    assert result["provenance"]["synthetic"] and len(calls) == 1
    assert not e.creative.list(e.nid, row["scope"])
    job = e.manager.get(running["model_execution"]["job_id"])
    assert job.experimental_origin == "creative_adaptation_model" and job.graph_binding is None
    assert job.adaptation_binding["project_incarnation"] == row["project_incarnation"]
    assert "author_preparation_guard" not in job.public()
    for path in ("", "/events"):
        assert e.client.get(e.prefix + "/generation/" + job.id + path, headers=e.headers).status_code == 404
    assert e.client.post(e.prefix + "/generation/" + job.id + "/accept", headers=e.headers, json={}).status_code == 404
    broker_view = checked(e.client.get(e.base + "/model-broker/jobs/" + running["model_execution"]["reservation_id"], headers=e.headers))
    assert broker_view["job"]["content_available"] is False and "output" not in broker_view["job"]
    accepted = checked(review(e, result))
    document = accepted["document"]
    assert document["mode"] == "SCREENPLAY" and document["version"] == 1
    assert document["scenes"][0]["source_chapter_id"] == e.chapter["id"]
    assert document["provenance"]["difference_report"] == result["output"]["report"]
    assert document["provenance"]["prompt"] == preview["request"]["prompt"]
    assert e.chapters.get(e.chapter["id"]) == before
    assert review(e, result).status_code == 409
    assert len(e.creative.list(e.nid, row["scope"])) == 1


@pytest.mark.parametrize("kind", ["invalid", "duplicate-key", "missing-id", "foreign-quote", "unknown-scene", "tool", "nan"])
def test_invalid_model_output_is_discarded_without_screenplay(creative_model, monkeypatch, kind):
    e = creative_model
    value = output(e)
    if kind == "missing-id": value["scenes"][0].pop("id")
    elif kind == "foreign-quote": value["report"]["changes"][0]["source_quote"] = "NOT IN SOURCE"
    elif kind == "unknown-scene": value["report"]["changes"][0]["scene_ids"] = ["not-a-scene"]
    elif kind == "tool": value["apply"] = "overwrite manuscript"
    text = {"invalid": "not json", "duplicate-key": '{"scenes":[],"scenes":[]}', "nan": '{"scenes":NaN}'}.get(kind, json.dumps(value))
    row, calls = ready(e, monkeypatch, text)
    result = settle(e, dispatch(e, row))
    assert result["status"] == "MODEL_UNAVAILABLE" and result["model_execution"]["status"] == "DISCARDED"
    assert result["output"] is None and len(calls) == 1
    assert not e.creative.list(e.nid, row["scope"])


def test_synthetic_requires_explicit_permission_and_preview_never_executes(creative_model):
    e = creative_model
    row = create(e)
    result = e.client.post(e.creative_base + f'/adaptation-proposals/{row["id"]}/preview', headers=e.headers,
        json={"expected_version": row["version"], "route_id": route(e)["route_id"]})
    assert result.status_code == 422
    assert not e.manager.jobs
    assert e.broker.budget(e.nid, row["scope"])["inflight"] == 0


def test_source_change_and_restart_never_replay_or_adopt(creative_model, monkeypatch):
    e = creative_model
    row, calls = ready(e, monkeypatch)
    result = settle(e, dispatch(e, row))
    monkeypatch.setattr(e.manager, "jobs", {})
    view = checked(e.client.get(e.creative_base + f'/adaptation-proposals/{row["id"]}', headers=e.headers))
    assert view["output"] is None and view["model_preview"] is None
    assert review(e, result).status_code == 409
    assert dispatch(e, row)["model_execution"]["job_id"] == result["model_execution"]["job_id"]
    assert len(calls) == 1 and not e.manager.jobs
    checked(e.client.put(e.prefix + f'/chapters/{e.chapter["id"]}', json={"version": e.chapter["version"], "content": "Changed source"}))
    assert e.client.get(e.creative_base + f'/adaptation-proposals/{row["id"]}', headers=e.headers).status_code == 409
    assert not e.creative.list(e.nid, row["scope"])


def test_private_routes_require_host_and_exact_actor_scope(creative_model, monkeypatch):
    e = creative_model
    assert e.client.get(e.creative_base + "/adaptation-proposals").status_code == 401
    e = scoped(e, monkeypatch)
    from app.services.branch_manuscript_service import BranchManuscriptService
    from app.experimental.ux import ReadContext
    import app.dependencies as dependencies
    monkeypatch.setattr(dependencies, "membership_authorization_service", e.membership)
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2,model_broker_v2,author_context_inspector_v2,branch_manuscript_v1")
    owner = BranchManuscriptService(e.store, e.novels, e.chapters, e.scopes)
    monkeypatch.setattr(e.chapters, "branch_authority", owner.for_scope, raising=False)
    monkeypatch.setattr(e.novels, "branch_authority", owner.for_scope, raising=False)
    e.chapter = owner.create(ReadContext(e.nid, e.scope, e.lead, e.lead, e.branch),
        {"title": "Owned branch source", "content": "The branch visitor waits."})
    # A collaboration role is not local Host provenance. Exercise the original
    # branch/actor data owner directly, while the HTTP model surface fails closed.
    row = e.creative.adaptations.create(e.nid, e.scope, e.lead, {
        "chapter_id": e.chapter["id"], "expected_source_version": e.chapter["version"],
        "title": "Private branch proposal"})
    assert e.creative.adaptations.get(e.nid, e.scope, e.lead, row["id"])["id"] == row["id"]
    with pytest.raises(FileNotFoundError):
        e.creative.adaptations.get(e.nid, e.scope, e.viewer, row["id"])
    assert e.creative.adaptations.list(e.nid, e.scope, e.viewer) == []
    assert checked(e.client.get(e.creative_base + "/capabilities", headers=e.headers))["source_adaptation"] == "HOST_SESSION_REQUIRED"
    for path in ("/adaptation-proposals", f'/adaptation-proposals/{row["id"]}', "/adaptation-proposals/model-routes"):
        assert e.client.get(e.creative_base + path, headers=e.headers).status_code == 403
    assert e.client.post(e.creative_base + "/adaptation-proposals", headers=e.viewer_headers, json={
        "chapter_id": e.chapter["id"], "expected_source_version": 1, "title": "No write"}).status_code == 403
    e.authorization.revoke_role(e.role, e.lead)
    assert e.client.get(e.creative_base + f'/adaptation-proposals/{row["id"]}', headers=e.headers).status_code == 403
    assert not e.manager.jobs


def test_parallel_dispatch_and_review_create_one_job_and_one_screenplay(creative_model, monkeypatch):
    e = creative_model
    row, calls = ready(e, monkeypatch)
    body = {"expected_version": row["version"], "reviewed_preview_digest": row["model_preview"]["preview_digest"]}
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(lambda _: e.client.post(e.creative_base + f'/adaptation-proposals/{row["id"]}/dispatch',
            headers=e.headers, json=body), range(2)))
    assert all(reply.status_code in {200, 409} for reply in replies)
    result = settle(e, next(reply.json() for reply in replies if reply.status_code == 200))
    assert len(e.manager.jobs) == len(calls) == 1
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(lambda _: review(e, result), range(2)))
    assert sorted(reply.status_code for reply in replies) == [200, 409]
    assert len(e.creative.list(e.nid, row["scope"])) == 1


@pytest.mark.parametrize("change", ["cancel", "source", "flags", "binding", "same_binding_aba", "replace_host"])
def test_late_output_cannot_cross_revoked_authority(creative_model, monkeypatch, change):
    e = creative_model
    row, _ = ready(e, monkeypatch)
    from app.runtime import runtime
    entered, release = Event(), Event()
    def delayed(prompt, model, **kwargs):
        entered.set()
        assert release.wait(15), "bounded synthetic provider was not released"
        yield json.dumps(output(e))
    monkeypatch.setattr(runtime.providers["mock"], "stream", delayed)
    try:
        running = dispatch(e, row)
        assert entered.wait(5)
        job = e.manager.get(running["model_execution"]["job_id"])
        # The slow call holds no scope transaction: an independent draft write succeeds.
        second = create(e, title="Independent proposal while model waits")
        assert second["status"] == "DRAFT"
        if change == "cancel": action(e, running, "cancel")
        elif change == "source": checked(e.client.put(e.prefix + f'/chapters/{e.chapter["id"]}', json={"version": 1, "content": "New saved source"}))
        elif change == "flags": monkeypatch.setenv("EXPERIMENTAL_FEATURES", "model_broker_v2,author_context_inspector_v2")
        elif change == "binding": job.adaptation_binding["preview_digest"] = "f" * 64
        else:
            from app.actor_context import SessionContext
            session = e.sessions.resolve("broker-host").session
            e.sessions.revoke("broker-host")
            e.sessions.register("broker-host", session if change == "same_binding_aba" else
                SessionContext("replacement-session", "replacement-client", "replacement-actor", "replacement-workspace"))
    finally:
        release.set()
    deadline = time.monotonic() + 20
    while job.terminal_hook_status is None:
        assert time.monotonic() < deadline
        time.sleep(.02)
    assert job.status in {"CANCELLED", "FAILED"} and job.output == ""
    assert not e.creative.list(e.nid, row["scope"])
    assert e.client.get(e.prefix + "/generation/" + job.id, headers=e.headers).status_code == 404


def test_settling_refresh_is_read_only_and_then_adopts_exact_terminal_pair(creative_model, monkeypatch):
    e = creative_model
    row, _ = ready(e, monkeypatch)
    entered, release = Event(), Event()
    finalize = e.broker.finalize
    def settling(*args, **kwargs):
        entered.set()
        assert release.wait(15)
        return finalize(*args, **kwargs)
    monkeypatch.setattr(e.broker, "finalize", settling)
    try:
        running = dispatch(e, row)
        assert entered.wait(5)
        before = e.creative.store.read(e.nid, row["scope"])
        for _ in range(3):
            observed = action(e, running, "refresh")
            assert observed["version"] == running["version"] and observed["status"] == "GENERATING"
        assert e.creative.store.read(e.nid, row["scope"]) == before
    finally:
        release.set()
    result = settle(e, running)
    assert result["status"] == "NEEDS_REVIEW"
    assert action(e, result, "refresh") == result


def test_unconfirmed_settlement_cannot_publish_partial_output(creative_model, monkeypatch):
    e = creative_model
    row, calls = ready(e, monkeypatch)
    def fail(*args, **kwargs): raise OSError("synthetic storage failure")
    monkeypatch.setattr(e.broker, "finalize", fail)
    running = dispatch(e, row)
    result = settle(e, running)
    job = e.manager.get(running["model_execution"]["job_id"])
    assert job.status == "FAILED" and job.output == "" and job.terminal_hook_status == "FAILED_RECONCILIATION_REQUIRED"
    assert result["status"] == "MODEL_UNAVAILABLE" and result["output"] is None and len(calls) == 1
    assert not e.creative.list(e.nid, row["scope"])


def test_durable_job_binding_cannot_be_changed_or_removed(creative_model, monkeypatch):
    e = creative_model
    row, _ = ready(e, monkeypatch)
    result = settle(e, dispatch(e, row))
    job = e.manager.get(result["model_execution"]["job_id"])
    saved = copy.deepcopy(job.public())
    from app.repositories.generation_repository import GenerationProjectIdentityError
    for field in ("adaptation_binding", "expected_request_digest", "novel_id"):
        changed = copy.deepcopy(saved)
        if field == "adaptation_binding":
            changed.pop(field); changed["experimental_origin"] = "author_context"
        elif field == "novel_id": changed[field] = "unrelated-project"
        else: changed[field] = "f" * 64
        with pytest.raises(GenerationProjectIdentityError): e.bundle.generations.save(changed)
    assert e.bundle.generations.get(job.id)["adaptation_binding"] == saved["adaptation_binding"]


def test_exact_serialized_history_budget_is_reserved_before_inference(creative_model, monkeypatch):
    e = creative_model
    row, calls = ready(e, monkeypatch)
    from app.experimental.store import canonical
    proposals = e.creative.adaptations
    stored = proposals._owned(e.nid, row["scope"], row["created_by"], row["id"])
    monkeypatch.setattr(proposals, "MAX_RECORD_BYTES", len(canonical(stored).encode("utf-8")) + 1000)
    before = e.creative.store.read(e.nid, row["scope"])
    response = e.client.post(e.creative_base + f'/adaptation-proposals/{row["id"]}/dispatch', headers=e.headers,
        json={"expected_version": row["version"], "reviewed_preview_digest": row["model_preview"]["preview_digest"]})
    assert response.status_code == 422 and "ADAPTATION_HISTORY_CAPACITY" in response.text
    assert not e.manager.jobs and not calls
    assert e.creative.store.read(e.nid, row["scope"]) == before


@pytest.mark.parametrize("publication_write", [1, 2], ids=["settlement-write", "final-notification-write"])
def test_terminal_persistence_in_flight_cannot_publish_or_adopt(creative_model, monkeypatch, publication_write):
    """A successful ledger is insufficient until the original worker publishes."""
    e = creative_model
    row, calls = ready(e, monkeypatch)
    entered, release = Event(), Event()
    original = e.manager._persist
    writes = 0
    def blocked(job):
        nonlocal writes
        if job.status == "COMPLETED" and job.terminal_hook_status == "COMPLETED":
            writes += 1
            if writes == publication_write:
                entered.set()
                assert release.wait(15), "test publication barrier was not released"
                raise OSError("synthetic terminal publication failure")
        return original(job)
    monkeypatch.setattr(e.manager, "_persist", blocked)
    running = dispatch(e, row)
    job = e.manager.get(running["model_execution"]["job_id"])
    try:
        assert entered.wait(10), "worker did not reach the controlled publication boundary"
        response = e.client.post(e.creative_base + f'/adaptation-proposals/{row["id"]}/refresh',
            headers=e.headers, json={"expected_version": running["version"]})
        result = checked(response)
        if result.get("output") is not None:
            # On the old implementation this is a real successful write before
            # the worker reports its injected persistence failure.
            checked(review(e, result))
        assert result["status"] == "GENERATING" and result["output"] is None
        assert not e.creative.list(e.nid, row["scope"])
    finally:
        release.set()
        deadline = time.monotonic() + 20
        with job.condition:
            while job.status not in e.manager.terminal or job.terminal_hook_status is None:
                remaining = deadline - time.monotonic()
                assert remaining > 0
                job.condition.wait(min(remaining, .05))
    assert job.status == "FAILED" and job.output == "" and len(calls) == 1
    assert not e.creative.list(e.nid, row["scope"])


def test_cancel_between_reservation_and_attachment_releases_only_undispatched_hold(creative_model, monkeypatch):
    e = creative_model
    row, calls = ready(e, monkeypatch)
    entered, release = Event(), Event()
    original = e.broker.reserve
    reserved = []
    def blocked(*args, **kwargs):
        result = original(*args, **kwargs)
        reserved.append(result)
        entered.set()
        assert release.wait(15), "test reservation barrier was not released"
        return result
    monkeypatch.setattr(e.broker, "reserve", blocked)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(lambda: e.client.post(e.creative_base + f'/adaptation-proposals/{row["id"]}/dispatch',
            headers=e.headers, json={"expected_version": row["version"], "reviewed_preview_digest": row["model_preview"]["preview_digest"]}))
        try:
            assert entered.wait(10)
            latest = checked(e.client.get(e.creative_base + f'/adaptation-proposals/{row["id"]}', headers=e.headers))
            cancelled = action(e, latest, "cancel")
            assert cancelled["status"] == "CANCELLED"
        finally:
            release.set()
        assert pending.result(timeout=20).status_code in {409, 422}
    ledger = e.broker.get(e.nid, row["scope"], e.broker.LEDGER, reserved[0]["id"])
    assert ledger["status"] == "RELEASED" and ledger["dispatched"] is False
    assert e.broker.budget(e.nid, row["scope"])["inflight"] == 0
    latest = checked(e.client.get(e.creative_base + f'/adaptation-proposals/{row["id"]}', headers=e.headers))
    assert latest["model_execution"]["reservation_id"] == ledger["id"]
    assert latest["model_execution"]["accounting"]["status"] == "RELEASED"
    assert not calls and not e.manager.jobs


def test_final_notification_pending_is_readonly_then_original_result_becomes_reviewable(creative_model, monkeypatch):
    e = creative_model
    row, calls = ready(e, monkeypatch)
    entered, release = Event(), Event()
    original = e.manager._persist
    writes = 0
    def blocked(job):
        nonlocal writes
        if job.status == "COMPLETED" and job.terminal_hook_status == "COMPLETED":
            writes += 1
            if writes == 2:
                entered.set()
                assert release.wait(15)
        return original(job)
    monkeypatch.setattr(e.manager, "_persist", blocked)
    running = dispatch(e, row)
    try:
        assert entered.wait(10)
        before = e.creative.store.read(e.nid, row["scope"])
        for _ in range(3):
            pending = action(e, running, "refresh")
            assert pending == running
        assert e.creative.store.read(e.nid, row["scope"]) == before
    finally:
        release.set()
    completed = settle(e, running)
    assert completed["status"] == "NEEDS_REVIEW" and len(calls) == 1
    checked(review(e, completed))
    assert len(e.creative.list(e.nid, row["scope"])) == 1


def test_durable_output_disagreement_prevents_adoption(creative_model, monkeypatch):
    e = creative_model
    row, calls = ready(e, monkeypatch)
    result = settle(e, dispatch(e, row))
    job = e.manager.get(result["model_execution"]["job_id"])
    saved = e.manager.persistence.get(job.id)
    e.manager.persistence.save({**saved, "output": "different persisted text"})
    assert review(e, result).status_code == 409
    view = checked(e.client.get(e.creative_base + f'/adaptation-proposals/{row["id"]}', headers=e.headers))
    assert view["output"] is None and not e.creative.list(e.nid, row["scope"])
    assert len(calls) == 1


def test_capability_does_not_mount_private_adaptation_without_host_authority(creative_model):
    e = creative_model
    ordinary = checked(e.client.get(e.creative_base + '/capabilities'))
    assert ordinary['enabled'] and ordinary['can_mutate']
    assert ordinary['source_adaptation'] == 'HOST_SESSION_REQUIRED'
    trusted = checked(e.client.get(e.creative_base + '/capabilities', headers=e.headers))
    assert trusted['source_adaptation'] == 'REVIEWED_LOCAL_MODEL'
    assert e.client.get(e.creative_base + '/adaptation-proposals').status_code == 401
    assert checked(e.client.get(e.creative_base + '/documents')) == {'items': []}


def test_host_binding_aba_during_preparation_never_reserves_or_executes(creative_model, monkeypatch):
    e = creative_model
    row, calls = ready(e, monkeypatch)
    preparer = e.creative.adaptations.generation.preparer
    prepare = preparer.prepare_author
    def rotate(*args, **kwargs):
        prepared = prepare(*args, **kwargs)
        session = e.sessions.resolve("broker-host").session
        e.sessions.revoke("broker-host")
        e.sessions.register("broker-host", session)
        return prepared
    monkeypatch.setattr(preparer, "prepare_author", rotate)
    result = e.client.post(e.creative_base + f'/adaptation-proposals/{row["id"]}/dispatch',
        headers=e.headers, json={"expected_version": row["version"],
        "reviewed_preview_digest": row["model_preview"]["preview_digest"]})
    assert result.status_code in {401, 403}, result.text
    assert not calls and not e.manager.jobs
    assert e.broker.budget(e.nid, row["scope"])["inflight"] == 0
