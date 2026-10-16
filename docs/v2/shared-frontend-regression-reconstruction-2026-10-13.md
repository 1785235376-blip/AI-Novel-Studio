# Shared frontend regression reconstruction

Date: 2026-10-13
Base: `a696d4401a5cc0660f4e20de36b84910711c1fc1`

## Scope and behavior

This repair addresses the 23 original shared Graph, private TextAsset, and advisory Provider frontend failures, plus the enclosing workspace identity and read-denial gaps found during review. It leaves the separate entry-activation failure to its owning change.

- The graph admission wrapper forwards the exact original transport argument tuple and receiver. It no longer appends missing optional arguments. Captured project/scope admission, response validation, AbortSignal identity, and idempotency keys remain intact.
- New explicit run selections replace older selection reads. An explicitly reviewed command may supersede a pending run-list read. Superseded responses cannot overwrite the new selection or command result. In-flight commands cannot be superseded or duplicated.
- The enclosing workspace read guard receives the operation's cancellation signal. An already-cancelled read cannot revoke a newer selection through a late 401/403. Active read denials still clear private state. Every mutation continues through the guard without a cancellable read signal.
- Legacy interactive preflight and selected-run transport calls retain their established argument shape. They use logical owner/operation/epoch cancellation; LIST and persisted-run restoration also supply transport AbortSignals. A superseded legacy GET may finish on the network, but its result cannot be adopted.
- Synchronous subscriptions permanently retire an owner after project, session, actor, actor-workspace, collaboration-scope, or relevant local Host identity loss, including batched A→B→A. Host identity includes token, actor and epoch. A retired owner cannot regain authority without remounting.
- Identity retirement clears adopted parent data and visibly removes graph directories, saved titles, source bindings, candidates, previews and private run/model/asset receipts. Only changed local author text/title remains in disabled, read-only controls. This preserves the original default/unsaved-draft contract without exposing old server projections.
- Model and nested Provider capability denial also removes private metadata when a standalone caller does not unmount the panel. Same-run version changes do not restore a revoked receipt. Parent-rendered denial uses the model-specific notice and clears the run selection.
- The original private TextAsset archival disclosure is restored beside the same explicit model-call confirmation. Additional ownership, review, and non-publication boundaries remain visible.

No source, Host, route, digest, CAS, permission, or security gate is relaxed. Shared shell components, tokens, and the integrated manual-mask implementation are unchanged. No original test assertion or skip is edited.

## Verification checkpoints

| Check | Result |
| --- | --- |
| Eight original affected suites before repair | 270 passed, 23 failed |
| First two new modules against untouched base | 5 passed, 11 failed |
| Eight original affected suites plus first two new modules after repair | 309 passed |
| Full frontend before enclosing-shell expansion | 2,697 passed, 1 failed, 8 original skips |
| Remaining failure at that checkpoint | Original `EntryExperience.studio.test.tsx` activation acknowledgement; handled separately |
| Initial identity regression checkpoint before latch | 4 passed, 9 failed |
| Loaded-private-data identity checkpoint before redaction | 13 passed, 6 failed |
| Real-shell cancelled-read checkpoint before guarded cancellation | 3 passed, 4 failed |
| Final scoped union across 21 suites | 480 passed, including all 42 new regression tests |
| Final TypeScript and Vite production build | Passed; large-chunk advisory remains |
| Final UI design-token guard | Passed (52 files) |
| All 380 original frontend test/spec files | Byte-identical to base by SHA-256 comparison |
| Diff whitespace validation | Passed |
| Independent final lifecycle/security review | Cleared; exact final source hashes recorded |
| Playwright visual and geometry cases | Blocked before render: bundled Chromium headless executable unavailable |

The final combined full frontend run is owned by integration after the separately repaired entry activation is applied. The earlier full run is explicitly a checkpoint, not a claim that the expanded final branch has passed the full suite.

The browser blocker is an environment limitation, not a visual pass. Browser protections and snapshots were not changed, and no browser installation retry was attempted in this repair.

## Retained local evidence

Uncommitted logs are retained under `.runtime/frontend-regressions/`: `before.log`, `additive-before.log`, `affected-after.log`, `additive-after.log`, `full-frontend.log`, `identity-before.log`, `identity-loaded-before.log`, `identity-loaded-after.log`, `shell-read-before.log`, `shell-read-after.log`, `final-scoped-union.log`, `final-build.log`, `final-lint.log`, and `visual-geometry.log`.

`original-test-sha256.before` and `original-test-sha256.after` preserve the eight affected original hashes. `all-original-tests-integrity.json` records all 380 original files and their identical before/after hashes. `final-source-sha256` records the independently reviewed eight production files. Logs and runtime artifacts are not part of this commit.

No upload, push, deployment, or generated-inventory publication is performed by this change.
