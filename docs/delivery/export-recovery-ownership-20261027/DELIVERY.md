# Export startup recovery ownership — PARTIAL

## Reproduced defect

On the published `048fe2a12212df85c272cdc0741659498378d334` baseline, process A uses original `create` and the real executor pool to enter a synthetic exporter and waits at a gate. Process B constructs the original service over the same File queue. It incorrectly treats A's running job as interrupted, increments recovery_count and invokes the same exporter. B completes with content `b`; resuming A then overwrites the result with `a`.

The original two-case baseline is **1 failed, 1 passed**. The failure is the expected no-live-replay assertion, not an environment failure. The passing contrast SIGKILLs A before B startup and verifies legitimate recovery. Earlier collection failed because the default identity path was read-only; that separate log is retained and not counted as a product test.

## Bounded implementation

Only the original owner and a new private execution-claim helper change production. A nonblocking per-job claim is acquired before recovery mutation/submission, retained while queued, through exporter/artifact/final state processing, and released idempotently on worker completion, submission failure or queued cancellation. Contention is distinct from an unavailable/unsafe lock facility; there is no unlocked fallback. Original short File writer coordination remains; unrelated jobs and cancellation do not wait for the exporter.

No persisted claim token, job schema migration, public API or new permission is added. Original cancellation, idempotency, snapshots and binding nonce behavior remain consumers of the same service. The claim does not authorize access to a job.

## Verification and evidence

Acceptance is frozen on `ead7d004386f1a23be3fb22b4a2ea104fc28aa44` with app tree `44f0a0fe8780611d1440687f799f5d13cb40714c`. The earlier production freeze `8f6d015493434b8d47389676de0c337cb8951814` has the same app tree.

The earlier consumer run has one fixture failure: a test stubbed all of `_submit` with a two-argument no-op and could not accept the new recovery argument. The test now substitutes only a DeferredPool returning real Futures, retains actual `_submit`/claim handling, releases a queued claim through real Future cancellation, and checks the original recovery_count and nonce transitions. It is a synthetic scheduling boundary, not a process crash test; real child-process tests separately cover SIGKILL recovery. Both the old failure and the corrected fixture evidence are retained.

See `RESULTS.json` for final group counts, exits and source checks. Groups overlap and must not be added. Independent owner cases are included in the final focused group.

Process coverage includes live-owner exclusion, dead-owner recovery, two recovery processes competing for one job, and unrelated-job/cancellation progress while another exporter waits. Independent tests cover queued claims, cancellation/release, duplicate submit, failed submission/exporter/artifact/final commit, canonical aliases, unsafe symbolic/hard links and path replacement at acquisition, plus get/list without execution-lock initialization.

Business-file snapshots and source inspection do not constitute a general OS-level zero-write instrumentation claim.

## Remaining boundaries

Same-host cooperating File processes only. Windows, PG, network filesystems, browser, real models/GPU and hosted CI are NOT_RUN. No live-fork or externally replaced held-lock coordination guarantee. Lock files are not unlinked; no exactly-once exporter external-effect guarantee after crash. A queued job may be claimed by another owner before its creator submits it. Recovery is still startup-driven, not a new watchdog. See WORK_HANDOFF for precise integration restrictions.

The original asset pagination 409/F37/Windows 503 remain separate unresolved observations. This package is not release-ready or permission to merge main. Publication requires separate user approval.
