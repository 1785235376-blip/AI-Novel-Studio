"""Adversarial original-File publication boundaries, with no public authority.

Run only after source freeze through scripts/run_v2_checks.py, using an owned
profile and basetemp. Separate Python writers inherit that clean profile and use the
same original File repository and OS-backed workspace locks as the worker.
"""
from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from threading import Event

import pytest
from fastapi import HTTPException

from app.creative.director_terminal_evidence import FIELD
from app.jobs import JobManager, generation_content_available
from app.services.generation_service import GenerationService
from creative_director_execution_fixture import (
    TEXT, ForbiddenOwner, lifecycle, preview, raw_proposal, result, wait,
)

pytestmark = pytest.mark.file_backend_only
DENIALS = (ValueError, HTTPException, PermissionError, FileNotFoundError, KeyError)


def _run_opted_in(e):
    prepared = preview(e)
    try:
        receipt = e.coordinator._dispatch_independent(e.ctx, prepared["id"], {
            "expected_version": prepared["version"],
            "reviewed_preview_digest": prepared["model_preview"]["preview_digest"],
        }, e.guard, host_authority=e.authority, terminal_evidence=True)
    except DENIALS:
        if len(e.manager.jobs) != 1:
            raise
        receipt = raw_proposal(e)
    job = e.manager.get(receipt["model_execution"]["job_id"])
    return wait(e, job)


def _ledger(e):
    return e.broker.ledger(e.nid, e.scope, e.actor)


def _reopen(e):
    forbidden = ForbiddenOwner()
    return JobManager(GenerationService(e.persistence.repository), forbidden,
        forbidden, forbidden, memory_extractor=forbidden, snapshot_required=True,
        collaboration_updates=forbidden)


class _DiskEvent:
    """Owned temporary files avoid socket servers and platform SemLock resources."""
    def __init__(self, path):
        self.path = Path(path)

    def set(self):
        self.path.touch()

    def is_set(self):
        return self.path.exists()

    def wait(self, timeout):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.is_set():
                return True
            time.sleep(.01)
        return self.is_set()


def _file_writer_main(root, controls):
    """Separate Python writer observes the actual OS-lock acquisition boundary."""
    import app.repositories.generation_repository as repository_module
    import app.repositories.file.mutation_coordinator as locks
    from app.repositories.file.generation import FileGenerationRepository

    controls = Path(controls)
    item = json.loads((controls / "item.json").read_text(encoding="utf-8"))
    attempted, acquired, release, wrote = [
        _DiskEvent(controls / name) for name in ("attempted", "acquired", "release", "wrote")]
    repository = FileGenerationRepository(Path(root))
    leaf = hashlib.sha256(repository._write_key(repository._job_path(item["id"])).encode()).hexdigest() + ".lock"
    original_lock, original_write = locks._lock_file, repository_module.atomic_write

    def observed_lock(handle):
        if Path(handle.name).name != leaf:
            return original_lock(handle)
        attempted.set()
        original_lock(handle)
        acquired.set()
        if not release.wait(15):
            raise AssertionError("Parent did not release the acquired generation leaf")

    def observed_write(path, value, *args, **kwargs):
        if Path(path) == repository.root / (item["id"] + ".json"):
            wrote.set()
        return original_write(path, value, *args, **kwargs)

    locks._lock_file = observed_lock
    repository_module.atomic_write = observed_write
    try:
        repository.save(item)
        outcome = {"outcome": "saved", "pid": os.getpid()}
    except BaseException as exc:
        outcome = {"outcome": "rejected", "pid": os.getpid(),
                   "type": type(exc).__name__, "message": str(exc)}
    (controls / "outcome.json").write_text(json.dumps(outcome), encoding="utf-8")


def _stop_children(children, releases):
    for release in releases:
        release.set()
    for child in children:
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
        assert child.poll() is not None, "Separate generation writer leaked"


@pytest.mark.parametrize("first", ["bound", "stale_unbound"])
def test_two_process_file_saves_share_leaf_in_both_orders(lifecycle, first):
    e = lifecycle
    job = _run_opted_in(e)
    assert job.status == "COMPLETED" and result(e)["text"] == TEXT
    saved = e.persistence.get(job.id)
    evidence = deepcopy(saved[FIELD])
    bound = deepcopy(saved)
    bound.pop(FIELD)
    bound.update(status="FAILED", output="", error="Later ordinary state update")
    stale = deepcopy(bound)
    stale.pop("creative_director_binding")
    stale.pop("expected_request_digest")
    stale.update(operation="writer", experimental_origin=None, actor_id=None, scope=None)
    items = {"bound": bound, "stale_unbound": stale}
    order = [first, "stale_unbound" if first == "bound" else "bound"]
    source = Path(__file__).resolve()
    assert Path(os.environ["PROJECT_ROOT"]).resolve() == source.parents[1]
    assert os.environ["PYTHONDONTWRITEBYTECODE"] == "1"
    processes, releases, logs, observations, controls = [], [], [], {}, {}
    bootstrap = ("import runpy,sys;sys.path.insert(0,sys.argv[1]);"
                 "scope=runpy.run_path(sys.argv[2]);"
                 "scope['_file_writer_main'](sys.argv[3],sys.argv[4])")
    try:
        for kind in order:
            folder = e.root / "process-controls" / kind
            folder.mkdir(parents=True)
            controls[kind] = folder
            (folder / "item.json").write_text(json.dumps(items[kind]), encoding="utf-8")
            attempted, acquired, release, wrote = [
                _DiskEvent(folder / name) for name in ("attempted", "acquired", "release", "wrote")]
            log = (folder / "child.log").open("w", encoding="utf-8")
            logs.append(log)
            process = subprocess.Popen([sys.executable, "-B", "-c", bootstrap,
                str(source.parent), str(source), str(e.root), str(folder)],
                cwd=source.parents[1], env=os.environ.copy(), stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT)
            processes.append(process)
            releases.append(release)
            observations[kind] = (attempted, acquired, wrote)
            assert attempted.wait(10), "Writer never reached the actual leaf lock: " + (folder / "child.log").read_text()
            if kind == first:
                assert acquired.wait(10), "First writer never acquired the generation leaf"
            else:
                assert not acquired.wait(.2), "Second process acquired an already held OS leaf lock"
                assert not wrote.is_set(), "Second process wrote through the held leaf"
        assert processes[0].pid != processes[1].pid
        assert all(not observation[2].is_set() for observation in observations.values())
        releases[0].set()
        assert observations[order[1]][1].wait(10), "Waiting writer did not acquire after release"
        releases[1].set()
        outcomes = {}
        for kind, process in zip(order, processes):
            process.wait(timeout=10)
            assert process.returncode == 0, (controls[kind] / "child.log").read_text()
            outcomes[kind] = json.loads((controls[kind] / "outcome.json").read_text())
            assert outcomes[kind]["pid"] == process.pid != os.getpid()
        assert outcomes["bound"]["outcome"] == "saved"
        assert outcomes["stale_unbound"]["outcome"] == "rejected"
        assert outcomes["stale_unbound"]["type"] == "GenerationProjectIdentityError"
        assert observations["bound"][2].is_set()
        assert not observations["stale_unbound"][2].is_set()
    finally:
        _stop_children(processes, releases)
        for log in logs:
            log.close()
    durable = e.persistence.get(job.id)
    assert durable[FIELD] == evidence
    assert durable["creative_director_binding"] == saved["creative_director_binding"]
    assert durable["status"] == "FAILED" and durable["output"] == ""
    reopened = _reopen(e).get(job.id)
    assert not generation_content_available(reopened)
    assert reopened.creative_execution_authority is None
    assert len(e.requests) == 1 and len(_ledger(e)) == 1


@pytest.mark.parametrize("boundary", ["before_write", "after_replace", "leaf_unwind"])
def test_publication_storage_ambiguity_never_retries_or_erases_history(lifecycle, monkeypatch, boundary):
    import app.repositories.generation_repository as repository_module
    e = lifecycle
    repository = e.persistence.repository
    original_write = repository_module.atomic_write
    import app.repositories.file.mutation_coordinator as locks
    original_mutation = locks.workspace_mutation
    original_save = repository.save
    original_finalize = e.broker.finalize
    publication_writes, finalized, cleanup_saves = [], [], []
    ambiguous = Event()

    def write(path, value, *args, **kwargs):
        document = json.loads(value)
        if FIELD not in document:
            return original_write(path, value, *args, **kwargs)
        publication_writes.append(deepcopy(document))
        if boundary == "before_write":
            ambiguous.set()
            raise OSError("Injected failure before generation replacement")
        response = original_write(path, value, *args, **kwargs)
        if boundary == "after_replace":
            ambiguous.set()
            raise OSError("Injected ambiguous error after actual atomic replacement")
        return response

    @contextmanager
    def mutation(root, key):
        with original_mutation(root, key):
            yield
        if (boundary == "leaf_unwind" and str(key).startswith("generation-write:")
                and publication_writes and not ambiguous.is_set()):
            ambiguous.set()
            raise OSError("Injected unwind after actual generation leaf release")

    def save(item):
        if ambiguous.is_set():
            cleanup_saves.append(deepcopy(item))
        return original_save(item)

    def finalize(*args, **kwargs):
        finalized.append(1)
        return original_finalize(*args, **kwargs)

    monkeypatch.setattr(repository_module, "atomic_write", write)
    monkeypatch.setattr(locks, "workspace_mutation", mutation)
    monkeypatch.setattr(repository, "save", save)
    monkeypatch.setattr(e.broker, "finalize", finalize)
    job = _run_opted_in(e)
    assert ambiguous.is_set() and len(publication_writes) == 1
    assert job.status == "FAILED" and job.output == ""
    assert job.creative_execution_authority.publication_state == "UNKNOWN"
    assert cleanup_saves == []
    assert finalized == [1] and len(e.requests) == 1
    assert len(_ledger(e)) == 1 and _ledger(e)[0]["status"] == "SETTLED"
    assert not generation_content_available(job)
    with pytest.raises(DENIALS):
        result(e)
    durable = e.persistence.get(job.id)
    if boundary == "before_write":
        assert FIELD not in durable
    else:
        assert durable[FIELD] == publication_writes[0][FIELD]
    before = deepcopy(durable)
    reopened = _reopen(e).get(job.id)
    assert reopened.creative_execution_authority is None
    assert not generation_content_available(reopened)
    assert e.persistence.get(job.id) == before
    assert cleanup_saves == [] and finalized == [1] and len(e.requests) == 1


@pytest.mark.parametrize("change", ["source", "host", "cancel", "deadline"])
def test_final_post_emit_bounds_precede_private_publication(lifecycle, monkeypatch, change):
    from app.creative import generation
    e = lifecycle
    if change == "deadline":
        monkeypatch.setattr(generation, "TIMEOUT_SECONDS", 2)
    original_emit = e.manager._emit
    publications, mutations = [], []
    original_publish = e.persistence.repository._publish_director_terminal

    def publish(*args, **kwargs):
        publications.append(1)
        return original_publish(*args, **kwargs)

    def emit(job, *args, **kwargs):
        response = original_emit(job, *args, **kwargs)
        if job.status != "COMPLETED" or job.terminal_hook_status != "COMPLETED" or mutations:
            return response
        assert FIELD not in e.persistence.get(job.id), "Earlier COMPLETED became evidence"
        mutations.append(change)
        if change == "host":
            e.sessions.revoke(e.token)
        elif change == "cancel":
            e.manager.cancel(job.id)
        elif change == "source":
            with e.raw.transaction(e.nid, e.scope) as state:
                state["collections"][e.documents.COLLECTION][e.source["id"]]["title"] = "Changed after completed emit"
        else:
            remaining = (datetime.fromisoformat(job.generation_deadline) - datetime.now(timezone.utc)).total_seconds()
            assert 0 < remaining <= 2
            Event().wait(remaining + .03)
        return response

    monkeypatch.setattr(e.manager, "_emit", emit)
    monkeypatch.setattr(e.persistence.repository, "_publish_director_terminal", publish)
    job = _run_opted_in(e)
    assert mutations == [change] and publications == []
    assert job.status == "FAILED" and not job.output
    assert FIELD not in e.persistence.get(job.id)
    assert len(e.requests) == 1 and len(_ledger(e)) == 1
    assert _ledger(e)[0]["status"] == "SETTLED"
    with pytest.raises(DENIALS):
        result(e)


def test_default_private_execution_and_restart_remain_legacy(lifecycle):
    from creative_director_execution_fixture import run
    e = lifecycle
    _, _, job = run(e)
    assert job.status == "COMPLETED" and result(e)["text"] == TEXT
    saved = e.persistence.get(job.id)
    assert FIELD not in saved and FIELD not in job.public()
    reopened = _reopen(e).get(job.id)
    assert reopened.status == "COMPLETED"
    assert reopened.creative_execution_authority is None
    assert not generation_content_available(reopened)
    assert e.persistence.get(job.id) == saved
    assert len(e.requests) == 1 and len(_ledger(e)) == 1


@pytest.mark.parametrize("first", ["publisher", "stale_unbound"])
def test_actual_worker_publication_and_process_writer_share_leaf(lifecycle, monkeypatch, first):
    import app.repositories.generation_repository as repository_module
    import app.repositories.file.mutation_coordinator as locks
    e = lifecycle
    wire_entered, wire_release, publisher_entered, publisher_release = [Event() for _ in range(4)]
    publish_attempted, publish_acquired, publish_write, write_release = [Event() for _ in range(4)]
    original_publish = e.persistence.repository._publish_director_terminal
    original_lock, original_write = locks._lock_file, repository_module.atomic_write
    leaf_name = []

    def wire():
        wire_entered.set()
        assert wire_release.wait(15), "Parent did not release the original provider fixture"

    def publish(*args, **kwargs):
        publisher_entered.set()
        assert publisher_release.wait(15), "Parent did not release the original publisher"
        return original_publish(*args, **kwargs)

    def lock(handle):
        publication_leaf = publisher_entered.is_set() and Path(handle.name).name in leaf_name
        if publication_leaf:
            publish_attempted.set()
        original_lock(handle)
        if publication_leaf:
            publish_acquired.set()

    def write(path, value, *args, **kwargs):
        if FIELD in json.loads(value):
            publish_write.set()
            assert write_release.wait(15), "Parent did not release the real evidence replacement"
        return original_write(path, value, *args, **kwargs)

    e.wire_hook = wire
    monkeypatch.setattr(e.persistence.repository, "_publish_director_terminal", publish)
    monkeypatch.setattr(locks, "_lock_file", lock)
    monkeypatch.setattr(repository_module, "atomic_write", write)
    children, releases, logs = [], [], []
    job = None
    try:
        prepared = preview(e)
        receipt = e.coordinator._dispatch_independent(e.ctx, prepared["id"], {
            "expected_version": prepared["version"],
            "reviewed_preview_digest": prepared["model_preview"]["preview_digest"],
        }, e.guard, host_authority=e.authority, terminal_evidence=True)
        job = e.manager.get(receipt["model_execution"]["job_id"])
        assert wire_entered.wait(5)
        repository = e.persistence.repository
        leaf_name.append(hashlib.sha256(repository._write_key(repository._job_path(job.id)).encode()).hexdigest() + ".lock")
        stale = deepcopy(job.public())
        stale.pop("creative_director_binding")
        stale.pop("expected_request_digest")
        stale.update(operation="writer", experimental_origin=None, actor_id=None, scope=None)
        wire_release.set()
        assert publisher_entered.wait(5), "Original worker never reached private publication"
        folder = e.root / "publication-process-controls"
        folder.mkdir()
        (folder / "item.json").write_text(json.dumps(stale), encoding="utf-8")
        attempted, acquired, release, wrote = [
            _DiskEvent(folder / name) for name in ("attempted", "acquired", "release", "wrote")]
        releases.append(release)
        source = Path(__file__).resolve()
        assert Path(os.environ["PROJECT_ROOT"]).resolve() == source.parents[1]
        assert os.environ["PYTHONDONTWRITEBYTECODE"] == "1"
        if first == "publisher":
            publisher_release.set()
            assert publish_write.wait(5)
            assert publish_attempted.is_set() and publish_acquired.is_set()
        log = (folder / "child.log").open("w", encoding="utf-8")
        logs.append(log)
        bootstrap = ("import runpy,sys;sys.path.insert(0,sys.argv[1]);"
                     "scope=runpy.run_path(sys.argv[2]);"
                     "scope['_file_writer_main'](sys.argv[3],sys.argv[4])")
        child = subprocess.Popen([sys.executable, "-B", "-c", bootstrap,
            str(source.parent), str(source), str(e.root), str(folder)],
            cwd=source.parents[1], env=os.environ.copy(), stdin=subprocess.DEVNULL,
            stdout=log, stderr=subprocess.STDOUT)
        children.append(child)
        assert attempted.wait(10), "Child missed actual leaf attempt: " + (folder / "child.log").read_text()
        if first == "publisher":
            assert not acquired.wait(.2), "Stale child bypassed publisher's held OS leaf"
            assert not wrote.is_set()
            release.set()
            write_release.set()
        else:
            assert acquired.wait(5)
            publisher_release.set()
            assert publish_attempted.wait(5), "Publisher never attempted the child-held OS leaf"
            assert not publish_acquired.wait(.2)
            assert not publish_write.is_set(), "Evidence write bypassed the child-held leaf"
            release.set()
            assert publish_write.wait(5), "Publisher did not progress after stale writer rejected"
            write_release.set()
        child.wait(timeout=10)
        assert child.returncode == 0, (folder / "child.log").read_text()
        outcome = json.loads((folder / "outcome.json").read_text())
        assert outcome["pid"] == child.pid != os.getpid()
        assert outcome["outcome"] == "rejected" and outcome["type"] == "GenerationProjectIdentityError"
        assert not wrote.is_set()
        wait(e, job)
        assert job.status == "COMPLETED" and job.creative_execution_authority.publication_state == "ACKNOWLEDGED"
        assert e.persistence.get(job.id)[FIELD]["job_id"] == job.id
        assert result(e)["text"] == TEXT
        assert len(e.requests) == 1 and len(_ledger(e)) == 1
    finally:
        wire_release.set()
        publisher_release.set()
        write_release.set()
        _stop_children(children, releases)
        for log in logs:
            log.close()
        if job is not None:
            wait(e, job)


@pytest.mark.parametrize("change", ["host", "cancel", "deadline"])
def test_late_revocation_retains_sampled_history_but_denies_fresh_result(lifecycle, monkeypatch, change):
    import app.repositories.generation_repository as repository_module
    from app.creative import generation
    e = lifecycle
    if change == "deadline":
        monkeypatch.setattr(generation, "TIMEOUT_SECONDS", 2)
    wire_entered, wire_release = Event(), Event()
    replacements = []
    original_write = repository_module.atomic_write

    def wire():
        wire_entered.set()
        assert wire_release.wait(10)

    def write(path, value, *args, **kwargs):
        document = json.loads(value)
        if FIELD not in document:
            return original_write(path, value, *args, **kwargs)
        job = e.manager.get(document["id"])
        evidence = document[FIELD]
        checkpoint = datetime.fromisoformat(evidence["checkpoint_at"])
        deadline = datetime.fromisoformat(evidence["generation_deadline"])
        assert checkpoint < deadline
        assert checkpoint <= datetime.now(timezone.utc)
        # No scope mutation or authority callback is added within the leaf.
        # These are externally revocable Host/cancel/time inputs at the actual
        # storage boundary, after the original sampled authorization checkpoint.
        if change == "host":
            e.sessions.revoke(e.token)
        elif change == "cancel":
            job.cancelled.set()
        else:
            remaining = (deadline - datetime.now(timezone.utc)).total_seconds()
            assert 0 < remaining <= 2
            Event().wait(remaining + .03)
        response = original_write(path, value, *args, **kwargs)
        replacements.append((deepcopy(evidence), datetime.now(timezone.utc)))
        assert json.loads(Path(path).read_text(encoding="utf-8"))[FIELD] == evidence
        return response

    e.wire_hook = wire
    monkeypatch.setattr(repository_module, "atomic_write", write)
    job = None
    try:
        prepared = preview(e)
        receipt = e.coordinator._dispatch_independent(e.ctx, prepared["id"], {
            "expected_version": prepared["version"],
            "reviewed_preview_digest": prepared["model_preview"]["preview_digest"],
        }, e.guard, host_authority=e.authority, terminal_evidence=True)
        job = e.manager.get(receipt["model_execution"]["job_id"])
        assert wire_entered.wait(5)
    finally:
        wire_release.set()
        if job is not None:
            wait(e, job)
    assert len(replacements) == 1
    evidence, replaced_at = replacements[0]
    assert evidence["semantics"] == "AUTHORITY_AND_BOUNDS_SAMPLED_PRE_COMMIT"
    assert evidence["consumer_authority"] is False
    if change == "deadline":
        assert replaced_at > datetime.fromisoformat(evidence["generation_deadline"])
    assert job.status == "COMPLETED"
    assert job.creative_execution_authority.publication_state == "ACKNOWLEDGED"
    assert e.persistence.get(job.id)[FIELD] == evidence
    with pytest.raises(DENIALS):
        result(e)
    assert not generation_content_available(job)
    durable = deepcopy(e.persistence.get(job.id))
    reopened = _reopen(e).get(job.id)
    assert reopened.creative_execution_authority is None
    assert not generation_content_available(reopened)
    assert e.persistence.get(job.id) == durable
    assert len(e.requests) == 1 and len(_ledger(e)) == 1
