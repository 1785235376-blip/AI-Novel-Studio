# Native OCR to original Research review

Private coordinator implementation; not public product availability.

Reuses Research analysis receipts, original JobManager persistence, native Vision OCR node, original broker preview/reserve/dispatch/finalize, and existing project-incarnation leases. Creates no queue, registry, workflow engine or secondary result owner.

Explicit preview pins source identity/version/digest, route, language, receipt version, five-minute expiry, output limit and zero external provider fee (not host compute cost). Dispatch requires the reviewed digest and idempotency key. Reservations precede receipt claims to avoid unsupported nested transactions; failed claims settle their unused reservations. Publication requires verified durable job output and terminal settlement, creates source-bound derived citations, and enters REVIEW_REQUIRED. Human review revalidates exact persisted result/citations, original job, broker reservation and route receipt. Original source files and manuscript chapters are not modified.

Cancellation hides native metadata and prevents publication. Completed receipts can be reopened and reviewed without restoring execution authority. Source revocation prevents review. Recomputed generic digests do not authorize forged citations.

## Evidence

- research-native-ocr-coordinator-file-r1: 19 passed, 19 PostgreSQL cases deselected.
- research-native-ocr-coordinator-pg-r1: 19 passed, 19 File cases deselected.
- research-native-ocr-coordinator-file-r2: 6 passed, 6 PostgreSQL cases deselected.
- research-native-ocr-coordinator-pg-r2: 6 passed, 6 File cases deselected.
- PostgreSQL was a real reused database, OID 31303; server stopped after each run. No fresh migration claim.
- Actual installed English Tesseract recognized STUDIO OCR 123 through original job and broker owners on both backends. No skipped native smoke cases.

## Remaining boundaries

No public API, production composition, host configuration or UI wiring in this slice. Native orphan recovery is not implemented; generic reconciliation remains blocked for those reservations. No Chinese model, PDF OCR, broad recognition-quality, Windows execution or whole-product acceptance claim. No automatic Canon adoption. Existing general VISION route fences and public/internal packaging separation are preserved.
