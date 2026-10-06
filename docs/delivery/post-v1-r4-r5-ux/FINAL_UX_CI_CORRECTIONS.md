# Final UX and hosted correction checkpoint

Runtime extension: original U01 workspace restoration and U10 isolated sample integration at `a6815ae7967944d1bebb50f2ed28541900f86b69`. See U01_WORKSPACE_RESUME.md and U10_ISOLATED_FIRST_USE.md for exact supported loops and recovery boundaries.

Full File-compatible suite at that runtime: **3,409 passed / 9 skipped / 1,035 real-PG-only deselected**, 289.03 seconds. Real two-independent-process TCP sync separately passed in 15.49 seconds. Full UI after the final source-control accessible-name repair: **971 passed / 6 optional HTTP skipped**; TypeScript, build and token guard passed. The initial UI rerun exposed one stale source-text layout assertion, now updated to retain the same feature-OFF/display-contents contract and the new explicit split visibility. No production geometry assertion was removed.

## Observed previous hosted failures, source 344062df

Both hosted runs passed File and the two Windows lanes. PR `37361106454` ran 33 R4 browser cases: **27 passed / 6 failed**. PostgreSQL completed **3,368 passed / 1 failed / 1,000 skipped** in 815.92 seconds. The marked-PostgreSQL execution gate reported no skipped PG contract; the actual failure was one fixture assertion.

- U08 source select was present, but its implicit label included every option description. The installed Playwright label engine reproduced that mismatch. Unique `useId` plus an explicit visible `aria-labelledby` fixes the actual accessible name; the exact selector and region/control visibility assertions remain. Two new naming regression cases pass.
- U07 had two rendered records containing the same original job ID: task projection and notice. The journey now selects the named original-task-center region before the exact ID and action.
- B07/B08 compared the raw creation echo, which lacks the authoritative version, against the initialized original chapter. Capture the original normalized GET before derived work, and compare exact content/document/version plus immutable history afterward.
- B09/B10 browser host tokens now use explicit request headers, with empty collaboration session/scope asserted. The prior localStorage setup incorrectly entered the collaboration picker.
- B09 interrupted-fork PG test assumed only two database projects. It now adds an owned unrelated sentinel, captures exact existing inventory, requires precisely one new target ID despite repeated create, and verifies unchanged prior metadata/source/history/neighbor. Cleanup is exact owned IDs only. No production fork guard was weakened.

All previous failures remain failures in their original runs. Corrected browser/PG execution is pending on the next published head. Local Chromium was not retried. Independent follow-up review remains BLOCKED, with no retry or alternative review route.
