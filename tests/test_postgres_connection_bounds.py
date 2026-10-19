"""Bounded PostgreSQL connection establishment (D-07 hang-class regression).

These are pure unit tests: no server is required. They pin the deadline, the
bounded retry policy and the guard that keeps future direct connections from
re-introducing an unbounded blocking connect in an async request path.
"""
from __future__ import annotations

from pathlib import Path

import psycopg
import pytest

from app.repositories.postgres import connection as pg_connection
from app.repositories.postgres.connection import (
    DEFAULT_CONNECT_ATTEMPTS,
    pooled_connection,
    DEFAULT_CONNECT_TIMEOUT_SECONDS,
    connect,
    connect_attempts,
    connect_timeout,
    connect_timeout_seconds,
    normalize_dsn,
)
from app.repositories.postgres.session import Database

ROOT = Path(__file__).resolve().parents[1]


def test_connect_timeout_defaults_and_environment_bounds(monkeypatch):
    monkeypatch.delenv("POSTGRES_CONNECT_TIMEOUT_SECONDS", raising=False)
    assert connect_timeout_seconds() == DEFAULT_CONNECT_TIMEOUT_SECONDS
    assert connect_timeout() == int(DEFAULT_CONNECT_TIMEOUT_SECONDS)

    monkeypatch.setenv("POSTGRES_CONNECT_TIMEOUT_SECONDS", "7")
    assert connect_timeout_seconds() == 7.0
    assert connect_timeout() == 7

    for invalid in ("not-a-number", "0", "1", "-5", "500"):
        monkeypatch.setenv("POSTGRES_CONNECT_TIMEOUT_SECONDS", invalid)
        assert connect_timeout_seconds() == DEFAULT_CONNECT_TIMEOUT_SECONDS


def test_connect_attempts_defaults_and_environment_bounds(monkeypatch):
    monkeypatch.delenv("POSTGRES_CONNECT_ATTEMPTS", raising=False)
    assert connect_attempts() == DEFAULT_CONNECT_ATTEMPTS
    monkeypatch.setenv("POSTGRES_CONNECT_ATTEMPTS", "2")
    assert connect_attempts() == 2
    for invalid in ("0", "-1", "99", "abc"):
        monkeypatch.setenv("POSTGRES_CONNECT_ATTEMPTS", invalid)
        assert connect_attempts() == DEFAULT_CONNECT_ATTEMPTS


def test_connect_timeout_is_at_least_two_seconds(monkeypatch):
    monkeypatch.setenv("POSTGRES_CONNECT_TIMEOUT_SECONDS", "2")
    assert connect_timeout() >= 2


def test_normalize_dsn_strips_sqlalchemy_driver_suffix():
    assert normalize_dsn("postgresql+psycopg://user@127.0.0.1:5432/db") == "postgresql://user@127.0.0.1:5432/db"
    assert normalize_dsn("postgresql://user@127.0.0.1:5432/db") == "postgresql://user@127.0.0.1:5432/db"


def test_connect_retries_transient_operational_error_then_returns(monkeypatch):
    calls = []
    sentinel = object()

    def fake_connect(dsn, **kwargs):
        calls.append((dsn, kwargs))
        if len(calls) < 3:
            raise psycopg.OperationalError("could not reserve shared memory region (error code 487)")
        return sentinel

    monkeypatch.setattr(pg_connection.psycopg, "connect", fake_connect)
    monkeypatch.setattr(pg_connection.time, "sleep", lambda seconds: None)
    assert connect("postgresql+psycopg://postgres@127.0.0.1:55432/v2_d07") is sentinel
    assert len(calls) == 3
    assert calls[0][0] == "postgresql://postgres@127.0.0.1:55432/v2_d07"
    assert calls[0][1]["connect_timeout"] == int(DEFAULT_CONNECT_TIMEOUT_SECONDS)
    assert calls[0][1]["options"] == "-c timezone=UTC"


def test_connect_exhaustion_reraises_the_original_error(monkeypatch):
    calls = []
    original = psycopg.OperationalError("connection timeout expired")

    def fake_connect(dsn, **kwargs):
        calls.append(dsn)
        raise original

    monkeypatch.setattr(pg_connection.psycopg, "connect", fake_connect)
    monkeypatch.setattr(pg_connection.time, "sleep", lambda seconds: None)
    with pytest.raises(psycopg.OperationalError) as caught:
        connect("postgresql://postgres@127.0.0.1:55432/v2_d07")
    assert caught.value is original
    assert len(calls) == DEFAULT_CONNECT_ATTEMPTS


def test_non_operational_errors_are_never_retried(monkeypatch):
    calls = []

    def fake_connect(dsn, **kwargs):
        calls.append(dsn)
        raise psycopg.ProgrammingError("syntax error")

    monkeypatch.setattr(pg_connection.psycopg, "connect", fake_connect)
    monkeypatch.setattr(pg_connection.time, "sleep", lambda seconds: None)
    with pytest.raises(psycopg.ProgrammingError):
        connect("postgresql://postgres@127.0.0.1:55432/v2_d07")
    assert len(calls) == 1


def test_database_engine_passes_bounded_connect_timeout(monkeypatch):
    captured = {}

    def fake_create_engine(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr("app.repositories.postgres.session.create_engine", fake_create_engine)
    Database("postgresql://postgres@127.0.0.1:55432/v2_d07")
    connect_args = captured["kwargs"]["connect_args"]
    assert connect_args["connect_timeout"] >= 2
    assert connect_args["options"] == "-c timezone=UTC"
    assert captured["url"].startswith("postgresql+psycopg://")


def test_app_has_no_unbounded_direct_psycopg_connect():
    allowed = {"app/repositories/postgres/connection.py"}
    offenders = []
    for path in sorted((ROOT / "app").rglob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        if relative in allowed:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "psycopg.connect(" not in line:
                continue
            if "connect_timeout" in line:
                continue
            offenders.append(f"{relative}:{number}")
    assert offenders == [], "direct psycopg.connect() must carry a bounded connect_timeout: " + ", ".join(offenders)


def test_repository_factory_uses_pooled_connections():
    factory = (ROOT / "app/repositories/factory.py").read_text(encoding="utf-8")
    store = (ROOT / "app/experimental/store.py").read_text(encoding="utf-8")
    assert "pooled_connection(database.engine)" in factory
    assert "psycopg.connect(" not in factory
    # D-24: the experimental store must borrow from the pool as well, not open a
    # new backend per metadata read.
    assert "pooled_connection(engine_for_url(self.database_url))" in store
    assert "postgres_connect(" not in store
    assert "psycopg.connect(" not in store


class _FakeConnection:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


class _FakeFairy:
    def __init__(self, connection):
        self.driver_connection = connection
        self.closed = False

    def close(self):
        self.closed = True


class _FakeEngine:
    def __init__(self):
        self.connection = _FakeConnection()
        self.fairy = _FakeFairy(self.connection)

    def raw_connection(self):
        return self.fairy


def test_pooled_connection_commits_clean_work_and_returns_to_the_pool():
    engine = _FakeEngine()
    with pooled_connection(engine) as connection:
        assert connection is engine.connection
        assert engine.fairy.closed is False
        assert engine.connection.commits == 0
    assert engine.connection.commits == 1
    assert engine.connection.rollbacks == 0
    assert engine.fairy.closed is True


def test_pooled_connection_rolls_back_and_returns_to_the_pool_on_error():
    engine = _FakeEngine()
    with pytest.raises(RuntimeError):
        with pooled_connection(engine):
            raise RuntimeError("repository failure")
    assert engine.connection.commits == 0
    assert engine.connection.rollbacks == 1
    assert engine.fairy.closed is True


def test_engine_for_url_is_cached_per_normalized_dsn_and_disposed(monkeypatch):
    from app.repositories.postgres import connection as connection_module
    created = []

    class FakeEngine:
        def __init__(self, url, **kwargs):
            self.url = url
            self.kwargs = kwargs
            self.disposed = False
            created.append(self)

        def dispose(self):
            self.disposed = True

    monkeypatch.setattr("sqlalchemy.create_engine", lambda url, **kwargs: FakeEngine(url, **kwargs))
    connection_module.clear_engine_cache()
    try:
        first = connection_module.engine_for_url("postgresql://pool@127.0.0.1:55432/engine_cache")
        second = connection_module.engine_for_url("postgresql://pool@127.0.0.1:55432/engine_cache")
        third = connection_module.engine_for_url("postgresql://pool@127.0.0.1:55432/engine_cache_other")
        assert first is second
        assert first is not third
        assert len(created) == 2
        assert created[0].url.startswith("postgresql+psycopg://")
        assert created[0].kwargs["pool_size"] == 4
        assert created[0].kwargs["max_overflow"] == 4
        assert created[0].kwargs["connect_args"]["connect_timeout"] == connection_module.connect_timeout()
        connection_module.clear_engine_cache()
        assert created[0].disposed is True
        assert created[1].disposed is True
    finally:
        connection_module.clear_engine_cache()