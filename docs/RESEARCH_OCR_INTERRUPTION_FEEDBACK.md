# Read-only native OCR interruption feedback

When a Research receipt remains persisted as RUNNING but the current original JobManager no longer holds usable live OCR execution authority, the original Research read path now returns an INTERRUPTED projection. The response retains persisted_status, reports that replay/resume is not automatic, and states whether the original reservation still holds an execution slot. It does not declare that an external process has definitely stopped.

Before returning this projection, the coordinator rechecks source visibility, actor, project incarnation, original reservation/job id and authorization digest. The original Research document, generation ownership and broker ledger are not rewritten by this read. No budget hold is released, result adopted or task replayed. The UI shows an explicit retained-slot warning rather than implying that reopening continues execution.

This is error feedback, not completed orphan reconciliation. Explicit host recovery remains required and is not implemented in this slice.

Evidence:
- native-ocr-interruption-file-r1: 8 passed, 8 opposite-backend cases deselected.
- native-ocr-interruption-pg-r1: 8 passed, 8 opposite-backend cases deselected; reused actual UTF8 PostgreSQL OID 16384, server stopped.
- The restart-specific case deliberately persists a queued original job without starting inference, then creates a new original manager and reads the original Research row. It checks unchanged Research/ledger bytes and retained RESERVED status. This is simulated restart-state injection against real persistence, not an actual killed-process or power-loss test.
- native-ocr-interruption-build-r1: 6 Python catalog/PUBLIC checks (actual offline wheel), 7 React tests, TypeScript and actual Vite production build passed. The new UI test reads a saved interrupted receipt and sends no mutation or dispatch.
- API catalog remains 2365 mounted method/path entries; application source hash binding refreshed without new endpoints.

Existing browser limitations and whole-product acceptance gaps remain. No new full OCR or V2 completion claim.
