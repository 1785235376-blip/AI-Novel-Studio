"""Run V2 checks beside an existing disposable PostgreSQL cluster.

No downloads, installation, cluster initialization, credentials, or external service are
performed. Server and checks share one process/network namespace. The supplied
cluster must be owned by this checkout under .runtime. Diagnostic reuse remains
the default; stage checks should use --fresh-database --database v2_<unique_name>.
Fresh databases use the original sorted migrations and are retained for evidence.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


CONNECT_TIMEOUT_SECONDS = 5
STATEMENT_TIMEOUT_MS = 60000
LOCK_TIMEOUT_MS = 5000
PG_CTL_TIMEOUT_SECONDS = 60
IDENTITY_SQL = (
    "SELECT version(), current_database(), host(inet_server_addr()), inet_server_port(), 1, "
    "(SELECT oid::bigint FROM pg_catalog.pg_database WHERE datname = current_database()), "
    "current_user"
)
# template0 contains public and plpgsql, but must not contain application objects.
EMPTY_DATABASE_SQL = """
SELECT 'relation', n.nspname, c.relname
FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema') AND left(n.nspname, 3) <> 'pg_'
UNION ALL
SELECT 'routine', n.nspname, p.proname
FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema') AND left(n.nspname, 3) <> 'pg_'
UNION ALL
SELECT 'type', n.nspname, t.typname
FROM pg_catalog.pg_type t JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema') AND left(n.nspname, 3) <> 'pg_'
UNION ALL
SELECT 'schema', '', nspname FROM pg_catalog.pg_namespace
WHERE nspname NOT IN ('pg_catalog', 'information_schema', 'public') AND left(nspname, 3) <> 'pg_'
UNION ALL
SELECT 'extension', '', extname FROM pg_catalog.pg_extension WHERE extname <> 'plpgsql'
ORDER BY 1, 2, 3
""".strip()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_owned_cluster(root: Path, pg_bin: Path, data: Path) -> tuple[Path, Path]:
    root, pg_bin, data = root.resolve(), pg_bin.resolve(), data.resolve()
    if not data.is_relative_to(root / ".runtime"):
        raise ValueError("PostgreSQL data must be owned by this checkout under .runtime")
    suffix = ".exe" if sys.platform == "win32" else ""
    if not (pg_bin / ("pg_ctl" + suffix)).is_file():
        raise ValueError("--pg-bin must contain an existing pg_ctl executable")
    if not (data / "PG_VERSION").is_file():
        raise ValueError("--data must be an existing disposable PostgreSQL cluster")
    return pg_bin / ("pg_ctl" + suffix), data


def validate_database_name(database: str) -> None:
    if not re.fullmatch(r"v2_[a-zA-Z0-9_]+", database) or len(database.encode("utf-8")) > 63:
        raise ValueError("database must be a V2-owned v2_* name of at most 63 bytes")


def load_migrations(root: Path) -> list[tuple[dict, str]]:
    """Snapshot original bytes and the same UTF-8/newline decoding as CI read_text."""
    migrations = []
    for order, path in enumerate(sorted((root / "database/migrations").glob("*.sql")), 1):
        raw = path.read_bytes()
        statement = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        migrations.append(({"order": order, "path": path.relative_to(root).as_posix(),
                            "sha256": hashlib.sha256(raw).hexdigest(), "status": "pending"}, statement))
    if not migrations:
        raise ValueError("fresh database requires the original database/migrations/*.sql files")
    return migrations


def connect_database(psycopg, database: str, user: str, port: int):
    return psycopg.connect(host="127.0.0.1", port=port, dbname=database, user=user,
                           autocommit=True, connect_timeout=CONNECT_TIMEOUT_SECONDS,
                           options=f"-c statement_timeout={STATEMENT_TIMEOUT_MS} -c lock_timeout={LOCK_TIMEOUT_MS}")


def live_identity(connection, database: str, user: str, port: int) -> dict:
    row = connection.execute(IDENTITY_SQL).fetchone()
    if row is None or len(row) != 7:
        raise RuntimeError("live PostgreSQL identity probe returned no complete result")
    version, actual_database, host, actual_port, one, oid, actual_user = row
    if ((actual_database, host, actual_port, one, actual_user) !=
            (database, "127.0.0.1", port, 1, user) or not isinstance(oid, int) or oid <= 0):
        raise RuntimeError("live PostgreSQL identity does not match the owned endpoint and user")
    return {"version": version, "endpoint": f"{host}:{actual_port}/{actual_database}",
            "database_oid": oid, "database_user": actual_user,
            "probe_sql": IDENTITY_SQL, "probe_result": list(row)}


def prepare_database(psycopg, args, migrations: list[tuple[dict, str]], receipt: dict) -> str:
    if args.fresh_database:
        from psycopg import sql
        with connect_database(psycopg, "postgres", args.user, args.port) as connection:
            receipt["maintenance_identity"] = live_identity(connection, "postgres", args.user, args.port)
            existing = connection.execute(
                "SELECT oid::bigint FROM pg_catalog.pg_database WHERE datname = %s", (args.database,)
            ).fetchone()
            receipt["database_existed_before"] = existing is not None
            if existing is not None:
                receipt["existing_database_oid"] = existing[0]
                receipt["existing_database_untouched"] = True
                raise RuntimeError("fresh database already exists; refusing to reuse or change it")
            # Identifier quoting prevents case-folding as well as SQL injection.
            connection.execute(sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
                sql.Identifier(args.database), sql.Identifier("template0")))
            receipt["database_created"] = True
            receipt["database_retained"] = True
            receipt["database_created_utc"] = utc_now()
    with connect_database(psycopg, args.database, args.user, args.port) as connection:
        receipt.update(live_identity(connection, args.database, args.user, args.port))
        if args.fresh_database:
            objects = connection.execute(EMPTY_DATABASE_SQL).fetchall()
            receipt["empty_before_migrations"] = {
                "sql": EMPTY_DATABASE_SQL, "objects": [list(row) for row in objects],
                "object_count": len(objects), "is_empty": not objects,
            }
            if objects:
                raise RuntimeError("fresh database is not empty; refusing to apply migrations")
            receipt["migration_status"] = "running"
            for entry, statement in migrations:
                entry["started_utc"] = utc_now()
                try:
                    # Keep CI's autocommit connection and one execute per original file.
                    connection.execute(statement)
                except BaseException as exc:
                    entry.update(status="failed", error=f"{type(exc).__name__}: {exc}", finished_utc=utc_now())
                    receipt["migration_status"] = "failed"
                    raise
                entry.update(status="applied", finished_utc=utc_now())
            receipt["migration_status"] = "applied"
    return f"postgresql://{args.user}@127.0.0.1:{args.port}/{args.database}"


def write_receipt(path: Path, receipt: dict) -> None:
    path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pg-bin", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--port", type=int, default=55432)
    parser.add_argument("--database", default=None)
    parser.add_argument("--fresh-database", action="store_true",
                        help="create the explicitly named new database; reject existing names and retain all data")
    parser.add_argument("--user", default="postgres")
    parser.add_argument("label")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    if args.fresh_database and args.database is None:
        parser.error("--fresh-database requires an explicit --database v2_* name")
    if args.database is None:
        args.database = "v2_creative_tests"
    try:
        pg_ctl, data = validate_owned_cluster(root, args.pg_bin, args.data)
        validate_database_name(args.database)
        migrations = load_migrations(root) if args.fresh_database else []
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    if not re.fullmatch(r"[a-z0-9-]+", args.label):
        parser.error("label must be a simple lowercase identifier")
    if not re.fullmatch(r"[a-zA-Z0-9_]+", args.user) or not 1024 <= args.port <= 65535:
        parser.error("use a simple disposable user name and unprivileged TCP port")
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("provide a check command after --")
    # Dependencies and every local input are checked before starting a server.
    import psycopg
    status = subprocess.run([str(pg_ctl), "-D", str(data), "status"], capture_output=True, timeout=10)
    if status.returncode == 0:
        parser.error("cluster is already running; refusing to take ownership of another process")
    if status.returncode != 3:
        parser.error("cannot establish that the owned PostgreSQL cluster is stopped")
    profile = root / ".runtime" / "v2-checks" / args.label
    profile.mkdir(parents=True, exist_ok=True)
    evidence = root / "docs" / "delivery" / "v2-development"
    evidence.mkdir(parents=True, exist_ok=True)
    receipt_path = evidence / f"{args.label}-postgres-runtime.json"
    receipt = {
        "utc": utc_now(), "database_mode": "fresh" if args.fresh_database else "reuse",
        "database": args.database, "database_created": False,
        "database_retained": not args.fresh_database, "database_existed_before": None,
        "data_path": data.relative_to(root).as_posix(),
        "boundary": "real disposable PostgreSQL; loopback only; no model calls",
        "migration_status": "pending" if args.fresh_database else "not_requested_reuse",
        "migrations": [entry for entry, _ in migrations],
        "harness_timeouts": {"connect_seconds": CONNECT_TIMEOUT_SECONDS,
                             "statement_ms": STATEMENT_TIMEOUT_MS, "lock_ms": LOCK_TIMEOUT_MS},
        "status": "starting", "checks_exit_code": None, "server_stop": "pending",
        "startup_ownership": "unconfirmed", "cleanup_status": "pending",
    }
    write_receipt(receipt_path, receipt)
    options = (f"-h 127.0.0.1 -p {args.port} -k '' -c shared_buffers=32MB "
               "-c max_connections=50 -c timezone=UTC -c log_timezone=UTC")
    primary_error = None
    startup_confirmed = False
    try:
        subprocess.run([str(pg_ctl), "-D", str(data), "-l", str(profile / "postgres.log"),
                        "-o", options, "-t", str(PG_CTL_TIMEOUT_SECONDS), "-w", "start"],
                       check=True, timeout=PG_CTL_TIMEOUT_SECONDS + 10)
        startup_confirmed = True
        receipt["startup_ownership"] = "confirmed"
        receipt["status"] = "preparing"
        url = prepare_database(psycopg, args, migrations, receipt)
        receipt["status"] = "checking"
        write_receipt(receipt_path, receipt)
        print(json.dumps(receipt), flush=True)
        result = subprocess.run([sys.executable, str(root / "scripts/run_v2_checks.py"),
                                 "--postgres-url", url, args.label, "--", *command], cwd=root)
        receipt["checks_exit_code"] = result.returncode
        receipt["status"] = "PASS" if result.returncode == 0 else "FAIL"
        return result.returncode
    except BaseException as exc:
        primary_error = exc
        receipt.update(status="ERROR", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        # Only successful startup establishes ownership. A failed/timed-out start
        # could race another server; never stop an unconfirmed process.
        stop_error = None
        try:
            if startup_confirmed:
                # Preserve all databases, even after create/migration/test failure.
                subprocess.run([str(pg_ctl), "-D", str(data), "-m", "fast", "-t",
                                str(PG_CTL_TIMEOUT_SECONDS), "-w", "stop"],
                               check=True, timeout=PG_CTL_TIMEOUT_SECONDS + 10)
                receipt.update(server_stop="stopped", cleanup_status="completed")
            else:
                receipt.update(startup_ownership="unknown", cleanup_status="unknown",
                               server_stop="not_attempted_unconfirmed_ownership")
        except BaseException as exc:
            stop_error = exc
            receipt.update(server_stop="failed", cleanup_status="failed", status="ERROR",
                           stop_error=f"{type(exc).__name__}: {exc}")
        finally:
            receipt["finished_utc"] = utc_now()
            write_receipt(receipt_path, receipt)
            print(json.dumps(receipt), flush=True)
        if stop_error is not None and primary_error is None:
            raise stop_error


if __name__ == "__main__":
    raise SystemExit(main())
