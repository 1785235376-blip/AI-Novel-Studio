# Adapter receipt and read-through completion

Scope: original Research analysis, visual identity comparison and hybrid retrieval owners. No new top-level module, task storage, worker, model admission, plugin execution, or automatic Canon/manuscript/production write.

## Engineering behavior

- Mounted POST `embeddings/hybrid-query` uses `domain.read`, as does `query`. Before/after feature and current branch authority checks remain intact; mutations still require `domain.write`. An approved/shared branch asset can be queried by a genuine read-only branch principal; private and cross-branch indexes cannot.
- `ReviewAdapterJobs` keeps a hard **100 history entries**, **8 MiB serialized receipt**, **768 KiB current snapshot**, and **512 KiB result** limit. Preflight occurs before claiming/dispatching; it changes a detached candidate before committing. No eviction or history truncation.
- Run needs **six free revision slots**: claim, terminal, review, cancel, recover, and source invalidation. Admission at history length 94 is the last permitted run. State-specific reserved slots and worst-case snapshot bytes preserve the full control tail. A failed/oversized/non-JSON provider result becomes a sanitized failure within that reservation.
- Reopening a running receipt reports recovery required and never automatically replays it. Cancellation/recovery invalidate its execution token, so late results cannot overwrite a later revision. Once finite admission capacity is exhausted, an explicit new receipt is required; recovery never grants unbounded additional retries. Cancel availability is computed by the same detached revision/byte preflight, so exhausted controls are not advertised. Pre-existing out-of-budget/corrupt receipts fail closed; no historical data is silently discarded to repair them.
- Repeated cancel/invalidate of the same terminal state is an idempotent no-op. Research replacement/revocation invalidates through the same bounded helper; repeated invalidation does not consume more history or block source replacement at the hard bound.
- Cancellation/invalidation responses omit captured request, source snapshot, model and result digest. Version-conflict responses contain only ID/version/status, so a stale cancellation cannot replay revoked source lineage. Reads still require current source visibility.

## Existing-center integration

Research analysis and visual identity task/review entries are read-through projections of their original receipts. Research retains its stronger `domain.write` read requirement; visual checks require `domain.read`, creator ownership and approved current source visibility. Source permissions and flags are checked before and after reads. A denied private domain does not disclose its rows through an otherwise readable unified list.

Task cancellation dispatches to the same original domain owner with current write authority and original CAS. The inbox has no generic approval or batch approval. Original inspector navigation remains a **formal surface contract**: there is **no rendered exact-open control** for these receipts. Existing task, resume and review panels state that limitation rather than opening an unrelated record or tool. These formal-only receipts are omitted from the navigable Workspace search index until their exact-open inspector exists; they remain filterable in the Task/Review centers.

## Verification boundaries

- New regression files: `tests/test_surface_hybrid_read_authority.py`, `tests/test_surface_adapter_capacity.py`, `tests/test_surface_adapter_projection.py`; existing tests/assertions/skips remain unchanged.
- File and real PostgreSQL use the existing mounted fixture and both `/api` and `/api/v1`. Local PostgreSQL is unavailable: its cases remain NOT_RUN here, never replaced with synthetic persistence.
- Provider execution is synthetic MOCK_ONLY. Real OCR, visual model quality, real model admission, GPU and durable-worker behavior remain NOT_RUN / NOT_CONFIGURED.
- Local Chromium was previously denied and was not retried. Browser/geometry verification belongs to the authorized hosted lane.
- Frozen PoemSeed protocol, migrations 001–020, SDK DENY_ALL, final catalogs and surface maps are not changed by this work.

## Local verification (2026-10-07)

- Final combined backend: **327 passed, 274 existing backend skips**. Included the three new adapter test files plus existing visual/Research surfaces, embedding invalidation, R3 embedding/inbox, R4 Research library/mounted/extraction, post-interop Research/embedding isolation and workspace UX suites.
- Additional terminal-pending isolation test: **1 passed**. Adapter `REVIEWED`/`INVALIDATED` (including aggregate review entries) are terminal; unrelated existing media owner semantics remain actionable.
- Focused frontend and existing workspace/DS geometry contracts: **48 passed** (`AdapterReceiptProjection.test.tsx`, `WorkspaceToolsPanel.test.tsx`, `workspaceResumeLayout.test.ts`, `uiContracts.test.ts`). These are unit/contract checks, not browser screenshots.
- TypeScript `tsc -b`: **PASS**. UI token guard: **PASS**. `git diff --check`: **PASS**.
- Hybrid read-gate red/green: two original-prefix reader requests failed with the old write gate; eight new mounted File cases pass with the corrected read gate, preserving eight real-PG variants.

Raw logs are outside the repository under `/workspace/shared`: `adapter-final-verified-20261007.log`, `adapter-pending-boundary-20261007.log`, `adapter-projection-{file,ui,types,tokens}.log`, and `hybrid-read-{red,green,regression}-20261007.log`. No commit/push was performed by this implementation task. Exact publication SHA and hosted PostgreSQL/browser outcomes belong to the integration report.
