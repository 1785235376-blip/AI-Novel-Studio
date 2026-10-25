"""Generation admission receipts with real File owners and original JobManager.

Only worker execution is synthetic. Preparation, QUEUED persistence and thread
admission remain production code, including in independent spawned processes.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import api
from app.config import Settings
from app.idempotency import IdempotencyStore
from app.jobs import Job, JobManager
from app.main import app
from app.services import CanonService, ChapterService, ContextService, GenerationService, LoreService, NovelService
from app.repositories.factory import create_repository_bundle
from test_generation_idempotency_contracts import collaboration_generation

pytestmark = pytest.mark.file_backend_only
TIMEOUT = 20


def _install(root, monkeypatch, *, initialize=True):
    import app.jobs as jobs_module
    import app.main as main_module

    config = Settings(storage_backend="file", novel_data=root, mock_provider=True,
                      enable_collaboration_runtime=False, enable_packaged_runtime=False)
    bundle = create_repository_bundle(config, root)
    novels = NovelService(bundle.novels, bundle.chapters)
    chapters = ChapterService(bundle.chapters)
    if initialize:
        novel = novels.create({"id": "admission-book", "title": "Admission contracts"})
        chapter = chapters.create(novel["id"], {"title": "One", "content": "Original source"})
    else:
        chapter = chapters.list("admission-book")[0]
    for module in (api, jobs_module, main_module):
        monkeypatch.setattr(module, "settings", config)
    manager = JobManager(
        generations=GenerationService(bundle.generations), chapters=chapters,
        contexts=ContextService(bundle.novels, bundle.chapters, LoreService(bundle.lore)),
        canon=CanonService(bundle.canon), snapshot_required=False,
        memory_extractor=SimpleNamespace(enqueue=lambda *_: "synthetic-only"),
    )
    runs, starts = [], []
    control = SimpleNamespace(start_failure=None, before_start=None)

    def synthetic_run(job):
        runs.append(job.id)

    monkeypatch.setattr(manager, "_run", synthetic_run)
    original_start = threading.Thread.start

    def counted_start(thread):
        if getattr(thread, "_target", None) is synthetic_run:
            starts.append(thread._args[0])
            if control.before_start is not None:
                control.before_start(thread._args[0])
            if control.start_failure is not None:
                raise control.start_failure
        return original_start(thread)

    monkeypatch.setattr(threading.Thread, "start", counted_start)
    store = IdempotencyStore(root / "idempotency.json")
    for name, value in (("novel_service", novels), ("chapter_service", chapters),
                        ("jobs", manager), ("_idempotency_store", store)):
        monkeypatch.setattr(api, name, value)
    return SimpleNamespace(
        client=TestClient(app, raise_server_exceptions=False), root=root, bundle=bundle,
        novels=novels, chapters=chapters, chapter=chapter, manager=manager,
        dispatcher=manager, store=store, runs=runs, starts=starts,
        control=control, payload={"novel_id": chapter["novel_id"], "chapter_id": chapter["id"], "instruction": "Continue"},
    )


@pytest.fixture
def generation(tmp_path, monkeypatch):
    return _install(tmp_path, monkeypatch)


def _post(fixture, key="admit", payload=None):
    return fixture.client.post("/api/generate/continue", json=payload or fixture.payload,
                               headers={"Idempotency-Key": key})


def _rows(fixture):
    return json.loads(fixture.store.path.read_text()) if fixture.store.path.exists() else {}


def _only_receipt(fixture):
    rows = _rows(fixture)
    assert len(rows) == 1
    return next(iter(rows.values()))["value"]


def _denied(response, status, code):
    assert response.status_code == status, response.text
    body = response.json()
    assert body.get("code", (body.get("detail") or {}).get("code")) == code, body
    assert "job_id" not in response.text


def _accepted(response):
    assert response.status_code == 202, response.text
    result = response.json()
    assert result == {"job_id": result["job_id"], "status": "QUEUED",
                      "events_url": f"/api/generation/{result['job_id']}/events", "base_chapter_version": 1}
    assert str(UUID(result["job_id"])) == result["job_id"]
    return result


def test_reserved_receipt_precedes_original_queued_save_and_thread_start(generation, monkeypatch):
    fixture = generation
    events = []
    original_put = fixture.store.put
    original_save = fixture.bundle.generations.save
    original_prepare = fixture.manager.prepare_job
    original_start = fixture.manager.start_prepared
    prepared = []

    def prepare(*args, **kwargs):
        job = original_prepare(*args, **kwargs)
        assert type(job) is Job and job.status == "PREPARED"
        assert fixture.manager.jobs == {}
        assert list((fixture.root / "runtime/jobs").glob("*.json")) == []
        prepared.append(job)
        events.append(("prepare", job.id))
        return job

    def start(job):
        assert job is prepared[0]
        assert _only_receipt(fixture)["job_id"] == job.id
        return original_start(job)

    def put(key, value):
        events.append(("reserve" if value.get("schema_version") == 3 else "complete", value.copy()))
        if value.get("schema_version") == 3:
            assert fixture.manager.jobs == {}
            assert list((fixture.root / "runtime/jobs").glob("*.json")) == []
            assert fixture.starts == []
        return original_put(key, value)

    def save(value):
        receipt = _only_receipt(fixture)
        assert receipt["schema_version"] == 3
        assert receipt["admission_state"] == "RESERVED"
        assert receipt["job_id"] == value["id"]
        assert value["status"] == "QUEUED"
        assert fixture.starts == []
        events.append(("save", value["id"]))
        return original_save(value)

    monkeypatch.setattr(fixture.manager, "prepare_job", prepare)
    monkeypatch.setattr(fixture.manager, "start_prepared", start)
    monkeypatch.setattr(fixture.store, "put", put)
    monkeypatch.setattr(fixture.bundle.generations, "save", save)
    result = _accepted(_post(fixture))
    assert [event[0] for event in events] == ["prepare", "reserve", "save", "complete"]
    reserved = events[1][1]
    assert set(reserved) == {"schema_version", "admission_state", "project_incarnation", "request_digest", "job_id"}
    assert reserved["job_id"] == result["job_id"]
    normalized = api.GenerateIn(**fixture.payload).model_dump(exclude={"count"})
    assert reserved["request_digest"] == hashlib.sha256(
        json.dumps(normalized, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    authority = [fixture.payload["novel_id"], fixture.payload["chapter_id"], "local-author", "local", None]
    scope = hashlib.sha256(json.dumps(authority).encode()).hexdigest()
    assert set(_rows(fixture)) == {f"generate:continue:{scope}:admit"}
    assert len(fixture.starts) == 1
    assert type(fixture.starts[0]) is Job
    assert fixture.starts[0] is fixture.manager.jobs[result["job_id"]]
    complete = _only_receipt(fixture)
    assert complete == {"schema_version": 2, "project_incarnation": reserved["project_incarnation"],
                        "request_digest": reserved["request_digest"], "result": result}
    assert _accepted(_post(fixture)) == result
    assert len(fixture.starts) == 1


@pytest.mark.parametrize("phase", ["reserve", "complete"])
@pytest.mark.parametrize("committed", [False, True], ids=["before-write", "commit-then-raise"])
def test_receipt_put_failure_preserves_its_actual_durable_evidence(generation, monkeypatch, phase, committed):
    fixture = generation
    original = fixture.store.put
    failed = False

    def put(key, value):
        nonlocal failed
        matches = (value.get("schema_version") == 3) == (phase == "reserve")
        if matches and not failed:
            failed = True
            if committed:
                original(key, value)
            raise OSError("controlled private disk error")
        return original(key, value)

    monkeypatch.setattr(fixture.store, "put", put)
    _denied(_post(fixture), 503, "IDEMPOTENCY_ADMISSION_PERSISTENCE_UNCONFIRMED")
    assert len(fixture.starts) == (phase == "complete")
    before = fixture.store.path.read_bytes() if fixture.store.path.exists() else None
    if phase == "reserve" and not committed:
        assert before is None
        assert fixture.manager.jobs == {}
        result = _accepted(_post(fixture))
    elif phase == "complete" and committed:
        result = _only_receipt(fixture)["result"]
        assert _accepted(_post(fixture)) == result
        assert fixture.store.path.read_bytes() == before
    else:
        reserved = _only_receipt(fixture)
        assert reserved["schema_version"] == 3
        _denied(_post(fixture), 409, "ADMISSION_UNCONFIRMED")
        assert fixture.store.path.read_bytes() == before
        assert len(fixture.starts) == (phase == "complete")
        return
    assert len(fixture.starts) == 1
    assert fixture.starts[0].id == result["job_id"]


@pytest.mark.parametrize("committed", [False, True], ids=["before-save", "save-then-raise"])
def test_original_job_save_failure_never_rebuilds_reserved_job(generation, monkeypatch, committed):
    fixture = generation
    original = fixture.bundle.generations.save

    def save(value):
        assert _only_receipt(fixture)["job_id"] == value["id"]
        if committed:
            original(value)
        raise OSError("controlled original job save failure")

    monkeypatch.setattr(fixture.bundle.generations, "save", save)
    _denied(_post(fixture), 503, "GENERATION_ADMISSION_UNCONFIRMED")
    reserved = _only_receipt(fixture)
    assert fixture.starts == []
    assert fixture.manager.jobs == {}
    durable = list((fixture.root / "runtime/jobs").glob("*.json"))
    assert len(durable) == int(committed)
    if durable:
        assert json.loads(durable[0].read_text())["status"] == "QUEUED"
        assert durable[0].stem == reserved["job_id"]
    before = fixture.store.path.read_bytes()
    monkeypatch.setattr(fixture.bundle.generations, "save", original)
    _denied(_post(fixture), 409, "ADMISSION_UNCONFIRMED")
    assert fixture.store.path.read_bytes() == before
    assert fixture.starts == []


def test_thread_start_failure_retains_reservation_and_original_failed_job(generation):
    fixture = generation
    fixture.control.start_failure = RuntimeError("controlled Thread.start failure")
    _denied(_post(fixture), 503, "GENERATION_ADMISSION_UNCONFIRMED")
    reserved = _only_receipt(fixture)
    assert len(fixture.starts) == 1
    assert fixture.runs == []
    persisted = fixture.manager.persistence.get(reserved["job_id"])
    assert persisted["status"] == "FAILED"
    assert persisted["error_code"] == "GENERATION_START_FAILED"
    before = fixture.store.path.read_bytes()
    fixture.control.start_failure = None
    _denied(_post(fixture), 409, "ADMISSION_UNCONFIRMED")
    assert len(fixture.starts) == 1
    assert fixture.store.path.read_bytes() == before


def test_original_preparation_failure_has_no_receipt_or_job(generation):
    # Pair validation is in the original prepare_job, not the HTTP schema.
    payload = {**generation.payload, "provider_id": "synthetic-unpaired-provider"}
    _denied(_post(generation, payload=payload), 500, "GENERATION_PREPARATION_FAILED")
    assert _rows(generation) == {}
    assert generation.manager.jobs == {}
    assert generation.starts == []
    _accepted(_post(generation))
    assert len(generation.starts) == 1


def _leave_reserved(fixture, monkeypatch):
    original = fixture.store.put

    def commit_then_raise(key, value):
        assert value["schema_version"] == 3
        original(key, value)
        raise OSError("reserved but acknowledgment lost")

    with monkeypatch.context() as patch:
        patch.setattr(fixture.store, "put", commit_then_raise)
        _denied(_post(fixture), 503, "IDEMPOTENCY_ADMISSION_PERSISTENCE_UNCONFIRMED")
    return _only_receipt(fixture)


def test_reserved_without_any_original_job_is_not_a_fake_accepted_response(generation, monkeypatch):
    fixture = generation
    reserved = _leave_reserved(fixture, monkeypatch)
    assert fixture.manager.jobs == {}
    assert list((fixture.root / "runtime/jobs").glob("*.json")) == []
    before = fixture.store.path.read_bytes()
    for _ in range(3):
        response = _post(fixture)
        _denied(response, 409, "ADMISSION_UNCONFIRMED")
        assert reserved["job_id"] not in response.text
    assert fixture.store.path.read_bytes() == before
    assert fixture.starts == []


@pytest.mark.parametrize("change,code", [
    ("expired", "IDEMPOTENCY_KEY_EXPIRED"),
    ("digest", "IDEMPOTENCY_REQUEST_MISMATCH"),
    ("owner", "IDEMPOTENCY_OWNER_CHANGED"),
    ("missing-field", "IDEMPOTENCY_RECORD_UNVERIFIED"),
    ("extra-field", "IDEMPOTENCY_RECORD_UNVERIFIED"),
    ("wrong-state", "IDEMPOTENCY_RECORD_UNVERIFIED"),
    ("bool-version", "IDEMPOTENCY_RECORD_UNVERIFIED"),
    ("non-uuid", "IDEMPOTENCY_RECORD_UNVERIFIED"),
    ("non-v4-uuid", "IDEMPOTENCY_RECORD_UNVERIFIED"),
    ("bad-digest", "IDEMPOTENCY_RECORD_UNVERIFIED"),
    ("naive-time", "IDEMPOTENCY_RECORD_UNVERIFIED"),
])
def test_reserved_receipt_validation_is_fail_closed_without_mutation(generation, monkeypatch, change, code):
    fixture = generation
    _leave_reserved(fixture, monkeypatch)
    rows = _rows(fixture)
    row = next(iter(rows.values()))
    receipt = row["value"]
    if change == "expired":
        row["created_at"] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    elif change == "digest":
        receipt["request_digest"] = "a" * 64
    elif change == "owner":
        receipt["project_incarnation"] = "file:" + str(uuid4())
    elif change == "missing-field":
        receipt.pop("job_id")
    elif change == "extra-field":
        receipt["result"] = {"job_id": receipt["job_id"]}
    elif change == "wrong-state":
        receipt["admission_state"] = "QUEUED"
    elif change == "bool-version":
        receipt["schema_version"] = True
    elif change == "non-uuid":
        receipt["job_id"] = "made-up-job"
    elif change == "non-v4-uuid":
        receipt["job_id"] = "00000000-0000-1000-8000-000000000000"
    elif change == "bad-digest":
        receipt["request_digest"] = "not-a-digest"
    elif change == "naive-time":
        row["created_at"] = datetime.now().isoformat()
    fixture.store.path.write_text(json.dumps(rows))
    before = fixture.store.path.read_bytes()
    _denied(_post(fixture), 409, code)
    assert fixture.store.path.read_bytes() == before
    assert fixture.manager.jobs == {}
    assert fixture.starts == []


@pytest.mark.parametrize("phase", ["reserve", "complete"])
@pytest.mark.parametrize("change", ["archive", "owner"])
def test_source_and_owner_revalidated_after_each_persistence_boundary(generation, monkeypatch, phase, change):
    fixture = generation
    original = fixture.store.put

    def put(key, value):
        result = original(key, value)
        if (value["schema_version"] == 3) == (phase == "reserve"):
            if change == "archive":
                fixture.chapters.archive(fixture.payload["chapter_id"])
            else:
                marker = fixture.root / "novels" / fixture.payload["novel_id"] / "creative_project_v2.json"
                marker.unlink()
        return result

    monkeypatch.setattr(fixture.store, "put", put)
    response = _post(fixture)
    _denied(response, 404 if change == "archive" else 409,
            "CHAPTER_NOT_FOUND" if change == "archive" else "IDEMPOTENCY_OWNER_CHANGED")
    assert len(fixture.starts) == (phase == "complete")
    receipt = _only_receipt(fixture)
    assert receipt["schema_version"] == (3 if phase == "reserve" else 2)
    before = fixture.store.path.read_bytes()
    _post(fixture)
    assert fixture.store.path.read_bytes() == before
    assert len(fixture.starts) == (phase == "complete")


@pytest.mark.parametrize("phase", ["reserve", "complete"])
def test_real_authorization_revocation_at_receipt_boundary_is_rechecked(collaboration_generation, monkeypatch, phase):
    from app.identity import IdentityStatus

    fixture = collaboration_generation
    original = fixture.store.put

    def put(key, value):
        result = original(key, value)
        if (value["schema_version"] == 3) == (phase == "reserve"):
            fixture.identity.set_membership_status("alice", "workspace", IdentityStatus.INACTIVE)
        return result

    monkeypatch.setattr(fixture.store, "put", put)
    response = _post(fixture)
    _denied(response, 403, "FORBIDDEN")
    assert len(fixture.starts) == (phase == "complete")
    assert _only_receipt(fixture)["schema_version"] == (3 if phase == "reserve" else 2)
    before = fixture.store.path.read_bytes()
    _denied(_post(fixture), 403, "FORBIDDEN")
    assert fixture.store.path.read_bytes() == before
    assert len(fixture.starts) == (phase == "complete")


def _process_worker(connection, root, mode):
    """Independent interpreter; no inherited locks, managers or API doubles."""
    root = Path(root)
    if mode == "ordinary-put":
        store = IdempotencyStore(root / "idempotency.json")
        connection.send(("ready", None))
        store.put("ordinary-export", {"unrelated": "saved"})
        connection.send(("done", "saved"))
        connection.close()
        return
    with pytest.MonkeyPatch.context() as patch:
        fixture = _install(root, patch, initialize=False)
        original_put = fixture.store.put
        original_save = fixture.bundle.generations.save

        def put(key, value):
            result = original_put(key, value)
            if value["schema_version"] == 3:
                if mode == "reserve-exit":
                    os._exit(71)
                if mode == "pause-reserve":
                    connection.send(("reserved", value))
                    if not connection.poll(TIMEOUT):
                        raise TimeoutError("Parent did not release reserved admission")
                    assert connection.recv() == "release"
            return result

        def save(value):
            original_save(value)
            if mode == "queued-exit":
                assert value["status"] == "QUEUED"
                assert fixture.starts == []
                os._exit(72)

        patch.setattr(fixture.store, "put", put)
        patch.setattr(fixture.bundle.generations, "save", save)
        connection.send(("ready", None))
        response = _post(fixture)
        connection.send(("done", {"status": response.status_code, "body": response.json(),
                                   "starts": len(fixture.starts)}))
    connection.close()


@contextmanager
def _process(root, mode):
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=_process_worker, args=(child, str(root), mode))
    process.start()
    child.close()
    try:
        yield process, parent
    finally:
        if process.is_alive():
            process.terminate()
        process.join(TIMEOUT)
        parent.close()
        assert not process.is_alive(), "Admission worker failed to stop"


def _receive(connection, expected):
    assert connection.poll(TIMEOUT), f"Admission worker did not report {expected}"
    kind, value = connection.recv()
    assert kind == expected, (kind, value)
    return value


def _finished(process, code=0):
    process.join(TIMEOUT)
    assert process.exitcode == code


@pytest.mark.skipif(sys.platform != "linux", reason="Independent Linux File process-death evidence")
@pytest.mark.parametrize("mode,exitcode", [("reserve-exit", 71), ("queued-exit", 72)])
def test_actual_process_exit_never_replays_uncertain_admission(generation, monkeypatch, mode, exitcode):
    fixture = generation
    with _process(fixture.root, mode) as (process, connection):
        _receive(connection, "ready")
        _finished(process, exitcode)
    receipt = _only_receipt(fixture)
    assert receipt["schema_version"] == 3
    files = list((fixture.root / "runtime/jobs").glob("*.json"))
    assert len(files) == int(mode == "queued-exit")
    if files:
        assert files[0].stem == receipt["job_id"]
        assert json.loads(files[0].read_text())["status"] == "QUEUED"
    before = fixture.store.path.read_bytes()
    restarted = _install(fixture.root, monkeypatch, initialize=False)
    _denied(_post(restarted), 409, "ADMISSION_UNCONFIRMED")
    assert restarted.starts == []
    assert fixture.store.path.read_bytes() == before
    if files:
        assert restarted.manager.persistence.get(receipt["job_id"])["status"] == "FAILED"
    else:
        assert restarted.manager.jobs == {}


@pytest.mark.skipif(sys.platform != "linux", reason="Independent Linux File process-lock evidence")
def test_same_key_in_independent_processes_has_one_original_admission(generation):
    fixture = generation
    with _process(fixture.root, "pause-reserve") as (first, first_pipe):
        _receive(first_pipe, "ready")
        reserved = _receive(first_pipe, "reserved")
        with _process(fixture.root, "normal") as (second, second_pipe):
            _receive(second_pipe, "ready")
            assert not second_pipe.poll(0.3), "Second process bypassed active admission lock"
            first_pipe.send("release")
            one = _receive(first_pipe, "done")
            two = _receive(second_pipe, "done")
            assert one["status"] == two["status"] == 202
            assert one["body"] == two["body"]
            assert one["body"]["job_id"] == reserved["job_id"]
            assert one["starts"] == 1 and two["starts"] == 0
            _finished(first)
            _finished(second)
    assert len(list((fixture.root / "runtime/jobs").glob("*.json"))) == 1
    assert _only_receipt(fixture)["result"] == one["body"]


@pytest.mark.skipif(sys.platform != "linux", reason="Independent Linux File process-lock evidence")
def test_admission_callback_does_not_hold_short_json_access_lock(generation):
    fixture = generation
    with _process(fixture.root, "pause-reserve") as (admission, admission_pipe):
        _receive(admission_pipe, "ready")
        _receive(admission_pipe, "reserved")
        with _process(fixture.root, "ordinary-put") as (writer, writer_pipe):
            _receive(writer_pipe, "ready")
            assert _receive(writer_pipe, "done") == "saved"
            _finished(writer)
        # The first route remains paused after reserve put has returned. An
        # unrelated process already changed this same JSON cache successfully.
        assert admission.is_alive()
        assert not admission_pipe.poll(0.1)
        admission_pipe.send("release")
        assert _receive(admission_pipe, "done")["status"] == 202
        _finished(admission)
    rows = _rows(fixture)
    assert rows["ordinary-export"]["value"] == {"unrelated": "saved"}
    assert len(rows) == 2


def test_admission_lock_metadata_is_bounded_per_canonical_cache_path(tmp_path):
    from app.repositories.file import mutation_coordinator

    path = tmp_path / "cache.json"
    before = set(mutation_coordinator._locks)
    for index in range(100):
        # New store objects and request keys cannot add per-request locks.
        store = IdempotencyStore(tmp_path / "." / path.name)
        with store.generation_admission():
            store.put(f"generate:continue:scope:{index}", {"index": index})
    added = set(mutation_coordinator._locks) - before
    assert len(added) == 2, "Expected one admission lock and one short JSON lock"
    lock_files = list((tmp_path / ".workspace-mutation-locks").glob("*.lock"))
    assert len(lock_files) == 2
    assert len(json.loads(path.read_text())) == 100


@pytest.mark.parametrize("change", ["archive", "owner"])
def test_real_source_and_owner_change_after_original_prepare_blocks_reservation(generation, monkeypatch, change):
    fixture = generation
    original = fixture.manager.prepare_job

    def prepare(*args, **kwargs):
        job = original(*args, **kwargs)
        assert type(job) is Job and job.status == "PREPARED"
        if change == "archive":
            fixture.chapters.archive(fixture.payload["chapter_id"])
        else:
            marker = fixture.root / "novels" / fixture.payload["novel_id"] / "creative_project_v2.json"
            marker.unlink()
        return job

    monkeypatch.setattr(fixture.manager, "prepare_job", prepare)
    _denied(_post(fixture), 404 if change == "archive" else 409,
            "CHAPTER_NOT_FOUND" if change == "archive" else "IDEMPOTENCY_OWNER_CHANGED")
    assert _rows(fixture) == {}
    assert fixture.manager.jobs == {}
    assert fixture.starts == []


def test_real_authorization_change_after_original_prepare_blocks_reservation(collaboration_generation, monkeypatch):
    from app.identity import IdentityStatus

    fixture = collaboration_generation
    original = fixture.manager.prepare_job

    def prepare(*args, **kwargs):
        job = original(*args, **kwargs)
        fixture.identity.set_membership_status("alice", "workspace", IdentityStatus.INACTIVE)
        return job

    monkeypatch.setattr(fixture.manager, "prepare_job", prepare)
    _denied(_post(fixture), 403, "FORBIDDEN")
    assert _rows(fixture) == {}
    assert fixture.manager.jobs == {}
    assert fixture.starts == []


def test_http_authorization_exception_from_original_preparation_is_preserved(generation, monkeypatch):
    fixture = generation
    original_prepare = fixture.manager.prepare_job
    original_get = fixture.chapters.get
    preparing = False

    def prepare(*args, **kwargs):
        nonlocal preparing
        preparing = True
        try:
            return original_prepare(*args, **kwargs)
        finally:
            preparing = False

    def get(chapter_id):
        if preparing:
            raise HTTPException(403, {"code": "FORBIDDEN"})
        return original_get(chapter_id)

    monkeypatch.setattr(fixture.manager, "prepare_job", prepare)
    monkeypatch.setattr(fixture.chapters, "get", get)
    _denied(_post(fixture), 403, "FORBIDDEN")
    assert _rows(fixture) == {}
    assert fixture.manager.jobs == {}
    assert fixture.starts == []


def test_collaboration_reserved_without_job_still_checks_authority_without_job_lookup(collaboration_generation, monkeypatch):
    from app.identity import IdentityStatus

    fixture = collaboration_generation
    receipt = _leave_reserved(fixture, monkeypatch)
    assert fixture.manager.jobs == {}
    assert list((fixture.root / "runtime/jobs").glob("*.json")) == []
    before = fixture.store.path.read_bytes()
    # Real JobManager.get would fail: RESERVED replay must not use the full-v2
    # job-visibility path or manufacture an accepted job from this receipt.
    response = _post(fixture)
    _denied(response, 409, "ADMISSION_UNCONFIRMED")
    assert receipt["job_id"] not in response.text
    fixture.identity.set_membership_status("alice", "workspace", IdentityStatus.INACTIVE)
    _denied(_post(fixture), 403, "FORBIDDEN")
    assert fixture.store.path.read_bytes() == before
    assert fixture.starts == []


@pytest.mark.parametrize("mutation", ["different-instance", "changed-id"])
def test_original_started_job_cannot_be_replaced_before_complete_receipt(generation, monkeypatch, mutation):
    from copy import copy

    fixture = generation
    original = fixture.manager.start_prepared

    def start(job):
        started = original(job)
        assert started is job
        if mutation == "different-instance":
            return copy(started)
        started.id = str(uuid4())
        return started

    monkeypatch.setattr(fixture.manager, "start_prepared", start)
    _denied(_post(fixture), 503, "GENERATION_ADMISSION_UNCONFIRMED")
    receipt = _only_receipt(fixture)
    assert receipt["schema_version"] == 3
    assert len(fixture.starts) == 1
    assert fixture.manager.persistence.get(receipt["job_id"])["status"] == "QUEUED"
    before = fixture.store.path.read_bytes()
    _denied(_post(fixture), 409, "ADMISSION_UNCONFIRMED")
    assert len(fixture.starts) == 1
    assert fixture.store.path.read_bytes() == before
