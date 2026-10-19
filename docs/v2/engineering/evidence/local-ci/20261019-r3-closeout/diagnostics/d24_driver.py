"""D-24 diagnostic reproduction on real PostgreSQL (driver for d24_probe plugin)."""
from __future__ import annotations
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(r"[repo]")
RUN = Path(r"[engineering-runs]")
PGBIN = Path(r"[portable-postgres-bin]")
DATA = ROOT / ".runtime" / "pg-r3" / "data"
PORT = 55432
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
PREFIX = os.environ.get("D24_PREFIX", "d24")
DRIVER_LOG = RUN / (PREFIX + "-driver.log")
PYTEST_LOG = RUN / (PREFIX + "-pytest.log")
PG_LOG = RUN / (PREFIX + "-postgres.log")
NODE = os.environ.get("D24_NODE", ("tests/test_v2_text_execution_receipts.py::"
        "test_receipt_preserves_exact_request_original_identity_and_terminal_time[postgres]"))
CHILD_TIMEOUT = 180
DETACHED = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)

sys.path.insert(0, str(ROOT / "scripts"))
from run_v2_checks import isolated_environment  # noqa: E402

log = open(DRIVER_LOG, "w", encoding="utf-8", errors="replace")


def say(*parts):
    line = " ".join(str(part) for part in parts)
    log.write(line + "\n")
    log.flush()


pg_ctl = PGBIN / "pg_ctl.exe"
status = subprocess.run([str(pg_ctl), "-D", str(DATA), "status"], capture_output=True, text=True, timeout=30)
if status.returncode == 0:
    subprocess.run([str(pg_ctl), "-D", str(DATA), "-m", "immediate", "-t", "30", "-w", "stop"], timeout=90, **DETACHED)
options = subprocess.list2cmdline(["-h", "127.0.0.1", "-p", str(PORT),
                                   "-c", "shared_buffers=32MB", "-c", "max_connections=50",
                                   "-c", "timezone=UTC", "-c", "log_timezone=UTC",
                                   "-c", "log_connections=on"])
start = subprocess.run([str(pg_ctl), "-D", str(DATA), "-l", str(PG_LOG), "-o", options,
                        "-t", "60", "-w", "start"], timeout=90, **DETACHED)
say("PG_START_EXIT", start.returncode)
if start.returncode != 0:
    raise SystemExit(2)

import psycopg  # noqa: E402

database = "v2_d24_" + str(int(time.time()))
with psycopg.connect(host="127.0.0.1", port=PORT, dbname="postgres", user="postgres",
                     autocommit=True, connect_timeout=10) as maintenance:
    maintenance.execute("CREATE DATABASE " + database + " TEMPLATE template0")
say("DB_CREATED", database)
migration_count = 0
with psycopg.connect(host="127.0.0.1", port=PORT, dbname=database, user="postgres",
                     autocommit=True, connect_timeout=10) as connection:
    for migration in sorted((ROOT / "database/migrations").glob("*.sql")):
        connection.execute(migration.read_text(encoding="utf-8").replace("\r\n", "\n"))
        migration_count += 1
say("MIGRATIONS_APPLIED", migration_count)

profile = ROOT / ".runtime" / "d24-instrumented"
profile.mkdir(parents=True, exist_ok=True)
(profile / "tmp").mkdir(parents=True, exist_ok=True)
env = {key: value for key, value in os.environ.items()
       if not key.endswith(("_API_KEY", "_TOKEN", "_SECRET"))}
env.update(isolated_environment(ROOT, profile))
url = "postgresql://postgres@127.0.0.1:" + str(PORT) + "/" + database
env.update({
    "STORAGE_BACKEND": "postgres",
    "DATABASE_URL": url,
    "TEST_POSTGRES_DATABASE_URL": url,
    "EXPERIMENTAL_FEATURES": "narrative_production_v2,asset_lineage_v2,ai_execution_v2,author_context_inspector_v2,model_broker_v2",
    "PYTHONPATH": os.pathsep.join([str(ROOT), str(RUN)]),
    "PYTHONUNBUFFERED": "1",
    "D24_METRICS_PATH": str(RUN / (PREFIX + "-metrics.json")),
    "TMP": str(profile / "tmp"),
    "TEMP": str(profile / "tmp"),
    "TMPDIR": str(profile / "tmp"),
})
command = [str(PYTHON), "-m", "pytest", "-q", "-s", "-p", "no:cacheprovider", "-p", "d24_probe",
           "--basetemp", str(profile / "pytest"), "-x", NODE]
say("PYTEST_CMD", subprocess.list2cmdline(command))

stop_watch = threading.Event()
no_watch = os.environ.get("D24_NO_WATCH") == "1"


def watch_postgres():
    try:
        import psycopg
    except Exception:
        return
    while not stop_watch.is_set():
        try:
            with psycopg.connect(host="127.0.0.1", port=PORT, dbname=database, user="postgres",
                                 connect_timeout=3) as watcher:
                rows = watcher.execute(
                    "SELECT pid, state, coalesce(wait_event_type,''), coalesce(wait_event,''), "
                    "coalesce(array_to_string(pg_blocking_pids(pid), ','),''), left(coalesce(query,''),60) "
                    "FROM pg_stat_activity WHERE datname = %s ORDER BY pid", (database,)).fetchall()
                log.write("PG_ACTIVITY " + repr([tuple(str(value) for value in row) for row in rows]) + "\n")
                log.flush()
        except Exception as exc:  # noqa: BLE001
            log.write("PG_ACTIVITY_ERROR " + type(exc).__name__ + "\n")
            log.flush()
        stop_watch.wait(2)


watcher = None
if not no_watch:
    watcher = threading.Thread(target=watch_postgres, name="pg-watcher", daemon=True)
    watcher.start()
started = time.monotonic()
with open(PYTEST_LOG, "w", encoding="utf-8", errors="replace") as pytest_log:
    process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=pytest_log, stderr=subprocess.STDOUT,
                               stdin=subprocess.DEVNULL)
    say("PYTEST_PID", process.pid)
    try:
        code = process.wait(timeout=CHILD_TIMEOUT)
        say("PYTEST_EXIT", code, "SECONDS", round(time.monotonic() - started, 1))
    except subprocess.TimeoutExpired:
        say("PYTEST_TIMED_OUT", round(time.monotonic() - started, 1), "seconds; killing")
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)], capture_output=True, text=True)
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            say("PYTEST_KILL_FAILED")
stop_watch.set()
if watcher is not None:
    watcher.join(timeout=10)
stop = subprocess.run([str(pg_ctl), "-D", str(DATA), "-m", "fast", "-t", "60", "-w", "stop"],
                      timeout=120, **DETACHED)
say("PG_STOP_EXIT", stop.returncode)
say("DONE", database)