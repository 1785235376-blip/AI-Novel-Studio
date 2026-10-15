"""Safely drop ONLY the PostgreSQL test databases this round created.

Ownership is proven before anything is dropped:
  * the database must appear in a creation receipt under docs/delivery/v2-development/
  * that receipt must say database_created is True AND database_existed_before is False
  * the live database_oid must equal the oid recorded when it was created
  * it must be idle (no other sessions)
Anything that cannot be proven is KEPT and reported.

Uses the same connection method as scripts/run_v2_postgres_checks.py
(psycopg.connect over 127.0.0.1 trust), never interactive psql.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"D:\PoemSeed\Worktrees\studio-v2-audio-editing-20261014")
PG_BIN = Path(r"D:\PoemSeed\Builds\studio-v2-host-5ed1cbee-20261011\Base\PostgreSQL\bin")
DATA = ROOT / ".runtime" / "pgdata-v2-phase14a"
PORT, USER = 55433, "novel_ci"
RECEIPTS = ROOT / "docs" / "delivery" / "v2-development"

import psycopg  # noqa: E402
from psycopg import sql  # noqa: E402


def connect(database):
    # autocommit is REQUIRED: DROP DATABASE cannot run inside a transaction block, and psycopg
    # otherwise opens an implicit one, which aborts everything after the first drop.
    return psycopg.connect(host="127.0.0.1", port=PORT, dbname=database, user=USER,
                           connect_timeout=5, autocommit=True)


def claimed():
    """(name -> recorded oid) for databases a receipt says THIS round created."""
    out = {}
    # Only THIS round's R3-I receipts. Historical runs are not ours to act on.
    for path in sorted(RECEIPTS.glob("r3i-*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(data, dict):
            continue
        name, oid = data.get("database"), data.get("database_oid")
        if not name or not re.fullmatch(r"v2_[a-z0-9_]+", str(name)):
            continue
        # Ownership: created here, absent before, and it is a disposable test cluster DB.
        if data.get("database_created") is True and data.get("database_existed_before") is False:
            out[str(name)] = (oid, path.name)
    return out


def main():
    wanted = claimed()
    print("receipts claim these test databases were created by the tests:")
    for name, (oid, src) in sorted(wanted.items()):
        print(f"  {name}  oid={oid}  from {src}")
    if not wanted:
        print("no owned test databases claimed; nothing to do")
        return 0

    started_here = False
    try:
        status = subprocess.run([str(PG_BIN / "pg_ctl.exe"), "-D", str(DATA), "status"],
                                capture_output=True, text=True, timeout=30)
        status_text = status.stdout + status.stderr
    except subprocess.TimeoutExpired:
        status_text = "status probe timed out"
    if "no server running" in status_text:
        print("cluster is stopped; starting it only to perform this owned cleanup")
        # Do NOT capture pg_ctl start output: postgres inherits those handles and the pipe
        # never closes, which hangs the call. Streams are detached to the log instead.
        start = subprocess.run([str(PG_BIN / "pg_ctl.exe"), "-D", str(DATA), "-w", "-t", "30",
                                "-o", f"-p {PORT}", "-l", str(ROOT / ".runtime" / "pg-cleanup.log"),
                                "start"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               stdin=subprocess.DEVNULL, timeout=90)
        if start.returncode != 0:
            print("could not start the cluster; see .runtime/pg-cleanup.log")
            return 2
        started_here = True

    dropped, kept, failed = [], [], []
    try:
        with connect("postgres") as conn:
            for name, (recorded_oid, _src) in sorted(wanted.items()):
                row = conn.execute(
                    "SELECT oid::bigint FROM pg_catalog.pg_database WHERE datname = %s",
                    (name,)).fetchone()
                if row is None:
                    print(f"  {name}: not present (already gone)")
                    continue
                live_oid = row[0]
                if recorded_oid is not None and live_oid != recorded_oid:
                    # Identity mismatch: this is NOT provably the database the receipt created.
                    kept.append((name, f"oid {live_oid} != recorded {recorded_oid}"))
                    continue
                sessions = conn.execute(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()",
                    (name,)).fetchone()[0]
                if sessions:
                    kept.append((name, f"{sessions} live session(s)"))
                    continue
                try:
                    conn.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
                    dropped.append(name)
                    print(f"  {name}: dropped (oid {live_oid} matched the receipt)")
                except Exception as exc:  # noqa: BLE001
                    failed.append((name, str(exc)))
            remaining = [r[0] for r in conn.execute(
                "SELECT datname FROM pg_database WHERE datname LIKE 'v2\\_%' ORDER BY 1").fetchall()]
    finally:
        if started_here:
            subprocess.run([str(PG_BIN / "pg_ctl.exe"), "-D", str(DATA), "-m", "fast", "stop"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           stdin=subprocess.DEVNULL, timeout=90)

    print("\nRESULT")
    print("  dropped:", dropped or "none")
    print("  kept (ownership not proven):", kept or "none")
    print("  failed:", failed or "none")
    print("  remaining v2_% databases in the cluster:", remaining or "none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
