# Host-only OCR execution through the original JobManager

2026-10-18. **Original job execution is exercised, including actual native OCR.
Public Research dispatch, real broker admission and review publication remain closed.**

The original JobManager can now prepare and start a private live OCR invocation.
It reuses its existing worker start, generation persistence, completion hooks and
restart owner. No new scheduler, registry, chapter or Graph identity is introduced.
A transient capability binds the exact manager/job, original Research source
preparation, VisionOCRModelNode/provider object, immutable typed job identity,
caller guard, cancellation object, output/deadline bounds and original hook pair.
No HTTP entry point can reconstruct that capability from a passive record.

Source, actor/scope/incarnation, route, feature flags, cancellation and deadline
are rechecked at preparation, before dispatch, through the model guard and before
publishing a private live result. The ordinary Author entry and manuscript/content
surfaces remain unavailable even for a running OCR job. A completed private result
requires matching durable status/text/binding and successful terminal-hook state.
It remains transient and deadline-bound; restart never rebuilds it or replays work.

The original before-dispatch and terminal hooks run once. Their real broker owner
has not been connected here: tests use explicit hook stand-ins, which must not be
reported as budget-ledger integration. A future coordinator also owns reconciliation
when preparation/start fails before a worker starts. Actual review publication must
still occur through the original Research receipt owner, not by accepting job text.

## Verification and retained findings

- File r1: 33 passed, 31 PG deselected.
- During the new worker audit, stripping passive markers selected the generic
  worker path. The original persistence fence still refused the downgraded record;
  no Author routing or output publication was observed. The initial narrowly written
  test passed but reported an unhandled thread exception. Its raw receipt (named
  marker-red) is retained as PASS, not misreported as a reproduced security bypass.
- A stronger typed-worker assertion then genuinely failed (marker-red-r2). The
  production classifier now also recognizes the transient capability independently
  of passive markers, and persistence checks its immutable identity. The same
  strengthened test passes with unhandled thread warnings treated as errors.
- File r2: 94 passed, 89 PG deselected, including unchanged Director persistence and
  original Author regressions. Final File r3: 67 passed, 33 PG deselected, including
  the additional project-recreation execution case and original harness checks.
- PG r1: 89 passed, 92 File cases deselected. Final PG r2: all 10 current execution
  cases passed, 10 File cases deselected. Both use actual PostgreSQL, reused database
  OID 31303, no fresh migration claim; the server stopped after each run.
- Actual installed Tesseract recognized `STUDIO OCR 123` through the original
  JobManager and original VisionOCRModelNode with both File and PostgreSQL stores.
  Hook accounting in those tests is still a stand-in, not actual broker settlement.
- The PG harness had a generic static 'no model calls' label inherited from earlier
  tests. That label is inaccurate for the native OCR smoke in PG r1. The harness now
  describes only its verified database boundary and points to the exact check/report
  for other activity. PG r2 has the corrected label; no timeout, isolation or policy
  enforcement was relaxed. Earlier receipts remain unchanged.
- 3 PUBLIC checks passed, including real offline wheel and metadata verification.
  PUBLIC adds only the STANDARD execution module. No dependency/UI/private-backend
  change; prior frontend type/build evidence is unchanged, not redundantly rerun.

Cases cover one execution, cancellation, source revocation, queue-time revocation,
settlement failure, altered identity, different managers, passive-marker stripping,
source-project recreation, persisted-output tampering and restart with no authority.
No Chinese/PDF/general OCR quality, final browser/Windows, full-suite or release
acceptance is claimed. The 0.7.0 wheel is a test artifact. No paid API or GPU was used.

## Next

Connect the original broker's preview/reservation/dispatch/finalize owners, then
publish source-bound results into the original Research review receipts. Keep
ReviewAdapterJobs' real-provider refusal and broker unavailable reason until that
complete path exists. Do not change either merely because this private runner works.
