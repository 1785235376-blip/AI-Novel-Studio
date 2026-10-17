# Caption import UI verification evidence

Execution completed 2026-10-17, approximately 00:32–00:34 UTC (coordination clock). Raw tool/test clock values are preserved unchanged. This evidence was collected in one exclusive frozen-source window at local base `46fff4797f6110e130256566b397cb08586e56c1`, with the uncommitted caption-import source delta.

## Commands and outcomes

All commands ran from `frontend/`, serially, without installs or dependency changes:

1. `node_modules/.bin/vitest run --maxWorkers=1 --minWorkers=1 --no-cache src/experimental/SubtitleTimelinePanel.import.test.tsx src/experimental/VoiceSubtitlePanels.test.tsx src/experimental/VoiceSubtitlePanels.additive.test.tsx src/experimental/captionTransferReview.test.ts` — exit 0; 4 suites, 71 unique tests passed. The new import suite contributes 38 tests; the other 33 are existing tests. These are mocked-transport jsdom UI checks and pure helper checks, not a real browser or full-stack acceptance test.
2. `node_modules/.bin/tsc -b --force` — exit 0; empty raw stdout/stderr log is expected.
3. `npm run build` — exit 0; production Vite build completed. Existing large-chunk and npm environment/version notices are retained verbatim.
4. `npm run lint` — exit 0; original UI token guard passed (52 files).

No verification command failed in this UI run. `vitest-r1.log`, `typecheck-r1.log`, `build-r1.log`, and `lint-r1.log` are byte-exact copies of raw combined output. No browser, screenshot, visual, live socket HTTP, PostgreSQL, provider, target-platform, full E2E or release acceptance was performed.

`before.sha256` and the four `after-*.sha256` receipts cover every regular file under `frontend/src/`. They are byte-identical at all five boundaries. They do not claim full-worktree/config/dependency hashing. Each original receipt and log was copied byte-for-byte and checked with `cmp`; `artifact-sha256.txt` binds those copied files. Broader independent verification is recorded separately by the parent/reviewer.

## Acceptance boundary

The separate backend File/TestClient run reported 109 passes and 96 PostgreSQL deselections. Those backend checks are separate evidence and do not turn mocked UI checks into browser/full E2E acceptance. The existing caption save owner retains local cues after an ambiguous failure and has no automatic retry, but this slice adds no durable UNKNOWN write lock, request-outcome reconciliation, or crash-persistent local draft.

## Independent source-slice review

The byte-exact `dot-caption-final-source-review-20261017.json` records `PASS_SOURCE_SLICE_REVIEW` against all seven final source/test SHA256 values. Independent UI execution reran the same 38 additive import cases with one worker, no cache and unchanged default timeouts: all passed, with 1,275 frontend files stable. `dot-caption-independent-ui-20261017{,-before,-after}.json` and its raw `.log` are retained unchanged. This is repeated confirmation, not 38 additional unique cases on top of the primary 71.

Independent backend execution passed 63 cases with 62 PostgreSQL cases deselected; 2,522 source entries remained stable. Its original receipt is `../caption-import-independent-backend-20261017.json`. These overlap the primary 109 backend checks and must not be summed as unique acceptance. The final review also confirms 1,271 protected entries unchanged and no source whitespace errors. Earlier static reviews are retained as historical findings; the final review identifies resolved lifecycle and inherited whitespace-loss issues. This remains source-slice approval, not browser/full E2E or release approval.
