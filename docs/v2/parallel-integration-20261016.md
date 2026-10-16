# Five-slice integration review — 2026-10-16

Verdict: **PASS for bounded slices; full product remains PARTIAL**. Tested source commit `6689935b223bc03a158b8966fd63e11d66767d29` on `work/dot-usability-handoff11-20261015`. The containing documentation commit identifies this report; it does not replace the tested source hash. No changes to implementation were made by the integration reviewer.

## Independent review identities

- Diagnostics: original `9c4fbfa68784a324bb2c48448baa38e6c72c93ea` → integrated `08903634ff6484b1051fada26ad9cf0ca209d6a4`; independent focused rerun **36 passed**, exit 0.
- Writer Room: original `50d6fa301b7db8d7e432fd689fba79070087dad0` → integrated `db83eb03ddcf74f220101db425883a7e5984b1f6`; independent focused rerun **14 passed**, exit 0.
- Branch comparison: original `771296530f4a0da8fa6f5f787ba55530f185ece3` → integrated `d3fe4f986716e242c9e44c22a8b76e54214ca458`; independent focused rerun **13 passed**, exit 0.
- Template authoring: original `e0f44c76220b10e02125bbd63cbe40220605d5f2` → integrated `3a6be5f76a0e4aa4d2b2444c01e92be12615fd4d`; independent focused rerun **46 passed**, exit 0.
- Character Mind: original `264eb4eeb014c487c6acb8f1f32fda82e3586b88` → integrated `6689935b223bc03a158b8966fd63e11d66767d29`; independent focused rerun **41 passed**, exit 0.

Template prerequisite: original `47b065948951277fda163447cf71924956abf5c8` → `a0be401297b1ffed74a63bee3fac069e1b2d0717`, followed by the Unicode fix above. Independent totals: 150 tests. The combined run adds 19 AppShell geometry tests and is not an additional product-completion count.

## Combined verification

- `cd frontend && node node_modules/vitest/vitest.mjs run --no-cache --maxWorkers=1 --minWorkers=1 src/experimental/WorkspaceDiagnostics.test.tsx src/experimental/WorkspaceToolsPanel.test.tsx src/experimental/WriterRoomPanel.test.tsx src/experimental/BranchComparisonReview.test.tsx src/experimental/BranchManuscriptPanel.test.tsx src/experimental/templateCopyEditing.test.ts src/experimental/TemplateCopyEditing.test.tsx src/experimental/DeclarativeTemplatePanels.test.tsx src/experimental/PersonalSkillBriefComposer.test.tsx src/experimental/personalSkillBrief.test.ts src/experimental/CharacterMindEvidenceReview.test.tsx src/experimental/StoryGraphPanel.test.tsx src/experimental/StoryGraphEvidenceReview.test.tsx src/novel/CharacterAuthorPanel.test.tsx src/ui/AppShell.test.tsx` — exit 0; 169 tests / 15 files.
- `cd frontend && node node_modules/typescript/bin/tsc -b --force --pretty false` — exit 0.
- `cd frontend && node node_modules/vite/bin/vite.js build` — exit 0.
- `python scripts/public_build.py --source .` — exit 0; 487 source files.
- `node scripts/check_ui_design_tokens.mjs` — exit 0.
- `cd frontend && node scripts/check-test-discovery.mjs` — exit 0.
- `git diff --check` — exit 0.

Vite emitted the existing >500 kB chunk warning. Test discovery only lists ownership; it does not run browser tests. Exact source hashes and retained command output are in the adjacent JSON. No implementation changed between source review, tests, typecheck and build.

## Closed review findings and preserved boundaries

- Template authoring now protects dirty edits against copy selection/catalog-copy replacement and requires explicit discard; section text and titles use Unicode code-point limits matching the original owner.
- Character Mind validates exact approved record identity, version, complete source pins, character/category/value and Unicode bounds. It leaves the character projection before the explicit author read and copies only into the existing pending form. Refresh and identity replacement invalidate old reads.
- Branch comparison uses own-property labels for malformed prototype keys, bounded Unicode excerpts and original segment indices. It adds no requests or merge authority.
- Diagnostics invalidates old previews on recheck/options/failure and binds explicit download to the original digest; Writer Room forwards exact pinned chapter revisions and preserves session decision notes through task switches and unknown outcomes.
- Original backend owners, CAS, review, permissions, explicit save/approval, UNKNOWN behavior and execution budgets remain authoritative. No new provider execution or automatic manuscript write.

## Limits and next acceptance

- No live HTTP/backend/File/PG tests rerun in integration. Template owner File persistence evidence is separate, not independently rerun.
- No browser, screenshot, native visual/accessibility/performance, Windows/GPU, real model/provider or external NLE acceptance.
- PUBLIC source closure is packaging hygiene, not real installer/container/release acceptance.
- Original typed response assumptions remain for diagnostics, Writer Room and complete branch comparison envelopes; newly introduced evidence/section helpers have focused malformed-input tests.
- P0 lifecycle remains platform-BLOCKED and untested; R3-GATE HOLD; production Prompt Adoption disabled; DeliveryCenter entitlement producer remains BLOCKED.
- No push, hosted CI, release, tag, deployment, paid service, user computer access, or new permissions.

The >=1000 persisted display-object target, deeper/executable subcanvas composition, Director multi-target proposal→approval→task→result loop, durable draft recovery, full historical replay, calibrated literary/model quality and complete runtime receipt/cost coverage remain open. Do not infer a delivery date or release readiness from these focused green tests. Continue independent bounded product slices under the current user authorization; do not retry denied P0 or browser routes. Main/V1/QingJian and user data are untouched.

Initial owner runs that used default shared Vitest cache are disclosed in their receipts. All independent and combined review reruns used --no-cache. Existing untracked historical verification receipts were preserved.
