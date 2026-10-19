
# Diagnostics provenance, counter definitions and limits

These diagnostics are the **Round-3 originals**, archived at closeout from
`Engineering-Runs/local-ci-round3-20261019/` (scripts and logs) plus the recovered original
`pool-regression-file` outputs. They are not new runs. The only new runs in this closeout are the
closeout verification runs recorded in the parent `SUMMARY.md` and `verification-summary.json`
(execution SHA `5e278819`).

## Materials

| File | What it is |
| --- | --- |
| `d24_driver.py` | Round-3 diagnostic driver: creates a fresh database, applies migrations, runs one pytest node with the probe plugin, optionally starts a `pg_stat_activity` watcher. Host paths replaced with `[repo]/[engineering-runs]/[portable-postgres-bin]`. |
| `d24_probe.py` | The actual pytest plugin used for the D-24 investigation/measurement (JobManager/store/connection instrumentation, pool events, thread-dump watchdog, metrics JSON). |
| `metrics-unpooled-replay-d24.json` | Probe metrics for the test-only replay of the old unpooled store path (`D24_FORCE_UNPOOLED=1`). |
| `metrics-pooled-d24.json` | Probe metrics for the fixed pooled path, same node/environment. |
| `metrics-pooled-d07-storm.json` | Probe metrics for the D-07 connection-storm node (the probe patches do not instrument that path, so counters are 0 by construction, not "no work"). |
| `thread-dumps-postfix-sample.txt` | Surviving watchdog thread-dump sample from a **post-fix** run. |
| `connection-counts.txt` | Re-read counts from the PostgreSQL logs of the two measurement runs. |

## Counter definitions (from the final `d24_probe.py`)

- `store_reads`: entries into `ExperimentalStore.read` (counts calls, including cached-local hits,
  not unique database rows).
- `direct_connect_attempts`: calls through the bounded `connect()` helper. Only the unpooled replay
  routes `ExperimentalStore._connect` through it; on the fixed path it stays 0 because the store
  borrows from the pool. Other entry points (repository factory, backup/restore) are not exercised
  by this node.
- `new_physical_connections`: SQLAlchemy pool `connect` events for engines returned by
  `engine_for_url()` - pool-created physical connections only. It does **not** see out-of-pool
  direct connects; a value of 0 is not "no physical connections at all".
- `pool_checkouts` / `pool_checkins` / `pool_peak`: pool `checkout`/`checkin` events and the
  observed peak number of concurrently checked-out connections for those engines.
- `persists`: entries into `JobManager._persist`.
- `emits`: entries into `JobManager._emit`.
- `hooks`: **entries** into `JobManager._finish_terminal_hook`. The method starts with a guard
  (`_terminal_hook_called / terminal_hook_status`) and can return early, so this number is **not**
  the number of executed callbacks and **not** the number of settlements. `hooks: 2` for one job
  must not be read as duplicate settlement.
- The plugin counts from `pytest_configure` for the whole test; it does not separate warm-up and
  read windows. The closeout regression separates them: one warm-up read is excluded, then a fixed
  50-read window is measured with two independent monitors (a psycopg.connect counter covering
  out-of-pool paths and the target pool's checkout/checkin events).

## The `D24_FORCE_UNPOOLED` replay

It replaces exactly one thing inside the probe process: `ExperimentalStore._connect` becomes
`connection_module.connect(self.database_url)` - the old per-read direct-connection path. It is not
a production switch; the production store always uses `pooled_connection(engine_for_url(...))`.
The new closeout counter-example test does the same replay via a temporary monkeypatch of the class
method and always restores it.

## Windows and measurement boundaries

- The watcher (`pg_stat_activity` poller in the driver) was **disabled** for the metric runs
  (`D24_NO_WATCH=1`), so its connections are not in the probe counters; when enabled it opened its
  own connections and did appear in PostgreSQL logs.
- The driver itself creates the database, runs 20 migrations and probes identity before pytest
  starts, so "connection authorized" log lines include those setup connections (see
  `connection-counts.txt`).
- Failed and successful runs did **not** perform the same workload: the replay aborted at the 8 s
  wait deadline after 173 reads, the pooled run completed 427 reads. The closeout regression
  compares both paths on the identical 50-read workload instead.
- The pre-fix D-24 timeout thread dump is **not recoverable**: the same log path was reused by
  later runs and overwritten. No claim about the exact timeout stack beyond what the surviving
  post-fix sample and the metrics show is made here.
- All diagnostics are from this Windows host only; no Linux/macOS connection behaviour is inferred.
