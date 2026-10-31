# Idempotency JSON store: Linux cross-process mutation isolation

Date: 2026-10-25 UTC

## Scope

Base: `fe90fce950504fded8fb8f3cc8255d0debebf0b9`, tree `c9b3ce5bffb9709548cf448fbdc71cba5c1c0b8d`.

Owned files: `app/idempotency.py`, `tests/test_idempotency_store_multiprocess.py`, and this report. No API, JobManager, queue, Asset, Audio history, frontend, permission, dependency or schema changes. This work is not committed or published by the implementation worker.

## Before: deterministic lost update

Before changing production code, two independent Linux processes created separate IdempotencyStore instances for the same empty JSON file in a temporary directory. Each wrapped `_load()` to wait at a two-party Barrier after obtaining its snapshot. Both then called the original `put()` with different keys.

Actual result: both calls returned successfully, but the resulting JSON contained only key `b`: expected two entries, actual one. The Barrier makes the stale-read interleaving deterministic; the surviving key is scheduling-dependent. This is a store-level counterexample, not a generation/provider execution or evidence of a production deployment incident.

Original log: `.runtime/idempotency-store-multiprocess-20261025/before-lost-update.log`. The unchanged baseline source is retained in the same directory as `baseline-idempotency.py`.

## Minimal implementation

- Resolve the cache path once at construction. Equivalent directory-symlink paths and later working-directory changes use the same stable target.
- Lazily import the existing `workspace_mutation` coordinator, avoiding a new top-level repository import dependency.
- Use one coordination key per canonical cache file, not per request key. Different cache files retain separate locks.
- Hold the existing instance lock and existing File cross-process coordinator over the complete `get`, `retained`, or `put` operation. TTL eviction and JSON replacement therefore share the same mutation boundary as other writes.
- Preserve `atomic_write`, the receipt format, timestamps, ordinary `get()` TTL eviction, strict non-evicting `retained()`, and empty-key `put()` no-op behavior. Same-key `put()` remains serialized last-write-wins; it does not become a claim operation.

Read operations may create the existing coordinator's `.workspace-mutation-locks` directory and lock file. These are coordination metadata, not a new business receipt. A missing cache remains missing after `get()` or `retained()`. Existing receipt bytes remain unchanged by `retained()`, including expired and malformed receipts. No metadata cleanup or permission changes are performed. As with the reused coordinator, callers must be able to create/open its metadata, and cooperating processes must not delete active lock files.

The lock surrounds storage only. No generation, authorization or provider callback is invoked under it.

## Verification

All pytest runs used the checkout's existing `.runtime/activate-backend.sh` and virtual environment. HOME, XDG paths, APPDATA, LOCALAPPDATA, NOVEL_DATA_PATH and temporary directories were redirected to run-specific locations. Storage was File, cloud disabled, configuration LOCAL_ONLY/Mock, the credential vault was process-local memory, and database/provider credential variables were unset. No model/provider was invoked, no network service or real PostgreSQL was used, and no dependency was installed.

Initial new-test run: **18 passed**, 0 failed/skipped, 19.00s. After strengthening the exception-release test to keep the failing process alive, the final combined run was **84 passed**, 0 failed/skipped, 28.42s:

- `tests/test_idempotency_store_multiprocess.py`: 18 Linux File cases, including 15 cases using independent spawned interpreters and three local path/metadata cases.
- `tests/test_generation_idempotency_contracts.py`: 55 cases, including retained legacy/corrupt/expired receipt fail-closed behavior, owner/source checks and unchanged ordinary TTL behavior.
- `tests/test_generation_variants_phase3.py`: 10 cases, with model dispatch replaced by the existing controlled staging fixture.
- `tests/test_generation_restart_recovery.py`: one synthetic interrupted-record case.

New coverage includes different-key writes, deterministic same-key ordering, canonical directory aliases, TTL eviction racing another key's put, readers waiting for a complete put, unchanged retained receipt bytes, release after load/write exceptions while the failing process remains alive, OS lock release after terminating its owning process, and independent progress for different cache files.

Fixed-code tests deliberately do not reuse the old two-party `_load()` Barrier: that would deadlock correctly serialized readers. Instead, the first worker pauses after reading while the second reports readiness; the parent verifies bounded blocking, releases the first worker, and checks both results. Every worker has bounded joins and cleanup. The termination test kills only its own disposable test worker and does not delete lock metadata.

A separate cold-import probe confirmed that importing IdempotencyStore alone does not import `app.repositories`; its first `retained()` access can lazily load the coordinator, and a subsequent put/get round trip succeeds. `git diff --check` passed.

Final evidence directory: `.runtime/idempotency-store-multiprocess-20261025/`:

- `before-lost-update.log`, `baseline-idempotency.py`
- `after/pytest.log`, `after/results.xml`, `after/pytest.exit`
- `final/pytest.log`, `final/results.xml`, `final/pytest.exit`
- `cold-import.log`, `final-summary.json`

Final production SHA256: `f3923db03921f379e2488866240b24285c3a90c843a8614e2bcb97648bddd8e1`.
Final test SHA256: `2d9791cf2f5a63b268df57e24e432f94bcc7084519b1800664c028095c2ebfcc`.

## Explicitly unchanged boundaries

Parent-owned independent review also reran the four-file selection: 84 passed in 32.32 seconds, with three existing warnings. Six additional probes verified cold lazy import, the baseline lost-update counterexample, file symlink aliases, SIGKILL lock release, all 120 writes from six spawned processes/twelve instances, and unchanged malformed UTF-8 bytes on strict retained reads. No blocking P1/P2 remained; overlapping counts are not a unique-test sum. Frozen production and test hashes matched before and after review.

Portable copies of the summaries and original logs are in [evidence/idempotency-store-lock-20261025](evidence/idempotency-store-lock-20261025/). Checkout paths are normalized in copies. This does not change the platform and execution limits below.

- This verifies Linux cooperating processes accessing the same local File store. It does not verify Windows, network/shared filesystems, cross-host locking, PostgreSQL request-key storage or multi-worker JobManager correctness.
- Separate `retained()`/`put()` calls are not one atomic request claim. The API's process-local admission lock and dispatch-to-receipt crash window are unchanged. No same-key single-dispatch or external exactly-once guarantee is claimed.
- JobManager's startup treatment of another worker's active jobs remains a follow-up boundary. No recovery automation or second queue/Job owner was added.
- An external provider may have accepted work before its result is known. UNKNOWN must not be automatically replayed; this storage-only change neither reconstructs provider results nor initiates recovery.
- Existing atomic replacement is preserved; this does not add power-loss durability or protection against non-cooperating file writers and mutable hostile filesystem aliases.
