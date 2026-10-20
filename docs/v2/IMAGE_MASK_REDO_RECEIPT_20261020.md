# Image mask local redo: bounded implementation receipt

Date: 2026-10-20. Base: `9ce5e243f925f6fb5141046758045c59b1dca46f`.

## Verified gap and scope

The original `BinaryMaskDraft.undo()` discarded the current packed bitplane. There was no `redo()`, `canRedo`, or redo control in `StudioBinaryMaskCanvas`.

This change closes that local editing gap in the existing Image mask owner. It is a bounded contribution to the Image mask/pixel-editor requirements (`IMAGE-08`, `IMAGE-14`), not acceptance or completion of either whole requirement.

Production changes are limited to:

- `frontend/src/creative/studioBinaryMask.ts`
- `frontend/src/creative/StudioBinaryMaskCanvas.tsx`

No API, source-verification, Save, execution, batch, Audio, Asset-browser, 3D, authentication, production shell, token, or keyboard-shortcut implementation was changed.

## Behavior

- Adds an explicit shared-primitive `重做蒙版编辑` button beside Undo.
- Undo and redo transfer ownership of exact packed bitplanes, with no image encoding, rescaling, or replay approximation.
- The combined undo/redo history remains at most the original 16 states: at most 2 MiB of retained history at 1024 × 1024. Current pixels and the optional in-progress stroke remain separate, as before.
- Committed pixel changes from brush, stroke, rectangle, polygon, or clear abandon and zero redo buffers. No-op edits, previews, invalid input, and cancelled strokes preserve redo.
- Disposal zeroes both history directions. A released draft cannot redo.
- The redo button uses the existing local edit/authority/source/busy/active-stroke checks and rejects stale render/revision callbacks, including rendered source/permission/mask ABA transitions.
- Redo clears obsolete polygon previews and notifies the original owner once for a real change. Returning to previously agreed pixels still requires fresh Save consent.
- Existing hotkeys and IME/text-input behavior are unchanged. Redo does not save, create an asset, call a model, or execute a task.

## Verification: passed

New targeted tests: **29 passed**, across three new files:

- `studioBinaryMask.redo.test.ts`: 12 cases. Exact mixed-operation round trips at 64 and 1024; shared memory bound; discarded-state zeroing; no-op/cancel preservation; serialization; disposal.
- `StudioBinaryMaskCanvas.redo.test.tsx`: 11 cases. Explicit control; callback/state fencing; permissions and busy ownership; active strokes/source errors; polygon invalidation; unchanged keyboard/IME/text input.
- `StudioManualMaskRedo.test.tsx`: 6 cases. Original-owner fresh consent and disposal on discard, source/project change, lost permission, and unmount. Native PNG decode and client reads are explicitly stubbed in this controller suite.

Existing focused compatibility regressions: **181 passed**, across seven existing files:

- `studioBinaryMask.test.ts`: 38
- `studioBinaryMask.polygon.test.ts`: 16
- `StudioBinaryMaskCanvas.test.tsx`: 20
- `StudioBinaryMaskCanvas.polygon.test.tsx`: 9
- `StudioManualMaskAuthoring.test.tsx`: 39
- `IndependentStudioManualMask.test.tsx`: 11
- `studioManualMaskContract.test.ts`: 48

Total: **210 passed across 10 files**. These are local unit/mounted-controller tests, not full end-to-end acceptance.

Additional checks:

- Final `node node_modules/typescript/bin/tsc --noEmit`: exit 0.
- `node node_modules/vite/bin/vite.js build`: passed, 2514 modules. Existing large-chunk warning remains; this is not a bundle-size acceptance claim.
- `node ../scripts/check_ui_design_tokens.mjs`: passed, 52 files. This guard scans the shared UI directory; the new button separately reuses the existing primitive and introduces no CSS/tokens.
- `node --check frontend/scripts/check-mask-redo-browser.mjs`: passed syntax validation only.
- `git diff --check`: passed.

## Verification: blocked / not claimed

Local browser screenshots and desktop geometry at 1366 × 768, 1440 × 900, and 1920 × 1080 are **BLOCKED and UNVERIFIED**.

The installed cloud Chromium process aborted before opening a page because the executor denied Unix socket creation. The supported escalation attempt failed before browser launch in the executor's sandbox mount setup. No sandbox permission was changed, and no user computer or alternate permission route was used.

A reproducible real-component synthetic fixture and browser helper are included:

- `frontend/tests/visual/studio-mask-redo.fixture.tsx`
- `frontend/scripts/check-mask-redo-browser.mjs`

They are not a successful visual run. On a permitted cloud browser executor, start this checkout's Vite server at `127.0.0.1:5187`, then run from `frontend`:

```sh
node scripts/check-mask-redo-browser.mjs http://127.0.0.1:5187 /path/to/unique-evidence
```

`PLAYWRIGHT_CHROMIUM_EXECUTABLE` can identify an installed Chromium; otherwise the helper uses Playwright's installed browser. The helper checks real canvas pixels and shared-shell/control geometry using a synthetic local blob, with API requests denied. It does not use a backend, model, credentials, or production assets.

No full-suite, backend, packaged-app, Windows-native, production-runtime, or full Image-workspace acceptance is claimed. No push, merge, Release, paid API call, or production execution was performed.

## Evidence and reproduction

Unique cloud evidence directory:

`/workspace/scratch/20a0022d2b33/studio-cloud-mask-redo-evidence-20261020/`

It contains `focused-tests.log` (204: 23 new + 181 existing), `owner-tests.log` (6 new), `typescript-final.log` (empty successful diagnostics), `vite-build.log`, `design-tokens.log`, `browser.log` (failed launch), and `browser-escalated.log` (failed executor setup). There are no browser screenshots or successful geometry results.

The isolated worktree is `/workspace/scratch/20a0022d2b33/studio-cloud-mask-redo-20261020`, branch `dot/image-mask-redo-20261020`. Dependencies were reused via a symlink to the existing cloud checkout's `frontend/node_modules`, not copied or reinstalled. The base checkout was kept clean.
