# Local Audio trim timecode entry

Base: `f4a5327866007efa0a6bd3261086114216955a7b`.
Branch: `work/v2-audio-local-efficiency-20261019`.

Requirement: `AI_NOVEL_STUDIO_V2_FEATURE_MATRIX.md:274` (`AUDIO-13`, independent import/audition/trim/export), reconciled by `docs/v2/V2_REQUIREMENTS_LEDGER_20261019_R2.json` AUDIO-13. The ledger requires inspecting current behavior rather than inheriting historical missing/completion claims. Current local trim supported only millisecond positions. This bounded addition removes manual time-to-millisecond arithmetic when selecting an interval; it does not close AUDIO-13 or change acceptance status.

The optional collapsed helper accepts `M:SS[.sss]` and `HH:MM:SS[.sss]` within the original ten-minute source-position bound. Decimal digits convert exactly to integer milliseconds. An explicit apply action copies both endpoints into the existing fields. Malformed, equal or reversed endpoints leave those fields intact. Current range/source selection changes discard helper scratch values. Applying uses the original `changeParameter`, preserving dirty state, preview/consent invalidation, duration/codec validation, edit locks and separate queue/execute/review actions. Typing and applying make no HTTP requests.

Scope: Audio-only presentation in `StudioMediaExecutionPanel.tsx`, new `StudioAudioTrimTimecodes.tsx` and `studioAudioTrimTimecode.ts`, plus focused tests. No controller, transport, persistence, shell, style or DSH-reserved panel changes.

Verification:

- `node node_modules/vitest/vitest.mjs run src/creative/studioAudioTrimTimecode.test.ts src/creative/IndependentStudioAudioWav.test.tsx src/creative/studioAudioFades.additive.test.tsx --cache=false --maxWorkers=2 --minWorkers=1`: **90 passed / 3 files**, exit 0. Covers exact parsing, invalid ranges, original command shape, preview-consent invalidation including return to the original interval, duration limits, and edit locks. Existing WAV/fade receipt and unknown-result regressions passed.
- One `tsc -b`, then one `vite build`: exit 0. Vite reported a large-chunk advisory.
- `node ../scripts/check_ui_design_tokens.mjs`: **PASS (52 files)**.
- Mounted `IndependentStudioWorkspace` in existing Playwright Chromium, intercepted synthetic HTTP: **1366×768, 1440×900, 1920×1080 passed**. Checks exact fill, invalid-range preservation, no write requests, no page errors or document horizontal overflow. Header/context/sidebar/inspector/status remain 56/44/248/340/32 px.
- `git diff --check`: passed.

Browser evidence and temporary reproducible harness are retained outside the checkout at `D:/codex数据/2026-10-19/task-10/audio-timecode-evidence/`. `browser-results.json` records fixture scope, requests and geometry per viewport. The initial browser-fixture selector failure is retained separately; correcting that selector required no product change. This is frontend unit and mounted-browser evidence, **not full E2E, native codec, real-model, acoustic-quality, live authorization or full V2 acceptance**.

Normal sandbox commands failed before process creation with `helper_unknown_error: setup refresh had errors`; the formal `require_escalated` reviewer path succeeded. No sandbox/OS/security setting changed. Initial checkout failed on archived screenshot path lengths and Git removed it; command-local `-c core.longpaths=true` succeeded. Graphflow skill was read, but `graphflow_context` was not exposed; no result or savings is claimed. Existing local dependencies were reused without installation. No model/paid API, push or release operation occurred.

## P2 follow-up: retire stale Apply callbacks

Independent review of `ec80560e3f88be76c05363cea4e07932b9e51cc3` found that retaining an old Apply callback could replace a newer range or apply an old interval after changing sources. The original red evidence remains at `D:/codex数据/2026-10-19/task-5/parallel-media-cross-review/audio/review-handoff.json`. The exact independent `audio3` counterexample was copied into a focused regression and reproduced before fixing: `200–800` became `125–625`, and source B also received the old range. No HTTP writes occurred. Local reproduction receipt: `D:/codex数据/2026-10-19/task-10/audio-timecode-evidence/p2-before.json` (1 failed, 2 skipped).

The helper now grants Apply to its current committed render only. Layout-effect cleanup retires callbacks on rerender/unmount, and invoking the current valid callback consumes that grant before forwarding to the original controller. This fences source/range keyed remounts, scratch-input changes, disabled/owner changes and ABA renders while preserving current valid input and StrictMode setup. No original controller, permission, persistence or UI geometry changes were needed.

Bounded follow-up verification only:

- `studioAudioTrimTimecodes.review.test.tsx`: the three original independent probes plus three lifecycle/current-input checks **6 passed**, recorded in `p2-after.json`.
- One additional same-event-batch source/range check **1 passed, 6 skipped**, recorded in `p2-batch-boundary.json`.
- `git diff --check`: passed. The original 90-test run, TS/build and browser suite were not rerun for this repair.

The first follow-up run used an unsupported Vitest matcher in three new assertions; its failure receipt is preserved as `p2-after-matcher-failure.json`. Replacing it with the existing equivalent call-count and argument assertions produced the passing run. All follow-up evidence is local synthetic component/controller validation, not independent repair acceptance or full E2E. Original implementation commit and red evidence are preserved.
