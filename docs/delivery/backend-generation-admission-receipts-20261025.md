# Keyed text generation: preserve uncertain admission

Date: 2026-10-25 UTC

## Scope and baseline

Base commit: `e9830fc4c24fe8b0b08f2fbba03d3f4dbf35a86e`, tree `452c7c3581952b4388a02b60a63c7f9b51f4ee2b`.

Production scope is `app/api.py`, a separate admission coordination method in `app/idempotency.py`, and the strict parser/builder `app/services/generation_admission_receipt.py`. Tests are the new `tests/test_generation_admission_receipts.py` and the prepare/start double adjustment in `tests/test_generation_idempotency_contracts.py`. No JobManager, GenerationRepository, source owner, queue, Asset/Audio history, frontend, migration or provider code is changed. Publication follows independent review and remote HEAD confirmation.

The final independent review passed 118 main cases plus 11 distinct adjacent cases (129 unique cases within that review), with frozen hashes unchanged and no P1/P2 findings. Its additional fault cases include a real thread starting before an injected exception, failed terminal persistence, process exit after start, and ordinary store writes progressing while admission pauses. The implementation's 123-case run overlaps this review and must not be added as unique coverage. Portable hashes, result counts and original log copies are in [evidence/generation-admission-20261025](evidence/generation-admission-20261025/); checkout paths in copies are normalized. These results do not broaden the execution, durability or platform limits below.

## Observed failure before this slice

The former route called `jobs.create()` before recording its complete receipt. The original `JobManager.create()` persisted QUEUED and called `Thread.start()` before returning. A subsequent receipt write failure left no cache entry, so the next same-key request could create and dispatch another original Job, even in one process.

A small isolated real-File probe in `.runtime/admission-review-20261025/probe.py` demonstrated two distinct original UUIDs and two synthetic worker starts after one injected final-receipt failure. Separately, the first new regression test was red: at the original QUEUED save, its assertion that RESERVED already existed failed. These are synthetic admission counterexamples, not model/provider executions or production incident claims.

## Protocol and ownership

The original operation/authority namespace, complete cache key and request digest remain unchanged. Project incarnation stays in the receipt value, not in the key. This prevents old requests from becoming cache misses when a project is recreated.

For a missing key, the route:

1. Checks current source, authority and original project owner.
2. Calls the original `prepare_job()` once. The resulting original Job UUID is real, but the object is only PREPARED in memory: no original repository row or worker exists yet.
3. Revalidates current source/authority/owner, then writes a strict RESERVED receipt through the original IdempotencyStore.
4. Revalidates again before invoking only the original `start_prepared(exact_job)`. Its returned object must be that exact instance, and its UUID must still equal the reserved original ID; otherwise the reservation remains unconfirmed.
5. Writes the original complete v2 response receipt, then performs the existing final revalidation before returning success.

The reservation schema has exactly `schema_version: 3`, `admission_state: RESERVED`, `project_incarnation`, `request_digest`, and `job_id`. The ID must be a canonical UUID4 and the request digest lowercase SHA-256 hex. No prompt, source, session token, request closure or copied Job execution status is stored in it. `RESERVED` is admission evidence, not a Job lifecycle state.

Full receipts retain the exact original v2 shape and validation contract. Their status is the original response snapshot, not a claim that generation completed. No existing v2 receipt is adopted into a new Job.

A valid RESERVED replay returns HTTP 409 with `ADMISSION_UNCONFIRMED`. The error does not expose the reserved ID or return a fabricated 202, even when the original Job does not exist. It never reconstructs a Job, calls start, or replaces an unconfirmed record. Legacy, malformed/unbound, mismatched, expired and changed-owner records remain fail-closed. Current source and authorization errors retain their existing precedence.

The cache remains a request-admission receipt, not a second Job owner: execution, persistence, Job state, recovery and observation remain with the original JobManager/GenerationRepository. Existing original Job reads may help a user reconcile, but a missing in-process Job or a 404 is never treated as permission to redispatch.

## Coordination and lock order

The existing process-global API lock is retained. A separate `generation-admission:<canonical cache path>` file coordinator serializes keyed admission for that cache across cooperating processes. It is one coordination key per canonical cache file, not one per user key or Job UUID. Different-key admission remains serialized, matching the previous broad process-global behavior; no throughput improvement is claimed.

This admission lock is distinct from the whole-JSON `idempotency-store:<canonical cache path>` lock. The latter still guards only short retained/read/write operations. The admission lock is never entered from inside `_access()` or an auth/source/Job lease. Auth/source/owner checks and original Job save/Thread.start run only after the JSON lock has been released. Project-owner leases remain short and do not span auth/source/jobs calls. The admission lock does not wait for model execution or Job completion.

## Failure and retention matrix

| Interruption | Retained evidence | Next same-key behavior |
| --- | --- | --- |
| Validation or inert preparation fails | No new reservation or Job | May retry after the underlying issue is corrected |
| First reservation write fails before replacement | No dispatch; record may still be absent | A later confirmed miss may prepare anew |
| First reservation write commits then raises | RESERVED, no start attempted | 409; never erase evidence or start automatically |
| Exit after RESERVED, before start | RESERVED; original Job may not exist | 409, not fabricated success |
| Original Job save fails before commit | RESERVED | 409, no automatic replay |
| Original Job save commits then raises | RESERVED and possibly QUEUED on disk; local dict may lack Job | 409; in-memory 404 does not imply no execution |
| Exit after QUEUED, before Thread.start | RESERVED and original QUEUED row | 409; never fill the gap by starting on replay |
| Thread.start fails or outcome is uncertain | RESERVED; original FAILED save may also be uncertain | 409; do not infer provider outcome from Job status |
| Complete receipt write fails before replacement | RESERVED and original Job | 409; never dispatch again |
| Complete receipt write commits then raises | Full original v2 receipt may exist | Subsequent reads may replay that exact receipt |
| Final source/authority/owner check rejects | Preserve full original v2 receipt | Reject under existing checks, no redispatch |
| Any receipt phase is expired or malformed | Preserve existing bytes | 409, never TTL-delete then treat as miss |

Unexpected inert preparation failures return `GENERATION_PREPARATION_FAILED` (500). Uncertain original start/result capture returns `GENERATION_ADMISSION_UNCONFIRMED` (503). Reservation/final receipt write exceptions return `IDEMPOTENCY_ADMISSION_PERSISTENCE_UNCONFIRMED` (503). Coordination failures use a fixed code. No error includes a raw key, filesystem path, DSN or exception message. HTTP authorization/source failures are not converted into successful admissions.

Reservation age is measured from its initial `put`. Finalization retains the old `put` behavior: the complete v2 record gets a fresh `created_at`, and its TTL runs from that full-record time. Expired records in either phase remain retained and return 409.

## Verification

Final frozen selection: **123 passed**, 0 failed/skipped, 3 pre-existing warnings, 67.11 seconds. The production and changed test hashes were verified unchanged before and after this run.

- `tests/test_generation_admission_receipts.py`: 39 new real-File cases.
- `tests/test_generation_idempotency_contracts.py`: 55 existing compatibility cases with the updated prepare/start dispatcher double.
- `tests/test_generation_variants_phase3.py`: 10 unchanged cases.
- `tests/test_generation_restart_recovery.py`: one unchanged case.
- `tests/test_idempotency_store_multiprocess.py`: 18 unchanged store-isolation cases.

Command: `python -m pytest -q tests/test_generation_admission_receipts.py tests/test_generation_idempotency_contracts.py tests/test_generation_variants_phase3.py tests/test_generation_restart_recovery.py tests/test_idempotency_store_multiprocess.py --junitxml=<run>/results.xml`.

The checkout's existing `.runtime/activate-backend.sh` and virtual environment were used. HOME, XDG paths, APPDATA, LOCALAPPDATA, NOVEL_DATA_PATH and temporary directories were redirected to run-specific locations. Storage was File, cloud/fallback disabled, configuration LOCAL_ONLY/Mock, and the credential vault process-local memory; database/provider credential variables were unset. No dependency was installed, no model generation/provider/network operation was performed, and no real PostgreSQL was used.

The new regression test was first observed red before production edits: the original QUEUED save found no RESERVED receipt. The red was recorded in the test worker's tool output, not a separate persisted logfile. An earlier isolated real-owner counterexample is also described above. Subsequent new-suite runs were green (39 cases); the final combined 123-case run rechecked the exact frozen production after adding the explicit exact-instance/UUID return guard. Earlier overlapping green counts are not additive unique-test totals.

New tests preserve original preparation, original Job persistence and original start admission, replacing only worker execution with a synthetic function. Observation/failure wrappers call the original methods where a commit-then-raise or late-source/authority change is required. They cover both reservation and full-receipt write failures before/after commit, original Job save failures before/after commit, Thread.start failure, no-Job reservations, exact-instance/UUID violations, strict schema/expiry checks, current source/project/authority changes at each admission boundary, and collaboration replay without fabricating an original Job.

Linux subprocess tests use independent spawned interpreters. Actual `os._exit(71)` after reservation and `os._exit(72)` after original QUEUED save are followed by cold same-key denial without a new start. Same-key contention starts only one original Job; a different process's ordinary `put()` completes while the first admission remains paused. A bounded-metadata test creates 100 keys/store objects for one canonical cache and observes exactly two coordinator identities: one admission lock and one short JSON lock. All subprocesses use bounded joins and cleanup. The concurrency test initializes its managers before the first Job save and therefore does not conceal or claim to fix the separate active-job startup recovery defect.

Final artifacts: `.runtime/generation-admission-20261025/final/pytest.log`, `results.xml`, `pytest.exit`, `SHA256SUMS.before`, `hashes.after.log`, and `summary.json`. The dedicated new-suite artifacts are under `.runtime/generation-admission-20261025/admission-final/`; earlier compatibility runs are under `compatibility/` and `store-compatibility/`. `git diff --check` passed.

Frozen SHA-256 values:

- `app/api.py`: `fb24d6de2a6ec0475257b48b2f5e4939b1a64f8c87938ba1c0b12af20a622670`
- `app/idempotency.py`: `4212aeb54b37d230efbd3bac26a0687274700a51c017fae3b736a41b3e923c3d`
- `app/services/generation_admission_receipt.py`: `9109bd2f4de5dee99f0ea5fb308e8150773b72e81484b199f9fce5673f39b227`
- `tests/test_generation_admission_receipts.py`: `aa8b083a210d134fe71e68821c999a3892ff5a0db6214b2dea3357a0b00da4c1`
- `tests/test_generation_idempotency_contracts.py`: `99274bba9e27ddeccba7b0aae505d0f9c7a258e1a9f9bb66a8bb111e1855c87d`

## Explicit limits

This proves only admission non-redispatch under retained receipts, cooperating processes sharing the same cache file, and tested process failures. It is not provider exactly-once execution, an automatically recovering queue, or generic multiworker JobManager support.

Unchanged boundaries include:

- JobManager startup can mark another process's active shared Job FAILED, and `get()` only sees that manager's in-process dictionary. Subprocess admission evidence must not be described as fixing those defects.
- Ordinary local/mainline generation does not universally invoke the request authorization callback at the last provider hop. This slice adds API admission rechecks, not a new worker execution fence.
- Provider retries/fallback, no-key requests, explicit new keys and other generation entrypoints are outside same-key admission protection.
- Missing/deleted/corrupted receipts, old backup restoration, non-cooperating writers, separate caches and multi-host/network filesystem coordination are not repaired. In particular, ordinary store `put()` still uses the prior fail-open `_load()` on malformed JSON; a later ordinary write can rebuild a corrupt file. The strict keyed read path itself continues to reject malformed data.
- Atomic replacement still fsyncs the temporary file but not its parent directory. No OS-crash/power-loss durability improvement is claimed.
- PostgreSQL request-key storage, real PostgreSQL concurrency, Windows coordination, and provider-side outcomes are not validated by Linux File tests.
- An uncertain original action must be reconciled before deliberately requesting a new key. A 503 or a Job lookup miss is not proof that the provider did nothing.
