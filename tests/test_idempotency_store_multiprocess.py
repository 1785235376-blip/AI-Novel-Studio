"""Linux File-store coordination only; no generation, provider or JobManager.

Spawned workers are independent interpreters. A paused first reader owns the
critical section; later workers must wait, not rendezvous inside _load().
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import multiprocessing
from pathlib import Path
import sys

import pytest

from app.idempotency import IdempotencyStore


pytestmark = [
    pytest.mark.file_backend_only,
    pytest.mark.skipif(sys.platform != "linux", reason="Linux File multiprocess evidence"),
]
TIMEOUT = 15


def _worker(connection, path, operation, key, value=None, pause=False, failure=None):
    # Finish lazy-import work before reporting readiness to contend on the lock.
    from app.repositories.file.mutation_coordinator import workspace_mutation
    import app.idempotency as module

    assert callable(workspace_mutation)
    store = IdempotencyStore(Path(path))
    original_load = store._load

    def controlled_load():
        result = original_load()
        if pause:
            connection.send(("loaded", None))
            if not connection.poll(TIMEOUT):
                raise TimeoutError("Parent did not release controlled reader")
            assert connection.recv() == "release"
        if failure == "load":
            raise ValueError("controlled load failure")
        return result

    store._load = controlled_load
    if failure == "write":
        def fail_write(*_args, **_kwargs):
            raise OSError("controlled write failure")
        module.atomic_write = fail_write
    connection.send(("ready", None))
    try:
        result = getattr(store, operation)(key, value) if operation == "put" else getattr(store, operation)(key)
    except Exception as exc:
        connection.send(("error", (type(exc).__name__, str(exc))))
        if failure:
            # Stay alive while the waiting writer finishes. Its progress must
            # come from exception unwinding, not process-exit lock cleanup.
            if not connection.poll(TIMEOUT):
                raise TimeoutError("Parent did not finish controlled failure")
            assert connection.recv() == "finish"
    else:
        connection.send(("done", result))
    finally:
        connection.close()


@contextmanager
def _process(path, operation, key, value=None, *, pause=False, failure=None):
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(target=_worker, args=(child, str(path), operation, key, value, pause, failure))
    process.start()
    child.close()
    try:
        yield process, parent
    finally:
        if process.is_alive():
            process.terminate()
        process.join(TIMEOUT)
        parent.close()
        assert not process.is_alive(), "Test worker did not stop"


def _receive(connection, kind):
    assert connection.poll(TIMEOUT), f"Worker did not report {kind}"
    actual, result = connection.recv()
    assert actual == kind, (actual, result)
    return result


def _finished(process):
    process.join(TIMEOUT)
    assert process.exitcode == 0


def _rows(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("second_key", ["different", "same"])
@pytest.mark.parametrize("alias", [False, True], ids=["same-path", "directory-symlink"])
def test_process_writers_share_the_whole_document_lock(tmp_path, second_key, alias):
    root = tmp_path / "data"
    root.mkdir()
    path = root / "idempotency.json"
    other = path
    if alias:
        link = tmp_path / "alias"
        link.symlink_to(root, target_is_directory=True)
        other = link / path.name
    with _process(path, "put", "same", "first", pause=True) as (first, first_pipe):
        _receive(first_pipe, "ready")
        _receive(first_pipe, "loaded")
        with _process(other, "put", second_key, "second") as (second, second_pipe):
            _receive(second_pipe, "ready")
            assert not second_pipe.poll(0.3), "Second process bypassed document lock"
            first_pipe.send("release")
            assert _receive(first_pipe, "done") == "first"
            assert _receive(second_pipe, "done") == "second"
            _finished(first)
            _finished(second)
    values = {key: row["value"] for key, row in _rows(path).items()}
    assert values == ({"same": "second"} if second_key == "same" else {"same": "first", "different": "second"})


def test_expiry_eviction_cannot_erase_another_process_put(tmp_path):
    path = tmp_path / "idempotency.json"
    now = datetime.now(timezone.utc)
    path.write_text(json.dumps({
        "expired": {"created_at": (now - timedelta(days=2)).isoformat(), "value": "old"},
        "keep": {"created_at": now.isoformat(), "value": "keep"},
    }), encoding="utf-8")
    with _process(path, "get", "expired", pause=True) as (reader, reader_pipe):
        _receive(reader_pipe, "ready")
        _receive(reader_pipe, "loaded")
        with _process(path, "put", "new", "new-value") as (writer, writer_pipe):
            _receive(writer_pipe, "ready")
            assert not writer_pipe.poll(0.3), "Writer bypassed TTL eviction lock"
            reader_pipe.send("release")
            assert _receive(reader_pipe, "done") is None
            assert _receive(writer_pipe, "done") == "new-value"
            _finished(reader)
            _finished(writer)
    assert {key: row["value"] for key, row in _rows(path).items()} == {"keep": "keep", "new": "new-value"}


@pytest.mark.parametrize("operation", ["get", "retained"])
def test_readers_wait_for_another_process_complete_put(tmp_path, operation):
    path = tmp_path / "idempotency.json"
    with _process(path, "put", "key", "committed", pause=True) as (writer, writer_pipe):
        _receive(writer_pipe, "ready")
        _receive(writer_pipe, "loaded")
        with _process(path, operation, "key") as (reader, reader_pipe):
            _receive(reader_pipe, "ready")
            assert not reader_pipe.poll(0.3), "Reader observed an in-flight mutation as a miss"
            writer_pipe.send("release")
            assert _receive(writer_pipe, "done") == "committed"
            result = _receive(reader_pipe, "done")
            assert (result["value"] if operation == "retained" else result) == "committed"
            _finished(writer)
            _finished(reader)


@pytest.mark.parametrize("contents,error", [
    ('{ "key": {"created_at": "2000-01-01T00:00:00+00:00", "value": {"original": true}} }\n', None),
    ('{broken json', "IDEMPOTENCY_RETAINED_STORE_INVALID"),
    ('[]', "IDEMPOTENCY_RETAINED_STORE_INVALID"),
    ('{"key": null}', "IDEMPOTENCY_RETAINED_RECORD_INVALID"),
])
def test_retained_read_or_error_never_changes_receipt_bytes(tmp_path, contents, error):
    path = tmp_path / "idempotency.json"
    path.write_bytes(contents.encode("utf-8"))
    before = path.read_bytes()
    with _process(path, "retained", "key") as (reader, connection):
        _receive(connection, "ready")
        if error:
            assert _receive(connection, "error") == ("ValueError", error)
        else:
            assert _receive(connection, "done") == json.loads(contents)["key"]
        _finished(reader)
    assert path.read_bytes() == before


@pytest.mark.parametrize("failure,exception", [("load", "ValueError"), ("write", "OSError")])
def test_exception_releases_lock_to_waiting_process(tmp_path, failure, exception):
    path = tmp_path / "idempotency.json"
    with _process(path, "put", "failed", "never-saved", pause=True, failure=failure) as (first, first_pipe):
        _receive(first_pipe, "ready")
        _receive(first_pipe, "loaded")
        with _process(path, "put", "survivor", "saved") as (second, second_pipe):
            _receive(second_pipe, "ready")
            assert not second_pipe.poll(0.3)
            first_pipe.send("release")
            assert _receive(first_pipe, "error")[0] == exception
            assert _receive(second_pipe, "done") == "saved"
            assert first.is_alive()
            first_pipe.send("finish")
            _finished(first)
            _finished(second)
    assert set(_rows(path)) == {"survivor"}


def test_process_termination_releases_lock_without_deleting_lock_file(tmp_path):
    path = tmp_path / "idempotency.json"
    with _process(path, "put", "terminated", "never-saved", pause=True) as (first, first_pipe):
        _receive(first_pipe, "ready")
        _receive(first_pipe, "loaded")
        lock_files = list((tmp_path / ".workspace-mutation-locks").glob("*.lock"))
        assert len(lock_files) == 1
        with _process(path, "put", "survivor", "saved") as (second, second_pipe):
            _receive(second_pipe, "ready")
            assert not second_pipe.poll(0.3)
            first.terminate()
            first.join(TIMEOUT)
            assert first.exitcode is not None and first.exitcode < 0
            assert _receive(second_pipe, "done") == "saved"
            _finished(second)
        assert lock_files[0].exists()
    assert set(_rows(path)) == {"survivor"}


def test_different_cache_files_do_not_share_one_global_lock(tmp_path):
    with _process(tmp_path / "one.json", "put", "key", "one", pause=True) as (first, first_pipe):
        _receive(first_pipe, "ready")
        _receive(first_pipe, "loaded")
        with _process(tmp_path / "two.json", "put", "key", "two") as (second, second_pipe):
            _receive(second_pipe, "ready")
            assert _receive(second_pipe, "done") == "two"
            _finished(second)
        first_pipe.send("release")
        assert _receive(first_pipe, "done") == "one"
        _finished(first)


@pytest.mark.parametrize("operation", ["get", "retained"])
def test_missing_reads_only_create_coordination_metadata(tmp_path, operation):
    path = tmp_path / "new-directory" / "idempotency.json"
    store = IdempotencyStore(path)
    assert getattr(store, operation)("absent") is None
    assert not path.exists()
    assert len(list((path.parent / ".workspace-mutation-locks").glob("*.lock"))) == 1


def test_canonical_path_survives_working_directory_change_and_no_key_put_is_noop(tmp_path, monkeypatch):
    original = tmp_path / "original"
    other = tmp_path / "other"
    original.mkdir()
    other.mkdir()
    monkeypatch.chdir(original)
    store = IdempotencyStore(Path("idempotency.json"))
    assert store.put("", "unchanged") == "unchanged"
    assert list(original.iterdir()) == []
    monkeypatch.chdir(other)
    assert store.put("key", "saved") == "saved"
    assert store.path == original / "idempotency.json"
    assert store.get("key") == "saved"
    assert list(other.iterdir()) == []
