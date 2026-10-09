"""Local PostgreSQL harness isolation, without launching a PostgreSQL process."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import psycopg
import pytest

from scripts import run_v2_postgres_checks as runner


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, harness, database):
        self.harness, self.database = harness, database

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.harness.closed.append(self.database)

    def execute(self, statement, params=None):
        sql = statement if isinstance(statement, str) else statement.as_string()
        self.harness.sql.append((self.database, sql, params))
        if sql == runner.IDENTITY_SQL:
            database = self.harness.identity_database or self.database
            return FakeCursor([("PostgreSQL test double", database, "127.0.0.1", 55432,
                                1, 5 if self.database == "postgres" else 12345, "postgres")])
        if "WHERE datname = %s" in sql:
            return FakeCursor([(9876,)] if self.harness.exists else [])
        if sql.startswith("CREATE DATABASE"):
            if self.harness.failure == "create":
                raise RuntimeError("synthetic create failure")
            self.harness.created.append(sql)
            return FakeCursor([])
        if sql == runner.EMPTY_DATABASE_SQL:
            return FakeCursor(self.harness.objects)
        if self.harness.failure == "migration":
            raise RuntimeError("synthetic migration failure")
        self.harness.applied.append(sql)
        return FakeCursor([])


@pytest.fixture
def harness(tmp_path, monkeypatch):
    root = tmp_path / "checkout"
    pg_bin, data = root / ".runtime/bin", root / ".runtime/data"
    pg_bin.mkdir(parents=True)
    data.mkdir(parents=True)
    (pg_bin / ("pg_ctl.exe" if runner.sys.platform == "win32" else "pg_ctl")).write_text("")
    (data / "PG_VERSION").write_text("17\n")
    migrations = root / "database/migrations"
    migrations.mkdir(parents=True)
    # Creation order differs from lexicographic CI order; retain original byte hashes.
    sources = {"020_last.sql": b"SELECT 20;\n", "002_second.sql": b"SELECT 2;\r\n",
               "001_first.sql": b"SELECT 1;\n"}
    for name, content in sources.items():
        (migrations / name).write_bytes(content)
    (migrations / "ignored.txt").write_text("not a migration")
    state = SimpleNamespace(root=root, pg_bin=pg_bin, data=data, sources=sources,
                            exists=False, objects=[], failure=None, identity_database=None,
                            status_code=3, checks_code=0, processes=[], connections=[],
                            sql=[], closed=[], created=[], applied=[], start_error=None)

    def connect(**kwargs):
        state.connections.append(kwargs)
        if state.failure == "connect":
            raise RuntimeError("synthetic connection failure")
        return FakeConnection(state, kwargs["dbname"])

    def run(command, **kwargs):
        state.processes.append((command, kwargs))
        operation = command[-1]
        if operation == "status":
            code = state.status_code
        elif operation in {"start", "stop"}:
            if operation == "start" and state.failure == "start_timeout":
                state.start_error = subprocess.TimeoutExpired(command, kwargs["timeout"])
                raise state.start_error
            code = 1 if state.failure == operation else 0
        else:
            assert command[1] == str(root / "scripts/run_v2_checks.py")
            if state.failure == "checks":
                raise RuntimeError("synthetic checks launch failure")
            code = state.checks_code
        if kwargs.get("check") and code:
            error = subprocess.CalledProcessError(code, command)
            if operation == "start":
                state.start_error = error
            raise error
        return subprocess.CompletedProcess(command, code)

    monkeypatch.setattr(runner, "__file__", str(root / "scripts/run_v2_postgres_checks.py"))
    monkeypatch.setattr(runner.subprocess, "run", run)
    monkeypatch.setattr(psycopg, "connect", connect)
    return state


def arguments(harness, *, fresh=True, database="v2_M3_unit"):
    args = ["--pg-bin", str(harness.pg_bin), "--data", str(harness.data)]
    if fresh:
        args.append("--fresh-database")
    if database is not None:
        args.extend(["--database", database])
    return [*args, "dev-m3-pg-isolation-unit", "--", "python", "-m", "pytest", "tests/unchanged.py"]


def read_receipt(harness):
    return json.loads((harness.root / "docs/delivery/v2-development/"
                       "dev-m3-pg-isolation-unit-postgres-runtime.json").read_text())


def operations(harness):
    return [command[-1] for command, _ in harness.processes]


@pytest.mark.parametrize("database", ["", "postgres", "v2_", "v2_bad-name", 'v2_bad"name',
                                     "v2_bad;SELECT 1", "v2_é", "v2_" + "x" * 61])
def test_invalid_name_fails_before_any_process_or_sql(harness, database):
    with pytest.raises(SystemExit) as exc:
        runner.main(arguments(harness, database=database))
    assert exc.value.code == 2
    assert harness.processes == harness.connections == []
    assert not (harness.root / "docs").exists()


def test_identifier_accepts_exactly_63_bytes_and_rejects_truncation():
    runner.validate_database_name("v2_" + "x" * 60)
    with pytest.raises(ValueError, match="63 bytes"):
        runner.validate_database_name("v2_" + "x" * 61)


def test_fresh_database_requires_caller_provided_name(harness):
    with pytest.raises(SystemExit):
        runner.main(arguments(harness, database=None))
    assert harness.processes == harness.connections == []


def test_missing_migrations_fails_before_startup(harness):
    for name in harness.sources:
        (harness.root / "database/migrations" / name).unlink()
    with pytest.raises(SystemExit):
        runner.main(arguments(harness))
    assert harness.processes == harness.connections == []


@pytest.mark.parametrize("status_code", [0, 4, 1])
def test_running_or_uncertain_cluster_is_never_started_or_stopped(harness, status_code):
    harness.status_code = status_code
    with pytest.raises(SystemExit):
        runner.main(arguments(harness))
    assert operations(harness) == ["status"]
    assert harness.connections == []


def test_existing_name_fails_closed_without_connecting_to_or_mutating_it(harness):
    harness.exists = True
    with pytest.raises(RuntimeError, match="already exists"):
        runner.main(arguments(harness))
    assert operations(harness) == ["status", "start", "stop"]
    assert [connection["dbname"] for connection in harness.connections] == ["postgres"]
    assert harness.created == harness.applied == []
    assert all(sql.startswith("SELECT") for _, sql, _ in harness.sql)
    assert harness.sql[-1][2] == ("v2_M3_unit",)
    receipt = read_receipt(harness)
    assert receipt["database_mode"] == "fresh"
    assert receipt["database_existed_before"] is True
    assert receipt["existing_database_oid"] == 9876
    assert receipt["existing_database_untouched"] is True
    assert receipt["database_created"] is receipt["database_retained"] is False
    assert receipt["server_stop"] == "stopped"
    assert receipt["checks_exit_code"] is None
    assert receipt["status"] == "ERROR"


def test_fresh_database_quotes_identifier_records_empty_identity_order_sha_and_keeps_data(harness):
    assert runner.main(arguments(harness)) == 0
    assert harness.created == ['CREATE DATABASE "v2_M3_unit" TEMPLATE "template0"']
    assert harness.applied == ["SELECT 1;\n", "SELECT 2;\n", "SELECT 20;\n"]
    assert harness.closed == ["postgres", "v2_M3_unit"]
    assert operations(harness) == ["status", "start", "tests/unchanged.py", "stop"]
    receipt = read_receipt(harness)
    assert receipt["database_existed_before"] is False
    assert receipt["database_created"] is receipt["database_retained"] is True
    assert receipt["database_oid"] == 12345
    assert receipt["endpoint"] == "127.0.0.1:55432/v2_M3_unit"
    assert receipt["maintenance_identity"]["database_oid"] == 5
    assert receipt["empty_before_migrations"]["is_empty"] is True
    assert receipt["empty_before_migrations"]["object_count"] == 0
    assert receipt["empty_before_migrations"]["objects"] == []
    assert receipt["migration_status"] == "applied"
    entries = receipt["migrations"]
    assert [entry["path"] for entry in entries] == [
        f"database/migrations/{name}" for name in sorted(harness.sources)]
    assert [entry["order"] for entry in entries] == [1, 2, 3]
    for entry in entries:
        original = harness.sources[Path(entry["path"]).name]
        assert entry["sha256"] == hashlib.sha256(original).hexdigest()
        assert (harness.root / entry["path"]).read_bytes() == original
        assert entry["status"] == "applied"
    assert receipt["status"] == "PASS"
    assert receipt["checks_exit_code"] == 0
    assert receipt["server_stop"] == "stopped"
    assert receipt["startup_ownership"] == "confirmed"
    assert receipt["cleanup_status"] == "completed"
    for connection in harness.connections:
        assert connection["host"] == "127.0.0.1"
        assert connection["port"] == 55432
        assert connection["user"] == "postgres"
        assert connection["autocommit"] is True
        assert connection["connect_timeout"] == runner.CONNECT_TIMEOUT_SECONDS
        assert connection["options"] == "-c statement_timeout=60000 -c lock_timeout=5000"
        assert "password" not in connection
    assert all("DROP DATABASE" not in sql and "TRUNCATE" not in sql for _, sql, _ in harness.sql)
    assert all(kwargs.get("timeout", 1) > 0 for _, kwargs in harness.processes)
    check_command = harness.processes[-2][0]
    assert check_command[2:] == ["--postgres-url", "postgresql://postgres@127.0.0.1:55432/v2_M3_unit",
                                 "dev-m3-pg-isolation-unit", "--", "python", "-m", "pytest", "tests/unchanged.py"]


@pytest.mark.parametrize("failure", ["connect", "create", "migration", "checks"])
def test_failures_stop_normally_and_retain_receipt_and_any_created_database(harness, failure):
    harness.failure = failure
    with pytest.raises((RuntimeError, subprocess.CalledProcessError)):
        runner.main(arguments(harness))
    assert operations(harness)[-1] == "stop"
    stop_command = harness.processes[-1][0]
    assert ["-m", "fast"] == stop_command[stop_command.index("-m"):stop_command.index("-m") + 2]
    receipt = read_receipt(harness)
    assert receipt["status"] == "ERROR"
    assert receipt["server_stop"] == "stopped"
    assert receipt["startup_ownership"] == "confirmed"
    assert receipt["cleanup_status"] == "completed"
    assert receipt["checks_exit_code"] is None
    created = failure in {"migration", "checks"}
    assert receipt["database_created"] is receipt["database_retained"] is created
    if failure == "migration":
        assert receipt["migration_status"] == "failed"
        assert [entry["status"] for entry in receipt["migrations"]] == ["failed", "pending", "pending"]
        assert "synthetic migration failure" in receipt["migrations"][0]["error"]
    if failure != "checks":
        assert all("run_v2_checks.py" not in " ".join(command) for command, _ in harness.processes)
    assert not any("DROP DATABASE" in sql or "TRUNCATE" in sql for _, sql, _ in harness.sql)


@pytest.mark.parametrize("failure", ["start", "start_timeout"])
def test_failed_or_uncertain_start_never_stops_an_unowned_server(harness, failure):
    harness.failure = failure
    with pytest.raises(subprocess.SubprocessError) as exc:
        runner.main(arguments(harness))
    assert exc.value is harness.start_error
    assert operations(harness) == ["status", "start"]
    assert harness.connections == harness.created == harness.applied == []
    receipt = read_receipt(harness)
    assert receipt["status"] == "ERROR"
    assert receipt["error"] == f"{type(harness.start_error).__name__}: {harness.start_error}"
    assert receipt["startup_ownership"] == receipt["cleanup_status"] == "unknown"
    assert receipt["server_stop"] == "not_attempted_unconfirmed_ownership"
    assert receipt["checks_exit_code"] is None
    assert receipt["database_created"] is receipt["database_retained"] is False


def test_nonempty_template_is_rejected_before_migrations_and_preserved(harness):
    harness.objects = [("relation", "public", "unexpected_table")]
    with pytest.raises(RuntimeError, match="not empty"):
        runner.main(arguments(harness))
    assert harness.applied == []
    receipt = read_receipt(harness)
    assert receipt["empty_before_migrations"]["is_empty"] is False
    assert receipt["database_retained"] is True
    assert receipt["server_stop"] == "stopped"
    assert receipt["checks_exit_code"] is None


def test_identity_mismatch_rejects_writes_and_stops(harness):
    harness.identity_database = "not_the_expected_database"
    with pytest.raises(RuntimeError, match="identity"):
        runner.main(arguments(harness))
    assert harness.created == harness.applied == []
    assert read_receipt(harness)["server_stop"] == "stopped"


def test_failed_checks_keep_original_exit_code_without_retry(harness):
    harness.checks_code = 7
    assert runner.main(arguments(harness)) == 7
    assert operations(harness).count("tests/unchanged.py") == 1
    receipt = read_receipt(harness)
    assert receipt["status"] == "FAIL"
    assert receipt["checks_exit_code"] == 7
    assert receipt["database_retained"] is True
    assert receipt["server_stop"] == "stopped"


def test_stop_failure_cannot_report_success(harness):
    harness.failure = "stop"
    with pytest.raises(subprocess.CalledProcessError):
        runner.main(arguments(harness))
    receipt = read_receipt(harness)
    assert receipt["status"] == "ERROR"
    assert receipt["checks_exit_code"] == 0
    assert receipt["server_stop"] == "failed"
    assert receipt["startup_ownership"] == "confirmed"
    assert receipt["cleanup_status"] == "failed"
    assert receipt["database_retained"] is True


def test_default_mode_reuses_legacy_database_without_creation_or_migration(harness):
    assert runner.main(arguments(harness, fresh=False, database=None)) == 0
    assert [connection["dbname"] for connection in harness.connections] == ["v2_creative_tests"]
    assert harness.created == harness.applied == []
    assert [sql for _, sql, _ in harness.sql] == [runner.IDENTITY_SQL]
    receipt = read_receipt(harness)
    assert receipt["database_mode"] == "reuse"
    assert receipt["database_created"] is False
    assert receipt["migration_status"] == "not_requested_reuse"
    assert receipt["migrations"] == []
    assert "empty_before_migrations" not in receipt
    assert receipt["endpoint"] == "127.0.0.1:55432/v2_creative_tests"
