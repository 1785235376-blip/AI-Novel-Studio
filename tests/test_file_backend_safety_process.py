"""Real Windows termination/competition probes using only synthetic owner data.

These tests exercise TerminateProcess, not POSIX SIGKILL or power-loss durability.
Pipes/events/barriers select the exact commit boundary without timing races.
"""
from __future__ import annotations

import multiprocessing as mp
import os
from pathlib import Path

import pytest

pytestmark = [pytest.mark.file_backend_only,
              pytest.mark.skipif(os.name != "nt", reason="Windows TerminateProcess evidence only")]
SCOPE = {"mode": "local", "novel_id": "book"}


def _exporter_forbidden(*args, **kwargs):
    raise AssertionError("storage probe must never execute an export or model")


def _export_service(root):
    from app.services.export_job_service import ExportJobService
    ExportJobService._submit = lambda self, jid: None
    return ExportJobService(Path(root), _exporter_forbidden)


def _boundary_writer(root, owner, point, ready, release):
    from app import storage
    from app.experimental.store import ExperimentalStore
    root = Path(root)
    service = _export_service(root) if owner == "export" else None
    store = ExperimentalStore(root)
    target = service.path if service else store.path("book", SCOPE)
    original = storage.os.replace

    def gated(source, destination):
        if Path(destination) != target:
            return original(source, destination)
        if point == "after_replace":
            original(source, destination)
        ready.send({"pid": os.getpid(), "owner": owner, "point": point})
        if not release.wait(30):
            raise RuntimeError("parent did not terminate boundary worker")
        if point == "before_replace":
            original(source, destination)

    storage.os.replace = gated
    if service:
        rows = service._read()
        rows["terminal"]["status"] = "failed"
        service._write(rows)
    else:
        with store.transaction("book", SCOPE) as doc:
            doc["collections"]["semantic_import_jobs"]["job"]["status"] = "RUNNING"


def _reopen_and_write(root, owner, result):
    if owner == "export":
        service = _export_service(root)
        try:
            rows = service._read()
            rows["terminal"]["status"] = "succeeded"
            service._write(rows)
            result.send(service.get("terminal")["status"])
        finally:
            service._pool.shutdown(wait=True)
    else:
        from app.experimental.store import ExperimentalStore
        store = ExperimentalStore(root)
        with store.transaction("book", SCOPE) as doc:
            doc["collections"]["semantic_import_jobs"]["job"]["status"] = "RECOVERED"
        result.send(store.capture_committed_collection("book", SCOPE)["rows"][0]["status"])


def _seed(root, owner):
    if owner == "export":
        service = _export_service(root)
        row = {"id": "terminal", "novel_id": "book", "status": "succeeded",
               "created_at": "2026-01-01T00:00:00Z", "result": None,
               "permission_context": {"mode": "local", "novel_id": "book", "actor_id": None}}
        service._write({"terminal": row})
        return service
    from app.creative.project_store import CreativeProjectStore
    from app.experimental.store import ExperimentalStore
    (root / "novels" / "book").mkdir(parents=True)
    store = ExperimentalStore(root)
    CreativeProjectStore(store).incarnation("book")
    with store.transaction("book", SCOPE) as doc:
        doc["collections"]["semantic_import_jobs"] = {
            "job": {"id": "job", "novel_id": "book", "scope": SCOPE,
                    "version": 1, "status": "QUEUED"}}
    return store


def _capture(owner, kind):
    if kind == "export":
        return owner._read(), owner.binding_observation(["terminal"])
    observation = owner.capture_committed_collection("book", SCOPE)
    return observation["rows"], observation


@pytest.mark.parametrize("kind", ["export", "experimental"])
@pytest.mark.parametrize("point", ["before_replace", "after_replace"])
def test_windows_terminate_at_atomic_replace_keeps_business_and_lifecycle_paired(tmp_path, kind, point):
    owner = _seed(tmp_path, kind)
    before_rows, before_evidence = _capture(owner, kind)
    ctx = mp.get_context("spawn")
    parent, child_pipe = ctx.Pipe(duplex=False)
    release = ctx.Event()
    child = ctx.Process(target=_boundary_writer,
                        args=(str(tmp_path), kind, point, child_pipe, release))
    child.start()
    try:
        assert parent.poll(30), "worker never reached selected atomic replacement boundary"
        receipt = parent.recv()
        assert receipt["point"] == point and receipt["pid"] == child.pid
        child.terminate()  # Windows multiprocessing uses TerminateProcess.
        child.join(15)
        assert not child.is_alive() and child.exitcode != 0
        rows, evidence = _capture(owner, kind)
        if point == "before_replace":
            assert rows == before_rows and evidence == before_evidence
        else:
            assert evidence != before_evidence
            assert (rows["terminal"]["status"] == "failed" if kind == "export"
                    else rows[0]["status"] == "RUNNING")
        # A fresh process must acquire the original OS lock after abrupt death.
        out, writer_pipe = ctx.Pipe(duplex=False)
        reopened = ctx.Process(target=_reopen_and_write, args=(str(tmp_path), kind, writer_pipe))
        reopened.start()
        try:
            assert out.poll(30), "original lock did not release after TerminateProcess"
            assert out.recv() == ("succeeded" if kind == "export" else "RECOVERED")
            reopened.join(15)
            assert not reopened.is_alive() and reopened.exitcode == 0
        finally:
            if reopened.is_alive():
                reopened.terminate()
                reopened.join(10)
        print("WINDOWS_TERMINATE_PROCESS", kind, point, "paired_commit_and_reopen_passed")
    finally:
        release.set()
        if child.is_alive():
            child.terminate()
            child.join(10)
        if kind == "export":
            owner._pool.shutdown(wait=True)


def _competing_export(root, key, gate, result):
    service = _export_service(root)
    try:
        gate.wait(30)
        row = service.create("book", "txt", key,
                             permission_context={"mode": "local", "novel_id": "book", "actor_id": None})
        result.send(row["id"])
    finally:
        service._pool.shutdown(wait=True)


@pytest.mark.parametrize("same_key", [False, True])
def test_windows_simultaneous_original_export_writers_preserve_jobs_and_idempotency(tmp_path, same_key):
    ctx = mp.get_context("spawn")
    gate = ctx.Barrier(3)
    children, results = [], []
    for role in ("a", "b"):
        parent, child_pipe = ctx.Pipe(duplex=False)
        child = ctx.Process(target=_competing_export,
                           args=(str(tmp_path), "same" if same_key else role, gate, child_pipe))
        results.append(parent)
        children.append(child)
        child.start()
    try:
        gate.wait(30)
        ids = []
        for pipe, child in zip(results, children):
            assert pipe.poll(30), "writer stalled"
            ids.append(pipe.recv())
            child.join(15)
            assert not child.is_alive() and child.exitcode == 0
        # Startup recovery is the existing policy; no new worker exclusivity claim.
        owner = _export_service(tmp_path)
        try:
            assert all(owner.get(jid)["id"] == jid for jid in ids)
            assert len(set(ids)) == (1 if same_key else 2)
            assert owner.binding_observation(list(dict.fromkeys(ids)))
        finally:
            owner._pool.shutdown(wait=True)
    finally:
        for child in children:
            if child.is_alive():
                child.terminate()
                child.join(10)
