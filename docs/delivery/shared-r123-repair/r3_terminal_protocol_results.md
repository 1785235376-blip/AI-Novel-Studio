# R3 terminal protocol repair verification

## Scope

Ordinary shared generation implementation (`app/jobs.py`), used by `/api` and `/api/v1`. No feature additions, model/GPU quality claims, paid APIs, deployment or frozen PR changes. This supplemental local run uses Python 3.12.14 and real isolated File repositories. It does not replace pinned Python 3.12.9 or real PostgreSQL CI. Historical independent-review status remains BLOCKED.

## Verified behavior

The new regression `test_running_reject_at_each_stream_boundary_cannot_truncate_or_revive_draft` covers both API prefixes and OFF/ON/V1 modes. At the first chunk, last chunk, and completion-event boundaries, reject returns HTTP 409. Memory and persistence remain GENERATING, and cancellation remains unset. After releasing the synthetic model stream, memory and persistence both reach COMPLETED with exactly `SYNTHETIC_FIRST_CHUNK_LATE_CHUNK`. The mounted HTTP/SSE response terminates with COMPLETED and concatenates to that same full output. A subsequent review reject returns HTTP 200/REJECTED; reopening the manager preserves REJECTED.

The status matrix accepts only COMPLETED review rejection. PREPARED, QUEUED, GENERATING, SETTLING, CANCELLED, FAILED, ACCEPTING, ACCEPTED, ACCEPTANCE_UNCERTAIN and REJECTED return HTTP 409 without changing stored data. State conflicts remain ValueError-compatible for existing Python callers.

Settlement is persisted as SETTLING before the callback. Reject during a paused settlement returns 409 promptly; it does not wait and reinterpret the operation as completed review. Existing acceptance-during-settlement waiting behavior is preserved and passed its original test. Cancellation remains responsive while settlement is paused and does not change the already completed execution outcome.

Late worker success/failure preserves previously decided terminal states. A second same-host manager's rejection cannot be overwritten by the first worker's final completion publication. Recovery rereads the record under the shared claim lock, so a stale startup snapshot cannot overwrite a newer completed/reviewed/cancelled terminal state. Recovered interrupted states are saved durably as FAILED; recovered unconfirmed settlement retains output, completed execution outcome and reconciliation-required state without replay. Already confirmed accounting is not reclassified as missing after restart.

For synthetic priced reservations with missing upstream usage, completed/cancelled/failed paths call terminal accounting exactly once, preserve UNKNOWN_UPSTREAM and the 40-microusd hold, and never treat unknown use as free. Repeated finalizers, rejection and manager reopening do not mutate the final ledger. Settlement failure preserves CANCELLED and exposes reconciliation required.

Completion publication and accounting-receipt write failures also have fault-injection coverage. A failed initial completion publication produces FAILED with GENERATION_TERMINAL_PERSISTENCE_UNCERTAIN, preserves the separate COMPLETED execution outcome for once-only accounting, and blocks acceptance/rejection. With a transient write failure, FAILED is saved; during a persistent storage outage, memory/SSE report FAILED while disk necessarily retains its earlier GENERATING record until restart recovery. This mismatch is explicitly treated as persistence uncertainty, not claimed as durable completion. Failed accounting confirmation remains reconciliation-required and is not replayed.

The existing egress unit contract deliberately overrides the emission seam without a persistence service. The extra direct pre-settlement write applies only to jobs with accounting; ordinary completion retains the existing `_emit` persistence seam and original assertions unchanged.

## Tests

- New terminal-protocol tests: 146 File PASS; 146 real-PostgreSQL parameters not run in the File lane, with existing backend markers.
- Related original acceptance, dispatch-hook, feature-origin, generation-bound, privacy and egress tests: 131 PASS; 42 PostgreSQL parameters not run in this lane.
- Combined supplemental run: 277 PASS, 188 SKIP, 0 FAIL/ERROR. JUnit and complete console receipt are adjacent to this document.
- `git diff --check`: passed.

The mounted TestClient exercises the production HTTP routes and final HTTP/SSE body. The R3 tests do not claim streaming network/browser timing coverage; the separate R2 suite owns live network SSE revocation coverage. Cross-host/distributed execution ownership is not claimed by the existing same-host mutation lock.
