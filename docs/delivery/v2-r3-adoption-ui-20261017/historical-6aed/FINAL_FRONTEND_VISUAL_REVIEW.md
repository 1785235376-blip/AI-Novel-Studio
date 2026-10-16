# Final frontend visual and evidence review

Independent read-only review at HEAD `6aed517611117771d767eb275a54773b24ba0300`, 2026-10-17 Asia/Shanghai. No product source, test, baseline or runtime was changed, and no test was rerun for this review.

## Verification and preservation

`frontend-verification.json` agrees with the retained runner receipts and logs: their recorded SHA-256 values match the current raw evidence files. The full frontend JSON reports 389 files, 4,204 passed, 6 skipped and zero failed. The corrected invocation actually changes the process directory to `frontend`; the original wrong-directory run (40 failures) remains retained and is not counted as passing evidence. TypeScript/Vite build passed, with the existing large-chunk warning retained. The original visual selection passed all seven checks (three original module baselines and four shell geometries). The original token guard passed its bounded 52-file scope; this is not a whole-feature CSS lint claim.

All four final frontend runner receipts contain the same 2,300-entry source SHA-256 map, identical before and after each run. I independently rehashed those 2,300 working files and found zero mismatches. The src receipt names current HEAD `6aed5176`; build/visual/token and File-browser receipts name earlier documentation/evidence HEAD `69df94ab`. Their frozen source maps are identical; these are not falsely relabelled as runs created at one Git commit.

Compared with the round base `95420aa59acb4c196d92e7292df0744098f6d2ff`, Git reports no changes to the original read-only `PromptAdoptionPanel.tsx`, `PromptAdoptionDisclosure.tsx`, `promptAdoptionClient.ts` or their existing panel/disclosure tests. The protected `frontend/src/ui` shell/tokens/primitives/test subtree, `frontend/tests/visual` baselines/tests and `frontend/playwright.visual.config.ts` also have no round diff. The original App entry source discussed below is unchanged in this round.

## Screens actually inspected

I opened the following six original File browser screenshots, without cropping, editing or generating replacements. All are under `r3-adoption-ui-browser-file-final-r1/test-results/v2-prompt-adoption-ui-live-10511-serves-its-exact-source-pin-prompt-adoption-ui-<viewport>/`:

| Viewport | Before confirming | After commit |
| --- | --- | --- |
| 1366×768 | `real-ui-adoption-before-confirm-checkbox.png` | `real-ui-adoption-committed-pin.png` |
| 1440×900 | `real-ui-adoption-before-confirm-checkbox.png` | `real-ui-adoption-committed-pin.png` |
| 1920×1080 | `real-ui-adoption-before-confirm-checkbox.png` | `real-ui-adoption-committed-pin.png` |

Across all three before-confirm images, the original shell remains intact: 56-pixel global header, scope bar, left assets, main CreativeCanvas, right inspector and bottom status bar. The inspector shows the readable r1 source, approved state, Chinese/emoji body, unchecked consent and disabled adoption button. The checkbox and full confirmation wording are visible. These are scrolled inspector views: the 1366/1440 captures do not show every target field at the same time, so they are not claimed as complete target-form screenshots. The 1920 view additionally shows target document v1, raw Shot identity and wrapped target/source digests.

Across all three committed images, the left original document card reads v2, the main canvas's `画面描述` contains the adopted Chinese/emoji text, and the existing read-only source panel displays the fixed r1 Asset/revision, result version 2, `仍然生效`, `可展示` and no newer revision at that capture. The columns remain separated, long source IDs fit or wrap, and the browser's recorded page scroll width equals each viewport width. A screenshot cannot prove invisible leading/trailing spaces; byte-exact content is established by the live spec's original-owner readback and retained decoded receipts.

Two visual boundaries remain explicit. The unchanged old read-only provenance panel clips the long 64-hex digest horizontally inside its inspector; the six images do not show every digest character there. Full exact pins are present in the decoded receipt/API assertions, not invented from pixels. The 1920 committed image also visibly reports the original upstream document as unavailable, so this evidence does not assert that every historical dependency is currently readable or usable. Neither observation was hidden or repaired by changing frozen read-only components or baselines.

## Actual runtime and model boundary

The retained File runner is PASS with no source drift. Playwright reports three passed real Edge viewport workflows. The launcher records original `LocalSessionBootstrap`, original File AssetLibraryService, no development sessions, no response mocks, and an explicitly enabled isolated child only. Ordinary before/after processes retain the literal production False gate and exact 503 control; their owned processes and the isolated backend/Vite are recorded stopped.

Each decoded viewport receipt records actual UI adoption POST 200; original target v1 becomes committed/reopened v2; the source remains r1; identical-request replay creates no further revision; advancing the source family does not silently move the adopted pin. The source binding proof observes the declared Character through its original owner at write time. It does not claim current dependency liveness, shot approval, rendering authority or model quality.

The launcher and decoded receipts say `model_execution: NOT_REQUESTED` and `model_counter: NOT_INSTRUMENTED`. This review therefore does not claim an instrumented zero-model-call count, a GPU/model generation PASS, or production adoption enablement. File runtime evidence, component/build/canonical visual evidence and pending/independent PostgreSQL browser evidence remain distinct. This is not a full V2 release.

## PostgreSQL entry readiness finding

While the separate PostgreSQL browser run remained active, its first viewport had already passed adoption POST, proof, main-frame synchronization and replay, then timed out reopening after a full page load. The retained error context showed Image/Prompt workspace after the helper had selected Novel/V2/Storyboard. Read-only source inspection identifies an existing entry race: `App.tsx:278` starts in Novel, while the overview query at 285 remains pending; scope navigation is already visible. The effect at 288–296 later applies the neutral project's default Image module unconditionally, without preserving an intervening explicit user module selection.

This is a preexisting product interaction race exposed by slow initialization, not proof of an adoption commit failure and not merely an incorrect locator. Waiting for the original one-time initial Image/IndependentStudio restoration before beginning a separate Novel navigation is a causally justified acceptance precondition; fixed sleeps or repeated clicks are not. The first failed PostgreSQL attempt must remain retained, and that wait must not be represented as validation of arbitrary navigation during initialization. No product or harness change was made by this review; the root/security owners decide the follow-up after their current bounded run stops. PostgreSQL browser success is not claimed here.
