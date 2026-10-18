# Original OCR worker result handoff

2026-10-18. Private completion hook only. Research review publication and real
broker admission are still not connected or enabled by this slice.

The original JobManager OCR capability accepts an optional trusted on_result
callback. It receives a detached verified response only after the original job
record and terminal hook have been confirmed. The worker rechecks source authority
and durable result identity after the callback. Failure retires the live result,
clears output and records an unconfirmed terminal state without replaying inference
or settling twice. The actual Research owner must still perform its own guarded
transaction and validate its own durable review receipt.

While this completion callback is running, another thread cannot obtain the
private live result. The original worker alone may read it for the callback; a
transient finished marker is published at the final condition notification. No
capability, callback or finished state is reconstructed after restart. Existing
public generation content and manuscript adoption remain unavailable for OCR.

Verification:
- Initial File r1: 14 passed, 14 PG cases deselected.
- Final File r2: 15 passed, 15 PG cases deselected, zero skips.
- Real PostgreSQL: 15 passed, 15 File cases deselected, zero skips; reused original
  database OID 31303, no migration claim, server stopped.
- Cases cover once-only settled/durable handoff, detached receipt metadata, callback
  failure, no callback after cancellation, source revocation during handoff and a
  controlled pending-publication race. Original OCR execution tests, including real
  installed English Tesseract through File/PG jobs, remain in the focused runs.
- 3 original PUBLIC checks passed with an actual offline wheel. No dependency or UI
  changed; prior frontend checks remain applicable, not rerun. Test wait helpers now
  observe the final worker marker instead of a result that may still be publishing.

The callbacks in these tests are explicit stand-ins. They are not evidence of a
Research review transaction, original broker ledger integration, Chinese OCR,
Windows/browser acceptance or V2 release readiness. The wheel is a 0.7.0 test artifact.
