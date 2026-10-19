"""Real-PostgreSQL regressions for pooled connection semantics (D-07 / D-24).

These run only against a real PostgreSQL backend (marker: postgres_backend_only).
They prove the behavioural contract the report relies on: a clean block commits,
an exception rolls back, a connection whose transaction failed can be borrowed
again, and the store reuses the same bounded pool instead of opening a connection
per metadata read.
"""
from __future__ import annotations

import hashlib
import json
import os
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
            connection.execute(INSERT_SQL, (scope_key, "pool-project", json.dumps({"mode": "local", "novel_id": "pool-project"}),
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
                connection.execute(INSERT_SQL, (scope_key, "pool-project", json.dumps({"mode": "local", "novel_id": "pool-project"}),
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


def test_many_store_reads_reuse_the_pool_instead_of_new_backends():
    """D-24 regression: repeated metadata reads must not open a backend each time."""
    import psycopg
    from app.experimental.store import ExperimentalStore
    from app.repositories.postgres.connection import engine_for_url

    url = database_url()
    pooled = engine_for_url(url)
    parsed = psycopg.conninfo.conninfo_to_dict(url)
    database = parsed.get("dbname") or "postgres"
    admin = {
        "host": parsed.get("host") or "127.0.0.1",
        "port": parsed.get("port") or 5432,
        "dbname": database,
        "user": parsed.get("user") or "postgres",
        "connect_timeout": 10,
    }
    store = ExperimentalStore("/unused-for-postgres", backend="postgres", database_url=url)
    nid = "pool-reads-" + uuid.uuid4().hex
    scope = {"mode": "local", "novel_id": nid}

    def backend_count() -> int:
        with psycopg.connect(**admin) as connection:
            return connection.execute(
                "SELECT count(*) FROM pg_stat_activity WHERE datname = %s", (database,)).fetchone()[0]

    try:
        assert store.read(nid, scope)["collections"] == {}
        before = backend_count()
        for _ in range(50):
            assert store.read(nid, scope)["collections"] == {}
        after = backend_count()
        # The pool is bounded at 4 + 4; 50 reads must not add ~50 backends.
        assert after - before <= 2, (before, after)
        assert pooled.pool.checkedout() == 0
    finally:
        from app.repositories.postgres.connection import pooled_connection
        with pooled_connection(pooled) as connection:
            connection.execute("DELETE FROM experimental_scope_documents WHERE novel_id = %s", (nid,))