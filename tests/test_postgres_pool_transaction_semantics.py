"""Real-PostgreSQL regressions for pooled connection semantics (D-07 / D-24).

These run only against a real PostgreSQL backend (marker: postgres_backend_only).
They prove the behavioural contract the report relies on: a clean block commits,
an exception rolls back, a connection whose transaction failed can be borrowed
again, and the store reuses one bounded pool instead of opening a connection per
metadata read.

The D-24 regression (test_many_store_reads_reuse_the_pool_instead_of_new_backends)
observes the whole physical-connection surface during a fixed read window:

* cumulative real DBAPI connections created (patched psycopg.connect), which also
  sees the old out-of-pool path - not only SQLAlchemy pool "connect" events;
* actual borrows/returns of the target engine's pool (checkout/checkin events);
* the pool's checked-out count after the window.

The count starts after an explicit warm-up read, so pool initialisation is not
included; warm-up, read window and cleanup are reported separately. A test-only
replay of the old per-read path proves the same contract rejects it (real reads
still complete; only the reuse contract fails). There is no production switch for
that replay.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid

import pytest

psycopg = pytest.importorskip("psycopg")

pytestmark = pytest.mark.postgres_backend_only

DELETE_SQL = "DELETE FROM experimental_scope_documents WHERE scope_key = %s"
INSERT_SQL = (
    "INSERT INTO experimental_scope_documents (scope_key, novel_id, scope, document) "
    "VALUES (%s, %s, %s::jsonb, %s::jsonb)"
)
SELECT_SQL = "SELECT document FROM experimental_scope_documents WHERE scope_key = %s"

POOLED_READ_COUNT = 50


def database_url() -> str:
    url = os.getenv("TEST_POSTGRES_DATABASE_URL", "").strip()
    if not url:
        pytest.skip("TEST_POSTGRES_DATABASE_URL is required for real PostgreSQL pool checks")
    return url


def engine():
    from app.repositories.postgres.connection import engine_for_url
    return engine_for_url(database_url())


def key() -> str:
    # experimental_scope_documents.scope_key must be 64 characters (migration 019).
    return hashlib.sha256(("pool-regression-" + uuid.uuid4().hex).encode()).hexdigest()


def cleanup(scope_key: str) -> None:
    from app.repositories.postgres.connection import pooled_connection
    with pooled_connection(engine()) as connection:
        connection.execute(DELETE_SQL, (scope_key,))


def test_clean_exit_commits_and_a_new_borrow_sees_the_write():
    from app.repositories.postgres.connection import pooled_connection
    scope_key = key()
    try:
        with pooled_connection(engine()) as connection:
            connection.execute(INSERT_SQL, (scope_key, "pool-project",
                                            json.dumps({"mode": "local", "novel_id": "pool-project"}),
                                            json.dumps({"schema_version": 1, "novel_id": "pool-project",
                                                        "scope": {"mode": "local", "novel_id": "pool-project"},
                                                        "collections": {"probe": {"item": {"n": 1}}}})))
        with pooled_connection(engine()) as connection:
            row = connection.execute(SELECT_SQL, (scope_key,)).fetchone()
            assert row is not None
            assert row[0]["collections"]["probe"]["item"]["n"] == 1
        assert engine().pool.checkedout() == 0
    finally:
        cleanup(scope_key)


def test_exception_exit_rolls_back_the_write():
    from app.repositories.postgres.connection import pooled_connection
    scope_key = key()
    try:
        with pytest.raises(RuntimeError):
            with pooled_connection(engine()) as connection:
                connection.execute(INSERT_SQL, (scope_key, "pool-project",
                                                json.dumps({"mode": "local", "novel_id": "pool-project"}),
                                                json.dumps({"schema_version": 1, "novel_id": "pool-project",
                                                            "scope": {"mode": "local", "novel_id": "pool-project"},
                                                            "collections": {}})))
                raise RuntimeError("rollback probe")
        with pooled_connection(engine()) as connection:
            assert connection.execute(SELECT_SQL, (scope_key,)).fetchone() is None
        assert engine().pool.checkedout() == 0
    finally:
        cleanup(scope_key)


def test_connection_is_reusable_after_a_failed_transaction():
    from app.repositories.postgres.connection import pooled_connection
    with pytest.raises(psycopg.errors.DivisionByZero):
        with pooled_connection(engine()) as connection:
            connection.execute("SELECT 1 / 0")
    with pooled_connection(engine()) as connection:
        assert connection.execute("SELECT 42").fetchone()[0] == 42
    assert engine().pool.checkedout() == 0


def test_experimental_store_uses_the_cached_pool():
    from app.experimental.store import ExperimentalStore
    from app.repositories.postgres.connection import engine_for_url
    pooled = engine()
    assert engine_for_url(database_url()) is pooled
    store = ExperimentalStore("/unused-for-postgres", backend="postgres", database_url=database_url())
    nid = "pool-store-" + uuid.uuid4().hex
    scope = {"mode": "local", "novel_id": nid}
    try:
        assert store.read(nid, scope)["collections"] == {}
        with store.transaction(nid, scope) as document:
            document["collections"]["probe"] = {"item": {"value": "committed"}}
        reloaded = store.read(nid, scope)
        assert reloaded["collections"]["probe"]["item"]["value"] == "committed"
        assert pooled.pool.checkedout() == 0
    finally:
        from app.repositories.postgres.connection import pooled_connection
        with pooled_connection(pooled) as connection:
            connection.execute("DELETE FROM experimental_scope_documents WHERE novel_id = %s", (nid,))


def _measure_store_reads(store, nid: str, scope: dict, reads: int, expected_marker: str) -> dict:
    """Measure one fixed read window around the store (warm-up excluded).

    Installs two independent monitors for the window only and always removes them
    again: a psycopg.connect counter (covers pooled and out-of-pool physical
    connections) and the target pool's checkout/checkin events (covers actual
    borrows from the pool). The count starts after one warm-up read, so every
    value refers strictly to the requested reads.
    """
    from sqlalchemy import event
    import app.repositories.postgres.connection as connection_module

    warmup_started = time.monotonic()
    assert store.read(nid, scope)["collections"]["probe"]["marker"] == expected_marker
    warmup_seconds = round(time.monotonic() - warmup_started, 4)

    target = engine()
    counters = {"new_physical_connections": 0, "pool_checkouts": 0, "pool_checkins": 0}
    real_connect = connection_module.psycopg.connect

    def counting_connect(*args, **kwargs):
        counters["new_physical_connections"] += 1
        return real_connect(*args, **kwargs)

    def on_checkout(*args, **kwargs):
        counters["pool_checkouts"] += 1

    def on_checkin(*args, **kwargs):
        counters["pool_checkins"] += 1

    event.listen(target.pool, "checkout", on_checkout)
    event.listen(target.pool, "checkin", on_checkin)
    connection_module.psycopg.connect = counting_connect
    started = time.monotonic()
    completed = 0
    try:
        for _ in range(reads):
            document = store.read(nid, scope)
            assert document["collections"]["probe"]["marker"] == expected_marker
            completed += 1
        window_seconds = round(time.monotonic() - started, 4)
    finally:
        connection_module.psycopg.connect = real_connect
        event.remove(target.pool, "checkout", on_checkout)
        event.remove(target.pool, "checkin", on_checkin)

    return {
        "reads_requested": reads,
        "reads_completed": completed,
        "read_window_seconds": window_seconds,
        "warmup_seconds": warmup_seconds,
        "new_physical_connections": counters["new_physical_connections"],
        "pool_checkouts": counters["pool_checkouts"],
        "pool_checkins": counters["pool_checkins"],
        "checked_out_after": target.pool.checkedout(),
        "target_pool_identity": id(target.pool),
    }


def _assert_pool_contract(metrics: dict) -> None:
    """The D-24 contract: reads borrow the target pool and create no new backend."""
    assert metrics["reads_completed"] == metrics["reads_requested"] == POOLED_READ_COUNT
    assert metrics["new_physical_connections"] == 0, (
        "store reads created new physical database connections instead of borrowing "
        "from the target pool: " + json.dumps(metrics, sort_keys=True))
    assert metrics["pool_checkouts"] == POOLED_READ_COUNT, (
        "store reads did not borrow exactly once per read from the target pool: "
        + json.dumps(metrics, sort_keys=True))
    assert metrics["pool_checkins"] == metrics["pool_checkouts"], (
        "store reads did not return every borrowed pool connection: "
        + json.dumps(metrics, sort_keys=True))
    assert metrics["checked_out_after"] == 0, (
        "pool connections were not fully returned after the read window: "
        + json.dumps(metrics, sort_keys=True))


def _seed_marker(store, nid: str, scope: dict) -> str:
    marker = "marker-" + uuid.uuid4().hex
    with store.transaction(nid, scope) as document:
        document["collections"]["probe"] = {"marker": marker}
    return marker


def test_many_store_reads_reuse_the_pool_instead_of_new_backends():
    """D-24 regression: repeated metadata reads must borrow from the pool, not connect."""
    from app.experimental.store import ExperimentalStore

    store = ExperimentalStore("/unused-for-postgres", backend="postgres", database_url=database_url())
    nid = "pool-reads-" + uuid.uuid4().hex
    scope = {"mode": "local", "novel_id": nid}
    scope_key = store.key(nid, scope)
    try:
        marker = _seed_marker(store, nid, scope)
        metrics = _measure_store_reads(store, nid, scope, POOLED_READ_COUNT, marker)
        _assert_pool_contract(metrics)
        print("POOL_CONTRACT_METRICS " + json.dumps(metrics, sort_keys=True), flush=True)
        assert engine().pool.checkedout() == 0
    finally:
        cleanup(scope_key)


def test_unpooled_store_path_is_rejected_by_the_pool_contract():
    """Counter-example: the old per-read path fails the same connection-reuse contract.

    The old path is replayed inside this test only by temporarily restoring
    ExperimentalStore._connect to the bounded direct connect helper; it is not a
    production flag and is always removed again. The reads must still really hit
    PostgreSQL; only the reuse contract fails.
    """
    from app.experimental.store import ExperimentalStore
    import app.repositories.postgres.connection as connection_module

    original_connect = ExperimentalStore._connect
    store = ExperimentalStore("/unused-for-postgres", backend="postgres", database_url=database_url())
    nid = "pool-replay-" + uuid.uuid4().hex
    scope = {"mode": "local", "novel_id": nid}
    scope_key = store.key(nid, scope)
    try:
        marker = _seed_marker(store, nid, scope)

        def unpooled_connect(self):
            return connection_module.connect(self.database_url)

        ExperimentalStore._connect = unpooled_connect
        try:
            metrics = _measure_store_reads(store, nid, scope, POOLED_READ_COUNT, marker)
        finally:
            ExperimentalStore._connect = original_connect

        # The replay did complete the real reads; it is rejected purely by the
        # connection-reuse contract, with the measured counts in the message.
        print("POOL_CONTRACT_REPLAY_METRICS " + json.dumps(metrics, sort_keys=True), flush=True)
        assert metrics["reads_completed"] == POOLED_READ_COUNT
        with pytest.raises(AssertionError, match="new physical database connections") as error_info:
            _assert_pool_contract(metrics)
        rejection_message = str(error_info.value)
        assert "\"new_physical_connections\": " + str(POOLED_READ_COUNT) in rejection_message
        assert "\"pool_checkouts\": 0" in rejection_message
        assert "\"reads_completed\": " + str(POOLED_READ_COUNT) in rejection_message
        print("POOL_CONTRACT_REJECTED " + rejection_message.replace(chr(10), " | "), flush=True)

        # Restoring the pooled path makes the same contract pass again.
        restored_metrics = _measure_store_reads(store, nid, scope, POOLED_READ_COUNT, marker)
        _assert_pool_contract(restored_metrics)
        print("POOL_CONTRACT_RESTORED_METRICS " + json.dumps(restored_metrics, sort_keys=True), flush=True)
        assert engine().pool.checkedout() == 0
    finally:
        ExperimentalStore._connect = original_connect
        cleanup(scope_key)