"""Ownership-verified cleanup of TEST PostgreSQL databases created by a specific run.

SAFETY MODEL
  * Read-only by default. Nothing is dropped unless --execute is passed explicitly.
  * Ownership must be PROVEN four ways before any drop:
      1. the database name appears in a receipt from the SAME run label set (default: r3i-*)
      2. that receipt records database_created True and database_existed_before False
      3. the live database_oid equals the oid recorded at creation, and both are real integers
      4. the database has no other live session
    Any of these failing KEEPS the database.
  * The cluster must pass the repository's own validate_owned_cluster check, so a data directory
    that is not an owned disposable test cluster is refused.
  * Connections use loopback trust via psycopg, like scripts/run_v2_postgres_checks.py. No
    password is written to source, git or receipts.
  * autocommit is required: DROP DATABASE cannot run inside a transaction block.
  * pg_ctl start/stop detach their streams, because postgres inherits them and a captured pipe
    never closes, which hangs the caller.

EXIT CODES (a failed cleanup must never look like a pass)
  0  nothing to do, or every owned target was dropped
  1  a drop FAILED (partial failure)
  2  BLOCKED: cluster ownership unconfirmed, or a target could not be proven owned / was busy
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

EXIT_OK, EXIT_PARTIAL, EXIT_BLOCKED = 0, 1, 2


def load_runner(repo_root: Path):
    """Reuse the runner's own cluster-ownership and database-name validation."""
    path = repo_root / "scripts" / "run_v2_postgres_checks.py"
    spec = importlib.util.spec_from_file_location("_v2_pg_runner", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def claimed_databases(receipts_dir: Path, pattern: str):
    """Return (owned, blocked). A receipt contributes ONLY if it proves creation.

    Conflicting receipts for the same database, or a missing/malformed oid, are treated as
    UNPROVEN and the database is kept.
    """
    owned: dict[str, dict] = {}
    blocked: list[tuple[str, str]] = []
    seen: dict[str, list] = {}
    for path in sorted(receipts_dir.glob(pattern)):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(data, dict):
            continue
        name = data.get("database")
        if not name or not re.fullmatch(r"v2_[a-z0-9_]+", str(name)):
            continue
        seen.setdefault(str(name), []).append((path.name, data))

    for name, entries in sorted(seen.items()):
        oids, proven = set(), False
        for _src, data in entries:
            if data.get("database_created") is True and data.get("database_existed_before") is False:
                proven = True
                oids.add(data.get("database_oid"))
        if not proven:
            blocked.append((name, "no receipt proves this run created it"))
            continue
        if len(oids) != 1:
            blocked.append((name, f"contradictory oids across receipts: {sorted(map(str, oids))}"))
            continue
        oid = oids.pop()
        if not isinstance(oid, int) or isinstance(oid, bool) or oid <= 0:
            blocked.append((name, f"receipt oid is not a valid integer oid: {oid!r}"))
            continue
        owned[name] = {"oid": oid, "sources": [s for s, _ in entries]}
    return owned, blocked


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--pg-bin", required=True, type=Path, help="PostgreSQL bin directory")
    parser.add_argument("--data", required=True, type=Path, help="owned test cluster data dir")
    parser.add_argument("--port", type=int, default=55433)
    parser.add_argument("--host", default="127.0.0.1", help="loopback only")
    parser.add_argument("--user", default="novel_ci")
    parser.add_argument("--receipts", type=Path, default=None)
    parser.add_argument("--pattern", default="r3i-*.json",
                        help="receipt glob; only these runs are ever acted on")
    parser.add_argument("--execute", action="store_true",
                        help="actually drop; without it this is a read-only precheck")
    args = parser.parse_args(argv)

    if args.host not in {"127.0.0.1", "::1", "localhost"}:
        print(f"refusing to connect to a non-loopback host: {args.host}")
        return EXIT_BLOCKED
    receipts = args.receipts or (args.repo_root / "docs" / "delivery" / "v2-development")
    if not args.data.is_dir():
        print(f"cluster data directory does not exist: {args.data}")
        return EXIT_BLOCKED

    runner = load_runner(args.repo_root)
    try:
        # The repository's own guard: refuses a data directory that is not an owned cluster.
        runner.validate_owned_cluster(args.repo_root, str(args.pg_bin), str(args.data))
    except Exception as exc:  # noqa: BLE001
        print(f"BLOCKED: cluster ownership not confirmed: {exc}")
        return EXIT_BLOCKED

    owned, blocked = claimed_databases(receipts, args.pattern)
    print(f"mode: {'EXECUTE' if args.execute else 'PRECHECK (read-only)'}")
    print(f"receipts scanned: {receipts} pattern={args.pattern}")
    print("proven-owned candidates:")
    for name, info in sorted(owned.items()):
        print(f"  {name}  oid={info['oid']}  from {info['sources']}")
    if blocked:
        print("NOT proven (kept):")
        for name, why in blocked:
            print(f"  {name}: {why}")
    if not owned:
        print("nothing provably owned; no database will be dropped")
        return EXIT_BLOCKED if blocked else EXIT_OK
    if not args.execute:
        print("precheck only: re-run with --execute to drop the candidates above")
        return EXIT_OK

    try:
        import psycopg
        from psycopg import sql
    except Exception as exc:  # noqa: BLE001
        print(f"BLOCKED: psycopg unavailable: {exc}")
        return EXIT_BLOCKED

    started_here = False
    try:
        status = subprocess.run([str(args.pg_bin / "pg_ctl.exe"), "-D", str(args.data), "status"],
                                capture_output=True, text=True, timeout=30)
        status_text = status.stdout + status.stderr
    except Exception:  # noqa: BLE001
        status_text = ""
    if "no server running" in status_text:
        print("cluster stopped; starting it only for this owned cleanup")
        start = subprocess.run(
            [str(args.pg_bin / "pg_ctl.exe"), "-D", str(args.data), "-w", "-t", "30",
             "-o", f"-h {args.host} -p {args.port}",
             "-l", str(args.repo_root / ".runtime" / "pg-cleanup.log"), "start"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
            timeout=90)
        if start.returncode != 0:
            print("BLOCKED: could not start the owned cluster; see .runtime/pg-cleanup.log")
            return EXIT_BLOCKED
        started_here = True

    dropped, kept, failed, remaining = [], [], [], []
    try:
        with psycopg.connect(host=args.host, port=args.port, dbname="postgres", user=args.user,
                             connect_timeout=5, autocommit=True) as conn:
            identity = conn.execute(
                "SELECT current_database(), inet_server_port(), "
                "(SELECT oid::bigint FROM pg_catalog.pg_database WHERE datname='postgres')"
            ).fetchone()
            print(f"connected to {args.host}:{identity[1]}/{identity[0]} as {args.user}")
            for name, info in sorted(owned.items()):
                row = conn.execute("SELECT oid::bigint FROM pg_catalog.pg_database "
                                   "WHERE datname = %s", (name,)).fetchone()
                if row is None:
                    print(f"  {name}: already gone")
                    continue
                live_oid = int(row[0])
                if live_oid != info["oid"]:
                    kept.append((name, f"live oid {live_oid} != recorded {info['oid']}"))
                    continue
                sessions = conn.execute(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE datname = %s AND pid <> pg_backend_pid()", (name,)).fetchone()[0]
                if sessions:
                    kept.append((name, f"{sessions} live session(s)"))
                    continue
                try:
                    conn.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
                    dropped.append(name)
                    print(f"  {name}: DROPPED (oid {live_oid} matched the receipt)")
                except Exception as exc:  # noqa: BLE001
                    failed.append((name, str(exc)))
            remaining = [r[0] for r in conn.execute(
                "SELECT datname FROM pg_database WHERE datname LIKE 'v2\\_%' ORDER BY 1").fetchall()]
    finally:
        if started_here:
            subprocess.run([str(args.pg_bin / "pg_ctl.exe"), "-D", str(args.data),
                            "-m", "fast", "stop"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           stdin=subprocess.DEVNULL, timeout=90)

    print("\nRESULT")
    print("  dropped:", dropped or "none")
    print("  kept (ownership not proven or busy):", kept or "none")
    print("  failed:", failed or "none")
    print("  remaining v2_% databases:", remaining or "none")
    if failed:
        return EXIT_PARTIAL
    if kept:
        return EXIT_BLOCKED
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
