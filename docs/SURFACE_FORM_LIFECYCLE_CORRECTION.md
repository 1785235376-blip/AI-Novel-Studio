# Story form lifecycle correction (2026-10-07)

Hosted frontend evidence for `90f211065fed2e2cd7c440365c949d954077bc50` (push artifact `11467843895`, pull-request artifact `11468785077`) reached real Story save/CAS/restore flows but failed the subsequent recovery and exact-label interactions:

- The Relationship journey could not locate the prefilled `关系描述` textarea.
- The Timeline/Foreshadowing journeys, and intermittently Character/Location, could not recover the immediate post-restore draft after reload.
- A Location journey reached recovery and Cancel but could not locate `反馈决定` after opening history.

### Confirmed causes and bounded changes

1. The existing forms accepted focus and typing while their save/restore operation was still settling. Their change handlers intentionally ignored changes when `saving` was true, including the period after the server response but before Story query invalidation completed. This created a real silent-edit-loss interval. The existing five forms now expose native `disabled` controls for that whole busy interval. Feedback controls use the same busy state. Once settlement ends, the next edit is synchronously persisted with the resulting digest/version and survives an immediate restart. No delays, retries or storage-key changes are substituted for this fix.

2. Playwright 1.62.1's exact `getByLabel` implementation includes textarea initial text and select option text when reading these implicit enclosing labels. For example, it compared `关系描述Original relationships` and `反馈决定已核对有意安排需要复查忽略此版本` against the shorter exact queries. Native accessible names and Testing Library's control-excluding label matching were already correct; this is not evidence of a general screen-reader naming defect. Explicit `aria-label` attributes now match the visible labels and provide stable exact names independent of control contents. Source inspection and a jsdom reproduction using the installed selector helpers confirmed this difference with native details both closed and open. No details-open-state change is supported by that evidence or included here.

The correction changes only the current Story forms and shared version-wrapper controls. All existing browser save, CAS, retained-draft, restore, feedback, source and geometry assertions remain unchanged. No browser-spec changes, backend changes, new owner, feature flag, shell or visual redesign are included.

### Verification

- New `StoryRecordLifecycle.test.tsx`: 20 additive cases. All five kinds are exercised under React StrictMode with deferred SAVE, RESTORE and FEEDBACK responses and separately deferred query settlement, followed by immediate editing, unmount/reopen, explicit local recovery and Cancel. Additional cases cover stable explicit labels for all structured controls and feedback fields.
- Initial lifecycle regression proof: all 10 initial SAVE/RESTORE cases failed on the old enabled controls before the runtime fix.
- Focused Story suite after correction: 93 passed, including all 20 new cases and unchanged original/core version tests.
- Frontend TypeScript and token guard: passed. Whitespace/diff checks: passed.
- Supplemental working-tree full frontend run: 1,447 passed, 8 existing skips (216 passed files, 2 existing skipped files). Concurrent integration work makes this supplemental rather than the final frozen receipt.
- Corrected hosted browser result: pending the next authorized checkpoint. Local browser execution was not attempted; the previous local Chromium denial remains respected. The lead owns final frozen aggregate checks and hosted publication receipts.
