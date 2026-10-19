"""D-24 diagnostic/measurement probe (test-only; not committed)."""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import traceback
import weakref
from pathlib import Path

import app.jobs as jobs_module

MANAGERS = weakref.WeakSet()
STARTED = time.monotonic()
COUNTS = {"store_reads": 0, "direct_connect_attempts": 0, "pool_new_connections": 0,
          "pool_checkouts": 0, "pool_peak": 0, "pool_active": 0, "persists": 0, "emits": 0, "hooks": 0}
QUIET = os.environ.get("D24_QUIET") == "1"
UNPOOLED = os.environ.get("D24_FORCE_UNPOOLED") == "1"


def log(message: str) -> None:
    if QUIET and not message.startswith(("METRICS", "REPLAY", "PROBE")):
        return
    print("[D24 %7.2fs %s] %s" % (time.monotonic() - STARTED, threading.current_thread().name, message),
          file=sys.stderr, flush=True)


def _dump_threads() -> None:
    frames = sys._current_frames()
    log("THREAD_DUMP threads=%d" % len(threading.enumerate()))
    for thread in threading.enumerate():
        frame = frames.get(thread.ident)
        frames_list = traceback.extract_stack(frame, limit=40) if frame else []
        compact = ["%s:%d:%s" % (Path(item.filename).name, item.lineno, item.name) for item in frames_list]
        log("THREAD %s daemon=%s alive=%s stack=%s" % (
            thread.name, thread.daemon, thread.is_alive(), " <- ".join(reversed(compact[-18:]))))
    for manager in list(MANAGERS):
        for job_id, job in list(getattr(manager, "jobs", {}).items()):
            log("JOB %s status=%s hook=%s outcome=%s output_len=%s error=%s" % (
                job_id, job.status, job.terminal_hook_status, job.execution_outcome,
                len(job.output or ""), job.error_code))


def _watchdog() -> None:
    while True:
        time.sleep(3)
        _dump_threads()


def pytest_configure(config):
    faulthandler_enabled = True
    import faulthandler
    if faulthandler_enabled:
        faulthandler.enable()

    original_init = jobs_module.JobManager.__init__

    def init_wrapper(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        MANAGERS.add(self)

    jobs_module.JobManager.__init__ = init_wrapper

    original_persist = jobs_module.JobManager._persist

    def persist_wrapper(self, job):
        COUNTS["persists"] += 1
        return original_persist(self, job)

    jobs_module.JobManager._persist = persist_wrapper

    original_hook = jobs_module.JobManager._finish_terminal_hook

    def hook_wrapper(self, job):
        COUNTS["hooks"] += 1
        return original_hook(self, job)

    jobs_module.JobManager._finish_terminal_hook = hook_wrapper

    original_emit = jobs_module.JobManager._emit

    def emit_wrapper(self, job, chunk=""):
        COUNTS["emits"] += 1
        return original_emit(self, job, chunk)

    jobs_module.JobManager._emit = emit_wrapper

    import app.experimental.store as store_module
    import app.repositories.postgres.connection as connection_module

    original_store_read = store_module.ExperimentalStore.read

    def store_read_wrapper(self, nid, scope):
        COUNTS["store_reads"] += 1
        return original_store_read(self, nid, scope)

    store_module.ExperimentalStore.read = store_read_wrapper

    if UNPOOLED:
        def unpooled_connect(self):
            if not self.database_url:
                raise ValueError("PostgreSQL experimental store requires DATABASE_URL")
            COUNTS["direct_connect_attempts"] += 1
            return connection_module.connect(self.database_url)

        store_module.ExperimentalStore._connect = unpooled_connect
        log("REPLAY unpooled experimental store path enabled")

    from sqlalchemy import event

    original_engine_for_url = connection_module.engine_for_url

    def engine_wrapper(url):
        engine = original_engine_for_url(url)
        if not getattr(engine, "_d24_instrumented", False):
            engine._d24_instrumented = True

            def on_connect(*args, **kwargs):
                COUNTS["pool_new_connections"] += 1

            def on_checkout(*args, **kwargs):
                COUNTS["pool_checkouts"] += 1
                COUNTS["pool_active"] += 1
                COUNTS["pool_peak"] = max(COUNTS["pool_peak"], COUNTS["pool_active"])

            def on_checkin(*args, **kwargs):
                COUNTS["pool_active"] -= 1

            event.listen(engine, "connect", on_connect)
            event.listen(engine.pool, "checkout", on_checkout)
            event.listen(engine.pool, "checkin", on_checkin)
        return engine

    connection_module.engine_for_url = engine_wrapper

    if not QUIET:
        threading.Thread(target=_watchdog, name="d24-watchdog", daemon=True).start()
    log("PROBE INSTALLED unpooled=%s" % UNPOOLED)


def pytest_sessionfinish(session, exitstatus):
    payload = {"exit_status": int(exitstatus), "seconds": round(time.monotonic() - STARTED, 2),
               "unpooled_replay": UNPOOLED, **COUNTS}
    path = Path(os.environ.get("D24_METRICS_PATH", "d24-metrics.json"))
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        log("METRICS_WRITE_FAILED " + type(exc).__name__)
    log("METRICS " + json.dumps(payload, ensure_ascii=False))
