"""Run V2 checks beside an existing disposable PostgreSQL cluster.

No downloads, installation, initialization, credentials, or external service are
performed. Server and checks share one process/network namespace. The supplied
cluster must be owned by this checkout under .runtime and already migrated.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pg-bin", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--port", type=int, default=55432)
    parser.add_argument("--database", default="v2_creative_tests")
    parser.add_argument("--user", default="postgres")
    parser.add_argument("label")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        pg_ctl, data = validate_owned_cluster(root, args.pg_bin, args.data)
    except ValueError as exc:
        parser.error(str(exc))
    if not re.fullmatch(r"[a-z0-9-]+", args.label):
        parser.error("label must be a simple lowercase identifier")
    if not re.fullmatch(r"v2_[a-zA-Z0-9_]+", args.database):
        parser.error("database must be a V2-owned v2_* name")
    if not re.fullmatch(r"[a-zA-Z0-9_]+", args.user) or not 1024 <= args.port <= 65535:
        parser.error("use a simple disposable user name and unprivileged TCP port")
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("provide a check command after --")
    status = subprocess.run([str(pg_ctl), "-D", str(data), "status"], capture_output=True)
    if status.returncode == 0:
        parser.error("cluster is already running; refusing to take ownership of another process")
    profile = root / ".runtime" / "v2-checks" / args.label
    profile.mkdir(parents=True, exist_ok=True)
    options = (f"-h 127.0.0.1 -p {args.port} -k '' -c shared_buffers=32MB "
               "-c max_connections=50 -c timezone=UTC -c log_timezone=UTC")
    subprocess.run([str(pg_ctl), "-D", str(data), "-l", str(profile / "postgres.log"),
                    "-o", options, "-w", "start"], check=True)
    try:
        import psycopg
        url = f"postgresql://{args.user}@127.0.0.1:{args.port}/{args.database}"
        sql = "SELECT version(), current_database(), host(inet_server_addr()), inet_server_port(), 1"
        with psycopg.connect(url) as connection:
            version, database, host, port, one = connection.execute(sql).fetchone()
            if (database, host, port, one) != (args.database, "127.0.0.1", args.port, 1):
                raise RuntimeError("live PostgreSQL identity does not match the owned endpoint")
        evidence = root / "docs" / "delivery" / "v2-development"
        evidence.mkdir(parents=True, exist_ok=True)
        receipt = {"utc": datetime.now(timezone.utc).isoformat(), "version": version,
                   "endpoint": f"{host}:{port}/{database}", "probe_sql": sql,
                   "probe_result": [version, database, host, port, one],
                   "data_path": data.relative_to(root).as_posix(),
                   "boundary": "real disposable PostgreSQL; loopback only; no model calls"}
        (evidence / f"{args.label}-postgres-runtime.json").write_text(
            json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(receipt), flush=True)
        return subprocess.run([sys.executable, str(root / "scripts/run_v2_checks.py"),
                               "--postgres-url", url, args.label, "--", *command], cwd=root).returncode
    finally:
        subprocess.run([str(pg_ctl), "-D", str(data), "-m", "fast", "-w", "stop"], check=True)


if __name__ == "__main__":
    raise SystemExit(main())
