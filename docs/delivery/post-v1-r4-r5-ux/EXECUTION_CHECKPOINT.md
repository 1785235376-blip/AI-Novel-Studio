# Execution checkpoint

Branch `work/post-v1-r4-r5-ux`, Draft PR39, stacked on released R3 `d712ab81e9d87bfd5902d0a6bbd47c4edaccac5b`. Frozen PR37 and PR38 are unchanged.

Published all-forty checkpoint `344062df637685d78cf25e9edf9f2c6734bbd75e`, tree `cfbf2c8cf750b7b1959135269db058ccc6faf643`: File and both Windows lanes passed. R4 browser 27/33 passed; PostgreSQL 3,368 passed / 1 failed / 1,000 skipped with no marked-PG execution-gate failure. The remaining failures and retained corrections are documented in FINAL_UX_CI_CORRECTIONS.md.

The next pinned source adds complete bounded U01 workspace/last-project restoration and U10 isolated first-use samples, plus those corrections. Backend runtime `a6815ae7967944d1bebb50f2ed28541900f86b69` passed 3,409 File-compatible cases, with 9 explicit skips and 1,035 PostgreSQL-only deselections. Subsequent production change is the source-control accessible label only; backend code is unchanged. Final frontend passed 971 cases / 6 optional HTTP skips; TypeScript, build and 42-file token guard passed. Real two-process TCP sync passed separately. A focused 42-case fork suite checks the corrected shared-database fixture. Thirty-five R4 journeys are authored and collected, not locally browser-run.

Exact hosted verification of this next source is pending. The Draft PR body is the live remote SHA/run readback; historic receipts are not silently upgraded. Independent follow-up review remains BLOCKED and has not been retried or routed elsewhere. NEXT_UX_PRIORITIES.md separates remaining acceptance gates, current-package extensions and genuinely new suggestions.
